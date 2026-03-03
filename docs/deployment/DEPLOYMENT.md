# 部署指南

## 本地开发部署

### 步骤 1: 准备环境

```bash
# 1.1 克隆或进入项目目录
cd ripgrep_all_mcp

# 1.2 安装 Node 依赖
npm install

# 1.3 验证 rga 安装
rga --version
```

### 步骤 2: 编译项目

```bash
npm run build
```

### 步骤 3: 测试服务器

```bash
# 方式 1: 直接运行编译后的版本
npm start

# 方式 2: 开发模式（需要安装 ts-node）
npm run dev
```

## Claude Desktop 配置

### macOS

1. 确保已编译项目：
```bash
npm run build
```

2. 打开配置文件：
```bash
nano ~/.config/Claude/claude_desktop_config.json
```

3. 添加配置：
```json
{
  "mcpServers": {
    "ripgrep-all": {
      "command": "node",
      "args": ["/absolute/path/to/ripgrep_all_mcp/dist/index.js"]
    }
  }
}
```

4. 重启 Claude Desktop

### Windows

1. 编译项目（在 WSL 或 PowerShell 中）：
```bash
npm run build
```

2. 打开配置文件：
```
%APPDATA%\Claude\claude_desktop_config.json
```

3. 添加配置（注意路径格式）：
```json
{
  "mcpServers": {
    "ripgrep-all": {
      "command": "node",
      "args": ["C:\\Users\\YourName\\path\\to\\ripgrep_all_mcp\\dist\\index.js"]
    }
  }
}
```

或在 WSL 中使用：
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

### Linux

1. 编译项目：
```bash
npm run build
```

2. 创建 Claude 配置目录（如不存在）：
```bash
mkdir -p ~/.config/Claude
```

3. 编辑配置文件：
```bash
nano ~/.config/Claude/claude_desktop_config.json
```

4. 添加配置：
```json
{
  "mcpServers": {
    "ripgrep-all": {
      "command": "node",
      "args": ["/home/user/ripgrep_all_mcp/dist/index.js"]
    }
  }
}
```

## Docker 部署

如果需要在容器中运行：

### Dockerfile

```dockerfile
FROM node:18-alpine

WORKDIR /app

# 安装 rga 及其依赖
RUN apk add --no-cache \
    ripgrep \
    poppler-utils \
    pandoc \
    libxslt-dev

# 复制项目文件
COPY package*.json ./
RUN npm install

COPY src ./src
COPY tsconfig.json ./

# 编译
RUN npm run build

# 启动服务
EXPOSE 3000
CMD ["npm", "start"]
```

### 构建和运行

```bash
# 构建镜像
docker build -t ripgrep-all-mcp .

# 运行容器
docker run -it \
  -v /local/path:/data \
  ripgrep-all-mcp
```

## 环境变量配置

创建 `.env` 文件（可选）：

```env
# 调试模式
DEBUG=ripgrep-all-mcp:*

# 日志级别: 'error' | 'warn' | 'info' | 'debug'
LOG_LEVEL=info

# 搜索超时时间（毫秒）
SEARCH_TIMEOUT=30000

# 最大并发搜索数
MAX_CONCURRENT_SEARCHES=5
```

## 系统依赖检查清单

- [ ] Node.js >= 18.0.0
- [ ] npm >= 8.0.0
- [ ] ripgrep-all (rga) 已安装
- [ ] pandoc（用于 Office 文档）
- [ ] poppler-utils（用于 PDF）
- [ ] tesseract（用于 OCR，可选）

### 依赖安装命令

**macOS:**
```bash
brew install ripgrep-all pandoc poppler tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install ripgrep-all pandoc poppler-utils tesseract-ocr
```

**Windows (WSL):**
```bash
sudo apt-get install ripgrep-all pandoc poppler-utils tesseract-ocr
```

## 验证安装

运行以下命令验证所有依赖：

```bash
# 检查 Node.js
node --version

# 检查 npm
npm --version

# 检查 rga
rga --version

# 检查其他依赖
pandoc --version
pdftotext -v
tesseract --version
```

## 常见部署问题

### 1. "rga not found"
```bash
# 确保 rga 在 PATH 中
which rga  # macOS/Linux
where rga  # Windows
```

### 2. Claude Desktop 找不到 MCP 服务器
- 检查路径是否为绝对路径
- 确保文件存在: `ls -l /path/to/dist/index.js`
- 检查文件权限: `chmod +x /path/to/dist/index.js`

### 3. 搜索无法找到文件
- 检查路径权限: `ls -R /search/path`
- 确保路径存在并可读
- 尝试使用绝对路径而非相对路径

### 4. 内存不足
对于大型搜索：
- 减少 `maxResults` 参数
- 限制搜索范围
- 使用 `--max-count` 限制每个文件的匹配数

## 性能优化

1. **限制搜索范围**: 使用特定目录而非 `/`
2. **使用文件扩展名过滤**: 减少搜索文件数量
3. **启用缓存**: 缓存常用搜索结果
4. **并发控制**: 限制同时进行的搜索数量

## 监控和日志

启用详细日志：

```bash
DEBUG=ripgrep-all-mcp:* npm start
```

监控可用的日志命名空间：
- `ripgrep-all-mcp:executor` - RGA 执行
- `ripgrep-all-mcp:server` - MCP 服务器
- `ripgrep-all-mcp:tools` - 工具处理

## 更新和维护

```bash
# 更新依赖
npm update

# 清理和重建
rm -rf dist node_modules
npm install
npm run build

# 更新 rga
brew upgrade ripgrep-all  # macOS
sudo apt-get upgrade ripgrep-all  # Linux
```
