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
