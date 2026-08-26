"""Desktop sign-in and account-registration dialog."""

from __future__ import annotations

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
