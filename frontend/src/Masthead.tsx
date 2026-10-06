import { Monitor, Moon, Sun } from "lucide-react";
import { motion } from "motion/react";
import { formatNumber, toBullets, todayLine } from "./format";
import { useLang, useT } from "./i18n";
import { EASE_OUT, entrance } from "./motion";
import { SegmentedControl } from "./SegmentedControl";
import type { Digest, Lang, Metrics, Theme } from "./types";

interface Props {
  metrics: Metrics | null;
  digest: Digest | null;
  onLang: (l: Lang) => void;
  theme: Theme;
  onTheme: (t: Theme) => void;
}

export function Masthead({ metrics, digest, onLang, theme, onTheme }: Props) {
  const lang = useLang();
  const t = useT();
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
        {!digest && metrics && metrics.articles_total > 0 && (
          <span>{t.dateline(formatNumber(metrics.articles_total, lang), formatNumber(metrics.articles_enriched, lang))}</span>
        )}
      </div>
      {digest && (
        <div className="digest">
          <p className="digest-kicker"><strong>{t.digestTitle}</strong> · {t.digestNote}</p>
          {/* Paragraph in two columns on wide screens; short points on phones. */}
          <div className="digest-text" lang={lang} data-active>
            <p className="digest-paragraph">{lang === "es" ? digest.text_es : digest.text_en}</p>
            <ul className="digest-bullets">
              {toBullets(lang === "es" ? digest.text_es : digest.text_en, lang === "es" ? digest.bullets_es : digest.bullets_en)
                .map((b) => <li key={b}>{b}</li>)}
            </ul>
          </div>
        </div>
      )}
    </motion.header>
  );
}
