"""Runtime configuration for the SearXNG-backed MCP server."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _read_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


def _normalize_base_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    if not cleaned:
        raise ValueError("SEARXNG_BASE_URL must not be empty.")
    return cleaned


def _normalize_path(path: str) -> str:
    cleaned = path.strip() or "/mcp"
    return cleaned if cleaned.startswith("/") else f"/{cleaned}"


# Default and recommended max HTTP response body size for `read_url` (5 MiB).
URL_READ_DEFAULT_MAX_BYTES = 5 * 1024 * 1024


def _optional_service_url(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    return cleaned if cleaned else None


@dataclass(frozen=True, slots=True)
class Settings:
    """Container-friendly application settings."""

    searxng_base_url: str
    request_timeout_seconds: float
    connect_timeout_seconds: float
    request_retries: int
    max_results: int
    max_query_length: int
    max_page_number: int
    default_safe_search: int
    url_read_timeout_seconds: float
    url_read_max_bytes: int
    url_read_max_chars: int
    verify_ssl: bool
    user_agent: str
    mcp_host: str
    mcp_port: int
    mcp_path: str
    mcp_stateless_http: bool
    readability_service_url: str | None
    readability_fallback_on_failure: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from environment variables once per process."""

    request_retries = max(0, _read_int("SEARXNG_REQUEST_RETRIES", 1))
    max_results = max(1, _read_int("MAX_RESULTS", 10))
    max_query_length = max(16, _read_int("MAX_QUERY_LENGTH", 512))
    max_page_number = max(1, _read_int("MAX_PAGE_NUMBER", 10))
    default_safe_search = min(max(_read_int("DEFAULT_SAFE_SEARCH", 1), 0), 2)
    url_read_max_bytes = max(
        4_096, _read_int("URL_READ_MAX_BYTES", URL_READ_DEFAULT_MAX_BYTES)
    )
    url_read_max_chars = max(512, _read_int("URL_READ_MAX_CHARS", 12_000))
    mcp_port = max(1, _read_int("MCP_PORT", 8000))

    return Settings(
        searxng_base_url=_normalize_base_url(
            os.getenv("SEARXNG_BASE_URL", "http://searxng:8080")
        ),
        request_timeout_seconds=max(
            1.0, _read_float("SEARXNG_REQUEST_TIMEOUT_SECONDS", 15.0)
        ),
        connect_timeout_seconds=max(
            0.5, _read_float("SEARXNG_CONNECT_TIMEOUT_SECONDS", 5.0)
        ),
        request_retries=request_retries,
        max_results=max_results,
        max_query_length=max_query_length,
        max_page_number=max_page_number,
        default_safe_search=default_safe_search,
        url_read_timeout_seconds=max(
            1.0, _read_float("URL_READ_TIMEOUT_SECONDS", 20.0)
        ),
        url_read_max_bytes=url_read_max_bytes,
        url_read_max_chars=url_read_max_chars,
        verify_ssl=_read_bool("VERIFY_SSL", True),
        user_agent=os.getenv(
            "USER_AGENT",
            "searxng-mcp-search/0.1.0 (+https://docs.searxng.org/)",
        ).strip(),
        mcp_host=os.getenv("MCP_HOST", "0.0.0.0").strip() or "0.0.0.0",
        mcp_port=mcp_port,
        mcp_path=_normalize_path(os.getenv("MCP_PATH", "/mcp")),
        mcp_stateless_http=_read_bool("MCP_STATELESS_HTTP", True),
        readability_service_url=_optional_service_url(
            os.getenv("READABILITY_SERVICE_URL")
        ),
        readability_fallback_on_failure=_read_bool(
            "READABILITY_FALLBACK_ON_FAILURE", True
        ),
    )
