# `web_search`

Capability class: General

Default endpoint: `http://localhost:8000/mcp`

Tags: `general_search`, `web`, `searxng`

Search the public web through the toolkit's general endpoint.

## Request

| Field | Type | Required | Contract |
| --- | --- | --- | --- |
| `query` | string | yes | Trimmed. Must be non-empty and no longer than `MAX_QUERY_LENGTH`. |
| `categories` | string[] | no | Optional SearXNG categories. Blank items are removed. |
| `engines` | string[] | no | Optional SearXNG engine names. Blank items are removed. |
| `language` | string | no | Optional SearXNG language code such as `en-US`. |
| `time_range` | string | no | Optional freshness filter. Allowed values: `day`, `month`, `year`. |
| `safe_search` | integer | no | Range `0..2`. Default comes from `DEFAULT_SAFE_SEARCH`. |
| `page` | integer | no | Range `1..MAX_PAGE_NUMBER`. Values are bounded server-side. |
| `limit` | integer | no | Range `1..MAX_RESULTS`. Returned `results` are truncated to this value. |

## Response

| Field | Type | Notes |
| --- | --- | --- |
| `query` | string | Normalized query echoed back from the server. |
| `number_of_results` | integer or `null` | Reported by SearXNG when available. |
| `suggestions` | string[] | Query suggestions. |
| `answers` | string[] | Direct answer strings when available. |
| `infoboxes` | object[] | Normalized infobox payloads from SearXNG. |
| `results` | object[] | Normalized search results, capped by `limit`. |

## `results[]` Item

| Field | Type | Notes |
| --- | --- | --- |
| `title` | string | Falls back to the URL when title is missing. |
| `url` | string | Required for an item to be included. |
| `content` | string or `null` | Snippet or summary text. |
| `engine` | string or `null` | Source engine name. |
| `category` | string or `null` | SearXNG category. |
| `score` | number or `null` | Normalized numeric score when provided upstream. |
| `published_date` | string or `null` | Publication date if available. |
| `thumbnail` | string or `null` | Thumbnail URL if available. |

## Notes

- Blank or whitespace-only values in `categories` and `engines` are removed
  before the request is sent upstream.
- The response shape is stable even though the underlying SearXNG payload may
  vary by engine.
