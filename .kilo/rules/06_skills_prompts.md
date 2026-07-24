# AUTOMATA — Prompt & Retrieval Quality Skill (SKILLS.md §5)

**Apply when writing or tuning any Bedrock prompt, or improving answer quality.**

## Checklist
- [ ] Ground factual answers strictly in retrieved memory — the prompt must explicitly instruct the model NOT to fabricate commits, files, or events not in the context
- [ ] Always pass retrieved memories with structure: table name, content, timestamp — so the model can reason about recency
- [ ] Use few-shot examples for structured outputs (morning brief bullets, commit messages)
- [ ] Separate "generated suggestion" from "recalled fact" clearly in the UI — never blur these
- [ ] Test at least **5 differently-phrased queries** per intent to ensure retrieval generalizes beyond the demo script phrasing

## Prompt templates location
`backend/ai/prompts/` — one `.txt` file per prompt type.
Planned templates (Phase 2):
- `grounded_answer.txt` — factual Q&A grounded in retrieved memories
- `morning_brief.txt` — daily brief generation
- `commit_message.txt` — commit message from diff/staged changes
- `next_task.txt` — next-step suggestion from pending TODOs

## Common failure modes to AVOID
- Prompts that let the model "fill in" plausible details when retrieval is empty — say "no memory found" instead
- Over-fitting prompts to the exact demo script phrases — breaks under real judge questions
