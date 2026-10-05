"""Page metadata from the original article: excerpt (og:description) and lead image (og:image),
for sources whose feed does not carry them."""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

_KEYS = ("og:description", "twitter:description", "description")
_IMAGE_KEYS = ("og:image", "og:image:url", "twitter:image", "twitter:image:src")

# Share images that are not photographs: auto-generated text cards, logos and icons. In a
# black-and-white newspaper layout they read as pasted-in, so they are skipped.
_CARD_HOSTS = ("opengraph.githubassets.com", "og-image.vercel.app", "og.tailgraph.com")
_NOT_A_PHOTO = re.compile(r"(logo|favicon|icon|avatar|placeholder|default[-_]?(og|share|image)|\.svg|\.gif)",
                          re.IGNORECASE)


def looks_like_photo(url: str) -> bool:
    parts = urlsplit(url)
    if parts.hostname in _CARD_HOSTS:
        return False
    return not _NOT_A_PHOTO.search(parts.path)


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        key = (a.get("property") or a.get("name") or "").lower()
        if key in _KEYS + _IMAGE_KEYS and a.get("content", "").strip():
            self.found.setdefault(key, " ".join(a["content"].split()))


def extract_description(html: str, *, min_length: int = 40, max_length: int = 400) -> str | None:
    parser = _MetaParser()
    parser.feed(html[:300_000])
    text = next((parser.found[k] for k in _KEYS if k in parser.found), None)
    if not text or len(text) < min_length:
        return None
    return text if len(text) <= max_length else text[: max_length - 1].rsplit(" ", 1)[0] + "…"


def extract_image(html: str, base_url: str) -> str | None:
    """Absolute http(s) URL of the page's share image, if it declares one."""
    parser = _MetaParser()
    parser.feed(html[:300_000])
    raw = next((parser.found[k] for k in _IMAGE_KEYS if k in parser.found), None)
    if not raw:
        return None
    url = urljoin(base_url, raw)
    if not url.startswith(("https://", "http://")) or not looks_like_photo(url):
        return None
    return url
