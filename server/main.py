"""Collaboration server scaffold using FastAPI."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="AI Spreadsheet Collaboration Server (Scaffold)")


@app.get("/health")
def health() -> dict[str, str]:
    """Basic health endpoint for scaffold verification."""
    return {"status": "ok", "note": "Collaboration features are scaffolded."}
