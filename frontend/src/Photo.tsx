import { useState } from "react";

/** Below this width or outside this aspect range a share image is usually a logo, an icon or a
 *  text banner rather than a photograph, and looks pasted-in next to real news photos. */
const MIN_WIDTH = 400;
const MIN_RATIO = 1.2;
const MAX_RATIO = 2.4;

export function isPhotoLike(width: number, height: number): boolean {
  if (!width || !height || width < MIN_WIDTH) return false;
  const ratio = width / height;
  return ratio >= MIN_RATIO && ratio <= MAX_RATIO;
}

/** Reuters' resizer serves any width from the same signed URL: thumbnails ask for a smaller one. */
export function sized(src: string, width: number): string {
  return src.includes("reuters.com/resizer/") ? src.replace(/([?&])width=\d+/, `$1width=${width}`) : src;
}

interface Props {
  src: string | null | undefined;
  className: string;
  /** Rendered width in CSS pixels, when the source can be asked for a smaller file. */
  width?: number;
  /** Called when the image turns out not to be a usable photo, so the layout can drop its slot. */
  onReject?: () => void;
}

/**
 * Source photo in black and white, cropped to a common 3:2 frame and faded in once loaded. The
 * frame is reserved while loading so text does not jump; images that fail or are not photo-like
 * are removed.
 */
export function Photo({ src, className, width, onReject }: Props) {
  const [state, setState] = useState<"loading" | "ready" | "rejected">("loading");
  if (!src || state === "rejected") return null;
  const reject = () => {
    setState("rejected");
    onReject?.();
  };
  return (
    <figure className={`photo ${className}`} data-state={state}>
      <img
        src={width ? sized(src, width) : src}
        alt=""
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        onLoad={(e) => (isPhotoLike(e.currentTarget.naturalWidth, e.currentTarget.naturalHeight) ? setState("ready") : reject())}
        onError={reject}
      />
    </figure>
  );
}
