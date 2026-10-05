from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ParsedArticle:
    source: str
    external_id: str
    url: str
    title: str
    published_at: datetime
    summary: str | None = None
    section: str | None = None
    author: str | None = None
    hn_points: int | None = None
    hn_comment_count: int | None = None


@dataclass(frozen=True)
class ParsedComment:
    id: int
    story_id: int
    parent_id: int | None
    author: str | None
    text: str | None
    created_at: datetime
    depth: int
    sibling_rank: int
    deleted: bool
