"""Shared FastAPI dependencies and error helpers."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..context import AppContext, get_context
from ..database import get_session


def context_from(request: Request) -> AppContext:
    return get_context()


def db_session() -> Iterator[Session]:
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def transactional_session() -> Iterator[Session]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def error_response(status_code: int, code: str, detail: str, correlation_id: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": code,
            "code": code,
            "detail": detail,
            "correlation_id": correlation_id or uuid.uuid4().hex[:12],
        },
    )
