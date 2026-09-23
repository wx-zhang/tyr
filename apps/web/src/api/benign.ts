import type { components } from "./generated";

export type Scenario = components["schemas"]["BenignScenario"];
export type Run = components["schemas"]["BenignRun"];
type Submission = components["schemas"]["Submission"];
const origin = import.meta.env.VITE_API_ORIGIN ?? "http://127.0.0.1:6687";

async function request<T>(path: string, body?: unknown, timeoutMs = 15000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${origin}/api/v1/benign${path}`, {
      signal: controller.signal,
      ...(body === undefined ? {} : {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      }),
    });
    const raw = await response.text();
    let value;
    try { value = JSON.parse(raw); }
    catch { throw new Error(`API returned HTTP ${response.status} without a JSON response.`); }
    if (!response.ok) throw new Error(typeof value.detail === "string"
      ? value.detail : JSON.stringify(value.detail ?? value));
    return value as T;
  } catch (error) {
    if (controller.signal.aborted) throw new Error(path === "/drafts"
      ? "Plan generation timed out. No plan was received; try again."
      : "Request timed out. Check Results before submitting again.");
    throw error;
  } finally { clearTimeout(timer); }
}

export const workspaces = () => request<components["schemas"]["WorkspaceOption"][]>("/workspaces");
export const runs = () => request<Run[]>("/runs?limit=1000");
export const read = (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}`);
export const resume = (id: string) => request(`/runs/${encodeURIComponent(id)}/resume`, {});
export const submit = (body: Submission) => request<Run[]>("/runs", body);
export const draft = (text: string, workspace: string, timezone: string) =>
  request<Scenario>("/drafts", { text, workspace, timezone }, 75000);
