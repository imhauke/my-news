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

export interface Metrics {
  articles_total: number;
  articles_enriched: number;
  last_ingest_at: string | null;
}
