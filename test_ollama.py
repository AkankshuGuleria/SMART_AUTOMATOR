import json, urllib.request

print("=== Test 1: Chat endpoint ===")
payload = json.dumps({
    "model": "qwen2.5:7b",
    "system": "You are a helpful assistant.",
    "prompt": "Say hello in one sentence.",
    "stream": False,
    "options": {"temperature": 0.3, "num_predict": 50},
}).encode("utf-8")
req = urllib.request.Request("http://localhost:11434/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        print("Response:", body.get("response", ""))
except Exception as e:
    print("Error:", e)

print("\n=== Test 2: Embedding endpoint ===")
payload = json.dumps({
    "model": "nomic-embed-text",
    "prompt": "test embedding",
    "options": {"num_ctx": 8192},
}).encode("utf-8")
req = urllib.request.Request("http://localhost:11434/api/embeddings", data=payload, headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        emb = body.get("embedding")
        print("Embedding length:", len(emb) if emb else "None")
        if emb is not None:
            print("First 5 values:", emb[:5])
except Exception as e:
    print("Error:", e)
