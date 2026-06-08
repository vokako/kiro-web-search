# Design: web_search MCP server

## Context

We want Kiro's internal `web_search` capability reachable from any
MCP-compatible agent. The upstream service (CodeWhisperer) already speaks
MCP JSON-RPC, but it's gated behind AWS auth and an HTTPS endpoint rather
than stdio. Agents expect stdio. Bridging is the job.

## Decision

Ship a **single-tool FastMCP server** published on PyPI as `kiro-web-search`,
invoked via `uvx kiro-web-search`. Implementation is a single file
(`server.py`), ~160 lines, stdlib-only for HTTP.

### Distribution: uvx over npx

Chosen after comparing `uvx` + PyPI vs `npx` + npm:

| Dimension          | uvx                                     | npx                                    |
| ------------------ | --------------------------------------- | -------------------------------------- |
| Cold start (cached)| ~50–150ms                               | ~200–800ms                             |
| Runtime memory     | ~25–35 MB (FastMCP)                     | ~40–80 MB baseline Node                |
| Version mgmt       | uv bundles Python — zero toolchain drift| nvm interaction is a known issue      |
| Stability reports  | Multiple community reports of uvx succeeding where npx failed | Multiple open issues around nvm + MCP |
| Official precedent | `mcp-server-fetch`, `mcp-server-git` etc.| Also common, but official Python servers prefer uvx |

Sources: `modelcontextprotocol/servers` repo (official reference servers all
use uvx); GitHub issues #64, #76, #240, #436, #213 across MCP repos documenting
npx+nvm failures.

### Framework: FastMCP over hand-rolled JSON-RPC

A hand-rolled stdlib-only implementation was considered and rejected:

- FastMCP is the de-facto Python framework (`jlowin/fastmcp`, now under
  PrefectHQ), extensively used across the MCP ecosystem.
- Business code collapses to ~15 lines; protocol handshake, capabilities
  negotiation, cancellation, logging all handled by the framework.
- The ~80 MB dependency footprint is paid **once** by uv's cache. Subsequent
  `uvx` invocations pay zero extra cost.
- Future MCP spec changes are absorbed by a FastMCP upgrade, not by our code.

### HTTP layer: stdlib `urllib` over `httpx`

- The whole HTTP surface is one POST. `urllib` handles it in ~20 lines.
- Avoids adding `httpx` as a dependency, keeping cold-start install smaller.
- FastMCP runs sync tool functions in a thread pool, so blocking `urllib`
  does not block the event loop. Verified against FastMCP docs.

### Request headers: impersonate AmazonQ-For-CLI

We send the exact headers a real AmazonQ-For-CLI client sends, including:

- `user-agent: aws-sdk-rust/1.3.15 ua/2.1 api/codewhispererstreaming/0.1.16551 ... md/appVersion-2.6.0 app/AmazonQ-For-CLI`
- `x-amz-user-agent: ...` (same string shape, `m/F` suffix)
- `x-amzn-codewhisperer-optout: true`
- `tokentype: API_KEY`
- `amz-sdk-request: attempt=1; max=3`
- `amz-sdk-invocation-id: <fresh UUID per call>`

**Rationale:** the endpoint `runtime.us-east-1.kiro.dev` is tuned for the
AmazonQ / Kiro CLI. Advertising our own user-agent (`kiro-web-search-mcp/0.1.0`
or similar) is a reliable way to:

1. Get bucketed into an unexpected rate-limit tier.
2. Show up on a traffic-pattern dashboard as "unknown client" and invite
   throttling or blocking.
3. Fail client-side feature-flag checks that gate `web_search` availability.

**Invariants to preserve:**

- **Do not add our own `user-agent`, `x-amz-user-agent`, or any custom
  tracer headers.** The disguise is only effective if it's complete.
- **Do not add a `redirect-for-internal: true` header.** Earlier captures
  contained it; current captures (June 2026, AmazonQ-For-CLI v2.6.0) do
  not. Re-introducing it would make our traffic look stale.
- `amz-sdk-invocation-id` must be a **fresh UUID per request**. `aws-sdk-rust`
  rotates it per attempt; a hardcoded or repeated value is a tell.
- If the upstream starts rejecting requests, update the two UA strings in
  lockstep from a current AmazonQ-For-CLI capture. They must agree on
  version/OS/lang fields.

**Endpoint migration (June 2026):**

The default endpoint moved from `https://q.us-east-1.amazonaws.com/` to
`https://runtime.us-east-1.kiro.dev/` to follow the AmazonQ → Kiro brand
rename. Both endpoints accept the same payload as of testing, but we
default to the new one because:

1. The old generic AWS subdomain is on the typical 6–12 month deprecation
   path that follows a brand split.
2. The new domain semantically matches the product, removing one
   inconsistency between our impersonation and what real clients send.

Users who set `KIRO_ENDPOINT` explicitly are not affected — only the
default changed. If the new domain misbehaves, fall back via
`KIRO_ENDPOINT=https://q.us-east-1.amazonaws.com/`.

**Non-goals:**

- We are **not** trying to defeat advanced fingerprinting (TLS JA3, HTTP/2
  settings, header ordering beyond what `urllib` produces). If the upstream
  deploys those, this approach will need more work.

### Pass-through result semantics

The upstream returns `result.content[0].text` as a stringified JSON. We
deliberately do **not** parse/unwrap it. Reasons:

1. This is the canonical MCP tool-result shape. The caller's MCP client
   already knows how to render `content[].text`.
2. Any unwrapping we do couples us to the upstream's internal JSON schema;
   when it changes, we break silently.
3. Unwrapping reduces the data an LLM client can see (e.g. `publishedDate`,
   `maxVerbatimWordLimit` fields that compliance tooling may rely on).

### Config surface

CLI flags AND env vars, CLI wins. Rationale:

- Some hosts (Claude Desktop) pass secrets via `env:` in the JSON config.
- Others (bare shell, systemd) prefer flags.
- Supporting both with a clear precedence costs ~15 lines and removes a class
  of "works on my machine" bugs.

## Alternatives Considered

1. **Pure stdlib Python, no framework** — viable, ~60 lines. Rejected because
   FastMCP is more maintainable and the dep weight is paid once by uv cache.
2. **TypeScript + `@modelcontextprotocol/sdk` + npx** — more popular in the
   overall MCP ecosystem, but npx+nvm issues are real and Node's baseline
   memory is higher. Rejected.
3. **Go / Rust static binary** — lowest possible runtime overhead, but
   publishing and updating a compiled binary is far more friction than
   PyPI + uvx. Rejected for a simple wrapper. Would reconsider if this
   grew into a multi-tool, latency-critical server.
4. **Docker image** — too heavy on cold start and defeats "uvx one-liner"
   ergonomics. Useful for hosted deployments, not for local agent use.
5. **SSE / streamable-HTTP transport** — not needed for v1. stdio is the
   dominant client config and covers all target agents.
6. **Local result caching (LRU)** — deferred. Adds state, complicates the
   "it's just a wrapper" story. Revisit if profiling shows upstream latency
   is the bottleneck for real workflows.

## Trade-offs

**Gained:**
- Single command to run: `uvx kiro-web-search`
- Zero-install for users (uv handles it)
- Matches Anthropic's own reference-server pattern
- Small, auditable codebase

**Gave up:**
- Python runtime baseline (~25 MB RAM while idle). A Rust/Go implementation
  could idle at ~5 MB but would cost 10× more to maintain.
- Cold-start when uv cache is empty (~1–3 s). Acceptable: happens once.

## Lessons Learned

Historical notes from early reference scripts (no longer in the repo — an
`examples/request.sh` curl recipe was removed as the MCP server covers the
same ground). Keep these in mind if you ever write a new raw curl harness:

- **Single-quote variable expansion trap**: `-H 'authorization: Bearer $TOKEN'`
  keeps `$TOKEN` as a literal because single quotes block shell expansion —
  the upstream then returns a confusing "invalid bearer token" error. Use
  double quotes, or build headers in code like we do now.
- **Hardcoded `content-length`**: curl computes `Content-Length`
  automatically; never hardcode it. The same principle applies anywhere we
  expose a raw HTTP adapter — don't compute framing manually.
- **`amz-sdk-invocation-id` must be unique per request**: the AWS SDK
  rotates it per attempt, so a hardcoded or repeated value is a tell that
  the traffic is not from a real SDK client. We now generate one per call.
