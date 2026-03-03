/**
 * Tool handlers for ripgrep-all MCP
 */

import { RgaExecutor } from "../utils/rga-executor.js";
import { MCPToolInput, RgaSearchResponse } from "../types/index.js";

export class ToolHandler {
  /**
   * Handle rga_search tool call
   */
  static async handleSearch(args: MCPToolInput): Promise<RgaSearchResponse> {
    const options = {
      query: args.query,
      path: args.path,
      extension: args.extension,
      maxResults: args.maxResults || 10,
      caseSensitive: args.caseSensitive !== false,
      useRegex: args.useRegex !== false,
      contextLines: args.contextLines || 0,
    };

    return RgaExecutor.search(options);
  }

  /**
   * Handle rga_info tool call
   */
  static async handleInfo(): Promise<{
    available: boolean;
    version?: string;
    supportedFormats: string[];
    description: string;
  }> {
    const available = await RgaExecutor.checkRgaAvailable();

    return {
      available,
      supportedFormats: [
        "PDF",
        "DOCX",
        "XLSX",
        "PPTX",
        "TXT",
        "MD",
        "JSON",
        "XML",
        "CSV",
        "ZIP",
        "TAR",
        "GZ",
        "EPUB",
        "MOBI",
        "HTML",
        "Images (OCR: JPG, PNG, etc.)",
      ],
      description:
        "ripgrep-all (rga) is a line-oriented search tool that also searches inside PDFs, " +
        "E-Books, Office documents, zip files, and other archive formats.",
    };
  }

  /**
   * Route tool calls
   */
  static async routeToolCall(
    toolName: string,
    args: any
  ): Promise<string> {
    switch (toolName) {
      case "rga_search": {
        const response = await this.handleSearch(args);
        return JSON.stringify(response, null, 2);
      }

      case "rga_info": {
        const response = await this.handleInfo();
        return JSON.stringify(response, null, 2);
      }

      default:
        throw new Error(`Unknown tool: ${toolName}`);
    }
  }
}
