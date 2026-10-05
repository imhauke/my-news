import { motion } from "motion/react";
import type { ReactNode } from "react";

export interface Segment<T extends string> {
  value: T;
  label: ReactNode;
  /** Accessible name when the label is an icon. */
  ariaLabel?: string;
  lang?: string;
}

interface Props<T extends string> {
  /** Unique per control on the page: names the sliding thumb so it animates between segments. */
  id: string;
  label: string;
  segments: Segment<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: "regular" | "small";
}

/**
 * Segmented control in the manner of Apple's: a quiet track with a raised thumb that slides to
 * the chosen segment. Segments are buttons with aria-pressed, inside a labelled group.
 */
export function SegmentedControl<T extends string>({ id, label, segments, value, onChange, size = "regular" }: Props<T>) {
  return (
    <div className="segmented-control" data-size={size} role="group" aria-label={label}>
      {segments.map((s) => {
        const active = s.value === value;
        return (
          <button
            key={s.value}
            type="button"
            aria-pressed={active}
            aria-label={s.ariaLabel}
            title={s.ariaLabel}
            lang={s.lang}
            onClick={() => !active && onChange(s.value)}
          >
            {active && (
              <motion.span
                layoutId={`${id}-thumb`}
                className="segment-thumb"
                transition={{ type: "spring", stiffness: 520, damping: 40, mass: 0.9 }}
              />
            )}
            <span className="segment-label">{s.label}</span>
          </button>
        );
      })}
    </div>
  );
}
