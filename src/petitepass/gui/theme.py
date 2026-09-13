"""A VS Code-inspired dark theme for the whole application.

Presentation only. This applies a single dark palette and Qt style sheet to the
``QApplication`` so every window and dialog inherits it without any of the GUI
modules needing to know the colours. Colours are pulled from the VS Code "Dark+"
default so the app feels familiar.
"""

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication, QStyleFactory

# -- VS Code "Dark+" palette ------------------------------------------------
_BG = "#1e1e1e"          # editor background
_BG_PANEL = "#252526"    # side bar / panel background
_BG_INPUT = "#3c3c3c"    # input / control background
_BG_HOVER = "#2a2d2e"    # list hover
_BORDER = "#3c3c3c"      # subtle separators
_BORDER_FOCUS = "#007acc"  # focus ring / active border (VS Code blue)
_TEXT = "#d4d4d4"        # primary foreground
_TEXT_MUTED = "#858585"  # placeholders / disabled
_SELECT = "#094771"      # active selection background
_ACCENT = "#0e639c"      # primary button
_ACCENT_HOVER = "#1177bb"
_ACCENT_PRESSED = "#0d5a8f"

_STYLESHEET = f"""
QWidget {{
    background-color: {_BG};
    color: {_TEXT};
    font-size: 13px;
}}

QDialog, QMainWindow {{
    background-color: {_BG};
}}

QLabel {{
    background: transparent;
    color: {_TEXT};
}}

QLineEdit {{
    background-color: {_BG_INPUT};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: {_SELECT};
    selection-color: #ffffff;
}}
QLineEdit:focus {{
    border: 1px solid {_BORDER_FOCUS};
}}
QLineEdit:disabled {{
    color: {_TEXT_MUTED};
}}

QPushButton {{
    background-color: {_ACCENT};
    color: #ffffff;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {_ACCENT_HOVER};
}}
QPushButton:pressed {{
    background-color: {_ACCENT_PRESSED};
}}
QPushButton:focus {{
    outline: none;
    border: 1px solid {_BORDER_FOCUS};
}}
QPushButton:disabled {{
    background-color: {_BG_INPUT};
    color: {_TEXT_MUTED};
}}

/* Compact, quieter buttons that live inside table cells. */
QPushButton[cellButton="true"] {{
    background-color: {_BG_INPUT};
    color: {_TEXT};
    padding: 3px 10px;
    font-weight: 400;
}}
QPushButton[cellButton="true"]:hover {{
    background-color: #4a4a4a;
}}
QPushButton[cellButton="true"]:pressed {{
    background-color: {_ACCENT};
    color: #ffffff;
}}

QTableWidget, QTableView {{
    background-color: {_BG};
    alternate-background-color: {_BG_PANEL};
    color: {_TEXT};
    gridline-color: {_BORDER};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    selection-background-color: {_SELECT};
    selection-color: #ffffff;
    outline: none;
}}
QTableWidget::item, QTableView::item {{
    padding: 4px 6px;
    border: none;
}}
QTableWidget::item:hover {{
    background-color: {_BG_HOVER};
}}
QTableWidget::item:selected {{
    background-color: {_SELECT};
    color: #ffffff;
}}

QHeaderView::section {{
    background-color: {_BG_PANEL};
    color: {_TEXT_MUTED};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {_BORDER};
    border-bottom: 1px solid {_BORDER};
    font-weight: 600;
}}
QTableCornerButton::section {{
    background-color: {_BG_PANEL};
    border: none;
}}

QMenu {{
    background-color: {_BG_PANEL};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {_SELECT};
    color: #ffffff;
}}
QMenu::separator {{
    height: 1px;
    background: {_BORDER};
    margin: 4px 8px;
}}

QMessageBox, QInputDialog, QFileDialog {{
    background-color: {_BG};
}}

QScrollBar:vertical {{
    background: {_BG};
    width: 14px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #424242;
    min-height: 24px;
    border-radius: 4px;
    border: 3px solid {_BG};
}}
QScrollBar::handle:vertical:hover {{
    background: #4f4f4f;
}}
QScrollBar:horizontal {{
    background: {_BG};
    height: 14px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #424242;
    min-width: 24px;
    border-radius: 4px;
    border: 3px solid {_BG};
}}
QScrollBar::handle:horizontal:hover {{
    background: #4f4f4f;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

QToolTip {{
    background-color: {_BG_PANEL};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    padding: 4px 6px;
}}
"""


def _dark_palette() -> QPalette:
    """Palette so native-drawn bits (title text, dialog chrome) match the QSS."""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(_BG))
    palette.setColor(QPalette.WindowText, QColor(_TEXT))
    palette.setColor(QPalette.Base, QColor(_BG_INPUT))
    palette.setColor(QPalette.AlternateBase, QColor(_BG_PANEL))
    palette.setColor(QPalette.Text, QColor(_TEXT))
    palette.setColor(QPalette.PlaceholderText, QColor(_TEXT_MUTED))
    palette.setColor(QPalette.Button, QColor(_ACCENT))
    palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase, QColor(_BG_PANEL))
    palette.setColor(QPalette.ToolTipText, QColor(_TEXT))
    palette.setColor(QPalette.Highlight, QColor(_SELECT))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.Link, QColor(_BORDER_FOCUS))
    disabled = QColor(_TEXT_MUTED)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, disabled)
    return palette


def apply_theme(app: QApplication) -> None:
    """Apply the dark theme to a ``QApplication`` (style, palette, style sheet)."""
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(_dark_palette())
    app.setStyleSheet(_STYLESHEET)
