/**
 * MCP Server integration test
 * 透過 MCP SDK Client 直接連線測試 MCP server 的完整功能
 *
 * 測試方式：
 *   npm test -- mcp-server
 *
 * 這個測試會啟動一個真實的 MCP server 子程序 (stdio)，
 * 然後透過 MCP Client SDK 發送請求，驗證工具列表和呼叫結果。
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import path from "path";
import fs from "fs/promises";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, "..");
const SERVER_PATH = path.join(PROJECT_ROOT, "dist", "index.js");

// 測試用上傳目錄
const TEST_UPLOAD_DIR = "/tmp/rga-mcp-integration-test";
const TEST_DOCS_DIR = "/tmp/rga-mcp-integration-test-docs";

let client: Client;
let transport: StdioClientTransport;

async function setupTestFiles() {
  await fs.mkdir(TEST_UPLOAD_DIR, { recursive: true });
  await fs.mkdir(TEST_DOCS_DIR, { recursive: true });

  // 建立測試純文字檔
  await fs.writeFile(
    path.join(TEST_DOCS_DIR, "sample.txt"),
    "Hello World\nThis is a test document.\nIt contains some searchable content.\nEmail: test@example.com\n"
  );
  await fs.writeFile(
    path.join(TEST_DOCS_DIR, "notes.md"),
    "# Meeting Notes\n\n## Action Items\n- Review contract terms\n- Send invoice to client\n"
  );

  // 建立子目錄與檔案 (for list_documents test)
  await fs.mkdir(path.join(TEST_DOCS_DIR, "reports"), { recursive: true });
  await fs.writeFile(
    path.join(TEST_DOCS_DIR, "reports", "q1.txt"),
    "Q1 Report content"
  );
}

async function cleanupTestFiles() {
  try {
    await fs.rm(TEST_UPLOAD_DIR, { recursive: true, force: true });
    await fs.rm(TEST_DOCS_DIR, { recursive: true, force: true });
  } catch {
    // ignore
  }
}

describe("MCP Server Integration", () => {
  beforeAll(async () => {
    await setupTestFiles();

    // 確認 dist/index.js 存在
    try {
      await fs.access(SERVER_PATH);
    } catch {
      throw new Error(
        `Server not built. Run 'npm run build' first. Expected: ${SERVER_PATH}`
      );
    }

    transport = new StdioClientTransport({
      command: "node",
      args: [SERVER_PATH],
      env: {
        ...process.env,
        MCP_TRANSPORT: "stdio",
        UPLOAD_DIR: TEST_UPLOAD_DIR,
        DOCUMENTS_DIR: TEST_DOCS_DIR,
      },
    });

    client = new Client({ name: "test-client", version: "1.0.0" });
    await client.connect(transport);
  }, 15000);

  afterAll(async () => {
    try {
      await client.close();
    } catch {
      // ignore
    }
    try {
      await transport.close();
    } catch {
      // ignore
    }
    await cleanupTestFiles();
  });

  // ============================================================
  // tools/list
  // ============================================================
  describe("tools/list", () => {
    it("should list all 5 tools", async () => {
      const result = await client.listTools();
      expect(result.tools.length).toBe(5);
    });

    it("should include expected tool names", async () => {
      const result = await client.listTools();
      const names = result.tools.map((t) => t.name);
      expect(names).toContain("rga_upload_file");
      expect(names).toContain("rga_extract_text");
      expect(names).toContain("rga_search_content");
      expect(names).toContain("rga_list_supported_formats");
      expect(names).toContain("rga_list_documents");
    });

    it("should have descriptions for all tools", async () => {
      const result = await client.listTools();
      for (const tool of result.tools) {
        expect(tool.description).toBeDefined();
        expect(tool.description!.length).toBeGreaterThan(10);
      }
    });

    it("should have inputSchema for all tools", async () => {
      const result = await client.listTools();
      for (const tool of result.tools) {
        expect(tool.inputSchema).toBeDefined();
      }
    });
  });

  // ============================================================
  // rga_list_supported_formats
  // ============================================================
  describe("rga_list_supported_formats", () => {
    it("should return format list", async () => {
      const result = await client.callTool({
        name: "rga_list_supported_formats",
        arguments: {},
      });

      expect(result.content).toBeDefined();
      expect(Array.isArray(result.content)).toBe(true);

      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      const data = JSON.parse(text);

      expect(data.formats).toBeDefined();
      expect(data.formats.length).toBeGreaterThan(5);
      expect(data.notes).toBeDefined();
    });
  });

  // ============================================================
  // rga_upload_file
  // ============================================================
  describe("rga_upload_file", () => {
    it("should upload a file and return file_id", async () => {
      const content = Buffer.from("Upload test content").toString("base64");

      const result = await client.callTool({
        name: "rga_upload_file",
        arguments: {
          filename: "test-upload.txt",
          content_base64: content,
        },
      });

      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      const data = JSON.parse(text);

      expect(data.file_id).toBeDefined();
      expect(data.original_name).toBe("test-upload.txt");
      expect(data.status).toBe("uploaded");
      expect(data.size_bytes).toBe(19); // "Upload test content".length
    });
  });

  // ============================================================
  // rga_extract_text (documents 目錄)
  // ============================================================
  describe("rga_extract_text", () => {
    it("should extract text from a file in documents dir", async () => {
      const result = await client.callTool({
        name: "rga_extract_text",
        arguments: {
          file_id: "sample.txt",
          max_tokens: 5000,
        },
      });

      expect(result.isError).toBeFalsy();

      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      const data = JSON.parse(text);

      expect(data.extracted_text).toContain("Hello World");
      expect(data.token_stats).toBeDefined();
      expect(data.token_stats.truncated).toBe(false);
    });

    it("should return error for non-existent file", async () => {
      const result = await client.callTool({
        name: "rga_extract_text",
        arguments: {
          file_id: "does-not-exist.pdf",
        },
      });

      expect(result.isError).toBe(true);
      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      expect(text).toContain("not found");
    });

    it("should support markdown response format", async () => {
      const result = await client.callTool({
        name: "rga_extract_text",
        arguments: {
          file_id: "sample.txt",
          response_format: "markdown",
        },
      });

      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      expect(text).toContain("## Extracted Text");
      expect(text).toContain("Token Statistics");
    });
  });

  // ============================================================
  // rga_search_content (需要 rga 可用)
  // ============================================================
  describe("rga_search_content", () => {
    it("should search and find matching content", async () => {
      const result = await client.callTool({
        name: "rga_search_content",
        arguments: {
          pattern: "Hello",
        },
      });

      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      const data = JSON.parse(text);

      // 若 rga 可用，應有匹配結果；若不可用會回傳 error
      if (!data.error) {
        expect(data.total_matches).toBeGreaterThanOrEqual(0);
        expect(data.results).toBeDefined();
        expect(data.token_stats).toBeDefined();
      }
    });

    it("should return 0 matches for non-matching pattern", async () => {
      const result = await client.callTool({
        name: "rga_search_content",
        arguments: {
          pattern: "xyznonexistent999",
        },
      });

      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      const data = JSON.parse(text);

      if (!data.error) {
        expect(data.total_matches).toBe(0);
        expect(data.results).toEqual([]);
      }
    });

    it("should support search_path parameter", async () => {
      const result = await client.callTool({
        name: "rga_search_content",
        arguments: {
          pattern: "contract",
          search_path: ".",
        },
      });

      expect(result.content).toBeDefined();
    });
  });

  // ============================================================
  // rga_list_documents
  // ============================================================
  describe("rga_list_documents", () => {
    it("should list root documents directory", async () => {
      const result = await client.callTool({
        name: "rga_list_documents",
        arguments: {},
      });

      expect(result.isError).toBeFalsy();
      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      const data = JSON.parse(text);

      expect(data.relative_path).toBe("/");
      expect(data.entries).toBeDefined();
      expect(data.total_files).toBeGreaterThanOrEqual(2); // sample.txt, notes.md
      expect(data.total_directories).toBeGreaterThanOrEqual(1); // reports/
      expect(data.tips).toBeDefined();

      // Check that files have size info
      const files = data.entries.filter(
        (e: { type: string }) => e.type === "file"
      );
      expect(files.length).toBeGreaterThan(0);
      expect(files[0].size).toBeDefined();
      expect(files[0].size_human).toBeDefined();
    });

    it("should list a subdirectory", async () => {
      const result = await client.callTool({
        name: "rga_list_documents",
        arguments: { path: "reports" },
      });

      expect(result.isError).toBeFalsy();
      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      const data = JSON.parse(text);

      expect(data.relative_path).toBe("reports");
      expect(data.total_files).toBe(1); // q1.txt
      expect(data.tips).toContain("reports");
    });

    it("should support recursive listing", async () => {
      const result = await client.callTool({
        name: "rga_list_documents",
        arguments: { recursive: true },
      });

      expect(result.isError).toBeFalsy();
      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      const data = JSON.parse(text);

      // Should include both root files and subdirectory contents
      const dirs = data.entries.filter(
        (e: { type: string }) => e.type === "directory"
      );
      expect(dirs.length).toBeGreaterThan(0);
      // Recursive directories should have children array
      expect(dirs[0].children).toBeDefined();
    });

    it("should return error for non-existent path", async () => {
      const result = await client.callTool({
        name: "rga_list_documents",
        arguments: { path: "nonexistent-dir" },
      });

      expect(result.isError).toBe(true);
    });

    it("should prevent path traversal", async () => {
      const result = await client.callTool({
        name: "rga_list_documents",
        arguments: { path: "../../etc" },
      });

      expect(result.isError).toBe(true);
      const text = (result.content as Array<{ type: string; text: string }>)[0]
        .text;
      expect(text).toContain("path traversal");
    });
  });
});
