import { ArrowUp, Maximize2, MessageSquare, Minimize2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Comments } from "./Comments";
import { StoryChat } from "./StoryChat";
import { useDiscussion } from "./discussion";
import { headline } from "./format";
import { useLang, useT } from "./i18n";
import { useMediaQuery } from "./useMediaQuery";

const SPRING = { type: "spring", stiffness: 420, damping: 42, mass: 0.9 } as const;
const FADE_OUT_MS = 90;
const MORPH_MS = 460;
const MORPH = { duration: MORPH_MS / 1000, ease: [0.32, 0.72, 0, 1] } as const; // Apple-like glide

/** Left edge and width of the floating panel, docked or full screen, tracking the window size. */
function useSideGeometry(enabled: boolean, fullscreen: boolean) {
  const [vw, setVw] = useState(() => (typeof window === "undefined" ? 1440 : window.innerWidth));
  useEffect(() => {
    if (!enabled) return;
    const onResize = () => setVw(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [enabled]);
  const rem = 16;
  const inset = 0.75 * rem;
  const docked = Math.min(Math.max(22 * rem, 0.3 * vw), 27 * rem); // matches --peek-w
  return fullscreen
    ? { left: inset, width: vw - inset * 2 }
    : { left: vw - inset - docked, width: docked };
}

/**
 * A story's Hacker News discussion, or a chat about the story, in a floating, non-modal panel: no
 * backdrop and no focus trap, so the page stays visible, scrollable and clickable. Opening
 * another story swaps the content in place. Docked on the right on wide screens (the page makes
 * room for it), a bottom sheet on phones.
 */
export function DiscussionPanel() {
  const { active, mode, close, fullscreen, setFullscreen } = useDiscussion();
  const t = useT();
  const lang = useLang();
  const compact = useMediaQuery("(max-width: 52rem)");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const chat = mode === "chat";
  const open = Boolean(active && (chat || active.hn_story_id != null));
  // Full screen on wide screens: the text fades out, the browser stops laying it out
  // (content-visibility), the panel's real box glides to its new position and width, and the
  // text fades back in. Nothing is scaled, so shadow, border and corners stay crisp.
  const [phase, setPhase] = useState<"idle" | "fading" | "moving">("idle");
  const changeFullscreen = useCallback((value: boolean) => {
    if (compact) {
      setFullscreen(value);
      return;
    }
    setPhase("fading");
    window.setTimeout(() => {
      setPhase("moving");
      setFullscreen(value);
      window.setTimeout(() => setPhase("idle"), MORPH_MS - 80); // text returns during the last stretch
    }, FADE_OUT_MS);
  }, [compact, setFullscreen]);
  const box = useSideGeometry(!compact, fullscreen);

  // Esc leaves full screen first, then closes, from anywhere on the page.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (fullscreen) changeFullscreen(false);
      else close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close, fullscreen, changeFullscreen]);

  // On open or switch: remember what opened it, move focus to the title (a chat focuses its text
  // box instead), start at the top.
  useEffect(() => {
    if (!active) return;
    if (!triggerRef.current && document.activeElement instanceof HTMLElement) triggerRef.current = document.activeElement;
    if (!chat) headingRef.current?.focus({ preventScroll: true });
    if (bodyRef.current) bodyRef.current.scrollTop = 0;
  }, [active, chat]);

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
      {open && active && (chat || active.hn_story_id != null) && (
        <motion.aside
          key="discussion"
          id="discussion-panel"
          className="discussion-panel"
          data-layout={compact ? "sheet" : "side"}
          data-fullscreen={fullscreen || undefined}
          aria-labelledby="discussion-title"
          style={{ borderRadius: compact ? undefined : 14, viewTransitionName: "discussion" }}
          initial={compact ? hidden : { ...hidden, ...box }}
          animate={compact ? shown : { ...shown, ...box }}
          exit={hidden}
          transition={{ ...SPRING, left: MORPH, width: MORPH }}
        >
          {compact && (
            <button className="sheet-handle" onClick={() => changeFullscreen(!fullscreen)}
                    aria-label={fullscreen ? t.collapsePanel : t.expandPanel} aria-expanded={fullscreen}>
              <span />
            </button>
          )}
          <motion.div
            className="panel-content"
            data-phase={phase}
            animate={{ opacity: phase === "idle" ? 1 : 0 }}
            transition={{ duration: phase === "idle" ? 0.24 : FADE_OUT_MS / 1000, ease: "easeOut" }}
          >
          <header className="panel-head">
            <div className="panel-heading">
              <p className="panel-kind">{chat ? t.chat.title : t.discussionTitle}</p>
              <h2 id="discussion-title" ref={headingRef} tabIndex={-1} className="headline">{headline(active, lang)}</h2>
              {!chat && <p className="panel-stats">
                {active.hn_points != null && (
                  <span><ArrowUp aria-hidden size={13} strokeWidth={2.25} />{t.points(active.hn_points)}</span>
                )}
                <span><MessageSquare aria-hidden size={13} />{t.comments(active.hn_comment_count ?? 0)}</span>
              </p>}
            </div>
            <div className="panel-actions">
              <button className="icon-button" onClick={() => changeFullscreen(!fullscreen)}
                      aria-label={fullscreen ? t.collapsePanel : t.expandPanel} aria-pressed={fullscreen}
                      title={fullscreen ? t.collapsePanel : t.expandPanel}>
                <FullscreenIcon aria-hidden size={16} />
              </button>
              <button className="icon-button" onClick={close} aria-label={t.close} title={t.close}>
                <X aria-hidden size={18} />
              </button>
            </div>
          </header>
          <div className="panel-body" ref={bodyRef} data-mode={mode}>
            <AnimatePresence mode="wait">
              <motion.div key={`${active.id}:${mode}`} className="panel-view" initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.14 }}>
                {chat || active.hn_story_id == null
                  ? <StoryChat article={active} />
                  : <Comments articleId={active.id} storyId={active.hn_story_id} />}
              </motion.div>
            </AnimatePresence>
          </div>
          </motion.div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
