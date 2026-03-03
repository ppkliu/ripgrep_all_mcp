/**
 * List supported formats tool
 */

import { execFile } from "child_process";
import { promisify } from "util";

const execFileAsync = promisify(execFile);

export async function listFormats() {
  let rgaVersion = "unknown";
  try {
    const { stdout } = await execFileAsync("rga", ["--version"]);
    rgaVersion = stdout.trim();
  } catch {
    // ignore
  }

  const formats = [
    {
      category: "PDF",
      extensions: [".pdf"],
      adapter: "poppler (pdftotext)",
      notes: "Native text extraction",
    },
    {
      category: "Office Documents",
      extensions: [".docx", ".odt"],
      adapter: "pandoc",
      notes: "Via pandoc conversion",
    },
    {
      category: "E-Books",
      extensions: [".epub", ".fb2"],
      adapter: "pandoc",
      notes: "Via pandoc conversion",
    },
    {
      category: "Notebooks",
      extensions: [".ipynb"],
      adapter: "pandoc",
      notes: "Jupyter notebooks",
    },
    {
      category: "Web",
      extensions: [".html", ".htm"],
      adapter: "pandoc",
      notes: "HTML to text",
    },
    {
      category: "Database",
      extensions: [".sqlite", ".db", ".sqlite3"],
      adapter: "sqlite (native)",
      notes: "Extracts all table rows",
    },
    {
      category: "Archives",
      extensions: [".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar.zst"],
      adapter: "zip / tar (native streaming)",
      notes: "Recursively searches inside archives",
    },
    {
      category: "Compressed",
      extensions: [".gz", ".bz2", ".xz", ".zst"],
      adapter: "decompress (native)",
      notes: "Single-file decompression",
    },
    {
      category: "Video (subtitles)",
      extensions: [".mkv", ".mp4", ".avi"],
      adapter: "ffmpeg",
      notes: "Extracts subtitle tracks and metadata",
    },
    {
      category: "Images (OCR)",
      extensions: [".jpg", ".jpeg", ".png"],
      adapter: "tesseract",
      notes: "Opt-in, requires enable_ocr=true. Supports: eng, chi_tra, chi_sim",
    },
    {
      category: "Plain Text",
      extensions: [".txt", ".md", ".json", ".xml", ".yaml", ".yml", ".csv", ".log", ".ts", ".js", ".py"],
      adapter: "ripgrep (native)",
      notes: "Direct text search",
    },
  ];

  const result = {
    rga_version: rgaVersion,
    total_categories: formats.length,
    formats,
    notes: {
      ocr: "OCR is disabled by default. Pass enable_ocr=true to extract_text or search_content to enable.",
      documents_dir: "Files in /data/documents are available for direct search without uploading.",
      upload: "Use rga_upload_file to upload files for processing.",
    },
  };

  return {
    content: [
      { type: "text" as const, text: JSON.stringify(result, null, 2) },
    ],
  };
}
