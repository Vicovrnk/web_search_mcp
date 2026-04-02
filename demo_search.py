"""Simple CLI demo that prints search results from the MCP server."""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

from fastmcp import Client

DEFAULT_MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")


def build_parser() -> argparse.ArgumentParser:
    """Build a small CLI for the demo search client."""

    parser = argparse.ArgumentParser(
        description="Call the SearXNG MCP server and print search results."
    )
    parser.add_argument("query", help="Search query to send to the MCP server.")
    parser.add_argument(
        "--url",
        default=DEFAULT_MCP_URL,
        help=f"MCP endpoint URL. Default: {DEFAULT_MCP_URL}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of results to request.",
    )
    parser.add_argument(
        "--safe-search",
        type=int,
        default=1,
        choices=(0, 1, 2),
        help="Safe-search level: 0 none, 1 moderate, 2 strict.",
    )
    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        default=None,
        help="Optional SearXNG category. Pass multiple times for several categories.",
    )
    parser.add_argument(
        "--engine",
        action="append",
        dest="engines",
        default=None,
        help="Optional SearXNG engine name. Pass multiple times for several engines.",
    )
    return parser


def _unwrap_result(result: Any) -> dict[str, Any]:
    """Extract structured search data from FastMCP's call result."""

    if hasattr(result, "data") and isinstance(result.data, dict):
        return result.data
    if hasattr(result, "structured_content") and isinstance(
        result.structured_content, dict
    ):
        return result.structured_content
    raise TypeError(f"Unexpected MCP response payload: {type(result)!r}")


def print_search_response(response: dict[str, Any]) -> None:
    """Pretty-print the normalized search response."""

    query = response.get("query", "")
    total = response.get("number_of_results")
    print(f"Query: {query}")
    if total is not None:
        print(f"Estimated total results: {total}")

    suggestions = response.get("suggestions") or []
    if suggestions:
        print(f"Suggestions: {', '.join(str(item) for item in suggestions)}")

    answers = response.get("answers") or []
    if answers:
        print("Answers:")
        for item in answers:
            print(f"- {item}")

    results = response.get("results") or []
    if not results:
        print("No search results found.")
        return

    print("\nResults:")
    for index, item in enumerate(results, start=1):
        title = item.get("title", "Untitled result")
        url = item.get("url", "")
        content = item.get("content")
        engine = item.get("engine")
        category = item.get("category")

        print(f"{index}. {title}")
        print(f"   URL: {url}")
        if engine:
            print(f"   Engine: {engine}")
        if category:
            print(f"   Category: {category}")
        if content:
            print(f"   Snippet: {content}")
        print()


async def run_demo(args: argparse.Namespace) -> None:
    """Call the MCP search tool and print the response."""

    payload = {
        "query": args.query,
        "limit": args.limit,
        "safe_search": args.safe_search,
    }
    if args.categories:
        payload["categories"] = args.categories
    if args.engines:
        payload["engines"] = args.engines

    async with Client(args.url) as client:
        result = await client.call_tool("web_search", payload)
    print_search_response(_unwrap_result(result))


def main() -> None:
    """Entry point for the demo CLI."""

    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run_demo(args))


if __name__ == "__main__":
    main()
