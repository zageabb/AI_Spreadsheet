# Best Codex Activation Method

## Best practical approach
Store these files in the repo:
- `AGENTS.md`
- `docs/tasks.md`
- `docs/codex/*.md`

Then in Codex, start with:

```text
Read AGENTS.md and docs/tasks.md.
Use the repository architecture as the source of truth.
Execute docs/codex/03_master_scaffold_prompt.md.
Do not skip files.
Mark scaffolded features clearly.
```

## Why this works
This makes the repo itself the source of truth, so Codex can refer back to:
- build rules
- task sequence
- stage prompts
- architecture constraints

## Best discipline
After each stage:
1. Review generated changes
2. Test the repo locally if possible
3. Commit
4. Start the next stage
