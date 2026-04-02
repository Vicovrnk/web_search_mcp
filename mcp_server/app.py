"""ASGI entrypoint for the SearXNG-backed FastMCP server."""

from __future__ import annotations

from http import HTTPStatus

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

from .config import get_settings
from .searx_client import SearxngError, fetch_instance_config
from .tools import register_config_tools, register_read_url_tools, register_search_tools

settings = get_settings()

mcp = FastMCP(
    name="SearXNG Web Search and Reader",
    instructions=(
        "Search the public web with a self-hosted SearXNG instance and fetch "
        "public HTML pages as compact, readable markdown-like text."
    ),
)

register_search_tools(mcp)
register_config_tools(mcp)
register_read_url_tools(mcp)


@mcp.custom_route(path="/healthz", methods=["GET"])
async def healthz(_: Request) -> JSONResponse:
    """Readiness probe that also verifies SearXNG is reachable."""

    try:
        config = await fetch_instance_config()
    except SearxngError as exc:
        return JSONResponse(
            {
                "status": "degraded",
                "upstream": "unreachable",
                "error": str(exc),
            },
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    return JSONResponse(
        {
            "status": "ok",
            "upstream": "reachable",
            "instance_name": config.get("instance_name", "SearXNG"),
            "mcp_path": settings.mcp_path,
        }
    )


app = mcp.http_app(
    path=settings.mcp_path,
    stateless_http=settings.mcp_stateless_http,
)


def main() -> None:
    """Run the MCP server over Streamable HTTP."""

    uvicorn.run(app, host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
