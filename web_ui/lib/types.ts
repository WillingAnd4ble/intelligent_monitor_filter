export type PaperListItem = {
  user_paper_id: string;
  paper_id: string;
  title: string;
  authors: string[];
  abstract: string;
  agent_score: number | null;
  agent_explanation: string | null;
  source_url: string;
  is_top_pick: boolean;
};

export type FeedStats = {
  total_scraped_today: number;
  evaluated_by_agent: number;
  recommended_today: number;
};

export type ExplainResponse = {
  status: "ready" | "processing" | "error";
  level?: string;
  explanation?: string;
  task_id?: string;
  detail?: string;
};

export type PipelineTaskStatus = {
  task_id: string;
  state: string;
  progress: number;
  stage: string;
};

export type ApiErrorBody = {
  error?: { code?: string; message?: string };
};
