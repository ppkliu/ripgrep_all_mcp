# API 文档

## MCP Server API

### 服务器信息

- **名称**: ripgrep-all-mcp
- **版本**: 1.0.0
- **传输**: stdio

## 可用工具

### 1. rga_search

执行 ripgrep-all 搜索操作。

#### 请求

```json
{
  "name": "rga_search",
  "arguments": {
    "query": "string",
    "path": "string",
    "extension": "string (optional)",
    "maxResults": "number (optional, default: 10)",
    "caseSensitive": "boolean (optional, default: true)",
    "useRegex": "boolean (optional, default: true)",
    "contextLines": "number (optional, default: 0)"
  }
}
```

#### 响应

```json
{
  "success": true,
  "results": [
    {
      "path": "/path/to/file.pdf",
      "lineNumber": 42,
      "content": "匹配的内容...",
      "fileType": "PDF"
    }
  ],
  "totalMatches": 5,
  "searchTime": 234
}
```

#### 参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | ✓ | - | 搜索关键词或正则表达式 |
| path | string | ✓ | - | 搜索的基础目录（支持相对和绝对路径） |
| extension | string | ✗ | - | 限制文件扩展名（如 'pdf'、'docx'） |
| maxResults | number | ✗ | 10 | 最多返回结果数（1-100） |
| caseSensitive | boolean | ✗ | true | 是否区分大小写 |
| useRegex | boolean | ✗ | true | 是否使用正则表达式 |
| contextLines | number | ✗ | 0 | 上下文行数（0-5） |

#### 错误响应

```json
{
  "success": false,
  "results": [],
  "totalMatches": 0,
  "error": "错误信息"
}
```

#### 示例

**示例 1: 简单搜索**
```json
{
  "name": "rga_search",
  "arguments": {
    "query": "TODO",
    "path": "/home/user/projects"
  }
}
```

**示例 2: PDF 搜索**
```json
{
  "name": "rga_search",
  "arguments": {
    "query": "合同",
    "path": "/home/user/documents",
    "extension": "pdf",
    "maxResults": 20
  }
}
```

**示例 3: 正则表达式搜索**
```json
{
  "name": "rga_search",
  "arguments": {
    "query": "[0-9]{3}-[0-9]{2}-[0-9]{4}",
    "path": "/home/user",
    "useRegex": true,
    "caseSensitive": false
  }
}
```

---

### 2. rga_info

获取 ripgrep-all 的信息。

#### 请求

```json
{
  "name": "rga_info",
  "arguments": {}
}
```

#### 响应

```json
{
  "available": true,
  "supportedFormats": [
    "PDF",
    "DOCX",
    "XLSX",
    "PPTX",
    "TXT",
    ...
  ],
  "description": "ripgrep-all (rga) 是一个行导向的搜索工具..."
}
```

#### 示例响应

```json
{
  "available": true,
  "supportedFormats": [
    "PDF",
    "DOCX",
    "XLSX",
    "PPTX",
    "TXT",
    "MD",
    "JSON",
    "XML",
    "CSV",
    "ZIP",
    "TAR",
    "GZ",
    "EPUB",
    "MOBI",
    "HTML",
    "Images (OCR: JPG, PNG, etc.)"
  ],
  "description": "ripgrep-all (rga) 是一个行导向的搜索工具，也可以搜索 PDF、电子书、Office 文档、zip 文件和其他档案格式内部。"
}
```

---

## 支持的文件格式

### 文档
- **PDF**: `.pdf` (需要 poppler)
- **Word**: `.docx`, `.doc` (需要 pandoc)
- **Excel**: `.xlsx`, `.xls` (需要 pandoc)
- **PowerPoint**: `.pptx`, `.ppt` (需要 pandoc)

### 文本文件
- `.txt`, `.md`, `.json`, `.xml`, `.csv`, `.yaml`, `.html` 等

### 档案
- `.zip`, `.tar`, `.tar.gz`, `.tar.bz2`

### 电子书
- `.epub`, `.mobi` (需要 pandoc)

### 图像 (OCR)
- `.jpg`, `.jpeg`, `.png`, `.bmp` (需要 tesseract)

### 源代码
- 所有编程语言源代码文件

---

## 错误处理

### 常见错误

#### 错误 1: "ripgrep-all (rga) is not installed"

```json
{
  "success": false,
  "error": "ripgrep-all (rga) is not installed or not in PATH"
}
```

**解决方案**: 安装 ripgrep-all

#### 错误 2: "Query and path are required"

```json
{
  "success": false,
  "error": "Query and path are required"
}
```

**解决方案**: 确保提供了 `query` 和 `path` 参数

#### 错误 3: 找不到结果

```json
{
  "success": true,
  "results": [],
  "totalMatches": 0
}
```

这不是错误，表示没有找到匹配项。

---

## 性能优化建议

### 1. 优化搜索范围

❌ **不推荐**:
```json
{
  "query": "test",
  "path": "/"
}
```

✅ **推荐**:
```json
{
  "query": "test",
  "path": "/home/user/projects"
}
```

### 2. 使用文件扩展名过滤

❌ **不推荐**:
```json
{
  "query": "def main",
  "path": "/home/user"
}
```

✅ **推荐**:
```json
{
  "query": "def main",
  "path": "/home/user",
  "extension": "py"
}
```

### 3. 限制结果数量

```json
{
  "query": "error",
  "path": "/var/log",
  "maxResults": 20
}
```

### 4. 使用正确的正则表达式

优化正则表达式以提高性能：

```json
{
  "query": "^\\[ERROR\\]",
  "path": "/var/log",
  "useRegex": true,
  "maxResults": 50
}
```

---

## 集成示例

### Python 集成

```python
import json
import subprocess

def search_files(query, path, extension=None):
    command = ["node", "dist/index.js"]

    input_data = {
        "method": "tools/call",
        "params": {
            "name": "rga_search",
            "arguments": {
                "query": query,
                "path": path,
                "extension": extension
            }
        }
    }

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    output, error = process.communicate(
        input=json.dumps(input_data).encode()
    )

    return json.loads(output.decode())
```

### JavaScript 集成

```javascript
const { RgaExecutor } = require('./dist/utils/rga-executor');

async function searchFiles(query, path, options = {}) {
  try {
    const response = await RgaExecutor.search({
      query,
      path,
      maxResults: options.maxResults || 10,
      extension: options.extension,
      ...options
    });

    return response;
  } catch (error) {
    console.error('搜索失败:', error);
    throw error;
  }
}

// 使用
searchFiles('bug', '/src', { extension: 'ts' })
  .then(results => console.log(results));
```

---

## 故障排除

### 搜索超时

如果搜索在大型目录中超时：

1. 减小搜索范围
2. 添加文件扩展名过滤
3. 减少 `maxResults`

### 内存不足

对于大型搜索操作：

1. 使用更具体的搜索词
2. 限制搜索路径
3. 增加上下文行数的限制

### 无权限访问

确保运行 MCP 服务器的用户有读取权限：

```bash
ls -ld /path/to/search
```

---

## 限制

- 最大结果数: 100
- 最大上下文行数: 5
- 每个文件最多 3 个匹配显示
- 单行最大长度: 取决于终端缓冲

---

## 更新日志

### v1.0.0
- 初始版本
- 基本搜索功能
- PDF, DOCX, Excel, PowerPoint 支持
- MCP 服务器实现
