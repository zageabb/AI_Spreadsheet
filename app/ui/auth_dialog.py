"""Desktop sign-in and account-registration dialog."""

from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.auth.service import AuthService, SessionPrincipal


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    """Successful desktop authentication result."""

    token: str
    principal: SessionPrincipal


class LoginDialog(QDialog):
    """Email/password sign-in with an adjacent registration workflow."""

    def __init__(self, auth_service: AuthService, parent=None) -> None:
        super().__init__(parent)
        self.auth_service = auth_service
        self.session: AuthenticatedSession | None = None
        self.setWindowTitle("Sign in — AI Spreadsheet")
        self.setMinimumWidth(430)
        self.setModal(True)

        layout = QVBoxLayout(self)
        heading = QLabel("AI Spreadsheet")
        heading.setObjectName("dialogHeading")
        layout.addWidget(heading)
        layout.addWidget(QLabel("Sign in to open and share protected workbooks."))

        tabs = QTabWidget()
        tabs.addTab(self._login_page(), "Sign in")
        tabs.addTab(self._register_page(), "Create account")
        layout.addWidget(tabs)

    def _login_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        form = QFormLayout()
        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("name@example.com")
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password.returnPressed.connect(self._sign_in)
        form.addRow("Email", self.login_email)
        form.addRow("Password", self.login_password)
        outer.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        sign_in = QPushButton("Sign in")
        sign_in.setDefault(True)
        sign_in.clicked.connect(self._sign_in)
        reset = QPushButton("Reset password")
        reset.clicked.connect(self._reset_password)
        buttons.addWidget(reset)
        buttons.addWidget(cancel)
        buttons.addWidget(sign_in)
        outer.addLayout(buttons)
        return page

    def _register_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        form = QFormLayout()
        self.register_email = QLineEdit()
        self.register_email.setPlaceholderText("name@example.com")
        self.register_password = QLineEdit()
        self.register_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.returnPressed.connect(self._register)
        form.addRow("Email", self.register_email)
        form.addRow("Password", self.register_password)
        form.addRow("Confirm", self.confirm_password)
        outer.addLayout(form)
        note = QLabel("Use at least 8 characters. Passwords are stored only as salted hashes.")
        note.setWordWrap(True)
        note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(note)
        buttons = QHBoxLayout()
        buttons.addStretch()
        create = QPushButton("Create account")
        create.clicked.connect(self._register)
        buttons.addWidget(create)
        outer.addLayout(buttons)
        return page

    def _sign_in(self) -> None:
        try:
            token = self.auth_service.login(
                self.login_email.text(), self.login_password.text()
            )
            principal = self.auth_service.validate_session(token)
            if principal is None:
                raise ValueError("The new session could not be validated.")
        except ValueError as exc:
            QMessageBox.warning(self, "Sign in failed", str(exc))
            return
        self.session = AuthenticatedSession(token, principal)
        self.accept()

    def _reset_password(self) -> None:
        dialog = PasswordResetDialog(self.auth_service, self)
        email = self.login_email.text().strip()
        if email:
            dialog.email.setText(email)
        dialog.exec()

    def _register(self) -> None:
        password = self.register_password.text()
        if password != self.confirm_password.text():
            QMessageBox.warning(self, "Registration failed", "Passwords do not match.")
            return
        try:
            self.auth_service.register_user(self.register_email.text(), password)
            token = self.auth_service.login(self.register_email.text(), password)
            principal = self.auth_service.validate_session(token)
            if principal is None:
                raise ValueError("The new session could not be validated.")
        except ValueError as exc:
            QMessageBox.warning(self, "Registration failed", str(exc))
            return
        self.session = AuthenticatedSession(token, principal)
        self.accept()


class PasswordResetDialog(QDialog):
    """Request an email token and apply it to a new local password."""

    def __init__(self, auth_service: AuthService, parent=None) -> None:
        super().__init__(parent)
        self.auth_service = auth_service
        self.setWindowTitle("Reset password")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.email = QLineEdit()
        self.email.setPlaceholderText("name@example.com")
        self.token = QLineEdit()
        self.token.setPlaceholderText("Paste the token from your reset email")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Email", self.email)
        form.addRow("Reset token", self.token)
        form.addRow("New password", self.password)
        form.addRow("Confirm", self.confirm)
        layout.addLayout(form)
        note = QLabel("Request a token, then paste it here. Tokens expire after 30 minutes by default.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QHBoxLayout()
        request_button = QPushButton("Email reset token")
        request_button.clicked.connect(self._request_token)
        apply_button = QPushButton("Set new password")
        apply_button.clicked.connect(self._apply_reset)
        buttons.addWidget(request_button)
        buttons.addStretch()
        buttons.addWidget(apply_button)
        layout.addLayout(buttons)

    def _request_token(self) -> None:
        try:
            self.auth_service.send_password_reset_email(
                self.email.text(), reset_link_base=os.getenv("APP_BASE_URL", "")
            )
        except (ValueError, OSError, RuntimeError) as exc:
            QMessageBox.warning(self, "Reset request failed", str(exc))
            return
        QMessageBox.information(self, "Reset requested", "Password reset instructions were sent.")

    def _apply_reset(self) -> None:
        if self.password.text() != self.confirm.text():
            QMessageBox.warning(self, "Reset failed", "Passwords do not match.")
            return
        try:
            self.auth_service.reset_password(
                self.email.text(), self.token.text(), self.password.text()
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Reset failed", str(exc))
            return
        QMessageBox.information(self, "Password updated", "You can now sign in with your new password.")
        self.accept()
