# MCP Client 設定範例

本目錄提供各 MCP Client 的設定範例，**預設使用 Docker HTTP 模式**連線至 rga-mcp-server。

## 前置步驟

### 1. 建構並啟動 Docker HTTP Server

```bash
# 建構映像
docker compose -f docker-compose.http.yaml build

# 放入文件
mkdir -p documents
cp ~/my-files/*.pdf ./documents/

# 啟動
docker compose -f docker-compose.http.yaml up -d

# 驗證
curl http://localhost:30003/health
# → {"status":"ok","server":"rga-mcp-server","version":"2.0.0"}
```

### 2. 選擇設定檔，複製到對應位置

---

## 設定檔一覽

| 檔案 | 適用 Client | 設定檔位置 |
|------|------------|-----------|
| `claude-desktop-config.json` | Claude Desktop | macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`<br>Windows: `%APPDATA%\Claude\claude_desktop_config.json` |
| `claude-code-mcp.json` | Claude Code (CLI) | `~/.claude/mcp.json` |
| `opencode.json` | OpenCode | 專案根目錄 `opencode.json` |
| `test-mcp-http.sh` | curl / 手動測試 | 直接執行 |

---

## Claude Desktop

將 `claude-desktop-config.json` 的內容合併到設定檔：

```json
{
  "mcpServers": {
    "rga": {
      "type": "url",
      "url": "http://localhost:30003/mcp"
    }
  }
}
```

設定完成後重啟 Claude Desktop。

---

## Claude Code (CLI)

將 `claude-code-mcp.json` 的內容合併到 `~/.claude/mcp.json`：

```json
{
  "mcpServers": {
    "rga": {
      "type": "url",
      "url": "http://localhost:30003/mcp"
    }
  }
}
```

---

## OpenCode

將 `opencode.json` 放到專案根目錄：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "rga": {
      "type": "remote",
      "url": "http://localhost:30003/mcp"
    }
  }
}
```

---

## Cursor / Windsurf

在 MCP 設定介面中新增 server：

- **Type**: URL / HTTP
- **URL**: `http://localhost:30003/mcp`

---

## 手動測試 (curl)

```bash
# 執行測試腳本
./examples/test-mcp-http.sh

# 指定自訂 URL
./examples/test-mcp-http.sh http://your-host:30003/mcp
```

測試腳本會依序執行：
1. Health Check
2. Initialize (取得 session ID)
3. List Tools
4. List Supported Formats
5. List Documents

---

## 自訂 MCP Server URL

如果 Docker 部署在遠端主機或使用不同 port，將所有設定中的 URL 替換為：

```
http://<host>:<port>/mcp
```

例如：
```
http://192.168.1.100:30003/mcp
```

---

## Docker 管理

```bash
# 啟動
docker compose -f docker-compose.http.yaml up -d

# 查看日誌
docker compose -f docker-compose.http.yaml logs -f

# 停止
docker compose -f docker-compose.http.yaml down

# 重新建構 (更新後)
docker compose -f docker-compose.http.yaml up -d --build
```

## 掛載自訂文件目錄

編輯 `docker-compose.http.yaml` 中的 volumes：

```yaml
volumes:
  - /path/to/your/docs:/data/documents:ro    # 唯讀掛載
  - rga-uploads:/data/uploads
  - rga-cache:/data/cache
```

掛載後重啟容器即可搜尋新目錄中的文件。
