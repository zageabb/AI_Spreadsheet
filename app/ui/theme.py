"""Context Studio visual language translated to Qt style sheets."""

CONTEXT_STUDIO_QSS = """
QMainWindow, QDialog { background: #f3f6fa; color: #15233a; }
QMenuBar, QToolBar { background: #071a38; color: white; border: 0; spacing: 4px; }
QMenuBar::item:selected, QToolButton:hover { background: #17345f; border-radius: 6px; }
QToolButton { color: white; padding: 7px 10px; }
QLineEdit, QComboBox { background: white; border: 1px solid #dde4ee; border-radius: 7px; padding: 7px; selection-background-color: #1768e5; }
QLineEdit:focus, QComboBox:focus { border-color: #1768e5; }
QTableView { background: white; alternate-background-color: #fbfcfe; gridline-color: #e3e8f0; border: 1px solid #dde4ee; selection-background-color: #eaf2ff; selection-color: #15233a; }
QHeaderView::section { background: #f7f9fc; color: #52657e; border: 0; border-right: 1px solid #dde4ee; border-bottom: 1px solid #dde4ee; padding: 6px; font-weight: 600; }
QTabWidget::pane { border: 1px solid #dde4ee; background: white; }
QTabBar::tab { background: #e8eef8; color: #52657e; padding: 8px 16px; border-top-left-radius: 7px; border-top-right-radius: 7px; margin-right: 2px; }
QTabBar::tab:selected { background: white; color: #174f9f; border-top: 2px solid #1768e5; }
QStatusBar { background: #071a38; color: #bec8d8; }
QPushButton { background: white; color: #15233a; border: 1px solid #dde4ee; border-radius: 7px; padding: 7px 11px; }
QPushButton:hover { background: #f7faff; border-color: #abc3e7; }
"""
