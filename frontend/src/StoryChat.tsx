import { ArrowUp, Square } from "lucide-react";
import { motion } from "motion/react";
import { Fragment, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ChatError, type ChatTurn, streamChat } from "./api";
import { track } from "./events";
import { useLang, useT } from "./i18n";
import { EASE_OUT } from "./motion";
import type { Article } from "./types";

interface Message extends ChatTurn {
  /** Set when the answer failed; the message then shows why instead of (or after) its text. */
  error?: string;
}

const MAX_HISTORY = 20; // turns sent with each question (the API accepts 24)
const MAX_SENT_ANSWER = 4000;

// Conversations last while the page is open, so closing the panel and coming back keeps them.
const conversations = new Map<number, Message[]>();

/** With a mouse the text box takes focus on open; on touch screens that would pop up the
 *  keyboard over the suggestions, so the reader taps the box when they want to type. */
export const focusesInputOnOpen = () =>
  typeof matchMedia !== "undefined" && matchMedia("(hover: hover) and (pointer: fine)").matches;

/** Answers use a tiny subset of Markdown: paragraphs, "- " lists and **bold**. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : <Fragment key={i}>{part}</Fragment>,
  );
}

function Rich({ text }: { text: string }) {
  return (
    <>
      {text.split(/\n{2,}/).map((block, i) => {
        const lines = block.split("\n").filter((l) => l.trim());
        if (lines.length && lines.every((l) => /^\s*[-*•] /.test(l))) {
          return <ul key={i}>{lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*[-*•] /, ""))}</li>)}</ul>;
        }
        return <p key={i}>{inline(lines.join(" "))}</p>;
      })}
    </>
  );
}

/**
 * A short conversation with Gemini about one story, in the side panel. The answer streams in as
 * it is written; the reader can stop it. Suggested questions get a first-time reader started.
 */
export function StoryChat({ article }: { article: Article }) {
  const t = useT();
  const lang = useLang();
  const [messages, setMessages] = useState<Message[]>(() => conversations.get(article.id) ?? []);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const stick = useRef(true); // follow the answer while the reader is at the bottom

  useEffect(() => { conversations.set(article.id, messages); }, [article.id, messages]);
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => { if (focusesInputOnOpen()) input.current?.focus({ preventScroll: true }); }, []);

  // Only the conversation scrolls (the text box stays put): keep the newest text in view unless
  // the reader scrolled up.
  useLayoutEffect(() => {
    const scroller = log.current;
    if (scroller && stick.current) scroller.scrollTop = scroller.scrollHeight;
  }, [messages]);
  useEffect(() => {
    const scroller = log.current;
    if (!scroller) return;
    const onScroll = () => { stick.current = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 48; };
    scroller.addEventListener("scroll", onScroll, { passive: true });
    return () => scroller.removeEventListener("scroll", onScroll);
  }, []);

  // The text box grows with the question, up to a few lines.
  useLayoutEffect(() => {
    const el = input.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [draft]);

  async function ask(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    const history: ChatTurn[] = messages
      .filter((m) => m.text && !m.error)
      .map((m) => ({ role: m.role, text: m.text.slice(0, MAX_SENT_ANSWER) }));
    const sent = [...history, { role: "user" as const, text: question }].slice(-MAX_HISTORY);
    setMessages((cur) => [...cur, { role: "user", text: question }, { role: "model", text: "" }]);
    setDraft("");
    setBusy(true);
    stick.current = true;
    track({ type: "ask", article_id: article.id });
    const controller = new AbortController();
    abort.current = controller;
    const updateLast = (change: (m: Message) => Message) =>
      setMessages((cur) => [...cur.slice(0, -1), change(cur[cur.length - 1])]);
    try {
      await streamChat(article.id, sent, lang, (delta) => updateLast((m) => ({ ...m, text: m.text + delta })),
        controller.signal);
    } catch (e) {
      if (controller.signal.aborted) {
        setMessages((cur) => (cur[cur.length - 1]?.text ? cur : cur.slice(0, -1))); // stopped before any text
      } else {
        updateLast((m) => ({ ...m, error: e instanceof ChatError ? e.code : "unavailable" }));
      }
    } finally {
      abort.current = null;
      setBusy(false);
    }
  }

  const errorText = (code: string) =>
    code === "rate_limited" ? t.chat.rateLimited : code === "daily_limit" ? t.chat.dailyLimit : t.chat.unavailable;

  return (
    <div className="chat">
      <div className="chat-scroll" ref={log}>
      {messages.length === 0 ? (
        <div className="chat-intro">
          <p>{t.chat.intro}</p>
          <div className="chat-suggestions">
            {t.chat.suggestions.map((s) => (
              <button key={s} className="chat-suggestion" onClick={() => void ask(s)}>{s}</button>
            ))}
          </div>
        </div>
      ) : (
        <ol className="chat-log" aria-live="polite" aria-busy={busy || undefined}>
          {messages.map((m, i) => (
            <motion.li
              key={i}
              className={`chat-message chat-${m.role}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, ease: EASE_OUT }}
            >
              {m.role === "user" ? (
                <p>{m.text}</p>
              ) : (
                <div className="chat-answer" lang={lang}>
                  {m.text ? <Rich text={m.text} /> : !m.error && <span className="chat-typing" aria-label={t.chat.thinking}><i /><i /><i /></span>}
                  {m.error && <p className="chat-error" role="alert">{errorText(m.error)}</p>}
                </div>
              )}
            </motion.li>
          ))}
        </ol>
      )}
      </div>

      <form className="chat-composer" onSubmit={(e) => { e.preventDefault(); void ask(draft); }}>
        <textarea
          ref={input}
          rows={1}
          value={draft}
          maxLength={1000}
          placeholder={t.chat.placeholder}
          aria-label={t.chat.placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void ask(draft);
            }
          }}
        />
        {busy ? (
          <button type="button" className="chat-send" onClick={() => abort.current?.abort()} aria-label={t.chat.stop} title={t.chat.stop}>
            <Square aria-hidden size={13} fill="currentColor" />
          </button>
        ) : (
          <button type="submit" className="chat-send" disabled={!draft.trim()} aria-label={t.chat.send} title={t.chat.send}>
            <ArrowUp aria-hidden size={17} strokeWidth={2.25} />
          </button>
        )}
      </form>
      <p className="chat-notice">{t.chat.notice}</p>
    </div>
  );
}
