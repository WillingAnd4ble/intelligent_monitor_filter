"use client";

import { useEffect, useRef } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

const schema = z.object({
  comment: z.string().min(1, "Feedback is required."),
});

type Form = z.infer<typeof schema>;

type Props = {
  open: boolean;
  onClose: () => void;
  onSubmit: (comment: string) => Promise<void>;
};

export function RejectModal({ open, onClose, onSubmit }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { comment: "" } });

  useEffect(() => {
    if (!open) reset();
  }, [open, reset]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-primary/40 p-4"
      role="presentation"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="reject-title"
        className="w-full max-w-md rounded-lg border border-stone-200 bg-stone-50 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="reject-title" className="text-lg font-semibold text-sage-700">
          Reject paper
        </h2>
        <p className="mt-1 text-sm text-ink-secondary">
          Tell the agent why this paper is not a fit — this trains future runs.
        </p>
        <form
          className="mt-4"
          onSubmit={handleSubmit(async (data) => {
            await onSubmit(data.comment);
            onClose();
          })}
        >
          <label className="sr-only" htmlFor="reject-comment">
            Comment
          </label>
          <textarea
            id="reject-comment"
            rows={4}
            className="w-full rounded-md border border-stone-200 bg-white px-3 py-2 text-sm text-ink-primary outline-none ring-sage-500 focus:ring-2"
            placeholder="Required feedback…"
            {...register("comment")}
          />
          {errors.comment && (
            <p className="mt-1 text-sm text-red-700">{errors.comment.message}</p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-ink-secondary hover:bg-stone-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-md bg-sage-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sage-700 disabled:opacity-60"
            >
              Submit rejection
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
