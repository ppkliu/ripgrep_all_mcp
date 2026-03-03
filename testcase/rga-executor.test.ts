/**
 * Tests for RgaExecutor
 */

import { fileURLToPath } from "url";
import path from "path";
import { RgaExecutor } from "../src/utils/rga-executor.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe("RgaExecutor", () => {
  describe("checkRgaAvailable", () => {
    it("should return a boolean indicating rga availability", async () => {
      const result = await RgaExecutor.checkRgaAvailable();
      expect(typeof result).toBe("boolean");
    });
  });

  describe("search", () => {
    it("should return error when query is empty", async () => {
      const result = await RgaExecutor.search({
        query: "",
        path: "/tmp",
      });
      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });

    it("should return error when path is empty", async () => {
      const result = await RgaExecutor.search({
        query: "test",
        path: "",
      });
      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });

    it("should return success with empty results for non-matching query", async () => {
      const isAvailable = await RgaExecutor.checkRgaAvailable();
      if (!isAvailable) {
        console.warn("Skipping: rga not installed");
        return;
      }

      const result = await RgaExecutor.search({
        query: "xyznonexistentpattern123456",
        path: "/tmp",
      });
      expect(result.success).toBe(true);
      expect(result.results).toEqual([]);
      expect(result.totalMatches).toBe(0);
    });

    it("should respect maxResults option", async () => {
      const isAvailable = await RgaExecutor.checkRgaAvailable();
      if (!isAvailable) {
        console.warn("Skipping: rga not installed");
        return;
      }

      const result = await RgaExecutor.search({
        query: "test",
        path: __dirname,
        maxResults: 2,
      });
      expect(result.results.length).toBeLessThanOrEqual(2);
    });

    it("should include searchTime in response", async () => {
      const isAvailable = await RgaExecutor.checkRgaAvailable();
      if (!isAvailable) {
        console.warn("Skipping: rga not installed");
        return;
      }

      const result = await RgaExecutor.search({
        query: "test",
        path: "/tmp",
      });
      expect(result.searchTime).toBeDefined();
      expect(typeof result.searchTime).toBe("number");
    });

    it("should handle extension filter", async () => {
      const isAvailable = await RgaExecutor.checkRgaAvailable();
      if (!isAvailable) {
        console.warn("Skipping: rga not installed");
        return;
      }

      const result = await RgaExecutor.search({
        query: "test",
        path: __dirname,
        extension: "ts",
      });
      expect(result.success).toBe(true);
      if (result.results.length > 0) {
        result.results.forEach((r) => {
          expect(r.path).toMatch(/\.ts$/);
        });
      }
    });
  });
});
