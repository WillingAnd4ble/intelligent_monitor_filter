"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { getPipelineStatus, triggerPipeline } from "@/lib/api";

export type PipelinePhase = "idle" | "running" | "error";

type PipelineContextValue = {
  phase: PipelinePhase;
  stateLabel: string;
  progress: number;
  taskId: string | null;
  runTrigger: () => Promise<void>;
};

const PipelineContext = createContext<PipelineContextValue | null>(null);

export function PipelineProvider({ children }: { children: React.ReactNode }) {
  const [phase, setPhase] = useState<PipelinePhase>("idle");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [stateLabel, setStateLabel] = useState("idle");
  const [progress, setProgress] = useState(0);
  const pollCount = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearPoll = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    pollCount.current = 0;
  }, []);

  const pollOnce = useCallback(async (id: string) => {
    try {
      const s = await getPipelineStatus(id);
      setStateLabel(s.state);
      setProgress(s.progress);
      pollCount.current += 1;
      const err = /error|fail|cancel/i.test(s.state);
      const done =
        s.progress >= 100 ||
        /complete|done|success|finished/i.test(s.state);
      if (err) {
        setPhase("error");
        clearPoll();
        setTaskId(null);
        return;
      }
      if (done) {
        setPhase("idle");
        clearPoll();
        setTaskId(null);
        setStateLabel("idle");
        return;
      }
      if (pollCount.current > 120) {
        clearPoll();
        setPhase("idle");
        setTaskId(null);
      }
    } catch {
      setPhase("error");
      clearPoll();
      setTaskId(null);
    }
  }, [clearPoll]);

  useEffect(() => {
    if (!taskId || phase !== "running") return;
    void pollOnce(taskId);
    timerRef.current = setInterval(() => void pollOnce(taskId), 2000);
    return () => clearPoll();
  }, [taskId, phase, pollOnce, clearPoll]);

  const runTrigger = async () => {
    try {
      const { task_id } = await triggerPipeline();
      clearPoll();
      setPhase("running");
      setTaskId(task_id);
      setProgress(0);
      setStateLabel("Queued…");
    } catch {
      setPhase("error");
    }
  };

  return (
    <PipelineContext.Provider
      value={{ phase, stateLabel, progress, taskId, runTrigger }}
    >
      {children}
    </PipelineContext.Provider>
  );
}

export function usePipeline() {
  const ctx = useContext(PipelineContext);
  if (!ctx) throw new Error("usePipeline must be used within PipelineProvider");
  return ctx;
}
