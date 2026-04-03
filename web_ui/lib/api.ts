import { apiClient } from "@/lib/axios";
import type {
  ExplainResponse,
  FeedStats,
  PaperListItem,
  PipelineTaskStatus,
} from "@/lib/types";
import type { SettingsUpdatePayload, UserSettings } from "@/lib/types/settings";

const v1 = "/api/v1";

export async function login(body: { email: string; password: string }) {
  const { data } = await apiClient.post<{ status: string }>("/auth/login", body);
  return data;
}

export async function register(body: { email: string; password: string }) {
  const { data } = await apiClient.post<{ status: string }>(
    "/auth/register",
    body,
  );
  return data;
}

export async function getFeed() {
  const { data } = await apiClient.get<PaperListItem[]>(`${v1}/feed`);
  return data;
}

export async function getFeedStats() {
  const { data } = await apiClient.get<FeedStats>(`${v1}/feed/stats`);
  return data;
}

export async function acceptPaper(userPaperId: string) {
  const { data } = await apiClient.post<{ status: string; paper_status: string }>(
    `${v1}/feed/${userPaperId}/accept`,
  );
  return data;
}

export async function rejectPaper(userPaperId: string, comment: string) {
  const { data } = await apiClient.post<{ status: string; paper_status: string }>(
    `${v1}/feed/${userPaperId}/reject`,
    { comment },
  );
  return data;
}

export async function getLibrary() {
  const { data } = await apiClient.get<PaperListItem[]>(`${v1}/library`);
  return data;
}

export async function explainPaper(userPaperId: string) {
  const { data } = await apiClient.post<ExplainResponse>(
    `${v1}/library/${userPaperId}/explain`,
  );
  return data;
}

export async function removeFromLibrary(userPaperId: string) {
  await apiClient.delete(`${v1}/library/${userPaperId}`);
}

export async function getSettings() {
  const { data } = await apiClient.get<UserSettings>(`${v1}/settings`);
  return data;
}

export async function putSettings(payload: SettingsUpdatePayload) {
  const { data } = await apiClient.put<{ status: string }>(
    `${v1}/settings`,
    payload,
  );
  return data;
}

export async function triggerPipeline() {
  const { data } = await apiClient.post<{ task_id: string }>(
    `${v1}/pipeline/trigger`,
  );
  return data;
}

export async function getPipelineStatus(taskId: string) {
  const { data } = await apiClient.get<PipelineTaskStatus>(
    `${v1}/pipeline/${taskId}/status`,
  );
  return data;
}

export async function cancelPipeline(taskId: string) {
  const { data } = await apiClient.post<{ status: string }>(
    `${v1}/pipeline/${taskId}/cancel`,
  );
  return data;
}
