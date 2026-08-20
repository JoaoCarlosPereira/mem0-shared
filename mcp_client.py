import json
import urllib.request
import urllib.error

base_url = "http://localhost:8765"

def request(method, path, data=None):
    url = f"{base_url}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header('Content-Type', 'application/json')
    if data:
        req.data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "body": e.read().decode()}
    except Exception as e:
        return {"error": str(e)}

print(request("GET", "/mcp"))
print(request("GET", "/tools"))
print(request("GET", "/api/v1/memories"))
