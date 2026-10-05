import { Monitor, Moon, Sun } from "lucide-react";
import { formatNumber, todayLine } from "./format";
import { useLang, useT } from "./i18n";
import type { Lang, Metrics, Theme } from "./types";

function GithubMark() {
  return (
    <svg aria-hidden width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

interface Props {
  metrics: Metrics | null;
  onLang: (l: Lang) => void;
  theme: Theme;
  onTheme: (t: Theme) => void;
}

export function Masthead({ metrics, onLang, theme, onTheme }: Props) {
  const lang = useLang();
  const t = useT();
  const themes: { value: Theme; label: string; Icon: typeof Sun }[] = [
    { value: "light", label: t.themeLight, Icon: Sun },
    { value: "dark", label: t.themeDark, Icon: Moon },
    { value: "system", label: t.themeSystem, Icon: Monitor },
  ];
  return (
    <header className="masthead">
      <div className="masthead-top">
        <h1 className="wordmark">MyNews</h1>
        <div className="masthead-tools">
          <div className="segmented" role="group" aria-label={t.langGroup}>
            {(["es", "en"] as Lang[]).map((l) => (
              <button key={l} aria-pressed={lang === l} onClick={() => onLang(l)} lang={l}
                      aria-label={l === "es" ? "Español" : "English"}>
                {l.toUpperCase()}
              </button>
            ))}
          </div>
          <div className="segmented" role="group" aria-label={t.themeGroup}>
            {themes.map(({ value, label, Icon }) => (
              <button key={value} aria-pressed={theme === value} onClick={() => onTheme(value)}
                      aria-label={label} title={label}>
                <Icon aria-hidden size={15} />
              </button>
            ))}
          </div>
          <a className="repo-link" href="https://github.com/imhauke/my-news" target="_blank" rel="noopener noreferrer">
            <GithubMark /> {t.code}
          </a>
        </div>
      </div>
      <p className="dateline">
        <time>{todayLine(lang)}</time>
        {metrics && metrics.articles_total > 0 && (
          <span>{t.dateline(formatNumber(metrics.articles_total, lang), formatNumber(metrics.articles_enriched, lang))}</span>
        )}
      </p>
    </header>
  );
}
