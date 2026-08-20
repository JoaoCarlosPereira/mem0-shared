import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession
import json

async def test_ops():
    url = "http://localhost:8765/mcp/test-client/sse/test-user"
    print(f"Connecting to {url} ...")
    
    try:
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                print("\n--- 1. Testing search_catalog ---")
                try:
                    search_result = await session.call_tool(
                        "search_catalog", 
                        arguments={"kind": "skill", "limit": 1}
                    )
                    res_text = "\n".join([c.text for c in search_result.content])
                    data = json.loads(res_text)
                    first_res = data["results"][0]
                    name = first_res["name"]
                    tag = first_res.get("tag", "1.0.0")
                    namespace = first_res.get("namespace", "default")
                    
                    print(f"search_catalog result SUCCESS! Found skill: {name} (namespace: {namespace})")
                    
                    print(f"\n--- 2. Testing get_catalog_resource (name: {name}) ---")
                    try:
                        get_result = await session.call_tool(
                            "get_catalog_resource", 
                            arguments={"kind": "skill", "name": name, "tag": tag, "namespace": namespace}
                        )
                        get_text = "\n".join([c.text for c in get_result.content])
                        
                        # Just print first 200 chars to prove it worked
                        print(f"get_catalog_resource result SUCCESS! (First 200 chars):\n{get_text[:200]}...")
                    except Exception as e:
                        print(f"Error calling get_catalog_resource: {e}")
                        
                except Exception as e:
                    print(f"Error calling search_catalog: {e}")
                    
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ops())
