# kiro-web-search

A minimal MCP server that exposes a `search` tool to any MCP-compatible
agent (Claude Code, Claude Desktop, Cursor, Kiro CLI, Continue, etc.) over
stdio.

Thin transport adapter: stdio JSON-RPC ↔ upstream HTTPS MCP endpoint.
No caching, no post-processing, results passed through verbatim.

## Prerequisite: get an API key

Requires a Kiro Pro / Pro+ / Power subscription. Sign in at
[app.kiro.dev](https://app.kiro.dev), open **API Keys**, create a new key,
and copy it — the full value is only shown once. Keys look like
`ksk_xxxxxxxx`. Full instructions:
[Kiro CLI docs → Authenticate with an API key](https://kiro.dev/docs/cli/authentication/#authenticate-with-an-api-key-headless-mode).

Use the key as `KIRO_API_KEY` in any of the install paths below.

## Install in Claude Code (one-click)

Inside any Claude Code session:

```
/plugin marketplace add vokako/kiro-web-search
/plugin install kiro-web-search@kiro-web-search
```

Claude Code will prompt you for the API key (stored securely in your
system keychain). Run `/reload-plugins` or start a new session and the
`search` tool appears.

To update later: `/plugin update kiro-web-search@kiro-web-search`.

## Install in Codex CLI

Two ways — pick whichever you prefer.

### Option A — as a Codex plugin

Codex plugins can't prompt for secrets at install time, so export your key
first, then add this repo as a plugin marketplace and install it:

```bash
export KIRO_API_KEY=your-token
codex plugin marketplace add vokako/kiro-web-search
codex plugin add kiro-web-search@kiro-web-search
```

The plugin lives at `plugins/kiro-web-search/` (manifest in
`.codex-plugin/plugin.json`, server in `.mcp.json`). The server inherits
`KIRO_API_KEY` from your environment. Manage it with `codex plugin list` and
`codex plugin remove kiro-web-search@kiro-web-search`.

### Option B — as a plain MCP server

```bash
codex mcp add web-search --env KIRO_API_KEY=your-token -- uvx kiro-web-search
```

Or edit `~/.codex/config.toml` directly:

```toml
[mcp_servers.web-search]
command = "uvx"
args = ["kiro-web-search"]

[mcp_servers.web-search.env]
KIRO_API_KEY = "your-token"
```

Restart Codex and the `search` tool appears. Manage it with `codex mcp list`,
`codex mcp get web-search`, or `codex mcp remove web-search`.

## Install in other MCP clients

### Claude Desktop, Cursor, Continue, generic stdio clients

```json
{
  "mcpServers": {
    "web-search": {
      "command": "uvx",
      "args": ["kiro-web-search"],
      "env": {
        "KIRO_API_KEY": "your-token"
      }
    }
  }
}
```

### Claude Code without the plugin system

```bash
claude mcp add --scope user web-search \
  -e KIRO_API_KEY=your-token \
  -- uvx kiro-web-search
```

## Configuration

| Setting  | CLI flag      | Env var         | Default                              |
| -------- | ------------- | --------------- | ------------------------------------ |
| API key  | `--api-key`   | `KIRO_API_KEY`  | — (required)                         |
| Endpoint | `--endpoint`  | `KIRO_ENDPOINT` | `https://q.us-east-1.amazonaws.com/` |
| Timeout  | `--timeout`   | `KIRO_TIMEOUT`  | `30` seconds                         |

CLI flags override environment variables.

## Exposed tool

### `search(query: string) -> string`

Searches the web. Returns a JSON string with `results` (up to 10 items),
`totalResults`, and the echoed `query`. Each result has `title`, `url`,
`snippet`, `domain`, `publishedDate`, and compliance metadata.

## License

MIT
