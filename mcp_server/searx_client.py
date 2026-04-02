"""Minimal async client for the SearXNG HTTP API."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx

from .config import get_settings

RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


class SearxngError(RuntimeError):
    """Base error raised for upstream SearXNG issues."""


class SearxngRequestError(SearxngError):
    """Raised when the SearXNG request cannot be completed successfully."""


class SearxngResponseError(SearxngError):
    """Raised when SearXNG responds with an unexpected payload."""


def _build_timeout() -> httpx.Timeout:
    settings = get_settings()
    return httpx.Timeout(
        settings.request_timeout_seconds,
        connect=settings.connect_timeout_seconds,
    )


def _build_client(
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.searxng_base_url,
        follow_redirects=True,
        headers={
            "Accept": "application/json",
            "User-Agent": settings.user_agent,
        },
        timeout=_build_timeout(),
        transport=transport,
        verify=settings.verify_ssl,
    )


def _format_upstream_error(response: httpx.Response, path: str) -> str:
    detail = response.text.strip()
    message = f"SearXNG returned HTTP {response.status_code} for {path}"
    if detail:
        message = f"{message}: {detail[:200]}"
    return message


async def request_json(
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Call SearXNG and return a parsed JSON object with simple retries."""

    settings = get_settings()
    last_error: Exception | None = None

    for attempt in range(settings.request_retries + 1):
        try:
            async with _build_client(transport=transport) as client:
                response = await client.get(path, params=params)
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < settings.request_retries
            ):
                await asyncio.sleep(0.25 * (attempt + 1))
                continue
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if (
                exc.response.status_code in RETRYABLE_STATUS_CODES
                and attempt < settings.request_retries
            ):
                await asyncio.sleep(0.25 * (attempt + 1))
                continue
            last_error = SearxngRequestError(
                _format_upstream_error(exc.response, path)
            )
        except httpx.RequestError as exc:
            if attempt < settings.request_retries:
                await asyncio.sleep(0.25 * (attempt + 1))
                continue
            last_error = SearxngRequestError(
                f"Failed to reach SearXNG at {settings.searxng_base_url}: {exc}"
            )
        else:
            try:
                payload = response.json()
            except ValueError as exc:
                raise SearxngResponseError(
                    "SearXNG returned invalid JSON."
                ) from exc
            if not isinstance(payload, dict):
                raise SearxngResponseError(
                    "SearXNG returned an unexpected payload shape."
                )
            return payload

    if last_error is None:
        raise SearxngRequestError("Unknown error while querying SearXNG.")
    raise last_error


async def fetch_search_payload(
    params: Mapping[str, Any],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Fetch normalized search data from the SearXNG `/search` endpoint."""

    return await request_json("/search", params=params, transport=transport)


async def fetch_instance_config(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Fetch instance configuration from the SearXNG `/config` endpoint."""

    return await request_json("/config", transport=transport)
