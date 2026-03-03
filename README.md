# Ripgrep-all MCP Server

一个功能强大的 MCP (Model Context Protocol) 服务器，集成了 ripgrep-all (rga) 搜索引擎，使 AI Agent 能够搜索 PDF、DOCX、Excel、PowerPoint、E-Book、ZIP 等多种文件格式。

## 🎯 特性

- 📄 **多格式支持**: PDF、DOCX、XLSX、PPTX、TXT、MD、JSON、XML、ZIP、TAR、E-Books 等
- 🔍 **强大搜索**: 支持正则表达式、大小写敏感、上下文展示
- ⚡ **高性能**: 继承 ripgrep 的高效搜索引擎
- 🔐 **隐私保护**: 所有搜索在本地执行，不上传数据到云端
- 🤖 **Agent 友好**: 完整的 MCP 支持，与 Claude、Agno 等 Agent 框架集成
- 📦 **模块化设计**: 易于扩展和集成

## 📋 前置要求

1. **Node.js** >= 18.0.0
2. **ripgrep-all (rga)** - 已安装并在 PATH 中

### 安装 ripgrep-all

#### macOS
```bash
brew install ripgrep-all
```

#### Ubuntu/Debian
```bash
# 添加 PPA
sudo add-apt-repository ppa:phiresky/ripgrep-all
sudo apt-get update
sudo apt-get install ripgrep-all
```

#### 从源代码编译
```bash
cargo install ripgrep-all
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd ripgrep_all_mcp
npm install
```

### 2. 编译 TypeScript

```bash
npm run build
```

### 3. 运行服务器

```bash
npm start
```

或开发模式：
```bash
npm run dev
```

## 📚 文档

详细文档位于 [docs/](docs/) 目录：

| 分類 | 文档 | 描述 |
|------|------|------|
| 入門導覽 | [00_START_HERE.md](docs/getting-started/00_START_HERE.md) | 项目入口，快速导航 |
| 入門導覽 | [QUICK_START.md](docs/getting-started/QUICK_START.md) | 快速开始指南 |
| 入門導覽 | [INDEX.md](docs/getting-started/INDEX.md) | 文档索引 |
| 技術參考 | [API.md](docs/technical-reference/API.md) | API 参考文档 |
| 技術參考 | [FILES.md](docs/technical-reference/FILES.md) | 文件说明 |
| 技術參考 | [PROJECT_SUMMARY.md](docs/technical-reference/PROJECT_SUMMARY.md) | 项目总结 |
| 部署運維 | [docker_usage_guide.md](docs/docker_usage_guide.md) | **Docker 使用指南** (工具詳解、curl 測試、Token 策略) |
| 部署運維 | [DEPLOYMENT.md](docs/deployment/DEPLOYMENT.md) | 部署指南 |
| 框架整合 | [AGNO_INTEGRATION.md](docs/integration/AGNO_INTEGRATION.md) | Agno Agent 整合指南 |
| 框架整合 | [OPENCODE_INTEGRATION.md](docs/integration/OPENCODE_INTEGRATION.md) | **OpenCode 整合指南** (MCP 設定、Agent、Skill) |
| 系統設計 | [rga-mcp-skill-design.md](docs/architecture/rga-mcp-skill-design.md) | 系統設計方案 (架構、Dockerfile、工具實作) |
| 系統設計 | [COMPLETION_REPORT.md](docs/architecture/COMPLETION_REPORT.md) | 完成报告 |

## 🔧 项目结构

```
ripgrep_all_mcp/
├── src/
│   ├── index.ts                 # MCP 入口 (stdio + HTTP 雙模式)
│   ├── types/
│   │   └── index.ts             # TypeScript 類型定義
│   ├── tools/
│   │   ├── register.ts          # McpServer 工具註冊 (zod schema)
│   │   ├── upload.ts            # rga_upload_file 工具
│   │   ├── extract.ts           # rga_extract_text 工具
│   │   ├── search.ts            # rga_search_content 工具
│   │   ├── formats.ts           # rga_list_supported_formats 工具
│   │   ├── registry.ts          # 舊版工具定義 (相容)
│   │   └── handler.ts           # 舊版工具處理器 (相容)
│   ├── utils/
│   │   ├── rga-executor.ts      # RGA 執行引擎
│   │   └── tokens.ts            # Token 計算工具
│   └── integrations/
│       └── agno-agent.ts        # Agno Agent 集成
├── docs/                        # 專案文檔
│   ├── docker_usage_guide.md           # 完整使用指南
│   ├── OPENCODE_INTEGRATION.md  # OpenCode 整合指南
│   └── ...                      # 其他文檔
├── testcase/                    # 自動測試
├── documents/                   # 外掛文件目錄 (掛載到 Docker)
├── Dockerfile                   # 完整 rga + adapter 環境
├── docker-compose.yaml          # stdio 模式部署
├── docker-compose.http.yaml     # HTTP 模式部署
├── package.json
├── tsconfig.json
└── README.md
```

## 📚 可用工具 (v2)

### 1. `rga_upload_file` — 上傳檔案

上傳 base64 編碼的檔案到伺服器，回傳 `file_id` 供後續使用。

### 2. `rga_extract_text` — 全文提取

使用 `rga-preproc` 從檔案提取純文字，支援 token 統計與截斷控制。
可直接讀取掛載的 `/data/documents` 目錄中的檔案。

### 3. `rga_search_content` — 正則搜尋

在文件中使用正則表達式搜尋，支援跨格式搜尋（包含壓縮檔內部）。

### 4. `rga_list_supported_formats` — 列出支援格式

列出所有支援的檔案格式及 adapter 狀態。

> 完整工具參數與回傳格式請參閱 [docs/docker_usage_guide.md](docs/docker_usage_guide.md)

## 🐳 Docker 一鍵部署

```bash
# 1. 放入你的文件
mkdir -p documents
cp ~/my-files/*.pdf ./documents/

# 2. 建構並啟動
docker compose up -d
```

## 🤖 MCP Client 設定

### Claude Code (~/.claude/mcp.json)

```json
{
  "mcpServers": {
    "rga": {
      "command": "docker",
      "args": ["run", "--rm", "-i",
               "-v", "./documents:/data/documents:ro",
               "-v", "rga-uploads:/data/uploads",
               "rga-mcp-server"]
    }
  }
}
```

### OpenCode (opencode.json)

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "rga": {
      "type": "local",
      "command": ["docker", "run", "--rm", "-i",
                  "-v", "./documents:/data/documents:ro",
                  "rga-mcp-server"]
    }
  }
}
```

> 更多 Client 設定（Claude Desktop, Cursor, HTTP 模式等）請參閱 [docs/docker_usage_guide.md](docs/docker_usage_guide.md)
> OpenCode 進階設定請參閱 [docs/integration/OPENCODE_INTEGRATION.md](docs/integration/OPENCODE_INTEGRATION.md)

## 💡 使用範例

```
# 搜尋 PDF 中的關鍵字
rga_search_content(pattern="合約條款", search_path="legal/")

# 提取文件全文
rga_extract_text(file_id="reports/quarterly.pdf", max_tokens=50000)

# 正則搜尋 Email 地址
rga_search_content(pattern="[\\w.+-]+@[\\w-]+\\.[\\w.]+")

# 在 ZIP 壓縮檔中搜尋
rga_search_content(pattern="api.key", file_id="backup.zip")

# 啟用 OCR 搜尋掃描文件
rga_extract_text(file_id="scanned.pdf", enable_ocr=true)
```

## 🛠️ 開發

```bash
npm install         # 安裝依賴
npm run build       # 編譯 TypeScript
npm test            # 執行測試 (55 tests)
npm run dev         # 開發模式
```

## 📄 License

MIT

## 📞 參考資源

- ripgrep-all: https://github.com/phiresky/ripgrep-all
- MCP 規範: https://modelcontextprotocol.io/
- OpenCode: https://opencode.ai
