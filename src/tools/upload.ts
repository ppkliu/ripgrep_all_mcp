/**
 * File upload tool
 * 處理 base64 編碼的檔案上傳
 */

import { randomUUID } from "crypto";
import path from "path";
import fs from "fs/promises";

function getUploadDir() {
  return process.env.UPLOAD_DIR || "/data/uploads";
}

function getMaxSize() {
  return parseInt(process.env.MAX_FILE_SIZE_MB || "100") * 1024 * 1024;
}

export async function uploadFile(filename: string, contentBase64: string) {
  const buffer = Buffer.from(contentBase64, "base64");
  const maxSize = getMaxSize();

  if (buffer.length > maxSize) {
    return {
      isError: true,
      content: [
        {
          type: "text" as const,
          text: `Error: File size ${(buffer.length / 1024 / 1024).toFixed(1)}MB exceeds limit of ${maxSize / 1024 / 1024}MB.`,
        },
      ],
    };
  }

  const ext = path.extname(filename);
  const fileId = `${randomUUID()}${ext}`;
  const uploadDir = getUploadDir();
  const filePath = path.join(uploadDir, fileId);

  // 確保目錄存在
  await fs.mkdir(uploadDir, { recursive: true });

  // 寫入檔案
  await fs.writeFile(filePath, buffer);

  // 寫入 metadata
  const meta = {
    originalName: filename,
    fileId,
    size: buffer.length,
    uploadedAt: new Date().toISOString(),
  };
  await fs.writeFile(`${filePath}.meta.json`, JSON.stringify(meta, null, 2));

  const result = {
    file_id: fileId,
    original_name: filename,
    size_bytes: buffer.length,
    size_human: `${(buffer.length / 1024 / 1024).toFixed(2)} MB`,
    status: "uploaded",
    next_steps: [
      `Use rga_extract_text with file_id="${fileId}" to extract all text content`,
      `Use rga_search_content with file_id="${fileId}" to search within the file`,
    ],
  };

  return {
    content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
  };
}
