#!/bin/bash
# test-mcp-http.sh - MCP HTTP API quick test
#
# Prerequisites:
#   docker compose up -d
#
# Usage:
#   ./examples/test-mcp-http.sh
#   ./examples/test-mcp-http.sh http://your-host:30003/mcp

set -euo pipefail

MCP_URL="${1:-http://localhost:30003/mcp}"
HEALTH_URL="${MCP_URL%/mcp}/health"

echo "=== Health Check ==="
echo "GET $HEALTH_URL"
curl -sf "$HEALTH_URL" | python3 -m json.tool 2>/dev/null || { echo "FAIL: server not reachable"; exit 1; }

echo ""
echo "=== Initialize (get session ID) ==="
RESPONSE=$(curl -s -D /dev/stderr -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "test-script", "version": "1.0"}
    },
    "id": 1
  }' 2>/tmp/mcp_headers)

SESSION_ID=$(grep -i 'mcp-session-id' /tmp/mcp_headers | tr -d '\r' | awk '{print $2}')
echo "Session: $SESSION_ID"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

echo ""
echo "=== Initialized Notification ==="
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
echo "(202 Accepted)"

echo ""
echo "=== List Tools ==="
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2}' | python3 -m json.tool 2>/dev/null

echo ""
echo "=== List Supported Formats ==="
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"rga_list_supported_formats","arguments":{}},"id":3}' | python3 -m json.tool 2>/dev/null

echo ""
echo "=== List Documents ==="
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"rga_list_documents","arguments":{}},"id":4}' | python3 -m json.tool 2>/dev/null

echo ""
echo "=== Done ==="
rm -f /tmp/mcp_headers
