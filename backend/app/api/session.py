"""One anonymous user per browser (HttpOnly cookie). Enough to keep each reader's ratings apart;
sign-up with email arrives with the For You feed (phase 3)."""

import hashlib
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User

COOKIE = "mn_session"
ONE_YEAR = 365 * 24 * 3600


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def optional_user(request: Request, session: Annotated[AsyncSession, Depends(get_session)]) -> User | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    return await session.scalar(select(User).where(User.anon_token_hash == _hash(token)))


async def required_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(401, "no session: call POST /session first")
    return user


async def ensure_session(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User | None, Depends(optional_user)],
) -> User:
    """Returns the cookie's user, or creates an anonymous one and sets the cookie."""
    if user is not None:
        return user
    token = secrets.token_urlsafe(32)
    user = User(anon_token_hash=_hash(token))
    session.add(user)
    await session.commit()
    response.set_cookie(
        COOKIE, token, max_age=ONE_YEAR, httponly=True, samesite="lax", secure=get_settings().cookie_secure
    )
    return user
