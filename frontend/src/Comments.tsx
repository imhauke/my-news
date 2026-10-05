import { ChevronRight, ExternalLink, Languages } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchComments } from "./api";
import { timeAgo } from "./format";
import { useLang, useT } from "./i18n";
import type { CommentNode } from "./types";

function countAll(nodes: CommentNode[]): number {
  return nodes.reduce((n, c) => n + 1 + countAll(c.children), 0);
}

function Node({ node, translated }: { node: CommentNode; translated: boolean }) {
  const t = useT();
  const lang = useLang();
  const [open, setOpen] = useState(node.depth < 2);
  const replies = countAll(node.children);
  const missing = translated && !node.text_es;
  const text = translated ? node.text_es ?? node.text : node.text;
  return (
    <li className="comment">
      <button className="comment-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <ChevronRight aria-hidden size={14} className="chevron" />
        <span className="comment-author">{node.author ?? t.deleted}</span>
        <time dateTime={node.created_at}>{timeAgo(node.created_at, lang)}</time>
        {!open && replies > 0 && <span className="comment-folded">{t.replies(replies)}</span>}
      </button>
      {open && (
        <div className="comment-body">
          {missing && <span className="untranslated">{t.untranslated}</span>}
          <p lang={missing || !translated ? "en" : "es"}>{text}</p>
          {node.children.length > 0 && (
            <ul>{node.children.map((c) => <Node key={c.id} node={c} translated={translated} />)}</ul>
          )}
        </div>
      )}
    </li>
  );
}

export function Comments({ articleId, storyId }: { articleId: number; storyId: number }) {
  const lang = useLang();
  const t = useT();
  const [tree, setTree] = useState<CommentNode[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [showOriginal, setShowOriginal] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setTree(null);
    fetchComments(articleId, lang)
      .then((tr) => !cancelled && setTree(tr))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => { cancelled = true; };
  }, [articleId, lang, attempt]);

  const hnLink = (
    <a className="hn-link" href={`https://news.ycombinator.com/item?id=${storyId}`} target="_blank" rel="noopener noreferrer">
      {t.openOnHN} <ExternalLink aria-hidden size={13} />
    </a>
  );

  if (error) {
    return (
      <div className="discussion-state" role="alert">
        {t.discussionError(error)}{" "}
        <button className="text-button" onClick={() => setAttempt(attempt + 1)}>{t.retry}</button>
      </div>
    );
  }
  if (!tree) {
    return <div className="discussion-state" aria-live="polite">{lang === "es" ? t.loadingDiscussion : t.loadingDiscussionEn}</div>;
  }
  if (tree.length === 0) return <div className="discussion-state">{t.noComments} {hnLink}</div>;

  const translated = lang === "es" && !showOriginal;
  return (
    <div className="discussion">
      {lang === "es" && (
        <p className="translation-note">
          <Languages aria-hidden size={14} />
          {t.translatedNote}{" "}
          <button className="text-button" onClick={() => setShowOriginal(!showOriginal)}>
            {showOriginal ? t.showTranslation : t.showOriginal}
          </button>
        </p>
      )}
      <ul className="comment-tree">{tree.map((n) => <Node key={n.id} node={n} translated={translated} />)}</ul>
      {hnLink}
    </div>
  );
}
