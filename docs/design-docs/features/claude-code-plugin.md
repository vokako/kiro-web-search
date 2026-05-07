# Design: Claude Code plugin distribution

## Context

Users running Claude Code want to add `web_search` as a tool with minimal
friction. The "raw" install path (`claude mcp add-json ...` with a JSON
blob including a hand-pasted API key) works but is ugly, copy-paste-prone,
and invites the user to leak tokens into shell history.

## Decision

Publish the repository **as its own Claude Code plugin marketplace**, so
that users install with two short slash commands and the API key is
collected through Claude Code's built-in secure-prompt UI:

```
/plugin marketplace add vokako/kiro-web-search
/plugin install kiro-web-search@kiro-web-search
```

Two files make this work, both at `.claude-plugin/` in the repo root:

1. **`marketplace.json`** — declares the repo as a marketplace with a single
   plugin entry pointing at `source: "./"` (the plugin IS the repo).
2. **`plugin.json`** — the plugin manifest. It:
   - Describes the plugin (name, version, author, license, repository).
   - Declares a `userConfig.api_key` field with `sensitive: true` and
     `required: true`. Claude Code prompts for this at install time and
     stores it in the system keychain (macOS), Credential Manager (Windows),
     or `~/.claude/.credentials.json` (Linux).
   - **Embeds the MCP server definition inline** (no separate `.mcp.json`).
     The substitution `KIRO_API_KEY=${user_config.api_key}` wires the
     keychain-stored token into the subprocess environment every time
     Claude Code starts the server.

The MCP server itself is unchanged; the plugin layer just gives users a
one-click path to reach it.

## Alternatives Considered

1. **Only document `claude mcp add-json`** — works today, no plugin
   scaffolding needed. Rejected: user types a JSON blob containing their
   API key on the command line, which leaks into shell history and is
   error-prone to quote correctly across shells.

2. **Ship a separate `.mcp.json` file at repo root** — the canonical layout
   in Anthropic's examples. Rejected: a `.mcp.json` at the repo root *also*
   gets picked up as a project-scope MCP server by anyone who opens the
   plugin's source repo in Claude Code, creating a confusing startup loop
   where the plugin you're developing tries to install itself. Inlining the
   config in `plugin.json` avoids this.

3. **Claude Desktop Extension (`.dxt`) format** — the equivalent "one-click"
   story for Claude Desktop. Deferred: the user asked about Claude Code
   specifically; DXT is a separate format with its own build pipeline, and
   Claude Desktop users can still install via the generic stdio config
   snippet in `README.md`. Adding DXT later is straightforward.

4. **Host the marketplace in a dedicated separate repo** — cleaner separation
   between "the plugin code" and "the catalog". Rejected for a
   single-plugin project: one repo keeps the install path shorter
   (`vokako/kiro-web-search` for both marketplace AND plugin) and removes
   a release-coordination problem.

5. **Publish to the Anthropic official marketplace** — submission is
   possible via https://platform.claude.com/plugins/submit but requires
   review and is a slower path. A self-hosted marketplace ships immediately;
   we can submit later once the project is battle-tested.

## Trade-offs

**Gained:**
- Two-command install (`/plugin marketplace add` + `/plugin install`).
- Secure API-key storage via OS keychain — no tokens on the command line
  or in the user's `.claude.json`.
- Automatic update path (`/plugin update ...`) once the plugin is versioned.
- Clients that aren't Claude Code still work via the manual JSON snippet.

**Gave up:**
- Maintaining the `.claude-plugin/` metadata in addition to `pyproject.toml`.
  Versions must be bumped in both places together (plugin.json `version`,
  `pyproject.toml` `version`, `__init__.py` `__version__`). This is a
  real footgun — see `docs/unresolved.md`.

## Invariants to preserve

- `plugin.json.version` and `pyproject.toml.version` and
  `src/kiro_web_search/__init__.py.__version__` must always agree. Bump
  all three in the same commit.
- Do **not** introduce a repo-root `.mcp.json` — keep the MCP server config
  inline in `plugin.json` to avoid self-install loops when Claude Code is
  opened on this repo.
- `userConfig.api_key.sensitive` must stay `true` — otherwise the token
  lands in plaintext `settings.json`.
- The plugin `mcpServers` key's server name (`kiro-web-search`) matches the
  PyPI command so the uvx invocation resolves without `--from`.

## Lessons Learned

- `claude plugin validate .` validates whichever manifest it finds at
  `.claude-plugin/`. If both `marketplace.json` and `plugin.json` live side
  by side, the marketplace takes precedence; to validate the plugin manifest
  alone, copy it into a scratch directory structure
  (`tmp/.claude-plugin/plugin.json`) and point `claude plugin validate` at
  `tmp/`. This is how we verified the plugin manifest before the repo has
  been published.
