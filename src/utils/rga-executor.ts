/**
 * RGA (Ripgrep-all) Executor Module
 * Handles execution of ripgrep-all commands
 */

import { exec } from "child_process";
import { promisify } from "util";
import { SearchResult, RgaSearchOptions, RgaSearchResponse } from "../types/index.js";

const execPromise = promisify(exec);

export class RgaExecutor {
  /**
   * Check if ripgrep-all (rga) is installed and available
   */
  static async checkRgaAvailable(): Promise<boolean> {
    try {
      await execPromise("rga --version");
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Execute ripgrep-all search
   */
  static async search(options: RgaSearchOptions): Promise<RgaSearchResponse> {
    const startTime = Date.now();

    try {
      // Validate input
      if (!options.query || !options.path) {
        return {
          success: false,
          results: [],
          totalMatches: 0,
          error: "Query and path are required",
        };
      }

      // Check if rga is available
      const isAvailable = await this.checkRgaAvailable();
      if (!isAvailable) {
        return {
          success: false,
          results: [],
          totalMatches: 0,
          error: "ripgrep-all (rga) is not installed or not in PATH",
        };
      }

      // Build command
      let command = this.buildCommand(options);

      // Execute command
      const { stdout } = await execPromise(command, {
        maxBuffer: 10 * 1024 * 1024, // 10MB buffer
      });

      // Parse results
      const results = this.parseOutput(stdout);

      const searchTime = Date.now() - startTime;

      return {
        success: true,
        results: results.slice(0, options.maxResults || 10),
        totalMatches: results.length,
        searchTime,
      };
    } catch (error: any) {
      // Exit code 1 means no matches found (not an error for ripgrep)
      if (error.code === 1) {
        return {
          success: true,
          results: [],
          totalMatches: 0,
          searchTime: Date.now() - startTime,
        };
      }

      return {
        success: false,
        results: [],
        totalMatches: 0,
        error: error.message || "Unknown error occurred",
      };
    }
  }

  /**
   * Build ripgrep-all command
   */
  private static buildCommand(options: RgaSearchOptions): string {
    const parts: string[] = ["rga"];

    // Output JSON format for easy parsing
    parts.push("--json");

    // Max count per file
    parts.push("--max-count 3");

    // Case sensitivity
    if (options.caseSensitive !== false) {
      parts.push("--case-sensitive");
    }

    // Regex mode
    if (options.useRegex !== false) {
      parts.push("--regexp");
    }

    // Context lines
    if (options.contextLines && options.contextLines > 0) {
      parts.push(`--context ${options.contextLines}`);
    }

    // Query (quoted)
    parts.push(`"${this.escapeShellArg(options.query)}"`);

    // Path (quoted)
    parts.push(`"${this.escapeShellArg(options.path)}"`);

    // Extension filter
    if (options.extension) {
      parts.push(`-g "*.${options.extension.replace(/^\*\./, "")}"`);
    }

    return parts.join(" ");
  }

  /**
   * Escape shell arguments
   */
  private static escapeShellArg(arg: string): string {
    // Replace backslashes and quotes
    return arg.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }

  /**
   * Parse ripgrep-all JSON output
   */
  private static parseOutput(output: string): SearchResult[] {
    const results: SearchResult[] = [];

    const lines = output.trim().split("\n").filter((l) => l.length > 0);

    for (const line of lines) {
      try {
        const parsed = JSON.parse(line);

        // Only process 'match' type messages
        if (parsed.type === "match") {
          const data = parsed.data;
          results.push({
            path: data.path.text,
            lineNumber: data.line_number || 0,
            content: (data.lines?.text || "").trim(),
            fileType: this.getFileType(data.path.text),
          });
        }
      } catch {
        // Ignore parsing errors for individual lines
        continue;
      }
    }

    return results;
  }

  /**
   * Determine file type from extension
   */
  private static getFileType(filePath: string): string {
    const ext = filePath.split(".").pop()?.toLowerCase() || "unknown";
    const typeMap: Record<string, string> = {
      pdf: "PDF",
      docx: "Word",
      doc: "Word",
      xlsx: "Excel",
      xls: "Excel",
      pptx: "PowerPoint",
      ppt: "PowerPoint",
      zip: "Archive",
      tar: "Archive",
      gz: "Archive",
      epub: "E-Book",
      mobi: "E-Book",
      html: "HTML",
      txt: "Text",
      md: "Markdown",
      json: "JSON",
      xml: "XML",
      yaml: "YAML",
      csv: "CSV",
      jpg: "Image (OCR)",
      jpeg: "Image (OCR)",
      png: "Image (OCR)",
    };

    return typeMap[ext] || ext.toUpperCase();
  }
}
