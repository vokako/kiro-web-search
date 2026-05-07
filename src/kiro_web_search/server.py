"""MCP server that wraps Kiro's web_search backend.

Configuration precedence: CLI arg > environment variable > built-in default.

Environment variables:
    KIRO_API_KEY   Bearer token for the upstream service (required).
    KIRO_ENDPOINT  Upstream URL. Defaults to the US-East-1 CodeWhisperer endpoint.
    KIRO_TIMEOUT   Request timeout in seconds. Defaults to 30.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastmcp import FastMCP

from kiro_web_search import __version__

DEFAULT_ENDPOINT = "https://q.us-east-1.amazonaws.com/"
DEFAULT_TIMEOUT = 30

# Impersonate the AmazonQ CLI. The upstream endpoint is tuned for that client;
# advertising our own user-agent is a good way to get filtered or rate-limited.
# These two strings are copied verbatim from a real AmazonQ-For-CLI request and
# must stay in lockstep with each other. See design-docs for rationale.
_UA = (
    "aws-sdk-rust/1.3.14 ua/2.1 api/codewhispererstreaming/0.1.14474 "
    "os/macos lang/rust/1.92.0 md/appVersion-2.2.1 app/AmazonQ-For-CLI"
)
_X_AMZ_UA = (
    "aws-sdk-rust/1.3.14 ua/2.1 api/codewhispererstreaming/0.1.14474 "
    "os/macos lang/rust/1.92.0 m/F app/AmazonQ-For-CLI"
)


@dataclass(frozen=True)
class Config:
    api_key: str
    endpoint: str
    timeout: int


class UpstreamError(RuntimeError):
    """Raised when the upstream service returns an error or is unreachable."""


def _build_headers(api_key: str) -> dict[str, str]:
    # Order and casing mirror the reference AmazonQ-For-CLI request. Adding,
    # renaming, or reordering fields here is an impersonation decision — weigh
    # it against the design-docs rationale before changing.
    return {
        "content-type": "application/x-amz-json-1.0",
        "x-amz-target": "AmazonCodeWhispererStreamingService.InvokeMCP",
        "user-agent": _UA,
        "x-amz-user-agent": _X_AMZ_UA,
        "x-amzn-codewhisperer-optout": "true",
        "tokentype": "API_KEY",
        "redirect-for-internal": "true",
        "authorization": f"Bearer {api_key}",
        "amz-sdk-request": "attempt=1; max=3",
        "amz-sdk-invocation-id": str(uuid.uuid4()),
        "accept": "*/*",
    }


def _call_upstream(config: Config, query: str) -> dict[str, Any]:
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": "web_search",
                "arguments": {"query": query},
            },
        }
    ).encode("utf-8")

    req = urllib_request.Request(
        config.endpoint,
        data=payload,
        method="POST",
        headers=_build_headers(config.api_key),
    )

    try:
        with urllib_request.urlopen(req, timeout=config.timeout) as resp:
            body = resp.read()
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise UpstreamError(f"Upstream HTTP {exc.code}: {detail}") from exc
    except urllib_error.URLError as exc:
        raise UpstreamError(f"Upstream unreachable: {exc.reason}") from exc

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as exc:
        raise UpstreamError(f"Upstream returned non-JSON: {body[:200]!r}") from exc

    if "error" in decoded:
        raise UpstreamError(f"Upstream error: {decoded['error']}")
    if "result" not in decoded:
        raise UpstreamError(f"Upstream response missing result: {decoded}")

    return decoded["result"]


def perform_web_search(config: Config, query: str) -> str:
    """Validate a query and proxy it to the upstream web_search tool.

    Returns the upstream result's inner text payload (a JSON string with
    `results`, `totalResults`, etc.). Returning the raw string lets FastMCP
    wrap it in a single text content block, matching the upstream response
    shape exactly instead of double-nesting.

    Separated from the FastMCP tool binding so it can be unit-tested directly.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    result = _call_upstream(config, query.strip())
    content = result.get("content") or []
    if not content or not isinstance(content, list):
        raise UpstreamError(f"Upstream result missing content: {result}")

    first = content[0]
    text = first.get("text") if isinstance(first, dict) else None
    if not isinstance(text, str):
        raise UpstreamError(f"Upstream content[0] has no text: {first}")
    return text


def build_server(config: Config) -> FastMCP:
    mcp = FastMCP(name="default")

    @mcp.tool
    def search(query: str) -> str:
        """Search the web and return up-to-date results.

        Args:
            query: Search query string.
        """
        return perform_web_search(config, query)

    return mcp


def _resolve_config(args: argparse.Namespace) -> Config:
    api_key = args.api_key or os.environ.get("KIRO_API_KEY")
    if not api_key:
        sys.stderr.write(
            "error: missing API key. Provide --api-key or set KIRO_API_KEY.\n"
        )
        sys.exit(2)

    endpoint = (
        args.endpoint
        or os.environ.get("KIRO_ENDPOINT")
        or DEFAULT_ENDPOINT
    )

    timeout_raw = args.timeout or os.environ.get("KIRO_TIMEOUT")
    try:
        timeout = int(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT
    except ValueError:
        sys.stderr.write(f"error: invalid timeout value: {timeout_raw!r}\n")
        sys.exit(2)

    return Config(api_key=api_key, endpoint=endpoint, timeout=timeout)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kiro-web-search",
        description="MCP server wrapping Kiro's web_search backend (stdio transport).",
    )
    parser.add_argument(
        "--api-key",
        help="Bearer token. Overrides KIRO_API_KEY.",
    )
    parser.add_argument(
        "--endpoint",
        help=f"Upstream URL. Overrides KIRO_ENDPOINT. Default: {DEFAULT_ENDPOINT}",
    )
    parser.add_argument(
        "--timeout",
        help=f"Request timeout in seconds. Overrides KIRO_TIMEOUT. Default: {DEFAULT_TIMEOUT}",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    config = _resolve_config(args)
    server = build_server(config)
    server.run()


if __name__ == "__main__":
    main()
