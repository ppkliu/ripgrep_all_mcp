/**
 * rga-mcp-server
 * MCP server for ripgrep-all document search and text extraction
 * Supports stdio and streamable HTTP transport
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerTools } from "./tools/register.js";

const transportMode = process.env.MCP_TRANSPORT || "stdio";

if (transportMode === "stdio") {
  const server = new McpServer({
    name: "rga-mcp-server",
    version: "2.0.0",
  });
  registerTools(server);

  const stdioTransport = new StdioServerTransport();
  await server.connect(stdioTransport);
  console.error("[rga-mcp] Running in stdio mode");
} else {
  // Streamable HTTP mode with stateful sessions
  const { randomUUID } = await import("node:crypto");
  const { default: express } = await import("express");
  const { StreamableHTTPServerTransport } = await import(
    "@modelcontextprotocol/sdk/server/streamableHttp.js"
  );

  const app = express();
  app.use(express.json());

  const port = parseInt(process.env.MCP_PORT || "3000");

  // Session store: each initialize creates a new McpServer + transport pair
  const sessions = new Map<
    string,
    { server: McpServer; transport: InstanceType<typeof StreamableHTTPServerTransport> }
  >();

  app.post("/mcp", async (req, res) => {
    const sessionId = req.headers["mcp-session-id"] as string | undefined;

    // Reuse existing session
    if (sessionId && sessions.has(sessionId)) {
      const session = sessions.get(sessionId)!;
      await session.transport.handleRequest(req, res, req.body);
      return;
    }

    // New session (triggered by initialize request)
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
      enableJsonResponse: true,
      onsessioninitialized: (id: string) => {
        sessions.set(id, { server: mcpServer, transport });
        console.error(`[rga-mcp] Session created: ${id}`);
      },
    });

    transport.onclose = () => {
      const id = transport.sessionId;
      if (id && sessions.has(id)) {
        sessions.delete(id);
        console.error(`[rga-mcp] Session closed: ${id}`);
      }
    };

    const mcpServer = new McpServer({
      name: "rga-mcp-server",
      version: "2.0.0",
    });
    registerTools(mcpServer);
    await mcpServer.connect(transport);
    await transport.handleRequest(req, res, req.body);
  });

  // GET /mcp for SSE stream (optional, for server-initiated notifications)
  app.get("/mcp", async (req, res) => {
    const sessionId = req.headers["mcp-session-id"] as string | undefined;
    if (sessionId && sessions.has(sessionId)) {
      const session = sessions.get(sessionId)!;
      await session.transport.handleRequest(req, res);
      return;
    }
    res.status(400).json({ error: "Invalid or missing session ID" });
  });

  // DELETE /mcp to close session
  app.delete("/mcp", async (req, res) => {
    const sessionId = req.headers["mcp-session-id"] as string | undefined;
    if (sessionId && sessions.has(sessionId)) {
      const session = sessions.get(sessionId)!;
      await session.transport.handleRequest(req, res, req.body);
      return;
    }
    res.status(404).json({ error: "Session not found" });
  });

  app.get("/health", (_req, res) => {
    res.json({ status: "ok", server: "rga-mcp-server", version: "2.0.0" });
  });

  app.listen(port, () => {
    console.error(`[rga-mcp] Streamable HTTP on port ${port}`);
  });
}
