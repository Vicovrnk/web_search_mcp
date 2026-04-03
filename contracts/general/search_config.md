# `search_config`

Capability class: General

Default endpoint: `http://localhost:8000/mcp`

Tags: `searxng`, `meta`

Return the current public search capabilities of the general endpoint.

## Request

This tool takes no arguments.

## Response

| Field | Type | Notes |
| --- | --- | --- |
| `instance_name` | string | Public SearXNG instance name. |
| `default_locale` | string or `null` | Default locale if exposed by the instance. |
| `default_theme` | string or `null` | Default UI theme if exposed by the instance. |
| `safe_search` | integer or `null` | Instance safe-search setting if available. |
| `categories` | string[] | Enabled categories exposed to clients. |
| `engines` | object[] | Enabled engine metadata. |
| `plugins` | string[] | Enabled public plugin names. |

## `engines[]` Item

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Engine name. |
| `categories` | string[] | Categories supported by that engine. |
| `shortcut` | string or `null` | Shortcut string when exposed by SearXNG. |

## Notes

- Only enabled engines and plugins are exposed.
- Use this tool to guide `web_search` arguments rather than hard-coding
  assumptions about available SearXNG engines or categories.
