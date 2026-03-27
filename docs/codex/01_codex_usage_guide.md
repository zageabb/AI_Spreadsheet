# Codex Usage Guide

## How to use these prompts
Use the prompts one at a time. Do not ask Codex to complete the whole system in one pass.

## Session starter
Use this at the start of a Codex session:

```text
Read AGENTS.md and docs/tasks.md.
Use the repository architecture as the source of truth.
Do not replace the desktop app with a web app.
Preserve the modular folder structure.
Mark scaffolded features clearly.
```

## Before each stage
Use:

```text
Read AGENTS.md and docs/tasks.md.
Execute docs/codex/<prompt-file-name>.
Only change files needed for this stage.
```

## Good working pattern
1. Run one prompt
2. Review generated files
3. Commit changes
4. Run the next prompt

## Safety correction prompt
If Codex starts drifting, use:

```text
Stay within the existing architecture and folder structure unless a change is clearly necessary.
Do not replace the desktop app with a web app.
Prefer completing the current scaffold over redesigning it.
```
