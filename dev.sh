#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# dev.sh — One-shot dev startup for the arXiv filter project (Windows + Git Bash)
#
# Spawns each long-running service in its own Windows Terminal tab:
#   1. Docker  (Postgres + Redis)  — detached, no window
#   2. Backend (FastAPI / uvicorn) — new tab
#   3. Celery worker               — new tab
#   4. Frontend (Next.js dev)      — new tab
#
# Usage:
#   ./dev.sh           # start everything
#   ./dev.sh stop      # tear everything down
#   ./dev.sh backend   # only backend + docker + celery
#   ./dev.sh frontend  # only frontend
# ---------------------------------------------------------------------------

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/web_ui"
VENV_ACTIVATE="$ROOT_DIR/.venv/Scripts/activate"
LAUNCH_DIR="$ROOT_DIR/.dev_launchers"

# ---------------------------------------------------------------------------
# Locate Git Bash explicitly. We CANNOT rely on `bash` from cmd/wt because
# Windows resolves bare `bash` to WSL first if it's installed.
#
# Strategy:
#   1. $EXEPATH — set automatically by Git Bash, points at its own bin/ dir.
#                 This is the most reliable source.
#   2. Common install locations (Program Files / user AppData / Scoop).
# ---------------------------------------------------------------------------
GIT_BASH=""

if [[ -n "$EXEPATH" ]]; then
    candidate_unix="$(cygpath -u "$EXEPATH")/bash.exe"
    if [[ -x "$candidate_unix" ]]; then
        GIT_BASH="$candidate_unix"
    fi
fi

if [[ -z "$GIT_BASH" ]]; then
    for candidate in \
        "/c/Program Files/Git/bin/bash.exe" \
        "/c/Program Files (x86)/Git/bin/bash.exe" \
        "$HOME/AppData/Local/Programs/Git/bin/bash.exe" \
        "/c/Users/$USER/AppData/Local/Programs/Git/bin/bash.exe" \
        "$HOME/scoop/apps/git/current/bin/bash.exe"; do
        if [[ -x "$candidate" ]]; then
            GIT_BASH="$candidate"
            break
        fi
    done
fi

if [[ -z "$GIT_BASH" ]]; then
    echo "ERROR: Could not find Git Bash (bash.exe) on this system."
    echo "       \$EXEPATH was: $EXEPATH"
    echo "       Set GIT_BASH manually or check your Git for Windows install."
    exit 1
fi

GIT_BASH_WIN="$(cygpath -w "$GIT_BASH")"
echo "==> Using Git Bash: $GIT_BASH_WIN"

# Detect Windows Terminal
USE_WT=0
if command -v wt.exe >/dev/null 2>&1; then
    USE_WT=1
fi

# ---------------------------------------------------------------------------
# Write per-service launcher scripts. We use stand-alone .sh files instead
# of `bash -c "..."` so that wt.exe never sees semicolons in its arg list
# (wt.exe parses `;` as a tab delimiter even inside quoted strings).
# ---------------------------------------------------------------------------
write_launchers() {
    mkdir -p "$LAUNCH_DIR"

    cat > "$LAUNCH_DIR/backend.sh" <<EOF
#!/usr/bin/env bash
trap 'echo; echo "[Backend exited with code \$? — press enter to close]"; read' EXIT
cd "$BACKEND_DIR"
source "$VENV_ACTIVATE"
echo "==> Starting FastAPI on http://localhost:8000"
python -m uvicorn app.main:app --reload --port 8000
EOF

    cat > "$LAUNCH_DIR/celery.sh" <<EOF
#!/usr/bin/env bash
# Always pause on exit so we can read errors
trap 'echo; echo "[Celery exited with code \$? — press enter to close]"; read' EXIT

cd "$BACKEND_DIR"
source "$VENV_ACTIVATE"

# Wait for Redis to be reachable (docker-compose may still be warming up)
echo "==> Waiting for Redis on localhost:6379..."
for i in {1..15}; do
    if (echo > /dev/tcp/localhost/6379) 2>/dev/null; then
        echo "    Redis is up."
        break
    fi
    if [[ \$i -eq 15 ]]; then
        echo "    ERROR: Redis not reachable after 15s. Is docker-compose running?"
        exit 1
    fi
    sleep 1
done

echo "==> Starting Celery worker (solo pool for Windows)"
# Use 'python -m celery' instead of bare 'celery' — Git Bash can't execute
# the venv's entry-point wrapper script (no .exe extension), but python -m
# works identically on every platform.
python -m celery -A app.worker.celery_app worker --pool=solo --loglevel=info --concurrency=1
EOF

    cat > "$LAUNCH_DIR/frontend.sh" <<EOF
#!/usr/bin/env bash
trap 'echo; echo "[Frontend exited with code \$? — press enter to close]"; read' EXIT
cd "$FRONTEND_DIR"
echo "==> Starting Next.js dev server on http://localhost:3000"
npm run dev
EOF

    chmod +x "$LAUNCH_DIR"/*.sh
}

# ---------------------------------------------------------------------------
# Spawners
# ---------------------------------------------------------------------------

start_docker() {
    echo "==> Starting Docker (Postgres + Redis)..."
    (cd "$BACKEND_DIR" && docker-compose up -d)
    echo "    waiting 3s for services to settle..."
    sleep 3
}

# Spawn one tab/window running a launcher script.
spawn_one() {
    local title="$1"
    local script_path="$2"

    if [[ $USE_WT -eq 1 ]]; then
        # Single wt.exe invocation per tab. No semicolons inside the arg list,
        # and we use the explicit Git Bash path so WSL can't hijack.
        wt.exe -w 0 nt --title "$title" "$GIT_BASH_WIN" "$script_path" &
    else
        # Fallback: classic cmd `start` opens a separate console window.
        MSYS2_ARG_CONV_EXCL="*" cmd //c start "$title" "$GIT_BASH_WIN" "$script_path"
    fi
}

# Open all three tabs in a SINGLE wt.exe call — much more reliable than
# multiple invocations because wt reuses one window naturally.
spawn_all_wt() {
    wt.exe \
        new-tab --title "Backend (FastAPI)" "$GIT_BASH_WIN" "$LAUNCH_DIR/backend.sh" \
        \; \
        new-tab --title "Celery Worker" "$GIT_BASH_WIN" "$LAUNCH_DIR/celery.sh" \
        \; \
        new-tab --title "Frontend (Next.js)" "$GIT_BASH_WIN" "$LAUNCH_DIR/frontend.sh" &
}

start_backend() {
    write_launchers
    if [[ $USE_WT -eq 1 ]]; then
        echo "==> Spawning Backend tab..."
        spawn_one "Backend (FastAPI)" "$LAUNCH_DIR/backend.sh"
        echo "==> Spawning Celery tab..."
        spawn_one "Celery Worker" "$LAUNCH_DIR/celery.sh"
    else
        echo "==> Spawning Backend window..."
        spawn_one "Backend (FastAPI)" "$LAUNCH_DIR/backend.sh"
        echo "==> Spawning Celery window..."
        spawn_one "Celery Worker" "$LAUNCH_DIR/celery.sh"
    fi
}

start_frontend() {
    write_launchers
    echo "==> Spawning Frontend..."
    spawn_one "Frontend (Next.js)" "$LAUNCH_DIR/frontend.sh"
}

start_all() {
    write_launchers
    start_docker

    if [[ $USE_WT -eq 1 ]]; then
        echo "==> Spawning all 3 tabs in one Windows Terminal window..."
        spawn_all_wt
    else
        spawn_one "Backend (FastAPI)" "$LAUNCH_DIR/backend.sh"
        spawn_one "Celery Worker" "$LAUNCH_DIR/celery.sh"
        spawn_one "Frontend (Next.js)" "$LAUNCH_DIR/frontend.sh"
    fi
}

restart_celery() {
    echo "==> Killing existing Celery worker..."
    powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'celery' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" 2>/dev/null || true
    sleep 1
    write_launchers
    echo "==> Spawning new Celery tab..."
    spawn_one "Celery Worker" "$LAUNCH_DIR/celery.sh"
    echo "==> Celery restarted."
}

stop_all() {
    echo "==> Stopping Docker services..."
    (cd "$BACKEND_DIR" && docker-compose down) || true

    echo "==> Killing dev processes (uvicorn, celery, next)..."
    taskkill //F //IM "node.exe" //T 2>/dev/null || true
    powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'uvicorn|celery' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" 2>/dev/null || true

    echo "==> Done."
}

# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

case "${1:-all}" in
    all|"")
        start_all
        echo
        echo "==> Launched. URLs:"
        echo "    Backend:  http://localhost:8000  (docs: /docs)"
        echo "    Frontend: http://localhost:3000"
        echo "    Postgres: localhost:5433"
        echo "    Redis:    localhost:6379"
        echo
        echo "    Stop with: ./dev.sh stop"
        ;;
    backend)
        start_docker
        start_backend
        ;;
    frontend)
        start_frontend
        ;;
    docker)
        start_docker
        ;;
    celery|restart-celery)
        restart_celery
        ;;
    stop|down)
        stop_all
        ;;
    *)
        echo "Usage: $0 [all|backend|frontend|docker|celery|stop]"
        exit 1
        ;;
esac
