"""Targeted tests for the SearXNG-backed search tool."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from mcp_server.searx_client import SearxngRequestError, request_json
from mcp_server.tools.search import build_search_params, normalize_search_response


def test_build_search_params_omits_blank_values() -> None:
    params = build_search_params(
        query="jax arrays",
        categories=["general", "it"],
        engines=None,
        language="en-US",
        time_range="month",
        safe_search=1,
        page=2,
    )

    assert params == {
        "q": "jax arrays",
        "format": "json",
        "pageno": 2,
        "safesearch": 1,
        "categories": "general,it",
        "language": "en-US",
        "time_range": "month",
    }


def test_normalize_search_response_limits_results_and_keeps_metadata() -> None:
    payload = {
        "query": "jax grad",
        "number_of_results": 123,
        "suggestions": ["jax autodiff"],
        "answers": ["Automatic differentiation in JAX"],
        "infoboxes": [{"infobox": "jax"}],
        "results": [
            {
                "title": "JAX Documentation",
                "url": "https://jax.readthedocs.io/",
                "content": "JAX combines NumPy with automatic differentiation.",
                "engine": "duckduckgo",
                "category": "general",
                "score": "1.5",
                "publishedDate": "2026-03-30",
            },
            {
                "title": "Second Result",
                "url": "https://example.com/2",
                "content": "Should be trimmed by limit.",
            },
        ],
    }

    normalized = normalize_search_response(
        query="jax grad",
        payload=payload,
        limit=1,
    )

    assert normalized["query"] == "jax grad"
    assert normalized["number_of_results"] == 123
    assert normalized["suggestions"] == ["jax autodiff"]
    assert normalized["answers"] == ["Automatic differentiation in JAX"]
    assert normalized["infoboxes"] == [{"infobox": "jax"}]
    assert normalized["results"] == [
        {
            "title": "JAX Documentation",
            "url": "https://jax.readthedocs.io/",
            "content": "JAX combines NumPy with automatic differentiation.",
            "engine": "duckduckgo",
            "category": "general",
            "score": 1.5,
            "published_date": "2026-03-30",
            "thumbnail": None,
        }
    ]


def test_request_json_raises_clear_error_for_upstream_failure() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream unavailable")

    transport = httpx.MockTransport(handler)

    with pytest.raises(SearxngRequestError, match="HTTP 503"):
        asyncio.run(
            request_json(
                "/search",
                params={"q": "jax", "format": "json"},
                transport=transport,
            )
        )
