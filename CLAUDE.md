# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
npm install             # Install dependencies
npm run build           # Compile TypeScript (tsc → dist/)
npm start               # Run MCP server (stdio mode)
npm run dev             # Dev mode with watch (tsx)
npm test                # Run all tests (63 tests, 7 suites)
```

Run a single test file:
```bash
NODE_OPTIONS='--experimental-vm-modules' npx jest --config jest.config.js testcase/mcp-server.test.ts
```

Docker:
```bash
npm run docker:build                                    # docker compose build
npm run docker:up                                       # docker compose up -d (HTTP mode, default)
docker compose -f docker-compose.stdio.yaml up -d       # stdio mode
curl http://localhost:30003/health                      # verify HTTP mode
```

## Architecture

MCP (Model Context Protocol) server wrapping **ripgrep-all (rga)** for document search and text extraction. Exposes 5 tools via the MCP SDK. Supports dual transport: stdio (default) and streamable HTTP with stateful sessions.

### Transport Layer

`src/index.ts` selects transport based on `MCP_TRANSPORT` env var:
- **stdio** (default): `StdioServerTransport` — used by Claude Code, OpenCode, Agno MCPTools
- **streamable-http**: Express server with `StreamableHTTPServerTransport` — stateful sessions via `mcp-session-id` header, each `initialize` creates a new McpServer + transport pair stored in a `Map`. Endpoints: `POST /mcp`, `GET /mcp` (SSE), `DELETE /mcp` (close session), `GET /health`. Uses `enableJsonResponse: true` for curl-friendly JSON output.

### Tool Registration

`src/tools/register.ts` registers 5 tools using `server.tool()` + zod schemas:

| Tool | Implementation | External binary |
|------|---------------|-----------------|
| `rga_upload_file` | `upload.ts` | none (fs only) |
| `rga_extract_text` | `extract.ts` | `rga-preproc` (or direct read for plaintext) |
| `rga_search_content` | `search.ts` | `rga --json` |
| `rga_list_supported_formats` | `formats.ts` | none (hardcoded list) |
| `rga_list_documents` | `list-documents.ts` | none (fs only) |

Each tool function returns `{ content: [{ type: "text", text: string }] }` or `{ isError: true, content: [...] }`.

### Key Design Decisions

- **Plaintext fallback**: `extract.ts` has a `PLAINTEXT_EXTENSIONS` set. Files matching these extensions are read directly with `fs.readFile` because `rga-preproc` has no adapter for plain text and will error.
- **Token estimation**: `src/utils/tokens.ts` uses character-based estimation (CJK-aware, no tiktoken dependency). CJK chars count as ~1.5 tokens, ASCII as ~4 chars per token.
- **File resolution**: `extract.ts` and `search.ts` look for files first in `UPLOAD_DIR`, then in `DOCUMENTS_DIR`.
- **upload.ts env access**: Uses getter functions (`getUploadDir()`, `getMaxSize()`) instead of module-level constants so tests can override `process.env` at runtime.
- **list-documents.ts**: Caps recursive depth at 5 levels and total entries at 1000. Skips hidden files and `.meta.json`. Path traversal protection via `path.resolve` check.

### Legacy Code

`src/tools/registry.ts`, `src/tools/handler.ts`, and `src/integrations/agno-agent.ts` are v1 remnants kept for backward compatibility. The v2 tool system is entirely in `register.ts` + individual tool files.

## Testing

Tests live in `testcase/` (not `__tests__`). Jest is configured for ESM via `ts-jest/presets/default-esm` in `jest.config.js`.

- **Unit tests**: `tokens.test.ts`, `formats.test.ts`, `upload.test.ts`, `tool-registry.test.ts`, `tool-handler.test.ts`, `rga-executor.test.ts`
- **Integration test**: `mcp-server.test.ts` — spawns a real MCP server process, connects via `StdioClientTransport`, exercises all 5 tools end-to-end
- **Agno tests**: `testcase/agno/test_agno_rga.py` — Python, requires `pip install agno anthropic`
- **Agno QA workflow**: `testcase/agno/document_qa_workflow.py` — Python, uses litellm + Agno MCPTools over HTTP to auto-generate questions and test agent Q&A. Requires `uv venv && uv pip install -e ".[dev]"` in `testcase/agno/`.

ESM quirk: jest config must be `.js` (not `.ts`) since ts-node is not installed. The `--experimental-vm-modules` flag is required.

## Docker

Two compose files:
- `docker-compose.yaml` — HTTP mode (default), port mapping `30003:3000`, `MCP_TRANSPORT=streamable-http`
- `docker-compose.stdio.yaml` — stdio mode (`stdin_open: true`, `tty: true`)

The Dockerfile is a multi-stage build (node:22-bookworm-slim) that installs all rga adapter dependencies: poppler-utils, pandoc, ffmpeg, tesseract-ocr (eng/chi-tra/chi-sim), and rga v1.0.0-alpha.5. Mount documents at `/data/documents:ro`.

## Documentation

Docs are organized under `docs/`:
- `docs/docker_usage_guide.md` — primary usage guide (Docker-first)
- `docs/getting-started/` — onboarding, quick start, index
- `docs/technical-reference/` — API, file manifest, project summary
- `docs/deployment/` — advanced deployment (local dev, Claude Desktop)
- `docs/integration/` — Agno Agent, OpenCode integration
- `docs/architecture/` — system design, completion report

## Project Language

Code comments and docs are primarily in Traditional/Simplified Chinese. Commit messages and code identifiers are in English.
