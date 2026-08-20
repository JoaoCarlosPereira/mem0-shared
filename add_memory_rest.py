import asyncio
from httpx import AsyncClient

async def run():
    url = "http://localhost:8765/api/v1/memories"
    token = "local"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    
    async with AsyncClient() as client:
        payload = {
            "messages": [{
                "role": "user", 
                "content": "O cliente SSE do SDK Python do MCP pode travar ao interagir localmente, exigindo kill. As operações do Kanban (tasks, workspaces) na API REST exigem atributos não mapeados no MCP (ex: claimant em /tasks/id/claim)."
            }],
            "metadata": {"project": "mem0-shared"}
        }
        r = await client.post(url, json=payload, headers=headers)
        print(r.status_code, r.text)

asyncio.run(run())
