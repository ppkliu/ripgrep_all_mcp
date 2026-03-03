# Agno Agent 整合指南

使用 [Agno](https://github.com/agno-agi/agno) 框架透過 MCP 整合 ripgrep-all MCP server。

## 1. 安裝依賴

```bash
pip install agno anthropic
```

## 2. 建構 MCP Server

```bash
cd /path/to/ripgrep_all_mcp
npm install && npm run build
```

或使用 Docker：

```bash
docker compose build
```

## 3. 基本連線 (stdio 模式)

```python
import asyncio
from agno.tools.mcp import MCPTools
from agno.agent import Agent
from agno.models.anthropic import Claude

async def main():
    mcp_tools = MCPTools(
        command="node /path/to/ripgrep_all_mcp/dist/index.js",
        env={
            "MCP_TRANSPORT": "stdio",
            "DOCUMENTS_DIR": "/path/to/your/documents",
            "UPLOAD_DIR": "/tmp/rga-uploads",
        },
    )

    async with mcp_tools:
        agent = Agent(
            name="Document Search Agent",
            model=Claude(id="claude-sonnet-4-5"),
            tools=[mcp_tools],
            instructions=[
                "You have access to rga MCP tools for document search and text extraction.",
                "Use rga_list_supported_formats to check available formats.",
                "Use rga_search_content to search across documents.",
                "Use rga_extract_text to extract full text from a file.",
                "Use rga_upload_file to upload new files for processing.",
            ],
            markdown=True,
        )

        await agent.aprint_response(
            "Search for 'invoice' in my documents",
            stream=True,
        )

asyncio.run(main())
```

## 4. Docker 模式

```python
mcp_tools = MCPTools(
    command="docker compose -f /path/to/docker-compose.yaml run --rm rga-mcp",
    env={"MCP_TRANSPORT": "stdio"},
)
```

## 5. 直接工具呼叫 (不需要 LLM)

不需要 API key 即可直接呼叫工具，適合測試與自動化：

```python
import asyncio
import json
import base64
from agno.tools.mcp import MCPTools

async def main():
    mcp_tools = MCPTools(
        command="node /path/to/ripgrep_all_mcp/dist/index.js",
        env={
            "MCP_TRANSPORT": "stdio",
            "DOCUMENTS_DIR": "/path/to/documents",
        },
    )

    async with mcp_tools:
        # 列出支援格式
        result = await mcp_tools.call("rga_list_supported_formats", {})
        print(json.loads(result))

        # 提取文字
        result = await mcp_tools.call("rga_extract_text", {
            "file_id": "report.pdf",
            "max_tokens": 5000,
        })
        print(json.loads(result))

        # 搜尋內容
        result = await mcp_tools.call("rga_search_content", {
            "pattern": "revenue",
            "case_insensitive": True,
        })
        print(json.loads(result))

        # 上傳檔案
        content_b64 = base64.b64encode(b"Hello World").decode()
        result = await mcp_tools.call("rga_upload_file", {
            "filename": "test.txt",
            "content_base64": content_b64,
        })
        print(json.loads(result))

asyncio.run(main())
```

## 6. 可用工具

| 工具名稱 | 說明 |
|---------|------|
| `rga_upload_file` | 上傳檔案 (base64)，回傳 file_id |
| `rga_extract_text` | 從檔案提取純文字，支援 token 限制與 OCR |
| `rga_search_content` | 使用 regex 搜尋文件內容 |
| `rga_list_supported_formats` | 列出所有支援的檔案格式 |

## 7. 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `MCP_TRANSPORT` | 傳輸模式 (`stdio` / `http`) | `stdio` |
| `DOCUMENTS_DIR` | 文件目錄路徑 | `/data/documents` |
| `UPLOAD_DIR` | 上傳目錄路徑 | `/data/uploads` |
| `MAX_FILE_SIZE_MB` | 最大上傳大小 (MB) | `100` |

## 8. 測試

執行整合測試：

```bash
# 安裝依賴
pip install agno anthropic

# 僅測試 MCP 連線 (不需要 API key)
python testcase/agno/test_agno_rga.py --connection-only

# 完整測試 (需要 ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY="your-key"
python testcase/agno/test_agno_rga.py
```
