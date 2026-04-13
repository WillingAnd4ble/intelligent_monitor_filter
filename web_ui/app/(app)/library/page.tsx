"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { getLibrary, removeFromLibrary } from "@/lib/api";
import { LibraryCard } from "@/components/library/LibraryCard";

export default function LibraryPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");

  const { data: papers, isLoading, isError, refetch } = useQuery({
    queryKey: ["library"],
    queryFn: getLibrary,
  });

  const filtered = useMemo(() => {
    if (!papers) return [];
    const s = q.trim().toLowerCase();
    if (!s) return papers;
    return papers.filter((p) => {
      const blob = `${p.title} ${p.authors.join(" ")}`.toLowerCase();
      return blob.includes(s);
    });
  }, [papers, q]);

  const removeMut = useMutation({
    mutationFn: removeFromLibrary,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["library"] }),
  });

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-sage-700">Library</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Accepted papers — request deeper explanations inline.
        </p>
      </div>

      <div className="mb-6 flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Search title or authors…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="min-w-[200px] flex-1 rounded-md border border-stone-200 px-3 py-2 text-sm outline-none ring-sage-500 focus:ring-2"
        />
      </div>

      {isLoading && (
        <p className="text-sm text-ink-muted">Loading library…</p>
      )}
      {isError && (
        <p className="text-sm text-red-800">
          Could not load library.{" "}
          <button
            type="button"
            className="font-semibold text-amber-warm underline"
            onClick={() => void refetch()}
          >
            Retry
          </button>
        </p>
      )}

      <div className="flex flex-col gap-4">
        {filtered.map((p) => (
          <LibraryCard
            key={p.user_paper_id}
            paper={p}
            onRemove={(id) => removeMut.mutate(id)}
          />
        ))}
      </div>

      {!isLoading && !isError && filtered.length === 0 && (
        <p className="text-sm text-ink-muted">
          No papers match your search, or your library is empty.
        </p>
      )}
    </div>
  );
}
