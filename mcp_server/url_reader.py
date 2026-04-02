"""Utilities for fetching HTML pages and converting them to markdown-like text."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from html import escape
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
import httpx

from .config import get_settings
from .models import ReadUrlResponse
from .readability_client import (
    ReadabilityOutcomeKind,
    extract_via_readability,
)

HTML_CONTENT_TYPES = {"application/xhtml+xml", "text/html"}
MAX_URL_LENGTH = 2_048
NOISE_TAGS = ("canvas", "noscript", "script", "style", "svg", "template")
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
SUPPORTED_SCHEMES = {"http", "https"}
TEXT_BLOCK_TAGS = ("blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "ol", "p", "pre", "ul")


class UrlReadError(RuntimeError):
    """Base error raised while reading an arbitrary URL."""


class UrlReadRequestError(UrlReadError):
    """Raised when the upstream request cannot be completed."""


class UrlReadResponseError(UrlReadError):
    """Raised when the response is not a readable HTML page."""


@dataclass(frozen=True, slots=True)
class FetchedHtmlDocument:
    """HTTP response data required for downstream HTML parsing."""

    requested_url: str
    final_url: str
    status_code: int
    content_type: str | None
    html: str


def validate_url(url: str, *, max_length: int = MAX_URL_LENGTH) -> str:
    """Return a normalized public URL or raise a validation error."""

    cleaned = url.strip()
    if not cleaned:
        raise ValueError("`url` must not be empty.")
    if len(cleaned) > max_length:
        raise ValueError(f"`url` must be <= {max_length} characters.")

    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in SUPPORTED_SCHEMES:
        raise ValueError("`url` must use the `http` or `https` scheme.")
    if not parsed.netloc:
        raise ValueError("`url` must include a host.")
    return cleaned


def _build_timeout() -> httpx.Timeout:
    settings = get_settings()
    return httpx.Timeout(
        settings.url_read_timeout_seconds,
        connect=settings.connect_timeout_seconds,
    )


def _build_client(
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        follow_redirects=True,
        headers={
            "Accept": "text/html,application/xhtml+xml;q=1.0,*/*;q=0.1",
            "User-Agent": settings.user_agent,
        },
        timeout=_build_timeout(),
        transport=transport,
        verify=settings.verify_ssl,
    )


def _format_upstream_error(response: httpx.Response, url: str) -> str:
    return f"URL reader received HTTP {response.status_code} for {url}"


async def _read_limited_body(response: httpx.Response, *, max_bytes: int) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise UrlReadResponseError(
                    f"Response body exceeds the configured limit of {max_bytes} bytes."
                )
        except ValueError:
            pass

    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in response.aiter_bytes():
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise UrlReadResponseError(
                f"Response body exceeds the configured limit of {max_bytes} bytes."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _looks_like_html(content_type: str | None, content: bytes) -> bool:
    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type in HTML_CONTENT_TYPES:
        return True

    snippet = content.lstrip()[:512].lower()
    return (
        snippet.startswith(b"<!doctype html")
        or b"<html" in snippet
        or b"<body" in snippet
    )


def _effective_read_max_bytes(requested: int | None) -> int:
    """Clamp per-request body limit to the server-configured ceiling."""

    settings = get_settings()
    ceiling = settings.url_read_max_bytes
    if requested is None:
        return ceiling
    return min(max(requested, 4_096), ceiling)


async def fetch_html_document(
    url: str,
    *,
    max_bytes: int | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FetchedHtmlDocument:
    """Fetch a public URL and validate that it returns HTML content."""

    settings = get_settings()
    cleaned_url = validate_url(url)
    limit_bytes = _effective_read_max_bytes(max_bytes)
    last_error: Exception | None = None

    for attempt in range(settings.request_retries + 1):
        try:
            async with _build_client(transport=transport) as client:
                async with client.stream("GET", cleaned_url) as response:
                    if (
                        response.status_code in RETRYABLE_STATUS_CODES
                        and attempt < settings.request_retries
                    ):
                        await asyncio.sleep(0.25 * (attempt + 1))
                        continue

                    response.raise_for_status()

                    content = await _read_limited_body(
                        response,
                        max_bytes=limit_bytes,
                    )
                    content_type = response.headers.get("content-type")
                    if not _looks_like_html(content_type, content):
                        raise UrlReadResponseError(
                            "The URL did not return an HTML document."
                        )

                    encoding = response.encoding or "utf-8"
                    html = content.decode(encoding, errors="replace").strip()
                    if not html:
                        raise UrlReadResponseError(
                            "The URL returned an empty HTML document."
                        )

                    return FetchedHtmlDocument(
                        requested_url=cleaned_url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        content_type=content_type,
                        html=html,
                    )
        except httpx.HTTPStatusError as exc:
            if (
                exc.response.status_code in RETRYABLE_STATUS_CODES
                and attempt < settings.request_retries
            ):
                await asyncio.sleep(0.25 * (attempt + 1))
                continue
            last_error = UrlReadRequestError(
                _format_upstream_error(exc.response, cleaned_url)
            )
        except httpx.RequestError as exc:
            if attempt < settings.request_retries:
                await asyncio.sleep(0.25 * (attempt + 1))
                continue
            last_error = UrlReadRequestError(f"Failed to fetch {cleaned_url}: {exc}")

    if last_error is None:
        raise UrlReadRequestError("Unknown error while fetching the URL.")
    raise last_error


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _clean_markdown_spacing(text: str) -> str:
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = cleaned.replace(" \n", "\n").replace("\n ", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned.strip()


def _extract_inline_markdown(node: Tag) -> str:
    fragments: list[str] = []

    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child)
            if text.strip():
                fragments.append(text)
            continue
        if not isinstance(child, Tag):
            continue

        if child.name in NOISE_TAGS or child.name in {"ol", "pre", "ul"}:
            continue
        if child.name == "br":
            fragments.append("\n")
            continue
        if child.name == "a":
            text = _normalize_whitespace(_extract_inline_markdown(child))
            href = child.get("href", "").strip()
            if text and href:
                fragments.append(f"[{text}]({href})")
            elif href:
                fragments.append(href)
            elif text:
                fragments.append(text)
            continue
        if child.name == "code" and child.parent is not None and child.parent.name != "pre":
            text = _normalize_whitespace(child.get_text(" ", strip=True))
            if text:
                fragments.append(f"`{text}`")
            continue

        nested_text = _extract_inline_markdown(child)
        if nested_text:
            fragments.append(nested_text)

    return _clean_markdown_spacing(" ".join(fragment.strip() for fragment in fragments if fragment.strip()))


def _select_content_root(soup: BeautifulSoup) -> Tag:
    candidates = [
        soup.find("main"),
        soup.find("article"),
        soup.find(attrs={"role": "main"}),
        soup.body,
    ]
    for candidate in candidates:
        if isinstance(candidate, Tag) and len(candidate.get_text(" ", strip=True)) >= 40:
            return candidate
    body = soup.body
    return body if isinstance(body, Tag) else soup


def _has_ancestor(tag: Tag, names: set[str], *, stop: Tag) -> bool:
    for parent in tag.parents:
        if parent is stop:
            return False
        if isinstance(parent, Tag) and parent.name in names:
            return True
    return False


def _render_list(list_tag: Tag, *, depth: int = 0) -> str:
    lines: list[str] = []
    list_name = list_tag.name or "ul"

    for index, item in enumerate(list_tag.find_all("li", recursive=False), start=1):
        cloned_soup = BeautifulSoup(str(item), "html.parser")
        cloned_item = cloned_soup.find("li")
        if cloned_item is None:
            continue

        for nested in cloned_item.find_all(["ol", "pre", "ul"]):
            nested.decompose()

        item_text = _extract_inline_markdown(cloned_item)
        prefix = f"{index}. " if list_name == "ol" else "- "
        indent = "  " * depth
        if item_text:
            lines.append(f"{indent}{prefix}{item_text}")

        for nested_list in item.find_all(["ol", "ul"]):
            nearest_list_parent = nested_list.find_parent(["ol", "ul"])
            if nearest_list_parent is list_tag:
                nested_block = _render_list(nested_list, depth=depth + 1)
                if nested_block:
                    lines.append(nested_block)

        for pre_block in item.find_all("pre"):
            nearest_list_parent = pre_block.find_parent(["ol", "ul"])
            if nearest_list_parent is list_tag:
                rendered_pre = _render_block(pre_block)
                if rendered_pre:
                    indented_block = "\n".join(
                        f"{'  ' * (depth + 1)}{line}" if line else ""
                        for line in rendered_pre.splitlines()
                    )
                    lines.append(indented_block)

    return "\n".join(lines).strip()


def _render_block(tag: Tag) -> str:
    if tag.name is None:
        return ""

    if tag.name.startswith("h") and len(tag.name) == 2 and tag.name[1].isdigit():
        level = int(tag.name[1])
        text = _extract_inline_markdown(tag)
        return f"{'#' * level} {text}" if text else ""

    if tag.name == "p":
        return _extract_inline_markdown(tag)

    if tag.name == "blockquote":
        text = _extract_inline_markdown(tag)
        if not text:
            return ""
        return "\n".join(f"> {line}" for line in text.splitlines())

    if tag.name == "pre":
        code = tag.get_text("\n", strip=False).strip()
        if not code:
            return ""
        return f"```\n{code}\n```"

    if tag.name in {"ol", "ul"}:
        return _render_list(tag)

    return ""


def _extract_title(soup: BeautifulSoup, root: Tag) -> str | None:
    meta_title = soup.find("meta", attrs={"property": "og:title"})
    if meta_title is None:
        meta_title = soup.find("meta", attrs={"name": "twitter:title"})
    if isinstance(meta_title, Tag):
        content = _normalize_whitespace(meta_title.get("content", ""))
        if content:
            return content

    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        text = _normalize_whitespace(title_tag.get_text(" ", strip=True))
        if text:
            return text

    heading = root.find("h1")
    if isinstance(heading, Tag):
        text = _extract_inline_markdown(heading)
        if text:
            return text
    return None


def _truncate_markdown(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    suffix = "\n..."
    cutoff = max(1, max_chars - len(suffix))
    truncated = text[:cutoff].rstrip()
    breakpoints = [truncated.rfind("\n\n"), truncated.rfind("\n"), truncated.rfind(". ")]
    best_break = max(breakpoints)
    if best_break >= cutoff // 2:
        truncated = truncated[:best_break].rstrip()
    return f"{truncated}{suffix}"


def _build_excerpt(text: str) -> str | None:
    plain_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    plain_text = re.sub(r"`+", "", plain_text)
    plain_text = re.sub(r"^#{1,6}\s+", "", plain_text, flags=re.MULTILINE)
    plain_text = re.sub(r"^>\s*", "", plain_text, flags=re.MULTILINE)
    plain_text = re.sub(r"^\s*(?:-|\d+\.)\s+", "", plain_text, flags=re.MULTILINE)
    plain_text = _normalize_whitespace(plain_text)
    if not plain_text:
        return None
    return plain_text[:277].rstrip() + "..." if len(plain_text) > 280 else plain_text


def _build_synthetic_readability_html(*, title: str | None, content_html: str) -> str:
    """Wrap Readability article HTML so existing markdown normalization can process it."""

    safe_title = escape(title or "", quote=True)
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<title>{safe_title}</title></head><body><main>{content_html}</main></body></html>"
    )


def normalize_html_document(
    *,
    url: str,
    final_url: str,
    status_code: int,
    content_type: str | None,
    html: str,
    max_chars: int,
) -> dict[str, str | int | None]:
    """Normalize raw HTML into a stable markdown-like tool response."""

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(NOISE_TAGS + ("aside", "footer", "form", "nav")):
        tag.decompose()

    root = _select_content_root(soup)
    title = _extract_title(soup, root)

    blocks: list[str] = []
    for tag in root.find_all(TEXT_BLOCK_TAGS):
        if tag.name in {"ol", "ul"}:
            if _has_ancestor(tag, {"ol", "ul"}, stop=root):
                continue
        elif _has_ancestor(tag, {"blockquote", "ol", "pre", "ul"}, stop=root):
            continue

        block = _render_block(tag)
        if block:
            blocks.append(block)

    if not blocks:
        fallback = _normalize_whitespace(root.get_text(" ", strip=True))
        if fallback:
            blocks.append(fallback)

    if not blocks:
        raise UrlReadResponseError("The HTML page did not contain readable text content.")

    content_markdown = _truncate_markdown(
        "\n\n".join(blocks).strip(),
        max_chars=max_chars,
    )
    if not content_markdown:
        raise UrlReadResponseError("The HTML page did not contain readable text content.")

    response = ReadUrlResponse(
        url=url,
        final_url=final_url,
        title=title,
        content_markdown=content_markdown,
        excerpt=_build_excerpt(content_markdown),
        content_type=content_type,
        status_code=status_code,
    )
    return response.model_dump(mode="json")


async def read_url_document(
    url: str,
    *,
    max_chars: int,
    max_bytes: int | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, str | int | None]:
    """Fetch a URL and return normalized markdown-like page content."""

    document = await fetch_html_document(url, max_bytes=max_bytes, transport=transport)
    settings = get_settings()

    if settings.readability_service_url:
        readability_result = await extract_via_readability(
            html=document.html,
            page_url=document.final_url,
        )
        if (
            readability_result.kind == ReadabilityOutcomeKind.OK
            and readability_result.article is not None
        ):
            synthetic_html = _build_synthetic_readability_html(
                title=readability_result.article.title,
                content_html=readability_result.article.content,
            )
            normalized = await asyncio.to_thread(
                normalize_html_document,
                url=document.requested_url,
                final_url=document.final_url,
                status_code=document.status_code,
                content_type=document.content_type,
                html=synthetic_html,
                max_chars=max_chars,
            )
            if readability_result.article.title:
                normalized["title"] = readability_result.article.title
            return normalized

        if not settings.readability_fallback_on_failure:
            detail = readability_result.detail or "Readability extraction failed."
            if readability_result.kind == ReadabilityOutcomeKind.NOT_ARTICLE:
                raise UrlReadResponseError(detail)
            raise UrlReadRequestError(detail)

    return await asyncio.to_thread(
        normalize_html_document,
        url=document.requested_url,
        final_url=document.final_url,
        status_code=document.status_code,
        content_type=document.content_type,
        html=document.html,
        max_chars=max_chars,
    )
