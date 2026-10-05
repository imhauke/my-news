import { DICTS } from "./i18n";
import type { Article, Lang, Source } from "./types";

export const SOURCE_LABEL: Record<Source, string> = { reuters: "Reuters", ars: "Ars Technica", hn: "Hacker News" };

/** Secciones que se pueden filtrar dentro de cada fuente. HN solo tiene /front. */
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

/** Agrupa artículos ya ordenados por fecha descendente en bloques por día. */
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

/** Titular en el idioma elegido (las fuentes publican en inglés). */
export const headline = (a: Article, lang: Lang) => (lang === "es" ? a.title_es ?? a.title : a.title);

/** Descripción generada en el idioma elegido; si aún no existe, el extracto de la fuente. */
export const description = (a: Article, lang: Lang) => (lang === "es" ? a.ai_summary_es : a.ai_summary_en) ?? a.summary;

export const firstTopic = (a: Article, lang: Lang) => (lang === "es" ? a.topics_es[0] ?? a.topics[0] : a.topics[0]);
