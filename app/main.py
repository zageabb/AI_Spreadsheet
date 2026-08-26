"""Application entrypoint for the desktop spreadsheet app."""

from __future__ import annotations

import sys

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication, QMessageBox

from app.auth.service import create_auth_service
from app.ui.auth_dialog import LoginDialog
from app.ui.main_window import MainWindow
from app.ui.theme import CONTEXT_STUDIO_QSS


def main() -> int:
    """Launch the PySide6 desktop application."""
    load_dotenv()
    app = QApplication(sys.argv)
    app.setStyleSheet(CONTEXT_STUDIO_QSS)
    try:
        auth_service = create_auth_service()
    except ValueError as exc:
        QMessageBox.critical(None, "Authentication configuration error", str(exc))
        return 2
    login = LoginDialog(auth_service)
    if not login.exec() or login.session is None:
        return 0
    window = MainWindow(principal=login.session.principal, session_token=login.session.token)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
