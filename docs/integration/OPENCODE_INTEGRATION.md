# OpenCode + rga-mcp-server 整合指南

> 將 ripgrep-all MCP server 整合到 [OpenCode](https://opencode.ai) 終端 AI 編碼工具中。

## 目錄

- [概述](#概述)
- [前置條件](#前置條件)
- [安裝方式](#安裝方式)
  - [方式一：Docker (推薦)](#方式一docker-推薦)
  - [方式二：本地安裝](#方式二本地安裝)
- [MCP 設定](#mcp-設定)
  - [專案級設定](#專案級設定)
  - [全域設定](#全域設定)
- [工具權限設定](#工具權限設定)
- [Agent 設定](#agent-設定)
- [Skill 設定](#skill-設定)
- [使用範例](#使用範例)
- [驗證與除錯](#驗證與除錯)
- [進階設定](#進階設定)

---

## 概述

OpenCode 是一個 Go-based 的終端 AI 編碼工具，支援 MCP (Model Context Protocol) 擴展外部工具。本文件說明如何將 rga-mcp-server 整合到 OpenCode，讓 AI Agent 能夠搜尋 PDF、DOCX、EPUB、ZIP 等 20+ 種文件格式。

**整合架構：**

```
┌──────────────────────────────┐
│       OpenCode TUI           │
│  (Claude / GPT / Gemini)     │
└──────────┬───────────────────┘
           │ MCP Protocol
           ▼
┌──────────────────────────────┐
│    rga-mcp-server (Docker)   │
│  ┌─────────┐ ┌────────────┐ │
│  │ upload  │ │ extract    │ │
│  │ _file   │ │ _text      │ │
│  ├─────────┤ ├────────────┤ │
│  │ search  │ │ list       │ │
│  │ _content│ │ _formats   │ │
│  └─────────┘ └────────────┘ │
│        ↕ rga / rga-preproc   │
│   /data/documents (mounted)  │
└──────────────────────────────┘
```

## 前置條件

- [OpenCode](https://opencode.ai) 已安裝
- [Docker](https://docs.docker.com/get-docker/) 已安裝（Docker 方式）
- 或 Node.js >= 18 + ripgrep-all（本地方式）

## 安裝方式

### 方式一：Docker (推薦)

```bash
# 1. 進入專案目錄
cd ripgrep_all_mcp

# 2. 建構 Docker 映像
docker compose build

# 3. 將要搜尋的文件放到 documents 資料夾
cp ~/my-reports/*.pdf ./documents/
cp ~/contracts/*.docx ./documents/
```

### 方式二：本地安裝

```bash
# 1. 安裝 ripgrep-all
# macOS:
brew install ripgrep-all
# Ubuntu:
sudo apt-get install ripgrep-all

# 2. 安裝 Node 依賴並編譯
cd ripgrep_all_mcp
npm install
npm run build
```

## MCP 設定

OpenCode 支援兩種 MCP server 類型：`local` (stdio) 和 `remote` (HTTP)。

### 專案級設定

在專案根目錄建立 `opencode.json`：

#### Docker stdio 模式（推薦）

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
        "-v", "rga-cache:/data/cache",
        "rga-mcp-server"
      ],
      "environment": {
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

#### Docker HTTP 模式

先啟動服務：

```bash
docker compose -f docker-compose.http.yaml up -d
```

然後設定 OpenCode：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "rga": {
      "type": "remote",
      "url": "http://localhost:3000/mcp"
    }
  }
}
```

#### 本地安裝模式

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "rga": {
      "type": "local",
      "command": ["node", "/path/to/ripgrep_all_mcp/dist/index.js"],
      "environment": {
        "MCP_TRANSPORT": "stdio",
        "DOCUMENTS_DIR": "/path/to/your/documents"
      }
    }
  }
}
```

### 全域設定

將 MCP 設定放到全域設定檔案，所有專案都可使用：

**路徑**: `~/.config/opencode/opencode.json`

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "rga": {
      "type": "local",
      "command": [
        "docker", "run", "--rm", "-i",
        "-v", "{env:HOME}/documents:/data/documents:ro",
        "-v", "rga-uploads:/data/uploads",
        "rga-mcp-server"
      ]
    }
  }
}
```

> OpenCode 支援 `{env:VARIABLE}` 語法來引用環境變數。

## 工具權限設定

OpenCode 預設允許所有工具執行。你可以在 `opencode.json` 中設定 MCP 工具的權限：

```jsonc
{
  "permission": {
    // 所有 rga 工具需要詢問確認
    "rga_*": "ask",

    // 或單獨設定
    "rga_upload_file": "ask",        // 上傳需確認
    "rga_extract_text": "allow",     // 提取自動允許
    "rga_search_content": "allow",   // 搜尋自動允許
    "rga_list_supported_formats": "allow"  // 列格式自動允許
  }
}
```

權限選項：
- `"allow"` — 自動執行，不需確認
- `"ask"` — 每次執行前詢問使用者
- `"deny"` — 禁止執行

## Agent 設定

你可以建立專門的 Agent 來使用 rga 工具。在 `.opencode/agents/` 或 `~/.config/opencode/agents/` 建立：

### `.opencode/agents/document-analyst.md`

```markdown
---
name: document-analyst
model: anthropic/claude-sonnet-4-5
tools:
  - rga_*
  - read
  - write
  - bash
---

You are a document analysis agent. You can search and extract text from
PDF, DOCX, EPUB, ZIP, and other document formats using the rga MCP tools.

## Workflow

1. Use `rga_list_supported_formats` to check available formats
2. For files in /data/documents, use `rga_search_content` to search directly
3. For uploaded files, use `rga_upload_file` first, then `rga_extract_text`
4. Always check `token_stats` to manage context window efficiently
5. If a document is too large (truncated=true), use targeted search instead

## Token Management

- Preview: max_tokens=2000 (quick overview)
- Full read: max_tokens=50000 (small documents)
- Search: use rga_search_content for large documents
```

## Skill 設定

OpenCode 支援 Skill 檔案 (`SKILL.md`)。在 `.opencode/skills/` 建立：

### `.opencode/skills/rga-document-search.md`

```markdown
---
name: rga-document-search
---

# Document Search Skill

## Available Tools

- `rga_upload_file(filename, content_base64)` → upload a file, get file_id
- `rga_extract_text(file_id, max_tokens?, enable_ocr?, response_format?)` → extract text
- `rga_search_content(pattern, file_id?, search_path?, case_insensitive?, ...)` → regex search
- `rga_list_supported_formats()` → list supported formats

## Quick Patterns

Search all mounted documents:
```
rga_search_content(pattern="keyword")
```

Search in subdirectory:
```
rga_search_content(pattern="contract", search_path="legal/")
```

Extract text from a specific file:
```
rga_extract_text(file_id="reports/quarterly.pdf", max_tokens=50000)
```

Search with OCR:
```
rga_search_content(pattern="invoice", enable_ocr=true)
```
```

## 使用範例

啟動 OpenCode 後，在對話中直接使用：

### 搜尋 PDF 中的關鍵字

```
> 在 documents 目錄下的所有 PDF 中搜尋 "合約條款"
```

Agent 會自動呼叫：
```
rga_search_content(pattern="合約條款", search_path=".", case_insensitive=true)
```

### 提取文件全文

```
> 提取 reports/quarterly.pdf 的全文內容
```

Agent 會呼叫：
```
rga_extract_text(file_id="reports/quarterly.pdf", max_tokens=50000)
```

### 在 ZIP 壓縮檔中搜尋

```
> 在 backup.zip 中找所有包含 API key 的內容
```

### 搜尋 Email 地址

```
> 在所有文件中搜尋 email 地址
```

Agent 使用正則：
```
rga_search_content(pattern="[\\w.+-]+@[\\w-]+\\.[\\w.]+", case_insensitive=true)
```

## 驗證與除錯

### 確認 MCP 伺服器狀態

```bash
# 列出所有已設定的 MCP 伺服器
opencode mcp list
```

### 測試 Docker 映像

```bash
# 直接測試 rga 是否正常
docker run --rm rga-mcp-server rga --version

# 測試搜尋功能
docker run --rm -v ./documents:/data/documents:ro \
  rga-mcp-server rga "test" /data/documents/
```

### 查看容器日誌

```bash
docker compose logs -f rga-mcp-server
```

### 常見問題

| 問題 | 原因 | 解決方式 |
|------|------|----------|
| MCP server 連線失敗 | Docker 未啟動 | `docker compose up -d` |
| 找不到文件 | documents 未掛載 | 確認 volume mount 路徑正確 |
| OCR 無結果 | 未啟用 OCR | 傳入 `enable_ocr=true` |
| 搜尋超時 | 目錄過大 | 用 `search_path` 縮小範圍 |
| 工具未出現 | MCP 設定錯誤 | `opencode mcp list` 檢查 |

## 進階設定

### 環境變數控制

在 `opencode.json` 中使用環境變數：

```jsonc
{
  "mcp": {
    "rga": {
      "type": "local",
      "command": [
        "docker", "run", "--rm", "-i",
        "-v", "{env:RGA_DOCUMENTS_DIR}:/data/documents:ro",
        "rga-mcp-server"
      ],
      "environment": {
        "MAX_OUTPUT_TOKENS": "{env:RGA_MAX_TOKENS}",
        "ENABLE_OCR": "{env:RGA_ENABLE_OCR}"
      }
    }
  }
}
```

### 多目錄掛載

掛載多個文件資料夾：

```jsonc
{
  "mcp": {
    "rga": {
      "type": "local",
      "command": [
        "docker", "run", "--rm", "-i",
        "-v", "./documents:/data/documents/local:ro",
        "-v", "/shared/team-docs:/data/documents/team:ro",
        "-v", "/archive:/data/documents/archive:ro",
        "rga-mcp-server"
      ]
    }
  }
}
```

搜尋時指定子路徑：
```
rga_search_content(pattern="keyword", search_path="team/")
rga_search_content(pattern="keyword", search_path="archive/")
```

### 資源限制

```jsonc
{
  "mcp": {
    "rga": {
      "type": "local",
      "command": [
        "docker", "run", "--rm", "-i",
        "--memory=2g", "--cpus=2",
        "-v", "./documents:/data/documents:ro",
        "rga-mcp-server"
      ],
      "timeout": 120000
    }
  }
}
```
