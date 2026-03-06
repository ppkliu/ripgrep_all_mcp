# ============================================================
# rga-mcp-server Dockerfile
# 包含 ripgrep-all 及所有 adapter 依賴
# ============================================================
FROM node:22-bookworm-slim AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# ============================================================
# Runtime stage
# ============================================================
FROM node:22-bookworm-slim

# 安裝系統依賴 (所有 rga adapter 需要的外部工具)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PDF adapter
    poppler-utils \
    # pandoc adapter (docx, epub, odt, html, ipynb)
    pandoc \
    # ffmpeg adapter (mkv, mp4 字幕)
    ffmpeg \
    # OCR adapter (tesseract + 中英文語言包)
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-chi-tra \
    tesseract-ocr-chi-sim \
    # 通用工具
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安裝 ripgrep-all
ARG RGA_VERSION=1.0.0-alpha.5
RUN curl -fsSL "https://github.com/phiresky/ripgrep-all/releases/download/v${RGA_VERSION}/ripgrep_all-v${RGA_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    | tar xz -C /usr/local/bin --strip-components=1 \
    && chmod +x /usr/local/bin/rga /usr/local/bin/rga-preproc

# 驗證安裝
RUN rga --version && which rga-preproc

WORKDIR /app

# Copy built artefacts + production deps only
COPY --from=builder /app/dist ./dist
COPY package.json package-lock.json* ./
RUN npm install --omit=dev

# 建立資料目錄
RUN mkdir -p /data/uploads /data/cache /data/documents
ENV RGA_CACHE_DIR=/data/cache

# rga cache 調優 (加速 PDF 重複提取)
ENV RGA_CACHE_COMPRESSION_LEVEL=6
ENV RGA_CACHE_MAX_BLOB_LEN=20M

# 環境變數預設值
ENV MCP_TRANSPORT=stdio
ENV UPLOAD_DIR=/data/uploads
ENV DOCUMENTS_DIR=/data/documents
ENV MAX_FILE_SIZE_MB=100
ENV MAX_OUTPUT_TOKENS=100000

EXPOSE 3000

VOLUME ["/data/uploads", "/data/cache", "/data/documents"]

ENTRYPOINT ["node", "dist/index.js"]
