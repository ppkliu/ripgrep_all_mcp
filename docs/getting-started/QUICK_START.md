# 快速开始指南

## 5 分钟快速上手

### 第一步：安装依赖

```bash
# 1. 进入项目目录
cd ripgrep_all_mcp

# 2. 安装 Node 依赖
npm install

# 3. 验证 rga 已安装
rga --version
```

如果 `rga --version` 失败，请先安装 ripgrep-all：

```bash
# macOS
brew install ripgrep-all

# Ubuntu
sudo apt-get install ripgrep-all

# 或从源码编译
cargo install ripgrep-all
```

### 第二步：构建项目

```bash
npm run build
```

完成后会生成 `dist/` 文件夹。

### 第三步：测试服务器

```bash
npm start
```

你应该看到输出：
```
Ripgrep-all MCP Server started successfully on stdio
```

### 第四步：集成到 Claude Desktop

#### macOS/Linux 用户：

1. 找到你的项目完整路径：
```bash
pwd
# 例如: /Users/john/projects/ripgrep_all_mcp
```

2. 编辑配置文件：
```bash
nano ~/.config/Claude/claude_desktop_config.json
```

3. 粘贴下面的配置（替换 `/path/to` 为实际路径）：
```json
{
  "mcpServers": {
    "ripgrep-all": {
      "command": "node",
      "args": ["/path/to/ripgrep_all_mcp/dist/index.js"]
    }
  }
}
```

4. 保存并退出编辑器（Ctrl+X, 然后 Y, 然后 Enter）

5. 重启 Claude Desktop

#### Windows 用户（WSL）：

1. 获取项目路径（在 WSL 终端中）：
```bash
pwd
# 例如: /home/user/ripgrep_all_mcp
```

2. 编辑配置文件（在 Windows 中）：
打开 `%APPDATA%\Claude\claude_desktop_config.json`

3. 使用 WSL 路径配置：
```json
{
  "mcpServers": {
    "ripgrep-all": {
      "command": "wsl",
      "args": ["node", "/home/user/ripgrep_all_mcp/dist/index.js"]
    }
  }
}
```

4. 保存文件

5. 重启 Claude Desktop

### 第五步：测试工具

在 Claude Desktop 中对话框尝试以下命令：

```
帮我在 ~/Documents 目录中搜索 "invoice" （在 PDF 文件中）
```

Claude 会自动使用 `rga_search` 工具！

## 常见问题速答

### Q: 怎样确保一切正常工作？

A: 在 Claude 中问："ripgrep-all 可用吗？" Agent 会用 `rga_info` 工具检查。

### Q: 可以搜索哪些文件类型？

A: PDF, Word, Excel, PowerPoint, E-books, ZIP, 图片, 和所有文本文件！

### Q: 搜索会上传到云端吗？

A: 不会！所有搜索都在你的电脑本地进行，完全隐私保护。

### Q: 如果找不到 rga？

A: 确保 rga 在 PATH 中：
```bash
which rga    # macOS/Linux
where rga    # Windows CMD
```

### Q: 服务器启动失败？

A: 检查是否有其他进程占用端口，或运行：
```bash
npm run dev
```
查看详细错误信息。

## 下一步

- 📚 阅读 [README.md](README.md) 了解所有功能
- 🚀 查看 [DEPLOYMENT.md](../deployment/DEPLOYMENT.md) 进行高级配置
- 🔗 查看 [AGNO_INTEGRATION.md](../integration/AGNO_INTEGRATION.md) 集成其他 Agent 框架
- 💡 查看 [examples.ts](examples.ts) 了解代码示例

## 获取帮助

### 检查日志

启用调试模式查看详细日志：

```bash
DEBUG=ripgrep-all-mcp:* npm start
```

### 常见命令

```bash
# 开发模式（有实时重载）
npm run dev

# 运行示例
npx ts-node examples.ts

# 检查代码风格
npm run lint

# 运行测试
npm test
```

## 成功标志

✅ 能运行 `npm start` 而不报错
✅ Claude Desktop 显示新的"ripgrep-all" 工具
✅ 能在 Claude 中对话时搜索本地文件
✅ 搜索结果正确显示

恭喜！你已成功设置 ripgrep-all MCP！ 🎉
