/**
 * Tests for ToolRegistry
 */

import { ToolRegistry } from "../src/tools/registry.js";

describe("ToolRegistry", () => {
  describe("getSearchTool", () => {
    it("should return a valid tool definition for rga_search", () => {
      const tool = ToolRegistry.getSearchTool();
      expect(tool.name).toBe("rga_search");
      expect(tool.description).toBeDefined();
      expect(tool.description.length).toBeGreaterThan(0);
    });

    it("should have required fields in inputSchema", () => {
      const tool = ToolRegistry.getSearchTool();
      expect(tool.inputSchema.type).toBe("object");
      expect(tool.inputSchema.required).toContain("query");
      expect(tool.inputSchema.required).toContain("path");
    });

    it("should define all expected properties", () => {
      const tool = ToolRegistry.getSearchTool();
      const props = tool.inputSchema.properties as Record<string, any>;
      expect(props.query).toBeDefined();
      expect(props.path).toBeDefined();
      expect(props.extension).toBeDefined();
      expect(props.maxResults).toBeDefined();
      expect(props.caseSensitive).toBeDefined();
      expect(props.useRegex).toBeDefined();
      expect(props.contextLines).toBeDefined();
    });

    it("should have correct types for properties", () => {
      const tool = ToolRegistry.getSearchTool();
      const props = tool.inputSchema.properties as Record<string, any>;
      expect(props.query.type).toBe("string");
      expect(props.path.type).toBe("string");
      expect(props.extension.type).toBe("string");
      expect(props.maxResults.type).toBe("number");
      expect(props.caseSensitive.type).toBe("boolean");
      expect(props.useRegex.type).toBe("boolean");
      expect(props.contextLines.type).toBe("number");
    });

    it("should enforce maxResults bounds", () => {
      const tool = ToolRegistry.getSearchTool();
      const props = tool.inputSchema.properties as Record<string, any>;
      expect(props.maxResults.minimum).toBe(1);
      expect(props.maxResults.maximum).toBe(100);
    });
  });

  describe("getInfoTool", () => {
    it("should return a valid tool definition for rga_info", () => {
      const tool = ToolRegistry.getInfoTool();
      expect(tool.name).toBe("rga_info");
      expect(tool.description).toBeDefined();
    });

    it("should have no required parameters", () => {
      const tool = ToolRegistry.getInfoTool();
      expect(tool.inputSchema.required).toEqual([]);
    });
  });

  describe("getAllTools", () => {
    it("should return all registered tools", () => {
      const tools = ToolRegistry.getAllTools();
      expect(tools.length).toBe(2);
    });

    it("should include both rga_search and rga_info", () => {
      const tools = ToolRegistry.getAllTools();
      const names = tools.map((t) => t.name);
      expect(names).toContain("rga_search");
      expect(names).toContain("rga_info");
    });

    it("should return unique tool names", () => {
      const tools = ToolRegistry.getAllTools();
      const names = tools.map((t) => t.name);
      const uniqueNames = new Set(names);
      expect(uniqueNames.size).toBe(names.length);
    });
  });
});
