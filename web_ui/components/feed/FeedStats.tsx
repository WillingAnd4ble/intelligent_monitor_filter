import type { FeedStats as FeedStatsType } from "@/lib/types";

export function FeedStats({ stats }: { stats: FeedStatsType | undefined }) {
  if (!stats) return null;
  return (
    <div className="mb-8 flex flex-wrap gap-3">
      <div className="rounded-lg border border-stone-200 bg-white px-5 py-3 shadow-card">
        <strong className="font-mono text-lg text-sage-700">
          {stats.total_scraped_today}
        </strong>
        <span className="ml-2 text-sm text-ink-muted">scraped today</span>
      </div>
      <div className="rounded-lg border border-stone-200 bg-white px-5 py-3 shadow-card">
        <strong className="font-mono text-lg text-sage-700">
          {stats.evaluated_by_agent}
        </strong>
        <span className="ml-2 text-sm text-ink-muted">evaluated</span>
      </div>
      <div className="rounded-lg border border-stone-200 bg-white px-5 py-3 shadow-card">
        <strong className="font-mono text-lg text-sage-700">
          {stats.recommended_today}
        </strong>
        <span className="ml-2 text-sm text-ink-muted">recommended</span>
      </div>
    </div>
  );
}
