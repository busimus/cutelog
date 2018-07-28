# from qtpy.uic import loadUi
from qtpy.QtWidgets import QDialog

from .config import CONFIG
from .utils import loadUi


class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        self.ui = loadUi(CONFIG.get_ui_qfile("about_dialog.ui"), baseinstance=self)
        self.nameLabel.setText(CONFIG.full_name)
