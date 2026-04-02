"""HTTP client for the sidecar Mozilla Readability (Node) service."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any
from urllib.parse import urljoin

import httpx

from .config import get_settings


class ReadabilityOutcomeKind(Enum):
    """How the readability service call finished."""

    OK = "ok"
    UNCONFIGURED = "unconfigured"
    UNAVAILABLE = "unavailable"
    NOT_ARTICLE = "not_article"
    BAD_RESPONSE = "bad_response"


@dataclass(frozen=True, slots=True)
class ReadabilityArticle:
    """Article fields returned by the Readability sidecar."""

    title: str | None
    content: str
    text_content: str | None
    excerpt: str | None
    byline: str | None
    site_name: str | None
    published_time: str | None
    lang: str | None


@dataclass(frozen=True, slots=True)
class ReadabilityExtractResult:
    """Result of POST /extract to the readability service."""

    kind: ReadabilityOutcomeKind
    article: ReadabilityArticle | None = None
    detail: str | None = None


def _article_from_payload(data: dict[str, Any]) -> ReadabilityArticle:
    return ReadabilityArticle(
        title=data.get("title"),
        content=data.get("content") or "",
        text_content=data.get("textContent"),
        excerpt=data.get("excerpt"),
        byline=data.get("byline"),
        site_name=data.get("siteName"),
        published_time=data.get("publishedTime"),
        lang=data.get("lang"),
    )


def _extract_url(base: str) -> str:
    return urljoin(base.rstrip("/") + "/", "extract")


async def extract_via_readability(
    *,
    html: str,
    page_url: str,
    client: httpx.AsyncClient | None = None,
) -> ReadabilityExtractResult:
    """Call the Readability sidecar if configured; otherwise UNCONFIGURED."""

    settings = get_settings()
    base = settings.readability_service_url
    if base is None:
        return ReadabilityExtractResult(kind=ReadabilityOutcomeKind.UNCONFIGURED)

    timeout = httpx.Timeout(
        settings.url_read_timeout_seconds,
        connect=min(5.0, settings.url_read_timeout_seconds),
    )
    payload = {"html": html, "pageUrl": page_url}
    url = _extract_url(base)

    post_kwargs = {
        "json": payload,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
    }

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=timeout) as ac:
                response = await ac.post(url, **post_kwargs)
        else:
            response = await client.post(url, **post_kwargs)
    except httpx.RequestError as exc:
        return ReadabilityExtractResult(
            kind=ReadabilityOutcomeKind.UNAVAILABLE,
            detail=str(exc),
        )

    try:
        body: Any = response.json()
    except json.JSONDecodeError:
        return ReadabilityExtractResult(
            kind=ReadabilityOutcomeKind.BAD_RESPONSE,
            detail="Readability service returned non-JSON body.",
        )

    if not isinstance(body, dict):
        return ReadabilityExtractResult(
            kind=ReadabilityOutcomeKind.BAD_RESPONSE,
            detail="Readability service returned an invalid JSON object.",
        )

    if response.status_code == 413:
        return ReadabilityExtractResult(
            kind=ReadabilityOutcomeKind.BAD_RESPONSE,
            detail=body.get("error", "Payload too large for readability service."),
        )

    if response.status_code >= 500:
        return ReadabilityExtractResult(
            kind=ReadabilityOutcomeKind.UNAVAILABLE,
            detail=body.get("error") or f"HTTP {response.status_code}",
        )

    if response.status_code >= 400:
        return ReadabilityExtractResult(
            kind=ReadabilityOutcomeKind.BAD_RESPONSE,
            detail=body.get("error") or f"HTTP {response.status_code}",
        )

    if not body.get("ok"):
        return ReadabilityExtractResult(
            kind=ReadabilityOutcomeKind.NOT_ARTICLE,
            detail=body.get("error")
            or "Readability could not extract an article from this page.",
        )

    article_raw = body.get("article")
    if not isinstance(article_raw, dict):
        return ReadabilityExtractResult(
            kind=ReadabilityOutcomeKind.BAD_RESPONSE,
            detail="Readability service response missing `article` object.",
        )

    article = _article_from_payload(article_raw)
    if not article.content.strip():
        return ReadabilityExtractResult(
            kind=ReadabilityOutcomeKind.NOT_ARTICLE,
            detail="Readability returned empty article content.",
        )

    return ReadabilityExtractResult(
        kind=ReadabilityOutcomeKind.OK,
        article=article,
    )
