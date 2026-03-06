/**
 * Content search tool
 * 使用 rga 進行正則搜尋
 */

import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";
import { countTokens, truncateToTokenLimit } from "../utils/tokens.js";

const execFileAsync = promisify(execFile);
const UPLOAD_DIR = process.env.UPLOAD_DIR || "/data/uploads";
const DOCUMENTS_DIR = process.env.DOCUMENTS_DIR || "/data/documents";

// 搜尋結果快取
const searchCache = new Map<
  string,
  { result: { content: { type: "text"; text: string }[] }; ts: number }
>();
const SEARCH_CACHE_TTL = 120_000; // 2 分鐘

export async function searchContent(
  pattern: string,
  fileId: string | undefined,
  searchPath: string | undefined,
  caseInsensitive: boolean,
  contextLines: number,
  maxMatches: number,
  maxTokens: number,
  enableOcr: boolean,
  responseFormat: string
) {
  // 快取檢查
  const cacheKey = `${pattern}:${fileId}:${searchPath}:${caseInsensitive}:${contextLines}:${maxMatches}:${maxTokens}:${enableOcr}:${responseFormat}`;
  const cached = searchCache.get(cacheKey);
  if (cached && Date.now() - cached.ts < SEARCH_CACHE_TTL) {
    console.error(`[rga-search] cache hit: ${pattern}`);
    return cached.result;
  }

  // 決定搜尋路徑
  let targetPath: string;
  if (fileId) {
    targetPath = path.join(UPLOAD_DIR, fileId);
  } else if (searchPath) {
    // 允許搜尋掛載的 documents 目錄下的子路徑
    targetPath = path.join(DOCUMENTS_DIR, searchPath);
  } else {
    // 預設搜尋 documents 目錄
    targetPath = DOCUMENTS_DIR;
  }

  const args: string[] = [];

  // JSON 輸出便於解析
  args.push("--json");

  if (caseInsensitive) args.push("-i");
  args.push("-C", String(contextLines));
  args.push("-m", String(maxMatches));

  if (enableOcr) {
    args.push("--rga-adapters=+pdfpages,tesseract");
  }

  args.push(pattern);
  args.push(targetPath);

  try {
    const { stdout } = await execFileAsync("rga", args, {
      maxBuffer: 20 * 1024 * 1024,
      timeout: 120_000,
    });

    // 解析 JSON lines 輸出
    const lines = stdout.trim().split("\n").filter(Boolean);
    const matches: Array<{
      file: string;
      line_number: number;
      text: string;
      submatches: string[];
    }> = [];

    for (const line of lines) {
      try {
        const obj = JSON.parse(line);
        if (obj.type === "match") {
          matches.push({
            file: path.relative(
              fileId ? UPLOAD_DIR : DOCUMENTS_DIR,
              obj.data.path?.text || ""
            ),
            line_number: obj.data.line_number,
            text: (obj.data.lines?.text || "").trim(),
            submatches: (obj.data.submatches || []).map(
              (s: { match?: { text?: string } }) => s.match?.text || ""
            ),
          });
        }
      } catch {
        continue;
      }
    }

    const resultText = JSON.stringify(matches, null, 2);
    const fullTokens = countTokens(resultText);
    const truncated = truncateToTokenLimit(resultText, maxTokens);
    const returnedTokens = countTokens(truncated);

    let output: { content: { type: "text"; text: string }[] };

    if (responseFormat === "markdown") {
      const md = [
        `## Search Results: \`${pattern}\``,
        "",
        `**Total matches**: ${matches.length}`,
        `**Tokens**: ${returnedTokens.toLocaleString()} / ${fullTokens.toLocaleString()}`,
        "",
        ...matches.slice(0, 50).map(
          (m, i) =>
            `### Match ${i + 1} — ${m.file}:${m.line_number}\n\`\`\`\n${m.text}\n\`\`\``
        ),
      ].join("\n");
      output = { content: [{ type: "text" as const, text: md }] };
    } else {
      const result = {
        pattern,
        total_matches: matches.length,
        search_path: fileId || searchPath || "all_documents",
        results: matches,
        token_stats: {
          full_result_tokens: fullTokens,
          returned_tokens: returnedTokens,
          max_tokens_requested: maxTokens,
          truncated: fullTokens > returnedTokens,
        },
      };

      output = {
        content: [
          { type: "text" as const, text: JSON.stringify(result, null, 2) },
        ],
      };
    }

    // 寫入快取
    searchCache.set(cacheKey, { result: output, ts: Date.now() });
    return output;
  } catch (error: any) {
    // rga exit code 1 = no matches
    if (error.code === 1) {
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify({
              pattern,
              total_matches: 0,
              results: [],
              token_stats: {
                full_result_tokens: 0,
                returned_tokens: 0,
                truncated: false,
              },
            }),
          },
        ],
      };
    }
    return {
      isError: true,
      content: [
        { type: "text" as const, text: `Search error: ${error.message}` },
      ],
    };
  }
}
