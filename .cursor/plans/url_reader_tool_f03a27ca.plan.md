---
name: url reader tool
overview: Add a new MCP tool that fetches static public `http/https` HTML pages, parses them with Beautiful Soup, and returns markdown-like content plus basic metadata. Reuse the existing FastMCP + `httpx` architecture, with focused config limits and tests.
todos:
  - id: design-contract
    content: Define the `read_url` MCP tool arguments and normalized response model for markdown-like page output.
    status: completed
  - id: reader-runtime
    content: Add a dedicated URL reader module using `httpx` + Beautiful Soup with HTML validation, limits, and extraction heuristics.
    status: completed
  - id: server-wiring
    content: Register the new tool in the FastMCP app and expose any fetch-specific settings needed by the runtime.
    status: completed
  - id: tests-docs
    content: Add targeted tests for fetch/parsing edge cases and document the new tool in the README.
    status: completed
isProject: false
---

# URL Reader Tool Plan

## Goal

Add a new MCP tool, tentatively `read_url`, to the existing server so clients can fetch a public HTML page by URL and receive a normalized, markdown-like representation of the page content.

## Existing Integration Points

The current server already follows a clean registration pattern in [d:\web_search_mcp\mcp_server\app.py](d:\web_search_mcp\mcp_server\app.py) and [d:\web_search_mcp\mcp_server\tools\search.py](d:\web_search_mcp\mcp_server\tools\search.py):

```26:27:d:/web_search_mcp/mcp_server/app.py
register_search_tools(mcp)
register_config_tools(mcp)
```

```184:193:d:/web_search_mcp/mcp_server/tools/search.py
def register_search_tools(mcp: FastMCP) -> None:
    """Register search tools on the provided FastMCP server."""

    settings = get_settings()

    @mcp.tool(
        name="web_search",
        description="Search the public web through a self-hosted SearXNG instance.",
    )
```

This means the URL reader should be added as one more `register_*_tools(...)` module and wired into the same app bootstrap.

## Proposed Implementation

1. Add `beautifulsoup4` to [d:\web_search_mcp\pyproject.toml](d:\web_search_mcp\pyproject.toml) and keep `httpx` as the HTTP client.
2. Introduce a dedicated fetch-and-parse module, likely [d:\web_search_mcp\mcp_server\url_reader.py](d:\web_search_mcp\mcp_server\url_reader.py), instead of overloading the SearXNG-specific client in [d:\web_search_mcp\mcp_server\searx_client.py](d:\web_search_mcp\mcp_server\searx_client.py).
3. Add a new tool module, likely [d:\web_search_mcp\mcp_server\tools\read_url.py](d:\web_search_mcp\mcp_server\tools\read_url.py), that:
  - validates `url`
  - allows only `http/https`
  - calls the reader helper
  - returns a stable MCP-friendly payload
4. Extend [d:\web_search_mcp\mcp_server\tools*init*_.py](d:\web_search_mcp\mcp_server\tools__init__.py) and [d:\web_search_mcp\mcp_server\app.py](d:\web_search_mcp\mcp_server\app.py) to export and register the new tool.
5. Add a typed response model in [d:\web_search_mcp\mcp_server\models.py](d:\web_search_mcp\mcp_server\models.py) so the output shape stays consistent with the existing search/config tools.
6. Add focused tests in [d:\web_search_mcp\tests](d:\web_search_mcp\tests), following the mocking style already used in [d:\web_search_mcp\tests\test_search_tool.py](d:\web_search_mcp\tests\test_search_tool.py).
7. Update [d:\web_search_mcp\README.md](d:\web_search_mcp\README.md) with the new tool contract and a smoke-test example.

## Output Contract

Plan the initial payload around a stable structure such as:

- `url`: requested URL
- `final_url`: post-redirect URL
- `title`: page title if present
- `content_markdown`: markdown-like extracted content
- `excerpt`: optional short preview
- `content_type`: response content type
- `status_code`: final HTTP status code

For the first iteration, keep the output text-focused and avoid trying to expose the full DOM.

## Parsing Strategy

Use Beautiful Soup for static HTML parsing and convert the most common content blocks into markdown-like text:

- headings to `#` / `##`
- paragraphs to plain text blocks
- lists to `- item`
- links to inline markdown links when useful
- code/pre blocks to fenced code blocks when clearly detectable

Also plan to strip low-signal elements before extraction:

- `script`, `style`, `noscript`
- likely chrome/boilerplate containers such as repeated nav/footer blocks when safely identifiable

Keep the first version heuristic and conservative: prefer readable output over aggressive “main content” inference.

## Safety And Limits

Add fetch-specific settings to [d:\web_search_mcp\mcp_server\config.py](d:\web_search_mcp\mcp_server\config.py), for example:

- URL read timeout
- maximum response size / bytes read
- maximum extracted characters returned
- optional redirect cap if not left to `httpx`

Validation should reject:

- non-`http/https` URLs
- non-HTML responses for the first version
- empty or oversized outputs

## Testing Focus

Cover the highest-risk cases:

- successful HTML fetch and markdown-like extraction
- redirect handling and `final_url`
- non-HTML response rejection
- timeout / upstream request failure
- noisy pages with `script/style` blocks removed
- stable handling when title/body are partially missing

## Notes

- The current Docker build in [d:\web_search_mcp\mcp_server\Dockerfile](d:\web_search_mcp\mcp_server\Dockerfile) already installs from `pyproject.toml`, so adding `beautifulsoup4` should flow into the container build automatically.
- Since Beautiful Soup is synchronous, keep network I/O async with `httpx`, and only offload parsing if profiling shows large pages are blocking the event loop.

