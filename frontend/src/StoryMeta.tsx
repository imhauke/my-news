import { ArrowUp, MessageSquare } from "lucide-react";
import { FeedbackButtons } from "./FeedbackButtons";
import { SECTION_LABEL, useLang, useT } from "./i18n";
import { SOURCE_LABEL, firstTopic, formatNumber, timeAgo } from "./format";
import type { Article } from "./types";

interface Props {
  article: Article;
  showTime?: boolean;
  commentsOpen?: boolean;
  onToggleComments?: () => void;
}

export function StoryMeta({ article, showTime = true, commentsOpen, onToggleComments }: Props) {
  const lang = useLang();
  const t = useT();
  // Reuters and Ars are labelled with their section; on HN everything is "front", so the topic is used.
  const label = article.source === "hn" || !article.section
    ? firstTopic(article, lang)
    : SECTION_LABEL[article.section]?.[lang] ?? article.section;
  return (
    <div className="meta">
      <span className="source">{SOURCE_LABEL[article.source]}</span>
      {label && <span className="topic">{label}</span>}
      {showTime && <time dateTime={article.published_at}>{timeAgo(article.published_at, lang)}</time>}
      {article.hn_points != null && (
        <span className="points" aria-label={t.points(article.hn_points)}>
          <ArrowUp aria-hidden size={14} strokeWidth={2.25} />
          {formatNumber(article.hn_points, lang)}
        </span>
      )}
      {article.hn_story_id != null && onToggleComments && (
        <button className="comments-toggle" onClick={onToggleComments} aria-expanded={commentsOpen}>
          <MessageSquare aria-hidden size={14} strokeWidth={2} />
          {commentsOpen ? t.hideComments : t.comments(article.hn_comment_count ?? 0)}
        </button>
      )}
      <FeedbackButtons articleId={article.id} initial={article.feedback} />
    </div>
  );
}
