/**
 * Token counting utilities
 * 使用簡單的字元估算 (避免 tiktoken 原生依賴問題)
 * 估算規則: 英文 ~4 字元/token, 中文 ~1.5 字元/token, 混合 ~3.5 字元/token
 */

/**
 * 計算文字的 token 數量估算
 */
export function countTokens(text: string): number {
  if (!text) return 0;

  // 分離中文和非中文字元
  const cjkChars = text.match(/[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]/g);
  const cjkCount = cjkChars ? cjkChars.length : 0;
  const nonCjkLength = text.length - cjkCount;

  // 中文約 1.5 字元/token, 英文約 4 字元/token
  return Math.ceil(cjkCount / 1.5 + nonCjkLength / 4);
}

/**
 * 截斷文字到指定 token 上限
 */
export function truncateToTokenLimit(text: string, maxTokens: number): string {
  const currentTokens = countTokens(text);
  if (currentTokens <= maxTokens) return text;

  // 按比例截斷
  const ratio = maxTokens / currentTokens;
  const targetLength = Math.floor(text.length * ratio * 0.95); // 留 5% 餘量
  return text.slice(0, targetLength);
}
