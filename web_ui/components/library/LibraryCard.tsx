"use client";

import { useState } from "react";
import type { PaperListItem } from "@/lib/types";
import { ExternalLink, Trash2 } from "lucide-react";
import { ExplanationInline } from "./ExplanationInline";
import { cn } from "@/lib/cn";

type Props = {
  paper: PaperListItem;
  onRemove: (id: string) => void;
  onExplain: (id: string) => Promise<{ level: string; explanation: string }>;
};

export function LibraryCard({ paper, onRemove, onExplain }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [payload, setPayload] = useState<{ level: string; explanation: string } | null>(
    null,
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
    try {
      const res = await onExplain(paper.user_paper_id);
      setPayload(res);
      setOpen(true);
    } finally {
      setLoading(false);
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
            <p className="mt-1 font-mono text-xs text-ink-muted">{paper.paper_id}</p>
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
              {loading ? "…" : open ? "Hide" : "Explain"}
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
