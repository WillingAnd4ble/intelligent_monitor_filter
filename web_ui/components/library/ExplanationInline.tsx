"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  level: string;
  markdown: string;
  onClose: () => void;
};

export function ExplanationInline({ level, markdown, onClose }: Props) {
  return (
    <div
      role="region"
      aria-label="AI explanation"
      className="border-t border-sage-200 bg-sage-50 px-5 py-4"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-sage-700">
          ✦ AI explanation · {level}
        </span>
        <button
          type="button"
          onClick={onClose}
          className="text-sm font-medium text-amber-warm hover:underline"
        >
          Close
        </button>
      </div>
      <div className="explain-md text-sm leading-relaxed text-ink-secondary">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
      </div>
    </div>
  );
}
