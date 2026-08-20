import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

async function run() {
  const transport = new StdioClientTransport({
    command: "python3",
    args: ["openmemory/api/mcp_server.py"]
  });
  
  const client = new Client({ name: "test-client", version: "1.0.0" }, { capabilities: {} });
  
  await client.connect(transport);
  
  const tools = await client.listTools();
  console.log("Available tools:", tools.tools.map(t => t.name));
  
  // Test search_catalog
  try {
    const result = await client.callTool({
      name: "search_catalog",
      arguments: { kind: "skill" }
    });
    console.log("search_catalog result:", result);
  } catch (e) {
    console.error("search_catalog failed:", e.message);
  }
  
  await client.close();
}

run().catch(console.error);
