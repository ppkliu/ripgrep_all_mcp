/**
 * Tests for list formats tool
 */

import { listFormats } from "../src/tools/formats.js";

describe("listFormats", () => {
  it("should return content array", async () => {
    const result = await listFormats();
    expect(result.content).toBeDefined();
    expect(Array.isArray(result.content)).toBe(true);
    expect(result.content.length).toBe(1);
    expect(result.content[0].type).toBe("text");
  });

  it("should include all major format categories", async () => {
    const result = await listFormats();
    const data = JSON.parse(result.content[0].text);

    const categories = data.formats.map(
      (f: { category: string }) => f.category
    );
    expect(categories).toContain("PDF");
    expect(categories).toContain("Office Documents");
    expect(categories).toContain("E-Books");
    expect(categories).toContain("Archives");
    expect(categories).toContain("Images (OCR)");
    expect(categories).toContain("Plain Text");
  });

  it("should include notes about OCR and documents_dir", async () => {
    const result = await listFormats();
    const data = JSON.parse(result.content[0].text);

    expect(data.notes).toBeDefined();
    expect(data.notes.ocr).toBeDefined();
    expect(data.notes.documents_dir).toBeDefined();
  });

  it("should have extensions array for each format", async () => {
    const result = await listFormats();
    const data = JSON.parse(result.content[0].text);

    for (const format of data.formats) {
      expect(Array.isArray(format.extensions)).toBe(true);
      expect(format.extensions.length).toBeGreaterThan(0);
    }
  });
});
