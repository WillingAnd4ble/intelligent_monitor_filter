import Link from "next/link";
import { PipelinePill } from "./PipelinePill";

export function Topbar() {
  return (
    <header className="col-span-full flex h-[58px] items-center justify-between border-b border-stone-200 bg-[rgba(250,250,248,0.85)] px-8 backdrop-blur-[10px]">
      <Link
        href="/dashboard"
        className="flex items-center gap-3 font-semibold text-ink-primary no-underline"
      >
        <span>
          arxiv<strong className="text-sage-700">lens</strong>
        </span>
      </Link>
      <div className="flex items-center gap-[18px]">
        <PipelinePill />
      </div>
    </header>
  );
}
