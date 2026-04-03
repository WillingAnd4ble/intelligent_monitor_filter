"use client";

import { PipelineProvider } from "@/contexts/pipeline-context";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <PipelineProvider>
      <div className="grid min-h-screen grid-cols-[232px_1fr] grid-rows-[auto_1fr] bg-page-gradient">
        <Topbar />
        <Sidebar />
        <main className="min-h-0 overflow-y-auto px-8 py-8">
          <div className="mx-auto max-w-shell">{children}</div>
        </main>
      </div>
    </PipelineProvider>
  );
}
