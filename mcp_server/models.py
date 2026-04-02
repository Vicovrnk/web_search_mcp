"""Shared data models for tool schemas and normalized responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TimeRange = Literal["day", "month", "year"]


class SearchResult(BaseModel):
    """Normalized search result item returned to MCP clients."""

    title: str
    url: str
    content: str | None = None
    engine: str | None = None
    category: str | None = None
    score: float | None = None
    published_date: str | None = None
    thumbnail: str | None = None


class SearchResponse(BaseModel):
    """Normalized SearXNG search payload."""

    query: str
    number_of_results: int | None = None
    suggestions: list[str] = Field(default_factory=list)
    answers: list[str] = Field(default_factory=list)
    infoboxes: list[dict] = Field(default_factory=list)
    results: list[SearchResult] = Field(default_factory=list)


class EngineInfo(BaseModel):
    """Enabled engine metadata exposed through `search_config`."""

    name: str
    categories: list[str] = Field(default_factory=list)
    shortcut: str | None = None


class SearchConfigResponse(BaseModel):
    """Public instance capabilities relevant to MCP clients."""

    instance_name: str
    default_locale: str | None = None
    default_theme: str | None = None
    safe_search: int | None = None
    categories: list[str] = Field(default_factory=list)
    engines: list[EngineInfo] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)


class ReadUrlResponse(BaseModel):
    """Normalized HTML page content exposed through the `read_url` tool."""

    url: str
    final_url: str
    title: str | None = None
    content_markdown: str
    excerpt: str | None = None
    content_type: str | None = None
    status_code: int
