import { AnimatePresence, motion } from "motion/react";
import { useRef, useState } from "react";
import { SOURCE_LABEL, SOURCE_SECTIONS, clockTime, description, groupByDay, groupByFrontDay } from "./format";
import { Headline } from "./Headline";
import { EASE_OUT, LOAD_SEQUENCE_MS, MAX_STAGGER_STEPS, STAGGER_S, entrance } from "./motion";
import { Photo } from "./Photo";
import { SegmentedControl } from "./SegmentedControl";
import { SECTION_LABEL, useLang, useT } from "./i18n";
import { StoryMeta } from "./StoryMeta";
import type { Article, Source } from "./types";
import { useImpression } from "./useImpression";

interface ItemProps {
  article: Article;
  position: number;
  ranked: boolean;
  /** Seconds to wait before revealing: staggers the stories visible on load, 0 when scrolling. */
  delay: number;
}

function RiverItem({ article, position, ranked, delay }: ItemProps) {
  const lang = useLang();
  const ref = useImpression<HTMLLIElement>(article.id, position);
  const [hasPhoto, setHasPhoto] = useState(Boolean(article.image_url));
  const text = description(article, lang);
  return (
    <motion.li
      ref={ref}
      className={`river-item${hasPhoto ? " has-photo" : ""}`}
      style={{ viewTransitionName: `river-${article.id}` }}
      initial={entrance.initial}
      whileInView={entrance.animate}
      viewport={{ once: true, amount: 0.1 }}
      transition={{ duration: 0.6, ease: EASE_OUT, delay }}
    >
      {ranked && article.hn_front_rank != null ? (
        <span className="clock rank">{article.hn_front_rank}.</span>
      ) : (
        <time className="clock" dateTime={article.published_at}>{clockTime(article.published_at, lang)}</time>
      )}
      <div className="river-body">
        <Headline article={article} position={position} />
        {text && <p className="description" lang={lang}>{text}</p>}
        <StoryMeta article={article} showTime={false} />
      </div>
      <Photo src={article.image_url} className="river-photo" width={480} onReject={() => setHasPhoto(false)} />
    </motion.li>
  );
}

export interface Filter {
  source?: Source;
  section?: string;
}

interface Props {
  articles: Article[];
  /** Identifies the list currently shown; changing it cross-fades the river (e.g. new source). */
  listKey: string;
  filter: Filter;
  onFilter: (f: Filter) => void;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  canLoadMore: boolean;
  onLoadMore: () => void;
  onRetry: () => void;
}

export function River({
  articles, listKey, filter, onFilter, loading, loadingMore, error, canLoadMore, onLoadMore, onRetry,
}: Props) {
  const lang = useLang();
  const t = useT();
  const sections = filter.source ? SOURCE_SECTIONS[filter.source] : [];
  // When a new list arrives (page load, another source), its visible stories enter as one
  // staggered sequence after the front lane; stories revealed later by scrolling enter at once.
  const mountedAt = useRef(Date.now());
  const shownKey = useRef("");
  if (articles.length === 0 || shownKey.current !== listKey) {
    shownKey.current = articles.length ? listKey : "";
    mountedAt.current = Date.now();
  }
  const ranked = filter.source === "hn"; // HN follows /front: grouped by day, in its own ranking
  const groups = ranked ? groupByFrontDay(articles, lang) : groupByDay(articles, lang);
  let position = 100; // river positions start after the front-page lane
  let step = 0;
  const delayFor = () => (Date.now() - mountedAt.current < LOAD_SEQUENCE_MS
    ? 0.35 + Math.min(step++, MAX_STAGGER_STEPS) * STAGGER_S
    : 0);
  return (
    <section className="river" aria-labelledby="river-title">
      <div className="river-head" style={{ viewTransitionName: "river-head" }}>
        <h2 id="river-title" className="section-title">{t.latest}</h2>
        <div className="filter-rows">
          <SegmentedControl
            id="source"
            label={t.filterSource}
            value={filter.source ?? "all"}
            onChange={(v) => onFilter(v === "all" ? {} : { source: v })}
            segments={[
              { value: "all" as const, label: t.all },
              ...(Object.keys(SOURCE_LABEL) as Source[]).map((s) => ({ value: s, label: SOURCE_LABEL[s] })),
            ]}
          />
          {/* The section row always keeps its height, so switching source never moves the list. */}
          <div className="subfilter-slot">
            <AnimatePresence mode="popLayout">
              {sections.length > 0 && filter.source && (
                <motion.div
                  key={filter.source}
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.22, ease: EASE_OUT }}
                >
                  <SegmentedControl
                    id={`section-${filter.source}`}
                    size="small"
                    label={t.filterSection}
                    value={filter.section ?? "all"}
                    onChange={(v) => onFilter(v === "all" ? { source: filter.source } : { source: filter.source, section: v })}
                    segments={[
                      { value: "all", label: t.all },
                      ...sections.map((sec) => ({ value: sec, label: SECTION_LABEL[sec]?.[lang] ?? sec })),
                    ]}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {error && (
        <p className="state" role="alert">
          {t.feedError(error)} <button className="text-button" onClick={onRetry}>{t.retry}</button>
        </p>
      )}
      {!error && !loading && articles.length === 0 && <p className="state">{t.emptySource}</p>}

      {/* Keyed by the list shown: a new source mounts a fresh list whose stories play their entrance,
          with no empty frame in between. While the next list loads, the current one dims. */}
      <motion.div
        key={listKey}
        className="river-lists"
        aria-busy={loading || undefined}
        animate={{ opacity: loading && articles.length > 0 ? 0.45 : 1 }}
        transition={{ duration: 0.25 }}
      >
        {groups.map((g, i) => (
          <div key={g.label} className="day">
            <h3 className="day-label" style={{ viewTransitionName: `day-${i}` }}>{g.label}</h3>
            <ol className="river-list">
              {g.items.map((a) => <RiverItem key={a.id} article={a} position={position++} ranked={ranked} delay={delayFor()} />)}
            </ol>
          </div>
        ))}
      </motion.div>

      {((loading && articles.length === 0) || loadingMore) && <p className="state" aria-live="polite">{t.loadingNews}</p>}
      {canLoadMore && !loading && !loadingMore && articles.length > 0 && (
        <button className="load-more" onClick={onLoadMore}>{t.loadMore}</button>
      )}
    </section>
  );
}
