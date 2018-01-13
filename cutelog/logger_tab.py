# import time
import asyncio
import logging
from collections import deque
from functools import partial

from PyQt5 import uic
from PyQt5.QtCore import (QAbstractItemModel, QAbstractTableModel, QEvent,
                          QModelIndex, QSortFilterProxyModel, Qt)
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QCheckBox, QHBoxLayout, QMenu, QShortcut, QStyle,
                             QTableWidgetItem, QWidget)

from .config import CONFIG
from .level_edit_dialog import LevelEditDialog
from .log_levels import LevelFilter, LogLevel
from .logger_table_header import HeaderEditDialog, LoggerTableHeader
from .text_view_dialog import TextViewDialog

uif = CONFIG.get_ui_qfile('logger.ui')
LoggerTabBase = uic.loadUiType(uif)
uif.close()

INVALID_INDEX = QModelIndex()
SearchRole = 256


class TreeNode:
    def __init__(self, parent, name):
        self.name = name
        self.parent = parent
        self.children = []

    @property
    def path(self):
        result = [self.name]
        cur_parent = self.parent
        while cur_parent.parent is not None:
            result.insert(0, cur_parent.name)
            cur_parent = cur_parent.parent
        return '.'.join(result)

    @property
    def row(self):
        if self.parent:
            return self.parent.children.index(self)
        else:
            return 0

    def __repr__(self):
        return "{}(name={}, path={})".format(self.__class__.__name__, self.name, self.path)


class LogNamespaceTreeModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root = TreeNode(None, '')
        self.registry = {'': self.root}

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        node = index.internalPointer()
        if role == Qt.DisplayRole:
            return node.name
        elif role == Qt.ToolTipRole:
            return node.path
        else:
            return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return INVALID_INDEX

        if not parent.isValid():
            parent_node = self.root
        else:
            parent_node = parent.internalPointer()

        child = parent_node.children[row]
        return self.createIndex(row, column, child)

    def parent(self, index):
        if index.isValid():
            parent = index.internalPointer().parent
            if parent:
                return self.createIndex(parent.row, 0, parent)
        return INVALID_INDEX

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return(len(self.root.children))
        else:
            node = parent.internalPointer()
            return len(node.children)

    def register_logger(self, full_name):
        if full_name in self.registry:  # if name is already registred, return it
            return self.registry[full_name]
        else:
            parts = full_name.rsplit('.', 1)  # split off the last name only
            name = parts[-1]

            if len(parts) == 1:
                parent = self.root
                parent_index = INVALID_INDEX
            else:
                parent = self.register_logger(parts[0])
                parent_index = self.createIndex(parent.row, 0, parent)

            row = len(parent.children)

            self.beginInsertRows(parent_index, row, row)
            result = TreeNode(parent, name)
            parent.children.append(result)
            self.registry[full_name] = result
            self.endInsertRows()
            return result

    def columnCount(self, parent=None):
        return 1

    def headerData(self, column, orientation, role):
        return None


class LogRecordModel(QAbstractTableModel):

    def __init__(self, parent, levels, header, max_capacity=0):
        super().__init__(parent)
        self.parent_widget = parent
        self.levels = levels
        # maxlen isn't needed here, because of how on_record has to handle max_capacity
        self.records = deque(maxlen=max_capacity if max_capacity > 0 else None)
        self.font = parent.font()
        self.date_formatter = logging.Formatter('%(asctime)s')  # to format unix timestamp as a date
        self.dark_theme = False
        self.max_capacity = max_capacity
        self.table_header = header
        self.table_header.table_model = self  # this is probably bad software practice

    def columnCount(self, index):
        return self.table_header.column_count

    def rowCount(self, index=INVALID_INDEX):
        return len(self.records)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        result = None
        record = self.records[index.row()]
        level = self.levels[record.levelno]

        if role == Qt.DisplayRole:
            column = self.table_header[index.column()]
            result = getattr(record, column.name)
        elif role == Qt.DecorationRole:
            if self.headerData(index.column()) == 'Message':
                if record.exc_text:
                    result = self.parent_widget.style().standardIcon(QStyle.SP_BrowserStop)
        elif role == Qt.FontRole:
            result = None
            styles = level.styles if not self.dark_theme else level.stylesDark
            # although there is a more efficient way of doing this,
            # this is as fast as QFont(self.font)
            result = QFont(CONFIG.logger_table_font, CONFIG.logger_table_font_size)
            if styles:
                # result = QFont(self.font)
                if 'bold' in styles:
                    result.setBold(True)
                if 'italic' in styles:
                    result.setItalic(True)
                if 'underline' in styles:
                    result.setUnderline(True)
        elif role == Qt.ForegroundRole:
            if not self.dark_theme:
                result = level.fg
            else:
                result = level.fgDark
        elif role == Qt.BackgroundRole:
            if not self.dark_theme:
                result = level.bg
            else:
                result = level.bgDark
        elif role == SearchRole:
            result = record.message
        return result

    def headerData(self, section, orientation=Qt.Horizontal, role=Qt.DisplayRole):
        result = None
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            result = self.table_header[section].title
        return result

    def add_record(self, record):
        self.trim_if_needed()
        row = len(self.records)
        self.beginInsertRows(INVALID_INDEX, row, row)
        self.date_formatter.format(record)
        self.records.append(record)
        self.endInsertRows()
        return row

    def trim_except_last_n(self, n):
        from itertools import islice
        start = len(self.records) - n
        if start < 0:
            return
        self.beginRemoveRows(INVALID_INDEX, 0, start - 1)
        new_records = deque(islice(self.records, start, None))
        self.records.clear()
        del self.records
        self.records = new_records
        self.endRemoveRows()

    def trim_if_needed(self):
        if self.max_capacity == 0 or len(self.records) == 0:
            return
        diff = len(self.records) - self.max_capacity
        if len(self.records) >= self.max_capacity:
            self.beginRemoveRows(INVALID_INDEX, 0, diff)
            while len(self.records) >= self.max_capacity:
                self.records.popleft()
            self.endRemoveRows()

    def merge_with_records(self, new_records):
        self.modelAboutToBeReset.emit()
        from itertools import chain
        from operator import attrgetter  # works faster than lambda, but not in pypy3
        new_records = deque(sorted(chain(self.records, new_records), key=attrgetter('created')))
        del self.records
        self.records = new_records
        self.modelReset.emit()

    def clear(self):
        self.records.clear()

    def get_record(self, pos):
        if type(pos) is QModelIndex:
            pos = pos.row()
        return self.records[pos]


class RecordFilter(QSortFilterProxyModel):
    def __init__(self, parent, namespace_tree, level_filter):
        super().__init__(parent)
        self.namespace_tree = namespace_tree
        self.level_filter = level_filter
        self.selection_includes_children = True
        self.search_filter = False

    def filterAcceptsRow(self, sourceRow, sourceParent):
        record = self.sourceModel().get_record(sourceRow)
        if record.levelno not in self.level_filter:
            return False
        else:
            result = True
            tindexes = self.namespace_tree.selectedIndexes()
            if len(tindexes) == 0:
                result = True
            else:
                for tindex in tindexes:
                    path = tindex.internalPointer().path
                    if path == '':
                        result = True
                    if path:
                        name = record.name
                        if name == path:
                            result = True
                        elif not self.selection_includes_children and name == path:
                            result = True
                        elif self.selection_includes_children and name.startswith('{}.'.format(path)):
                            result = True
                        else:
                            result = False
        if result and self.search_filter:
            msg = record.message
            regexp = self.filterRegExp()
            if not regexp.isEmpty():
                # print(regexp.pattern())
                return regexp.exactMatch(msg)
            else:
                if self.filterCaseSensitivity() == Qt.CaseInsensitive:
                    msg = msg.lower()
                return self.filter_string in msg
        else:
            return result
        return False

    def set_filter(self, string, regexp, wildcard, casesensitive):
        if regexp:
            self.setFilterRegExp(string)
        elif wildcard:
            self.setFilterWildcard(string)
        else:
            if not casesensitive:
                string = string.lower()
            self.filter_string = string
            self.setFilterRegExp("")

        self.search_filter = True
        self.setFilterCaseSensitivity(casesensitive)
        self.invalidateFilter()

    def clear_filter(self):
        self.search_filter = False
        self.filter_string = ""
        self.setFilterRegExp("")
        self.invalidateFilter()


class DetailTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.record = tuple()

    def columnCount(self, index):
        return 2

    def rowCount(self, index):
        return len(self.record)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ('Name', 'Value')[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            row, column = index.row(), index.column()
            if role == Qt.DisplayRole:
                return self.record[row][column]
        return None

    def clear(self):
        self.record = tuple()
        self.reset()

    def reset(self):
        self.beginResetModel()
        self.endResetModel()

    def set_record(self, record):
        record_dict = vars(record).copy()  # copy to prevent editing the actual record
        del record_dict['exc_text']
        del record_dict['exc_info']
        self.record = tuple(record_dict.items())
        self.reset()


class LoggerTab(*LoggerTabBase):
    def __init__(self, parent, name, connection, log, loop, main_window):
        super().__init__(parent)
        self.log = log.getChild(name)
        self.log.debug('Starting a logger named {}'.format(name))
        self.name = name
        self.main_window = main_window
        self.loop = loop
        self.level_filter = LevelFilter()
        self.level_filter.set_all_pass(False)
        self.filter_model_enabled = True
        self.detail_model = DetailTableModel()
        self.namespace_tree_model = LogNamespaceTreeModel()
        self.popped_out = False
        self.autoscroll = True
        self.scroll_max = 0
        self.record_count = 0
        self.monitor_count = 0  # for monitoring
        self.connections = [connection]
        self.last_status_update_time = 0

        self.search_bar_visible = CONFIG['search_open_default']
        self.search_regex = CONFIG['search_regex_default']
        self.search_casesensitive = CONFIG['search_casesensitive_default']
        self.search_wildcard = CONFIG['search_wildcard_default']

        self.search_start = 0
        self.search_filter = False
        self.setupUi()

    def setupUi(self):
        super().setupUi(self)
        self.table_header = LoggerTableHeader(self.loggerTable.horizontalHeader())
        self.record_model = LogRecordModel(self, self.level_filter.levels, self.table_header)

        self.createLevelButton.clicked.connect(self.create_level)

        self.loggerTable.setMouseTracking(False)
        self.loggerTable.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.loggerTable.verticalScrollBar().rangeChanged.connect(self.onRangeChanged)
        self.loggerTable.verticalScrollBar().valueChanged.connect(self.onScroll)
        self.loggerTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.loggerTable.customContextMenuRequested.connect(self.open_logger_table_menu)

        self.loggerTable.setStyleSheet("QTableView { border: 0px;}")

        self.loggerTable.verticalHeader().setDefaultSectionSize(CONFIG['logger_row_height'])

        self.namespaceTreeView.setModel(self.namespace_tree_model)
        self.namespaceTreeView.selectionModel().selectionChanged.connect(self.reset_master)
        self.namespaceTreeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.namespaceTreeView.customContextMenuRequested.connect(self.open_namespace_table_menu)
        self.namespace_tree_model.rowsInserted.connect(self.on_tree_rows_inserted)

        for levelno, level in self.level_filter.levels.items():
            self.add_level_to_table(level)
        self.levelsTable.doubleClicked.connect(self.level_double_clicked)
        self.levelsTable.installEventFilter(self)
        self.levelsTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.levelsTable.customContextMenuRequested.connect(self.open_levels_table_menu)

        if self.filter_model_enabled:
            self.filter_model = RecordFilter(self, self.namespaceTreeView, self.level_filter)
            self.filter_model.setSourceModel(self.record_model)
            self.loggerTable.setModel(self.filter_model)
        else:
            self.loggerTable.setModel(self.record_model)

        self.loggerTable.selectionModel().selectionChanged.connect(self.update_detail)
        self.detailTable.setModel(self.detail_model)

        self.table_header_view = header = self.loggerTable.horizontalHeader()
        header.setStretchLastSection(True)
        # header.sectionResized.connect(self.table_header.column_resized)
        header.viewport().installEventFilter(self.table_header)  # read the docstring
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.open_header_menu)

        self.searchSC = QShortcut('Ctrl+F', self)
        self.searchSC.activated.connect(self.toggle_search)
        self.searchSC.setAutoRepeat(False)

        self.searchSC_F3 = QShortcut('F3', self)
        self.searchSC_F3.activated.connect(self.search_down_or_close)
        self.searchSC_F3.setAutoRepeat(True)

        self.searchSC_Esc = QShortcut('Esc', self)
        self.searchSC_Esc.activated.connect(partial(self.set_search_visible, False))
        self.searchSC_Esc.setAutoRepeat(False)

        self.searchLine.returnPressed.connect(self.search_down)
        self.searchDownButton.clicked.connect(self.search_down)
        self.searchDownButton.setMenu(self.setup_search_button_menu())

        self.searchWidget.setVisible(self.search_bar_visible)
        self.filterButton.clicked.connect(self.filter_or_clear)
        self.filterButton.setToolTip('Adheres to the same settings as the search')

        # @NextVersion: make this happen
        self.levelButtonsLayout.setParent(None)
        self.createLevelButton.setVisible(False)
        self.presetsButton.setVisible(False)

        self.setup_internal_connections()
        self.set_columns_sizes()

    def setup_search_button_menu(self):
        smenu = QMenu(self.searchDownButton)
        action_regex = smenu.addAction('Regex')
        action_regex.setCheckable(True)
        action_regex.setChecked(self.search_regex)
        action_regex.triggered.connect(partial(setattr, self, 'search_regex'))
        action_case = smenu.addAction('Case sensitive')
        action_case.setCheckable(True)
        action_case.setChecked(self.search_casesensitive)
        action_case.triggered.connect(partial(setattr, self, 'search_casesensitive'))
        action_wild = smenu.addAction('Wildcard')
        action_wild.setCheckable(True)
        action_wild.setChecked(self.search_wildcard)
        action_wild.triggered.connect(partial(setattr, self, 'search_wildcard'))
        return smenu

    def setup_internal_connections(self):
        CONFIG.row_height_changed.connect(self.row_height_changed)

    def filter_or_clear(self):
        self.search_filter = not self.search_filter
        if self.search_filter:
            self.filterButton.setText('Clear filter')
            self.filter_model.search_filter = True
            self.filter_model.set_filter(self.searchLine.text(), self.search_regex,
                                         self.search_wildcard, self.search_casesensitive)
        else:
            self.filterButton.setText('Filter')
            self.filter_model.clear_filter()

    def set_columns_sizes(self):
        # self.table_header.ignore_resizing = True
        cols = self.table_header.visible_columns
        for i, col in enumerate(cols):
            self.table_header_view.resizeSection(i, col.width)
        # self.table_header.ignore_resizing = False

    def set_max_capacity(self, max_capacity):
        self.record_model.max_capacity = max_capacity
        self.record_model.trim_if_needed()

    def eventFilter(self, object, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Space or event.key() == Qt.Key_Return:
                self.toggle_selected_levels()
                return True
        return False

    def toggle_selected_levels(self):
        selected = self.levelsTable.selectedIndexes()
        for index in selected:
            if index.column() == 0:
                checkbox = self.levelsTable.cellWidget(index.row(), index.column()).children()[1]
                checkbox.toggle()
        self.reset_master()

    def search_down(self):
        start = self.filter_model.index(self.search_start, 0, INVALID_INDEX)
        s = self.searchLine.text()

        if not self.search_regex:
            search_flags = Qt.MatchContains
        else:
            search_flags = Qt.MatchRegExp
        if self.search_casesensitive:
            search_flags = search_flags | Qt.MatchCaseSensitive
        if self.search_wildcard:
            search_flags = search_flags | Qt.MatchWildcard

        hits = self.filter_model.match(start, SearchRole, s, 1, Qt.MatchWrap | search_flags)
        if not hits:
            self.log.warn('No matches for {}'.format(s))
            self.search_start = 0
        else:
            result = hits[0]
            self.search_start = result.row() + 1
            self.loggerTable.scrollTo(result)
            self.loggerTable.setCurrentIndex(result)

    def search_down_or_close(self):
        if self.search_bar_visible is False:
            self.set_search_visible(True)
        elif self.searchLine.text() == "":
            self.set_search_visible(False)
        else:
            self.search_down()

    def set_search_visible(self, visible):
        self.search_bar_visible = visible
        self.searchWidget.setVisible(self.search_bar_visible)
        if self.search_bar_visible:
            self.searchLine.setFocus()
        else:
            self.searchLine.clear()

    def toggle_search(self):
        self.search_bar_visible = not self.search_bar_visible
        self.set_search_visible(self.search_bar_visible)

    def on_record(self, record):
        level = self.process_level(record.levelno, record.levelname)
        record.levelname = level.levelname
        self.record_model.add_record(record)
        if self.autoscroll:
            self.loggerTable.scrollToBottom()
        self.register_logger(record.name)
        self.record_count += 1
        self.monitor_count += 1
        # self.loggerTable.resizeRowsToContents()

    def get_record(self, index):
        if self.filter_model_enabled:
            source_index = self.filter_model.mapToSource(index)
            record = self.record_model.get_record(source_index)
        else:
            record = self.record_model.get_record(index)
        return record

    def register_logger(self, name):
        self.namespace_tree_model.register_logger(name)

    def process_level(self, levelno, levelname):
        level = self.level_filter.levels.get(levelno)
        if level:
            level.msg_count += 1
            return level
        new_level = LogLevel(levelno, levelname)
        self.level_filter.add_level(new_level)
        self.add_level_to_table(new_level)
        return new_level

    def add_level_to_table(self, level):
        row_count = self.levelsTable.rowCount()
        self.levelsTable.setRowCount(row_count + 1)

        checkbox = QCheckBox()
        checkbox.setStyleSheet("QCheckBox::indicator { width: 15px; height: 15px;}")
        checkbox.toggle()
        checkbox.clicked.connect(level.set_enabled)
        checkbox.clicked.connect(self.reset_master)
        checkbox.toggled.connect(level.set_enabled)

        checkbox_layout = QHBoxLayout()
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.addWidget(checkbox)

        checkbox_widget = QWidget()
        checkbox_widget.setLayout(checkbox_layout)
        checkbox_widget.setStyleSheet("QWidget { background-color:none;}")

        self.levelsTable.setCellWidget(row_count, 0, checkbox_widget)
        self.levelsTable.setItem(row_count, 1, QTableWidgetItem(str(level.levelno)))
        self.levelsTable.setItem(row_count, 2, QTableWidgetItem(level.levelname))

        self.levelsTable.sortItems(1, Qt.SortOrder(Qt.AscendingOrder))
        self.levelsTable.resizeColumnToContents(1)

    def open_namespace_table_menu(self, position):
        menu = QMenu(self)
        include_children_action = menu.addAction("Selection includes children")
        include_children_action.setCheckable(True)
        if self.filter_model_enabled:
            include_children_action.setChecked(self.filter_model.selection_includes_children)
        else:
            include_children_action.set_enabled(False)
        include_children_action.triggered.connect(self.toggle_selection_includes_children)
        menu.popup(self.namespaceTreeView.viewport().mapToGlobal(position))

    def toggle_selection_includes_children(self, val):
        self.filter_model.selection_includes_children = val
        self.reset_master()

    def open_levels_table_menu(self, position):
        menu = QMenu(self)
        enable_all_action = menu.addAction("Enable all")
        enable_all_action.triggered.connect(self.enable_all_levels)
        disable_all_action = menu.addAction("Disable all")
        disable_all_action.triggered.connect(self.disable_all_levels)
        menu.addSeparator()
        edit_action = menu.addAction("Edit selected level")
        edit_action.triggered.connect(self.open_edit_level_dialog)
        menu.popup(self.levelsTable.viewport().mapToGlobal(position))

    def open_logger_table_menu(self, position):
        # Needed as a workaround for when the header column count is 0 and it becomes invisible
        if self.table_header.column_count == 0:
            self.open_header_menu(position)
            return
        selected = self.loggerTable.selectedIndexes()
        if not selected:
            return
        row_index = selected[0]
        record = self.get_record(row_index)
        menu = QMenu(self)
        view_message = menu.addAction("View message")
        view_message.triggered.connect(partial(self.open_text_view_dialog, row_index, False))
        if record.exc_text:
            view_traceback = menu.addAction("View traceback")
            view_traceback.triggered.connect(partial(self.open_text_view_dialog, row_index, True))
        menu.popup(self.table_header_view.viewport().mapToGlobal(position))

    def open_header_menu(self, position):
        menu = QMenu(self)
        customize_header = menu.addAction("Customize header")
        customize_header.triggered.connect(self.open_header_dialog)
        reset_header_action = menu.addAction("Reset header")
        reset_header_action.triggered.connect(self.table_header.reset_columns)
        reset_header_action.triggered.connect(self.set_columns_sizes)
        menu.popup(self.table_header_view.viewport().mapToGlobal(position))

    def open_header_dialog(self):
        d = HeaderEditDialog(self.main_window, self.table_header.columns)
        d.header_changed.connect(self.header_changed)
        d.setWindowTitle('Header editor')
        d.open()

    def header_changed(self, action, data):
        if action == 'rearrange':
            self.table_header.replace_columns(data)
        elif action == 'load':
            loaded = CONFIG.load_columns_preset(data)
            self.table_header.replace_columns(loaded)
        elif action == 'save':
            CONFIG.save_columns_preset(data, self)
        elif action == 'save new':
            pass
        self.set_columns_sizes()

    def merge_with_records(self, new_records):
        self.record_model.merge_with_records(new_records)
        for record in new_records:
            self.register_logger(record.name)
            level = self.process_level(record.levelno, record.levelname)
            record.levelname = level.levelname

    def update_detail(self, sel, desel):
        indexes = sel.indexes()
        if len(indexes) <= 0:
            self.detail_model.clear()
            return
        index = indexes[0]
        record = self.get_record(index)
        self.detail_model.set_record(record)

    def open_text_view_dialog(self, index, exception=False):
        record = self.get_record(index)
        d = TextViewDialog(self.main_window, record.exc_text if exception else record.message)
        d.setWindowModality(Qt.NonModal)
        d.setAttribute(Qt.WA_DeleteOnClose, True)
        d.setWindowTitle('Exception traceback' if exception else 'View message')
        d.open()

    def enable_all_levels(self):
        for row in range(self.levelsTable.rowCount()):
            checkbox = self.levelsTable.cellWidget(row, 0).children()[1]
            if not checkbox.isChecked():
                checkbox.setChecked(True)
        self.reset_master()

    def disable_all_levels(self):
        for row in range(self.levelsTable.rowCount()):
            checkbox = self.levelsTable.cellWidget(row, 0).children()[1]
            if checkbox.isChecked():
                checkbox.setChecked(False)
        self.reset_master()

    def set_dark_theme(self, value):
        self.record_model.dark_theme = value

    def level_double_clicked(self, index):
        row, column = index.row(), index.column()
        if column == 0:  # if you're clicking at the checkbox widget, just toggle it instead
            checkbox = self.levelsTable.cellWidget(row, column).children()[1]
            checkbox.toggle()
            self.reset_master()
        else:
            self.open_edit_level_dialog(row)

    def open_edit_level_dialog(self, row=None):
        if not row:
            selected = self.levelsTable.selectedIndexes()
            if not selected:
                return
            row = selected[0].row()
        levelno = self.levelsTable.item(row, 1).data(Qt.DisplayRole)
        level = self.level_filter.levels[int(levelno)]
        d = LevelEditDialog(self.main_window, level)
        d.setWindowModality(Qt.NonModal)
        d.setWindowTitle('Level editor')
        d.open()

    def create_level(self):
        self.log.warn('Creating level')
        d = LevelEditDialog(creating_new_level=True)
        d.setWindowModality(Qt.NonModal)
        d.setWindowTitle('Level editor')
        d.open()

    def reset_master(self, sel=None, desel=None):
        self.record_model.beginResetModel()
        self.record_model.endResetModel()
        if self.autoscroll:
            self.loggerTable.scrollToBottom()

    def onScroll(self, pos):
        if pos < self.scroll_max:
            self.autoscroll = False
        else:
            self.autoscroll = True

    def on_tree_rows_inserted(self, pindex, start, end):
        tree = self.namespaceTreeView
        tmodel = self.namespace_tree_model
        tree.expand(pindex)
        while start <= end:
            index = tmodel.index(start, 0, pindex)
            if not index.isValid():
                self.log.error('Invalid index!')
            else:
                tree.expand(index)
            start += 1

    def onRangeChanged(self, min, max):
        self.scroll_max = max

    def closeEvent(self, event=None):
        self.log.debug('Tab close event!')
        self.stop_all_connections()
        if self.popped_out:
            self.main_window.close_popped_out_logger(self)

    def add_connection(self, connection):
        self.log.debug('Adding connection "{}"'.format(connection))
        self.connections.append(connection)

    def remove_connection(self, connection):
        self.log.debug('Removing connection "{}"'.format(connection))
        self.connections.remove(connection)

    def stop_all_connections(self):
        for conn in self.connections:
            conn.tab_closed = True

    def row_height_changed(self, new_height):
        self.loggerTable.verticalHeader().setDefaultSectionSize(new_height)

    async def monitor(self):
        "Used only when benchmark parameter of LogServer is True"
        records = []
        while True:
            await asyncio.sleep(0.5)
            status = "{} rows/s".format(self.monitor_count * 2)
            if self.monitor_count == 0:
                break
            records.append(self.monitor_count)
            print(status, int(sum(records) / len(records)) * 2, 'average')
            self.main_window.set_status(status)
            self.monitor_count = 0
        print('Result:', int(sum(records) / len(records)) * 2, 'average')
