"""Workbook access-management dialog for owners."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.models.workbook import Workbook
from app.permissions.service import PermissionService, SharingWorkflowService


class SharingDialog(QDialog):
    """Edit a workbook's viewer/editor list while preserving its owner."""

    def __init__(
        self,
        workbook: Workbook,
        actor_email: str,
        permission_service: PermissionService,
        parent=None,
        sharing_workflow: SharingWorkflowService | None = None,
    ) -> None:
        super().__init__(parent)
        self.workbook = workbook
        self.actor_email = actor_email
        self.permission_service = permission_service
        self.sharing_workflow = sharing_workflow or SharingWorkflowService(
            permission_service=permission_service
        )
        self.changed = False
        self.setWindowTitle(f"Share — {workbook.name}")
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Owner: {workbook.permissions.get('owner') or 'Unassigned'}"))
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["User", "Role"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        form = QFormLayout()
        self.email = QLineEdit()
        self.email.setPlaceholderText("colleague@example.com")
        self.role = QComboBox()
        self.role.addItems(["viewer", "editor"])
        form.addRow("Email", self.email)
        form.addRow("Role", self.role)
        layout.addLayout(form)

        actions = QHBoxLayout()
        grant = QPushButton("Grant or update")
        grant.clicked.connect(self._grant)
        revoke = QPushButton("Revoke selected")
        revoke.clicked.connect(self._revoke)
        transfer = QPushButton("Transfer ownership")
        transfer.clicked.connect(self._transfer)
        actions.addWidget(grant)
        actions.addWidget(revoke)
        actions.addWidget(transfer)
        actions.addStretch()
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)
        self._reload()

    def _reload(self) -> None:
        entries = self.workbook.permissions.get("shared_with", [])
        entries = entries if isinstance(entries, list) else []
        self.table.setRowCount(0)
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(entry.get("user") or "")))
            self.table.setItem(row, 1, QTableWidgetItem(str(entry.get("role") or "viewer")))

    def _grant(self) -> None:
        try:
            self.sharing_workflow.grant_access(
                self.workbook,
                actor_email=self.actor_email,
                target_email=self.email.text(),
                role=self.role.currentText(),
            )
        except (PermissionError, ValueError, OSError, RuntimeError) as exc:
            QMessageBox.warning(self, "Access not changed", str(exc))
            return
        self.changed = True
        self.email.clear()
        self._reload()

    def _revoke(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        target = self.table.item(row, 0).text()
        try:
            self.sharing_workflow.revoke_access(
                self.workbook,
                actor_email=self.actor_email,
                target_email=target,
            )
        except (PermissionError, ValueError, OSError, RuntimeError) as exc:
            QMessageBox.warning(self, "Access not changed", str(exc))
            return
        self.changed = True
        self._reload()

    def _transfer(self) -> None:
        target, accepted = QInputDialog.getText(
            self, "Transfer ownership", "New owner's email:"
        )
        if not accepted or not target.strip():
            return
        confirmation = QMessageBox.question(
            self,
            "Confirm ownership transfer",
            f"Transfer ownership of '{self.workbook.name}' to {target.strip()}?",
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        try:
            self.workbook.permissions = self.permission_service.transfer_ownership(
                self.workbook.permissions,
                actor_email=self.actor_email,
                new_owner_email=target,
            )
        except (PermissionError, ValueError) as exc:
            QMessageBox.warning(self, "Ownership not transferred", str(exc))
            return
        self.changed = True
        self.accept()
