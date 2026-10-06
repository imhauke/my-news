import { ExternalLink } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { loadInsight } from "./api";
import { useLang, useT } from "./i18n";
import { EASE_OUT } from "./motion";
import type { ThreadInsight } from "./types";

/**
 * "What the community says": the gist of a Hacker News thread above its comments. It appears
 * once the worker has analysed the thread; until then (or for small threads) nothing is shown.
 */
export function ThreadInsightCard({ articleId }: { articleId: number }) {
  const t = useT();
  const lang = useLang();
  const [insight, setInsight] = useState<ThreadInsight | null>(null);

  useEffect(() => {
    let cancelled = false;
    setInsight(null);
    loadInsight(articleId).then((i) => !cancelled && setInsight(i), () => undefined);
    return () => { cancelled = true; };
  }, [articleId]);

  if (!insight) return null;
  const es = lang === "es";
  const summary = es ? insight.summary_es ?? insight.summary_en : insight.summary_en;
  return (
    <motion.section
      className="insight"
      aria-labelledby="insight-title"
      lang={lang}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: EASE_OUT }}
    >
      <header className="insight-head">
        <h3 id="insight-title">{t.insight.title}</h3>
        {insight.tone && <span className="insight-tone" data-tone={insight.tone}>{t.insight.tones[insight.tone]}</span>}
      </header>
      {summary && <p className="insight-summary">{summary}</p>}
      {insight.points.length > 0 && (
        <ul className="insight-points">
          {insight.points.map((p) => (
            <li key={p.title_en}><strong>{es ? p.title_es : p.title_en}.</strong> {es ? p.text_es : p.text_en}</li>
          ))}
        </ul>
      )}
      {insight.contributions.length > 0 && (
        <>
          <h4>{t.insight.contributions}</h4>
          <ul className="insight-contributions">
            {insight.contributions.map((c) => (
              <li key={c.author}><span className="insight-author">{c.author}</span> {es ? c.text_es : c.text_en}</li>
            ))}
          </ul>
        </>
      )}
      {insight.resources.length > 0 && (
        <>
          <h4>{t.insight.resources}</h4>
          <ul className="insight-links">
            {insight.resources.map((r) => (
              <li key={r.url}>
                <a href={r.url} target="_blank" rel="noopener noreferrer">{r.title} <ExternalLink aria-hidden size={12} /></a>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="insight-note">{t.insight.basedOn(insight.comments_covered)}</p>
    </motion.section>
  );
}
