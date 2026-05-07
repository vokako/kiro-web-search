"""Unit tests for the web_search server.

These tests stub out the upstream HTTP call so they don't require a live
KIRO_API_KEY or network access.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from kiro_web_search.server import (
    Config,
    UpstreamError,
    _call_upstream,
    _parse_args,
    _resolve_config,
    perform_web_search,
)


def _fake_config() -> Config:
    return Config(api_key="test-key", endpoint="https://example.invalid/", timeout=5)


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_call_upstream_success() -> None:
    upstream_payload = {
        "jsonrpc": "2.0",
        "id": "abc",
        "result": {
            "content": [{"type": "text", "text": '{"results":[],"totalResults":0}'}],
            "isError": False,
        },
    }
    body = json.dumps(upstream_payload).encode()

    with patch(
        "kiro_web_search.server.urllib_request.urlopen",
        return_value=_FakeResponse(body),
    ):
        result = _call_upstream(_fake_config(), "test query")

    assert result == upstream_payload["result"]


def test_perform_web_search_unwraps_inner_text() -> None:
    upstream_payload = {
        "jsonrpc": "2.0",
        "id": "abc",
        "result": {
            "content": [{"type": "text", "text": '{"results":[],"totalResults":0}'}],
            "isError": False,
        },
    }
    body = json.dumps(upstream_payload).encode()

    with patch(
        "kiro_web_search.server.urllib_request.urlopen",
        return_value=_FakeResponse(body),
    ):
        out = perform_web_search(_fake_config(), "anything")

    assert out == '{"results":[],"totalResults":0}'
    assert json.loads(out) == {"results": [], "totalResults": 0}


def test_call_upstream_rejects_error_body() -> None:
    err_payload = {"jsonrpc": "2.0", "id": "abc", "error": {"code": -32000, "message": "boom"}}
    body = json.dumps(err_payload).encode()

    with patch(
        "kiro_web_search.server.urllib_request.urlopen",
        return_value=_FakeResponse(body),
    ):
        with pytest.raises(UpstreamError, match="Upstream error"):
            _call_upstream(_fake_config(), "test")


def test_web_search_rejects_empty_query() -> None:
    with pytest.raises(ValueError):
        perform_web_search(_fake_config(), "   ")


def test_resolve_config_cli_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIRO_API_KEY", "env-key")
    monkeypatch.setenv("KIRO_ENDPOINT", "https://env.invalid/")
    monkeypatch.setenv("KIRO_TIMEOUT", "60")

    args = _parse_args(
        ["--api-key", "cli-key", "--endpoint", "https://cli.invalid/", "--timeout", "10"]
    )
    cfg = _resolve_config(args)

    assert cfg.api_key == "cli-key"
    assert cfg.endpoint == "https://cli.invalid/"
    assert cfg.timeout == 10


def test_resolve_config_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIRO_API_KEY", "env-key")
    monkeypatch.delenv("KIRO_ENDPOINT", raising=False)
    monkeypatch.delenv("KIRO_TIMEOUT", raising=False)

    args = _parse_args([])
    cfg = _resolve_config(args)

    assert cfg.api_key == "env-key"
    assert cfg.endpoint == "https://q.us-east-1.amazonaws.com/"
    assert cfg.timeout == 30


def test_resolve_config_missing_key_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KIRO_API_KEY", raising=False)
    args = _parse_args([])

    with pytest.raises(SystemExit) as excinfo:
        _resolve_config(args)

    assert excinfo.value.code == 2
