"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { putSettings, triggerPipeline } from "@/lib/api";
import { cn } from "@/lib/cn";
import { StepCategories } from "./StepCategories";
import { StepGoal } from "./StepGoal";
import { StepExplainLevel } from "./StepExplainLevel";
import type { LibraryExplanationLevel } from "@/lib/types/settings";

const STEPS = ["Categories", "Goal", "Explain level"];

export function OnboardingWizard() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1
  const [categories, setCategories] = useState<string[]>([]);
  const [topics, setTopics] = useState<string[]>([]);
  const [authors, setAuthors] = useState<string[]>([]);

  // Step 2
  const [filteringGoal, setFilteringGoal] = useState("");

  // Step 3
  const [explanationLevel, setExplanationLevel] =
    useState<LibraryExplanationLevel>("professional");

  const canContinue = step === 1 ? categories.length > 0 : true;

  const handleComplete = async () => {
    setSaving(true);
    setError(null);
    try {
      await putSettings({
        categories,
        topics,
        authors,
        filtering_goal: filteringGoal || null,
        library_explanation_level: explanationLevel,
      });
      await triggerPipeline();
      router.push("/dashboard?first_run=true");
    } catch {
      setError("Could not save settings. Please try again.");
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-8 shadow-card">
      {/* Step indicator */}
      <div className="mb-8 flex items-center justify-center">
        {STEPS.map((label, i) => {
          const num = i + 1;
          const active = num === step;
          const done = num < step;
          return (
            <div key={label} className="flex items-center">
              {i > 0 && (
                <div
                  className={cn(
                    "h-px w-10 sm:w-16",
                    done ? "bg-sage-500" : "bg-stone-200",
                  )}
                />
              )}
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold",
                    active
                      ? "bg-sage-500 text-white"
                      : done
                        ? "bg-sage-200 text-sage-700"
                        : "bg-stone-100 text-ink-muted",
                  )}
                >
                  {num}
                </div>
                <span
                  className={cn(
                    "mt-1.5 hidden text-xs sm:block",
                    active ? "font-medium text-sage-700" : "text-ink-muted",
                  )}
                >
                  {label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Step content */}
      {step === 1 && (
        <StepCategories
          categories={categories}
          topics={topics}
          authors={authors}
          onCategoriesChange={setCategories}
          onTopicsChange={setTopics}
          onAuthorsChange={setAuthors}
        />
      )}
      {step === 2 && (
        <StepGoal goal={filteringGoal} onChange={setFilteringGoal} />
      )}
      {step === 3 && (
        <StepExplainLevel
          level={explanationLevel}
          onChange={setExplanationLevel}
        />
      )}

      {error && <p className="mt-4 text-sm text-red-800">{error}</p>}

      {/* Navigation */}
      <div className="mt-8 flex items-center justify-between">
        <div>
          {step > 1 && (
            <button
              type="button"
              className="text-sm font-medium text-sage-700 hover:text-sage-500"
              onClick={() => setStep(step - 1)}
            >
              Back
            </button>
          )}
        </div>

        <div className="flex items-center gap-4">
          <Link
            href="/dashboard"
            className="text-sm text-ink-muted hover:text-ink-secondary"
          >
            Skip for now
          </Link>

          {step < 3 ? (
            <button
              type="button"
              disabled={!canContinue}
              className="rounded-md bg-sage-500 px-6 py-2.5 text-sm font-semibold text-white hover:bg-sage-700 disabled:opacity-50"
              onClick={() => setStep(step + 1)}
            >
              Continue
            </button>
          ) : (
            <button
              type="button"
              disabled={saving}
              className="rounded-md bg-sage-500 px-6 py-2.5 text-sm font-semibold text-white hover:bg-sage-700 disabled:opacity-60"
              onClick={handleComplete}
            >
              {saving ? "Saving\u2026" : "Finish setup"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
