"use client";

import { usePipeline } from "@/contexts/pipeline-context";
import { cn } from "@/lib/cn";

export function PipelinePill() {
  const { phase, stateLabel, progress } = usePipeline();

  const running = phase === "running";
  const err = phase === "error";

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2.5 rounded-lg border px-4 py-2 font-mono text-xs",
        err && "border-stone-400 bg-stone-100 text-stone-700",
        !err && running && "border-moss/30 bg-moss-light text-moss",
        !err && !running && "border-moss/30 bg-moss-light text-moss",
      )}
      role="status"
      aria-live="polite"
    >
      <span
        className={cn(
          "h-2.5 w-2.5 rounded-full bg-moss",
          running && "motion-safe:animate-pulse",
        )}
        aria-hidden
      />
      <span>
        {err
          ? "Error"
          : running
            ? `${stateLabel} · ${progress}%`
            : stateLabel}
      </span>
    </div>
  );
}
