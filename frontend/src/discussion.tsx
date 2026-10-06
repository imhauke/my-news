import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
import type { Article } from "./types";

/** What the side panel shows for its story: the Hacker News thread or a chat about the story. */
export type PanelMode = "comments" | "chat";

interface Discussion {
  /** The story open in the side panel, if any. */
  active: Article | null;
  mode: PanelMode;
  fullscreen: boolean;
  toggle: (article: Article, mode?: PanelMode) => void;
  close: () => void;
  setFullscreen: (value: boolean) => void;
}

const DiscussionContext = createContext<Discussion>({
  active: null, mode: "comments", fullscreen: false, toggle: () => undefined, close: () => undefined, setFullscreen: () => undefined,
});

/** Wide screens make room for the panel (see :root[data-peek] in styles.css). */
const PUSHES_LAYOUT = "(min-width: 72rem)";
/** Phones show the panel as a bottom sheet (see DiscussionPanel). */
const SHEET_LAYOUT = "(max-width: 52rem)";

const matches = (query: string) => typeof matchMedia !== "undefined" && matchMedia(query).matches;

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

/** One side panel for the whole page: a thread or a chat opened from any story shows it there. */
export function DiscussionProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<Article | null>(null);
  const [mode, setMode] = useState<PanelMode>("comments");
  const [fullscreen, setFullscreen] = useState(false);
  const current = useRef<Article | null>(null);
  const currentMode = useRef<PanelMode>("comments");

  const show = useCallback((next: Article | null, nextMode: PanelMode = "comments") => {
    const opensOrCloses = Boolean(next) !== Boolean(current.current);
    const commit = () => {
      current.current = next;
      currentMode.current = nextMode;
      setActive(next);
      setMode(nextMode);
      if (!next) setFullscreen(false);
      // On phones a chat needs the keyboard and the whole height: its sheet opens full screen.
      else if (nextMode === "chat" && matches(SHEET_LAYOUT)) setFullscreen(true);
      const root = document.documentElement;
      if (next) root.dataset.peek = "";
      else delete root.dataset.peek;
    };
    if (opensOrCloses && matches(PUSHES_LAYOUT)) withViewTransition(commit);
    else commit();
  }, []);

  const toggle = useCallback((article: Article, nextMode: PanelMode = "comments") => {
    const same = current.current?.id === article.id && currentMode.current === nextMode;
    show(same ? null : article, nextMode);
  }, [show]);

  const close = useCallback(() => show(null), [show]);
  const value = useMemo(
    () => ({ active, mode, fullscreen, toggle, close, setFullscreen }),
    [active, mode, fullscreen, toggle, close],
  );
  return <DiscussionContext.Provider value={value}>{children}</DiscussionContext.Provider>;
}

export const useDiscussion = () => useContext(DiscussionContext);
