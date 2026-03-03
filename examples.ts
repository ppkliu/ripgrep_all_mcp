/**
 * 使用示例和测试脚本
 */

import { RgaExecutor } from "./src/utils/rga-executor.js";
import { AgnoAgentToolWrapper, quickSearch, formatSearchResults } from "./src/integrations/agno-agent.js";

/**
 * 示例 1: 基础搜索
 */
async function example1_basicSearch() {
  console.log("=== 示例 1: 基础搜索 ===");

  const response = await RgaExecutor.search({
    query: "TODO",
    path: "./",
    maxResults: 5,
  });

  console.log(JSON.stringify(response, null, 2));
}

/**
 * 示例 2: PDF 搜索
 */
async function example2_pdfSearch() {
  console.log("\n=== 示例 2: 在 PDF 中搜索 ===");

  const response = await RgaExecutor.search({
    query: "关键词",
    path: "./documents",
    extension: "pdf",
    maxResults: 10,
  });

  console.log(JSON.stringify(response, null, 2));
}

/**
 * 示例 3: 正则表达式搜索
 */
async function example3_regexSearch() {
  console.log("\n=== 示例 3: 正则表达式搜索（邮箱） ===");

  const response = await RgaExecutor.search({
    query: "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}",
    path: "./documents",
    useRegex: true,
    caseSensitive: false,
  });

  console.log(JSON.stringify(response, null, 2));
}

/**
 * 示例 4: 快速搜索辅助函数
 */
async function example4_quickSearch() {
  console.log("\n=== 示例 4: 快速搜索 ===");

  try {
    const results = await quickSearch("bug", "./src", {
      extension: "ts",
      maxResults: 5,
    });

    console.log("找到结果数:", results.length);
    console.log(formatSearchResults(results));
  } catch (error) {
    console.error("错误:", error);
  }
}

/**
 * 示例 5: Agno Agent 工具
 */
async function example5_agnoAgentTools() {
  console.log("\n=== 示例 5: Agno Agent 工具 ===");

  const tools = AgnoAgentToolWrapper.getAllTools();

  console.log("可用工具数:", tools.length);

  for (const tool of tools) {
    console.log(`\n工具: ${tool.name}`);
    console.log(`描述: ${tool.displayName}`);
    console.log(`必需参数:`, tool.schema.required);
  }
}

/**
 * 示例 6: 检查 RGA 可用性
 */
async function example6_checkAvailability() {
  console.log("\n=== 示例 6: 检查 RGA 可用性 ===");

  const available = await RgaExecutor.checkRgaAvailable();
  console.log("RGA 可用:", available);
}

/**
 * 示例 7: 综合搜索场景
 */
async function example7_complexSearch() {
  console.log("\n=== 示例 7: 综合搜索（API 密钥） ===");

  const response = await RgaExecutor.search({
    query: "(api[_-]?key|secret|password|token)",
    path: "./",
    useRegex: true,
    caseSensitive: false,
    maxResults: 20,
    contextLines: 1,
  });

  if (response.success) {
    console.log(`找到 ${response.totalMatches} 个匹配`);
    console.log(`耗时: ${response.searchTime}ms`);

    response.results.forEach((result, index) => {
      console.log(`\n[${index + 1}] ${result.path}`);
      console.log(`    行号: ${result.lineNumber}`);
      console.log(`    类型: ${result.fileType}`);
      console.log(`    内容: ${result.content.substring(0, 80)}...`);
    });
  } else {
    console.error("搜索失败:", response.error);
  }
}

/**
 * 主函数
 */
async function main() {
  try {
    // 取消注释要运行的示例

    // await example1_basicSearch();
    // await example2_pdfSearch();
    // await example3_regexSearch();
    // await example4_quickSearch();
    await example5_agnoAgentTools();
    // await example6_checkAvailability();
    // await example7_complexSearch();

  } catch (error) {
    console.error("执行出错:", error);
    process.exit(1);
  }
}

main();
