"""Tests for the Readability sidecar HTTP client."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_server.config import get_settings
from mcp_server.readability_client import ReadabilityOutcomeKind, extract_via_readability


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_extract_unconfigured_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("READABILITY_SERVICE_URL", raising=False)
    get_settings.cache_clear()

    result = asyncio.run(
        extract_via_readability(html="<html></html>", page_url="https://example.com/")
    )

    assert result.kind == ReadabilityOutcomeKind.UNCONFIGURED


def test_extract_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READABILITY_SERVICE_URL", "http://readability:3010")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "http://readability:3010/extract"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["pageUrl"] == "https://example.com/a"
        assert "noise" in payload["html"]
        return httpx.Response(
            200,
            json={
                "ok": True,
                "article": {
                    "title": "Story",
                    "content": "<p>Hello</p>",
                    "textContent": "Hello",
                },
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    result = asyncio.run(
        extract_via_readability(
            html="<html><body>noise</body></html>",
            page_url="https://example.com/a",
            client=httpx.AsyncClient(transport=transport),
        )
    )

    assert result.kind == ReadabilityOutcomeKind.OK
    assert result.article is not None
    assert result.article.title == "Story"
    assert result.article.content == "<p>Hello</p>"
    assert result.article.text_content == "Hello"


def test_extract_not_article(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READABILITY_SERVICE_URL", "http://readability:3010")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": False, "error": "No article here."},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    result = asyncio.run(
        extract_via_readability(
            html="<html></html>",
            page_url="https://example.com/",
            client=httpx.AsyncClient(transport=transport),
        )
    )

    assert result.kind == ReadabilityOutcomeKind.NOT_ARTICLE
    assert result.detail == "No article here."


def test_extract_empty_article_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READABILITY_SERVICE_URL", "http://readability:3010")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": True, "article": {"title": "T", "content": "   "}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    result = asyncio.run(
        extract_via_readability(
            html="<html></html>",
            page_url="https://example.com/",
            client=httpx.AsyncClient(transport=transport),
        )
    )

    assert result.kind == ReadabilityOutcomeKind.NOT_ARTICLE


def test_extract_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READABILITY_SERVICE_URL", "http://readability:3010")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json", request=request)

    transport = httpx.MockTransport(handler)
    result = asyncio.run(
        extract_via_readability(
            html="<html></html>",
            page_url="https://example.com/",
            client=httpx.AsyncClient(transport=transport),
        )
    )

    assert result.kind == ReadabilityOutcomeKind.BAD_RESPONSE


def test_extract_unavailable_on_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READABILITY_SERVICE_URL", "http://readability:3010")
    get_settings.cache_clear()

    async def boom(*args, **kwargs):
        raise httpx.RequestError("connection refused", request=httpx.Request("POST", "http://x"))

    with patch("mcp_server.readability_client.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.__aenter__.return_value = instance
        instance.__aexit__.return_value = None
        instance.post = boom
        mock_cls.return_value = instance

        result = asyncio.run(
            extract_via_readability(html="<html></html>", page_url="https://example.com/")
        )

    assert result.kind == ReadabilityOutcomeKind.UNAVAILABLE
    assert "connection refused" in (result.detail or "")
