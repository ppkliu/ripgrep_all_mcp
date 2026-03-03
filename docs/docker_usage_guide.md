# rga-mcp-server 完整使用指南

> ripgrep-all MCP Server — 讓 AI Agent 搜尋 PDF、Office、E-Book、壓縮檔等 20+ 種文件格式

## 目錄

- [快速開始](#快速開始)
- [Docker 一鍵部署](#docker-一鍵部署)
- [curl 測試 MCP HTTP API](#curl-測試-mcp-http-api)
- [MCP 工具詳解](#mcp-工具詳解)
  - [rga_upload_file](#1-rga_upload_file)
  - [rga_extract_text](#2-rga_extract_text)
  - [rga_search_content](#3-rga_search_content)
  - [rga_list_supported_formats](#4-rga_list_supported_formats)
- [支援的文件格式](#支援的文件格式)
- [MCP Client 設定](#mcp-client-設定)
  - [Claude Code](#claude-code)
  - [Claude Desktop](#claude-desktop)
  - [OpenCode](#opencode)
  - [Cursor / Windsurf](#cursor--windsurf)
- [Token 管理策略](#token-管理策略)
- [搜尋技巧](#搜尋技巧)
- [OCR 圖片文字辨識](#ocr-圖片文字辨識)
- [常見使用場景](#常見使用場景)
- [除錯與疑難排解](#除錯與疑難排解)
- [API Reference](#api-reference)

---

## 快速開始

### 30 秒上手

```bash
# 1. 建構 Docker 映像
docker compose build

# 2. 放入你的文件
mkdir -p documents
cp ~/my-files/*.pdf ./documents/
cp ~/my-files/*.docx ./documents/

# 3. 啟動 (stdio 模式)
docker compose up -d

# 4. 設定你的 MCP Client (見下方各 Client 設定)
```

完成後，在 AI 對話中直接說：

> "搜尋 documents 目錄下所有 PDF 中包含 '合約' 的內容"

Agent 會自動使用 rga 工具搜尋並回傳結果。

---

## Docker 一鍵部署

### 專案結構

```
ripgrep_all_mcp/
├── docker-compose.yaml        # stdio 模式 (預設)
├── docker-compose.http.yaml   # HTTP 模式 (遠端)
├── Dockerfile                 # 完整 rga + adapter 環境
├── documents/                 # ← 放入你要搜尋的文件
│   ├── report.pdf
│   ├── contract.docx
│   └── data.xlsx
└── src/                       # MCP server 原始碼
```

### stdio 模式 (本地使用)

```bash
docker compose up -d
```

適用於：Claude Code, OpenCode 等本地 MCP client。

### HTTP 模式 (遠端 / 團隊共用)

```bash
docker compose -f docker-compose.http.yaml up -d

# 驗證
curl http://localhost:30003/health
# → {"status":"ok","server":"rga-mcp-server","version":"2.0.0"}
```

適用於：需要透過網路存取的場景，或 Claude Desktop 的 remote MCP。

---

## curl 測試 MCP HTTP API

MCP 使用 **JSON-RPC 2.0** 協定，透過 Streamable HTTP transport 可以直接用 curl 測試。

> **必要條件**: 先啟動 HTTP 模式 `docker compose -f docker-compose.http.yaml up -d`

### 快速測試 (一鍵腳本)

```bash
#!/bin/bash
# test_mcp.sh — 一鍵測試 MCP HTTP API
MCP_URL="http://localhost:30003/mcp"
HEADERS='-H "Content-Type: application/json" -H "Accept: application/json, text/event-stream"'

# Step 1: Initialize 取得 session ID
echo "=== Initialize ==="
RESPONSE=$(curl -s -D /dev/stderr -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl-test","version":"1.0"}},"id":1}' 2>/tmp/mcp_headers)

SESSION_ID=$(grep -i 'mcp-session-id' /tmp/mcp_headers | tr -d '\r' | awk '{print $2}')
echo "Session: $SESSION_ID"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Step 2: Initialized notification
echo -e "\n=== Initialized ==="
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

# Step 3: List tools
echo -e "\n=== Tools ==="
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2}' | python3 -m json.tool 2>/dev/null

# Step 4: List supported formats
echo -e "\n=== Supported Formats ==="
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"rga_list_supported_formats","arguments":{}},"id":3}' | python3 -m json.tool 2>/dev/null
```

### 逐步手動測試

#### Step 1: Health Check

```bash
curl http://localhost:30003/health
# → {"status":"ok","server":"rga-mcp-server","version":"2.0.0"}
```

#### Step 2: Initialize (建立 MCP Session)

```bash
curl -s -D - -X POST http://localhost:30003/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl-test","version":"1.0"}},"id":1}'
```

回應包含 `mcp-session-id` header，後續所有請求都需要帶上這個 header：

```
HTTP/1.1 200 OK
mcp-session-id: c361e968-c527-4775-82f0-001e34262fae

{"result":{"protocolVersion":"2025-03-26","capabilities":{"tools":{"listChanged":true}},"serverInfo":{"name":"rga-mcp-server","version":"2.0.0"}},"jsonrpc":"2.0","id":1}
```

#### Step 3: Initialized Notification (完成握手)

```bash
curl -s -X POST http://localhost:30003/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <SESSION_ID>" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
# → 202 Accepted (no body)
```

#### Step 4: 列出所有工具

```bash
curl -s -X POST http://localhost:30003/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <SESSION_ID>" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2}'
```

#### Step 5: 上傳檔案

```bash
# 將檔案轉為 base64 後上傳
BASE64=$(base64 -w0 myfile.pdf)
curl -s -X POST http://localhost:30003/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <SESSION_ID>" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\",\"params\":{\"name\":\"rga_upload_file\",\"arguments\":{\"filename\":\"myfile.pdf\",\"content_base64\":\"$BASE64\"}},\"id\":3}"
```

#### Step 6: 搜尋文件內容

```bash
curl -s -X POST http://localhost:30003/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <SESSION_ID>" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"rga_search_content","arguments":{"pattern":"keyword","case_insensitive":true,"context_lines":2}},"id":4}'
```

#### Step 7: 提取文字

```bash
curl -s -X POST http://localhost:30003/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <SESSION_ID>" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"rga_extract_text","arguments":{"file_id":"sample.txt","max_tokens":5000}},"id":5}'
```

#### Step 8: 查看支援格式

```bash
curl -s -X POST http://localhost:30003/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <SESSION_ID>" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"rga_list_supported_formats","arguments":{}},"id":6}'
```

### MCP JSON-RPC 協定說明

| 欄位 | 說明 | 範例 |
|------|------|------|
| `jsonrpc` | 固定 `"2.0"` | `"2.0"` |
| `method` | RPC 方法名 | `"initialize"`, `"tools/list"`, `"tools/call"` |
| `params` | 方法參數 (選填) | `{"name":"rga_search_content","arguments":{...}}` |
| `id` | 請求 ID (選填，通知不需要) | `1`, `2`, `3` |

### 重要注意事項

1. **必要 Headers**: 每個 POST 請求都需要:
   - `Content-Type: application/json`
   - `Accept: application/json, text/event-stream`
   - `mcp-session-id: <ID>` (initialize 之後的請求)

2. **Session 管理**: 每次 `initialize` 會建立新的 session，同一 session 內可執行多次 tool call

3. **Notification vs Request**: `notifications/*` 方法不需要 `id` 欄位，也不會回傳 body

---

## 自訂掛載目錄 (進階)

修改 `docker-compose.yaml` 中的 volumes：

```yaml
volumes:
  # 掛載多個目錄
  - /home/user/reports:/data/documents/reports:ro
  - /shared/team-docs:/data/documents/team:ro
  - /mnt/archive:/data/documents/archive:ro
```

---

## MCP 工具詳解

### 1. `rga_upload_file`

**用途**: 上傳 base64 編碼的檔案到伺服器

**參數**:

| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `filename` | string | Yes | 原始檔名，含副檔名，如 `"report.pdf"` |
| `content_base64` | string | Yes | 檔案內容的 base64 編碼字串 |

**回傳範例**:

```json
{
  "file_id": "a1b2c3d4-5678-9abc-def0-123456789abc.pdf",
  "original_name": "report.pdf",
  "size_bytes": 2567890,
  "size_human": "2.45 MB",
  "status": "uploaded",
  "next_steps": [
    "Use rga_extract_text with file_id=\"a1b2c3d4...\" to extract all text content",
    "Use rga_search_content with file_id=\"a1b2c3d4...\" to search within the file"
  ]
}
```

**使用時機**: 當文件不在 `/data/documents` 掛載目錄中，需要透過 MCP 傳送給伺服器時。

---

### 2. `rga_extract_text`

**用途**: 使用 `rga-preproc` 從檔案中提取全部純文字

**參數**:

| 參數 | 類型 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| `file_id` | string | Yes | - | 上傳後的 file_id，或 `/data/documents` 下的相對路徑 |
| `max_tokens` | number | No | 50000 | 回傳的最大 token 數量 |
| `enable_ocr` | boolean | No | false | 啟用 OCR (掃描 PDF / 圖片) |
| `response_format` | string | No | "json" | `"json"` 或 `"markdown"` |

**JSON 回傳範例**:

```json
{
  "file_id": "reports/quarterly.pdf",
  "original_name": "quarterly.pdf",
  "extracted_text": "Q3 2025 Quarterly Report\n\nRevenue increased by 15%...",
  "token_stats": {
    "full_document_tokens": 125000,
    "returned_tokens": 50000,
    "max_tokens_requested": 50000,
    "truncated": true,
    "note": "Document was truncated from 125000 to 50000 tokens. Use rga_search_content for targeted retrieval."
  }
}
```

**Markdown 回傳範例** (`response_format="markdown"`):

```markdown
## Extracted Text: quarterly.pdf

### Token Statistics
- **Full document**: 125,000 tokens
- **Returned**: 50,000 tokens
- **Truncated**: Yes

### Content
```
Q3 2025 Quarterly Report
Revenue increased by 15%...
```
```

**使用範例**:

```
# 提取掛載目錄中的文件
rga_extract_text(file_id="reports/quarterly.pdf")

# 提取上傳的文件
rga_extract_text(file_id="a1b2c3d4-5678-9abc.pdf", max_tokens=100000)

# 預覽模式 (快速了解文件大小)
rga_extract_text(file_id="huge-doc.pdf", max_tokens=2000)

# 啟用 OCR
rga_extract_text(file_id="scanned-invoice.pdf", enable_ocr=true)
```

---

### 3. `rga_search_content`

**用途**: 使用正則表達式在文件中搜尋匹配的內容

**參數**:

| 參數 | 類型 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| `pattern` | string | Yes | - | 正則表達式搜尋模式 |
| `file_id` | string | No | - | 指定搜尋某個已上傳的檔案 |
| `search_path` | string | No | - | `/data/documents` 下的子路徑 |
| `case_insensitive` | boolean | No | true | 是否忽略大小寫 |
| `context_lines` | number | No | 2 | 匹配前後的上下文行數 |
| `max_matches` | number | No | 100 | 最大匹配數量 |
| `max_tokens` | number | No | 20000 | 回傳的最大 token 數量 |
| `enable_ocr` | boolean | No | false | 啟用 OCR |
| `response_format` | string | No | "json" | `"json"` 或 `"markdown"` |

**JSON 回傳範例**:

```json
{
  "pattern": "revenue|profit",
  "total_matches": 15,
  "search_path": "reports/",
  "results": [
    {
      "file": "reports/quarterly.pdf",
      "line_number": 42,
      "text": "Total revenue for Q3 reached $12.5M",
      "submatches": ["revenue"]
    },
    {
      "file": "reports/annual.pdf",
      "line_number": 108,
      "text": "Net profit margin improved to 18.5%",
      "submatches": ["profit"]
    }
  ],
  "token_stats": {
    "full_result_tokens": 3500,
    "returned_tokens": 3500,
    "max_tokens_requested": 20000,
    "truncated": false
  }
}
```

**使用範例**:

```
# 在所有文件中搜尋
rga_search_content(pattern="合約")

# 在特定子目錄搜尋
rga_search_content(pattern="invoice", search_path="finance/")

# 在已上傳的檔案中搜尋
rga_search_content(pattern="API key", file_id="a1b2c3d4.zip")

# 正則表達式：搜尋 email
rga_search_content(pattern="[\\w.+-]+@[\\w-]+\\.[\\w.]+")

# 正則表達式：搜尋金額
rga_search_content(pattern="\\$[\\d,]+\\.?\\d*")

# 帶更多上下文
rga_search_content(pattern="error", context_lines=5, max_matches=50)
```

---

### 4. `rga_list_supported_formats`

**用途**: 列出所有支援的文件格式及 adapter 狀態

**參數**: 無

**回傳範例**:

```json
{
  "rga_version": "ripgrep_all 1.0.0-alpha.5",
  "total_categories": 11,
  "formats": [
    {
      "category": "PDF",
      "extensions": [".pdf"],
      "adapter": "poppler (pdftotext)",
      "notes": "Native text extraction"
    },
    {
      "category": "Office Documents",
      "extensions": [".docx", ".odt"],
      "adapter": "pandoc",
      "notes": "Via pandoc conversion"
    }
  ],
  "notes": {
    "ocr": "OCR is disabled by default. Pass enable_ocr=true to enable.",
    "documents_dir": "Files in /data/documents are available for direct search.",
    "upload": "Use rga_upload_file to upload files for processing."
  }
}
```

---

## 支援的文件格式

| 類別 | 副檔名 | Adapter | 說明 |
|------|---------|---------|------|
| **PDF** | `.pdf` | poppler (pdftotext) | 原生文字提取 |
| **Office 文件** | `.docx`, `.odt` | pandoc | Word / LibreOffice |
| **E-Book** | `.epub`, `.fb2` | pandoc | 電子書 |
| **Notebook** | `.ipynb` | pandoc | Jupyter Notebook |
| **Web** | `.html`, `.htm` | pandoc | HTML 轉文字 |
| **資料庫** | `.sqlite`, `.db`, `.sqlite3` | sqlite (native) | 提取所有表格資料 |
| **壓縮檔** | `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz` | native (streaming) | 遞迴搜尋壓縮檔內容 |
| **單檔壓縮** | `.gz`, `.bz2`, `.xz`, `.zst` | decompress (native) | 解壓後搜尋 |
| **影片字幕** | `.mkv`, `.mp4`, `.avi` | ffmpeg | 提取字幕軌與 metadata |
| **圖片 (OCR)** | `.jpg`, `.jpeg`, `.png` | tesseract | 需啟用 `enable_ocr=true`，支援英文、繁體中文、簡體中文 |
| **純文字** | `.txt`, `.md`, `.json`, `.xml`, `.yaml`, `.csv`, `.log` 等 | ripgrep (native) | 直接文字搜尋 |

---

## MCP Client 設定

### Claude Code

**~/.claude/mcp.json**

```json
{
  "mcpServers": {
    "rga": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "./documents:/data/documents:ro",
        "-v", "rga-uploads:/data/uploads",
        "rga-mcp-server"
      ]
    }
  }
}
```

### Claude Desktop

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "rga": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/Users/yourname/documents:/data/documents:ro",
        "-v", "rga-uploads:/data/uploads",
        "rga-mcp-server"
      ]
    }
  }
}
```

或使用 HTTP 模式（先啟動 `docker compose -f docker-compose.http.yaml up -d`）：

```json
{
  "mcpServers": {
    "rga": {
      "type": "url",
      "url": "http://localhost:3000/mcp"
    }
  }
}
```

### OpenCode

**opencode.json** (專案根目錄)

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "rga": {
      "type": "local",
      "command": [
        "docker", "run", "--rm", "-i",
        "-v", "./documents:/data/documents:ro",
        "-v", "rga-uploads:/data/uploads",
        "rga-mcp-server"
      ]
    }
  }
}
```

詳細設定請參閱 [OPENCODE_INTEGRATION.md](../integration/OPENCODE_INTEGRATION.md)。

### Cursor / Windsurf

在 MCP 設定介面中新增 server，使用 HTTP 模式：

1. 啟動 HTTP 服務：`docker compose -f docker-compose.http.yaml up -d`
2. 新增 MCP Server URL：`http://localhost:3000/mcp`

---

## Token 管理策略

每個工具回傳都包含 `token_stats`，幫助 Agent 高效管理 context window：

```json
{
  "token_stats": {
    "full_document_tokens": 125000,
    "returned_tokens": 50000,
    "max_tokens_requested": 50000,
    "truncated": true
  }
}
```

### 建議策略

| 場景 | 建議 | 參數設定 |
|------|------|----------|
| **快速預覽** | 先看文件大小和結構 | `max_tokens=2000` |
| **小文件全讀** | tokens < 30K 可一次讀取 | `max_tokens=50000` |
| **大文件** | 用搜尋取代全文提取 | 使用 `rga_search_content` |
| **精準查找** | 正則搜尋特定內容 | `pattern="specific term"` |
| **分批讀取** | 先提取概要，再精準搜尋 | 先 2K 預覽，再搜尋 |

### Agent 決策流程

```
收到文件分析請求
       │
       ▼
  extract_text(max_tokens=2000)  ← 先預覽
       │
       ├─ tokens < 30K → extract_text(max_tokens=50000)  全文讀取
       │
       └─ tokens > 30K → search_content(pattern=...)     精準搜尋
```

---

## 搜尋技巧

### 基本搜尋

```
rga_search_content(pattern="關鍵字")
```

### 正則表達式

| 目標 | Pattern | 說明 |
|------|---------|------|
| Email | `[\\w.+-]+@[\\w-]+\\.[\\w.]+` | 匹配 email 地址 |
| URL | `https?://[\\S]+` | 匹配網址 |
| 金額 | `\\$[\\d,]+\\.?\\d*` | 匹配美元金額 |
| 日期 | `\\d{4}[-/]\\d{2}[-/]\\d{2}` | 匹配日期格式 |
| 電話 | `\\d{2,4}-\\d{3,4}-\\d{4}` | 匹配電話號碼 |
| IP | `\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}` | 匹配 IP 地址 |
| 多個關鍵字 | `keyword1\|keyword2\|keyword3` | OR 搜尋 |

### 限制搜尋範圍

```
# 只搜尋 legal 子目錄
rga_search_content(pattern="clause", search_path="legal/")

# 只搜尋特定已上傳檔案
rga_search_content(pattern="clause", file_id="contract-abc.pdf")
```

---

## OCR 圖片文字辨識

Docker 映像內建 Tesseract OCR，支援三種語言：

- **eng** — English
- **chi_tra** — 繁體中文
- **chi_sim** — 簡體中文

### 使用方式

```
# 提取掃描 PDF 的文字
rga_extract_text(file_id="scanned-doc.pdf", enable_ocr=true)

# 搜尋圖片中的文字
rga_search_content(pattern="invoice", enable_ocr=true)
```

> OCR 預設關閉，因為處理速度較慢。只有需要時才啟用。

---

## 常見使用場景

### 場景 1：法律文件分析

```
> 在 legal 目錄下搜尋所有合約中的賠償條款

rga_search_content(
  pattern="賠償|損害|違約金|indemnification|damages",
  search_path="legal/",
  context_lines=3
)
```

### 場景 2：財務報表搜尋

```
> 提取 Q3 季報中的所有金額

rga_search_content(
  pattern="\\$[\\d,]+\\.?\\d*",
  file_id="quarterly-q3.pdf",
  max_matches=200
)
```

### 場景 3：程式碼壓縮檔搜尋

```
> 在 backup.zip 中搜尋所有的 API endpoint

rga_search_content(
  pattern="app\\.(get|post|put|delete)\\(",
  file_id="backup.zip",
  case_insensitive=false
)
```

### 場景 4：多語言文件搜尋

```
> 在所有文件中搜尋中英文混合的產品名

rga_search_content(
  pattern="產品A|Product A|製品A",
  case_insensitive=true
)
```

### 場景 5：電子書批量搜尋

```
> 在所有 epub 電子書中找到關於 machine learning 的章節

rga_search_content(
  pattern="machine learning|深度學習|neural network",
  search_path="ebooks/"
)
```

---

## 除錯與疑難排解

### 確認環境正常

```bash
# 測試 Docker 映像
docker run --rm rga-mcp-server rga --version
docker run --rm rga-mcp-server which rga-preproc

# 測試文件搜尋
docker run --rm \
  -v ./documents:/data/documents:ro \
  rga-mcp-server \
  rga "test" /data/documents/

# 測試文字提取
docker run --rm \
  -v ./documents:/data/documents:ro \
  rga-mcp-server \
  rga-preproc /data/documents/sample.pdf
```

### 常見錯誤

| 錯誤訊息 | 原因 | 解決方式 |
|----------|------|----------|
| `File not found` | 檔案不在掛載目錄中 | 確認 volume mount 或使用 `rga_upload_file` |
| `rga not installed` | Docker 映像建構失敗 | `docker compose build --no-cache` |
| `Permission denied` | 掛載目錄權限不足 | 確認檔案可讀，使用 `:ro` 唯讀掛載 |
| `Search timeout` | 目錄太大或文件太多 | 用 `search_path` 縮小範圍 |
| `OCR error` | tesseract 問題 | 確認 Docker 映像包含 tesseract-ocr |
| `truncated: true` | 文件超過 token 上限 | 增加 `max_tokens` 或使用搜尋 |

### 日誌查看

```bash
# Docker 模式
docker compose logs -f rga-mcp-server

# 本地模式 (stderr)
node dist/index.js 2>rga-mcp.log
```

---

## API Reference

### 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `MCP_TRANSPORT` | `stdio` | 傳輸模式：`stdio` 或 `streamable-http` |
| `MCP_PORT` | `3000` | HTTP 模式的監聽埠 |
| `UPLOAD_DIR` | `/data/uploads` | 上傳檔案儲存目錄 |
| `DOCUMENTS_DIR` | `/data/documents` | 掛載文件目錄 |
| `MAX_FILE_SIZE_MB` | `100` | 上傳檔案大小上限 (MB) |
| `MAX_OUTPUT_TOKENS` | `100000` | 回傳 token 上限 |
| `RGA_CACHE_DIR` | `/data/cache` | rga 快取目錄 |
| `ENABLE_OCR` | `false` | 全域啟用 OCR |

### Docker Volumes

| 路徑 | 用途 | 建議掛載方式 |
|------|------|-------------|
| `/data/documents` | 要搜尋的文件 | `./documents:/data/documents:ro` |
| `/data/uploads` | 上傳的檔案 | named volume `rga-uploads` |
| `/data/cache` | rga 快取 | named volume `rga-cache` |

### Health Check (HTTP 模式)

```bash
curl http://localhost:3000/health
# → {"status":"ok","server":"rga-mcp-server","version":"2.0.0"}
```
