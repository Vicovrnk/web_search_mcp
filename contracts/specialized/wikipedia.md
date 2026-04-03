# Wikipedia Specialized Endpoint

Capability class: Specialized

Default endpoint: `http://localhost:8001/mcp`

Implementation: `wikipedia-mcp`

Pinned build version: `2.0.0`

This endpoint is not implemented in `mcp_server/`. This repository packages the
upstream `wikipedia-mcp` server into the toolkit as a standalone specialized
capability.

## Naming

Each tool is registered twice by the upstream server:

- plain name, for example `get_summary`
- `wikipedia_`-prefixed alias, for example `wikipedia_get_summary`

Clients can use either form.

## Tool Contracts

- `search_wikipedia(query, limit=10)`: returns `query`, `results[]`, `status`,
  and optional `count`, `language`, `message`.
- `test_wikipedia_connectivity()`: returns `status`, `url`, `language`, and
  optional `site_name`, `server`, `response_time_ms`, `error`, `error_type`.
- `get_article(title)`: returns `title`, `exists`, and optional `pageid`,
  `summary`, `text`, `url`, `sections`, `categories`, `links`, `error`.
- `get_summary(title)`: returns `title`, optional `summary`, optional `error`.
- `summarize_article_for_query(title, query, max_length=250)`: returns `title`,
  `query`, `summary`.
- `summarize_article_section(title, section_title, max_length=150)`: returns
  `title`, `section_title`, `summary`.
- `extract_key_facts(title, topic_within_article="", count=5)`: returns
  `title`, `topic_within_article`, `facts[]`.
- `get_related_topics(title, limit=10)`: returns `title`, `related_topics[]`.
- `get_sections(title)`: returns `title`, `sections[]`.
- `get_links(title)`: returns `title`, `links[]`.
- `get_coordinates(title)`: returns `title`, `exists`, and optional `pageid`,
  `coordinates[]`, `error`, `message`.

## Nested Item Shapes

`search_wikipedia.results[]` items expose:

- `title`
- `snippet`
- `pageid`
- `wordcount`
- `timestamp`

`get_coordinates.coordinates[]` items expose:

- `latitude`
- `longitude`
- `primary`
- `globe`
- `type`
- `name`
- `region`
- `country`

## Resources

The upstream server also exposes read-only resources:

- `/search/{query}`
- `/article/{title}`
- `/summary/{title}`
- `/summary/{title}/query/{query}/length/{max_length}`
- `/summary/{title}/section/{section_title}/length/{max_length}`
- `/sections/{title}`
- `/links/{title}`
- `/facts/{title}/topic/{topic_within_article}/count/{count}`
- `/coordinates/{title}`

## Notes

- For `search_wikipedia`, limits below or equal to `0` are reset to `10`, and
  limits above `500` are capped at `500`.
- For `extract_key_facts`, an empty `topic_within_article` is treated as
  "no topic filter".

## Ownership

This document describes the integration surface that this repository ships
today. The authoritative implementation and JSON schemas come from the upstream
`wikipedia-mcp` package version pinned in `wikipedia_mcp/Dockerfile`.
