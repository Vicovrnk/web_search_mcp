"""Tool registration for fetching and reading static HTML pages by URL."""

from typing import Annotated, Any

from fastmcp import FastMCP
import httpx
from pydantic import Field

from ..config import URL_READ_DEFAULT_MAX_BYTES, get_settings
from ..url_reader import read_url_document


async def execute_url_read(
    *,
    url: str,
    max_chars: int,
    max_body_bytes: int,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Validate user options, fetch the page, and normalize the response."""

    settings = get_settings()
    bounded_max_chars = min(max(256, max_chars), settings.url_read_max_chars)
    bounded_body = min(
        max(4_096, max_body_bytes),
        settings.url_read_max_bytes,
    )
    return await read_url_document(
        url,
        max_chars=bounded_max_chars,
        max_bytes=bounded_body,
        transport=transport,
    )


def register_read_url_tools(mcp: FastMCP) -> None:
    """Register URL reading tools on the provided FastMCP server."""

    settings = get_settings()
    default_max_body = min(URL_READ_DEFAULT_MAX_BYTES, settings.url_read_max_bytes)

    @mcp.tool(
        name="read_url",
        description=(
            "Fetch a public HTML page and return markdown-like readable content. "
            "Parameters: `url` (required), `max_chars` (output length limit), "
            "`max_body_bytes` (download size limit for the raw HTTP body)."
        ),
        tags={"general_read", "readability", "web"},
    )
    async def read_url(
        url: Annotated[
            str,
            Field(
                description="Public `http/https` URL to fetch and convert into markdown-like text.",
                min_length=1,
                max_length=2_048,
            ),
        ],
        max_chars: Annotated[
            int,
            Field(
                description="Maximum number of markdown characters to return.",
                ge=256,
                le=settings.url_read_max_chars,
            ),
        ] = min(4_000, settings.url_read_max_chars),
        max_body_bytes: Annotated[
            int,
            Field(
                description=(
                    "Maximum size in bytes of the HTTP response body to download "
                    "(recommended default ~5 MiB). Cannot exceed the server "
                    "`URL_READ_MAX_BYTES` cap."
                ),
                ge=4_096,
                le=settings.url_read_max_bytes,
            ),
        ] = default_max_body,
    ) -> dict[str, Any]:
        """Read a static HTML page and return extracted markdown-like content."""

        return await execute_url_read(
            url=url,
            max_chars=max_chars,
            max_body_bytes=max_body_bytes,
        )
