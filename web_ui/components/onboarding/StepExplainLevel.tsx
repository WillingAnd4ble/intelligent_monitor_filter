"use client";

import { Briefcase, GraduationCap, Sparkles } from "lucide-react";
import { cn } from "@/lib/cn";
import type { LibraryExplanationLevel } from "@/lib/types/settings";

const LEVELS = [
  {
    value: "professional" as const,
    label: "Professional",
    desc: "Technical depth, assumes domain knowledge",
    icon: Briefcase,
  },
  {
    value: "student" as const,
    label: "Student",
    desc: "Clear explanations, defines key concepts",
    icon: GraduationCap,
  },
  {
    value: "kid" as const,
    label: "Simplified",
    desc: "Plain language, accessible to anyone",
    icon: Sparkles,
  },
];

type Props = {
  level: LibraryExplanationLevel;
  onChange: (v: LibraryExplanationLevel) => void;
};

export function StepExplainLevel({ level, onChange }: Props) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-sage-700">
          How should we explain papers?
        </h2>
        <p className="mt-1 text-sm text-ink-secondary">
          Choose how detailed the AI explanations should be.
        </p>
      </div>

      <div className="space-y-3">
        {LEVELS.map(({ value, label, desc, icon: Icon }) => (
          <button
            key={value}
            type="button"
            onClick={() => onChange(value)}
            className={cn(
              "flex w-full items-start gap-4 rounded-md border px-4 py-4 text-left transition-colors",
              level === value
                ? "border-sage-500 bg-sage-50"
                : "border-stone-200 hover:bg-stone-50",
            )}
          >
            <Icon
              className={cn(
                "mt-0.5 h-5 w-5 shrink-0",
                level === value ? "text-sage-500" : "text-ink-muted",
              )}
            />
            <div>
              <p className="text-sm font-semibold text-ink-primary">{label}</p>
              <p className="mt-0.5 text-sm text-ink-muted">{desc}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
