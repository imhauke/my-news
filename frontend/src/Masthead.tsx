import { Monitor, Moon, Sun } from "lucide-react";
import { motion } from "motion/react";
import { formatNumber, toBullets, todayLine } from "./format";
import { useLang, useT } from "./i18n";
import { EASE_OUT, entrance } from "./motion";
import { SegmentedControl } from "./SegmentedControl";
import type { DigestKind, Digests, Lang, Metrics, Theme } from "./types";

interface Props {
  metrics: Metrics | null;
  digests: Digests;
  digestKind: DigestKind;
  onDigestKind: (k: DigestKind) => void;
  onLang: (l: Lang) => void;
  theme: Theme;
  onTheme: (t: Theme) => void;
}

const DIGEST_KINDS: DigestKind[] = ["general", "world", "tech"];

export function Masthead({ metrics, digests, digestKind, onDigestKind, onLang, theme, onTheme }: Props) {
  const lang = useLang();
  const t = useT();
  const available = DIGEST_KINDS.filter((k) => digests[k]);
  const kind = available.includes(digestKind) ? digestKind : available[0] ?? "general";
  const current = digests[kind] ?? null;
  const themes: { value: Theme; label: string; Icon: typeof Sun }[] = [
    { value: "light", label: t.themeLight, Icon: Sun },
    { value: "dark", label: t.themeDark, Icon: Moon },
    { value: "system", label: t.themeSystem, Icon: Monitor },
  ];
  return (
    <motion.header className="masthead" style={{ viewTransitionName: "masthead" }} {...entrance}
                   transition={{ duration: 0.8, ease: EASE_OUT }}>
      <div className="masthead-top">
        <h1 className="wordmark">MyNews</h1>
        <div className="masthead-tools">
          <SegmentedControl
            id="lang"
            label={t.langGroup}
            value={lang}
            onChange={onLang}
            segments={(["es", "en"] as Lang[]).map((l) => ({
              value: l, label: l.toUpperCase(), lang: l, ariaLabel: l === "es" ? "Español" : "English",
            }))}
          />
          <SegmentedControl
            id="theme"
            label={t.themeGroup}
            value={theme}
            onChange={onTheme}
            segments={themes.map(({ value, label, Icon }) => ({ value, ariaLabel: label, label: <Icon aria-hidden size={15} /> }))}
          />
        </div>
      </div>
      <div className="dateline">
        <time>{todayLine(lang)}</time>
        {available.length > 1 && (
          <SegmentedControl
            id="digest"
            size="small"
            label={t.digestGroup}
            value={kind}
            onChange={onDigestKind}
            segments={available.map((k) => ({ value: k, label: t.digestKinds[k] }))}
          />
        )}
        {!current && metrics && metrics.articles_total > 0 && (
          <span>{t.dateline(formatNumber(metrics.articles_total, lang), formatNumber(metrics.articles_enriched, lang))}</span>
        )}
      </div>
      {current && (
        <div className="digest">
          {/* All overviews share one cell: it takes the height of the longest, so switching
              between them cross-fades without moving anything below. */}
          <div className="digest-stack">
            {available.map((k) => {
              const d = digests[k]!;
              const text = lang === "es" ? d.text_es : d.text_en;
              return (
                <div key={k} className="digest-text" lang={lang} data-active={k === kind || undefined} aria-hidden={k !== kind}>
                  {/* Paragraph in two columns on wide screens; short points on phones. */}
                  <p className="digest-paragraph">{text}</p>
                  <ul className="digest-bullets">
                    {toBullets(text, lang === "es" ? d.bullets_es : d.bullets_en).map((b) => <li key={b}>{b}</li>)}
                  </ul>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </motion.header>
  );
}
