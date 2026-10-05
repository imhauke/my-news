import { ExternalLink, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { formatNumber } from "./format";
import { useLang, useT } from "./i18n";
import type { Metrics } from "./types";

/** Author links. An empty URL hides its link. */
export const LINKS = {
  github: "https://github.com/imhauke/my-news",
  linkedin: "https://www.linkedin.com/in/janguzmanperez/",
  site: "https://janguzman.com",
};

function GithubMark() {
  return (
    <svg aria-hidden width="15" height="15" viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

function LinkedinMark() {
  return (
    <svg aria-hidden width="15" height="15" viewBox="0 0 16 16" fill="currentColor">
      <path d="M0 1.15C0 .52.52 0 1.15 0h13.7C15.48 0 16 .52 16 1.15v13.7c0 .63-.52 1.15-1.15 1.15H1.15A1.15 1.15 0 010 14.85V1.15zm4.94 12.24V6.17H2.54v7.22h2.4zM3.74 5.18c.84 0 1.36-.55 1.36-1.25-.02-.71-.52-1.25-1.34-1.25-.82 0-1.36.54-1.36 1.25 0 .7.52 1.25 1.33 1.25h.01zm4.91 8.21V9.36c0-.22.02-.43.08-.59.17-.43.57-.88 1.23-.88.87 0 1.21.66 1.21 1.63v3.87h2.4V9.25c0-2.22-1.18-3.25-2.76-3.25-1.3 0-1.88.72-2.2 1.22v.03h-.02l.02-.03V6.17h-2.4c.03.68 0 7.22 0 7.22h2.44z" />
    </svg>
  );
}

/** Explains where the news comes from and why, in a small scrollable dialog. */
function SourcesDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const t = useT();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal?.();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className="sources-dialog"
      aria-labelledby="sources-title"
      onClose={onClose}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="sources-inner">
        <header className="sources-head">
          <h2 id="sources-title">{t.sources.title}</h2>
          <button className="icon-button" onClick={onClose} aria-label={t.close} title={t.close}>
            <X aria-hidden size={18} />
          </button>
        </header>
        <div className="sources-body">
          <p className="sources-intro">{t.sources.intro}</p>
          {t.sources.items.map((s) => (
            <section key={s.name} className="source-entry" aria-labelledby={`source-${s.name}`}>
              <h3 id={`source-${s.name}`}>{s.name}</h3>
              <p className="source-sections">{s.sections}</p>
              <p>{s.text}</p>
            </section>
          ))}
          <p className="sources-closing">{t.sources.closing}</p>
        </div>
      </div>
    </dialog>
  );
}

export function Footer({ metrics }: { metrics: Metrics | null }) {
  const t = useT();
  const lang = useLang();
  const [sourcesOpen, setSourcesOpen] = useState(false);
  return (
    <footer className="colophon" style={{ viewTransitionName: "colophon" }}>
      <div className="colophon-text">
        {metrics && metrics.articles_total > 0 && (
          <p>{t.dateline(formatNumber(metrics.articles_total, lang), formatNumber(metrics.articles_enriched, lang))}</p>
        )}
        <p>{t.colophon}</p>
      </div>
      <nav className="colophon-links" aria-label={t.footerLinks}>
        <button className="colophon-link" onClick={() => setSourcesOpen(true)} aria-haspopup="dialog">
          {t.ourSources}
        </button>
        <a className="colophon-link" href={LINKS.github} target="_blank" rel="noopener noreferrer">
          <GithubMark /> GitHub
        </a>
        {LINKS.linkedin && (
          <a className="colophon-link" href={LINKS.linkedin} target="_blank" rel="noopener noreferrer">
            <LinkedinMark /> LinkedIn
          </a>
        )}
        <a className="colophon-link" href={LINKS.site} target="_blank" rel="noopener noreferrer">
          janguzman.com <ExternalLink aria-hidden size={13} />
        </a>
      </nav>
      <SourcesDialog open={sourcesOpen} onClose={() => setSourcesOpen(false)} />
    </footer>
  );
}
