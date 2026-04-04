# Contract Catalog

This repository documents contracts by capability class rather than by internal
module layout.

## General Tools

General tools live behind one MCP endpoint and provide reusable primitives for
open-web access.

Default endpoint: `http://localhost:8000/mcp`

- [web_search](general/web_search.md)
- [read_url](general/read_url.md)
- [search_config](general/search_config.md)

## Specialized Tools

Each specialized capability gets its own endpoint and its own contract
document.

- [Wikipedia](specialized/wikipedia.md)
- [ArXiv](specialized/arxiv.md)

## Extension Rules

- Add cross-domain web primitives under `general/`.
- Add domain-specific endpoints under `specialized/`, one document per
  endpoint/package.
- If a specialized endpoint is provided by an upstream MCP package, document
  the local integration surface here and treat the upstream package as the
  implementation authority.
- Keep `README.md` at the concept and architecture level; keep request/response
  shapes in the files under this directory.
