/**
 * Text extraction tool
 * 使用 rga-preproc 從各種檔案格式提取純文字
 */

import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";
import fs from "fs/promises";
import { countTokens, truncateToTokenLimit } from "../utils/tokens.js";

const execFileAsync = promisify(execFile);
const UPLOAD_DIR = process.env.UPLOAD_DIR || "/data/uploads";
const DOCUMENTS_DIR = process.env.DOCUMENTS_DIR || "/data/documents";

// 提取結果快取 (避免對同一檔案重複執行 rga-preproc)
const extractCache = new Map<
  string,
  { result: { content: { type: "text"; text: string }[] }; ts: number }
>();
const EXTRACT_CACHE_TTL = 300_000; // 5 分鐘

// rga-preproc 沒有 adapter 的純文字格式，直接讀取
const PLAINTEXT_EXTENSIONS = new Set([
  ".txt", ".md", ".json", ".xml", ".yaml", ".yml",
  ".csv", ".log", ".ts", ".js", ".py", ".go", ".rs",
  ".java", ".c", ".cpp", ".h", ".sh", ".bash", ".toml",
  ".ini", ".cfg", ".conf", ".env", ".gitignore",
]);

export async function extractText(
  fileId: string,
  maxTokens: number,
  enableOcr: boolean,
  responseFormat: string
) {
  // 快取檢查
  const cacheKey = `${fileId}:${maxTokens}:${enableOcr}:${responseFormat}`;
  const cached = extractCache.get(cacheKey);
  if (cached && Date.now() - cached.ts < EXTRACT_CACHE_TTL) {
    console.error(`[rga-extract] cache hit: ${fileId}`);
    return cached.result;
  }

  // 先在 uploads 目錄找，再在 documents 目錄找
  let filePath = path.join(UPLOAD_DIR, fileId);
  let originalName = fileId;

  try {
    await fs.access(filePath);
    // 嘗試讀取 metadata
    try {
      const meta = JSON.parse(
        await fs.readFile(`${filePath}.meta.json`, "utf-8")
      );
      originalName = meta.originalName;
    } catch {
      // no metadata, use fileId as name
    }
  } catch {
    // 嘗試在 documents 目錄中查找
    filePath = path.join(DOCUMENTS_DIR, fileId);
    try {
      await fs.access(filePath);
      originalName = path.basename(fileId);
    } catch {
      return {
        isError: true,
        content: [
          {
            type: "text" as const,
            text: `Error: File not found: ${fileId}. Use rga_upload_file to upload, or provide a path relative to /data/documents.`,
          },
        ],
      };
    }
  }

  // 判斷是否為純文字檔案（rga-preproc 不支援）
  const ext = path.extname(filePath).toLowerCase();
  let rawText: string;

  if (PLAINTEXT_EXTENSIONS.has(ext)) {
    // 純文字：直接讀取
    try {
      rawText = await fs.readFile(filePath, "utf-8");
    } catch (error: any) {
      return {
        isError: true,
        content: [
          {
            type: "text" as const,
            text: `Error reading file: ${error.message}`,
          },
        ],
      };
    }
  } else {
    // 二進位格式：使用 rga-preproc
    const args: string[] = [];
    if (enableOcr) {
      args.push("--rga-adapters=+pdfpages,tesseract");
    }
    args.push(filePath);

    try {
      const { stdout, stderr } = await execFileAsync("rga-preproc", args, {
        maxBuffer: 50 * 1024 * 1024,
        timeout: 120_000,
      });
      if (stderr) {
        console.error(`[rga-preproc stderr] ${stderr}`);
      }
      rawText = stdout;
    } catch (error: any) {
      return {
        isError: true,
        content: [
          {
            type: "text" as const,
            text: `Error extracting text: ${error.message}. Ensure the file format is supported (use rga_list_supported_formats).`,
          },
        ],
      };
    }
  }

  try {
    // Token 計算與截斷
    const fullTokenCount = countTokens(rawText);
    const truncatedText = truncateToTokenLimit(rawText, maxTokens);
    const returnedTokenCount = countTokens(truncatedText);
    const wasTruncated = fullTokenCount > returnedTokenCount;

    let output: { content: { type: "text"; text: string }[] };

    if (responseFormat === "markdown") {
      const md = [
        `## Extracted Text: ${originalName}`,
        "",
        "### Token Statistics",
        `- **Full document**: ${fullTokenCount.toLocaleString()} tokens`,
        `- **Returned**: ${returnedTokenCount.toLocaleString()} tokens`,
        `- **Truncated**: ${wasTruncated ? "Yes" : "No"}`,
        "",
        "### Content",
        "```",
        truncatedText,
        "```",
      ].join("\n");

      output = { content: [{ type: "text" as const, text: md }] };
    } else {
      // JSON format (default)
      const result = {
        file_id: fileId,
        original_name: originalName,
        extracted_text: truncatedText,
        token_stats: {
          full_document_tokens: fullTokenCount,
          returned_tokens: returnedTokenCount,
          max_tokens_requested: maxTokens,
          truncated: wasTruncated,
          note: wasTruncated
            ? `Document was truncated from ${fullTokenCount} to ${returnedTokenCount} tokens. Use rga_search_content for targeted retrieval.`
            : "Full document returned.",
        },
      };

      output = {
        content: [
          { type: "text" as const, text: JSON.stringify(result, null, 2) },
        ],
      };
    }

    // 寫入快取
    extractCache.set(cacheKey, { result: output, ts: Date.now() });
    return output;
  } catch (error: any) {
    return {
      isError: true,
      content: [
        {
          type: "text" as const,
          text: `Error extracting text: ${error.message}. Ensure the file format is supported (use rga_list_supported_formats).`,
        },
      ],
    };
  }
}
