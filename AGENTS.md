# AGENTS.md

> Agent-facing entry point. For user-facing info see `README.md`.

## What this project is

A **single-tool MCP server** that wraps Kiro's backend `web_search` endpoint.
The upstream is itself an MCP server reachable via
`AmazonCodeWhispererStreamingService.InvokeMCP` on `q.us-east-1.amazonaws.com`,
so this project is fundamentally a **transport adapter**: stdio JSON-RPC ↔
HTTPS + Bearer auth.

Keep it thin. Any temptation to "enrich" or "post-process" results should be
resisted — see `docs/design-docs/features/web-search-mcp.md` for the reasoning.

## Architecture one-liner

```
MCP client ──stdio JSON-RPC──▶ FastMCP (this pkg) ──HTTPS Bearer──▶ Kiro backend MCP
```

## Code map

- `src/kiro_web_search/server.py` — everything lives here: config resolution,
  HTTP call to upstream, FastMCP tool definition, CLI entry point.
- `src/kiro_web_search/__main__.py` — enables `python -m kiro_web_search`.
- `.claude-plugin/marketplace.json` — makes this repo a Claude Code plugin
  marketplace. Users add via `/plugin marketplace add vokako/kiro-web-search`.
- `.claude-plugin/plugin.json` — plugin manifest. Declares `userConfig.api_key`
  (prompted at install time, stored in the system keychain) and embeds the MCP
  server config inline. Substitution: `KIRO_API_KEY=${user_config.api_key}`.
- `.agents/plugins/marketplace.json` — Codex plugin marketplace. Users add via
  `codex plugin marketplace add vokako/kiro-web-search`. Local plugin `source`
  must be a subdir (`./plugins/...`); Codex rejects `"./"`, so the Codex plugin
  cannot live at the repo root like the Claude one does.
- `plugins/kiro-web-search/.codex-plugin/plugin.json` — Codex plugin manifest.
  Unlike Claude, `mcpServers` is a **path** to a file, not an inline object,
  and there is **no `userConfig` secret prompt**.
- `plugins/kiro-web-search/.mcp.json` — Codex MCP server file. The API key is
  inherited from the shell via `env_vars: ["KIRO_API_KEY"]` (Codex can't prompt
  for it). Format verified against `openai/codex` `core-plugins/src/loader.rs`.
- `tests/` — smoke tests for the handshake + a mocked `tools/call`.

## Conventions specific to this project

1. **Single-file server.** No package sprawl. If logic grows, first ask whether
   we really need it before splitting.
2. **Config precedence: CLI flag > env var > default.** Applies to every
   setting. Don't add a setting without honoring this contract.
3. **Pass results through verbatim.** Don't touch `result.content`. The outer
   `result` is returned as-is to the caller. See design-docs for why.
4. **stdlib only for HTTP.** `urllib` is enough. Don't add `httpx`/`requests`
   — dependency weight matters for uvx cold start.
5. **Impersonate AmazonQ-For-CLI in request headers.** Do not introduce our
   own `user-agent` or `x-amz-user-agent`. The upstream endpoint is tuned
   for that client; announcing ourselves is a fast way to get filtered.
   Full rationale in `docs/design-docs/features/web-search-mcp.md`.

## Publishing

- Package name on PyPI: `kiro-web-search`
- Command (entry point): `kiro-web-search`
- Versioning: semver. Bump `__version__` in `src/kiro_web_search/__init__.py`
  **and** `version` in `pyproject.toml` together.
- Build: `uv build`
- Publish: `uv publish` (requires PyPI token)

## Docs map

```
docs/
├── requirements/features/web-search-mcp.md   # WHAT this server does
├── design-docs/features/web-search-mcp.md    # WHY these choices were made
├── unresolved.md                             # Open questions / TODOs
└── references/                               # Upstream API notes
```

## Lookup order when you need info

1. This file → `docs/`
2. Source code (`src/kiro_web_search/server.py` — it's small)
3. Context7 MCP (`/prefecthq/fastmcp` for FastMCP API questions)
4. Web search
5. Your own knowledge — last resort
