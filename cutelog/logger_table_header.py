import copy
import json

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QEvent
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QListWidget,
                             QListWidgetItem, QMenu, QVBoxLayout)

from .config import CONFIG


class Column:
    def __init__(self, name=None, title=None, visible=True, width=50, load=None):
        if load:
            self.load_from_string(load)
        else:
            self.name = name
            self.title = title
            self.visible = visible
            self.width = width

    def dump_to_string(self):
        d = {'name': self.name, 'title': self.title,
             'width': self.width, 'visible': self.visible}
        return json.dumps(d, ensure_ascii=False, separators=(',', ':'))

    def load_from_string(self, string):
        d = json.loads(string)
        self.name = d['name']
        self.title = d['title']
        self.visible = d['visible']
        self.width = int(d['width'])

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name}, title={self.title})"


DEFAULT_COLUMNS = [
    Column('asctime', 'Time', width=125),
    Column('name', 'Logger name', width=80),
    Column('levelname', 'Level', width=60),
    Column('levelno', '#', width=22),
    Column('funcName', 'Function', False, width=80),
    Column('pathname', 'Path', False, width=120),
    Column('filename', 'File', False, width=75),
    Column('lineno', 'Line #', False, width=35),
    Column('module', 'Module', False, width=50),
    Column('process', 'Process', False, width=40),
    Column('processName', 'Process name', False, width=80),
    Column('thread', 'Thread', False, width=100),
    Column('threadName', 'Thread name', False, width=70),
    Column('message', 'Message'),
]


class LoggerTableHeader(QObject):
    def __init__(self, header_view):
        super().__init__()
        columns = CONFIG.load_header_preset('Default')
        if not columns:
            columns = DEFAULT_COLUMNS
        self.columns = copy.deepcopy(columns)
        self.visible_columns = [c for c in self.columns if c.visible]
        self.header_view = header_view
        self.table_model = None  # will be set from within the model immediately
        self.preset_name = 'Default'
        # self.ignore_resizing = False

    def load_columns(self):
        pass

    def eventFilter(self, object, event):
        """
        The problem with headerView.sectionResized is that it gets called way
        too much, often pointlessly or in annoying ways. So I decided that
        instead I'll listen for mouse releases on the headerView and save the
        whole header whenever that event comes through the filter.

        Is this the best solution or the worst solution?
        I guess we'll never know.
        """
        if event.type() == QEvent.MouseButtonRelease:
            self.mouse_released()
            return True
        return False

    def reset_columns(self):
        self.replace_columns(copy.deepcopy(DEFAULT_COLUMNS))

    # def column_resized(self, index, old_size, new_size):
    def mouse_released(self):
        for section in range(self.header_view.count()):
            col = self.visible_columns[section]
            col.width = self.header_view.sectionSize(section)
        CONFIG.save_header_preset(self.preset_name, self.columns)

    def replace_columns(self, new_columns, preset_name='Default'):
        self.preset_name = preset_name
        self.columns = new_columns
        self.visible_columns = [c for c in self.columns if c.visible]
        self.table_model.modelReset.emit()
        CONFIG.save_header_preset(self.preset_name, self.columns)

    def __getitem__(self, index):
        return self.visible_columns[index]

    @property
    def column_count(self):
        return len(self.visible_columns)


class ColumnListItem(QListWidgetItem):
    def __init__(self, parent, column):
        super().__init__(parent)
        self.column = column

    def data(self, role):
        if role == Qt.DisplayRole:
            return self.column.title
        elif role == Qt.CheckStateRole:
            if self.column.visible:
                return Qt.Checked
            else:
                return Qt.Unchecked
        return None

    def setData(self, role, value):
        if role == Qt.CheckStateRole:
            self.column.visible = value


class HeaderEditDialog(QDialog):

    header_changed = pyqtSignal(str, list)

    def __init__(self, parent, columns):
        super().__init__(parent)

        self.columns = copy.deepcopy(columns)
        self.setupUi()

    def setupUi(self):
        self.resize(200, 400)
        self.vbox = QVBoxLayout(self)
        self.columnList = QListWidget(self)
        self.vbox.addWidget(self.columnList)

        self.columnList.setDragDropMode(QListWidget.InternalMove)
        self.columnList.setDefaultDropAction(Qt.MoveAction)
        self.columnList.setSelectionMode(QListWidget.ExtendedSelection)
        self.columnList.setAlternatingRowColors(True)
        self.columnList.installEventFilter(self)
        self.columnList.setObjectName("ColumnList")
        # self.columnList.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.columnList.customContextMenuRequested.connect(self.open_menu)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.vbox.addWidget(self.buttonBox)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.fill_column_list()

    def eventFilter(self, object, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Space or event.key() == Qt.Key_Return:
                self.toggle_selected_columns()
                return True
        return False

    def fill_column_list(self):
        for column in self.columns:
            ColumnListItem(self.columnList, column)

    def accept(self):
        result = []
        for i in range(self.columnList.count()):
            item = self.columnList.item(i)
            result.append(item.column)
        self.header_changed.emit('rearrange', result)
        self.done(0)

    def reject(self):
        self.done(0)

    def toggle_selected_columns(self):
        selected = self.columnList.selectedItems()
        for item in selected:
            value_now = item.data(Qt.CheckStateRole)
            item.setData(Qt.CheckStateRole, not value_now)
        self.columnList.reset()  # @Improvement: is there a better way to update QListWidget?

    # def load_preset(self, action):
    #     name = action.text()
    #     self.result_future(('load', name))
    #
    # def save_preset(self, action):
    #     result = []
    #     for i in range(self.columnList.count()):  # column list has to be generated here because if
    #         item = self.columnList.item(i)        # you rearrange and save, then what gets saved is
    #         result.append(item.column)            # the un-rearranged list from the table header
    #
    #     name = action.text()
    #     if action.property('new'):
    #         self.result_future(('save new', (name, result)))
    #     else:
    #         self.result_future(('save', (name, result)))

    # def open_menu(self, position):
    #     return  # @TODO: implement header presets
    #     menu = QMenu(self)
    #
    #     load_menu = QMenu('Load preset', self)
    #     save_menu = QMenu('Save preset as', self)
    #     save_new_action = save_menu.addAction('New')
    #     save_new_action.setProperty('new', True)
    #     save_menu.addSeparator()
    #
    #     presets = CONFIG.get_columns_presets()
    #     for preset in presets:
    #         load_menu.addAction(preset)
    #         save_menu.addAction(preset)
    #
    #     load_menu.triggered.connect(self.load_preset)
    #     save_menu.triggered.connect(self.save_preset)
    #
    #     menu.addMenu(load_menu)
    #     menu.addMenu(save_menu)
    #
    #     menu.popup(self.columnList.viewport().mapToGlobal(position))

    def get_selected_items(self):
        result = []
        selected = self.columnList.selectedIndexes()
        for index in selected:
            item = self.columnList.itemFromIndex(index)
            result.append(item)
        return result

    def enable_selected(self):
        selected = self.get_selected_items()
        for item in selected:
            item.setData(Qt.CheckStateRole, Qt.Checked)

    def disable_selected(self):
        selected = self.get_selected_items()
        for item in selected:
            item.setData(Qt.CheckStateRole, Qt.Unchecked)
