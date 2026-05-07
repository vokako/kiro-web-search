# Feature: web_search MCP tool

## Description

Expose a single MCP tool `web_search(query: string)` that performs a web
search by proxying through Kiro's backend (CodeWhisperer MCP endpoint) and
returns the upstream tool result verbatim.

## Scope of Impact

- Any MCP-compatible agent that configures this server: Claude Desktop, Cursor,
  Continue, Kiro CLI, VS Code MCP, n8n with UV MCP support, etc.
- No other components are affected — this is a standalone binary/package.

## Behavior Details

### Tool: `web_search`

**Input:**

| Field   | Type   | Required | Notes                                |
| ------- | ------ | -------- | ------------------------------------ |
| `query` | string | yes      | Non-empty; whitespace-only rejected. |

**Upstream input constraints (verified by probing):**

- `query` must be **exactly one string**. Lists on `query`, singleton lists,
  empty lists, plural name (`queries`), and non-string types are all rejected
  upstream with `-32602 Invalid tool parameters provided`.
- Extra keys (`count`, `lang`, `region`, etc.) are silently accepted but
  have **no effect** — you always get up to 10 results, language/region
  comes from the backend's own logic. Bake any such constraints into the
  query text itself (e.g. `site:arxiv.org`, `"上海 天气 今天"`).
- There is no way to control page size or pagination.

These findings come from `temp/probe_shapes.py` (not committed); re-run it
if the upstream contract appears to change.

**Output:**

Returns the `result` object from the upstream MCP response. Canonical shape:

```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"results\":[{\"title\":...}], \"totalResults\":10, \"query\":\"...\"}"
    }
  ],
  "isError": false
}
```

The `content[0].text` is a stringified JSON object with fields:

- `results`: array of `{title, url, snippet, domain, publishedDate, id, ...}`
- `totalResults`: integer
- `query`: echoed input
- `error`: null on success

**Error cases:**

- Empty/whitespace query → `ValueError` surfaced to the MCP client as a tool error.
- Upstream returns `error` in JSON-RPC → re-raised as `UpstreamError` and the
  MCP client sees a tool error with the upstream message.
- Network failure / timeout → `UpstreamError` with descriptive message.
- Upstream HTTP 4xx/5xx → `UpstreamError` including status and response body.

## API Dependencies

- **Upstream endpoint:** `POST https://q.us-east-1.amazonaws.com/` (override
  via `--endpoint` / `KIRO_ENDPOINT` for testing or region change)
- **Upstream protocol:** AWS JSON 1.0 envelope carrying MCP JSON-RPC 2.0 in
  the body. Target header: `AmazonCodeWhispererStreamingService.InvokeMCP`.
- **Auth:** Bearer token in `authorization` header, plus `tokentype: API_KEY`.

## Configuration

| Setting  | CLI flag     | Env var         | Default                              | Required |
| -------- | ------------ | --------------- | ------------------------------------ | -------- |
| API key  | `--api-key`  | `KIRO_API_KEY`  | —                                    | yes      |
| Endpoint | `--endpoint` | `KIRO_ENDPOINT` | `https://q.us-east-1.amazonaws.com/` | no       |
| Timeout  | `--timeout`  | `KIRO_TIMEOUT`  | `30` (seconds)                       | no       |

**Precedence:** CLI flag > environment variable > built-in default.

## Constraints

- **Transport:** stdio only. SSE / streamable HTTP are out of scope for v1.
- **No caching.** Every call hits upstream. Rationale in design-docs.
- **No rate limiting.** Upstream enforces its own limits; we surface errors
  as-is.
- **Result shape is a pass-through.** We do not parse, flatten, or rewrite
  the upstream `content`. Rationale in design-docs.
