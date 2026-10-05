import { DICTS } from "./i18n";
import type { Article, Lang, Source } from "./types";

export const SOURCE_LABEL: Record<Source, string> = { reuters: "Reuters", ars: "Ars Technica", hn: "Hacker News" };

/** Sections that can be filtered within each source. HN only has /front. */
export const SOURCE_SECTIONS: Record<Source, string[]> = {
  reuters: ["world", "technology"],
  ars: ["ai", "biz-it", "security"],
  hn: [],
};

const LOCALE: Record<Lang, string> = { es: "es-ES", en: "en-GB" };

export function timeAgo(iso: string, lang: Lang, now: number = Date.now()): string {
  const t = DICTS[lang];
  const minutes = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000));
  if (minutes < 60) return t.minutesAgo(minutes);
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t.hoursAgo(hours);
  return t.daysAgo(Math.floor(hours / 24));
}

export const clockTime = (iso: string, lang: Lang) =>
  new Intl.DateTimeFormat(LOCALE[lang], { hour: "2-digit", minute: "2-digit" }).format(new Date(iso));

export const todayLine = (lang: Lang, now = new Date()) =>
  capitalize(new Intl.DateTimeFormat(LOCALE[lang], { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(now));

export const formatNumber = (n: number, lang: Lang) => n.toLocaleString(LOCALE[lang]);

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const dayKey = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;

export function dayLabel(iso: string, lang: Lang, now: Date = new Date()): string {
  const d = new Date(iso);
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (dayKey(d) === dayKey(now)) return DICTS[lang].today;
  if (dayKey(d) === dayKey(yesterday)) return DICTS[lang].yesterday;
  return capitalize(new Intl.DateTimeFormat(LOCALE[lang], { weekday: "long", day: "numeric", month: "long" }).format(d));
}

/** Groups articles already sorted by date (newest first) into blocks per day. */
export function groupByDay(articles: Article[], lang: Lang, now: Date = new Date()) {
  const groups: { label: string; items: Article[] }[] = [];
  for (const a of articles) {
    const label = dayLabel(a.published_at, lang, now);
    const last = groups.at(-1);
    if (last?.label === label) last.items.push(a);
    else groups.push({ label, items: [a] });
  }
  return groups;
}

/** Headline in the chosen language (the sources publish in English). */
export const headline = (a: Article, lang: Lang) => (lang === "es" ? a.title_es ?? a.title : a.title);

/** Generated description in the chosen language; falls back to the source excerpt. */
export const description = (a: Article, lang: Lang) => (lang === "es" ? a.ai_summary_es : a.ai_summary_en) ?? a.summary;

export const firstTopic = (a: Article, lang: Lang) => (lang === "es" ? a.topics_es[0] ?? a.topics[0] : a.topics[0]);

/** Hacker News view: groups by the day of the /front page, in HN's own order. */
export function groupByFrontDay(articles: Article[], lang: Lang) {
  const groups: { label: string; items: Article[] }[] = [];
  const fmt = new Intl.DateTimeFormat(LOCALE[lang], { day: "numeric", month: "long", timeZone: "UTC" });
  for (const a of articles) {
    const day = a.hn_front_day ? fmt.format(new Date(`${a.hn_front_day}T00:00:00Z`)) : "";
    const label = DICTS[lang].frontOf(day);
    const last = groups.at(-1);
    if (last?.label === label) last.items.push(a);
    else groups.push({ label, items: [a] });
  }
  return groups;
}
