/** Shared motion vocabulary: one easing and one entrance, so every reveal feels the same. */
export const EASE_OUT = [0.16, 1, 0.3, 1] as const;

/** Rise, unblur and fade in. Used on page load and when stories scroll into view. */
export const entrance = {
  initial: { opacity: 0, y: 28, filter: "blur(6px)" },
  animate: { opacity: 1, y: 0, filter: "blur(0px)" },
};

/** Stories revealed within this window after the list mounts are staggered as one sequence;
 *  later ones (scrolling) appear on their own without delay. */
export const LOAD_SEQUENCE_MS = 1200;
export const STAGGER_S = 0.07;
export const MAX_STAGGER_STEPS = 8;
export const REVEAL_S = 0.6;

// Recent scroll speed in px/ms, smoothed over the last few scroll events.
let lastY = 0;
let lastT = 0;
let speed = 0;
if (typeof window !== "undefined") {
  window.addEventListener("scroll", () => {
    const now = performance.now();
    const y = window.scrollY;
    const dt = now - lastT;
    speed = dt > 0 && dt < 200 ? 0.6 * speed + (0.4 * Math.abs(y - lastY)) / dt : 0;
    lastY = y;
    lastT = now;
  }, { passive: true });
}

/** How fast the page is scrolling right now, in px/ms (0 once it has settled). */
export function scrollSpeed() {
  return performance.now() - lastT > 150 ? 0 : speed;
}

/** Entrance for a story scrolled into view: the full reveal when reading slowly, ever shorter as
 *  the scroll speeds up, so a fast scroll never outruns the content. */
export function scrollReveal() {
  return { duration: Math.max(0.15, REVEAL_S / Math.max(scrollSpeed(), 1)), ease: EASE_OUT };
}
