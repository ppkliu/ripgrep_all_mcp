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
    ├── .env.example          # 環境變數範例 (複製為 .env 使用)
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
- [uv](https://docs.astral.sh/uv/) (建議) 或 pip

#### 使用 uv 建立虛擬環境 (建議)

```bash
# 進入 agno 測試目錄
cd testcase/agno

# 建立虛擬環境 (會在 testcase/agno/.venv/ 下建立)
uv venv

# 啟用虛擬環境
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

# 安裝依賴 (含 dev 套件: pytest, pytest-asyncio)
uv pip install -e ".[dev]"

# 驗證安裝
python -c "import agno; import anthropic; import litellm; print('OK')"
```

#### 使用 pip (替代方案)

```bash
cd testcase/agno
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

安裝完成後回到 repo 根目錄執行測試：

```bash
cd ../..   # 回到 ripgrep_all_mcp/
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

---

## Agno Agent 測試詳細說明

Agno 測試分為三個層級，由淺到深：

### 層級 1: MCP 連線測試 (test_agno_rga.py --connection-only)

**不需要 API key**，僅測試 MCP server 是否正常啟動、工具是否正確註冊。

前置條件：
- 已編譯 TypeScript：`npm run build`
- 已啟用 Agno 虛擬環境

```bash
# 啟用虛擬環境 (如果尚未啟用)
source testcase/agno/.venv/bin/activate

# 執行連線測試
python testcase/agno/test_agno_rga.py --connection-only
```

測試內容：
- 透過 stdio 啟動 MCP server (node dist/index.js)
- 驗證 MCP 連線成功
- 檢查 4 個工具是否已註冊：`rga_upload_file`, `rga_extract_text`, `rga_search_content`, `rga_list_supported_formats`

預期輸出：
```
============================================================
TEST 1: MCP Connection & Tool Discovery
============================================================
[PASS] MCP server connected successfully
[INFO] Discovered 5 tools: [...]
  [PASS] rga_upload_file
  [PASS] rga_extract_text
  [PASS] rga_search_content
  [PASS] rga_list_supported_formats
```

### 層級 2: 完整工具測試 (test_agno_rga.py)

**需要 LLM API**（Anthropic 或 OpenAI-compatible local LLM），測試所有 MCP 工具的實際調用，以及 Agno Agent 的 LLM 整合。

前置條件：
- 已編譯 TypeScript：`npm run build`
- 已啟用 Agno 虛擬環境
- 已設定 LLM API（二擇一，見下方）

#### 使用 .env 檔案設定 (建議)

測試腳本會自動載入 `testcase/agno/.env`，不需要手動 export 環境變數：

```bash
# 複製範例檔並編輯
cd testcase/agno
cp .env.example .env
# 編輯 .env 填入實際值

# 執行測試
source .venv/bin/activate
python test_agno_rga.py
```

#### 方式 A: 使用 Anthropic API

`.env` 設定：
```bash
ANTHROPIC_API_KEY=sk-ant-xxx
# LLM_MODEL=claude-sonnet-4-5    # 選填，預設 claude-sonnet-4-5
```

或直接 export：
```bash
export ANTHROPIC_API_KEY="sk-ant-xxx"
python testcase/agno/test_agno_rga.py
```

#### 方式 B: 使用 OpenAI-compatible Local LLM

適用於 LM Studio、Ollama、vLLM、LocalAI 等提供 OpenAI-compatible API 的本地模型。

`.env` 設定：
```bash
LLM_API_BASE=http://localhost:1234/v1
LLM_API_KEY=lm-studio
# LLM_MODEL 選填，未設定時自動從 API /v1/models 偵測
```

或直接 export：
```bash
export LLM_API_BASE="http://localhost:1234/v1"
export LLM_API_KEY="lm-studio"
export LLM_MODEL="openai/your-local-model"
python testcase/agno/test_agno_rga.py
```

常見 Local LLM 設定範例：

| LLM 服務 | LLM_API_BASE | LLM_MODEL | 備註 |
|----------|-------------|-----------|------|
| LM Studio | `http://localhost:1234/v1` | `openai/lmstudio-model` | 啟動後自動提供 API |
| Ollama | `http://localhost:11434/v1` | `openai/llama3.1` | 需先 `ollama serve` |
| vLLM | `http://localhost:8000/v1` | `openai/Qwen2.5-72B` | 依啟動參數而定 |
| LocalAI | `http://localhost:8080/v1` | `openai/gpt-4` | 依載入模型而定 |

> **LLM 優先順序**: 若同時設定 `LLM_API_BASE` 和 `ANTHROPIC_API_KEY`，會優先使用 OpenAI-compatible API。

#### LLM_MODEL 格式說明

模型名稱使用 [LiteLLM](https://docs.litellm.ai/docs/providers) 格式：

- OpenAI-compatible: `openai/<model-name>` (例如 `openai/llama3.1`)
- Anthropic: 直接使用模型 ID (例如 `claude-sonnet-4-5`)
- **未設定時**: 自動查詢 `{LLM_API_BASE}/models` 端點偵測可用模型
- 若指定模型名稱不含 `/`，會自動補上 `openai/` 前綴

#### 測試內容（3 個階段）

| 階段 | 測試名稱 | 需要 LLM API | 說明 |
|------|---------|-------------|------|
| Test 1 | MCP Connection | 否 | 連線與工具發現 |
| Test 2 | Direct Tool Calls | 否 | 直接呼叫每個工具 (list_formats, upload, extract, search) |
| Test 3 | Agno Agent Integration | 是 | LLM Agent 透過自然語言驅動工具呼叫 |

Test 2 會自動建立臨時測試文件 (sample.txt, notes.md, config.json)，測試完畢後自動清理。

Test 3 會讓 Agent 執行三個任務：
1. 列出支援的文件格式
2. 在文件中搜尋 "bug"
3. 提取 sample.txt 的內容並摘要

預期輸出：
```
============================================================
SUMMARY
============================================================
  [PASS] MCP Connection
  [PASS] Direct Tool Calls
  [PASS] Agno Agent
```

### 層級 3: Document QA Workflow (document_qa_workflow.py)

**需要 Docker HTTP server + LLM API**，自動化文件問答測試流程。

前置條件：
- Docker HTTP server 已啟動
- 已啟用 Agno 虛擬環境
- 已設定 LLM 環境變數 (`.env` 或 export)
- documents/ 目錄中已放入測試文件

```bash
# 1. 啟動 MCP HTTP server
docker compose -f docker-compose.http.yaml up -d

# 驗證 server 啟動
curl http://localhost:30003/health

# 2. 啟用虛擬環境
source testcase/agno/.venv/bin/activate

# 3. 設定 .env (與 test_agno_rga.py 共用同一份)
cd testcase/agno
cp .env.example .env     # 編輯填入 LLM_API_BASE / LLM_API_KEY 等

# 4. 執行
python document_qa_workflow.py
```

> **環境變數**: QA workflow 支援 `LLM_*` 和 `LITELLM_*` 兩組變數名稱（`LLM_*` 優先）。
> 未設定 `LLM_MODEL` 時會自動從 API `/v1/models` 端點偵測可用模型。

**雙 LLM 模式**（選填）：設定 `LLM_API_BASE_2` 可讓 Phase 4 Agent 使用不同的 LLM，
方便比較不同模型的 tool calling 能力：
```bash
# .env 中加入第二組 LLM
LLM_API_BASE_2=http://localhost:8000/v1
LLM_API_KEY_2=no-key
# LLM_MODEL_2=openai/your-agent-model   # 選填，未設定時自動偵測
```

進階設定（`.env` 或 export）：
```bash
MCP_URL=http://localhost:30003/mcp      # MCP HTTP URL (預設)
MAX_CONTEXT_TOKENS=32000                # 最大上下文 token 數
DOCUMENTS_PATH=subfolder                # 指定文件子路徑
```

執行流程（5 個階段）：

| 階段 | 說明 |
|------|------|
| Phase 1 | 透過 MCP 掃描 documents/ 下所有檔案路徑 (表格化輸出) |
| Phase 2 | 提取文字、判斷 token 是否放入 context、生成中文問題、精煉摘要 |
| Phase 3 | 產生文件摘要 Markdown 表格 |
| Phase 4 | Agno Agent 逐一問答 (支援雙 LLM)，即時顯示 tool calling 歷程 |
| Phase 5 | 輸出帶時間戳的 QA 結果 Markdown + 時間分析 |

結果會自動輸出到 `testcase/agno/qa_results/qa_YYYYMMDD_HHMMSS.md`，包含：
- 測試環境設定表格
- 各階段時間分析 (Phase 耗時、佔比)
- 文件摘要表格
- 每題的回答、工具呼叫歷程、回應時間
- 工具呼叫統計 (呼叫次數、佔比)
- 摘要 Context 對照比較

## 環境變數

| 變數 | 用途 | 預設值 |
|------|------|--------|
| `LLM_API_BASE` | 主要 LLM — OpenAI-compatible API 端點 | (無) |
| `LLM_API_KEY` | 主要 LLM — API key | `no-key` |
| `LLM_MODEL` | 主要 LLM — 模型名稱，未設定時自動偵測 | 依 provider 自動選擇 |
| `LLM_API_BASE_2` | 第二組 LLM — Agent 用 (選填，未設定用主要) | (無) |
| `LLM_API_KEY_2` | 第二組 LLM — API key | `no-key` |
| `LLM_MODEL_2` | 第二組 LLM — 模型名稱，未設定時自動偵測 | (無) |
| `ANTHROPIC_API_KEY` | Anthropic API key | (無) |
| `LITELLM_MODEL` | `LLM_MODEL` 的別名 (向下相容) | (無) |
| `LITELLM_API_BASE` | `LLM_API_BASE` 的別名 (向下相容) | (無) |
| `LITELLM_API_KEY` | `LLM_API_KEY` 的別名 (向下相容) | (無) |
| `MCP_URL` | MCP HTTP server URL | `http://localhost:30003/mcp` |
| `MAX_CONTEXT_TOKENS` | QA workflow 最大上下文 token 數 | `32000` |
| `DOCUMENTS_PATH` | 文件子路徑 (相對於 /data/documents) | (空, 即根目錄) |

## 測試類型說明

| 類型 | 檔案 | 需要 rga | 需要 API key |
|------|------|----------|-------------|
| 單元測試 | `*.test.ts` (除 mcp-server) | 部分 | 否 |
| MCP 整合測試 | `mcp-server.test.ts` | 是 | 否 |
| Agno 連線測試 | `test_agno_rga.py --connection-only` | 否 | 否 |
| Agno 完整測試 | `test_agno_rga.py` | 是 | 是 (Anthropic 或 OpenAI-compatible) |
| QA Workflow | `document_qa_workflow.py` | 是 (Docker) | 是 (OpenAI-compatible 或 Anthropic) |

## 輸出檔案 (已加入 .gitignore)

- `testcase/agno/qa_results/*.md` — QA 測試結果
- `testcase/agno/.venv/` — Python 虛擬環境
- `testcase/agno/rga_mcp_agno_tests.egg-info/` — Python 建構產物
