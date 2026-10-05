import { useSyncExternalStore } from "react";
import { deleteSession, ensureSession, putFeedback } from "./api";
import { localVotes } from "./local";

/**
 * The reader's choice about personalisation. Until they agree, the server knows nothing that
 * identifies them: no session cookie is created and events are sent without credentials, as
 * anonymous counts. Language, theme, read marks and votes stay in this browser either way.
 */
export type Consent = "granted" | "declined" | null;

const KEY = "mynews.consent.v1";

function load(): Consent {
  try {
    const value = localStorage.getItem(KEY);
    return value === "granted" || value === "declined" ? value : null;
  } catch {
    return null;
  }
}

let consent: Consent = load();
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const getConsent = () => consent;
export const useConsent = () => useSyncExternalStore(subscribe, getConsent);

/** Uploads the ratings made before consent, so the For You feed starts from them. */
async function syncLocalVotes() {
  for (const [id, vote] of localVotes()) {
    await putFeedback(id, vote.value).catch(() => undefined);
  }
}

export async function setConsent(value: Exclude<Consent, null>) {
  const previous = consent;
  consent = value;
  try {
    localStorage.setItem(KEY, value);
  } catch {
    /* blocked storage: the choice lasts for this visit */
  }
  emit();
  if (value === "granted" && previous !== "granted") {
    await ensureSession().catch(() => undefined);
    await syncLocalVotes();
  }
  // Withdrawing (or declining with a cookie left from an earlier visit) erases the server side.
  if (value === "declined") await deleteSession().catch(() => undefined);
}

let privacyOpen = false;
export const usePrivacyOpen = () => useSyncExternalStore(subscribe, () => privacyOpen);
export function setPrivacyOpen(open: boolean) {
  privacyOpen = open;
  emit();
}

/** For tests. */
export function resetConsent() {
  consent = load();
  emit();
}
