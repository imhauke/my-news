// Event capture: batches sent with navigator.sendBeacon to POST /events.
import { getConsent } from "./consent";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export type EventType =
  | "impression" | "click" | "like" | "dislike"
  | "more_like_this" | "less_like_this" | "hide" | "read_time";

export interface TrackedEvent {
  type: EventType;
  article_id?: number;
  value?: number;
  position?: number;
}

let queue: TrackedEvent[] = [];
let timer: ReturnType<typeof setTimeout> | undefined;

export function flush(): void {
  clearTimeout(timer);
  timer = undefined;
  if (queue.length === 0) return;
  const body = JSON.stringify({ events: queue.slice(0, 200) });
  queue = queue.slice(200);
  // Without consent the batch goes without the session cookie: anonymous counts, linked to no one.
  // (A beacon always carries cookies, so it is only used once the reader has agreed.)
  const granted = getConsent() === "granted";
  const blob = new Blob([body], { type: "application/json" });
  if (!granted || !navigator.sendBeacon?.(`${BASE}/events`, blob)) {
    void fetch(`${BASE}/events`, {
      method: "POST", body, headers: { "Content-Type": "application/json" }, keepalive: true,
      credentials: granted ? "same-origin" : "omit",
    }).catch(() => undefined);
  }
}

export function track(event: TrackedEvent): void {
  queue.push(event);
  timer ??= setTimeout(flush, 3000);
}

if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
}
