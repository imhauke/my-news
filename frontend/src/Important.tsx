import { motion } from "motion/react";
import { useState } from "react";
import { description } from "./format";
import { Headline } from "./Headline";
import { useLang, useT } from "./i18n";
import { EASE_OUT, entrance } from "./motion";
import { Photo } from "./Photo";
import { StoryMeta } from "./StoryMeta";
import type { Article } from "./types";
import { useImpression } from "./useImpression";

interface StoryProps {
  article: Article;
  position: number;
  lead?: boolean;
  onComments: (a: Article) => void;
}

function Story({ article, position, lead, onComments }: StoryProps) {
  const lang = useLang();
  const ref = useImpression<HTMLElement>(article.id, position);
  const [hasPhoto, setHasPhoto] = useState(Boolean(article.image_url));
  const text = description(article, lang);
  const meta = (
    <StoryMeta article={article} onToggleComments={article.hn_story_id != null ? () => onComments(article) : undefined} />
  );
  // Part of the page-load sequence: masthead, then the lead, then the four stories in order.
  const enter = { ...entrance, transition: { duration: 0.7, ease: EASE_OUT, delay: 0.12 + position * 0.08 } };
  if (lead) {
    return (
      <motion.article ref={ref} className={`lead${hasPhoto ? " has-photo" : ""}`} {...enter}>
        <div className="lead-text">
          <Headline article={article} position={position} />
          {text && <p className="description" lang={lang}>{text}</p>}
          {meta}
        </div>
        <Photo src={article.image_url} className="lead-photo" onReject={() => setHasPhoto(false)} />
      </motion.article>
    );
  }
  return (
    <motion.article ref={ref} className="second" {...enter}>
      <Photo src={article.image_url} className="second-photo" width={640} />
      <Headline article={article} position={position} />
      {text && <p className="description" lang={lang}>{text}</p>}
      {meta}
    </motion.article>
  );
}

export function Important({ articles, onComments }: { articles: Article[]; onComments: (a: Article) => void }) {
  const t = useT();
  const [lead, ...rest] = articles;
  if (!lead) return null;
  return (
    <section className="important" aria-labelledby="important-title">
      <h2 id="important-title" className="section-title">{t.important}</h2>
      <Story article={lead} position={0} lead onComments={onComments} />
      {rest.length > 0 && (
        <div className="seconds">
          {rest.map((a, i) => <Story key={a.id} article={a} position={i + 1} onComments={onComments} />)}
        </div>
      )}
    </section>
  );
}
