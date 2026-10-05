import { MotionConfig } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { PAGE_SIZE, ensureSession, fetchDigest, fetchImportant, fetchLatest, fetchMetrics } from "./api";
import { DiscussionPanel } from "./DiscussionPanel";
import { DiscussionProvider } from "./discussion";
import { formatNumber, mergeFresh } from "./format";
import { DICTS, LangContext } from "./i18n";
import { Important } from "./Important";
import { Masthead } from "./Masthead";
import { type Filter, River } from "./River";
import type { Article, Digest, Lang, Metrics, Theme } from "./types";

function stored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return allowed.includes(v as T) ? (v as T) : fallback;
  } catch {
    return fallback;
  }
}

/** Only a complete overview is shown; anything else (none yet, an unexpected payload) hides it. */
const validDigest = (d: Digest | null): Digest | null =>
  d && typeof d.text_es === "string" && typeof d.text_en === "string" && !Number.isNaN(Date.parse(d.created_at)) ? d : null;

/** How often the open page pulls fresh data while visible. The worker refreshes every 5 minutes. */
export const POLL_MS = 60_000;

function persist(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* no storage: the choice lasts for this visit only */ }
}

export default function App() {
  const [lang, setLang] = useState<Lang>(() => stored("mynews.lang", ["es", "en"] as const, "es"));
  const [theme, setTheme] = useState<Theme>(() => stored("mynews.theme", ["system", "light", "dark"] as const, "system"));
  const [filter, setFilter] = useState<Filter>({});
  const [shownFilter, setShownFilter] = useState<Filter>({}); // the filter the list on screen belongs to
  const [important, setImportant] = useState<Article[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [digest, setDigest] = useState<Digest | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canLoadMore, setCanLoadMore] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [sessionReady, setSessionReady] = useState(false);

  useEffect(() => {
    persist("mynews.lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    persist("mynews.theme", theme);
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }, [theme]);

  // The anonymous session comes first, so the feeds already include this browser's ratings.
  useEffect(() => {
    ensureSession().catch(() => undefined).finally(() => setSessionReady(true));
  }, []);

  useEffect(() => {
    if (!sessionReady) return;
    fetchImportant().then(setImportant).catch(() => setImportant([]));
    fetchMetrics().then(setMetrics).catch(() => setMetrics(null));
    fetchDigest().then(validDigest).then(setDigest).catch(() => undefined);
  }, [attempt, sessionReady]);

  useEffect(() => {
    if (!sessionReady) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchLatest(filter)
      .then((a) => {
        if (cancelled) return;
        setArticles(a);
        setShownFilter(filter);
        setCanLoadMore(a.length === PAGE_SIZE);
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [filter, attempt, sessionReady]);

  // Keep the page current: poll while visible, and catch up as soon as the tab is shown again.
  useEffect(() => {
    if (!sessionReady) return;
    let lastRefresh = Date.now();
    const refresh = async () => {
      lastRefresh = Date.now();
      fetchImportant().then(setImportant).catch(() => undefined);
      fetchMetrics().then(setMetrics).catch(() => undefined);
      fetchDigest().then(validDigest).then(setDigest).catch(() => undefined);
      try {
        const fresh = await fetchLatest(filter);
        setArticles((current) => mergeFresh(current, fresh, filter.source === "hn", PAGE_SIZE));
      } catch {
        /* keep what is on screen; the next tick retries */
      }
    };
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible" && Date.now() - lastRefresh >= POLL_MS) void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [filter, sessionReady]);

  const loadMore = useCallback(async () => {
    const last = articles.at(-1);
    if (!last) return;
    setLoadingMore(true);
    try {
      // HN is ranked, not chronological: page by position instead of by date.
      const page = filter.source === "hn" ? { offset: articles.length } : { before: last.published_at };
      const more = await fetchLatest({ ...filter, ...page });
      setArticles((prev) => [...prev, ...more]);
      setCanLoadMore(more.length === PAGE_SIZE);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingMore(false);
    }
  }, [articles, filter]);

  const t = DICTS[lang];
  return (
    <MotionConfig reducedMotion="user">
    <LangContext.Provider value={lang}>
    <DiscussionProvider>
      <div className="page">
        <Masthead metrics={metrics} digest={digest} onLang={setLang} theme={theme} onTheme={setTheme} />
        <main>
          <Important articles={important} />
          <River
            articles={articles} listKey={JSON.stringify(shownFilter)} filter={filter} onFilter={setFilter} loading={loading} loadingMore={loadingMore} error={error}
            canLoadMore={canLoadMore} onLoadMore={loadMore} onRetry={() => setAttempt(attempt + 1)}
          />
        </main>
        <footer className="colophon" style={{ viewTransitionName: "colophon" }}>
          {metrics && metrics.articles_total > 0 && (
            <p>{t.dateline(formatNumber(metrics.articles_total, lang), formatNumber(metrics.articles_enriched, lang))}</p>
          )}
          <p>{t.colophon}</p>
          <a href="https://github.com/imhauke/my-news" target="_blank" rel="noopener noreferrer">github.com/imhauke/my-news</a>
        </footer>
        <DiscussionPanel />
      </div>
    </DiscussionProvider>
    </LangContext.Provider>
    </MotionConfig>
  );
}
