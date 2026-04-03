"""Search tool registration and SearXNG response normalization."""

from collections.abc import Iterable, Mapping
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from ..config import get_settings
from ..models import SearchResponse, SearchResult, TimeRange
from ..searx_client import fetch_search_payload


def _clean_query(query: str, *, max_length: int) -> str:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("`query` must not be empty.")
    if len(cleaned) > max_length:
        raise ValueError(f"`query` must be <= {max_length} characters.")
    return cleaned


def _clean_values(values: Iterable[str] | None) -> list[str] | None:
    if values is None:
        return None
    cleaned = [value.strip() for value in values if value and value.strip()]
    return cleaned or None


def _normalize_score(score: Any) -> float | None:
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def _normalize_result(result: Mapping[str, Any]) -> SearchResult | None:
    url = str(result.get("url", "")).strip()
    if not url:
        return None

    title = str(result.get("title", "")).strip() or url
    content = str(result.get("content", "")).strip() or None
    engine = str(result.get("engine", "")).strip() or None
    category = str(result.get("category", "")).strip() or None
    published_date = str(result.get("publishedDate", "")).strip() or None
    thumbnail = (
        str(result.get("thumbnail", "")).strip()
        or str(result.get("img_src", "")).strip()
        or None
    )

    return SearchResult(
        title=title,
        url=url,
        content=content,
        engine=engine,
        category=category,
        score=_normalize_score(result.get("score")),
        published_date=published_date,
        thumbnail=thumbnail,
    )


def build_search_params(
    *,
    query: str,
    categories: list[str] | None,
    engines: list[str] | None,
    language: str | None,
    time_range: TimeRange | None,
    safe_search: int,
    page: int,
) -> dict[str, str | int]:
    """Map normalized tool arguments to the SearXNG search API."""

    params: dict[str, str | int] = {
        "q": query,
        "format": "json",
        "pageno": page,
        "safesearch": safe_search,
    }
    if categories:
        params["categories"] = ",".join(categories)
    if engines:
        params["engines"] = ",".join(engines)
    if language:
        params["language"] = language
    if time_range:
        params["time_range"] = time_range
    return params


def normalize_search_response(
    *,
    query: str,
    payload: Mapping[str, Any],
    limit: int,
) -> dict[str, Any]:
    """Convert raw SearXNG JSON into a stable MCP-friendly payload."""

    raw_results = payload.get("results", [])
    if not isinstance(raw_results, list):
        raw_results = []

    normalized_results: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, Mapping):
            continue
        normalized = _normalize_result(item)
        if normalized is None:
            continue
        normalized_results.append(normalized.model_dump(mode="json"))
        if len(normalized_results) >= limit:
            break

    suggestions = payload.get("suggestions", [])
    answers = payload.get("answers", [])
    infoboxes = payload.get("infoboxes", [])

    normalized_payload = SearchResponse(
        query=str(payload.get("query", "")).strip() or query,
        number_of_results=payload.get("number_of_results"),
        suggestions=[str(item).strip() for item in suggestions if str(item).strip()]
        if isinstance(suggestions, list)
        else [],
        answers=[str(item).strip() for item in answers if str(item).strip()]
        if isinstance(answers, list)
        else [],
        infoboxes=[
            dict(item)
            for item in infoboxes
            if isinstance(item, Mapping)
        ]
        if isinstance(infoboxes, list)
        else [],
        results=normalized_results,
    )
    return normalized_payload.model_dump(mode="json")


async def execute_search(
    *,
    query: str,
    categories: list[str] | None,
    engines: list[str] | None,
    language: str | None,
    time_range: TimeRange | None,
    safe_search: int,
    page: int,
    limit: int,
) -> dict[str, Any]:
    """Validate user input, call SearXNG, and normalize the response."""

    settings = get_settings()
    cleaned_query = _clean_query(query, max_length=settings.max_query_length)
    cleaned_categories = _clean_values(categories)
    cleaned_engines = _clean_values(engines)
    cleaned_language = language.strip() if language else None
    bounded_limit = min(max(1, limit), settings.max_results)
    bounded_page = min(max(1, page), settings.max_page_number)
    bounded_safe_search = min(max(safe_search, 0), 2)

    payload = await fetch_search_payload(
        build_search_params(
            query=cleaned_query,
            categories=cleaned_categories,
            engines=cleaned_engines,
            language=cleaned_language,
            time_range=time_range,
            safe_search=bounded_safe_search,
            page=bounded_page,
        )
    )
    return normalize_search_response(
        query=cleaned_query,
        payload=payload,
        limit=bounded_limit,
    )


def register_search_tools(mcp: FastMCP) -> None:
    """Register search tools on the provided FastMCP server."""

    settings = get_settings()

    @mcp.tool(
        name="web_search",
        description="Search the public web through a self-hosted SearXNG instance.",
        tags={"general_search", "web", "searxng"},
    )
    async def web_search(
        query: Annotated[
            str,
            Field(
                description="Search query passed to SearXNG.",
                min_length=1,
                max_length=settings.max_query_length,
            ),
        ],
        categories: Annotated[
            list[str] | None,
            Field(
                description="Optional SearXNG categories such as `general` or `it`."
            ),
        ] = None,
        engines: Annotated[
            list[str] | None,
            Field(description="Optional list of SearXNG engine names to target."),
        ] = None,
        language: Annotated[
            str | None,
            Field(description="Optional SearXNG language code, for example `en-US`."),
        ] = None,
        time_range: Annotated[
            TimeRange | None,
            Field(description="Optional freshness filter supported by the engine."),
        ] = None,
        safe_search: Annotated[
            int,
            Field(description="Safe search level: 0 none, 1 moderate, 2 strict.", ge=0, le=2),
        ] = settings.default_safe_search,
        page: Annotated[
            int,
            Field(description="Search results page number.", ge=1, le=settings.max_page_number),
        ] = 1,
        limit: Annotated[
            int,
            Field(
                description="Maximum number of normalized results to return.",
                ge=1,
                le=settings.max_results,
            ),
        ] = min(5, settings.max_results),
    ) -> dict[str, Any]:
        """Search the web and return normalized result objects."""

        return await execute_search(
            query=query,
            categories=categories,
            engines=engines,
            language=language,
            time_range=time_range,
            safe_search=safe_search,
            page=page,
            limit=limit,
        )
