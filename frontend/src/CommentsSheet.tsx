import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Comments } from "./Comments";
import { headline } from "./format";
import { useLang, useT } from "./i18n";
import type { Article } from "./types";

/** Panel lateral con la discusión de HN para las noticias de la portada, donde no cabe en línea. */
export function CommentsSheet({ article, onClose }: { article: Article | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const t = useT();
  const lang = useLang();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (article && !dialog.open) dialog.showModal?.();
    if (!article && dialog.open) dialog.close();
  }, [article]);

  return (
    <dialog
      ref={ref}
      className="sheet"
      aria-labelledby="sheet-title"
      onClose={onClose}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {article && article.hn_story_id != null && (
        <div className="sheet-inner">
          <header className="sheet-head">
            <div>
              <p className="sheet-kind">{t.discussionTitle}</p>
              <h2 id="sheet-title" className="headline">{headline(article, lang)}</h2>
            </div>
            <button className="icon-button" onClick={onClose} aria-label={t.close}>
              <X aria-hidden size={18} />
            </button>
          </header>
          <Comments articleId={article.id} storyId={article.hn_story_id} />
        </div>
      )}
    </dialog>
  );
}
