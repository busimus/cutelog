from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox, QDesktopWidget


def show_info_dialog(parent, title, text):
    show_dialog(parent, title, text, QMessageBox.Information)


def show_warning_dialog(parent, title, text):
    show_dialog(parent, title, text, QMessageBox.Warning)


def show_critical_dialog(parent, title, text):
    show_dialog(parent, title, text, QMessageBox.Critical)


def show_dialog(parent, title, text, icon):
    m = QMessageBox(parent)
    m.setWindowModality(Qt.NonModal)
    m.setText(text)
    m.setWindowTitle(title)
    m.setAttribute(Qt.WA_DeleteOnClose, True)
    m.setIcon(icon)
    m.show()
    center_widget_on_screen(m)


def center_widget_on_screen(widget):
    rect = widget.frameGeometry()
    center = QDesktopWidget().availableGeometry().center()
    rect.moveCenter(center)
    widget.move(rect.topLeft())
