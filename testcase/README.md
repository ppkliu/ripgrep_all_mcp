# Testcase 使用說明

## 目錄結構

```
testcase/
├── formats.test.ts          # 單元測試: listFormats 工具
├── tokens.test.ts           # 單元測試: countTokens, truncateToTokenLimit
├── upload.test.ts           # 單元測試: uploadFile
├── tool-registry.test.ts    # 單元測試: ToolRegistry (v1 legacy)
├── tool-handler.test.ts     # 單元測試: ToolHandler (v1 legacy)
├── rga-executor.test.ts     # 單元測試: RgaExecutor
├── mcp-server.test.ts       # 整合測試: 啟動 MCP server，透過 MCP SDK Client 測試
├── run-all-tests.sh         # 全測試執行腳本
└── agno/
    ├── pyproject.toml        # Python 專案設定
    ├── requirements.txt      # Python 依賴清單
    ├── test_agno_rga.py      # Agno Agent 整合測試 (stdio 模式)
    ├── document_qa_workflow.py # 自動化文件問答測試 (HTTP 模式 + LiteLLM)
    └── qa_results/           # QA 測試輸出目錄 (自動產生)
```

## 前置需求

### Jest 測試 (TypeScript)

- Node.js >= 18
- 已執行 `npm install`
- 已編譯 TypeScript: `npm run build`

### Agno 測試 (Python)

- Python >= 3.11
- 安裝依賴:
  ```bash
  cd testcase/agno
  uv venv && uv pip install -e ".[dev]"
  # 或
  pip install -r requirements.txt
  ```

## 執行測試

### 全部 Jest 測試 (63 tests, 7 suites)

```bash
npm test
```

### 單一測試檔案

```bash
NODE_OPTIONS='--experimental-vm-modules' npx jest --config jest.config.js testcase/<test-file>.test.ts
```

例如:
```bash
# 只跑 MCP 整合測試
NODE_OPTIONS='--experimental-vm-modules' npx jest --config jest.config.js testcase/mcp-server.test.ts

# 只跑 token 工具測試
NODE_OPTIONS='--experimental-vm-modules' npx jest --config jest.config.js testcase/tokens.test.ts
```

### 使用 run-all-tests.sh

```bash
./testcase/run-all-tests.sh              # 全部測試 (Jest + MCP + Agno)
./testcase/run-all-tests.sh --unit       # 只跑 Jest 單元測試
./testcase/run-all-tests.sh --mcp        # 只跑 MCP 整合測試
./testcase/run-all-tests.sh --agno       # 只跑 Agno 連線測試
```

### Agno 測試

```bash
# 連線測試 (不需要 API key)
python testcase/agno/test_agno_rga.py --connection-only

# 完整測試 (需要 ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY="your-api-key"
python testcase/agno/test_agno_rga.py
```

### Document QA Workflow

```bash
# 1. 啟動 MCP HTTP server
docker compose -f docker-compose.http.yaml up -d

# 2. 設定環境變數
export LITELLM_MODEL="openai/your-model"
export LITELLM_API_BASE="http://localhost:8000/v1"
export LITELLM_API_KEY="sk-xxx"
export MCP_URL="http://localhost:30003/mcp"

# 3. 執行
python testcase/agno/document_qa_workflow.py
```

結果會自動輸出到 `testcase/agno/qa_results/qa_YYYYMMDD_HHMMSS.md`。

## 環境變數

| 變數 | 用途 | 預設值 |
|------|------|--------|
| `ANTHROPIC_API_KEY` | Agno Agent 測試用 API key | (無) |
| `LITELLM_MODEL` | QA workflow 使用的模型 | `openai/your-model-name` |
| `LITELLM_API_BASE` | LiteLLM API 端點 | `http://localhost:8000/v1` |
| `LITELLM_API_KEY` | LiteLLM API key | `sk-placeholder` |
| `MCP_URL` | MCP HTTP server URL | `http://localhost:30003/mcp` |
| `MAX_CONTEXT_TOKENS` | QA workflow 最大上下文 token 數 | `32000` |
| `DOCUMENTS_PATH` | 文件子路徑 (相對於 /data/documents) | (空, 即根目錄) |

## 測試類型說明

| 類型 | 檔案 | 需要 rga | 需要 API key |
|------|------|----------|-------------|
| 單元測試 | `*.test.ts` (除 mcp-server) | 部分 | 否 |
| MCP 整合測試 | `mcp-server.test.ts` | 是 | 否 |
| Agno 連線測試 | `test_agno_rga.py --connection-only` | 否 | 否 |
| Agno 完整測試 | `test_agno_rga.py` | 是 | 是 (Anthropic) |
| QA Workflow | `document_qa_workflow.py` | 是 (Docker) | 是 (LiteLLM) |

## 輸出檔案 (已加入 .gitignore)

- `testcase/agno/qa_results/*.md` — QA 測試結果
- `testcase/agno/.venv/` — Python 虛擬環境
- `testcase/agno/rga_mcp_agno_tests.egg-info/` — Python 建構產物
