import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
import type { Article } from "./types";

interface Discussion {
  /** The story whose Hacker News thread is open in the side panel, if any. */
  active: Article | null;
  fullscreen: boolean;
  toggle: (article: Article) => void;
  close: () => void;
  setFullscreen: (value: boolean) => void;
}

const DiscussionContext = createContext<Discussion>({
  active: null, fullscreen: false, toggle: () => undefined, close: () => undefined, setFullscreen: () => undefined,
});

/** Wide screens make room for the panel (see :root[data-peek] in styles.css). */
const PUSHES_LAYOUT = "(min-width: 72rem)";

/**
 * Runs a DOM update inside a view transition when the browser supports it: the page reflows once
 * and the browser morphs every named block (see view-transition-name) from its old box to its
 * new one on the GPU. Elsewhere, or with reduced motion, the update is simply applied.
 */
function withViewTransition(update: () => void) {
  const reduce = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!("startViewTransition" in document) || reduce) {
    update();
    return;
  }
  document.startViewTransition(() => flushSync(update));
}

/** One discussion panel for the whole page: opening a thread from any story shows it there. */
export function DiscussionProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<Article | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const current = useRef<Article | null>(null);

  const show = useCallback((next: Article | null) => {
    const opensOrCloses = Boolean(next) !== Boolean(current.current);
    const commit = () => {
      current.current = next;
      setActive(next);
      if (!next) setFullscreen(false);
      const root = document.documentElement;
      if (next) root.dataset.peek = "";
      else delete root.dataset.peek;
    };
    const pushes = typeof matchMedia !== "undefined" && matchMedia(PUSHES_LAYOUT).matches;
    if (opensOrCloses && pushes) withViewTransition(commit);
    else commit();
  }, []);

  const toggle = useCallback((article: Article) => show(current.current?.id === article.id ? null : article), [show]);


  const close = useCallback(() => show(null), [show]);
  const value = useMemo(
    () => ({ active, fullscreen, toggle, close, setFullscreen }),
    [active, fullscreen, toggle, close],
  );
  return <DiscussionContext.Provider value={value}>{children}</DiscussionContext.Provider>;
}

export const useDiscussion = () => useContext(DiscussionContext);
