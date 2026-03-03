/**
 * Agno Agent Integration Module
 * 用於與 Agno Agent 框架集成
 * 注意：Agno 透過 MCPTools 直接連接 MCP server，此模組提供額外的工具包裝
 */

import { RgaExecutor } from "../utils/rga-executor.js";
import { SearchResult, RgaSearchOptions } from "../types/index.js";

/**
 * Agno Agent Tool Wrapper
 * 包裝 rga 搜尋功能供 Agent 使用
 */
export class AgnoAgentToolWrapper {
  /**
   * Create a search tool for Agno Agent
   */
  static createSearchTool() {
    return {
      name: "rga_search",
      displayName: "Ripgrep-all Search",
      description:
        "Search across PDF, DOCX, XLSX, PPTX, E-books, ZIP and other formats",
      category: "search",
      async execute(params: {
        query: string;
        path: string;
        extension?: string;
        maxResults?: number;
        caseSensitive?: boolean;
        useRegex?: boolean;
      }): Promise<{
        success: boolean;
        results: SearchResult[];
        totalMatches: number;
        error?: string;
      }> {
        const options: RgaSearchOptions = {
          query: params.query,
          path: params.path,
          extension: params.extension,
          maxResults: params.maxResults || 10,
          caseSensitive: params.caseSensitive !== false,
          useRegex: params.useRegex !== false,
        };

        const response = await RgaExecutor.search(options);
        return {
          success: response.success,
          results: response.results,
          totalMatches: response.totalMatches,
          error: response.error,
        };
      },
      schema: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description: "Search query or regex pattern",
          },
          path: {
            type: "string",
            description: "Base directory to search in",
          },
          extension: {
            type: "string",
            description: "Optional file extension filter",
          },
          maxResults: {
            type: "number",
            description: "Maximum results to return",
          },
          caseSensitive: {
            type: "boolean",
            description: "Case-sensitive search",
          },
          useRegex: {
            type: "boolean",
            description: "Use regex pattern",
          },
        },
        required: ["query", "path"],
      },
    };
  }

  /**
   * Get all tools for Agno Agent
   */
  static getAllTools() {
    return [this.createSearchTool()];
  }
}

/**
 * Quick search utility for agents
 */
export async function quickSearch(
  query: string,
  path: string,
  options?: Partial<RgaSearchOptions>
): Promise<SearchResult[]> {
  const response = await RgaExecutor.search({
    query,
    path,
    maxResults: 10,
    ...options,
  });

  if (!response.success) {
    throw new Error(response.error || "Search failed");
  }

  return response.results;
}

/**
 * Format search results for agent output
 */
export function formatSearchResults(results: SearchResult[]): string {
  if (results.length === 0) {
    return "No matches found";
  }

  return results
    .map((result, index) => {
      return `[${index + 1}] ${result.path}:${result.lineNumber} (${result.fileType})
Content: ${result.content.substring(0, 100)}${
        result.content.length > 100 ? "..." : ""
      }`;
    })
    .join("\n\n");
}
