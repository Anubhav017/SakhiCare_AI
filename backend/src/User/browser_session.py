from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from src.User.models import UserModel
from src.utils.settings import settings

COOKIE_NAME = "sakhicare_session"
AUDIENCE = "sakhicare-browser"


def require_session_header(x_sakhicare_session: str | None = Header(None)) -> None:
    # A cross-origin HTML form cannot set this header.
    if x_sakhicare_session != "1":
        raise HTTPException(403, "Invalid browser session request")


def set_session(response: Response, user: UserModel, remember: bool) -> None:
    duration = timedelta(
        minutes=settings.REMEMBER_ME_HOURS * 60 if remember else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    token = jwt.encode(
        {"sub": str(user.id), "aud": AUDIENCE, "exp": datetime.now(timezone.utc) + duration},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(duration.total_seconds()) if remember else None,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="strict",
    )


def get_session(request: Request, db: Session) -> UserModel:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                audience=AUDIENCE,
                options={"require": ["sub", "aud", "exp"]},
            )
            user = db.get(UserModel, int(payload["sub"]))
            if user is not None:
                return user
        except (jwt.InvalidTokenError, ValueError):
            pass
    raise HTTPException(401, "Sign in to continue")


def clear_session(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="strict",
    )
