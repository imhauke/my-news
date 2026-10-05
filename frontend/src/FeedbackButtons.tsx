import { ThumbsDown, ThumbsUp } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { putFeedback } from "./api";
import { useT } from "./i18n";
import { saveVote, useVote } from "./local";
import { EASE_OUT } from "./motion";
import type { Article } from "./types";

type Vote = 1 | -1;
const SPARK_ANGLES = Array.from({ length: 8 }, (_, i) => (i * Math.PI) / 4 + Math.PI / 8);
const CELEBRATION_MS = 760;

/** A ring of short strokes flying out of the button and fading (after React Bits' Click Spark). */
function Sparks() {
  return (
    <span className="sparks" aria-hidden>
      {SPARK_ANGLES.map((angle) => (
        <motion.span
          key={angle}
          className="spark"
          style={{ rotate: (angle * 180) / Math.PI }}
          initial={{ x: Math.cos(angle) * 10, y: Math.sin(angle) * 10, scaleX: 1, opacity: 1 }}
          animate={{ x: Math.cos(angle) * 26, y: Math.sin(angle) * 26, scaleX: 0.15, opacity: 0 }}
          // Fly out fast, fade late: the strokes stay visible for most of their travel.
          transition={{ duration: 0.6, ease: EASE_OUT, opacity: { duration: 0.55, ease: [0.42, 0, 1, 1] } }}
        />
      ))}
    </span>
  );
}

/**
 * Thumbs up / down. The vote is stored in this browser (and sent to the API as an event). The
 * chosen thumb pops with a burst of sparks and the other one shrinks away; then the control fades
 * out in place. Its space is kept, also on later visits, so nothing around it ever shifts.
 */
export function FeedbackButtons({ article }: { article: Article }) {
  const t = useT();
  const voted = useVote(article.id);
  const reduceMotion = useReducedMotion();
  const [celebrating, setCelebrating] = useState<Vote | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  const done = voted !== 0 && celebrating === null;

  function rate(value: Vote) {
    if (celebrating || voted) return;
    saveVote(article, value);
    putFeedback(article.id, value).catch(() => undefined); // best effort: the local vote is what counts
    setCelebrating(value);
    timer.current = setTimeout(() => setCelebrating(null), reduceMotion ? 120 : CELEBRATION_MS);
  }

  const buttons: { value: Vote; label: string; Icon: typeof ThumbsUp }[] = [
    { value: 1, label: t.like, Icon: ThumbsUp },
    { value: -1, label: t.dislike, Icon: ThumbsDown },
  ];

  return (
    <motion.span
      className="feedback"
      role="group"
      aria-label={t.feedbackHint}
      aria-hidden={done || undefined}
      title={done ? undefined : t.feedbackHint}
      initial={done ? { opacity: 0, visibility: "hidden" } : false}
      animate={done ? { opacity: 0, transitionEnd: { visibility: "hidden" } } : { opacity: 1, visibility: "visible" }}
      transition={{ duration: 0.3, ease: EASE_OUT }}
    >
      {buttons.map(({ value, label, Icon }) => {
        const chosen = celebrating === value;
        const other = celebrating !== null && !chosen;
        const tilt = value === 1 ? -1 : 1;
        return (
          <motion.button
            key={value}
            type="button"
            className={`vote ${value === 1 ? "vote-up" : "vote-down"}`}
            aria-label={label}
            aria-pressed={chosen}
            data-chosen={chosen || undefined}
            tabIndex={done ? -1 : undefined}
            onClick={() => rate(value)}
            animate={
              chosen && !reduceMotion
                ? { scale: [1, 1.5, 0.9, 1.1, 1], rotate: [0, 18 * tilt, -6 * tilt, 0] }
                : other
                  ? { opacity: 0, scale: 0.4 }
                  : { opacity: 1, scale: 1, rotate: 0 }
            }
            transition={chosen ? { duration: 0.6, ease: "easeOut" } : { duration: 0.2, ease: EASE_OUT }}
            whileTap={celebrating || done ? undefined : { scale: 0.85 }}
          >
            <Icon aria-hidden size={15} strokeWidth={2} />
            {chosen && !reduceMotion && <Sparks />}
          </motion.button>
        );
      })}
    </motion.span>
  );
}
