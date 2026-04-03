"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, LayoutList, Monitor } from "lucide-react";
import { usePipeline } from "@/contexts/pipeline-context";
import { cn } from "@/lib/cn";

const nav = [
  { href: "/dashboard", label: "Feed", icon: LayoutList },
  { href: "/library", label: "Library", icon: BookOpen },
  { href: "/terminal", label: "Terminal", icon: Monitor },
];

export function Sidebar() {
  const pathname = usePathname();
  const { runTrigger } = usePipeline();

  return (
    <aside className="flex flex-col gap-1.5 border-r border-stone-200 bg-white/55 px-[18px] py-7">
      <div className="mb-2 px-2.5 text-[11px] font-semibold uppercase tracking-wide text-sage-500">
        Explore
      </div>
      {nav.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3.5 py-3 text-[15px] font-medium transition-colors",
              active
                ? "bg-sage-50 text-sage-700 ring-1 ring-sage-200"
                : "text-ink-secondary hover:bg-stone-100 hover:text-ink-primary",
            )}
          >
            <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={2} />
            {label}
          </Link>
        );
      })}
      <button
        type="button"
        onClick={() => void runTrigger()}
        className="mt-1 rounded-md border border-sage-200 bg-white px-3.5 py-3 text-left text-[13px] font-semibold text-sage-700 shadow-sm transition hover:bg-sage-50"
      >
        Trigger run
      </button>
      <div className="mt-auto pt-6 font-mono text-[12px] leading-relaxed text-ink-muted">
        <span className="select-all">
          {process.env.NEXT_PUBLIC_DEMO_EMAIL ?? "you@research.example"}
        </span>
        <br />
        <Link
          href="/login"
          className="font-medium text-amber-warm no-underline hover:underline"
        >
          Sign out
        </Link>
      </div>
    </aside>
  );
}
