"""ASGI entrypoint for the source-built arXiv FastMCP server."""

from __future__ import annotations

import json
import os
import re
import sys
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
import mcp.types as types
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn


def _get_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _configure_storage_path() -> Path:
    storage_path = Path(_get_env("ARXIV_STORAGE_PATH", "/app/papers")).expanduser()
    resolved_path = storage_path.resolve()
    resolved_path.mkdir(parents=True, exist_ok=True)

    if "--storage-path" not in sys.argv:
        sys.argv.extend(["--storage-path", str(resolved_path)])

    return resolved_path


def _canonicalize_paper_id(paper_id: str) -> str:
    """Normalize arXiv IDs by stripping a trailing version suffix."""

    return re.sub(r"v\d+$", "", paper_id.strip())


def _paper_version_sort_key(path: Path) -> tuple[str, int]:
    """Sort paper files by canonical ID, then by numeric version."""

    match = re.search(r"v(\d+)$", path.stem)
    version = int(match.group(1)) if match else 0
    return (_canonicalize_paper_id(path.stem), version)


def _resolve_stored_paper_id(paper_id: str) -> str | None:
    """Resolve a user-facing paper ID to the actual cached markdown filename stem."""

    candidate = paper_id.strip()
    if not candidate:
        return None

    exact_path = STORAGE_PATH / f"{candidate}.md"
    if exact_path.exists():
        return candidate

    canonical_id = _canonicalize_paper_id(candidate)
    canonical_path = STORAGE_PATH / f"{canonical_id}.md"
    if canonical_path.exists():
        return canonical_id

    versioned_matches = sorted(
        STORAGE_PATH.glob(f"{canonical_id}v*.md"),
        key=_paper_version_sort_key,
    )
    if versioned_matches:
        return versioned_matches[-1].stem

    return None


def _normalize_semantic_search_result(result: Any) -> Any:
    """Rewrite semantic-search IDs so they can be fed back into `read_paper`."""

    if not isinstance(result, dict):
        return result

    papers = result.get("papers")
    if not isinstance(papers, list):
        return result

    for paper in papers:
        if not isinstance(paper, dict):
            continue
        paper_id = str(paper.get("id", "")).strip()
        if not paper_id:
            continue

        resolved_id = _resolve_stored_paper_id(paper_id) or _canonicalize_paper_id(
            paper_id
        )
        paper["id"] = resolved_id
        resource_uri = paper.get("resource_uri")
        if isinstance(resource_uri, str) and resource_uri.startswith("arxiv://"):
            paper["resource_uri"] = f"arxiv://{resolved_id}"

    return result


STORAGE_PATH = _configure_storage_path()
MCP_HOST = _get_env("ARXIV_MCP_HOST", "0.0.0.0")
MCP_PORT = int(_get_env("ARXIV_MCP_PORT", "8080"))
MCP_PATH = _get_env("ARXIV_MCP_PATH", "/mcp")
MCP_STATELESS_HTTP = _get_bool_env("ARXIV_MCP_STATELESS_HTTP", True)

# Configure upstream storage before importing the upstream handlers. The
# upstream package resolves storage from CLI args rather than environment vars.
import arxiv_mcp_server.tools.semantic_search as semantic_search_module  # noqa: E402
from arxiv_mcp_server.tools import (  # noqa: E402
    abstract_tool,
    download_tool,
    handle_download,
    handle_get_abstract,
    handle_list_papers,
    handle_read_paper,
    handle_reindex,
    handle_search,
    handle_semantic_search,
    list_tool,
    read_tool,
    reindex_tool,
    search_tool,
    semantic_search_tool,
)


def _patch_semantic_search_compat() -> None:
    """Adapt upstream semantic search to the installed sentence-transformers API."""

    sentence_transformer_cls = getattr(
        semantic_search_module,
        "SentenceTransformer",
        None,
    )
    if sentence_transformer_cls is None:
        return

    def _get_model_compatible() -> Any:
        if semantic_search_module._model is None:
            semantic_search_module.logger.info(
                "Loading semantic embedding model %s",
                semantic_search_module.EMBEDDING_MODEL_NAME,
            )
            semantic_search_module._model = sentence_transformer_cls(
                semantic_search_module.EMBEDDING_MODEL_NAME
            )
        return semantic_search_module._model

    semantic_search_module._get_model = _get_model_compatible


_patch_semantic_search_compat()


def _decode_response(contents: list[types.ContentBlock]) -> Any:
    text_payloads = [
        item.text
        for item in contents
        if isinstance(item, types.TextContent) and item.text.strip()
    ]

    if not text_payloads:
        return {}

    if len(text_payloads) == 1:
        return _decode_text(text_payloads[0])

    return [_decode_text(text) for text in text_payloads]


def _decode_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


async def _invoke_upstream(handler: Any, arguments: dict[str, Any]) -> Any:
    return _decode_response(await handler(arguments))


search_schema = search_tool.inputSchema["properties"]
abstract_schema = abstract_tool.inputSchema["properties"]
download_schema = download_tool.inputSchema["properties"]
read_schema = read_tool.inputSchema["properties"]
semantic_search_schema = semantic_search_tool.inputSchema["properties"]
reindex_schema = reindex_tool.inputSchema["properties"]

mcp = FastMCP(
    name="ArXiv Research",
    instructions=(
        "Search arXiv, inspect abstracts, download papers into local storage, "
        "semantically search what is cached, and read paper content through a "
        "source-built upstream integration."
    ),
)


@mcp.custom_route(path="/healthz", methods=["GET"])
async def healthz(_: Request) -> JSONResponse:
    """Readiness probe for the arXiv FastMCP service."""

    return JSONResponse(
        {
            "status": "ok",
            "storage_path": str(STORAGE_PATH),
            "mcp_path": MCP_PATH,
            "source_repo": "https://github.com/blazickjp/arxiv-mcp-server",
        },
        status_code=HTTPStatus.OK,
    )


@mcp.tool(
    name=search_tool.name,
    description=search_tool.description,
    tags={"arxiv", "papers", "research"},
)
async def search_papers(
    query: Annotated[
        str,
        Field(description=search_schema["query"]["description"], min_length=1),
    ],
    categories: Annotated[
        list[str] | None,
        Field(description=search_schema["categories"]["description"]),
    ] = None,
    date_from: Annotated[
        str | None,
        Field(description=search_schema["date_from"]["description"]),
    ] = None,
    date_to: Annotated[
        str | None,
        Field(description=search_schema["date_to"]["description"]),
    ] = None,
    max_results: Annotated[
        int,
        Field(description=search_schema["max_results"]["description"], ge=1, le=50),
    ] = 10,
    sort_by: Annotated[
        Literal["relevance", "date"],
        Field(description=search_schema["sort_by"]["description"]),
    ] = "relevance",
) -> Any:
    """Search arXiv papers by topic, date range, and category filters."""

    return await _invoke_upstream(
        handle_search,
        {
            "query": query,
            "categories": categories,
            "date_from": date_from,
            "date_to": date_to,
            "max_results": max_results,
            "sort_by": sort_by,
        },
    )


@mcp.tool(
    name=abstract_tool.name,
    description=abstract_tool.description,
    tags={"arxiv", "papers", "metadata"},
)
async def get_abstract(
    paper_id: Annotated[
        str,
        Field(description=abstract_schema["paper_id"]["description"], min_length=1),
    ],
) -> Any:
    """Fetch arXiv metadata and abstract without downloading the full paper."""

    return await _invoke_upstream(handle_get_abstract, {"paper_id": paper_id})


@mcp.tool(
    name=download_tool.name,
    description=download_tool.description,
    tags={"arxiv", "papers", "download"},
)
async def download_paper(
    paper_id: Annotated[
        str,
        Field(description=download_schema["paper_id"]["description"], min_length=1),
    ],
) -> Any:
    """Download an arXiv paper into local storage and return its content."""

    return await _invoke_upstream(handle_download, {"paper_id": paper_id})


@mcp.tool(
    name=list_tool.name,
    description=list_tool.description,
    tags={"arxiv", "papers", "storage"},
)
async def list_papers() -> Any:
    """List locally cached arXiv paper IDs."""

    return await _invoke_upstream(handle_list_papers, {})


@mcp.tool(
    name=semantic_search_tool.name,
    description=semantic_search_tool.description,
    tags={"arxiv", "papers", "semantic_search"},
)
async def semantic_search(
    query: Annotated[
        str | None,
        Field(description=semantic_search_schema["query"]["description"]),
    ] = None,
    paper_id: Annotated[
        str | None,
        Field(description=semantic_search_schema["paper_id"]["description"]),
    ] = None,
    max_results: Annotated[
        int,
        Field(
            description=semantic_search_schema["max_results"]["description"],
            ge=1,
            le=50,
        ),
    ] = semantic_search_schema["max_results"].get("default", 10),
) -> Any:
    """Run semantic similarity search over locally indexed downloaded papers."""

    result = await _invoke_upstream(
        handle_semantic_search,
        {
            "query": query,
            "paper_id": paper_id,
            "max_results": max_results,
        },
    )
    return _normalize_semantic_search_result(result)


@mcp.tool(
    name=reindex_tool.name,
    description=reindex_tool.description,
    tags={"arxiv", "papers", "semantic_search"},
)
async def reindex(
    clear_existing: Annotated[
        bool,
        Field(description=reindex_schema["clear_existing"]["description"]),
    ] = reindex_schema["clear_existing"].get("default", True),
) -> Any:
    """Rebuild the local semantic index from downloaded papers."""

    return await _invoke_upstream(
        handle_reindex,
        {"clear_existing": clear_existing},
    )


@mcp.tool(
    name=read_tool.name,
    description=read_tool.description,
    tags={"arxiv", "papers", "storage"},
)
async def read_paper(
    paper_id: Annotated[
        str,
        Field(description=read_schema["paper_id"]["description"], min_length=1),
    ],
) -> Any:
    """Read a previously downloaded paper from local storage."""

    resolved_paper_id = _resolve_stored_paper_id(paper_id) or paper_id
    return await _invoke_upstream(handle_read_paper, {"paper_id": resolved_paper_id})


app = mcp.http_app(
    path=MCP_PATH,
    stateless_http=MCP_STATELESS_HTTP,
)


def main() -> None:
    """Run the arXiv MCP server over Streamable HTTP."""

    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)


if __name__ == "__main__":
    main()
