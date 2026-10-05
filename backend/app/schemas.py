from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    url: str
    title: str
    title_es: str | None
    summary: str | None
    ai_summary_en: str | None
    ai_summary_es: str | None
    section: str | None
    author: str | None
    published_at: datetime
    hn_points: int | None
    hn_comment_count: int | None
    hn_front_day: date | None = None
    hn_front_rank: int | None = None
    topics: list[str]
    topics_es: list[str]
    hn_story_id: int | None = None
    feedback: int = 0  # session user's rating: 1, -1 or 0


class CommentNode(BaseModel):
    id: int
    author: str | None
    text: str | None
    text_es: str | None = None
    created_at: datetime
    depth: int
    children: list["CommentNode"] = []


EventType = Literal[
    "impression", "click", "like", "dislike", "more_like_this", "less_like_this", "hide", "read_time"
]


class EventIn(BaseModel):
    type: EventType
    article_id: int | None = None
    value: float | None = None
    position: int | None = None


class FeedbackIn(BaseModel):
    value: Literal[-1, 0, 1]


class EventBatch(BaseModel):
    events: list[EventIn] = Field(max_length=200)
