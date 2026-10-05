import type { Article, CommentNode, Feedback, Lang, Metrics, Source } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";
export const PAGE_SIZE = 30;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: "same-origin", ...init });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export interface LatestQuery {
  source?: Source;
  section?: string;
  before?: string;
  offset?: number;
}

export const fetchLatest = ({ source, section, before, offset }: LatestQuery = {}) => {
  const q = new URLSearchParams({ limit: String(PAGE_SIZE) });
  if (source) q.set("source", source);
  if (section) q.set("section", section);
  if (before) q.set("before", before);
  if (offset) q.set("offset", String(offset));
  return request<Article[]>(`/feed/latest?${q}`);
};

export const fetchImportant = () => request<Article[]>("/feed/important?limit=5");
export const fetchMetrics = () => request<Metrics>("/metrics");
export const fetchComments = (articleId: number, lang: Lang) =>
  request<CommentNode[]>(`/articles/${articleId}/comments?lang=${lang}`);

/** Creates (or, with an existing cookie, returns) this browser's anonymous user. */
export const ensureSession = () => request<{ user_id: number }>("/session", { method: "POST" });

export const putFeedback = (articleId: number, value: Feedback) =>
  request<{ feedback: Feedback }>(`/articles/${articleId}/feedback`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
