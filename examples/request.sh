#!/usr/bin/env bash
# Raw curl against the upstream MCP endpoint. Useful for debugging upstream
# issues without going through the MCP stdio layer.
#
# Usage:
#   KIRO_API_KEY=... ./request.sh "your search query"
#
# Headers are a faithful replay of what AmazonQ-For-CLI sends; do not
# substitute your own user-agent. See docs/design-docs/features/web-search-mcp.md
# for the rationale behind the impersonation.

set -euo pipefail

QUERY="${1:-上海 天气 今天}"
ENDPOINT="${KIRO_ENDPOINT:-https://q.us-east-1.amazonaws.com/}"

if [[ -z "${KIRO_API_KEY:-}" ]]; then
  echo "error: KIRO_API_KEY is not set" >&2
  exit 2
fi

BODY=$(python3 -c "import json,sys; print(json.dumps({'jsonrpc':'2.0','id':'1','method':'tools/call','params':{'name':'web_search','arguments':{'query': sys.argv[1]}}}))" "$QUERY")

curl -sS "$ENDPOINT" \
  -X POST \
  -H 'content-type: application/x-amz-json-1.0' \
  -H 'x-amz-target: AmazonCodeWhispererStreamingService.InvokeMCP' \
  -H 'user-agent: aws-sdk-rust/1.3.14 ua/2.1 api/codewhispererstreaming/0.1.14474 os/macos lang/rust/1.92.0 md/appVersion-2.2.1 app/AmazonQ-For-CLI' \
  -H 'x-amz-user-agent: aws-sdk-rust/1.3.14 ua/2.1 api/codewhispererstreaming/0.1.14474 os/macos lang/rust/1.92.0 m/F app/AmazonQ-For-CLI' \
  -H 'x-amzn-codewhisperer-optout: true' \
  -H 'tokentype: API_KEY' \
  -H 'redirect-for-internal: true' \
  -H "authorization: Bearer $KIRO_API_KEY" \
  -H 'amz-sdk-request: attempt=1; max=3' \
  -H "amz-sdk-invocation-id: $(uuidgen)" \
  -H 'accept: */*' \
  --data-raw "$BODY"
echo
