"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PaperListItem } from "@/lib/types";
import { ExternalLink, Trash2 } from "lucide-react";
import { ExplanationInline } from "./ExplanationInline";
import { cn } from "@/lib/cn";
import { explainPaper, getExplainStatus } from "@/lib/api";

type Props = {
  paper: PaperListItem;
  onRemove: (id: string) => void;
};

export function LibraryCard({ paper, onRemove }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [payload, setPayload] = useState<{
    level: string;
    explanation: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const startPolling = useCallback(
    (taskId: string) => {
      stopPolling();
      let attempts = 0;
      pollRef.current = setInterval(async () => {
        attempts++;
        if (attempts > 90) {
          stopPolling();
          setLoading(false);
          setError("Explanation timed out. Try again.");
          return;
        }
        try {
          const res = await getExplainStatus(paper.user_paper_id, taskId);
          if (res.status === "ready" && res.level && res.explanation) {
            stopPolling();
            setPayload({ level: res.level, explanation: res.explanation });
            setOpen(true);
            setLoading(false);
          } else if (res.status === "error") {
            stopPolling();
            setLoading(false);
            setError(res.detail ?? "Explanation failed.");
          }
        } catch {
          stopPolling();
          setLoading(false);
          setError("Failed to check status.");
        }
      }, 3000);
    },
    [paper.user_paper_id, stopPolling],
  );

  const handleExplain = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    if (payload) {
      setOpen(true);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await explainPaper(paper.user_paper_id);
      if (res.status === "ready" && res.level && res.explanation) {
        setPayload({ level: res.level, explanation: res.explanation });
        setOpen(true);
        setLoading(false);
      } else if (res.status === "processing" && res.task_id) {
        startPolling(res.task_id);
      } else if (res.status === "error") {
        setLoading(false);
        setError(res.detail ?? "Explanation failed.");
      }
    } catch {
      setLoading(false);
      setError("Request failed.");
    }
  };

  return (
    <div className="rounded-lg border border-stone-200 bg-white shadow-card">
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            {paper.agent_score != null && (
              <span className="font-mono text-sm font-semibold text-sage-700">
                {paper.agent_score.toFixed(1)}
              </span>
            )}
            <h2 className="mt-1 text-base font-semibold text-ink-primary">
              {paper.title}
            </h2>
            <p className="mt-1 font-mono text-xs text-ink-muted">
              {paper.paper_id}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a
              href={paper.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-md border border-stone-200 px-2.5 py-1.5 text-xs font-medium text-ink-primary hover:bg-stone-100"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              arXiv
            </a>
            <button
              type="button"
              aria-expanded={open}
              onClick={() => void handleExplain()}
              disabled={loading}
              className={cn(
                "rounded-md border border-sage-200 px-2.5 py-1.5 text-xs font-semibold text-sage-700 hover:bg-sage-50",
                loading && "opacity-60",
              )}
            >
              {loading ? "Generating…" : open ? "Hide" : "Explain"}
            </button>
            <button
              type="button"
              onClick={() => onRemove(paper.user_paper_id)}
              className="inline-flex items-center gap-1 rounded-md border border-stone-200 px-2.5 py-1.5 text-xs text-ink-secondary hover:bg-red-50 hover:text-red-800"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Remove
            </button>
          </div>
        </div>
        {loading && (
          <p className="mt-3 text-xs text-ink-muted animate-pulse">
            Generating explanation — this may take a minute…
          </p>
        )}
        {error && (
          <p className="mt-3 text-xs text-red-700">{error}</p>
        )}
      </div>
      {open && payload && (
        <ExplanationInline
          level={payload.level}
          markdown={payload.explanation}
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  );
}
