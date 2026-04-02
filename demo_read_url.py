"""CLI demo: call the MCP `read_url` tool and print markdown-like page content."""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

from fastmcp import Client

DEFAULT_MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Call the MCP server `read_url` tool for a public HTML page."
    )
    parser.add_argument(
        "url",
        help="Public http(s) URL to fetch and normalize.",
    )
    parser.add_argument(
        "--mcp-url",
        default=DEFAULT_MCP_URL,
        dest="mcp_url",
        help=f"MCP endpoint URL. Default: {DEFAULT_MCP_URL}",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help="Max markdown characters in the response (server may clamp).",
    )
    parser.add_argument(
        "--max-body-bytes",
        type=int,
        default=None,
        help="Max HTTP response body size in bytes (server clamps to URL_READ_MAX_BYTES).",
    )
    return parser


def _unwrap_result(result: Any) -> dict[str, Any]:
    if hasattr(result, "data") and isinstance(result.data, dict):
        return result.data
    if hasattr(result, "structured_content") and isinstance(
        result.structured_content, dict
    ):
        return result.structured_content
    raise TypeError(f"Unexpected MCP response payload: {type(result)!r}")


def print_read_url_response(response: dict[str, Any]) -> None:
    print(f"URL: {response.get('url', '')}")
    print(f"Final URL: {response.get('final_url', '')}")
    print(f"Status: {response.get('status_code', '')}")
    if response.get("content_type"):
        print(f"Content-Type: {response['content_type']}")

    title = response.get("title")
    if title:
        print(f"Title: {title}")

    excerpt = response.get("excerpt")
    if excerpt:
        print(f"Excerpt: {excerpt}")

    print()
    print("--- Markdown ---")
    print(response.get("content_markdown", "") or "(empty)")


async def run_demo(args: argparse.Namespace) -> None:
    payload: dict[str, Any] = {"url": args.url.strip()}
    if args.max_chars is not None:
        payload["max_chars"] = args.max_chars
    if args.max_body_bytes is not None:
        payload["max_body_bytes"] = args.max_body_bytes

    async with Client(args.mcp_url) as client:
        result = await client.call_tool("read_url", payload)
    print_read_url_response(_unwrap_result(result))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run_demo(args))


if __name__ == "__main__":
    main()
