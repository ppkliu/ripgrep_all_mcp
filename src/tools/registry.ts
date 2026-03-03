/**
 * Tool definitions for ripgrep-all MCP
 */

import { ToolDefinition } from "../types/index.js";

export class ToolRegistry {
  static getSearchTool(): ToolDefinition {
    return {
      name: "rga_search",
      description:
        "Search across multiple file formats using ripgrep-all (rga). " +
        "Supports PDF, DOCX, XLSX, PPTX, E-books, ZIP archives, images (OCR), and more. " +
        "Returns matching content with file paths and line numbers.",
      inputSchema: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description:
              "Search query or regex pattern to look for in files",
          },
          path: {
            type: "string",
            description:
              "Base directory path to search in (absolute path recommended). " +
              "Supports ~ for home directory and relative paths.",
          },
          extension: {
            type: "string",
            description:
              "Optional: Limit search to specific file extension (e.g., 'pdf', 'docx', 'txt')",
          },
          maxResults: {
            type: "number",
            description: "Maximum number of results to return (default: 10, max: 100)",
            default: 10,
            minimum: 1,
            maximum: 100,
          },
          caseSensitive: {
            type: "boolean",
            description: "Enable case-sensitive search (default: true)",
            default: true,
          },
          useRegex: {
            type: "boolean",
            description: "Use query as regex pattern (default: true)",
            default: true,
          },
          contextLines: {
            type: "number",
            description: "Number of context lines around matches (default: 0, max: 5)",
            default: 0,
            minimum: 0,
            maximum: 5,
          },
        },
        required: ["query", "path"],
      },
    };
  }

  static getInfoTool(): ToolDefinition {
    return {
      name: "rga_info",
      description:
        "Get information about ripgrep-all (rga) installation and supported file formats",
      inputSchema: {
        type: "object",
        properties: {},
        required: [],
      },
    };
  }

  static getAllTools(): ToolDefinition[] {
    return [
      this.getSearchTool(),
      this.getInfoTool(),
    ];
  }
}
