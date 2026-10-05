"""Extracto de la página original (og:description) para fuentes cuyo feed no trae resumen."""

from html.parser import HTMLParser

_KEYS = ("og:description", "twitter:description", "description")


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        key = (a.get("property") or a.get("name") or "").lower()
        if key in _KEYS and a.get("content", "").strip():
            self.found.setdefault(key, " ".join(a["content"].split()))


def extract_description(html: str, *, min_length: int = 40, max_length: int = 400) -> str | None:
    parser = _MetaParser()
    parser.feed(html[:300_000])
    text = next((parser.found[k] for k in _KEYS if k in parser.found), None)
    if not text or len(text) < min_length:
        return None
    return text if len(text) <= max_length else text[: max_length - 1].rsplit(" ", 1)[0] + "…"
