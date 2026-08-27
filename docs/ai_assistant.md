# Grounded AI spreadsheet assistant

Phase 11 adds a right-side copilot that can explain formulas, analyse selected values, suggest formulas and propose cell changes. The deterministic workbook and formula engine remain authoritative.

## Safety model

- Only the current selection is included as evidence, capped by `AI_MAX_CONTEXT_CELLS`.
- The complete workbook, permissions, credentials and unrelated sheets are not sent.
- Provider output is treated as untrusted data and parsed through a strict response schema.
- Invalid addresses, cross-sheet proposals, malformed formulas, complex values and excess proposals are discarded.
- The assistant never writes directly. Proposed changes are listed and require an explicit confirmation.
- Read-only viewers cannot apply proposals.
- Provider outages leave the workbook fully usable and local.

## Configuration

AI assistance is off by default:

```env
AI_ENABLED=true
AI_PROVIDER=ollama
AI_BASE_URL=http://127.0.0.1:11434
AI_MODEL=qwen3:14b
AI_TIMEOUT_SECONDS=60
AI_MAX_CONTEXT_CELLS=200
AI_MAX_PROPOSALS=50
```

For an OpenAI-compatible endpoint, set `AI_PROVIDER=openai_compatible`, configure its base URL and place the token in `AI_API_KEY`. Secrets are read from the environment and are never included in workbook context.

Open **Tools → AI Assistant** or press **Ctrl+Shift+A**. Select the relevant cells before asking a question. Review every proposed change in the list before choosing **Apply proposals**.
