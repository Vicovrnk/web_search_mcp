"""Targeted tests for the URL reader tool."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_server.readability_client import (
    ReadabilityArticle,
    ReadabilityExtractResult,
    ReadabilityOutcomeKind,
)
from mcp_server.config import URL_READ_DEFAULT_MAX_BYTES, get_settings
from mcp_server.tools.read_url import execute_url_read
from mcp_server.url_reader import (
    UrlReadRequestError,
    UrlReadResponseError,
    normalize_html_document,
    read_url_document,
    validate_url,
)


def test_normalize_html_document_converts_html_to_markdown() -> None:
    normalized = normalize_html_document(
        url="https://example.com/article",
        final_url="https://example.com/article",
        status_code=200,
        content_type="text/html; charset=utf-8",
        html="""
        <html>
          <head>
            <title>Example article</title>
            <style>.hidden { display: none; }</style>
          </head>
          <body>
            <nav>Navigation should disappear</nav>
            <main>
              <h1>Example article</h1>
              <p>Read the <a href="https://example.com/docs">docs</a> for <code>jax.jit</code>.</p>
              <ul>
                <li>First item</li>
                <li>Second item</li>
              </ul>
              <pre>print("hello")</pre>
              <script>console.log("ignore me")</script>
            </main>
            <footer>Footer should disappear</footer>
          </body>
        </html>
        """,
        max_chars=1_000,
    )

    content = normalized["content_markdown"]
    assert normalized["title"] == "Example article"
    assert "# Example article" in content
    assert "[docs](https://example.com/docs)" in content
    assert "`jax.jit`" in content
    assert "- First item" in content
    assert 'print("hello")' in content
    assert "ignore me" not in content
    assert "Footer should disappear" not in content
    assert normalized["excerpt"] is not None


def test_normalize_html_document_truncates_long_content() -> None:
    normalized = normalize_html_document(
        url="https://example.com/article",
        final_url="https://example.com/article",
        status_code=200,
        content_type="text/html",
        html=f"<html><body><main><p>{'word ' * 200}</p></main></body></html>",
        max_chars=80,
    )

    assert len(normalized["content_markdown"]) <= 80
    assert normalized["content_markdown"].endswith("...")


def test_execute_url_read_follows_redirects() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.com/start":
            return httpx.Response(
                302,
                headers={"location": "https://example.com/final"},
                request=request,
            )

        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="""
            <html>
              <head><title>Final page</title></head>
              <body><main><p>Redirected content.</p></main></body>
            </html>
            """,
            request=request,
        )

    transport = httpx.MockTransport(handler)
    normalized = asyncio.run(
        execute_url_read(
            url="https://example.com/start",
            max_chars=500,
            max_body_bytes=URL_READ_DEFAULT_MAX_BYTES,
            transport=transport,
        )
    )

    assert normalized["url"] == "https://example.com/start"
    assert normalized["final_url"] == "https://example.com/final"
    assert normalized["status_code"] == 200
    assert "Redirected content." in normalized["content_markdown"]


def test_execute_url_read_rejects_non_html_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"message": "not html"},
            request=request,
        )

    transport = httpx.MockTransport(handler)

    with pytest.raises(UrlReadResponseError, match="HTML document"):
        asyncio.run(
            execute_url_read(
                url="https://example.com/data.json",
                max_chars=500,
                max_body_bytes=URL_READ_DEFAULT_MAX_BYTES,
                transport=transport,
            )
        )


def test_default_url_read_max_bytes_is_five_mebibyte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("URL_READ_MAX_BYTES", raising=False)
    get_settings.cache_clear()
    assert get_settings().url_read_max_bytes == 5 * 1024 * 1024


def test_execute_url_read_rejects_response_exceeding_max_body_bytes() -> None:
    payload = b"<html><body><main><p>" + b"x" * 20_000 + b"</p></main></body></html>"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html; charset=utf-8",
                "content-length": str(len(payload)),
            },
            content=payload,
            request=request,
        )

    transport = httpx.MockTransport(handler)

    with pytest.raises(UrlReadResponseError, match="exceeds the configured limit"):
        asyncio.run(
            execute_url_read(
                url="https://example.com/huge.html",
                max_chars=500,
                max_body_bytes=4_096,
                transport=transport,
            )
        )


def test_validate_url_rejects_non_http_scheme() -> None:
    with pytest.raises(ValueError, match="http` or `https"):
        validate_url("ftp://example.com/file.txt")


def test_read_url_document_uses_readability_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READABILITY_SERVICE_URL", "http://readability:3010")
    get_settings.cache_clear()

    async def fetch_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body><nav>Nav</nav><p>noise</p></body></html>",
            request=request,
        )

    transport = httpx.MockTransport(fetch_handler)

    article = ReadabilityArticle(
        title="From Readability",
        content="<p>Clean body</p>",
        text_content="Clean body",
        excerpt=None,
        byline=None,
        site_name=None,
        published_time=None,
        lang=None,
    )
    extract_result = ReadabilityExtractResult(
        kind=ReadabilityOutcomeKind.OK,
        article=article,
    )

    with patch(
        "mcp_server.url_reader.extract_via_readability",
        new_callable=AsyncMock,
        return_value=extract_result,
    ) as extract_mock:
        normalized = asyncio.run(
            read_url_document(
                url="https://example.com/page",
                max_chars=2_000,
                transport=transport,
            )
        )

    extract_mock.assert_awaited_once()
    assert normalized["title"] == "From Readability"
    assert "Clean body" in normalized["content_markdown"]
    assert "Nav" not in normalized["content_markdown"]


def test_read_url_document_falls_back_when_readability_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READABILITY_SERVICE_URL", "http://readability:3010")
    monkeypatch.setenv("READABILITY_FALLBACK_ON_FAILURE", "true")
    get_settings.cache_clear()

    async def fetch_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="""
            <html><head><title>Full</title></head>
            <body><main><p>Fallback paragraph.</p></main></body></html>
            """,
            request=request,
        )

    transport = httpx.MockTransport(fetch_handler)
    fail_result = ReadabilityExtractResult(
        kind=ReadabilityOutcomeKind.NOT_ARTICLE,
        detail="No article",
    )

    with patch(
        "mcp_server.url_reader.extract_via_readability",
        new_callable=AsyncMock,
        return_value=fail_result,
    ):
        normalized = asyncio.run(
            read_url_document(
                url="https://example.com/page",
                max_chars=2_000,
                transport=transport,
            )
        )

    assert normalized["title"] == "Full"
    assert "Fallback paragraph." in normalized["content_markdown"]


def test_read_url_document_raises_when_readability_fails_and_fallback_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READABILITY_SERVICE_URL", "http://readability:3010")
    monkeypatch.setenv("READABILITY_FALLBACK_ON_FAILURE", "false")
    get_settings.cache_clear()

    async def fetch_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body><main><p>x</p></main></body></html>",
            request=request,
        )

    transport = httpx.MockTransport(fetch_handler)
    fail_result = ReadabilityExtractResult(
        kind=ReadabilityOutcomeKind.NOT_ARTICLE,
        detail="No article extracted.",
    )

    with patch(
        "mcp_server.url_reader.extract_via_readability",
        new_callable=AsyncMock,
        return_value=fail_result,
    ):
        with pytest.raises(UrlReadResponseError, match="No article extracted"):
            asyncio.run(
                read_url_document(
                    url="https://example.com/page",
                    max_chars=500,
                    transport=transport,
                )
            )


def test_read_url_document_raises_on_service_error_when_fallback_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READABILITY_SERVICE_URL", "http://readability:3010")
    monkeypatch.setenv("READABILITY_FALLBACK_ON_FAILURE", "false")
    get_settings.cache_clear()

    async def fetch_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body><main><p>x</p></main></body></html>",
            request=request,
        )

    transport = httpx.MockTransport(fetch_handler)
    fail_result = ReadabilityExtractResult(
        kind=ReadabilityOutcomeKind.UNAVAILABLE,
        detail="Connection refused",
    )

    with patch(
        "mcp_server.url_reader.extract_via_readability",
        new_callable=AsyncMock,
        return_value=fail_result,
    ):
        with pytest.raises(UrlReadRequestError, match="Connection refused"):
            asyncio.run(
                read_url_document(
                    url="https://example.com/page",
                    max_chars=500,
                    transport=transport,
                )
            )
