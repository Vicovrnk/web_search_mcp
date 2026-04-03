"""Configuration inspection tools for the SearXNG instance."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastmcp import FastMCP

from ..models import EngineInfo, SearchConfigResponse
from ..searx_client import fetch_instance_config


def normalize_instance_config(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only the SearXNG config fields that are useful to MCP clients."""

    categories = payload.get("categories", [])
    engines = payload.get("engines", [])
    plugins = payload.get("plugins", [])

    enabled_engines = [
        EngineInfo(
            name=str(engine.get("name", "")).strip(),
            categories=[
                str(category).strip()
                for category in engine.get("categories", [])
                if str(category).strip()
            ]
            if isinstance(engine.get("categories", []), list)
            else [],
            shortcut=str(engine.get("shortcut", "")).strip() or None,
        )
        for engine in engines
        if isinstance(engine, Mapping)
        and engine.get("enabled")
        and str(engine.get("name", "")).strip()
    ]

    normalized = SearchConfigResponse(
        instance_name=str(payload.get("instance_name", "SearXNG")).strip() or "SearXNG",
        default_locale=str(payload.get("default_locale", "")).strip() or None,
        default_theme=str(payload.get("default_theme", "")).strip() or None,
        safe_search=payload.get("safe_search"),
        categories=sorted(
            {
                str(category).strip()
                for category in categories
                if str(category).strip()
            }
        )
        if isinstance(categories, list)
        else [],
        engines=sorted(enabled_engines, key=lambda item: item.name.lower()),
        plugins=sorted(
            {
                str(plugin.get("name", "")).strip()
                for plugin in plugins
                if isinstance(plugin, Mapping)
                and plugin.get("enabled")
                and str(plugin.get("name", "")).strip()
            }
        )
        if isinstance(plugins, list)
        else [],
    )
    return normalized.model_dump(mode="json")


async def execute_config_lookup() -> dict[str, Any]:
    """Fetch the current SearXNG config exposed to API consumers."""

    payload = await fetch_instance_config()
    return normalize_instance_config(payload)


def register_config_tools(mcp: FastMCP) -> None:
    """Register auxiliary SearXNG configuration tools."""

    @mcp.tool(
        name="search_config",
        description="Inspect enabled SearXNG categories, engines, and safe-search defaults.",
        tags={"searxng", "meta"},
    )
    async def search_config() -> dict[str, Any]:
        """Return public SearXNG config that helps clients form better searches."""

        return await execute_config_lookup()
