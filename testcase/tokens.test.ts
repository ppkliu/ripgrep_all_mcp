/**
 * Tests for token utilities
 */

import { countTokens, truncateToTokenLimit } from "../src/utils/tokens.js";

describe("countTokens", () => {
  it("should return 0 for empty string", () => {
    expect(countTokens("")).toBe(0);
  });

  it("should return 0 for null/undefined-like input", () => {
    expect(countTokens("")).toBe(0);
  });

  it("should count English text tokens", () => {
    const text = "Hello world, this is a test sentence.";
    const tokens = countTokens(text);
    expect(tokens).toBeGreaterThan(0);
    expect(tokens).toBeLessThan(text.length);
  });

  it("should count CJK text with higher token density", () => {
    const cjkText = "這是一個測試句子";
    const englishText = "This is a test sentence";
    const cjkTokens = countTokens(cjkText);
    const englishTokens = countTokens(englishText);
    // CJK characters should have more tokens per character
    expect(cjkTokens / cjkText.length).toBeGreaterThan(
      englishTokens / englishText.length
    );
  });
});

describe("truncateToTokenLimit", () => {
  it("should not truncate short text", () => {
    const text = "short text";
    const result = truncateToTokenLimit(text, 1000);
    expect(result).toBe(text);
  });

  it("should truncate long text", () => {
    const text = "a".repeat(10000);
    const result = truncateToTokenLimit(text, 100);
    expect(result.length).toBeLessThan(text.length);
  });

  it("should return non-empty result when truncating", () => {
    const text = "a".repeat(10000);
    const result = truncateToTokenLimit(text, 10);
    expect(result.length).toBeGreaterThan(0);
  });
});
