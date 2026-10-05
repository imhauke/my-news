import re
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|ref_src$|cmpid$)", re.I)


def normalize_url(url: str) -> str:
    """URL canónica para deduplicar: sin esquema, www, tracking, fragmento ni barra final."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k)))
    path = parts.path.rstrip("/")
    return urlunsplit(("", host, path, query, "")).lstrip("/")


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", title.lower()).strip()


def titles_similar(a: str, b: str, threshold: float = 0.88) -> bool:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return False
    return SequenceMatcher(None, na, nb).ratio() >= threshold


class _TextExtractor(HTMLParser):
    """HTML → texto conservando enlaces y bloques de código."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._href: str | None = None
        self._in_pre = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self.out.append("\n\n")
        elif tag == "br":
            self.out.append("\n")
        elif tag == "a":
            self._href = dict(attrs).get("href")
        elif tag == "pre":
            self._in_pre = True
            self.out.append("\n```\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._href = None
        elif tag == "pre":
            self._in_pre = False
            self.out.append("\n```\n")

    def handle_data(self, data: str) -> None:
        if self._href and data.strip() != self._href:
            self.out.append(f"{data} ({self._href})")
        else:
            self.out.append(data)


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    return re.sub(r"\n{3,}", "\n\n", "".join(parser.out)).strip()
