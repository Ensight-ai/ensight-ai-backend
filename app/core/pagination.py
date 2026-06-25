"""Reusable pagination helpers (limit/offset + a typed page envelope)."""

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class PageParams:
    """Query params ``?limit=&offset=`` injected via ``Depends()``."""

    def __init__(
        self,
        limit: int = Query(
            DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max items to return"
        ),
        offset: int = Query(0, ge=0, description="Items to skip"),
    ) -> None:
        self.limit = limit
        self.offset = offset


class Page(BaseModel, Generic[T]):
    """A page of results plus the total count for building page controls."""

    items: list[T]
    total: int
    limit: int
    offset: int
