# SearXNG MCP Search

Remote MCP server backed by a self-hosted SearXNG instance for both web search
and static HTML page reading.

The stack runs three services with Docker Compose:

- `valkey` for SearXNG limiter state
- `searxng` as the metasearch backend
- `mcp-web-search` as a Streamable HTTP MCP server on `/mcp`

Only the MCP service is exposed on the host by default. SearXNG stays on the
internal Compose network but can still reach external search engines.

## Features

- Remote MCP over Streamable HTTP
- `web_search` tool with structured results
- `read_url` tool for markdown-like page extraction from public HTML URLs
- `search_config` tool for enabled categories and engines
- Health checks for both the MCP server and SearXNG
- Request timeouts, retries, result limits, and input validation

## Prerequisites

- Docker Engine or Docker Desktop
- Docker Compose
- Python 3.11+ if you want to run tests locally

## Configuration

Environment variables are optional because Compose provides sensible defaults.
If you want overrides, define them in `.env`.

Relevant variables:

- `MCP_PORT` default `8000`
- `SEARXNG_SECRET` default `change-me`
- `SEARXNG_REQUEST_TIMEOUT_SECONDS` default `15`
- `SEARXNG_CONNECT_TIMEOUT_SECONDS` default `5`
- `SEARXNG_REQUEST_RETRIES` default `1`
- `MAX_RESULTS` default `10`
- `MAX_QUERY_LENGTH` default `512`
- `MAX_PAGE_NUMBER` default `10`
- `DEFAULT_SAFE_SEARCH` default `1`
- `VERIFY_SSL` default `false`
- `URL_READ_TIMEOUT_SECONDS` default `20`
- `URL_READ_MAX_BYTES` default `1000000`
- `URL_READ_MAX_CHARS` default `12000`

## Run The Stack

```bash
docker compose up --build
```

The MCP endpoint becomes available at:

- `http://localhost:8000/mcp`

The health endpoint becomes available at:

- `http://localhost:8000/healthz`

## Smoke Test

Check readiness:

```bash
curl http://localhost:8000/healthz
```

Call the MCP server from Python with FastMCP's client:

```python
import asyncio

from fastmcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8000/mcp") as client:
        search_response = await client.call_tool(
            "web_search",
            {
                "query": "JAX vmap tutorial",
                "limit": 3,
                "safe_search": 1,
                "categories": ["general"],
            },
        )
        print(search_response)

        config_response = await client.call_tool("search_config", {})
        print(config_response)

        page_response = await client.call_tool(
            "read_url",
            {
                "url": "https://jax.readthedocs.io/en/latest/quickstart.html",
                "max_chars": 4000,
            },
        )
        print(page_response)


asyncio.run(main())
```

## Tool Contracts

### `web_search`

Accepted arguments:

- `query`
- `categories`
- `engines`
- `language`
- `time_range`
- `safe_search`
- `page`
- `limit`

Returned payload:

- `query`
- `number_of_results`
- `suggestions`
- `answers`
- `infoboxes`
- `results`

Each item in `results` includes:

- `title`
- `url`
- `content`
- `engine`
- `category`
- `score`
- `published_date`
- `thumbnail`

### `search_config`

Returns:

- `instance_name`
- `default_locale`
- `default_theme`
- `safe_search`
- `categories`
- `engines`
- `plugins`

### `read_url`

Accepted arguments:

- `url`
- `max_chars`

Returned payload:

- `url`
- `final_url`
- `title`
- `content_markdown`
- `excerpt`
- `content_type`
- `status_code`

## Local Tests

Install the package and test dependencies, then run `pytest`:

```bash
python -m pip install -e ".[dev]"
pytest
```

## Notes

- SearXNG JSON output is enabled in `searxng/core-config/settings.yml`.
- The limiter is enabled and backed by Valkey.
- SearXNG itself does not publish a host port in the default Compose setup.
