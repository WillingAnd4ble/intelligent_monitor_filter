export type PaperListItem = {
  user_paper_id: string;
  paper_id: string;
  title: string;
  authors: string[];
  abstract: string;
  agent_score: number | null;
  agent_explanation: string | null;
  source_url: string;
};

export type FeedStats = {
  total_scraped_today: number;
  evaluated_by_agent: number;
  recommended_today: number;
};

export type ExplainResponse = {
  level: string;
  explanation: string;
};

export type PipelineTaskStatus = {
  task_id: string;
  state: string;
  progress: number;
};

export type ApiErrorBody = {
  error?: { code?: string; message?: string };
};
