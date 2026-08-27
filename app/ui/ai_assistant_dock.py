"""Right-side grounded AI assistant for the desktop spreadsheet."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QHBoxLayout, QLabel, QListWidget, QMessageBox, QPlainTextEdit,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from app.services.ai_assistant import AIAnswer, AISelectionContext, SpreadsheetAIAssistant


class AIRequestThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self, assistant: SpreadsheetAIAssistant, question: str,
        context: AISelectionContext, parent=None,
    ) -> None:
        super().__init__(parent)
        self.assistant = assistant
        self.question = question
        self.context = context

    def run(self) -> None:
        try:
            self.succeeded.emit(self.assistant.ask(self.question, self.context))
        except Exception as exc:  # noqa: BLE001 - transport/config errors belong in the UI
            self.failed.emit(str(exc))


class AIAssistantDock(QDockWidget):
    """Conversation panel that exposes proposals but never applies them silently."""

    apply_requested = Signal(object)

    def __init__(
        self, context_provider: Callable[[], AISelectionContext],
        assistant: SpreadsheetAIAssistant | None = None, parent=None,
    ) -> None:
        super().__init__("AI Assistant", parent)
        self.context_provider = context_provider
        self.assistant = assistant or SpreadsheetAIAssistant()
        self.current_answer = AIAnswer("")
        self.worker: AIRequestThread | None = None
        self.setObjectName("aiAssistantDock")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setMinimumWidth(340)

        root = QWidget()
        layout = QVBoxLayout(root)
        heading = QLabel("Grounded spreadsheet copilot")
        heading.setObjectName("dialogHeading")
        layout.addWidget(heading)
        note = QLabel("Only the selected cells are sent. Suggested changes require your approval.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.transcript = QTextBrowser()
        self.transcript.setPlaceholderText("Ask for an explanation, summary, formula, or proposed cleanup.")
        layout.addWidget(self.transcript, 1)
        self.proposals = QListWidget()
        self.proposals.setMaximumHeight(150)
        self.proposals.hide()
        layout.addWidget(self.proposals)
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Ask about the current selection…")
        self.prompt.setMaximumHeight(90)
        layout.addWidget(self.prompt)
        actions = QHBoxLayout()
        self.apply_button = QPushButton("Apply proposals")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        self.send_button = QPushButton("Ask AI")
        self.send_button.clicked.connect(self._send)
        actions.addWidget(self.apply_button)
        actions.addStretch()
        actions.addWidget(self.send_button)
        layout.addLayout(actions)
        self.setWidget(root)

    def _send(self) -> None:
        question = self.prompt.toPlainText().strip()
        if not question or self.worker is not None:
            return
        try:
            context = self.context_provider()
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "AI context unavailable", str(exc))
            return
        self.transcript.append(f"You: {question}")
        self.transcript.append("AI: Working from the selected cells…")
        self.prompt.clear()
        self.send_button.setEnabled(False)
        self.worker = AIRequestThread(self.assistant, question, context, self)
        self.worker.succeeded.connect(self._received)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _received(self, answer: AIAnswer) -> None:
        self.current_answer = answer
        self.transcript.append(f"AI: {answer.message}")
        self.proposals.clear()
        for proposal in answer.proposals:
            content = proposal.formula if proposal.formula is not None else repr(proposal.value)
            self.proposals.addItem(
                f"{proposal.sheet_name}!{proposal.address} → {content}"
                + (f" — {proposal.reason}" if proposal.reason else "")
            )
        self.proposals.setVisible(bool(answer.proposals))
        self.apply_button.setEnabled(bool(answer.proposals))

    def _failed(self, detail: str) -> None:
        self.transcript.append(f"AI unavailable: {detail}")

    def _finished(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
        self.worker = None
        self.send_button.setEnabled(True)

    def _apply(self) -> None:
        if self.current_answer.proposals:
            self.apply_requested.emit(self.current_answer.proposals)

    def mark_proposals_applied(self) -> None:
        self.current_answer = AIAnswer(self.current_answer.message)
        self.proposals.clear()
        self.proposals.hide()
        self.apply_button.setEnabled(False)
