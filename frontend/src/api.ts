import type { Article, CommentNode, Digest, Feedback, Lang, Metrics, Source } from "./types";

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
export const fetchDigest = () => request<Digest | null>("/digest");
export const fetchComments = (articleId: number, lang: Lang) =>
  request<CommentNode[]>(`/articles/${articleId}/comments?lang=${lang}`);

/** Comment trees are cached briefly so reopening a thread, or opening one that was prefetched on
 *  hover, is instant. The worker refreshes live threads every few minutes, so two is plenty. */
const COMMENTS_TTL_MS = 2 * 60_000;
const commentsCache = new Map<string, { at: number; promise: Promise<CommentNode[]>; data?: CommentNode[] }>();

export function loadComments(articleId: number, lang: Lang): Promise<CommentNode[]> {
  const key = `${articleId}:${lang}`;
  const hit = commentsCache.get(key);
  if (hit && Date.now() - hit.at < COMMENTS_TTL_MS) return hit.promise;
  const entry: { at: number; promise: Promise<CommentNode[]>; data?: CommentNode[] } = {
    at: Date.now(),
    promise: fetchComments(articleId, lang),
  };
  entry.promise.then((data) => { entry.data = data; }, () => commentsCache.delete(key)); // never cache a failure
  commentsCache.set(key, entry);
  return entry.promise;
}

/** The thread if it is already loaded for this language (no waiting), else null. */
export function cachedComments(articleId: number, lang: Lang): CommentNode[] | null {
  const hit = commentsCache.get(`${articleId}:${lang}`);
  return hit?.data && Date.now() - hit.at < COMMENTS_TTL_MS ? hit.data : null;
}

/** Warms the cache (original first: it is the fast one) when the reader points at a thread. */
export function prefetchComments(articleId: number) {
  loadComments(articleId, "en").catch(() => undefined);
}

/** Creates (or, with an existing cookie, returns) this browser's anonymous user. */
export const ensureSession = () => request<{ user_id: number }>("/session", { method: "POST" });

export const putFeedback = (articleId: number, value: Feedback) =>
  request<{ feedback: Feedback }>(`/articles/${articleId}/feedback`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
