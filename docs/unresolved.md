# Unresolved

Open questions, TODOs, and known gaps. Mark priority and affected areas.

## P2

- **PyPI package name squat check.** Before first publish, verify
  `kiro-web-search` is available on PyPI and not being squatted. If taken,
  fall back to `kiro-websearch-mcp` or similar.
- **GitHub URL in `pyproject.toml`** — now set to `vokako/kiro-web-search`
  everywhere. Remove this bullet once the repo is published and the URL is
  verified to resolve.
- **Version triple-sync footgun.** `plugin.json.version`,
  `pyproject.toml.version`, and `src/kiro_web_search/__init__.py.__version__`
  must be bumped together. Consider a pre-release script (`scripts/bump.sh`)
  or a `ruff`-style version-extractor single-source-of-truth if this starts
  causing drift.
- **Claude Code plugin install flow not yet exercised end-to-end.** We
  validated manifests with `claude plugin validate` but haven't actually
  run `/plugin install` against a real GitHub-hosted copy. The first publish
  is the empirical test; be prepared to iterate on the manifest if Claude
  Code rejects it at install time.

## P3

- **SSE / streamable-HTTP transport** — consider if/when we want to deploy
  hosted instances. Not needed for the current local-stdio use case.
- **Multi-tool dynamic proxy.** The upstream is a full MCP server with more
  than just `web_search`. A future version could call `tools/list` on upstream
  at startup and mirror all tools. Interesting but scope-creep for v1.
- **Local result cache (LRU).** Only worth adding if profiling shows upstream
  latency is a real bottleneck in typical agent workflows.

## P4

- Windows path / encoding quirks. Not yet tested; follow the
  `PYTHONIOENCODING=utf-8` workaround documented by `mcp-server-fetch` if
  users report timeouts on Windows.
