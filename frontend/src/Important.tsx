import { track } from "./events";
import { description, headline } from "./format";
import { useLang, useT } from "./i18n";
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
  const text = description(article, lang);
  const title = (
    <h3 className="headline" lang={lang === "es" && article.title_es ? "es" : "en"}>
      <a href={article.url} target="_blank" rel="noopener noreferrer"
         onClick={() => track({ type: "click", article_id: article.id, position })}>
        {headline(article, lang)}
      </a>
    </h3>
  );
  const body = (
    <>
      {text && <p className="description" lang={lang}>{text}</p>}
      <StoryMeta article={article} onToggleComments={article.hn_story_id != null ? () => onComments(article) : undefined} />
    </>
  );
  return (
    <article ref={ref} className={lead ? "lead" : "second"} style={{ "--i": position } as React.CSSProperties}>
      {lead ? <>{title}<div className="lead-body">{body}</div></> : <>{title}{body}</>}
    </article>
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
