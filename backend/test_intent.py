from decision_engine.intent_parser import IntentParser

p = IntentParser()
tests = [
    "open browser to chatgpt.com",
    "open notepad",
    "run tests",
    "explain repository",
    "what was I working on yesterday?",
    "generate commit message",
    "resume where I left off",
    "what should I work on next?",
    "hello",
    "xyzzy unknown",
]
for t in tests:
    r = p.parse(t)
    target = (r.params or {}).get("target", "")[:40]
    print(f"{r.intent.value:32s} | target={target!r}")
