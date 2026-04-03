# `read_url`

Capability class: General

Default endpoint: `http://localhost:8000/mcp`

Tags: `general_read`, `readability`, `web`

Fetch a public HTML page and return compact markdown-like text from the general
endpoint.

## Request

| Field | Type | Required | Contract |
| --- | --- | --- | --- |
| `url` | string | yes | Public `http` or `https` URL to fetch. |
| `max_chars` | integer | no | Range `256..URL_READ_MAX_CHARS`. Output is capped to this length. |
| `max_body_bytes` | integer | no | Range `4096..URL_READ_MAX_BYTES`. Download size is capped to this value. |

## Response

| Field | Type | Notes |
| --- | --- | --- |
| `url` | string | Original request URL. |
| `final_url` | string | Final URL after redirects. |
| `title` | string or `null` | Extracted page title when available. |
| `content_markdown` | string | Extracted readable content. |
| `excerpt` | string or `null` | Short excerpt when available. |
| `content_type` | string or `null` | Final HTTP content type when known. |
| `status_code` | integer | Final HTTP status code. |

## Notes

- The extraction pipeline may use the local Readability service and can fall
  back to the built-in parser when configured to do so.
- The response contract stays the same regardless of which extractor produced
  the content.
- `content_markdown` is capped by `max_chars`, while download size is capped
  separately by `max_body_bytes`.
