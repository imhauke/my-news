import { ArrowUp, Check, MessageSquare, Sparkles } from "lucide-react";
import { FeedbackButtons } from "./FeedbackButtons";
import { SECTION_LABEL, useLang, useT } from "./i18n";
import { SOURCE_LABEL, firstTopic, formatNumber, timeAgo } from "./format";
import { prefetchComments } from "./api";
import { useDiscussion } from "./discussion";
import { useIsRead } from "./local";
import type { Article } from "./types";

interface Props {
  article: Article;
  showTime?: boolean;
}

export function StoryMeta({ article, showTime = true }: Props) {
  const lang = useLang();
  const t = useT();
  const read = useIsRead(article.id);
  const { active, mode, toggle } = useDiscussion();
  const commentsOpen = active?.id === article.id && mode === "comments";
  const chatOpen = active?.id === article.id && mode === "chat";
  // Reuters and Ars are labelled with their section; on HN everything is "front", so the topic is used.
  const label = article.source === "hn" || !article.section
    ? firstTopic(article, lang)
    : SECTION_LABEL[article.section]?.[lang] ?? article.section;
  return (
    <div className="meta">
      {read && (
        <span className="read-mark">
          <Check aria-hidden size={13} strokeWidth={2.5} />
          {t.read}
        </span>
      )}
      <span className="source">{SOURCE_LABEL[article.source]}</span>
      {label && <span className="topic">{label}</span>}
      {showTime && <time dateTime={article.published_at}>{timeAgo(article.published_at, lang)}</time>}
      {article.hn_points != null && (
        <span className="points" aria-label={t.points(article.hn_points)}>
          <ArrowUp aria-hidden size={14} strokeWidth={2.25} />
          {formatNumber(article.hn_points, lang)}
        </span>
      )}
      {article.hn_story_id != null && (
        <button
          className="comments-toggle"
          aria-expanded={commentsOpen}
          aria-controls={commentsOpen ? "discussion-panel" : undefined}
          onClick={() => toggle(article, "comments")}
          // Start loading on intent, so the panel usually opens with the thread already there.
          onPointerEnter={() => prefetchComments(article.id)}
          onFocus={() => prefetchComments(article.id)}
        >
          <MessageSquare aria-hidden size={14} strokeWidth={2} />
          {t.comments(article.hn_comment_count ?? 0)}
        </button>
      )}
      <button
        className="comments-toggle ask-toggle"
        aria-expanded={chatOpen}
        aria-controls={chatOpen ? "discussion-panel" : undefined}
        aria-label={t.chat.askLabel}
        title={t.chat.askLabel}
        onClick={() => toggle(article, "chat")}
      >
        <Sparkles aria-hidden size={14} strokeWidth={2} />
        {t.chat.ask}
      </button>
      <FeedbackButtons article={article} />
    </div>
  );
}
