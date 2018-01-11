from PyQt5 import uic

from .config import CONFIG


uif = CONFIG.get_ui_qfile('about_dialog.ui')
AboutDialogBase = uic.loadUiType(uif)
uif.close()


class AboutDialog(*AboutDialogBase):
    def __init__(self, parent):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        super().setupUi(self)
