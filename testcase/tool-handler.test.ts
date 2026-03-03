/**
 * Tests for ToolHandler
 */

import { ToolHandler } from "../src/tools/handler.js";

describe("ToolHandler", () => {
  describe("handleInfo", () => {
    it("should return supported formats list", async () => {
      const result = await ToolHandler.handleInfo();
      expect(result.supportedFormats).toBeDefined();
      expect(Array.isArray(result.supportedFormats)).toBe(true);
      expect(result.supportedFormats.length).toBeGreaterThan(0);
    });

    it("should include common document formats", async () => {
      const result = await ToolHandler.handleInfo();
      expect(result.supportedFormats).toContain("PDF");
      expect(result.supportedFormats).toContain("DOCX");
      expect(result.supportedFormats).toContain("XLSX");
      expect(result.supportedFormats).toContain("PPTX");
    });

    it("should return a description string", async () => {
      const result = await ToolHandler.handleInfo();
      expect(typeof result.description).toBe("string");
      expect(result.description.length).toBeGreaterThan(0);
    });

    it("should return availability boolean", async () => {
      const result = await ToolHandler.handleInfo();
      expect(typeof result.available).toBe("boolean");
    });
  });

  describe("handleSearch", () => {
    it("should return error for empty query", async () => {
      const result = await ToolHandler.handleSearch({
        query: "",
        path: "/tmp",
      });
      expect(result.success).toBe(false);
    });

    it("should return error for empty path", async () => {
      const result = await ToolHandler.handleSearch({
        query: "test",
        path: "",
      });
      expect(result.success).toBe(false);
    });

    it("should return valid response structure", async () => {
      const result = await ToolHandler.handleSearch({
        query: "nonexistent_xyz_pattern",
        path: "/tmp",
      });
      expect(result).toHaveProperty("success");
      expect(result).toHaveProperty("results");
      expect(result).toHaveProperty("totalMatches");
      expect(Array.isArray(result.results)).toBe(true);
    });
  });

  describe("routeToolCall", () => {
    it("should route rga_search correctly", async () => {
      const result = await ToolHandler.routeToolCall("rga_search", {
        query: "",
        path: "/tmp",
      });
      const parsed = JSON.parse(result);
      expect(parsed).toHaveProperty("success");
      expect(parsed).toHaveProperty("results");
    });

    it("should route rga_info correctly", async () => {
      const result = await ToolHandler.routeToolCall("rga_info", {});
      const parsed = JSON.parse(result);
      expect(parsed).toHaveProperty("supportedFormats");
      expect(parsed).toHaveProperty("description");
    });

    it("should throw error for unknown tool", async () => {
      await expect(
        ToolHandler.routeToolCall("unknown_tool", {})
      ).rejects.toThrow("Unknown tool: unknown_tool");
    });

    it("should return valid JSON string", async () => {
      const result = await ToolHandler.routeToolCall("rga_info", {});
      expect(() => JSON.parse(result)).not.toThrow();
    });
  });
});
