/**
 * Type definitions for rga-mcp-server
 */

export interface SearchResult {
  path: string;
  lineNumber: number;
  content: string;
  fileType?: string;
}

export interface RgaSearchOptions {
  query: string;
  path: string;
  extension?: string;
  maxResults?: number;
  caseSensitive?: boolean;
  useRegex?: boolean;
  contextLines?: number;
}

export interface RgaSearchResponse {
  success: boolean;
  results: SearchResult[];
  totalMatches: number;
  searchTime?: number;
  error?: string;
}

export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties: Record<string, unknown>;
    required: string[];
  };
}

export interface MCPToolInput {
  query: string;
  path: string;
  extension?: string;
  maxResults?: number;
  caseSensitive?: boolean;
  useRegex?: boolean;
  contextLines?: number;
}

export interface TokenStats {
  full_document_tokens: number;
  returned_tokens: number;
  max_tokens_requested: number;
  truncated: boolean;
  note?: string;
}

export interface FileMeta {
  originalName: string;
  fileId: string;
  size: number;
  uploadedAt: string;
}
