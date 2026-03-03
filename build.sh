#!/bin/bash

# 构建脚本
# 用于构建和部署 ripgrep-all MCP

set -e

echo "🔨 开始构建 ripgrep-all MCP..."

# 检查依赖
echo "📦 检查依赖..."
npm --version > /dev/null || { echo "❌ npm 未安装"; exit 1; }
rga --version > /dev/null || { echo "❌ ripgrep-all 未安装"; exit 1; }

# 安装 npm 包
echo "📥 安装 npm 包..."
npm install

# 运行 linter
echo "✨ 运行代码检查..."
npm run lint || true

# 编译 TypeScript
echo "📝 编译 TypeScript..."
npm run build

# 生成文档
echo "📚 准备文档..."
ls -la dist/

echo "✅ 构建完成！"
echo ""
echo "后续步骤："
echo "1. 运行服务器: npm start"
echo "2. 配置 MCP 客户端 (见 QUICK_START.md)"
echo "3. 重启 MCP 客户端"
echo ""
echo "需要帮助？查看 QUICK_START.md"
