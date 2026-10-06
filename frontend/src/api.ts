import type { Article, CommentNode, Digest, ThreadInsight, Feedback, Lang, Metrics, Source } from "./types";

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

/** The community's take on a thread (null until analysed), cached briefly like the comments. */
const insightCache = new Map<number, { at: number; promise: Promise<ThreadInsight | null> }>();

export function loadInsight(articleId: number): Promise<ThreadInsight | null> {
  const hit = insightCache.get(articleId);
  if (hit && Date.now() - hit.at < COMMENTS_TTL_MS) return hit.promise;
  const promise = request<ThreadInsight | null>(`/articles/${articleId}/insight`).then((i) =>
    i && typeof i === "object" && Array.isArray(i.points) ? i : null, // anything unexpected shows nothing
  );
  promise.catch(() => insightCache.delete(articleId));
  insightCache.set(articleId, { at: Date.now(), promise });
  return promise;
}

/** Stories about what the query means, in any language. */
export const searchStories = (query: string, signal?: AbortSignal) =>
  request<Article[]>(`/search?${new URLSearchParams({ q: query })}`, { signal });

/** Creates (or, with an existing cookie, returns) this browser's anonymous user. */
export const ensureSession = () => request<{ user_id: number }>("/session", { method: "POST" });

/** Forgets this browser: deletes its anonymous user and everything linked to it. */
export const deleteSession = async () => {
  const res = await fetch(`${BASE}/session`, { method: "DELETE", credentials: "same-origin" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
};

export const putFeedback = (articleId: number, value: Feedback) =>
  request<{ feedback: Feedback }>(`/articles/${articleId}/feedback`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });

export interface ChatTurn {
  role: "user" | "model";
  text: string;
}

/** Why an answer could not be given: "rate_limited", "daily_limit" or "unavailable". */
export class ChatError extends Error {
  constructor(readonly code: string) {
    super(code);
  }
}

/**
 * Asks about a story and streams the answer: `onDelta` receives each piece of text as Gemini
 * writes it. The server keeps no conversation, so the whole history is sent each time.
 */
export async function streamChat(
  articleId: number, messages: ChatTurn[], lang: Lang, onDelta: (text: string) => void, signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/articles/${articleId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, lang }),
    credentials: "omit", // a question needs no session
    signal,
  });
  if (!res.ok) {
    let code = "unavailable";
    if (res.status === 429) {
      const detail = await res.json().then((d: { detail?: unknown }) => d.detail, () => null);
      if (typeof detail === "string") code = detail;
    }
    throw new ChatError(code);
  }
  if (!res.body) throw new ChatError("unavailable");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replaceAll("\r\n", "\n");
    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const name = /^event: (.+)$/m.exec(block)?.[1];
      const data = JSON.parse(/^data: (.*)$/m.exec(block)?.[1] ?? "{}") as { text?: string; code?: string };
      if (name === "delta" && data.text) onDelta(data.text);
      else if (name === "error") throw new ChatError(data.code ?? "unavailable");
      else if (name === "done") return;
    }
  }
  throw new ChatError("unavailable"); // the stream ended without finishing
}
