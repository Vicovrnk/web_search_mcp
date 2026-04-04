# ArXiv Specialized Endpoint

Capability class: Specialized

Default endpoint: `http://localhost:8002/mcp`

Implementation: local FastMCP HTTP adapter over source-built
`blazickjp/arxiv-mcp-server`

Upstream source repository:

- `https://github.com/blazickjp/arxiv-mcp-server`

Default build ref:

- `main` via `ARXIV_UPSTREAM_REF`

Observed upstream package version on `main` during integration:

- `0.4.11`

This endpoint is not implemented in `mcp_server/`. This repository builds its
own container from the upstream `blazickjp/arxiv-mcp-server` source tree and
publishes the core paper-research workflow over Streamable HTTP through the
local adapter in `arxiv_mcp/app.py`.

## Tool Contracts

This toolkit currently exposes the following upstream-backed tools:

- `search_papers(query, categories=None, date_from=None, date_to=None,
  max_results=10, sort_by="relevance")`: searches arXiv with optional category
  and date filters. The upstream descriptions encourage quoted phrases plus
  field-specific queries such as `ti:`, `au:`, and `abs:`.
- `get_abstract(paper_id)`: fetches a paper abstract and metadata without
  downloading the full paper.
- `download_paper(paper_id)`: downloads a paper, stores it in local toolkit
  storage, and returns the downloaded content. The upstream implementation
  prefers arXiv HTML and falls back to PDF conversion when needed.
- `semantic_search(query=None, paper_id=None, max_results=10)`: semantic
  similarity search over locally downloaded papers. Requires the upstream
  `pro` dependencies.
- `reindex(clear_existing=True)`: rebuilds the local semantic index for
  downloaded papers. Requires the upstream `pro` dependencies.
- `list_papers()`: lists papers already downloaded into local storage, with
  metadata useful for browsing and duplicate avoidance.
- `read_paper(paper_id)`: returns the markdown content of a previously
  downloaded paper.

## Storage Semantics

- The Compose bundle mounts the named volume `arxiv_papers` into the container
  at `/app/papers`.
- The local HTTP adapter maps `ARXIV_STORAGE_PATH` into the upstream
  `--storage-path` CLI argument before importing the upstream handlers.
- Downloaded papers persist across `arxiv-mcp` container restarts because they
  live in the named Docker volume rather than in the container filesystem.

## Notes

- The upstream project currently ships as a stdio MCP server; this repository
  adds the HTTP transport layer locally instead of relying on a third-party
  gateway image.
- The local adapter exposes the current search, metadata, download, storage,
  and semantic-index workflows, but does not yet mirror every upstream prompt
  or alert feature.
- The upstream project also contains `citation_graph`, but this toolkit
  intentionally does not expose it because it depends on an external service
  outside the project's no-mandatory-keys design goal.
- The local wrapper exposes `/healthz` for Compose health checks.
- Upstream handlers prefix downloaded or read paper content with an untrusted
  content warning, which is preserved by this integration.
- `semantic_search` and `reindex` depend on the upstream `pro` extras
  (`sentence-transformers` and `numpy`) being installed in the built image.
- Upstream documentation describes `search_papers.max_results` with a default
  of `10` and a maximum of `50`.

## Ownership

This document describes the integration surface that this repository ships
today. The authoritative paper-search and paper-storage logic comes from the
upstream `blazickjp/arxiv-mcp-server` source selected by `ARXIV_UPSTREAM_REF`.
The local HTTP adapter, Compose wiring, and healthcheck behavior are owned by
this repository.
