import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { setConsent, setPrivacyOpen, useConsent } from "./consent";
import { useT } from "./i18n";
import { EASE_OUT } from "./motion";

/** Lets the masthead and the front lane enter first, so the note is not the first thing seen. */
export const NOTE_DELAY_MS = 1200;

/** A short editor's note asking whether MyNews may learn from the reader. It appears on the first
 *  visit, and on any later one until they choose (the choice is kept in localStorage). */
export function ConsentNote() {
  const t = useT();
  const consent = useConsent();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setReady(true), NOTE_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);
  const asked = ready && consent === null;
  return (
    <AnimatePresence>
      {asked && (
        <motion.aside
          className="consent-note"
          aria-labelledby="consent-kicker"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.45, ease: EASE_OUT }}
        >
          <p id="consent-kicker" className="consent-kicker">{t.consent.kicker}</p>
          <p className="consent-text">{t.consent.text}</p>
          <div className="consent-actions">
            <button className="consent-accept" onClick={() => void setConsent("granted")}>{t.consent.accept}</button>
            <button className="consent-decline" onClick={() => void setConsent("declined")}>{t.consent.decline}</button>
            <button className="text-button consent-more" onClick={() => setPrivacyOpen(true)} aria-haspopup="dialog">
              {t.consent.more}
            </button>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
