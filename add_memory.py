import asyncio
from httpx import AsyncClient

async def run():
    url = "http://localhost:8765/mcp"
    token = "local"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    
    async with AsyncClient() as client:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "add_memories",
                "arguments": {
                    "text": "O cliente SSE do SDK Python do MCP pode travar ao testar o servidor local OpenMemory (mcp_server.py). Operações do Kanban (tasks, claim_task) podem ser testadas com sucesso via API REST (/api/v1/specs/), lembrando que o endpoint REST de claim exige 'claimant' no payload, diferente da tool MCP que usa o contexto de usuário.",
                    "project": "mem0-shared"
                }
            }
        }
        r = await client.post(url, json=payload, headers=headers)
        print(r.status_code, r.text)

asyncio.run(run())
