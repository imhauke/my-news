import { useEffect, useRef } from "react";
import { track } from "./events";

/** Logs an impression once the element is at least half visible. */
export function useImpression<T extends HTMLElement>(articleId: number, position: number) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          track({ type: "impression", article_id: articleId, position });
          io.disconnect();
        }
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [articleId, position]);
  return ref;
}
