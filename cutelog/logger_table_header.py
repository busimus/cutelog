import copy
import json
from functools import partial

from PyQt5.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                             QInputDialog, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMenu, QVBoxLayout)

from .config import CONFIG
from .utils import show_warning_dialog


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
        return "{}(name={}, title={})".format(self.__class__.__name__, self.name, self.title)


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
        self.preset_name = CONFIG['default_header_preset']
        columns = CONFIG.load_header_preset(self.preset_name)
        if not columns:
            columns = DEFAULT_COLUMNS
        self.columns = copy.deepcopy(columns)
        self.visible_columns = [c for c in self.columns if c.visible]
        self.header_view = header_view
        self.table_model = None  # will be set from within the model immediately

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

    def mouse_released(self):
        for section in range(self.header_view.count()):
            col = self.visible_columns[section]
            col.width = self.header_view.sectionSize(section)
        CONFIG.save_header_preset(self.preset_name, self.columns)

    def reset_columns(self):
        self.replace_columns(copy.deepcopy(DEFAULT_COLUMNS), save=False)
        self.preset_name = 'Stock'

    def replace_columns(self, new_columns, save=True):
        self.columns = new_columns
        self.visible_columns = [c for c in self.columns if c.visible]
        self.table_model.modelReset.emit()
        if save:
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
        elif role == Qt.ToolTipRole:
            return self.column.name
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

    # name of the current preset, whether to set this preset as default, list of Columns
    header_changed = pyqtSignal(str, bool, list)

    def __init__(self, parent, table_header):
        super().__init__(parent)

        self.table_header = table_header
        self.default_preset_name = None
        self.preset_name = table_header.preset_name
        self.columns = copy.deepcopy(table_header.columns)
        self.setupUi()

    def setupUi(self):
        self.resize(200, 400)
        self.vbox = QVBoxLayout(self)
        self.presetLabel = QLabel("Preset: {}".format(self.preset_name), self)
        self.columnList = QListWidget(self)
        self.setAsDefaultCheckbox = QCheckBox("Set as default preset", self)
        self.vbox.addWidget(self.presetLabel)
        self.vbox.addWidget(self.columnList)
        self.vbox.addWidget(self.setAsDefaultCheckbox)

        self.columnList.setDragDropMode(QListWidget.InternalMove)
        self.columnList.setDefaultDropAction(Qt.MoveAction)
        self.columnList.setSelectionMode(QListWidget.ExtendedSelection)
        self.columnList.setAlternatingRowColors(True)
        self.columnList.installEventFilter(self)
        self.columnList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.columnList.customContextMenuRequested.connect(self.open_menu)
        self.columnList.model().rowsMoved.connect(self.read_columns_from_list)

        # for a dumb qss hack to make selected checkboxes not white on a light theme
        self.columnList.setObjectName("ColumnList")

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        self.vbox.addWidget(self.buttonBox)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.fill_column_list()
        self.set_default_checkbox()

    def eventFilter(self, object, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Space or event.key() == Qt.Key_Return:
                self.toggle_selected_columns()
                return True
        return False

    def fill_column_list(self):
        self.columnList.clear()
        for column in self.columns:
            ColumnListItem(self.columnList, column)

    def accept(self):
        self.read_columns_from_list()
        self.header_changed.emit(self.preset_name,
                                 self.setAsDefaultCheckbox.isChecked(),
                                 self.columns)
        self.done(0)

    def reject(self):
        self.done(0)

    def read_columns_from_list(self):
        new_columns = []
        for i in range(self.columnList.count()):
            item = self.columnList.item(i)
            new_columns.append(item.column)
        self.columns = new_columns

    def toggle_selected_columns(self):
        selected = self.columnList.selectedItems()
        for item in selected:
            value_now = item.data(Qt.CheckStateRole)
            item.setData(Qt.CheckStateRole, not value_now)
        self.columnList.reset()  # @Improvement: is there a better way to update QListWidget?

    def open_menu(self, position):
        menu = QMenu(self)

        preset_menu = menu.addMenu('Presets')
        preset_menu.addAction('New preset', self.new_preset_dialog)
        preset_menu.addSeparator()

        preset_names = CONFIG.get_header_presets()

        if len(preset_names) == 0:
            action = preset_menu.addAction('No presets')
            action.setEnabled(False)
        else:
            delete_menu = menu.addMenu('Delete preset')
            for name in preset_names:
                preset_menu.addAction(name, partial(self.load_preset, name))
                delete_menu.addAction(name, partial(self.delete_preset, name))

        menu.addSeparator()
        menu.addAction('New column...', self.create_new_column_dialog)

        if len(self.columnList.selectedIndexes()) > 0:
            menu.addAction('Delete selected', self.delete_selected)

        menu.popup(self.columnList.viewport().mapToGlobal(position))

    def load_preset(self, name):
        new_columns = CONFIG.load_header_preset(name)
        if not new_columns:
            return

        self.columns = new_columns
        self.preset_name = name
        self.fill_column_list()
        self.presetLabel.setText("Preset: {}".format(name))
        self.set_default_checkbox()

    def new_preset_dialog(self):
        d = QInputDialog(self)
        d.setLabelText('Enter the new name for the new preset:')
        d.setWindowTitle('Create new preset')
        d.textValueSelected.connect(self.create_new_preset)
        d.open()

    def create_new_preset(self, name):
        if name in CONFIG.get_header_presets():
            show_warning_dialog(self, "Preset creation error",
                                'Preset named "{}" already exists.'.format(name))
            return
        if len(name.strip()) == 0:
            show_warning_dialog(self, "Preset creation error",
                                'This preset name is not allowed.'.format(name))
            return

        self.preset_name = name
        self.presetLabel.setText("Preset: {}".format(name))
        CONFIG.save_header_preset(name, self.columns)
        self.setAsDefaultCheckbox.setChecked(False)

    def delete_preset(self, name):
        CONFIG.delete_header_preset(name)
        if name == self.preset_name:
            self.columns = copy.deepcopy(DEFAULT_COLUMNS)
            self.fill_column_list()

    def create_new_column_dialog(self):
        d = CreateNewColumnDialog(self)
        d.add_new_column.connect(self.add_new_column)
        d.setWindowTitle('Create new column')
        d.open()

    def add_new_column(self, name, title):
        new_column = Column(name, title)
        # if the last column is message, insert this column before it (i think it makes sense?)
        if self.columns[-1].name == 'message':
            self.columns.insert(-1, new_column)
        else:
            self.columns.append(new_column)
        self.fill_column_list()

    def set_default_checkbox(self):
        self.setAsDefaultCheckbox.setChecked(CONFIG['default_header_preset'] == self.preset_name)

    def delete_selected(self):
        selected = self.columnList.selectedItems()
        for item in selected:
            self.columnList.takeItem(self.columnList.row(item))
        self.read_columns_from_list()
        self.fill_column_list()


class CreateNewColumnDialog(QDialog):

    # name, title
    add_new_column = pyqtSignal(str, str)

    def __init__(self, parent):
        super().__init__(parent)

        self.setupUi()

    def setupUi(self):
        self.resize(300, 120)
        self.vbox = QVBoxLayout(self)
        self.nameLabel = QLabel("Name of the column:", self)
        self.nameLine = QLineEdit(self)
        self.nameLine.setPlaceholderText('threadName')
        self.titleLabel = QLabel("Title of the column:", self)
        self.titleLine = QLineEdit(self)
        self.titleLine.setPlaceholderText('Thread name')
        self.vbox.addWidget(self.nameLabel)
        self.vbox.addWidget(self.nameLine)
        self.vbox.addWidget(self.titleLabel)
        self.vbox.addWidget(self.titleLine)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.vbox.addWidget(self.buttonBox)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def accept(self):
        self.add_new_column.emit(self.nameLine.text(), self.titleLine.text())
        self.done(0)

    def reject(self):
        self.done(0)
