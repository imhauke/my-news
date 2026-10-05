import { track } from "./events";
import { headline } from "./format";
import { useLang } from "./i18n";
import { markRead } from "./local";
import type { Article } from "./types";

/** Story headline linking to the original. Opening it logs a click and marks the story as read. */
export function Headline({ article, position }: { article: Article; position: number }) {
  const lang = useLang();
  return (
    <h3 className="headline" lang={lang === "es" && article.title_es ? "es" : "en"}>
      <a href={article.url} target="_blank" rel="noopener noreferrer"
         onClick={() => { track({ type: "click", article_id: article.id, position }); markRead(article.id); }}>
        {headline(article, lang)}
      </a>
    </h3>
  );
}
