# rga-mcp-server 文件指南

## 🐳 快速開始 (推薦)

**預設使用 Docker 安裝與啟動，無需額外安裝 rga 或任何系統依賴。**

👉 **[Docker 完整使用指南](docker_usage_guide.md)** — 一鍵部署、工具詳解、curl 測試、MCP Client 設定

### 三步啟動

```bash
# 1. 放入你的文件
mkdir -p documents && cp ~/my-files/*.pdf ./documents/

# 2. 建構並啟動 (stdio 模式，供 Claude Code / OpenCode 等 MCP Client 使用)
docker compose up -d

# 3. 或啟動 HTTP 模式 (支援 curl 測試 / 遠端連線 / Agent 框架整合)
docker compose -f docker-compose.http.yaml up -d
curl http://localhost:30003/health   # → {"status":"ok"}
```

### 支援的文件格式

PDF, DOCX, XLSX, PPTX, EPUB, ODT, ZIP, TAR.GZ, SQLite, MKV/MP4 (字幕), 圖片 OCR, 以及所有純文字格式。

---

## 📚 文件分類導覽

| 分類 | 目錄 | 內容 |
|------|------|------|
| **入門導覽** | [getting-started/](getting-started/) | 專案入口、5 分鐘快速上手、文件索引 |
| **技術參考** | [technical-reference/](technical-reference/) | API 完整文件、檔案說明、專案架構 |
| **部署設定** | [deployment/](deployment/) | 本地開發、Claude Desktop / Cursor 設定 |
| **框架整合** | [integration/](integration/) | Agno Agent、OpenCode 整合指南 |
| **系統設計** | [architecture/](architecture/) | 技術設計方案、專案完成報告 |

### 建議閱讀順序

1. **[Docker 使用指南](docker_usage_guide.md)** — 安裝、啟動、測試
2. [getting-started/QUICK_START.md](getting-started/QUICK_START.md) — 5 分鐘快速上手
3. [technical-reference/API.md](technical-reference/API.md) — 工具參數與回傳格式
4. [integration/AGNO_INTEGRATION.md](integration/AGNO_INTEGRATION.md) — Agent 框架整合
