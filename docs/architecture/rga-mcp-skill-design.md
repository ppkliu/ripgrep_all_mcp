# ripgrep-all (rga) MCP Server + Skill 完整設計方案

## 一、ripgrep-all 輸入與輸出分析

### 1.1 核心架構

ripgrep-all (rga) 是 ripgrep 的增強版，透過 **adapter 機制** 將各種二進位檔案轉為純文字後再進行正則搜尋。

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐
│  輸入檔案    │────▶│ rga-preproc  │────▶│  ripgrep    │────▶│ 搜尋結果  │
│ (任意格式)   │     │ (adapter匹配) │     │  (正則匹配)  │     │ (stdout)  │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────┘
```

### 1.2 輸入 (Input)

| 類別 | 說明 |
|------|------|
| **搜尋模式** | 正則表達式 (regex pattern) |
| **目標路徑** | 檔案或目錄路徑，支援遞迴搜尋 |
| **支援檔案格式** | PDF, DOCX, ODT, EPUB, FB2, IPYNB, HTML, SQLite, ZIP, TAR.GZ, BZ2, XZ, ZST, MKV/MP4 (字幕), JPG/PNG (OCR, 預設關閉) |

**關鍵命令模式：**

```bash
# 基本搜尋
rga "pattern" /path/to/files/

# 純文字提取 (預處理模式 - MCP 最重要的用法)
rga-preproc /path/to/file.pdf    # 輸出純文字到 stdout

# 進階搜尋
rga --rga-adapters=+pdfpages,tesseract "pattern" /path/  # 啟用 OCR
rga --json "pattern" /path/       # JSON 格式輸出
rga --rga-accurate "pattern" /path/  # 用 MIME type 而非副檔名匹配
```

### 1.3 輸出 (Output)

| 輸出模式 | 格式 | 說明 |
|----------|------|------|
| **預設** | `檔名:行號:匹配內容` | 類似 grep，逐行匹配結果 |
| **JSON** | `--json` | 結構化 JSON，每行一個 JSON 物件 |
| **rga-preproc** | 純文字 stdout | 直接提取檔案全文，**最適合 MCP 使用** |
| **files-with-matches** | `--files-with-matches` | 僅列出匹配的檔案名 |

**rga-preproc 輸出範例：**

```
# PDF → 純文字
Page 1: Hello from a PDF!

# DOCX → 純文字 (via pandoc)
Hello from a MS Office document!

# SQLite → 純文字
tbl: greeting='hello', from='sqlite database!'

# MKV → 字幕文字
metadata: chapters.chapter.0.tags.title="Chapter 1: Hello"
00:08.398 --> 00:11.758: Hello from a movie!
```

### 1.4 內建 Adapters

| Adapter | 方式 | 支援副檔名 |
|---------|------|-----------|
| **poppler** | pdftotext 外部命令 | .pdf |
| **pandoc** | pandoc 外部命令 | .epub, .odt, .docx, .fb2, .ipynb, .html, .htm |
| **sqlite** | Rust 原生 | .db, .sqlite, .sqlite3 |
| **zip** | Rust 原生 (串流) | .zip |
| **tar** | Rust 原生 (串流) | .tar, .tgz, .tbz2 等 |
| **decompress** | Rust 原生 | .gz, .bz2, .xz, .zst |
| **ffmpeg** | ffmpeg 外部命令 | .mkv, .mp4, .avi 等 |
| **pdfpages** | 預設關閉 | .pdf → 圖片 |
| **tesseract** | 預設關閉 (OCR) | .jpg, .png |

---

## 二、系統整體架構

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Agent / OpenCode                              │
│  1. 上傳檔案 → upload_file tool                                       │
│  2. 提取文字 → extract_text tool                                      │
│  3. 搜尋內容 → search_content tool                                    │
│  4. 接收結果 (含 token 統計)                                          │
└─────────────┬────────────────────────────────────────────────────────┘
              │ MCP Protocol (stdio / streamable HTTP)
              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    rga-mcp-server (容器內)                            │
│                                                                      │
│  ┌───────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────┐ │
│  │ upload_   │  │ extract_     │  │ search_    │  │ list_        │ │
│  │ file      │  │ text         │  │ content    │  │ supported_   │ │
│  │           │  │              │  │            │  │ formats      │ │
│  └─────┬─────┘  └──────┬───────┘  └─────┬──────┘  └──────────────┘ │
│        │               │                │                           │
│        ▼               ▼                ▼                           │
│  ┌─────────────────────────────────────────────┐                    │
│  │           /data/uploads/ (Volume)           │                    │
│  │  存放上傳的檔案，rga / rga-preproc 處理      │                    │
│  └─────────────────────────────────────────────┘                    │
│        │               │                │                           │
│        ▼               ▼                ▼                           │
│  ┌─────────────────────────────────────────────┐                    │
│  │     rga / rga-preproc + adapters (依賴)      │                    │
│  │     poppler-utils, pandoc, ffmpeg, tesseract │                    │
│  └─────────────────────────────────────────────┘                    │
│                                                                      │
│  Token 計算: tiktoken / cl100k_base 估算回傳內容                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 三、Dockerfile

```dockerfile
# ============================================================
# rga-mcp-server Dockerfile
# 包含 ripgrep-all 及所有 adapter 依賴
# ============================================================
FROM node:20-slim AS base

# 安裝系統依賴 (所有 rga adapter 需要的外部工具)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # rga 本體
    ripgrep \
    # PDF adapter
    poppler-utils \
    # pandoc adapter (docx, epub, odt, html, ipynb)
    pandoc \
    # ffmpeg adapter (mkv, mp4 字幕)
    ffmpeg \
    # OCR adapter (可選，啟用 tesseract)
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-chi-tra \
    tesseract-ocr-chi-sim \
    # 通用工具
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安裝 ripgrep-all
RUN curl -L https://github.com/phiresky/ripgrep-all/releases/latest/download/ripgrep_all-v1.0.0-alpha.5-x86_64-unknown-linux-musl.tar.gz \
    | tar xz --strip-components=1 -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/rga /usr/local/bin/rga-preproc

# 驗證安裝
RUN rga --version && rga-preproc --version

# ============================================================
# MCP Server 應用層
# ============================================================
WORKDIR /app

COPY package.json package-lock.json tsconfig.json ./
RUN npm ci --production=false

COPY src/ ./src/
RUN npm run build

# 建立資料目錄
RUN mkdir -p /data/uploads /data/cache
ENV RGA_CACHE_DIR=/data/cache

# 預設以 stdio 模式啟動 (適配 Claude Code / MCP client)
EXPOSE 3000
ENV MCP_TRANSPORT=stdio
ENV UPLOAD_DIR=/data/uploads
ENV MAX_FILE_SIZE_MB=100
ENV MAX_OUTPUT_TOKENS=100000

CMD ["node", "dist/index.js"]
```

---

## 四、docker-compose.yml

```yaml
version: "3.9"

services:
  rga-mcp-server:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: rga-mcp-server
    restart: unless-stopped

    # --- 環境變數 ---
    environment:
      - MCP_TRANSPORT=streamable-http   # stdio | streamable-http
      - MCP_PORT=3000
      - UPLOAD_DIR=/data/uploads
      - MAX_FILE_SIZE_MB=200
      - MAX_OUTPUT_TOKENS=100000        # 回傳 token 上限
      - RGA_CACHE_DIR=/data/cache
      - ENABLE_OCR=true                 # 啟用 tesseract OCR
      - LOG_LEVEL=info

    # --- 掛載 ---
    volumes:
      - rga-uploads:/data/uploads       # 上傳檔案持久化
      - rga-cache:/data/cache           # rga 快取

    # --- 網路 (streamable HTTP 模式) ---
    ports:
      - "3000:3000"

    # --- 資源限制 ---
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "2.0"
        reservations:
          memory: 512M

volumes:
  rga-uploads:
  rga-cache:
```

**stdio 模式 (適配 OpenCode / 本地 MCP client)：**

```yaml
# docker-compose.stdio.yml
version: "3.9"
services:
  rga-mcp-server:
    build: .
    container_name: rga-mcp-stdio
    environment:
      - MCP_TRANSPORT=stdio
    volumes:
      - rga-uploads:/data/uploads
      - rga-cache:/data/cache
    stdin_open: true
    tty: true

volumes:
  rga-uploads:
  rga-cache:
```

---

## 五、MCP Server 實作 (TypeScript)

### 5.1 package.json

```json
{
  "name": "rga-mcp-server",
  "version": "1.0.0",
  "description": "MCP server for ripgrep-all document search and text extraction",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "tsx watch src/index.ts"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.12.0",
    "express": "^4.21.0",
    "zod": "^3.23.0",
    "tiktoken": "^1.0.18",
    "uuid": "^10.0.0",
    "mime-types": "^2.1.35"
  },
  "devDependencies": {
    "@types/express": "^5.0.0",
    "@types/node": "^22.0.0",
    "@types/uuid": "^10.0.0",
    "@types/mime-types": "^2.1.4",
    "typescript": "^5.6.0",
    "tsx": "^4.19.0"
  }
}
```

### 5.2 src/index.ts — 主入口

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import express from "express";
import { registerTools } from "./tools/index.js";

const server = new McpServer({
  name: "rga-mcp-server",
  version: "1.0.0",
});

// 註冊所有工具
registerTools(server);

// 啟動
const transport = process.env.MCP_TRANSPORT || "stdio";

if (transport === "stdio") {
  const stdioTransport = new StdioServerTransport();
  await server.connect(stdioTransport);
  console.error("[rga-mcp] Running in stdio mode");
} else {
  const app = express();
  const port = parseInt(process.env.MCP_PORT || "3000");

  app.post("/mcp", async (req, res) => {
    const httpTransport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // stateless
    });
    await server.connect(httpTransport);
    await httpTransport.handleRequest(req, res);
  });

  app.listen(port, () => {
    console.error(`[rga-mcp] Streamable HTTP on port ${port}`);
  });
}
```

### 5.3 src/tools/index.ts — 工具註冊

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { uploadFile } from "./upload.js";
import { extractText } from "./extract.js";
import { searchContent } from "./search.js";
import { listFormats } from "./formats.js";

export function registerTools(server: McpServer) {

  // ============================================================
  // Tool 1: rga_upload_file — 上傳檔案
  // ============================================================
  server.registerTool(
    "rga_upload_file",
    {
      title: "Upload File for Processing",
      description:
        "Upload a file (base64-encoded) to the rga server for text extraction or search. " +
        "Supports: PDF, DOCX, EPUB, ODT, ZIP, TAR.GZ, SQLite, MKV/MP4, images (OCR). " +
        "Returns a file_id for subsequent extract/search operations.",
      inputSchema: {
        filename: z.string().describe("Original filename with extension, e.g. 'report.pdf'"),
        content_base64: z.string().describe("File content encoded as base64 string"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async ({ filename, content_base64 }) => {
      return uploadFile(filename, content_base64);
    }
  );

  // ============================================================
  // Tool 2: rga_extract_text — 全文提取 (核心功能)
  // ============================================================
  server.registerTool(
    "rga_extract_text",
    {
      title: "Extract Text from File",
      description:
        "Extract all text content from an uploaded file using rga-preproc. " +
        "Returns extracted plain text with token count estimation. " +
        "Use max_tokens to limit output size for large files. " +
        "Token count uses cl100k_base encoding (GPT-4/Claude compatible).",
      inputSchema: {
        file_id: z.string().describe("File ID returned from rga_upload_file"),
        max_tokens: z
          .number()
          .optional()
          .default(50000)
          .describe("Max tokens to return. Default 50000. Use smaller values for summaries."),
        enable_ocr: z
          .boolean()
          .optional()
          .default(false)
          .describe("Enable OCR for images/scanned PDFs (slower). Default false."),
        response_format: z
          .enum(["json", "markdown"])
          .optional()
          .default("json")
          .describe("Response format: 'json' for structured data, 'markdown' for readable text"),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ file_id, max_tokens, enable_ocr, response_format }) => {
      return extractText(file_id, max_tokens, enable_ocr, response_format);
    }
  );

  // ============================================================
  // Tool 3: rga_search_content — 正則搜尋
  // ============================================================
  server.registerTool(
    "rga_search_content",
    {
      title: "Search Content in Files",
      description:
        "Search for a regex pattern within uploaded files using ripgrep-all. " +
        "Searches across all supported formats including inside archives. " +
        "Returns matching lines with context, plus token count.",
      inputSchema: {
        pattern: z.string().describe("Regex pattern to search for"),
        file_id: z
          .string()
          .optional()
          .describe("Search in specific file. Omit to search all uploaded files."),
        case_insensitive: z.boolean().optional().default(true),
        context_lines: z
          .number()
          .optional()
          .default(2)
          .describe("Number of context lines before/after each match"),
        max_matches: z.number().optional().default(100),
        max_tokens: z.number().optional().default(20000),
        enable_ocr: z.boolean().optional().default(false),
        response_format: z
          .enum(["json", "markdown"])
          .optional()
          .default("json"),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ pattern, file_id, case_insensitive, context_lines, max_matches, max_tokens, enable_ocr, response_format }) => {
      return searchContent(pattern, file_id, case_insensitive, context_lines, max_matches, max_tokens, enable_ocr, response_format);
    }
  );

  // ============================================================
  // Tool 4: rga_list_supported_formats — 列出支援格式
  // ============================================================
  server.registerTool(
    "rga_list_supported_formats",
    {
      title: "List Supported File Formats",
      description: "List all file formats supported by this rga instance and their adapter status.",
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      return listFormats();
    }
  );
}
```

### 5.4 src/tools/extract.ts — 文字提取（核心邏輯）

```typescript
import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";
import fs from "fs/promises";
import { countTokens, truncateToTokenLimit } from "../utils/tokens.js";

const execFileAsync = promisify(execFile);
const UPLOAD_DIR = process.env.UPLOAD_DIR || "/data/uploads";

export async function extractText(
  fileId: string,
  maxTokens: number,
  enableOcr: boolean,
  responseFormat: string
) {
  // 查找檔案
  const filePath = path.join(UPLOAD_DIR, fileId);
  try {
    await fs.access(filePath);
  } catch {
    return {
      isError: true,
      content: [{ type: "text" as const, text: `Error: File not found: ${fileId}. Use rga_upload_file first.` }],
    };
  }

  // 取得原始檔名 (從 metadata)
  const metaPath = `${filePath}.meta.json`;
  let originalName = fileId;
  try {
    const meta = JSON.parse(await fs.readFile(metaPath, "utf-8"));
    originalName = meta.originalName;
  } catch {}

  // 建構 rga-preproc 命令
  const args: string[] = [];
  if (enableOcr) {
    args.push("--rga-adapters=+pdfpages,tesseract");
  }
  args.push("--rga-no-cache"); // 容器中每次重新提取
  args.push(filePath);

  try {
    const { stdout, stderr } = await execFileAsync("rga-preproc", args, {
      maxBuffer: 50 * 1024 * 1024, // 50MB
      timeout: 120_000, // 2 分鐘超時
    });

    if (stderr) {
      console.error(`[rga-preproc stderr] ${stderr}`);
    }

    // Token 計算與截斷
    const fullTokenCount = countTokens(stdout);
    const truncatedText = truncateToTokenLimit(stdout, maxTokens);
    const returnedTokenCount = countTokens(truncatedText);
    const wasTruncated = fullTokenCount > returnedTokenCount;

    if (responseFormat === "json") {
      const result = {
        file_id: fileId,
        original_name: originalName,
        extracted_text: truncatedText,
        token_stats: {
          full_document_tokens: fullTokenCount,
          returned_tokens: returnedTokenCount,
          max_tokens_requested: maxTokens,
          truncated: wasTruncated,
          encoding: "cl100k_base",
          note: wasTruncated
            ? `Document was truncated from ${fullTokenCount} to ${returnedTokenCount} tokens. ` +
              `Call again with higher max_tokens or use rga_search_content for targeted retrieval.`
            : "Full document returned.",
        },
      };
      return {
        content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
      };
    } else {
      // Markdown 格式
      const md = [
        `## Extracted Text: ${originalName}`,
        "",
        "### Token Statistics",
        `- **Full document**: ${fullTokenCount.toLocaleString()} tokens`,
        `- **Returned**: ${returnedTokenCount.toLocaleString()} tokens`,
        `- **Truncated**: ${wasTruncated ? "Yes" : "No"}`,
        `- **Encoding**: cl100k_base`,
        "",
        "### Content",
        "```",
        truncatedText,
        "```",
      ].join("\n");

      return {
        content: [{ type: "text" as const, text: md }],
      };
    }
  } catch (error: any) {
    return {
      isError: true,
      content: [{
        type: "text" as const,
        text: `Error extracting text: ${error.message}. ` +
          `Ensure the file format is supported (use rga_list_supported_formats).`,
      }],
    };
  }
}
```

### 5.5 src/tools/search.ts — 搜尋邏輯

```typescript
import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";
import { countTokens, truncateToTokenLimit } from "../utils/tokens.js";

const execFileAsync = promisify(execFile);
const UPLOAD_DIR = process.env.UPLOAD_DIR || "/data/uploads";

export async function searchContent(
  pattern: string,
  fileId: string | undefined,
  caseInsensitive: boolean,
  contextLines: number,
  maxMatches: number,
  maxTokens: number,
  enableOcr: boolean,
  responseFormat: string
) {
  const searchPath = fileId ? path.join(UPLOAD_DIR, fileId) : UPLOAD_DIR;

  const args: string[] = [];

  // JSON 輸出便於解析
  args.push("--json");

  if (caseInsensitive) args.push("-i");
  args.push("-C", String(contextLines));
  args.push("-m", String(maxMatches));

  if (enableOcr) {
    args.push("--rga-adapters=+pdfpages,tesseract");
  }

  args.push("--rga-no-cache");
  args.push(pattern);
  args.push(searchPath);

  try {
    const { stdout } = await execFileAsync("rga", args, {
      maxBuffer: 20 * 1024 * 1024,
      timeout: 120_000,
    });

    // 解析 JSON lines 輸出
    const lines = stdout.trim().split("\n").filter(Boolean);
    const matches: any[] = [];

    for (const line of lines) {
      try {
        const obj = JSON.parse(line);
        if (obj.type === "match") {
          matches.push({
            file: path.relative(UPLOAD_DIR, obj.data.path?.text || ""),
            line_number: obj.data.line_number,
            text: obj.data.lines?.text?.trim(),
            submatches: obj.data.submatches?.map((s: any) => s.match?.text),
          });
        }
      } catch {}
    }

    const resultText = JSON.stringify(matches, null, 2);
    const fullTokens = countTokens(resultText);
    const truncated = truncateToTokenLimit(resultText, maxTokens);
    const returnedTokens = countTokens(truncated);

    const result = {
      pattern,
      total_matches: matches.length,
      search_path: fileId || "all_uploads",
      results: JSON.parse(truncated.endsWith("]") ? truncated : truncated + "]"),
      token_stats: {
        full_result_tokens: fullTokens,
        returned_tokens: returnedTokens,
        max_tokens_requested: maxTokens,
        truncated: fullTokens > returnedTokens,
        encoding: "cl100k_base",
      },
    };

    return {
      content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
    };
  } catch (error: any) {
    // rga exit code 1 = no matches
    if (error.code === 1) {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            pattern,
            total_matches: 0,
            results: [],
            token_stats: { full_result_tokens: 0, returned_tokens: 0, truncated: false },
          }),
        }],
      };
    }
    return {
      isError: true,
      content: [{ type: "text" as const, text: `Search error: ${error.message}` }],
    };
  }
}
```

### 5.6 src/tools/upload.ts — 檔案上傳

```typescript
import { v4 as uuidv4 } from "uuid";
import path from "path";
import fs from "fs/promises";
import { lookup } from "mime-types";
import { countTokens } from "../utils/tokens.js";

const UPLOAD_DIR = process.env.UPLOAD_DIR || "/data/uploads";
const MAX_SIZE = parseInt(process.env.MAX_FILE_SIZE_MB || "100") * 1024 * 1024;

export async function uploadFile(filename: string, contentBase64: string) {
  const buffer = Buffer.from(contentBase64, "base64");

  if (buffer.length > MAX_SIZE) {
    return {
      isError: true,
      content: [{
        type: "text" as const,
        text: `Error: File size ${(buffer.length / 1024 / 1024).toFixed(1)}MB exceeds limit of ${MAX_SIZE / 1024 / 1024}MB.`,
      }],
    };
  }

  const ext = path.extname(filename);
  const fileId = `${uuidv4()}${ext}`;
  const filePath = path.join(UPLOAD_DIR, fileId);

  // 寫入檔案
  await fs.writeFile(filePath, buffer);

  // 寫入 metadata
  const meta = {
    originalName: filename,
    fileId,
    size: buffer.length,
    mimeType: lookup(filename) || "application/octet-stream",
    uploadedAt: new Date().toISOString(),
  };
  await fs.writeFile(`${filePath}.meta.json`, JSON.stringify(meta, null, 2));

  const result = {
    file_id: fileId,
    original_name: filename,
    size_bytes: buffer.length,
    size_human: `${(buffer.length / 1024 / 1024).toFixed(2)} MB`,
    mime_type: meta.mimeType,
    status: "uploaded",
    next_steps: [
      `Use rga_extract_text with file_id="${fileId}" to extract all text content`,
      `Use rga_search_content with file_id="${fileId}" to search within the file`,
    ],
  };

  return {
    content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
  };
}
```

### 5.7 src/utils/tokens.ts — Token 計算

```typescript
import { encoding_for_model } from "tiktoken";

// 使用 cl100k_base (GPT-4 / Claude 相容)
let enc: ReturnType<typeof encoding_for_model> | null = null;

function getEncoder() {
  if (!enc) {
    enc = encoding_for_model("gpt-4");
  }
  return enc;
}

/**
 * 計算文字的 token 數量
 * 使用 cl100k_base 編碼，與 GPT-4/Claude 高度相容
 */
export function countTokens(text: string): number {
  if (!text) return 0;
  try {
    return getEncoder().encode(text).length;
  } catch {
    // fallback: 粗略估算 (1 token ≈ 4 字元英文, ≈ 1.5 字元中文)
    return Math.ceil(text.length / 3.5);
  }
}

/**
 * 截斷文字到指定 token 上限
 * 使用二分搜尋高效截斷
 */
export function truncateToTokenLimit(text: string, maxTokens: number): string {
  const currentTokens = countTokens(text);
  if (currentTokens <= maxTokens) return text;

  try {
    const encoder = getEncoder();
    const tokens = encoder.encode(text);
    const truncatedTokens = tokens.slice(0, maxTokens);
    return new TextDecoder().decode(encoder.decode(truncatedTokens));
  } catch {
    // fallback: 字元級截斷
    const ratio = maxTokens / currentTokens;
    return text.slice(0, Math.floor(text.length * ratio));
  }
}
```

---

## 六、Skill 定義 (SKILL.md)

將此 MCP 包裝為 Claude Skill，放置於 `/mnt/skills/user/rga-document-search/SKILL.md`：

```markdown
---
name: rga-document-search
description: >
  Use this skill when the user uploads documents (PDF, DOCX, EPUB, ODT, ZIP,
  TAR.GZ, SQLite, MKV/MP4, images) and wants to extract text, search content,
  or analyze document contents. Triggers on: 'extract text from', 'search in
  document', 'read this PDF', 'find in file', 'what does this document say',
  or any request involving uploaded binary documents. Also use when the user
  mentions 'rga', 'ripgrep-all', or asks to search across multiple file types.
---

# rga Document Search & Extraction Skill

## Overview
This skill uses the rga-mcp-server to extract text from and search within
binary documents. It wraps ripgrep-all (rga) which supports 20+ file formats.

## MCP Server Configuration

### Claude Code (~/.claude/mcp.json)
```json
{
  "mcpServers": {
    "rga": {
      "command": "docker",
      "args": ["exec", "-i", "rga-mcp-server", "node", "dist/index.js"],
      "env": { "MCP_TRANSPORT": "stdio" }
    }
  }
}
```

### Streamable HTTP (remote)
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

## Workflow

### Step 1: Upload the file
```
rga_upload_file(filename="report.pdf", content_base64="<base64>")
→ Returns: { file_id: "abc-123.pdf", size_human: "2.45 MB" }
```

### Step 2: Extract or Search

**Full text extraction:**
```
rga_extract_text(file_id="abc-123.pdf", max_tokens=50000)
→ Returns: { extracted_text: "...", token_stats: { ... } }
```

**Targeted search:**
```
rga_search_content(pattern="revenue|profit", file_id="abc-123.pdf")
→ Returns: { total_matches: 15, results: [...], token_stats: { ... } }
```

### Step 3: Use token_stats for agent decisions

The response always includes `token_stats`:
```json
{
  "token_stats": {
    "full_document_tokens": 125000,
    "returned_tokens": 50000,
    "max_tokens_requested": 50000,
    "truncated": true,
    "encoding": "cl100k_base",
    "note": "Document was truncated. Use search for targeted retrieval."
  }
}
```

**Agent decision patterns:**
- If `truncated: true` → use `rga_search_content` for targeted queries
- If `full_document_tokens < 30000` → safe to extract in one call
- If `full_document_tokens > 100000` → use search or extract in chunks
- Use `returned_tokens` to estimate context window usage

## Supported Formats

| Format | Extensions | Adapter |
|--------|-----------|---------|
| PDF | .pdf | poppler (pdftotext) |
| Office | .docx, .odt | pandoc |
| E-Books | .epub, .fb2 | pandoc |
| Notebooks | .ipynb | pandoc |
| Web | .html, .htm | pandoc |
| Database | .sqlite, .db | native |
| Archives | .zip, .tar.gz, .bz2, .xz | native (streaming) |
| Video | .mkv, .mp4 | ffmpeg (subtitles) |
| Images | .jpg, .png | tesseract (OCR, opt-in) |
```

---

## 七、Agent 工作流程圖

```
Agent 收到使用者上傳檔案
         │
         ▼
  ┌──────────────────┐
  │ rga_upload_file   │  上傳 base64 檔案
  │ → file_id         │
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────────────────────┐
  │ rga_extract_text(max_tokens=5000)│  先小量提取看概要
  │ → token_stats.full_document_tokens│
  └────────┬─────────────────────────┘
           │
     ┌─────┴──────┐
     │ tokens     │
     │ < 30K?     │
     └─────┬──────┘
       Yes │        No
           │         │
           ▼         ▼
  ┌────────────┐  ┌──────────────────────┐
  │ extract_   │  │ rga_search_content    │
  │ text(50K)  │  │ 用正則精準搜尋         │
  │ 全文送入    │  │ 只回傳相關段落         │
  │ context    │  │ + token_stats         │
  └────────────┘  └──────────────────────┘
           │                │
           ▼                ▼
  ┌─────────────────────────────────┐
  │ Agent 根據 token_stats 決策:     │
  │ - 還需要更多內容？ → 再次搜尋    │
  │ - 已足夠 → 生成回應              │
  │ - token 預算管理                 │
  └─────────────────────────────────┘
```

---

## 八、token_stats 設計說明

每個工具回傳都包含 `token_stats`，這是讓 Agent 高效管理 context window 的關鍵：

```typescript
interface TokenStats {
  // 原始完整內容的 token 數
  full_document_tokens: number;

  // 實際回傳的 token 數
  returned_tokens: number;

  // 請求的 max_tokens 上限
  max_tokens_requested: number;

  // 是否被截斷
  truncated: boolean;

  // 使用的 tokenizer 編碼
  encoding: "cl100k_base";

  // 給 agent 的建議
  note: string;
}
```

**Agent 可用的策略：**

1. **預覽模式**：`max_tokens=2000`，快速了解文件結構和大小
2. **全文模式**：`max_tokens=50000`，適合小文件一次讀取
3. **搜尋模式**：用 `rga_search_content` 配合正則，只取需要的段落
4. **預算管理**：`returned_tokens` 讓 agent 知道已用多少 context window

---

## 九、部署指南

### 本地開發 (stdio + Claude Code)

```bash
# 1. 建構映像
docker compose build

# 2. Claude Code MCP 設定
cat >> ~/.claude/mcp.json << 'EOF'
{
  "mcpServers": {
    "rga": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-v", "rga-uploads:/data/uploads", "rga-mcp-server"],
      "env": { "MCP_TRANSPORT": "stdio" }
    }
  }
}
EOF

# 3. 重啟 Claude Code
```

### 遠端部署 (streamable HTTP)

```bash
# 啟動服務
docker compose up -d

# 驗證
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```
