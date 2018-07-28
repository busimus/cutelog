from qtpy.QtCore import Signal
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QListWidget, QVBoxLayout


class PopInDialog(QDialog):

    pop_in_tabs = Signal(list)

    def __init__(self, parent, loggers):
        super().__init__(parent)
        self.loggers = loggers
        self.setupUi()

    def setupUi(self):
        self.resize(200, 320)
        self.vbox = QVBoxLayout(self)
        self.listWidget = QListWidget(self)
        self.listWidget.setSelectionMode(self.listWidget.MultiSelection)
        self.listWidget.selectionModel().reset()
        self.vbox.addWidget(self.listWidget)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.vbox.addWidget(self.buttonBox)

        self.buttonBox.accepted.connect(self.accept)
        self.listWidget.doubleClicked.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.fill_logger_list()

    def fill_logger_list(self):
        for logger in self.loggers:
            if logger.popped_out:
                self.listWidget.addItem(logger.name)
        self.listWidget.setCurrentRow(0)

    def accept(self, index=None):
        names = []
        if index is not None:
            item = self.listWidget.itemFromIndex(index)
            names.append(item.text())
        else:
            for item in self.listWidget.selectedItems():
                names.append(item.text())
        if len(names) > 0:
            self.pop_in_tabs.emit(names)
        self.done(0)

    def reject(self):
        self.done(0)
