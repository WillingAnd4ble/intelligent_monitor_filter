"use client";

import { useState, type CSSProperties } from "react";
import type { PaperListItem } from "@/lib/types";
import { cn } from "@/lib/cn";
import { ExternalLink, FileText } from "lucide-react";

function scoreStripStyle(score: number | null): CSSProperties {
  if (score == null) {
    return {
      background: "linear-gradient(90deg, #e2d9c8, #c9cfa8)",
    };
  }
  const t = Math.min(10, Math.max(0, score)) / 10;
  return {
    background: `linear-gradient(90deg, #d6d0c4 0%, #a8b596 ${40 + t * 20}%, #6b7c4f ${70 + t * 30}%)`,
  };
}

type Props = {
  paper: PaperListItem;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
};

export function PaperCard({ paper, onAccept, onReject }: Props) {
  const [expanded, setExpanded] = useState(false);
  const score = paper.agent_score;

  return (
    <article
      className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-card"
      aria-label={paper.title}
    >
      <div
        className="h-2 w-full"
        style={scoreStripStyle(score)}
        aria-hidden
      />
      <div className="relative p-6 pt-5">
        {score != null && (
          <span
            className="absolute right-5 top-5 rounded-md bg-sage-50 px-2 py-1 font-mono text-sm font-semibold text-sage-700 ring-1 ring-sage-200"
            aria-label={`Score: ${score} out of 10`}
          >
            {score.toFixed(1)}
          </span>
        )}
        <div className="mb-3 flex flex-wrap items-center gap-2 pr-16">
          <span className="font-mono text-xs text-ink-muted">{paper.paper_id}</span>
        </div>
        <h2 className="text-lg font-semibold leading-snug text-ink-primary">
          {paper.title}
        </h2>
        <p className="mt-2 text-sm text-ink-secondary">
          {paper.authors.slice(0, 4).join(", ")}
          {paper.authors.length > 4 ? `, +${paper.authors.length - 4} more` : ""}
        </p>
        {paper.agent_explanation && (
          <div className="mt-4 rounded-md border border-sage-200 bg-sage-50 px-4 py-3 text-sm leading-relaxed text-ink-primary">
            <strong className="text-sage-700">Why it fits</strong>
            <p className="mt-1 whitespace-pre-wrap">{paper.agent_explanation}</p>
          </div>
        )}
        <p
          className={cn(
            "mt-4 text-sm leading-relaxed text-ink-secondary",
            !expanded && "line-clamp-3",
          )}
        >
          {paper.abstract}
        </p>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="mt-1 text-sm font-medium text-amber-warm hover:underline"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
        <div className="mt-5 flex flex-wrap gap-2">
          <a
            href={paper.source_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-stone-200 bg-white px-3 py-2 text-sm font-medium text-ink-primary hover:bg-stone-100"
          >
            <ExternalLink className="h-4 w-4" />
            arXiv
          </a>
          <a
            href={paper.source_url.replace("/abs/", "/pdf/") + ".pdf"}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-stone-200 bg-white px-3 py-2 text-sm font-medium text-ink-primary hover:bg-stone-100"
          >
            <FileText className="h-4 w-4" />
            PDF
          </a>
          <button
            type="button"
            onClick={() => onAccept(paper.user_paper_id)}
            className="rounded-md bg-sage-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sage-700"
          >
            Accept
          </button>
          <button
            type="button"
            onClick={() => onReject(paper.user_paper_id)}
            className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-ink-secondary hover:bg-stone-100"
          >
            Reject
          </button>
        </div>
      </div>
    </article>
  );
}
