# SearXNG MCP Search

MIT-licensed remote MCP server backed by a self-hosted [SearXNG](https://github.com/searxng/searxng)
instance for both web search and static HTML page reading.

The stack runs these services with Docker Compose:

- [`valkey`](https://valkey.io/) for SearXNG limiter state
- [`searxng`](https://github.com/searxng/searxng) as the metasearch backend
- `readability` as a small local wrapper around [Mozilla Readability](https://github.com/mozilla/readability) for HTML-to-text extraction used by `read_url`
- `mcp-web-search` as a [FastMCP](https://github.com/jlowin/fastmcp)-based Streamable HTTP MCP server on `/mcp` (web search + URL reading)
- `wikipedia-mcp` as a second Streamable HTTP MCP server on `/mcp` ([wikipedia-mcp on PyPI](https://pypi.org/project/wikipedia-mcp/))

SearXNG stays on the internal Compose network by default. Both MCP services are
exposed on the host (`8000` and `8001` by default) so clients can connect to
either or both.

## Features

- Remote MCP over Streamable HTTP (SearXNG stack + optional Wikipedia stack)
- `web_search` tool with structured results (tags: `general_search`, `web`, `searxng`)
- `read_url` tool for markdown-like page extraction from public HTML URLs (tags: `general_read`, `readability`, `web`)
- `search_config` tool for enabled categories and engines (tags: `searxng`, `meta`)
- Wikipedia MCP tools (`search_wikipedia`, `get_article`, …) on a separate endpoint; see the [wikipedia-mcp](https://pypi.org/project/wikipedia-mcp/) package for the full list
- Health checks for MCP services, SearXNG, and supporting containers
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
- `WIKIPEDIA_MCP_PORT` default `8001` (host port for the Wikipedia MCP container)
- `WIKIPEDIA_LANGUAGE` default `en` (passed into the Wikipedia MCP process; see upstream CLI)
- `WIKIPEDIA_ACCESS_TOKEN` optional (reduces Wikipedia API rate limiting when set)

To use a Wikipedia country/locale instead of a raw language code, override the
`wikipedia-mcp` service `command` in Compose (for example `--country US`) as
documented in [wikipedia-mcp](https://pypi.org/project/wikipedia-mcp/).

## Run The Stack

```bash
docker compose up --build
```

MCP endpoints:

- SearXNG-backed server: `http://localhost:8000/mcp`
- Wikipedia server: `http://localhost:8001/mcp`

The SearXNG MCP health endpoint:

- `http://localhost:8000/healthz`

### IDE / Cursor (two remote servers)

Point each server at its Streamable HTTP URL (exact config keys depend on your
client version; typical shape):

```json
{
  "mcpServers": {
    "searxng-mcp-search": {
      "url": "http://localhost:8000/mcp"
    },
    "wikipedia-mcp": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

## Smoke Test

Check readiness:

```bash
curl http://localhost:8000/healthz
```

Call the MCP server from Python with [FastMCP](https://github.com/jlowin/fastmcp)'s client:

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

- `url` (required)
- `max_chars` — cap on returned markdown length (default 4000, bounded by server config)
- `max_body_bytes` — max HTTP response body size to download in bytes (default 5 MiB, bounded by `URL_READ_MAX_BYTES`)

Returned payload:

- `url`
- `final_url`
- `title`
- `content_markdown`
- `excerpt`
- `content_type`
- `status_code`

## Local Tests

Install the package and test dependencies, then run `pytest`. On Windows, use the
project virtualenv interpreter:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

On macOS or Linux:

```bash
python -m pip install -e ".[dev]"
pytest
```

## Notes

- SearXNG JSON output is enabled in `searxng/core-config/settings.yml`.
- The limiter is enabled and backed by Valkey.
- SearXNG itself does not publish a host port in the default Compose setup.

## License

This project is available under the [MIT License](https://opensource.org/license/mit).
