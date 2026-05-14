"""
Pipeline timing harness for thesis section 4.4 (Task 16).

Measures the wall-clock duration of the `light` and `full` filtering cycles by
driving the real backend over HTTP and reading the structured `pipeline.start` /
`pipeline.end` JSON telemetry lines that `_run_pipeline` emits to the Celery
worker log.

Design — why one fresh user per sample, full-then-light:
  Each measurement run registers a NEW user, sets a filtering goal (this chains
  GoalDistiller -> run_full_pipeline because onboarding_completed is False on a
  fresh user), waits for the full cycle, then CHANGES the goal (now chains
  GoalDistiller -> run_light_pipeline because onboarding_completed flipped True).
  Both cycles are measured. The light cycle is intentionally dedup-heavy: in real
  usage, light mode only ever runs for an already-onboarded user who therefore
  already has UserPaper rows — so this is the representative light-mode scenario,
  matching the thesis 4.2.2 walkthrough.

Prerequisites:
  - Postgres + Redis up (docker-compose up -d)
  - API server running:   uvicorn app.main:app          (port 8000)
  - Celery worker running WITH ITS STDOUT REDIRECTED TO A FILE, e.g.:
        celery -A app.worker.celery_app worker --pool=solo --loglevel=info > worker.log 2>&1
    Pass that file path with --worker-log.

Usage (from the testing/ directory):
    python measure_pipeline.py --worker-log ../backend/worker.log --runs 3

Output:
    testing/perf_runs_summary.txt   — median + min/max for light and full,
                                      plus the raw per-run table.
"""

import argparse
import json
import statistics
import sys
import time
import uuid
from pathlib import Path

import httpx


# Two distinct, realistic filtering goals. They MUST differ so the second
# settings PUT is registered as a goal change and triggers the light chain.
GOAL_A = (
    "Multi-agent LLM systems for autonomous software engineering, "
    "especially coordination protocols between specialised agents."
)
GOAL_B = (
    "LLM-based automated program repair and code generation agents "
    "evaluated on real-world bug datasets."
)
CATEGORIES = ["cs.AI"]
DEEP_SCAN_LIMIT = 5

# How long to wait for a single cycle before giving up.
CYCLE_TIMEOUT_S = 25 * 60
POLL_INTERVAL_S = 2.0


def _extract_json(line: str) -> dict | None:
    """Pull the JSON object out of a log line that may have a logging prefix."""
    start = line.find("{")
    if start == -1:
        return None
    try:
        return json.loads(line[start:])
    except json.JSONDecodeError:
        return None


class WorkerLogTail:
    """Tails the worker log file, yielding parsed pipeline.* telemetry events."""

    def __init__(self, path: Path):
        self.path = path
        self._fh = open(path, "r", encoding="utf-8", errors="replace")
        self._fh.seek(0, 2)  # seek to end — ignore anything already there

    def seek_to_end(self):
        self._fh.seek(0, 2)

    def wait_for_pipeline_end(self, mode: str, timeout_s: float) -> tuple[dict, list[dict]]:
        """Block until a `pipeline.end` event with the given mode appears.

        Returns (end_event, stage_events) where end_event includes duration_ms and
        stage_events is the list of pipeline.stage events seen between start and end.
        Raises TimeoutError if nothing matching shows up within timeout_s. A
        `pipeline.skipped_locked` event for the same mode is a hard error.
        """
        deadline = time.monotonic() + timeout_s
        saw_start = False
        stage_events: list[dict] = []
        while time.monotonic() < deadline:
            line = self._fh.readline()
            if not line:
                time.sleep(POLL_INTERVAL_S)
                continue
            evt = _extract_json(line)
            if not evt or "event" not in evt:
                continue
            if evt["event"] == "pipeline.start" and evt.get("mode") == mode:
                saw_start = True
                stage_events = []
            elif evt["event"] == "pipeline.stage" and evt.get("mode") == mode and saw_start:
                stage_events.append(evt)
            elif evt["event"] == "pipeline.skipped_locked" and evt.get("mode") == mode:
                raise RuntimeError(
                    f"pipeline.skipped_locked for mode={mode} — a previous run for "
                    f"this user is still holding the Redis lock. Runs must be sequential."
                )
            elif evt["event"] == "pipeline.end" and evt.get("mode") == mode:
                if not saw_start:
                    # An end without a matching start we saw — likely a stale line; keep going.
                    continue
                return evt, stage_events
        raise TimeoutError(
            f"No pipeline.end for mode={mode} within {timeout_s:.0f}s. "
            f"Check the worker is running and pointed at the same Redis."
        )

    def close(self):
        self._fh.close()


def register_and_login(client: httpx.Client, email: str, password: str) -> None:
    """Register a fresh user, then log in so the JWT cookie is set on `client`.

    Note: auth router is mounted at /auth (not /api/v1/auth) in this codebase.
    """
    r = client.post("/auth/register", json={"email": email, "password": password})
    if r.status_code not in (200, 201):
        # If the user somehow already exists, fall through to login.
        if r.status_code != 400:
            r.raise_for_status()
    r = client.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    if "access_token" not in client.cookies:
        raise RuntimeError("login did not set an access_token cookie")


def put_goal(client: httpx.Client, goal: str, *, first_time: bool) -> None:
    """PUT the settings goal. On first_time, also set categories + deep_scan_limit."""
    payload: dict = {"filtering_goal": goal}
    if first_time:
        payload["categories"] = CATEGORIES
        payload["deep_scan_limit"] = DEEP_SCAN_LIMIT
    r = client.put("/api/v1/settings/", json=payload)
    r.raise_for_status()


def measure_one_user(
    client: httpx.Client, tail: WorkerLogTail, run_index: int
) -> tuple[dict, list[dict], dict, list[dict]]:
    """Drive one fresh user through a full cycle then a light cycle.

    Returns (full_end, full_stages, light_end, light_stages).
    """
    email = f"perf_{int(time.time())}_{run_index}_{uuid.uuid4().hex[:6]}@test.local"
    password = "perf-measure-123"
    print(f"  [run {run_index}] registering {email}")
    register_and_login(client, email, password)

    # --- FULL cycle: first goal on a fresh (onboarding_completed=False) user ---
    print(f"  [run {run_index}] setting goal A -> expecting FULL cycle")
    tail.seek_to_end()
    put_goal(client, GOAL_A, first_time=True)
    full_evt, full_stages = tail.wait_for_pipeline_end("full", CYCLE_TIMEOUT_S)
    full_s = full_evt["duration_ms"] / 1000.0
    print(
        f"  [run {run_index}] FULL done in {full_s:.1f}s "
        f"(phase1={full_evt.get('phase1_count')}, phase2={full_evt.get('phase2_count')}, "
        f"top_picks={full_evt.get('top_pick_count')})"
    )

    # --- LIGHT cycle: changed goal on the now-onboarded user ---
    print(f"  [run {run_index}] changing goal to B -> expecting LIGHT cycle")
    tail.seek_to_end()
    put_goal(client, GOAL_B, first_time=False)
    light_evt, light_stages = tail.wait_for_pipeline_end("light", CYCLE_TIMEOUT_S)
    light_s = light_evt["duration_ms"] / 1000.0
    print(
        f"  [run {run_index}] LIGHT done in {light_s:.1f}s "
        f"(phase1={light_evt.get('phase1_count')})"
    )

    # Clear the cookie so the next run starts from a clean client.
    client.cookies.clear()
    return full_evt, full_stages, light_evt, light_stages


def summarise(label: str, durations_s: list[float]) -> str:
    med = statistics.median(durations_s)
    lo = min(durations_s)
    hi = max(durations_s)
    return (
        f"{label:8s}  median={med/60:.2f} min  "
        f"min={lo/60:.2f} min  max={hi/60:.2f} min  "
        f"(raw seconds: {', '.join(f'{d:.1f}' for d in durations_s)})"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure light/full pipeline cycle timings.")
    ap.add_argument(
        "--worker-log",
        required=True,
        type=Path,
        help="Path to the Celery worker log file (worker stdout redirected to a file).",
    )
    ap.add_argument("--runs", type=int, default=3, help="Number of measurement runs (default 3).")
    ap.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend API base URL (default http://localhost:8000).",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "perf_runs_summary.txt",
        help="Output summary file (default testing/perf_runs_summary.txt).",
    )
    args = ap.parse_args()

    if not args.worker_log.exists():
        print(f"ERROR: worker log not found: {args.worker_log}", file=sys.stderr)
        print(
            "Start the worker with stdout redirected, e.g.:\n"
            "  celery -A app.worker.celery_app worker --pool=solo --loglevel=info > worker.log 2>&1",
            file=sys.stderr,
        )
        return 1

    tail = WorkerLogTail(args.worker_log)
    full_durations: list[float] = []
    light_durations: list[float] = []
    raw_rows: list[str] = []
    # stage name -> list of per-run durations in seconds (from full-mode runs)
    stage_durations: dict[str, list[float]] = {}

    print(f"Measuring {args.runs} run(s) against {args.base_url}")
    print(f"Watching worker log: {args.worker_log}\n")

    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        for i in range(1, args.runs + 1):
            try:
                full_evt, full_stages, light_evt, light_stages = measure_one_user(
                    client, tail, i
                )
            except (TimeoutError, RuntimeError, httpx.HTTPError) as e:
                print(f"  [run {i}] ABORTED: {e}", file=sys.stderr)
                tail.close()
                print(
                    "\nPartial data only — fix the issue above and re-run. "
                    "No summary written.",
                    file=sys.stderr,
                )
                return 2
            full_s = full_evt["duration_ms"] / 1000.0
            light_s = light_evt["duration_ms"] / 1000.0
            full_durations.append(full_s)
            light_durations.append(light_s)
            # Per-stage breakdown from the full-mode run (it exercises every stage).
            for st in full_stages:
                stage_durations.setdefault(st["stage"], []).append(
                    st["duration_ms"] / 1000.0
                )
            raw_rows.append(
                f"run {i}: full={full_s:.1f}s "
                f"(p1={full_evt.get('phase1_count')}, p2={full_evt.get('phase2_count')}, "
                f"top={full_evt.get('top_pick_count')})  |  "
                f"light={light_s:.1f}s (p1={light_evt.get('phase1_count')})  |  "
                f"full stages: "
                + ", ".join(f"{s['stage']}={s['duration_ms']/1000.0:.1f}s" for s in full_stages)
            )
            print()

    tail.close()

    full_med = statistics.median(full_durations)
    light_med = statistics.median(light_durations)
    ratio = full_med / light_med if light_med else float("nan")

    # Per-stage medians, in the canonical pipeline order.
    stage_order = ["scrape", "rrf", "phase1", "marker", "deep_reader", "notify"]
    stage_lines = []
    for st in stage_order:
        if st in stage_durations:
            vals = stage_durations[st]
            med = statistics.median(vals)
            unit = f"{med*1000:.0f} ms" if med < 1.0 else f"{med:.1f} s"
            stage_lines.append(
                f"  {st:12s} median={unit:>10s}  "
                f"(raw: {', '.join(f'{v:.2f}s' for v in vals)})"
            )

    lines = [
        f"Pipeline timing summary — Task 16 — N={args.runs} runs",
        f"Generated by testing/measure_pipeline.py",
        "",
        "=" * 70,
        "CYCLE DURATIONS (use these for thesis section 4.4.1)",
        "=" * 70,
        summarise("light", light_durations),
        summarise("full", full_durations),
        "",
        f"full median is ~{ratio:.1f}x the light median",
        "",
        "=" * 70,
        "STAGE BREAKDOWN — full-mode runs (use these for section 4.4.2)",
        "=" * 70,
        *stage_lines,
        "",
        "=" * 70,
        "RAW PER-RUN DATA",
        "=" * 70,
        *raw_rows,
        "",
        "Notes for filling in <N> placeholders in section 4.4:",
        f"  4.4.1 light median   = {light_med/60:.2f} min "
        f"(range {min(light_durations)/60:.2f}-{max(light_durations)/60:.2f} min)",
        f"  4.4.1 full median    = {full_med/60:.2f} min "
        f"(range {min(full_durations)/60:.2f}-{max(full_durations)/60:.2f} min)",
        f"  4.4.1 full/light ratio = ~{ratio:.1f}x",
        "  4.4.2 stage medians are in the STAGE BREAKDOWN block above. The 'notify'",
        "        bucket also includes the result-save loop + top-pick selection.",
        "  4.2 references two <N> cycle-time mentions — use the full median for the",
        "      first-run mention (4.2.1) and the light median for the goal-change",
        "      mention (4.2.2).",
    ]
    summary = "\n".join(lines) + "\n"
    args.out.write_text(summary, encoding="utf-8")

    print("=" * 70)
    print(summary)
    print(f"Written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
