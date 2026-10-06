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
    image_url: str | None = None
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
    "impression", "click", "like", "dislike", "more_like_this", "less_like_this", "hide", "read_time", "ask"
]


class EventIn(BaseModel):
    type: EventType
    article_id: int | None = None
    value: float | None = None
    position: int | None = None


class DigestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    text_en: str
    text_es: str
    bullets_en: list[str] = []
    bullets_es: list[str] = []
    article_ids: list[int]
    created_at: datetime


class FeedbackIn(BaseModel):
    value: Literal[-1, 0, 1]


class EventBatch(BaseModel):
    events: list[EventIn] = Field(max_length=200)


class ChatMessage(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(min_length=1, max_length=4000)


class ChatIn(BaseModel):
    """The conversation so far, kept by the browser (the server stores none); the last turn is
    the reader's new question."""

    messages: list[ChatMessage] = Field(min_length=1, max_length=24)
    lang: Literal["es", "en"] = "es"
