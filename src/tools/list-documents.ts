/**
 * List documents tool
 * 列出 /data/documents 與 /data/uploads 下的檔案與資料夾結構
 */

import fs from "fs/promises";
import path from "path";

const DOCUMENTS_DIR = process.env.DOCUMENTS_DIR || "/data/documents";
const UPLOAD_DIR = process.env.UPLOAD_DIR || "/data/uploads";

const MAX_DEPTH = 5;
const MAX_ENTRIES = 1000;

interface FileEntry {
  name: string;
  type: "file" | "directory";
  size?: number;
  size_human?: string;
  children_count?: number;
  children?: FileEntry[];
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

async function listDir(
  basePath: string,
  recursive: boolean,
  depth: number,
  counter: { files: number; dirs: number }
): Promise<FileEntry[]> {
  if (depth > MAX_DEPTH || counter.files + counter.dirs >= MAX_ENTRIES) {
    return [];
  }

  let dirents;
  try {
    dirents = await fs.readdir(basePath, { withFileTypes: true });
  } catch {
    return [];
  }

  // Sort: directories first, then files, alphabetical
  dirents.sort((a, b) => {
    if (a.isDirectory() && !b.isDirectory()) return -1;
    if (!a.isDirectory() && b.isDirectory()) return 1;
    return a.name.localeCompare(b.name);
  });

  const entries: FileEntry[] = [];

  for (const dirent of dirents) {
    if (counter.files + counter.dirs >= MAX_ENTRIES) break;

    // Skip hidden files and metadata files
    if (dirent.name.startsWith(".") || dirent.name.endsWith(".meta.json"))
      continue;

    const fullPath = path.join(basePath, dirent.name);

    if (dirent.isDirectory()) {
      counter.dirs++;
      const entry: FileEntry = {
        name: dirent.name + "/",
        type: "directory",
      };

      if (recursive) {
        const children = await listDir(
          fullPath,
          recursive,
          depth + 1,
          counter
        );
        entry.children = children;
        entry.children_count = children.length;
      } else {
        // Count immediate children for non-recursive mode
        try {
          const sub = await fs.readdir(fullPath);
          entry.children_count = sub.filter((n) => !n.startsWith(".")).length;
        } catch {
          entry.children_count = 0;
        }
      }

      entries.push(entry);
    } else if (dirent.isFile()) {
      counter.files++;
      try {
        const stat = await fs.stat(fullPath);
        entries.push({
          name: dirent.name,
          type: "file",
          size: stat.size,
          size_human: formatSize(stat.size),
        });
      } catch {
        entries.push({ name: dirent.name, type: "file" });
      }
    }
  }

  return entries;
}

export async function listDocuments(
  relativePath: string,
  recursive: boolean,
  includeUploads: boolean
) {
  const targetPath = path.join(DOCUMENTS_DIR, relativePath);

  // Security: prevent path traversal
  const resolved = path.resolve(targetPath);
  if (!resolved.startsWith(path.resolve(DOCUMENTS_DIR))) {
    return {
      isError: true,
      content: [
        {
          type: "text" as const,
          text: "Error: path traversal not allowed. Path must be within /data/documents.",
        },
      ],
    };
  }

  // Check if directory exists
  try {
    const stat = await fs.stat(resolved);
    if (!stat.isDirectory()) {
      return {
        isError: true,
        content: [
          {
            type: "text" as const,
            text: `Error: '${relativePath}' is not a directory. Use rga_extract_text to read file content.`,
          },
        ],
      };
    }
  } catch {
    return {
      isError: true,
      content: [
        {
          type: "text" as const,
          text: `Error: directory '${relativePath || "/data/documents"}' not found. Check that documents are mounted correctly.`,
        },
      ],
    };
  }

  const counter = { files: 0, dirs: 0 };
  const entries = await listDir(resolved, recursive, 0, counter);

  const result: Record<string, unknown> = {
    base_path: DOCUMENTS_DIR,
    relative_path: relativePath || "/",
    entries,
    total_files: counter.files,
    total_directories: counter.dirs,
  };

  if (counter.files + counter.dirs >= MAX_ENTRIES) {
    result.truncated = true;
    result.note = `Results capped at ${MAX_ENTRIES} entries. Use 'path' parameter to browse subdirectories.`;
  }

  // Tips for next steps
  if (relativePath) {
    result.tips = `Use rga_search_content with search_path="${relativePath}" to search within this directory.`;
  } else {
    result.tips =
      "Use rga_search_content with search_path to search a specific directory, or rga_extract_text with file_id to read a specific file.";
  }

  // Include uploads if requested
  if (includeUploads) {
    const uploadCounter = { files: 0, dirs: 0 };
    const uploadEntries = await listDir(UPLOAD_DIR, false, 0, uploadCounter);
    result.uploads = {
      base_path: UPLOAD_DIR,
      entries: uploadEntries,
      total_files: uploadCounter.files,
    };
  }

  return {
    content: [
      { type: "text" as const, text: JSON.stringify(result, null, 2) },
    ],
  };
}
