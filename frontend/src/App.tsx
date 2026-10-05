import { useCallback, useEffect, useState } from "react";
import { PAGE_SIZE, ensureSession, fetchImportant, fetchLatest, fetchMetrics } from "./api";
import { CommentsSheet } from "./CommentsSheet";
import { DICTS, LangContext } from "./i18n";
import { Important } from "./Important";
import { Masthead } from "./Masthead";
import { type Filter, River } from "./River";
import type { Article, Lang, Metrics, Theme } from "./types";

function stored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return allowed.includes(v as T) ? (v as T) : fallback;
  } catch {
    return fallback;
  }
}

function persist(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* sin almacenamiento: solo dura la sesión */ }
}

export default function App() {
  const [lang, setLang] = useState<Lang>(() => stored("mynews.lang", ["es", "en"] as const, "es"));
  const [theme, setTheme] = useState<Theme>(() => stored("mynews.theme", ["system", "light", "dark"] as const, "system"));
  const [filter, setFilter] = useState<Filter>({});
  const [important, setImportant] = useState<Article[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canLoadMore, setCanLoadMore] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [sessionReady, setSessionReady] = useState(false);
  const [sheetArticle, setSheetArticle] = useState<Article | null>(null);

  useEffect(() => {
    persist("mynews.lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    persist("mynews.theme", theme);
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }, [theme]);

  // La sesión anónima va primero: así los feeds ya traen las valoraciones de este navegador.
  useEffect(() => {
    ensureSession().catch(() => undefined).finally(() => setSessionReady(true));
  }, []);

  useEffect(() => {
    if (!sessionReady) return;
    fetchImportant().then(setImportant).catch(() => setImportant([]));
    fetchMetrics().then(setMetrics).catch(() => setMetrics(null));
  }, [attempt, sessionReady]);

  useEffect(() => {
    if (!sessionReady) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchLatest(filter)
      .then((a) => { if (!cancelled) { setArticles(a); setCanLoadMore(a.length === PAGE_SIZE); } })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [filter, attempt, sessionReady]);

  const loadMore = useCallback(async () => {
    const last = articles.at(-1);
    if (!last) return;
    setLoading(true);
    try {
      const more = await fetchLatest({ ...filter, before: last.published_at });
      setArticles((prev) => [...prev, ...more]);
      setCanLoadMore(more.length === PAGE_SIZE);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [articles, filter]);

  const t = DICTS[lang];
  return (
    <LangContext.Provider value={lang}>
      <div className="page">
        <Masthead metrics={metrics} onLang={setLang} theme={theme} onTheme={setTheme} />
        <main>
          <Important articles={important} onComments={setSheetArticle} />
          <River
            articles={articles} filter={filter} onFilter={setFilter} loading={loading} error={error}
            canLoadMore={canLoadMore} onLoadMore={loadMore} onRetry={() => setAttempt(attempt + 1)}
          />
        </main>
        <footer className="colophon">
          <p>{t.colophon}</p>
          <a href="https://github.com/imhauke/my-news" target="_blank" rel="noopener noreferrer">github.com/imhauke/my-news</a>
        </footer>
        <CommentsSheet article={sheetArticle} onClose={() => setSheetArticle(null)} />
      </div>
    </LangContext.Provider>
  );
}
