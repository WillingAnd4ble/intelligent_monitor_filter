"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  acceptPaper,
  getFeed,
  getFeedStats,
  rejectPaper,
} from "@/lib/api";
import { FeedStats } from "@/components/feed/FeedStats";
import { PaperCard } from "@/components/feed/PaperCard";
import { RejectModal } from "@/components/feed/RejectModal";
import { usePipeline } from "@/contexts/pipeline-context";
import Link from "next/link";

export default function DashboardPage() {
  const qc = useQueryClient();
  const { runTrigger } = usePipeline();
  const [isFirstRun, setIsFirstRun] = useState(false);
  const [rejectId, setRejectId] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setIsFirstRun(params.get("first_run") === "true");
  }, []);

  const { data: papers, isLoading, isError, refetch } = useQuery({
    queryKey: ["feed"],
    queryFn: getFeed,
  });

  const { data: stats } = useQuery({
    queryKey: ["feed-stats"],
    queryFn: getFeedStats,
  });

  const dateStr = useMemo(
    () => new Date().toISOString().slice(0, 10),
    [],
  );

  const acceptMut = useMutation({
    mutationFn: acceptPaper,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feed"] });
      qc.invalidateQueries({ queryKey: ["feed-stats"] });
    },
  });

  const rejectMut = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment: string }) =>
      rejectPaper(id, comment),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feed"] });
      qc.invalidateQueries({ queryKey: ["feed-stats"] });
    },
  });

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-sage-700">
            Today&rsquo;s feed
          </h1>
          <span className="font-mono text-sm text-ink-muted">{dateStr}</span>
        </div>
      </div>

      <FeedStats stats={stats} />

      {isLoading && (
        <p className="text-sm text-ink-muted">Loading recommendations…</p>
      )}
      {isError && (
        <div className="rounded-md border border-amber-warm/40 bg-amber-soft px-4 py-3 text-sm text-ink-primary">
          Could not load the feed.{" "}
          <button
            type="button"
            className="font-semibold text-amber-warm underline"
            onClick={() => void refetch()}
          >
            Retry
          </button>
        </div>
      )}

      {!isLoading && !isError && papers?.length === 0 && (
        isFirstRun ? (
          <div className="rounded-lg border border-sage-200 bg-moss-light px-6 py-10 text-center">
            <h2 className="text-lg font-semibold text-sage-700">
              Your first batch is processing
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-ink-secondary">
              We&rsquo;re scanning today&rsquo;s papers against your goals. This
              usually takes a few minutes. Your feed will appear here once
              results are ready.
            </p>
            <p className="mt-4 text-xs text-ink-muted">
              Check the status pill in the top bar for real-time progress.
            </p>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-stone-300 bg-white/80 px-6 py-12 text-center">
            <p className="text-ink-secondary">
              No papers in your feed yet. Tune your goal in{" "}
              <Link href="/terminal" className="font-semibold text-amber-warm">
                Terminal
              </Link>{" "}
              or run the pipeline.
            </p>
            <button
              type="button"
              className="mt-4 rounded-md bg-sage-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-sage-700"
              onClick={() => void runTrigger()}
            >
              Trigger pipeline
            </button>
          </div>
        )
      )}

      <div className="flex flex-col gap-7">
        {papers?.map((p) => (
          <PaperCard
            key={p.user_paper_id}
            paper={p}
            onAccept={(id) => acceptMut.mutate(id)}
            onReject={(id) => setRejectId(id)}
          />
        ))}
      </div>

      <RejectModal
        open={rejectId != null}
        onClose={() => setRejectId(null)}
        onSubmit={async (comment) => {
          if (!rejectId) return;
          await rejectMut.mutateAsync({ id: rejectId, comment });
          setRejectId(null);
        }}
      />
    </div>
  );
}
