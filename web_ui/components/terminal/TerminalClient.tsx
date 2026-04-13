"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getSettings, putSettings } from "@/lib/api";
import type { UserSettings } from "@/lib/types/settings";
import { usePipeline } from "@/contexts/pipeline-context";
import { cn } from "@/lib/cn";

const CONTENT_OPTIONS = [
  { value: "introduction", label: "Introduction" },
  { value: "methodology", label: "Methodology" },
  { value: "experiments", label: "Experiments" },
  { value: "conclusions", label: "Conclusions" },
] as const;

function emptySettings(): UserSettings {
  return {
    filtering_goal: "",
    categories: [],
    topics: [],
    authors: [],
    content_interest: [],
    library_explanation_level: "professional",
    notification_email: null,
    notification_time: null,
    deep_scan_limit: 10,
    pdf_parser_mode: "pypdfium",
  };
}

export function TerminalClient() {
  const qc = useQueryClient();
  const { runTrigger } = usePipeline();
  const [tab, setTab] = useState<
    "filtering" | "library" | "pipeline" | "account"
  >("filtering");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
  });

  const [s, setS] = useState<UserSettings>(emptySettings());

  useEffect(() => {
    if (data) setS({ ...emptySettings(), ...data });
  }, [data]);

  const mutation = useMutation({
    mutationFn: putSettings,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  const save = (patch: Partial<UserSettings>) => {
    const next = { ...s, ...patch };
    setS(next);
    mutation.mutate(next);
  };

  const errMsg =
    error && typeof error === "object" && "message" in error
      ? String((error as { message?: string }).message)
      : null;

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-sage-700">Terminal</h1>
      </div>

      <nav
        className="mb-6 flex flex-wrap gap-2 border-b border-stone-200 pb-1"
        aria-label="Settings sections"
      >
        {(
          [
            ["filtering", "Filtering"],
            ["library", "Library"],
            ["pipeline", "Pipeline"],
            ["account", "Account"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              "rounded-t-md px-4 py-2 text-sm font-semibold transition-colors",
              tab === id
                ? "bg-white text-sage-700 ring-1 ring-b-0 ring-stone-200"
                : "text-ink-muted hover:text-ink-primary",
            )}
          >
            {label}
          </button>
        ))}
      </nav>

      {isLoading && (
        <p className="text-sm text-ink-muted">Loading settings…</p>
      )}
      {isError && (
        <p className="text-sm text-red-800">
          Could not load settings.{errMsg ? ` ${errMsg}` : ""}
        </p>
      )}

      {!isLoading && !isError && (
        <div className="space-y-8">
          {tab === "filtering" && (
            <section className="rounded-lg border border-stone-200 bg-white p-6 shadow-card">
              <h2 className="text-lg font-semibold text-sage-700">
                Filtering goal
              </h2>
              <textarea
                className="mt-3 w-full rounded-md border border-stone-200 px-3 py-2 text-sm outline-none ring-sage-500 focus:ring-2"
                rows={5}
                value={s.filtering_goal ?? ""}
                onChange={(e) =>
                  setS((prev) => ({ ...prev, filtering_goal: e.target.value }))
                }
              />
              <p className="mt-2 text-xs text-ink-muted">
                Your natural language goal is distilled by the GoalDistiller agent
                on save.
              </p>
              <button
                type="button"
                className="mt-4 w-full rounded-md bg-sage-500 py-2.5 text-sm font-semibold text-white hover:bg-sage-700"
                onClick={() => save({ filtering_goal: s.filtering_goal })}
                disabled={mutation.isPending}
              >
                Save goal
              </button>

              <TagBlock
                title="Categories"
                hint="arXiv category codes, e.g. cs.CV, math.OC"
                values={s.categories}
                onChange={(categories) => setS((prev) => ({ ...prev, categories }))}
                onSave={() => save({ categories: s.categories })}
                disabled={mutation.isPending}
                placeholder="cs.AI"
              />
              <TagBlock
                title="Topics"
                values={s.topics}
                onChange={(topics) => setS((prev) => ({ ...prev, topics }))}
                onSave={() => save({ topics: s.topics })}
                disabled={mutation.isPending}
                placeholder="agents"
              />
              <TagBlock
                title="Authors"
                values={s.authors}
                onChange={(authors) => setS((prev) => ({ ...prev, authors }))}
                onSave={() => save({ authors: s.authors })}
                disabled={mutation.isPending}
                placeholder="Name"
              />
              <button
                type="button"
                className="mt-6 w-full rounded-md bg-sage-500 py-2.5 text-sm font-semibold text-white hover:bg-sage-700"
                onClick={() =>
                  save({
                    filtering_goal: s.filtering_goal,
                    categories: s.categories,
                    topics: s.topics,
                    authors: s.authors,
                  })
                }
                disabled={mutation.isPending}
              >
                Save all filtering settings
              </button>
            </section>
          )}

          {tab === "library" && (
            <section className="rounded-lg border border-stone-200 bg-white p-6 shadow-card">
              <h2 className="text-lg font-semibold text-sage-700">
                Explanation level
              </h2>
              <p className="mt-1 text-sm text-ink-muted">
                How should papers be explained to you?
              </p>
              <div className="mt-4 space-y-2">
                {(
                  [
                    ["professional", "Professional"],
                    ["student", "Student"],
                    ["kid", "Simplified (kid)"],
                  ] as const
                ).map(([value, label]) => (
                  <label
                    key={value}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-md border px-4 py-3",
                      s.library_explanation_level === value
                        ? "border-sage-500 bg-sage-50"
                        : "border-stone-200 hover:bg-stone-50",
                    )}
                  >
                    <input
                      type="radio"
                      name="level"
                      value={value}
                      checked={s.library_explanation_level === value}
                      onChange={() =>
                        setS((prev) => ({
                          ...prev,
                          library_explanation_level: value,
                        }))
                      }
                    />
                    <span className="text-sm font-medium">{label}</span>
                  </label>
                ))}
              </div>

              <h3 className="mt-8 text-base font-semibold text-sage-700">
                Content interest
              </h3>
              <p className="mt-1 text-sm text-ink-muted">
                Which sections matter when the agent reads PDFs?
              </p>
              <div className="mt-3 flex flex-wrap gap-3">
                {CONTENT_OPTIONS.map(({ value, label }) => (
                  <label
                    key={value}
                    className="flex cursor-pointer items-center gap-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={s.content_interest.includes(value)}
                      onChange={(e) => {
                        const set = new Set(s.content_interest);
                        if (e.target.checked) set.add(value);
                        else set.delete(value);
                        setS((prev) => ({
                          ...prev,
                          content_interest: [...set],
                        }));
                      }}
                    />
                    {label}
                  </label>
                ))}
              </div>
              <button
                type="button"
                className="mt-6 w-full rounded-md bg-sage-500 py-2.5 text-sm font-semibold text-white hover:bg-sage-700"
                onClick={() =>
                  save({
                    library_explanation_level: s.library_explanation_level,
                    content_interest: s.content_interest,
                  })
                }
                disabled={mutation.isPending}
              >
                Save library preferences
              </button>
            </section>
          )}

          {tab === "pipeline" && (
            <section className="rounded-lg border border-stone-200 bg-white p-6 shadow-card">
              <h2 className="text-lg font-semibold text-sage-700">
                Notification time
              </h2>
              <input
                type="text"
                className="mt-2 w-full max-w-xs rounded-md border border-stone-200 px-3 py-2 font-mono text-sm"
                placeholder="09:00"
                value={s.notification_time ?? ""}
                onChange={(e) =>
                  setS((prev) => ({ ...prev, notification_time: e.target.value }))
                }
              />
              <h3 className="mt-8 text-base font-semibold text-sage-700">
                PDF parser
              </h3>
              <select
                className="mt-2 w-full max-w-xs rounded-md border border-stone-200 px-3 py-2 text-sm"
                value={s.pdf_parser_mode}
                onChange={(e) =>
                  setS((prev) => ({ ...prev, pdf_parser_mode: e.target.value }))
                }
              >
                <option value="pypdfium">pypdfium (local)</option>
                <option value="marker-modal">marker-modal (cloud)</option>
              </select>
              <button
                type="button"
                className="mt-6 w-full rounded-md bg-sage-500 py-2.5 text-sm font-semibold text-white hover:bg-sage-700"
                onClick={() =>
                  save({
                    notification_time: s.notification_time,
                    pdf_parser_mode: s.pdf_parser_mode,
                  })
                }
                disabled={mutation.isPending}
              >
                Save pipeline settings
              </button>
              <button
                type="button"
                className="mt-4 w-full rounded-md border border-sage-200 py-2.5 text-sm font-semibold text-sage-700 hover:bg-sage-50"
                onClick={() => void runTrigger()}
              >
                Run full discovery now
              </button>
            </section>
          )}

          {tab === "account" && (
            <section className="rounded-lg border border-stone-200 bg-white p-6 shadow-card">
              <h2 className="text-lg font-semibold text-sage-700">Account</h2>

              <h3 className="mt-6 text-base font-semibold text-sage-700">
                Notification email
              </h3>
              <p className="mt-1 text-sm text-ink-muted">
                Top-pick papers (score ≥ 7.0) will be sent to this email after
                each pipeline run.
              </p>
              <input
                type="email"
                className="mt-2 w-full max-w-sm rounded-md border border-stone-200 px-3 py-2 text-sm outline-none ring-sage-500 focus:ring-2"
                placeholder="your@email.com"
                value={s.notification_email ?? ""}
                onChange={(e) =>
                  setS((prev) => ({
                    ...prev,
                    notification_email: e.target.value,
                  }))
                }
              />

              <h3 className="mt-8 text-base font-semibold text-sage-700">
                Deep scan limit
              </h3>
              <p className="mt-1 text-sm text-ink-muted">
                How many top papers get full-text analysis per pipeline run.
              </p>
              <div className="mt-3 flex gap-3">
                {[5, 10, 15].map((n) => (
                  <label
                    key={n}
                    className={cn(
                      "flex cursor-pointer items-center gap-2 rounded-md border px-4 py-2.5 text-sm font-medium",
                      s.deep_scan_limit === n
                        ? "border-sage-500 bg-sage-50 text-sage-700"
                        : "border-stone-200 text-ink-secondary hover:bg-stone-50",
                    )}
                  >
                    <input
                      type="radio"
                      name="deep_scan_limit"
                      className="sr-only"
                      checked={s.deep_scan_limit === n}
                      onChange={() =>
                        setS((prev) => ({ ...prev, deep_scan_limit: n }))
                      }
                    />
                    Top {n}
                  </label>
                ))}
              </div>

              <button
                type="button"
                className="mt-6 w-full rounded-md bg-sage-500 py-2.5 text-sm font-semibold text-white hover:bg-sage-700"
                onClick={() =>
                  save({
                    notification_email: s.notification_email,
                    deep_scan_limit: s.deep_scan_limit,
                  })
                }
                disabled={mutation.isPending}
              >
                Save account settings
              </button>
            </section>
          )}
        </div>
      )}

      {mutation.isError && (
        <p className="mt-4 text-sm text-red-800">Save failed. Try again.</p>
      )}
      {mutation.isSuccess && (
        <p className="mt-4 text-sm text-moss">Saved.</p>
      )}
    </div>
  );
}

function TagBlock({
  title,
  hint,
  values,
  onChange,
  onSave,
  disabled,
  placeholder,
}: {
  title: string;
  hint?: string;
  values: string[];
  onChange: (v: string[]) => void;
  onSave: () => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const [input, setInput] = useState("");
  return (
    <div className="form-section mt-8">
      <h3 className="text-base font-semibold text-sage-700">{title}</h3>
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
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        <input
          className="min-w-[140px] flex-1 rounded-md border border-stone-200 px-3 py-1.5 text-sm"
          value={input}
          placeholder={placeholder}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              const v = input.trim();
              if (v && !values.includes(v)) {
                onChange([...values, v]);
                setInput("");
              }
            }
          }}
        />
        <button
          type="button"
          className="rounded-md border border-stone-200 px-3 py-1.5 text-xs font-semibold text-sage-700 hover:bg-sage-50"
          onClick={() => {
            const v = input.trim();
            if (v && !values.includes(v)) {
              onChange([...values, v]);
              setInput("");
            }
          }}
        >
          Add
        </button>
        <button
          type="button"
          className="rounded-md bg-sage-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sage-700"
          onClick={onSave}
          disabled={disabled}
        >
          Save {title.toLowerCase()}
        </button>
      </div>
      {hint && <p className="mt-1 text-xs text-ink-muted">{hint}</p>}
    </div>
  );
}
