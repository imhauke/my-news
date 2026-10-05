"""Plain text of the original article, read on demand for enrichment and never stored.

Feeds such as Ars Technica only ship a one-line dek, so a description built from it just restates
the headline. Reading the opening paragraphs of the original page gives the model real content."""

from html.parser import HTMLParser

_SKIP = {"script", "style", "nav", "footer", "aside", "figcaption", "form", "header"}
MIN_PARAGRAPH = 80
MIN_TOTAL = 600


class _Paragraphs(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self._current: list[str] | None = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._skip_depth += 1
        elif tag == "p":
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "p" and self._current is not None:
            text = " ".join("".join(self._current).split())
            self._current = None
            if len(text) >= MIN_PARAGRAPH:
                self.paragraphs.append(text)

    def handle_data(self, data: str) -> None:
        if self._current is not None and not self._skip_depth:
            self._current.append(data)


def extract_article_text(html: str, *, max_chars: int = 2500) -> str | None:
    """Opening paragraphs of the page, or None when there is not enough body text
    (author bios, paywalls, single-page apps)."""
    parser = _Paragraphs()
    parser.feed(html[:1_000_000])
    text = "\n\n".join(parser.paragraphs)
    if len(parser.paragraphs) < 3 or len(text) < MIN_TOTAL:
        return None
    return text[:max_chars]
