export type Source = "reuters" | "ars" | "hn";
export type Lang = "es" | "en";
export type Theme = "system" | "light" | "dark";
export type Feedback = -1 | 0 | 1;

export interface Article {
  id: number;
  source: Source;
  url: string;
  title: string;
  title_es: string | null;
  summary: string | null;
  ai_summary_en: string | null;
  ai_summary_es: string | null;
  section: string | null;
  image_url?: string | null;
  author: string | null;
  published_at: string;
  hn_points: number | null;
  hn_comment_count: number | null;
  hn_front_day?: string | null;
  hn_front_rank?: number | null;
  topics: string[];
  topics_es: string[];
  hn_story_id: number | null;
  feedback: Feedback;
}

export interface CommentNode {
  id: number;
  author: string | null;
  text: string | null;
  text_es: string | null;
  created_at: string;
  depth: number;
  children: CommentNode[];
}

/** The brief at the top of the front page. */
export interface Digest {
  kind: string;
  text_en: string;
  text_es: string;
  bullets_en?: string[];
  bullets_es?: string[];
  article_ids: number[];
  created_at: string;
}

export interface Metrics {
  articles_total: number;
  articles_enriched: number;
  last_ingest_at: string | null;
}

export type ThreadTone = "positive" | "skeptical" | "divided" | "mixed";

/** What the Hacker News community says about a story, written by the worker. */
export interface ThreadInsight {
  tone: ThreadTone | null;
  summary_en: string | null;
  summary_es: string | null;
  points: { title_en: string; title_es: string; text_en: string; text_es: string }[];
  contributions: { author: string; text_en: string; text_es: string }[];
  resources: { title: string; url: string }[];
  comments_covered: number;
  created_at: string;
}
