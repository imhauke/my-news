import { useSyncExternalStore } from "react";
import type { Article, Feedback } from "./types";

/**
 * Per-browser reader state kept in localStorage, so every visitor has their own without an
 * account: which stories they opened and how they rated them. Votes keep enough context
 * (source, section, topics, title) to seed a future per-user For You feed. Clearing site data
 * simply resets both.
 */

export interface StoredVote {
  value: Exclude<Feedback, 0>;
  at: string;
  source: Article["source"];
  section: string | null;
  topics: string[];
  title: string;
}

const READ_KEY = "mynews.read.v1";
const VOTES_KEY = "mynews.votes.v1";
const MAX_READ = 3000; // oldest entries are dropped beyond this

type ReadMap = Record<string, number>;
type VoteMap = Record<string, StoredVote>;

function load<T extends object>(key: string): T {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) ?? "{}");
    return parsed && typeof parsed === "object" ? (parsed as T) : ({} as T);
  } catch {
    return {} as T;
  }
}

function save(key: string, value: object) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full or blocked: the state lasts for this visit only */
  }
}

let read: ReadMap = load<ReadMap>(READ_KEY);
let votes: VoteMap = load<VoteMap>(VOTES_KEY);
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function markRead(id: number) {
  if (read[id]) return;
  read = { ...read, [id]: Date.now() };
  const ids = Object.keys(read);
  if (ids.length > MAX_READ) {
    const keep = ids.sort((a, b) => read[b] - read[a]).slice(0, MAX_READ);
    read = Object.fromEntries(keep.map((k) => [k, read[k]]));
  }
  save(READ_KEY, read);
  emit();
}

export function saveVote(article: Article, value: Exclude<Feedback, 0>) {
  votes = {
    ...votes,
    [article.id]: {
      value, at: new Date().toISOString(), source: article.source, section: article.section,
      topics: article.topics, title: article.title,
    },
  };
  save(VOTES_KEY, votes);
  emit();
}

export const useIsRead = (id: number) => useSyncExternalStore(subscribe, () => Boolean(read[id]));
export const useVote = (id: number): Feedback =>
  useSyncExternalStore(subscribe, (): Feedback => votes[id]?.value ?? 0);

/** Every rating kept in this browser, as [article id, vote]. */
export const localVotes = () => Object.entries(votes).map(([id, vote]) => [Number(id), vote] as const);

/** For tests: reloads the in-memory copies from localStorage. */
export function reloadLocalState() {
  read = load<ReadMap>(READ_KEY);
  votes = load<VoteMap>(VOTES_KEY);
  emit();
}
