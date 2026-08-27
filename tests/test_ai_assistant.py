"""Tests for grounded, proposal-only spreadsheet AI assistance."""

from __future__ import annotations

import json

from app.services.ai_assistant import (
    AICellContext, AISelectionContext, AISettings, SpreadsheetAIAssistant,
    build_selection_context,
)


def _settings(**overrides):
    values = {
        "enabled": True, "provider": "ollama", "base_url": "http://localhost:11434",
        "model": "test-model", "api_key": "", "timeout_seconds": 5,
        "max_context_cells": 2, "max_proposals": 2,
    }
    values.update(overrides)
    return AISettings(**values)


class FakeProvider:
    def __init__(self, response: str):
        self.response = response
        self.user_prompt = ""

    def complete(self, _system_prompt: str, user_prompt: str) -> str:
        self.user_prompt = user_prompt
        return self.response


def test_ai_request_contains_only_bounded_selection_evidence():
    provider = FakeProvider('{"message":"Total is 30","proposals":[]}')
    assistant = SpreadsheetAIAssistant(_settings(), provider)
    context = build_selection_context(
        "Budget", "Sheet1", "A1:A3",
        [AICellContext("A1", 10), AICellContext("A2", 20), AICellContext("A3", 30)], 2,
    )
    answer = assistant.ask("What is here?", context)
    payload = json.loads(provider.user_prompt)
    assert answer.message == "Total is 30"
    assert payload["evidence"]["truncated"] is True
    assert [item["address"] for item in payload["evidence"]["cells"]] == ["A1", "A2"]
    assert all(item["address"] != "A3" for item in payload["evidence"]["cells"])


def test_ai_proposals_are_validated_and_limited_to_grounded_sheet():
    raw = json.dumps({
        "message": "Suggestions",
        "proposals": [
            {"sheet": "Sheet1", "address": "B2", "formula": "=SUM(A1:A2)", "reason": "total"},
            {"sheet": "Other", "address": "A1", "value": "not allowed"},
            {"sheet": "Sheet1", "address": "A0", "value": 1},
            {"sheet": "Sheet1", "address": "C3", "formula": "SUM(A1:A2)"},
            {"sheet": "Sheet1", "address": "D4", "value": 4},
        ],
    })
    context = AISelectionContext("Book", "Sheet1", "A1:B2", ())
    answer = SpreadsheetAIAssistant(_settings(), FakeProvider(raw)).ask("Suggest", context)
    assert [(item.address, item.formula, item.value) for item in answer.proposals] == [
        ("B2", "=SUM(A1:A2)", None), ("D4", None, 4)
    ]


def test_ai_disabled_and_non_json_responses_fail_safely():
    context = AISelectionContext("Book", "Sheet1", "A1", ())
    assistant = SpreadsheetAIAssistant(_settings(enabled=False), FakeProvider("plain explanation"))
    try:
        assistant.ask("Explain", context)
    except RuntimeError as exc:
        assert "disabled" in str(exc).lower()
    else:
        raise AssertionError("Disabled assistant unexpectedly made a request")

    enabled = SpreadsheetAIAssistant(_settings(), FakeProvider("plain explanation"))
    answer = enabled.ask("Explain", context)
    assert answer.message == "plain explanation"
    assert answer.proposals == ()
