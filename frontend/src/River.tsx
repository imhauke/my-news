import { useState } from "react";
import { Comments } from "./Comments";
import { track } from "./events";
import { SOURCE_LABEL, SOURCE_SECTIONS, clockTime, description, groupByDay, headline } from "./format";
import { SECTION_LABEL, useLang, useT } from "./i18n";
import { StoryMeta } from "./StoryMeta";
import type { Article, Source } from "./types";
import { useImpression } from "./useImpression";

function RiverItem({ article, position }: { article: Article; position: number }) {
  const lang = useLang();
  const ref = useImpression<HTMLLIElement>(article.id, position);
  const [open, setOpen] = useState(false);
  const text = description(article, lang);
  return (
    <li ref={ref} className="river-item">
      <time className="clock" dateTime={article.published_at}>{clockTime(article.published_at, lang)}</time>
      <div className="river-body">
        <h3 className="headline" lang={lang === "es" && article.title_es ? "es" : "en"}>
          <a href={article.url} target="_blank" rel="noopener noreferrer"
             onClick={() => track({ type: "click", article_id: article.id, position })}>
            {headline(article, lang)}
          </a>
        </h3>
        {text && <p className="description" lang={lang}>{text}</p>}
        <StoryMeta article={article} showTime={false} commentsOpen={open} onToggleComments={() => setOpen(!open)} />
        {article.hn_story_id != null && (
          <div className="expander" data-open={open}>
            <div>{open && <Comments articleId={article.id} storyId={article.hn_story_id} />}</div>
          </div>
        )}
      </div>
    </li>
  );
}

export interface Filter {
  source?: Source;
  section?: string;
}

interface Props {
  articles: Article[];
  filter: Filter;
  onFilter: (f: Filter) => void;
  loading: boolean;
  error: string | null;
  canLoadMore: boolean;
  onLoadMore: () => void;
  onRetry: () => void;
}

export function River({ articles, filter, onFilter, loading, error, canLoadMore, onLoadMore, onRetry }: Props) {
  const lang = useLang();
  const t = useT();
  const sections = filter.source ? SOURCE_SECTIONS[filter.source] : [];
  let position = 100; // las posiciones del río empiezan tras las de la portada
  return (
    <section className="river" aria-labelledby="river-title">
      <div className="river-head">
        <h2 id="river-title" className="section-title">{t.latest}</h2>
        <div className="filter-rows">
          <nav className="filters" aria-label={t.filterSource}>
            <button aria-pressed={!filter.source} onClick={() => onFilter({})}>{t.all}</button>
            {(Object.keys(SOURCE_LABEL) as Source[]).map((s) => (
              <button key={s} aria-pressed={filter.source === s} onClick={() => onFilter({ source: s })}>
                {SOURCE_LABEL[s]}
              </button>
            ))}
          </nav>
          {sections.length > 0 && filter.source && (
            <nav className="filters subfilters" aria-label={t.filterSection}>
              <button aria-pressed={!filter.section} onClick={() => onFilter({ source: filter.source })}>
                {t.allOf(SOURCE_LABEL[filter.source])}
              </button>
              {sections.map((sec) => (
                <button key={sec} aria-pressed={filter.section === sec}
                        onClick={() => onFilter({ source: filter.source, section: sec })}>
                  {SECTION_LABEL[sec]?.[lang] ?? sec}
                </button>
              ))}
            </nav>
          )}
        </div>
      </div>

      {error && (
        <p className="state" role="alert">
          {t.feedError(error)} <button className="text-button" onClick={onRetry}>{t.retry}</button>
        </p>
      )}
      {!error && !loading && articles.length === 0 && <p className="state">{t.emptySource}</p>}

      {groupByDay(articles, lang).map((g) => (
        <div key={g.label} className="day">
          <h3 className="day-label">{g.label}</h3>
          <ol className="river-list">
            {g.items.map((a) => <RiverItem key={a.id} article={a} position={position++} />)}
          </ol>
        </div>
      ))}

      {loading && <p className="state" aria-live="polite">{t.loadingNews}</p>}
      {canLoadMore && !loading && articles.length > 0 && (
        <button className="load-more" onClick={onLoadMore}>{t.loadMore}</button>
      )}
    </section>
  );
}
