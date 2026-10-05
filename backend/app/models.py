"""PostgreSQL schema."""

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 768


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_articles_source_external_id"),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_url_normalized", "url_normalized"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))  # reuters | ars | hn
    external_id: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(Text)
    url_normalized: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    title_es: Mapped[str | None] = mapped_column(Text)  # translated headline (stage 0)
    summary: Mapped[str | None] = mapped_column(Text)  # source excerpt (RSS or og:description)
    ai_summary_en: Mapped[str | None] = mapped_column(Text)  # generated short description (stage 0)
    ai_summary_es: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(String(64))
    author: Mapped[str | None] = mapped_column(String(128))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hn_points: Mapped[int | None] = mapped_column(Integer)
    hn_comment_count: Mapped[int | None] = mapped_column(Integer)
    hn_front_day: Mapped[date | None] = mapped_column(Date)  # day of the /front page it was ranked on
    hn_front_rank: Mapped[int | None] = mapped_column(Integer)  # 1-based position on that page
    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    topics_es: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    global_score: Mapped[float | None] = mapped_column(Float)
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("articles.id"))
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comments_pass: Mapped[int] = mapped_column(Integer, server_default="0")
    comments_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    """A user. Until sign-up exists (phase 3) each browser is an anonymous user identified by a
    cookie; only the token's hash is stored."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    anon_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    profile_text: Mapped[str | None] = mapped_column(Text)
    profile_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserInterest(Base):
    __tablename__ = "user_interests"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    cluster_id: Mapped[int] = mapped_column(primary_key=True)
    centroid: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MutedTopic(Base):
    __tablename__ = "muted_topics"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topic: Mapped[str] = mapped_column(String(128), primary_key=True)


class FeedItem(Base):
    __tablename__ = "feed_items"
    __table_args__ = (Index("ix_feed_items_user_generated", "user_id", "generated_at"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    stage_scores: Mapped[dict | None] = mapped_column(JSONB)
    final_score: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(Text)
    slot: Mapped[str] = mapped_column(String(16), default="ranked")  # ranked | explore
    variant: Mapped[str | None] = mapped_column(String(16))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArticleFeedback(Base):
    """A user's current rating (thumbs up/down) of an article. The full history is in events;
    this table holds the current state, shown in the UI and used by the For You feed."""

    __tablename__ = "article_feedback"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    value: Mapped[int] = mapped_column(Integer)  # 1 = interested, -1 = not interested
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    value: Mapped[float | None] = mapped_column(Float)
    variant: Mapped[str | None] = mapped_column(String(16))
    position: Mapped[int | None] = mapped_column(Integer)
    source_ranker: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HNComment(Base):
    __tablename__ = "hn_comments"
    __table_args__ = (Index("ix_hn_comments_tree", "story_id", "parent_id", "sibling_rank"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # HN id
    story_id: Mapped[int] = mapped_column(BigInteger)
    parent_id: Mapped[int | None] = mapped_column(BigInteger)
    author: Mapped[str | None] = mapped_column(String(64))
    text: Mapped[str | None] = mapped_column(Text)
    text_es: Mapped[str | None] = mapped_column(Text)  # translated on demand
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    depth: Mapped[int] = mapped_column(Integer, default=0)
    sibling_rank: Mapped[int] = mapped_column(Integer, default=0)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class ThreadInsight(Base):
    __tablename__ = "thread_insights"

    story_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    summary: Mapped[str | None] = mapped_column(Text)
    key_points: Mapped[list | None] = mapped_column(JSONB)
    disagreements: Mapped[list | None] = mapped_column(JSONB)
    notable_comments: Mapped[list | None] = mapped_column(JSONB)
    resources: Mapped[list | None] = mapped_column(JSONB)
    comments_covered: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        Index(
            "ix_embeddings_vector_hnsw",
            "vector",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"vector": "vector_cosine_ops"},
        ),
    )

    owner_type: Mapped[str] = mapped_column(String(16), primary_key=True)  # article | comment
    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model: Mapped[str] = mapped_column(String(64))
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))


class EvalLabel(Base):
    __tablename__ = "eval_labels"

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    label: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_model_created", "model", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64))
    requests: Mapped[int] = mapped_column(Integer, default=1)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16))  # ok | rate_limited | error
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
