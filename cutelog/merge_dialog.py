from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QListWidgetItem, QDialogButtonBox

from .config import CONFIG

uif = CONFIG.get_ui_qfile('merge_dialog.ui')
MergeDialogBase = uic.loadUiType(uif)
uif.close()


class LoggerListItem(QListWidgetItem):
    def __init__(self, parent, name):
        super().__init__(parent)
        self.name = name

    def data(self, role):
        if role == Qt.DisplayRole:
            return self.name
        return None


class MergeDialog(*MergeDialogBase):

    # name of src tab, names of dst tabs, whether to keep connections alive or not
    merge_tabs_signal = pyqtSignal(str, list, bool)

    def __init__(self, parent, loggers):
        super().__init__(parent)

        self.loggers = loggers
        self.merge_list = []   # all tabs to be merged
        self.merge_dst = None  # tab to merge the rest of merge_list into

        self.setupUi()

    def setupUi(self):
        super().setupUi(self)
        self.loggerList.selectionModel().selectionChanged.connect(self.merge_list_changed)
        self.dstComboBox.currentTextChanged.connect(self.merge_dst_changed)
        self.ok_button = self.buttonBox.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        self.keepAliveCheckBox.setToolTip("If disabled then only the destination connection "
                                          "will still be alive after merging.")

        self.fill_logger_list()

    def fill_logger_list(self):
        for logger_name in self.loggers.keys():
            LoggerListItem(self.loggerList, logger_name)

    def merge_list_changed(self, sel, desel):
        sel = sel.indexes()
        desel = desel.indexes()
        for index in sel:
            sel_item = self.loggerList.itemFromIndex(index)
            self.merge_list.append(sel_item)
            self.dstComboBox.addItem(sel_item.name)
            self.ok_button.setEnabled(True)

        for index in desel:
            desel_item = self.loggerList.itemFromIndex(index)
            self.merge_list.remove(desel_item)
            row = self.dstComboBox.findText(desel_item.name)
            self.dstComboBox.removeItem(row)
            if self.dstComboBox.count() == 0:
                self.ok_button.setEnabled(False)

    def merge_dst_changed(self, text):
        self.merge_dst = text

    def accept(self):
        name_list = [item.name for item in self.merge_list]
        name_list.remove(self.merge_dst)
        self.merge_tabs_signal.emit(self.merge_dst, name_list, self.keepAliveCheckBox.isChecked())
        self.done(0)

    def reject(self):
        self.done(0)
