import json
import urllib.request
import urllib.error
from config import settings

cases = [
    (
        'groq',
        settings.groq_api_key,
        'https://api.groq.com/openai/v1/chat/completions',
        json.dumps({
            'model': 'llama-3.1-8b-instant',
            'messages': [{'role': 'user', 'content': 'Reply with one word: ok'}],
            'max_tokens': 16,
            'temperature': 0.2,
        }).encode('utf-8'),
        {'Content-Type': 'application/json', 'Authorization': f'Bearer {settings.groq_api_key}'},
    ),
    (
        'gemini',
        settings.gemini_api_key,
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}",
        json.dumps({
            'contents': [{'parts': [{'text': 'Reply with one word: ok'}]}],
        }).encode('utf-8'),
        {'Content-Type': 'application/json'},
    ),
]

for name, key, url, payload, headers in cases:
    if not key or key.startswith('your_'):
        print(name, 'SKIPPED: placeholder key')
        continue
    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode('utf-8', 'ignore')
            print(name, 'STATUS', resp.status)
            print(body[:2000])
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'ignore')
        print(name, 'HTTP', e.code)
        print(body[:2000])
    except Exception as e:
        print(name, 'ERR', repr(e))
