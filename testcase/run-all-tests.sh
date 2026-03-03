#!/usr/bin/env bash
# ============================================================
# rga-mcp-server 完整測試腳本
#
# 使用方式:
#   ./testcase/run-all-tests.sh              # 執行全部測試
#   ./testcase/run-all-tests.sh --unit       # 只跑 Jest 單元測試
#   ./testcase/run-all-tests.sh --mcp        # 只跑 MCP 整合測試
#   ./testcase/run-all-tests.sh --agno       # 只跑 Agno 連線測試
# ============================================================

set -e
cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

MODE="${1:-all}"

echo "============================================================"
echo " rga-mcp-server Test Suite"
echo "============================================================"

# --- Step 0: Build ---
echo -e "\n${YELLOW}[build]${NC} Compiling TypeScript..."
npm run build
echo -e "${GREEN}[build]${NC} Done"

RESULTS=()

# --- Step 1: Jest Unit Tests ---
if [[ "$MODE" == "all" || "$MODE" == "--unit" ]]; then
    echo -e "\n${YELLOW}[jest]${NC} Running unit tests..."
    if npm test 2>&1; then
        RESULTS+=("Unit Tests (Jest): PASS")
        echo -e "${GREEN}[jest]${NC} All unit tests passed"
    else
        RESULTS+=("Unit Tests (Jest): FAIL")
        echo -e "${RED}[jest]${NC} Some tests failed"
    fi
fi

# --- Step 2: MCP Server Integration Test ---
if [[ "$MODE" == "all" || "$MODE" == "--mcp" ]]; then
    echo -e "\n${YELLOW}[mcp]${NC} Running MCP integration test..."
    if NODE_OPTIONS='--experimental-vm-modules' npx jest --config jest.config.js testcase/mcp-server.test.ts 2>&1; then
        RESULTS+=("MCP Integration: PASS")
        echo -e "${GREEN}[mcp]${NC} MCP integration tests passed"
    else
        RESULTS+=("MCP Integration: FAIL")
        echo -e "${RED}[mcp]${NC} MCP integration tests failed"
    fi
fi

# --- Step 3: Agno Connection Test ---
if [[ "$MODE" == "all" || "$MODE" == "--agno" ]]; then
    echo -e "\n${YELLOW}[agno]${NC} Running Agno connection test..."
    if command -v python3 &> /dev/null && python3 -c "import agno" 2>/dev/null; then
        if python3 testcase/agno/test_agno_rga.py --connection-only 2>&1; then
            RESULTS+=("Agno Connection: PASS")
            echo -e "${GREEN}[agno]${NC} Agno connection test passed"
        else
            RESULTS+=("Agno Connection: FAIL")
            echo -e "${RED}[agno]${NC} Agno connection test failed"
        fi
    else
        RESULTS+=("Agno Connection: SKIP (agno not installed)")
        echo -e "${YELLOW}[agno]${NC} Skipped: agno not installed (pip install agno)"
    fi
fi

# --- Summary ---
echo ""
echo "============================================================"
echo " Results"
echo "============================================================"
ALL_PASS=true
for r in "${RESULTS[@]}"; do
    if [[ "$r" == *"FAIL"* ]]; then
        echo -e "  ${RED}$r${NC}"
        ALL_PASS=false
    elif [[ "$r" == *"SKIP"* ]]; then
        echo -e "  ${YELLOW}$r${NC}"
    else
        echo -e "  ${GREEN}$r${NC}"
    fi
done
echo "============================================================"

if $ALL_PASS; then
    exit 0
else
    exit 1
fi
