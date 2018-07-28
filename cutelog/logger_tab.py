from collections import deque
from datetime import datetime
from functools import partial

from qtpy.QtCore import (QAbstractItemModel, QAbstractTableModel, QEvent,
                         QModelIndex, QSize, QSortFilterProxyModel, Qt)
from qtpy.QtGui import QBrush, QColor, QFont
from qtpy.QtWidgets import (QCheckBox, QHBoxLayout, QMenu, QShortcut, QStyle,
                            QTableWidgetItem, QWidget)

from .config import CONFIG, Exc_Indication
from .level_edit_dialog import LevelEditDialog
from .levels_preset_dialog import LevelsPresetDialog
from .log_levels import NO_LEVEL, LevelFilter, LogLevel, get_default_level
from .logger_table_header import HeaderEditDialog, LoggerTableHeader
from .text_view_dialog import TextViewDialog
from .utils import loadUi

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

    def is_descendant_of(self, node_path):
        return self.path.startswith(node_path + '.')

    def __repr__(self):
        return "{}(name={}, path={})".format(self.__class__.__name__, self.name, self.path)


class LogNamespaceTreeModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root = TreeNode(None, '')
        self.registry = {'': self.root}
        self.selected_nodes = set()

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

    def selection_changed(self, selected, deselected):
        for item in selected.indexes():
            self.selected_nodes.add(item.internalPointer())
        for item in deselected.indexes():
            self.selected_nodes.remove(item.internalPointer())


class LogRecord:
    """
    This is a simple replacement for logging.LogRecord to support non-Python logging.
    It's used to avoid creation of useless fields that logging.makeLogRecord produces,
    as well as imitate some of its behavior.
    """
    def __init__(self, logDict):
        # this is what logging.Formatter (for asctime) did previously, but it didn't delete "msg"
        self.message = logDict.get("message")
        if self.message is None:
            self.message = logDict.get("msg")

        # copying level field to levelname, if it doesn't exits already
        self.levelname = logDict.get("levelname")
        if self.levelname is None:
            self.levelname = logDict.get("level")
        if self.levelname is not None:
            self.levelname = self.levelname.upper()

        self.created = logDict.get("created")
        if self.created is None:
            self.created = logDict.get("time")
        if self.created is None or type(self.created) not in (int, float):
            self.created = datetime.now().timestamp()

        self._logDict = logDict
        self.generate_asctime()

    def __getattr__(self, name):
        try:
            return self.__dict__[name]
        except Exception:
            return self._logDict.get(name)

    def __repr__(self):
        return str(self._logDict)

    def generate_asctime(self):
        fmt = CONFIG['time_format_string']
        if fmt:
            try:
                self.asctime = datetime.fromtimestamp(self.created).strftime(fmt)
            except Exception:
                self.asctime = datetime.now().strftime(fmt)
        else:
            self.asctime = self.created


class LogRecordModel(QAbstractTableModel):

    def __init__(self, parent, levels, header, max_capacity=0):
        super().__init__(parent)
        self.parent_widget = parent
        self.levels = levels
        self.records = deque()
        self.font = parent.font()
        self.dark_theme = False
        self.max_capacity = max_capacity
        self.table_header = header
        self.extra_mode = CONFIG['extra_mode_default']

    def columnCount(self, index):
        return self.table_header.column_count

    def rowCount(self, index=INVALID_INDEX):
        return len(self.records)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        result = None
        record = self.records[index.row()]
        if getattr(record, '_cutelog', False):
            return self.data_internal(index, record, role)

        if role == Qt.DisplayRole:
            column_name = self.table_header[index.column()].name
            if self.extra_mode and column_name == "message":
                result = self.get_extra(record.message, record)
            else:
                result = getattr(record, column_name, None)
        elif role == Qt.SizeHintRole:
            if self.extra_mode and self.table_header[index.column()].name == 'message':
                return QSize(1, CONFIG.logger_row_height *
                             (1 + len(self.get_fields_for_extra(record))))
            else:
                return QSize(1, CONFIG.logger_row_height)
        elif role == Qt.DecorationRole:
            if self.table_header[index.column()].name == 'message':
                if record.exc_text:
                    mode = CONFIG['exception_indication']
                    should = mode in (Exc_Indication.MSG_ICON, Exc_Indication.ICON_AND_RED_BG)
                    if should:
                        result = self.parent_widget.style().standardIcon(QStyle.SP_BrowserStop)
        elif role == Qt.FontRole:
            level = self.levels.get(record.levelname, NO_LEVEL)
            styles = level.styles if not self.dark_theme else level.stylesDark
            result = QFont(CONFIG.logger_table_font, CONFIG.logger_table_font_size)
            if styles:
                if 'bold' in styles:
                    result.setBold(True)
                if 'italic' in styles:
                    result.setItalic(True)
                if 'underline' in styles:
                    result.setUnderline(True)
        elif role == Qt.ForegroundRole:
            level = self.levels.get(record.levelname, NO_LEVEL)
            if not self.dark_theme:
                result = level.fg
            else:
                result = level.fgDark
        elif role == Qt.BackgroundRole:
            if record.exc_text:
                mode = CONFIG['exception_indication']
                should = mode in (Exc_Indication.RED_BG, Exc_Indication.ICON_AND_RED_BG)
                if should:
                    if not self.dark_theme:
                        color = QColor(255, 180, 180)
                    else:
                        color = Qt.darkRed
                    result = QBrush(color, Qt.DiagCrossPattern)
                    return result
            level = self.levels.get(record.levelname, NO_LEVEL)
            if not self.dark_theme:
                result = level.bg
            else:
                result = level.bgDark
        elif role == SearchRole:
            result = record.message
        return result

    def data_internal(self, index, record, role):
        result = None
        if role == Qt.DisplayRole:
            if index.column() == self.columnCount(INVALID_INDEX) - 1:
                result = record._cutelog
            else:
                column = self.table_header[index.column()]
                if column.name == 'asctime':
                    result = record.asctime
        elif role == Qt.SizeHintRole:
            result = QSize(1, CONFIG.logger_row_height)
        elif role == Qt.FontRole:
            result = QFont(CONFIG.logger_table_font, CONFIG.logger_table_font_size)
        elif role == Qt.ForegroundRole:
            if not self.dark_theme:
                result = QColor(Qt.black)
            else:
                result = QColor(Qt.white)
        elif role == Qt.BackgroundRole:
            if not self.dark_theme:
                color = QColor(Qt.lightGray)
            else:
                color = QColor(Qt.darkGray)
            result = QBrush(color, Qt.BDiagPattern)
        return result

    def get_fields_for_extra(self, record):
        # this is a tiny bit slower than a set difference, but preserves order
        return [field for field in record._logDict if field not in self.table_header.visible_names]

    def get_extra(self, msg, record):
        fields = self.get_fields_for_extra(record)
        result = ["{}={}".format(field, record._logDict[field]) for field in fields]
        if msg is not None:
            result.insert(0, msg)
        return "\n".join(result)

    def headerData(self, section, orientation=Qt.Horizontal, role=Qt.DisplayRole):
        result = None
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            result = self.table_header[section].title
        return result

    def add_record(self, record, internal=False):
        if not internal:
            self.trim_if_needed()
        row = len(self.records)

        self.beginInsertRows(INVALID_INDEX, row, row)
        self.records.append(record)
        self.endInsertRows()

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
    def __init__(self, parent, namespace_tree_model, level_filter):
        super().__init__(parent)
        self.namespace_tree_model = namespace_tree_model
        self.level_filter = level_filter
        self.selection_includes_children = True
        self.search_filter = False
        self.clear_filter()

    def filterAcceptsRow(self, sourceRow, sourceParent):
        record = self.sourceModel().get_record(sourceRow)
        if record.levelname not in self.level_filter:
            return False
        else:
            result = True
            selected_nodes = self.namespace_tree_model.selected_nodes
            if len(selected_nodes) == 0:
                result = True
            else:
                for node in selected_nodes:
                    path = node.path
                    if path == '':
                        result = True
                        break
                    if path:
                        name = record.name
                        # name is None for record added by method add_conn_closed_record().
                        if name is None:
                            result = False
                        elif name == path:
                            result = True
                            break
                        elif not self.selection_includes_children and name == path:
                            result = True
                            break
                        elif self.selection_includes_children and name.startswith(path + '.'):
                            result = True
                            break
                        else:
                            result = False
        if result and self.search_filter:
            msg = record.message
            if msg is None:
                return False
            regexp = self.filterRegExp()
            if not regexp.isEmpty():
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
        record_dict = record._logDict.copy()  # copy to prevent editing the actual record
        self.record = tuple(record_dict.items())
        self.reset()


class LoggerTab(QWidget):
    def __init__(self, parent, name, connection, log, main_window):
        super().__init__(parent)
        self.log = log.getChild(name)
        self.log.debug('Starting a logger named {}'.format(name))
        self.name = name
        self.main_window = main_window
        self.level_filter = LevelFilter()
        self.filter_model_enabled = True
        self.detail_model = DetailTableModel()
        self.namespace_tree_model = LogNamespaceTreeModel()
        self.popped_out = False
        self.autoscroll = True
        self.scroll_max = 0
        self.monitor_count = 0  # for monitoring
        self.connections = []
        if connection is not None:
            self.connections.append(connection)
        self.last_status_update_time = 0
        self.extra_mode = CONFIG['extra_mode_default']

        self.search_bar_visible = CONFIG['search_open_default']
        self.search_regex = CONFIG['search_regex_default']
        self.search_casesensitive = CONFIG['search_casesensitive_default']
        self.search_wildcard = CONFIG['search_wildcard_default']

        self.search_start = 0
        self.search_filter = False

        self.setupUi()
        self.setup_shortcuts()
        self.setup_internal_connections()
        self.set_columns_sizes()

    def setupUi(self):
        self.ui = loadUi(CONFIG.get_ui_qfile('logger.ui'), baseinstance=self)
        self.table_header = LoggerTableHeader(self.loggerTable.horizontalHeader())
        self.record_model = LogRecordModel(self, self.level_filter.levels, self.table_header)

        self.loggerTable.verticalScrollBar().rangeChanged.connect(self.onRangeChanged)
        self.loggerTable.verticalScrollBar().valueChanged.connect(self.onScroll)
        self.loggerTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.loggerTable.customContextMenuRequested.connect(self.open_logger_table_menu)

        self.loggerTable.setStyleSheet("QTableView { border: 0px;}")

        self.loggerTable.verticalHeader().setDefaultSectionSize(CONFIG['logger_row_height'])

        self.namespaceTreeView.setModel(self.namespace_tree_model)
        self.namespaceTreeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.namespaceTreeView.customContextMenuRequested.connect(self.open_namespace_table_menu)
        tree_sel_model = self.namespaceTreeView.selectionModel()
        tree_sel_model.selectionChanged.connect(self.namespace_tree_model.selection_changed)
        tree_sel_model.selectionChanged.connect(self.tree_selection_changed)
        self.namespace_tree_model.rowsInserted.connect(self.on_tree_rows_inserted)

        for levelname, level in self.level_filter.levels.items():
            self.add_level_to_table(level)
        self.levelsTable.doubleClicked.connect(self.level_double_clicked)
        self.levelsTable.installEventFilter(self)
        self.levelsTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.levelsTable.customContextMenuRequested.connect(self.open_levels_table_menu)

        if self.filter_model_enabled:
            self.filter_model = RecordFilter(self, self.namespace_tree_model, self.level_filter)
            self.filter_model.setSourceModel(self.record_model)
            self.loggerTable.setModel(self.filter_model)
        else:
            self.loggerTable.setModel(self.record_model)

        self.loggerTable.selectionModel().selectionChanged.connect(self.update_detail)
        self.detailTable.setModel(self.detail_model)

        self.table_header_view = header = self.loggerTable.horizontalHeader()
        header.setStretchLastSection(True)
        self.loggerTable.resizeColumnsToContents()
        header.viewport().installEventFilter(self.table_header)  # read the docstring
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.open_header_menu)

        self.searchLine.returnPressed.connect(self.search_down)
        self.searchDownButton.clicked.connect(self.search_down)
        self.searchDownButton.setMenu(self.setup_search_button_menu())

        self.searchWidget.setVisible(self.search_bar_visible)
        self.filterButton.clicked.connect(self.filter_or_clear)
        self.filterButton.setToolTip('Adheres to the same settings as the search')

    def setup_shortcuts(self):
        self.searchSC_Home = QShortcut('Home', self)
        self.searchSC_Home.activated.connect(partial(self.loggerTable.selectRow, 0))
        self.searchSC_Home.setAutoRepeat(False)

        self.searchSC_End = QShortcut('End', self)
        self.searchSC_End.activated.connect(self.select_last_row)
        self.searchSC_End.setAutoRepeat(False)

        self.searchSC = QShortcut('Ctrl+F', self)
        self.searchSC.activated.connect(self.toggle_search)
        self.searchSC.setAutoRepeat(False)

        self.searchSC_F3 = QShortcut('F3', self)
        self.searchSC_F3.activated.connect(self.search_down_or_close)
        self.searchSC_F3.setAutoRepeat(True)

        self.searchSC_Esc = QShortcut('Esc', self)
        self.searchSC_Esc.activated.connect(partial(self.set_search_visible, False))
        self.searchSC_Esc.setAutoRepeat(False)

    def setup_search_button_menu(self):
        smenu = QMenu(self.searchDownButton)
        action_regex = smenu.addAction('Regex')
        action_regex.setCheckable(True)
        action_regex.setChecked(self.search_regex)
        # PySide2 doesn't like functools.partial(setattr, ...)
        action_regex.triggered.connect(self.set_search_regex)
        action_case = smenu.addAction('Case sensitive')
        action_case.setCheckable(True)
        action_case.setChecked(self.search_casesensitive)
        action_case.triggered.connect(self.set_search_casesensitive)
        action_wild = smenu.addAction('Wildcard')
        action_wild.setCheckable(True)
        action_wild.setChecked(self.search_wildcard)
        action_wild.triggered.connect(self.set_search_wildcard)
        return smenu

    def set_search_regex(self, enabled):
        self.search_regex = enabled

    def set_search_casesensitive(self, enabled):
        self.search_casesensitive = enabled

    def set_search_wildcard(self, enabled):
        self.search_wildcard = enabled

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
            self.invalidate_filter(resize_rows=True)

    def set_columns_sizes(self):
        cols = self.table_header.visible_columns
        for i, col in enumerate(cols):
            self.table_header_view.resizeSection(i, col.width)

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
        self.invalidate_filter(resize_rows=True)

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
        # these 2 lines are for clearing selection when you press Esc with the search bar hidden
        if not self.search_bar_visible and not visible:
            self.loggerTable.clearSelection()

        self.search_bar_visible = visible
        self.searchWidget.setVisible(self.search_bar_visible)
        if self.search_bar_visible:
            self.searchLine.setFocus()
        else:
            self.searchLine.clear()

    def toggle_search(self):
        self.set_search_visible(not self.search_bar_visible)

    def on_record(self, record):
        levelname = record.levelname
        if levelname:
            self.process_level(levelname)
        self.record_model.add_record(record)
        if record.name:
            self.register_logger(record.name)
        self.monitor_count += 1

        self.loggerTable.resizeRowToContents(self.filter_model.rowCount() - 1)
        if self.autoscroll:
            self.loggerTable.scrollToBottom()

    def add_conn_closed_record(self, conn):
        record = LogRecord({'_cutelog': 'Connection {} closed'.format(conn.conn_id)})
        self.on_record(record)

    def get_record(self, index):
        if self.filter_model_enabled:
            source_index = self.filter_model.mapToSource(index)
            record = self.record_model.get_record(source_index)
        else:
            record = self.record_model.get_record(index)
        return record

    def register_logger(self, name):
        self.namespace_tree_model.register_logger(name)

    def process_level(self, levelname):
        levelname = levelname.upper()
        level = self.level_filter.levels.get(levelname)
        if level:
            return level
        new_level = LogLevel(levelname)
        new_level.copy_from(get_default_level(levelname))
        self.level_filter.set_level(new_level)
        self.add_level_to_table(new_level)
        return new_level

    def add_level_to_table(self, level):
        row_count = self.levelsTable.rowCount()
        self.levelsTable.setRowCount(row_count + 1)

        checkbox_widget = QWidget(self.levelsTable)
        checkbox_widget.setStyleSheet("QWidget { background-color:none;}")

        checkbox = QCheckBox()
        checkbox.setStyleSheet("QCheckBox::indicator { width: 15px; height: 15px;}")
        checkbox.setChecked(level.enabled)
        checkbox.clicked.connect(level.set_enabled)
        checkbox.clicked.connect(self.level_show_changed)
        checkbox.toggled.connect(level.set_enabled)

        checkbox_layout = QHBoxLayout()
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.addWidget(checkbox)
        checkbox_widget.setLayout(checkbox_layout)

        self.levelsTable.setCellWidget(row_count, 0, checkbox_widget)
        self.levelsTable.setItem(row_count, 1, QTableWidgetItem(level.levelname))
        self.levelsTable.resizeColumnToContents(1)

    def open_namespace_table_menu(self, position):
        menu = QMenu(self)
        include_children_action = menu.addAction("Selection includes children")
        include_children_action.setCheckable(True)
        if self.filter_model_enabled:
            include_children_action.setChecked(self.filter_model.selection_includes_children)
        else:
            include_children_action.setEnabled(False)
        include_children_action.triggered.connect(self.toggle_selection_includes_children)
        menu.popup(self.namespaceTreeView.viewport().mapToGlobal(position))

    def toggle_selection_includes_children(self, val):
        self.filter_model.selection_includes_children = val
        self.invalidate_filter(resize_rows=True)

    def open_levels_table_menu(self, position):
        menu = QMenu(self)
        enable_all_action = menu.addAction("Enable all")
        enable_all_action.triggered.connect(self.enable_all_levels)
        disable_all_action = menu.addAction("Disable all")
        disable_all_action.triggered.connect(self.disable_all_levels)
        menu.addSeparator()
        if self.levelsTable.selectedIndexes():
            edit_action = menu.addAction("Edit selected level")
            edit_action.triggered.connect(self.open_level_edit_dialog)
        presets_dialog_action = menu.addAction("Presets")
        presets_dialog_action.triggered.connect(self.open_levels_preset_dialog)
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
        menu.popup(self.table_header_view.viewport().mapToGlobal(position))

    def open_header_dialog(self):
        d = HeaderEditDialog(self.main_window, self.table_header)
        d.header_changed.connect(self.header_changed)
        d.setWindowTitle('Header editor')
        d.open()

    def header_changed(self, preset_name, set_as_default, columns):
        self.table_header.preset_name = preset_name
        if set_as_default:
            CONFIG.set_option('default_header_preset', preset_name)
        CONFIG.save_header_preset(preset_name, columns)
        self.table_header.replace_columns(columns)
        self.record_model.modelReset.emit()
        self.set_columns_sizes()
        if self.extra_mode:
            self.loggerTable.resizeRowsToContents()

    def merge_with_records(self, new_records):
        self.record_model.merge_with_records(new_records)
        for record in new_records:
            if record._cutelog is not None:
                continue
            if record.name:
                self.register_logger(record.name)
            if record.levelname:
                level = self.process_level(record.levelname)
                record.levelname = level.levelname
        self.invalidate_filter(resize_rows=True)

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
        self.level_show_changed(True)

    def disable_all_levels(self):
        for row in range(self.levelsTable.rowCount()):
            checkbox = self.levelsTable.cellWidget(row, 0).children()[1]
            if checkbox.isChecked():
                checkbox.setChecked(False)
        self.level_show_changed(False)

    def set_dark_theme(self, enabled):
        self.record_model.dark_theme = enabled

    def set_extra_mode(self, enabled):
        self.extra_mode = enabled
        self.record_model.extra_mode = enabled
        self.loggerTable.resizeRowsToContents()

    def level_double_clicked(self, index):
        row, column = index.row(), index.column()
        if column == 0:  # if you're clicking at the checkbox widget, just toggle it instead
            checkbox = self.levelsTable.cellWidget(row, column).children()[1]
            checkbox.toggle()
            self.level_show_changed(checkbox.isChecked())
        else:
            self.open_level_edit_dialog(row)

    def open_level_edit_dialog(self, row=None):
        if not row:
            selected = self.levelsTable.selectedIndexes()
            if not selected:
                return
            row = selected[0].row()
        levelname = self.levelsTable.item(row, 1).data(Qt.DisplayRole)
        level = self.level_filter.levels[levelname]
        d = LevelEditDialog(self.main_window, level)
        d.level_changed.connect(self.level_changed)
        d.setWindowModality(Qt.NonModal)
        d.setWindowTitle('Level editor')
        d.open()

    def open_levels_preset_dialog(self):
        preset_name = self.level_filter.preset_name
        d = LevelsPresetDialog(self.main_window, preset_name, self.level_filter.levels)
        d.levels_changed.connect(self.levels_changed)
        d.setWindowTitle('Header editor')
        d.open()

    def level_changed(self, level):
        self.level_filter.set_level(level)
        CONFIG.save_levels_preset(self.level_filter.preset_name, self.level_filter.levels)

    def levels_changed(self, preset_name, set_as_default, levels):
        self.level_filter.preset_name = preset_name
        if set_as_default:
            CONFIG.set_option('default_levels_preset', preset_name)
        self.level_filter.merge_with(levels)
        self.regen_levels_table(self.level_filter.levels)
        CONFIG.save_levels_preset(preset_name, levels)
        self.invalidate_filter(resize_rows=True)

    def regen_levels_table(self, levels):
        self.levelsTable.clearContents()
        self.levelsTable.setRowCount(0)
        for levelname in levels:
            level = levels[levelname]
            self.add_level_to_table(level)

    def tree_selection_changed(self, sel, desel):
        # Problem: when RecordFilter un-hides a row, that row forgets its size.
        # This creates major problems in extra mode.
        #
        # The obvious solution is to use ResizeToContents mode on the vertical
        # header of the table and let Qt handle it. But it slows down insertions
        # to a halt, but it also doesn't have any speed benefits of this approach.
        #
        # So, the second best solution is to force a resize only when rows can
        # definitely reappear. The drawback is code bloat, the benefit is speed
        # in certain cases
        cur_sel = self.namespace_tree_model.selected_nodes
        sel = [i.internalPointer() for i in sel.indexes()]
        desel = [i.internalPointer() for i in desel.indexes()]
        prev_sel = cur_sel.difference(sel)
        prev_sel = prev_sel.union(desel)
        # print('prev:', prev_sel)
        # print('cur :', cur_sel)

        resize_rows = False
        # empty filter, resizing needed
        if len(cur_sel) == 0:
            resize_rows = True
        # filter can only converge, no resizing needed
        elif len(prev_sel) == 0:
            resize_rows = False
        else:
            # if selection includes children, and at least one currently
            # selected node is not a descendant of a previously selected
            # node, then resizing is needed
            if self.filter_model.selection_includes_children:
                for node in cur_sel:
                    if not any([node.is_descendant_of(pnode.path) for pnode in prev_sel]):
                        resize_rows = True
                        break
            # if selection doesn't include children, records can re-appear
            # when a currently selected node wasn't selected before
            else:
                for node in cur_sel:
                    if node not in prev_sel:
                        resize_rows = True
                        break

        self.log.debug('resize_rows = {}'.format(resize_rows))
        self.invalidate_filter(resize_rows=resize_rows)

    def level_show_changed(self, val):
        # resize_rows is only needed when rows get un-hidden, because they forget their size
        self.invalidate_filter(resize_rows=val)

    def invalidate_filter(self, resize_rows=True):
        self.filter_model.invalidateFilter()
        # resizeRowsToContents is very slow, so it's best to try to do it only when necessary
        if resize_rows:
            self.loggerTable.resizeRowsToContents()
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
        self.add_conn_closed_record(connection)

    def destroy(self):
        for conn in self.connections:
            conn.tab_closed = True
        self.record_model.records.clear()

    def row_height_changed(self, new_height):
        self.log.info("new height = {}".format(new_height))
        self.loggerTable.verticalHeader().setDefaultSectionSize(new_height)
        self.loggerTable.resizeRowsToContents()

    def select_last_row(self):
        row = self.record_model.rowCount()
        self.loggerTable.selectRow(row - 1)
