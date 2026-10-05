import { ArrowUp, Maximize2, MessageSquare, Minimize2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";
import { Comments } from "./Comments";
import { useDiscussion } from "./discussion";
import { headline } from "./format";
import { useLang, useT } from "./i18n";
import { useMediaQuery } from "./useMediaQuery";

const SPRING = { type: "spring", stiffness: 420, damping: 42, mass: 0.9 } as const;

/**
 * Hacker News discussion in a floating, non-modal panel: no backdrop and no focus trap, so the
 * page stays visible, scrollable and clickable. Opening another story's comments swaps the thread
 * in place. Docked on the right on wide screens (the page makes room for it), a half-height
 * bottom sheet on phones.
 */
export function DiscussionPanel() {
  const { active, close, fullscreen, setFullscreen } = useDiscussion();
  const t = useT();
  const lang = useLang();
  const compact = useMediaQuery("(max-width: 52rem)");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const open = Boolean(active && active.hn_story_id != null);

  // Esc leaves full screen first, then closes, from anywhere on the page.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (fullscreen) setFullscreen(false);
      else close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close, fullscreen, setFullscreen]);

  // On open or thread switch: remember what opened it, move focus to the title, start at the top.
  useEffect(() => {
    if (!active) return;
    if (!triggerRef.current && document.activeElement instanceof HTMLElement) triggerRef.current = document.activeElement;
    headingRef.current?.focus({ preventScroll: true });
    if (bodyRef.current) bodyRef.current.scrollTop = 0;
  }, [active]);

  // On close: give focus back to the button that opened it.
  useEffect(() => {
    if (open || !triggerRef.current) return;
    if (triggerRef.current.isConnected) triggerRef.current.focus({ preventScroll: true });
    triggerRef.current = null;
  }, [open]);

  // Phones: a full-height sheet moved by transform; half open it shows the top 58% of it.
  const viewport = typeof window === "undefined" ? 800 : window.innerHeight;
  const hidden = compact ? { y: viewport } : { x: "calc(100% + 2rem)" };
  const shown = compact ? { y: fullscreen ? 0 : Math.round(viewport * 0.42) } : { x: 0 };
  const FullscreenIcon = fullscreen ? Minimize2 : Maximize2;
  return (
    <AnimatePresence>
      {open && active && active.hn_story_id != null && (
        <motion.aside
          key="discussion"
          id="discussion-panel"
          className="discussion-panel"
          data-layout={compact ? "sheet" : "side"}
          data-fullscreen={fullscreen || undefined}
          aria-labelledby="discussion-title"
          layout={!compact}
          style={{ borderRadius: compact ? undefined : 14, viewTransitionName: "discussion" }}
          initial={hidden}
          animate={shown}
          exit={hidden}
          transition={{ ...SPRING, layout: { type: "spring", stiffness: 360, damping: 38 } }}
        >
          {compact && (
            <button className="sheet-handle" onClick={() => setFullscreen(!fullscreen)}
                    aria-label={fullscreen ? t.collapsePanel : t.expandPanel} aria-expanded={fullscreen}>
              <span />
            </button>
          )}
          <motion.header layout={!compact ? "position" : false} className="panel-head">
            <div className="panel-heading">
              <p className="panel-kind">{t.discussionTitle}</p>
              <h2 id="discussion-title" ref={headingRef} tabIndex={-1} className="headline">{headline(active, lang)}</h2>
              <p className="panel-stats">
                {active.hn_points != null && (
                  <span><ArrowUp aria-hidden size={13} strokeWidth={2.25} />{t.points(active.hn_points)}</span>
                )}
                <span><MessageSquare aria-hidden size={13} />{t.comments(active.hn_comment_count ?? 0)}</span>
              </p>
            </div>
            <div className="panel-actions">
              <button className="icon-button" onClick={() => setFullscreen(!fullscreen)}
                      aria-label={fullscreen ? t.collapsePanel : t.expandPanel} aria-pressed={fullscreen}
                      title={fullscreen ? t.collapsePanel : t.expandPanel}>
                <FullscreenIcon aria-hidden size={16} />
              </button>
              <button className="icon-button" onClick={close} aria-label={t.close} title={t.close}>
                <X aria-hidden size={18} />
              </button>
            </div>
          </motion.header>
          <motion.div layout={!compact ? "position" : false} className="panel-body" ref={bodyRef}>
            <AnimatePresence mode="wait">
              <motion.div key={active.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                          transition={{ duration: 0.14 }}>
                <Comments articleId={active.id} storyId={active.hn_story_id} />
              </motion.div>
            </AnimatePresence>
          </motion.div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
