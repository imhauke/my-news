import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useT } from "./i18n";

const MIN_CHARS = 3;
const DEBOUNCE_MS = 600;

/**
 * Search by meaning: results follow the typing after a short pause (or at once with Enter), and
 * clearing the box brings the timeline back. Each new query costs one embedding request, hence
 * the pause and the minimum length.
 */
export function SearchBox({ query, onSearch }: { query: string; onSearch: (q: string) => void }) {
  const t = useT();
  const [draft, setDraft] = useState(query);

  useEffect(() => { setDraft(query); }, [query]);

  useEffect(() => {
    const q = draft.trim();
    if (q === query || (q && q.length < MIN_CHARS)) return;
    const timer = setTimeout(() => onSearch(q), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [draft, query, onSearch]);

  const clear = () => {
    setDraft("");
    onSearch("");
  };

  return (
    <form
      role="search"
      className="search-box"
      onSubmit={(e) => {
        e.preventDefault();
        const q = draft.trim();
        if (!q || q.length >= 2) onSearch(q);
      }}
    >
      <Search aria-hidden size={16} className="search-icon" />
      <input
        type="search"
        value={draft}
        maxLength={200}
        enterKeyHint="search"
        placeholder={t.search.placeholder}
        aria-label={t.search.label}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Escape" && draft) { e.preventDefault(); clear(); } }}
      />
      {draft && (
        <button type="button" className="search-clear" onClick={clear} aria-label={t.search.clear} title={t.search.clear}>
          <X aria-hidden size={15} />
        </button>
      )}
    </form>
  );
}
