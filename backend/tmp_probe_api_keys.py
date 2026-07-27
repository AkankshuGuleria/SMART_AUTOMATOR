import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env')


def probe(name, url, payload, headers, timeout=20):
    key = os.getenv(name, '')
    if not key or key.startswith('REPLACE') or key.startswith('your') or key.lower().startswith('replace_with_'):
        print(f'{name}: SKIPPED (missing or placeholder)')
        return

    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(400).decode('utf-8', 'ignore')
            print(f'{name}: OK status={resp.status}')
            print(body.replace('\n', ' ')[:400])
    except urllib.error.HTTPError as exc:
        body = exc.read(400).decode('utf-8', 'ignore')
        print(f'{name}: HTTP {exc.code}')
        print(body.replace('\n', ' ')[:400])
    except Exception as exc:
        print(f'{name}: ERROR {type(exc).__name__}: {exc}')


probe(
    'GROQ_API_KEY',
    'https://api.groq.com/openai/v1/chat/completions',
    json.dumps({
        'model': 'llama-3.3-70b-versatile',
        'messages': [{'role': 'user', 'content': 'Say hello in one word.'}],
        'max_tokens': 16,
        'temperature': 0,
    }).encode(),
    {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {os.getenv('GROQ_API_KEY')}",
        'User-Agent': 'AUTOMATA/1.0',
    },
)

probe(
    'GEMINI_API_KEY',
    'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + os.getenv('GEMINI_API_KEY', ''),
    json.dumps({'contents': [{'role': 'user', 'parts': [{'text': 'Say hello in one word.'}]}]}).encode(),
    {'Content-Type': 'application/json'},
)

probe(
    'COHERE_API_KEY',
    'https://api.cohere.ai/v1/chat',
    json.dumps({'model': 'command-r', 'message': 'Say hello in one word.', 'max_tokens': 16, 'temperature': 0}).encode(),
    {'Content-Type': 'application/json', 'Authorization': f"Bearer {os.getenv('COHERE_API_KEY')}"},
)

probe(
    'OPENROUTER_API_KEY',
    'https://openrouter.ai/api/v1/chat/completions',
    json.dumps({'model': 'openai/gpt-4o-mini', 'messages': [{'role': 'user', 'content': 'Say hello in one word.'}], 'max_tokens': 16, 'temperature': 0}).encode(),
    {'Content-Type': 'application/json', 'Authorization': f"Bearer {os.getenv('OPENROUTER_API_KEY')}", 'HTTP-Referer': 'http://localhost:5173', 'X-Title': 'AUTOMATA'},
)

probe(
    'NVIDIA_API_KEY',
    'https://integrate.api.nvidia.com/v1/chat/completions',
    json.dumps({'model': 'nvidia/nemotron-3-ultra-550b-a55b', 'messages': [{'role': 'user', 'content': 'Say hello in one word.'}], 'max_tokens': 16, 'temperature': 0}).encode(),
    {'Content-Type': 'application/json', 'Authorization': f"Bearer {os.getenv('NVIDIA_API_KEY')}"},
)

probe(
    'MINIMAX_API_KEY',
    'https://api.minimax.chat/v1/text/chatcompletion',
    json.dumps({'model': 'glm-4', 'messages': [{'role': 'system', 'content': 'You are helpful'}, {'role': 'user', 'content': 'Say hello in one word.'}], 'max_tokens': 16, 'temperature': 0}).encode(),
    {'Content-Type': 'application/json', 'Authorization': f"Bearer {os.getenv('MINIMAX_API_KEY')}"},
)
