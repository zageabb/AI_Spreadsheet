"""Qt undo commands for worksheet state changes."""

from typing import Any, Callable

from PySide6.QtGui import QUndoCommand

from app.models.sheet import Worksheet
from app.services.worksheet_editing import restore


class WorksheetStateCommand(QUndoCommand):
    def __init__(
        self, label: str, sheet: Worksheet, before: dict[str, Any], after: dict[str, Any],
        refresh: Callable[[], None], *, already_applied: bool = True,
    ) -> None:
        super().__init__(label)
        self.sheet = sheet
        self.before = before
        self.after = after
        self.refresh = refresh
        self.already_applied = already_applied

    def undo(self) -> None:
        restore(self.sheet, self.before); self.refresh()

    def redo(self) -> None:
        if self.already_applied:
            self.already_applied = False
            return
        restore(self.sheet, self.after); self.refresh()
