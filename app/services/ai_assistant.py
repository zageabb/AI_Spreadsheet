"""Grounded, proposal-only AI assistance for spreadsheet selections."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib import error, request

from app.core.coordinates import CellAddress


@dataclass(frozen=True, slots=True)
class AISettings:
    enabled: bool
    provider: str
    base_url: str
    model: str
    api_key: str
    timeout_seconds: int
    max_context_cells: int
    max_proposals: int

    @classmethod
    def from_env(cls) -> "AISettings":
        settings = cls(
            enabled=os.getenv("AI_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
            provider=os.getenv("AI_PROVIDER", "ollama").strip().lower(),
            base_url=os.getenv("AI_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/"),
            model=os.getenv("AI_MODEL", "qwen3:14b").strip(),
            api_key=os.getenv("AI_API_KEY", "").strip(),
            timeout_seconds=int(os.getenv("AI_TIMEOUT_SECONDS", "60")),
            max_context_cells=int(os.getenv("AI_MAX_CONTEXT_CELLS", "200")),
            max_proposals=int(os.getenv("AI_MAX_PROPOSALS", "50")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.provider not in {"ollama", "openai_compatible"}:
            raise ValueError("AI_PROVIDER must be 'ollama' or 'openai_compatible'.")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("AI_BASE_URL must be an HTTP or HTTPS URL.")
        if not self.model:
            raise ValueError("AI_MODEL must not be empty.")
        if self.timeout_seconds <= 0 or self.max_context_cells <= 0 or self.max_proposals <= 0:
            raise ValueError("AI timeout and context/proposal limits must be positive.")


@dataclass(frozen=True, slots=True)
class AICellContext:
    address: str
    value: Any = None
    formula: str | None = None


@dataclass(frozen=True, slots=True)
class AISelectionContext:
    workbook_name: str
    sheet_name: str
    range_ref: str
    cells: tuple[AICellContext, ...]
    truncated: bool = False

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "workbook": self.workbook_name,
            "sheet": self.sheet_name,
            "selection": self.range_ref,
            "truncated": self.truncated,
            "cells": [
                {"address": item.address, "value": item.value, "formula": item.formula}
                for item in self.cells
            ],
        }


@dataclass(frozen=True, slots=True)
class AICellProposal:
    sheet_name: str
    address: str
    value: Any = None
    formula: str | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class AIAnswer:
    message: str
    proposals: tuple[AICellProposal, ...] = field(default_factory=tuple)


class AIProvider(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return assistant response text."""


class HTTPAIProvider:
    """Small HTTP client for Ollama and OpenAI-compatible chat APIs."""

    def __init__(self, settings: AISettings) -> None:
        self.settings = settings

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if self.settings.provider == "ollama":
            endpoint = f"{self.settings.base_url}/api/chat"
            payload = {"model": self.settings.model, "messages": messages, "stream": False}
        else:
            endpoint = f"{self.settings.base_url}/v1/chat/completions"
            payload = {"model": self.settings.model, "messages": messages, "temperature": 0.1}
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        call = request.Request(
            endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with request.urlopen(call, timeout=self.settings.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"AI provider is unavailable: {exc}") from exc
        try:
            if self.settings.provider == "ollama":
                return str(result["message"]["content"])
            return str(result["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("AI provider returned an unexpected response.") from exc


class SpreadsheetAIAssistant:
    """Send bounded evidence and validate model-proposed workbook changes."""

    SYSTEM_PROMPT = """You are a grounded spreadsheet copilot. Use only the supplied selection evidence.
Explain calculations clearly. Never claim to have inspected cells outside the evidence. Never execute code,
change permissions, or modify a workbook directly. Return strict JSON with this shape:
{"message":"answer", "proposals":[{"sheet":"Sheet1","address":"A1","value":null,
"formula":"=SUM(B1:B3)","reason":"why"}]}. Proposals are optional and require user approval.
Use either value or formula for each proposal, never both. Formulas must begin with '='."""

    def __init__(self, settings: AISettings | None = None, provider: AIProvider | None = None) -> None:
        self.settings = settings or AISettings.from_env()
        self.provider = provider or HTTPAIProvider(self.settings)

    def ask(self, question: str, context: AISelectionContext) -> AIAnswer:
        if not self.settings.enabled:
            raise RuntimeError("AI assistance is disabled. Set AI_ENABLED=true to enable it.")
        if not question.strip():
            raise ValueError("Enter a question for the AI assistant.")
        prompt = json.dumps(
            {"question": question.strip(), "evidence": context.to_prompt_dict()},
            ensure_ascii=False, default=str,
        )
        return self.parse_answer(self.provider.complete(self.SYSTEM_PROMPT, prompt), context)

    def parse_answer(self, raw: str, context: AISelectionContext) -> AIAnswer:
        text = raw.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return AIAnswer(message=raw.strip() or "The AI provider returned an empty response.")
        if not isinstance(payload, dict):
            return AIAnswer(message=str(payload))
        message = str(payload.get("message") or "").strip()
        proposals: list[AICellProposal] = []
        raw_proposals = payload.get("proposals", [])
        allowed_sheets = {context.sheet_name}
        for item in raw_proposals if isinstance(raw_proposals, list) else []:
            if len(proposals) >= self.settings.max_proposals or not isinstance(item, dict):
                break
            sheet_name = str(item.get("sheet") or context.sheet_name).strip()
            if sheet_name not in allowed_sheets:
                continue
            try:
                address = CellAddress.parse(str(item.get("address") or "")).a1(False)
            except ValueError:
                continue
            formula = item.get("formula")
            if formula is not None:
                formula = str(formula)
                if not formula.startswith("="):
                    continue
            value = item.get("value")
            if formula is not None and value is not None:
                continue
            if formula is None and "value" not in item:
                continue
            if not isinstance(value, (str, int, float, bool, type(None))):
                continue
            proposals.append(AICellProposal(
                sheet_name=sheet_name, address=address, value=value, formula=formula,
                reason=str(item.get("reason") or "").strip(),
            ))
        return AIAnswer(message=message or "AI response received.", proposals=tuple(proposals))


def build_selection_context(
    workbook_name: str, sheet_name: str, range_ref: str,
    cells: list[AICellContext], max_cells: int,
) -> AISelectionContext:
    limited = tuple(cells[:max_cells])
    return AISelectionContext(
        workbook_name=workbook_name, sheet_name=sheet_name, range_ref=range_ref,
        cells=limited, truncated=len(cells) > max_cells,
    )
