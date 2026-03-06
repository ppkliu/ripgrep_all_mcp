/**
 * Tool registration for rga-mcp-server
 * 使用 McpServer.registerTool API + zod schema
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { uploadFile } from "./upload.js";
import { extractText } from "./extract.js";
import { searchContent } from "./search.js";
import { listFormats } from "./formats.js";
import { listDocuments } from "./list-documents.js";

export function registerTools(server: McpServer) {
  // ============================================================
  // Tool 1: rga_upload_file — 上傳檔案
  // ============================================================
  server.tool(
    "rga_upload_file",
    "Upload a file (base64-encoded) for text extraction or search. " +
      "Supports: PDF, DOCX, EPUB, ODT, ZIP, TAR.GZ, SQLite, MKV/MP4, images (OCR). " +
      "Returns a file_id for subsequent extract/search operations.",
    {
      filename: z
        .string()
        .describe("Original filename with extension, e.g. 'report.pdf'"),
      content_base64: z
        .string()
        .describe("File content encoded as base64 string"),
    },
    async ({ filename, content_base64 }) => {
      return uploadFile(filename, content_base64);
    }
  );

  // ============================================================
  // Tool 2: rga_extract_text — 全文提取
  // ============================================================
  server.tool(
    "rga_extract_text",
    "Extract text content from a file using rga-preproc. " +
      "Works with uploaded files (by file_id) or files in the mounted /data/documents directory. " +
      "Returns extracted text with token count estimation. " +
      "For PDF files: use page_start/page_end to extract specific pages (much faster for large PDFs). " +
      "Tip: Use rga_search_content first to find relevant pages, then extract only those pages.",
    {
      file_id: z
        .string()
        .describe(
          "File ID from rga_upload_file, or relative path within /data/documents"
        ),
      max_tokens: z
        .number()
        .optional()
        .default(50000)
        .describe(
          "Max tokens to return. Default 50000. Use smaller values for summaries."
        ),
      enable_ocr: z
        .boolean()
        .optional()
        .default(false)
        .describe(
          "Enable OCR for images/scanned PDFs (slower). Default false."
        ),
      page_start: z
        .number()
        .optional()
        .describe(
          "PDF only: first page to extract (1-based). Use with page_end for page-range extraction."
        ),
      page_end: z
        .number()
        .optional()
        .describe(
          "PDF only: last page to extract (1-based). Use with page_start for page-range extraction."
        ),
      response_format: z
        .enum(["json", "markdown"])
        .optional()
        .default("json")
        .describe("Response format: 'json' or 'markdown'"),
    },
    async ({ file_id, max_tokens, enable_ocr, page_start, page_end, response_format }) => {
      return extractText(file_id, max_tokens, enable_ocr, response_format, page_start, page_end);
    }
  );

  // ============================================================
  // Tool 3: rga_search_content — 正則搜尋
  // ============================================================
  server.tool(
    "rga_search_content",
    "Search for a regex pattern within files using ripgrep-all. " +
      "Searches across all supported formats including inside archives. " +
      "Can search uploaded files, mounted documents directory, or a specific subdirectory. " +
      "Tip: Use rga_list_documents first to discover available files and directories.",
    {
      pattern: z.string().describe("Regex pattern to search for"),
      file_id: z
        .string()
        .optional()
        .describe("Search in specific uploaded file by file_id"),
      search_path: z
        .string()
        .optional()
        .describe(
          "Relative path within /data/documents to narrow search scope"
        ),
      case_insensitive: z.boolean().optional().default(true),
      context_lines: z
        .number()
        .optional()
        .default(2)
        .describe("Context lines before/after each match"),
      max_matches: z.number().optional().default(100),
      max_tokens: z.number().optional().default(20000),
      enable_ocr: z.boolean().optional().default(false),
      response_format: z
        .enum(["json", "markdown"])
        .optional()
        .default("json"),
    },
    async ({
      pattern,
      file_id,
      search_path,
      case_insensitive,
      context_lines,
      max_matches,
      max_tokens,
      enable_ocr,
      response_format,
    }) => {
      return searchContent(
        pattern,
        file_id,
        search_path,
        case_insensitive,
        context_lines,
        max_matches,
        max_tokens,
        enable_ocr,
        response_format
      );
    }
  );

  // ============================================================
  // Tool 4: rga_list_supported_formats — 列出支援格式
  // ============================================================
  server.tool(
    "rga_list_supported_formats",
    "List all file formats supported by this rga-mcp-server and their adapter status.",
    {},
    async () => {
      return listFormats();
    }
  );

  // ============================================================
  // Tool 5: rga_list_documents — 列出文件目錄結構
  // ============================================================
  server.tool(
    "rga_list_documents",
    "List files and directories in the mounted documents directory (/data/documents). " +
      "Use this to discover available files before searching or extracting text. " +
      "Supports browsing subdirectories and showing file sizes.",
    {
      path: z
        .string()
        .optional()
        .default("")
        .describe(
          "Relative path within /data/documents to list. Default: root directory"
        ),
      recursive: z
        .boolean()
        .optional()
        .default(false)
        .describe(
          "List subdirectories recursively (max depth 5). Default false."
        ),
      include_uploads: z
        .boolean()
        .optional()
        .default(false)
        .describe("Also list uploaded files in /data/uploads. Default false."),
    },
    async ({ path, recursive, include_uploads }) => {
      return listDocuments(path, recursive, include_uploads);
    }
  );
}
