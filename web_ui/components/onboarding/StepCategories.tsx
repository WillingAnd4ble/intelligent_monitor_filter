"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";

const ARXIV_CATEGORIES = [
  { value: "cs.AI", desc: "Artificial Intelligence" },
  { value: "cs.CL", desc: "Computation & Language" },
  { value: "cs.LG", desc: "Machine Learning" },
  { value: "cs.CV", desc: "Computer Vision" },
  { value: "cs.RO", desc: "Robotics" },
  { value: "cs.SE", desc: "Software Engineering" },
  { value: "stat.ML", desc: "Machine Learning (Stats)" },
];

type Props = {
  categories: string[];
  topics: string[];
  authors: string[];
  onCategoriesChange: (v: string[]) => void;
  onTopicsChange: (v: string[]) => void;
  onAuthorsChange: (v: string[]) => void;
};

export function StepCategories({
  categories,
  topics,
  authors,
  onCategoriesChange,
  onTopicsChange,
  onAuthorsChange,
}: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-sage-700">
          What do you follow?
        </h2>
        <p className="mt-1 text-sm text-ink-secondary">
          Select the arXiv categories you want to monitor.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {ARXIV_CATEGORIES.map(({ value, desc }) => {
          const selected = categories.includes(value);
          return (
            <button
              key={value}
              type="button"
              onClick={() => {
                if (selected) {
                  onCategoriesChange(categories.filter((c) => c !== value));
                } else {
                  onCategoriesChange([...categories, value]);
                }
              }}
              className={cn(
                "rounded-md px-3 py-2 text-sm transition-colors",
                selected
                  ? "bg-sage-500 text-white"
                  : "bg-stone-100 text-ink-secondary hover:bg-stone-200",
              )}
            >
              <span className="font-mono font-medium">{value}</span>
              <span className="ml-1.5 text-xs opacity-75">{desc}</span>
            </button>
          );
        })}
      </div>

      <TagInput
        title="Topics / keywords"
        placeholder="e.g. transformer, LoRA, RLHF"
        values={topics}
        onChange={onTopicsChange}
      />

      <TagInput
        title="Authors (optional)"
        placeholder="e.g. Yann LeCun"
        values={authors}
        onChange={onAuthorsChange}
      />
    </div>
  );
}

function TagInput({
  title,
  placeholder,
  values,
  onChange,
}: {
  title: string;
  placeholder: string;
  values: string[];
  onChange: (v: string[]) => void;
}) {
  const [input, setInput] = useState("");

  const add = () => {
    const v = input.trim();
    if (v && !values.includes(v)) {
      onChange([...values, v]);
      setInput("");
    }
  };

  return (
    <div>
      <h3 className="text-sm font-medium text-ink-primary">{title}</h3>
      {values.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {values.map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 rounded-md bg-sage-50 px-2 py-1 font-mono text-xs text-sage-700 ring-1 ring-sage-200"
            >
              {t}
              <button
                type="button"
                className="text-ink-muted hover:text-ink-primary"
                aria-label={`Remove ${t}`}
                onClick={() => onChange(values.filter((x) => x !== t))}
              >
                &times;
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="mt-2 flex gap-2">
        <input
          className="min-w-[140px] flex-1 rounded-md border border-stone-200 px-3 py-1.5 text-sm outline-none ring-sage-500 focus:ring-2"
          value={input}
          placeholder={placeholder}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <button
          type="button"
          className="rounded-md border border-stone-200 px-3 py-1.5 text-xs font-semibold text-sage-700 hover:bg-sage-50"
          onClick={add}
        >
          Add
        </button>
      </div>
    </div>
  );
}
