# Open Information MCP Toolkit

Self-hosted, MIT-licensed MCP toolkit for agents that need access to open
information without depending on mandatory third-party API keys. The stack is
delivered as one Docker Compose bundle, but its capabilities are intentionally
split into separate MCP endpoints:

- one general endpoint for broad internet access
- one specialized endpoint per focused knowledge domain

Today this repository ships:

- a general web endpoint implemented in this repo and backed by
  [SearXNG](https://github.com/searxng/searxng) plus
  [Mozilla Readability](https://github.com/mozilla/readability)
- a specialized encyclopedia endpoint backed by
  [wikipedia-mcp](https://pypi.org/project/wikipedia-mcp/)
- a specialized academic paper endpoint backed by
  [arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server)

## Concept

The toolkit is built around a simple separation of responsibilities:

- `general` tools expose reusable open-web primitives that almost any agent needs
- `specialized` tools expose deeper workflows for one domain and live behind
  their own endpoint
- the default stack relies on open-source components and works without
  mandatory external API keys
- the whole bundle is delivered as one Docker stack so clients can enable only
  the endpoints they need

This structure leaves room for future specialized endpoints such as library
documentation research or YouTube transcription without changing the general
endpoint contract.

## Current Toolkit Layout

| Capability class | Default endpoint | Purpose | Current tools |
| --- | --- | --- | --- |
| General | `http://localhost:8000/mcp` | Broad web search, page reading, and search capability discovery | `web_search`, `read_url`, `search_config` |
| Specialized | `http://localhost:8001/mcp` | Encyclopedic and subject-area research through Wikipedia | `search_wikipedia`, `get_article`, `get_summary`, ... |
| Specialized | `http://localhost:8002/mcp` | Scientific paper search, metadata lookup, download, semantic search, and reading through arXiv | `search_papers`, `get_abstract`, `download_paper`, `semantic_search`, `reindex`, `list_papers`, `read_paper` |

## Services In The Compose Stack

- [`valkey`](https://valkey.io/) for SearXNG limiter state
- [`searxng`](https://github.com/searxng/searxng) as the metasearch backend for
  the general endpoint
- `readability` as a local HTML-to-text extraction service for the general
  endpoint
- `mcp-web-search` as the in-repo
  [FastMCP](https://github.com/jlowin/fastmcp)-based Streamable HTTP server
  that exposes the general tools
- `wikipedia-mcp` as a separate Streamable HTTP server for the specialized
  Wikipedia toolset
- `arxiv-mcp` as a separate Streamable HTTP server for the specialized arXiv
  paper toolset, built from upstream source and published through a local
  [FastMCP](https://github.com/jlowin/fastmcp) adapter

SearXNG and Readability stay on the internal Compose network by default. Only
the MCP endpoints are exposed on the host.

## Contract Catalog

The high-level concept lives in this README. Detailed contracts are grouped by
capability class under `contracts/`:

- `contracts/README.md` for the contract catalog and extension rules
- `contracts/general/web_search.md`
- `contracts/general/read_url.md`
- `contracts/general/search_config.md`
- `contracts/specialized/wikipedia.md`
- `contracts/specialized/arxiv.md`

The general endpoint contracts are owned by this repository. Specialized
endpoint contracts may wrap upstream MCP packages; in that case this repository
documents the integration surface and points to the upstream implementation
ownership clearly.

## Prerequisites

- Docker Engine or Docker Desktop
- Docker Compose
- Python 3.11+ if you want to run tests locally

## Configuration

Environment variables are optional because Compose provides sensible defaults.
If you want overrides, define them in `.env`.

General endpoint (`mcp-web-search`) variables:

- `MCP_PORT` default `8000`
- `SEARXNG_SECRET` default `change-me`
- `SEARXNG_REQUEST_TIMEOUT_SECONDS` default `15`
- `SEARXNG_CONNECT_TIMEOUT_SECONDS` default `5`
- `SEARXNG_REQUEST_RETRIES` default `1`
- `MAX_RESULTS` default `10`
- `MAX_QUERY_LENGTH` default `512`
- `MAX_PAGE_NUMBER` default `10`
- `DEFAULT_SAFE_SEARCH` default `1`
- `URL_READ_TIMEOUT_SECONDS` default `20`
- `URL_READ_MAX_BYTES` default `5242880`
- `URL_READ_MAX_CHARS` default `12000`
- `READABILITY_SERVICE_URL` default `http://readability:3010`
- `READABILITY_FALLBACK_ON_FAILURE` default `true`
- `VERIFY_SSL` default `false`
- `USER_AGENT` default `searxng-mcp-search/0.1.0`

Specialized Wikipedia endpoint (`wikipedia-mcp`) variables:

- `WIKIPEDIA_MCP_PORT` default `8001`
- `WIKIPEDIA_LANGUAGE` default `en`
- `WIKIPEDIA_ACCESS_TOKEN` optional; reduces Wikipedia API rate limiting when
  set

To use a Wikipedia country/locale instead of a raw language code, override the
`wikipedia-mcp` service `command` in Compose (for example `--country US`) as
documented in [wikipedia-mcp](https://pypi.org/project/wikipedia-mcp/).

Specialized ArXiv endpoint (`arxiv-mcp`) variables:

- `ARXIV_MCP_PORT` default `8002`
- `ARXIV_UPSTREAM_REF` default `main`; git ref from
  [blazickjp/arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server)
  that is baked into the local image at build time
- `ARXIV_STORAGE_PATH` default `/app/papers`; passed to the upstream server as
  `--storage-path` and backed by the named volume `arxiv_papers`

The upstream `arxiv-mcp-server` package currently runs over stdio. This
toolkit builds its own container from the upstream source repository and
publishes a Streamable HTTP endpoint at `/mcp` through the local adapter in
`arxiv_mcp/app.py`.

## Run The Stack

```bash
docker compose up --build
```

Default host endpoints:

- General MCP endpoint: `http://localhost:8000/mcp`
- General health endpoint: `http://localhost:8000/healthz`
- Specialized Wikipedia MCP endpoint: `http://localhost:8001/mcp`
- Specialized ArXiv MCP endpoint: `http://localhost:8002/mcp`
- Specialized ArXiv health endpoint: `http://localhost:8002/healthz`

### IDE / Cursor

Point each server at its Streamable HTTP URL:

```json
{
  "mcpServers": {
    "general-web-tools": {
      "url": "http://localhost:8000/mcp"
    },
    "wikipedia-research": {
      "url": "http://localhost:8001/mcp"
    },
    "arxiv-research": {
      "url": "http://localhost:8002/mcp"
    }
  }
}
```

## Smoke Test

Check general endpoint readiness:

```bash
curl http://localhost:8000/healthz
```

Call all three MCP endpoints from Python with
[FastMCP](https://github.com/jlowin/fastmcp)'s client:

```python
import asyncio

from fastmcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8000/mcp") as general_client:
        search_response = await general_client.call_tool(
            "web_search",
            {
                "query": "JAX vmap tutorial",
                "limit": 3,
                "safe_search": 1,
                "categories": ["general"],
            },
        )
        print(search_response.data)

        config_response = await general_client.call_tool("search_config", {})
        print(config_response.data)

        page_response = await general_client.call_tool(
            "read_url",
            {
                "url": "https://jax.readthedocs.io/en/latest/quickstart.html",
                "max_chars": 4000,
            },
        )
        print(page_response.data)

    async with Client("http://127.0.0.1:8001/mcp") as wikipedia_client:
        wikipedia_response = await wikipedia_client.call_tool(
            "search_wikipedia",
            {
                "query": "JAX",
                "limit": 3,
            },
        )
        print(wikipedia_response.data)

    async with Client("http://127.0.0.1:8002/mcp") as arxiv_client:
        arxiv_search_response = await arxiv_client.call_tool(
            "search_papers",
            {
                "query": 'ti:"Attention Is All You Need"',
                "categories": ["cs.CL", "cs.LG"],
                "max_results": 1,
            },
        )
        print(arxiv_search_response.data)

        arxiv_abstract_response = await arxiv_client.call_tool(
            "get_abstract",
            {
                "paper_id": "1706.03762",
            },
        )
        print(arxiv_abstract_response.data)

        arxiv_download_response = await arxiv_client.call_tool(
            "download_paper",
            {
                "paper_id": "1706.03762",
            },
        )
        print(arxiv_download_response.data)

        arxiv_library_response = await arxiv_client.call_tool("list_papers", {})
        print(arxiv_library_response.data)

        arxiv_semantic_search_response = await arxiv_client.call_tool(
            "semantic_search",
            {
                "query": "attention mechanisms for sequence modeling",
                "max_results": 3,
            },
        )
        print(arxiv_semantic_search_response.data)

        arxiv_paper_response = await arxiv_client.call_tool(
            "read_paper",
            {
                "paper_id": "1706.03762",
            },
        )
        print(arxiv_paper_response.data)


asyncio.run(main())
```

To verify persistence after the first download:

1. Run the Python smoke test above once.
2. Restart only the specialized paper service with
   `docker compose restart arxiv-mcp`.
3. Re-run `list_papers` against `http://127.0.0.1:8002/mcp` and confirm that
   paper `1706.03762` is still present.

## Local Tests

Install the package and test dependencies, then run `pytest`. On Windows, use
the project virtualenv interpreter:

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

- The general endpoint is implemented in `mcp_server/` and currently published
  as the `searxng-mcp-search` Python package/script.
- SearXNG JSON output is enabled in `searxng/core-config/settings.yml`.
- The limiter is enabled and backed by Valkey.
- SearXNG itself does not publish a host port in the default Compose setup.
- `arxiv-mcp` wraps the upstream `arxiv-mcp-server` package with
  a local FastMCP adapter because the upstream server currently ships as a
  stdio MCP server.
- `arxiv-mcp` is built from the upstream
  [blazickjp/arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server)
  source repository, using `ARXIV_UPSTREAM_REF` with default `main`.
- The arXiv HTTP adapter currently exposes:
  `search_papers`, `get_abstract`, `download_paper`,
  `semantic_search`, `reindex`, `list_papers`, and `read_paper`.
- `semantic_search` works over the local downloaded paper library and depends on
  the upstream `pro` extras being present in the built image.
- The adapter exposes `http://localhost:8002/healthz` for container health
  checks.
- Downloaded arXiv papers are stored in the named volume `arxiv_papers`.
- The current specialized catalog includes Wikipedia and arXiv, but
  `contracts/specialized/` is meant to grow as new domain-specific endpoints
  are added.

## License

This project is available under the
[MIT License](https://opensource.org/license/mit).
