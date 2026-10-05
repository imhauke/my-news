import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { putFeedback } from "./api";
import { useT } from "./i18n";
import type { Feedback } from "./types";

/** Pulgar arriba / abajo. Pulsar el activo lo quita. Actualización optimista con vuelta atrás. */
export function FeedbackButtons({ articleId, initial }: { articleId: number; initial: Feedback }) {
  const t = useT();
  const [value, setValue] = useState<Feedback>(initial);
  const [failed, setFailed] = useState(false);

  async function rate(next: Feedback) {
    const target: Feedback = value === next ? 0 : next;
    const previous = value;
    setValue(target);
    setFailed(false);
    try {
      await putFeedback(articleId, target);
    } catch {
      setValue(previous);
      setFailed(true);
    }
  }

  return (
    <span className="feedback" role="group" aria-label={t.feedbackHint} title={t.feedbackHint}>
      <button className="vote vote-up" aria-pressed={value === 1} aria-label={t.like} onClick={() => rate(1)}>
        <ThumbsUp aria-hidden size={15} strokeWidth={2} />
      </button>
      <button className="vote vote-down" aria-pressed={value === -1} aria-label={t.dislike} onClick={() => rate(-1)}>
        <ThumbsDown aria-hidden size={15} strokeWidth={2} />
      </button>
      {failed && <span className="vote-error" role="status">{t.feedbackError}</span>}
    </span>
  );
}
