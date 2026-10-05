"""Usuario anónimo por navegador (cookie HttpOnly). Basta para guardar las valoraciones de cada
lector sin mezclarlas; el registro con email llegará con el feed «Para ti» (fase 3)."""

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
        raise HTTPException(401, "sin sesión: llama antes a POST /session")
    return user


async def ensure_session(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User | None, Depends(optional_user)],
) -> User:
    """Devuelve el usuario de la cookie o crea uno anónimo y le pone la cookie."""
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
