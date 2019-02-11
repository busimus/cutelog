from qtpy.QtCore import QFile, Qt, QTextStream
from qtpy.QtWidgets import (QFileDialog, QInputDialog, QMainWindow, QMenuBar,
                            QStatusBar, QTabWidget)

from .about_dialog import AboutDialog
from .config import CONFIG
from .listener import LogServer
from .logger_tab import LoggerTab, LogRecord
from .merge_dialog import MergeDialog
from .pop_in_dialog import PopInDialog
from .settings_dialog import SettingsDialog
from .utils import (center_widget_on_screen, show_critical_dialog,
                    show_warning_dialog)


class MainWindow(QMainWindow):

    def __init__(self, log, app):
        self.log = log.getChild('Main')
        self.app = app
        super().__init__()

        self.dark_theme = CONFIG['dark_theme_default']
        self.single_tab_mode = CONFIG['single_tab_mode_default']

        self.loggers_by_name = {}  # name -> LoggerTab
        self.popped_out_loggers = {}

        self.server_running = False
        self.shutting_down = False

        self.setupUi()
        self.start_server()

    def setupUi(self):
        self.resize(800, 600)
        self.setWindowTitle('cutelog')

        self.loggerTabWidget = QTabWidget(self)
        self.loggerTabWidget.setTabsClosable(True)
        self.loggerTabWidget.setMovable(True)
        self.loggerTabWidget.setTabBarAutoHide(True)
        self.loggerTabWidget.currentChanged.connect(self.change_actions_state)
        self.setCentralWidget(self.loggerTabWidget)

        self.statusbar = QStatusBar(self)
        self.setStatusBar(self.statusbar)

        self.setup_menubar()
        self.setup_action_triggers()
        self.setup_shortcuts()

        self.loggerTabWidget.tabCloseRequested.connect(self.close_tab)

        self.reload_stylesheet()
        self.restore_geometry()

        self.show()

    def setup_menubar(self):
        self.menubar = QMenuBar(self)
        self.setMenuBar(self.menubar)

        # File menu
        self.menuFile = self.menubar.addMenu("File")
        self.actionLoadRecords = self.menuFile.addAction('Load records')
        self.actionSaveRecords = self.menuFile.addAction('Save records')
        self.menuFile.addSeparator()
        self.actionDarkTheme = self.menuFile.addAction('Dark theme')
        self.actionDarkTheme.setCheckable(True)
        self.actionDarkTheme.setChecked(self.dark_theme)
        self.actionSingleTab = self.menuFile.addAction('Single tab mode')
        self.actionSingleTab.setCheckable(True)
        self.actionSingleTab.setChecked(self.single_tab_mode)
        # self.actionReloadStyle = self.menuFile.addAction('Reload style')
        self.actionSettings = self.menuFile.addAction('Settings')
        self.menuFile.addSeparator()
        self.actionQuit = self.menuFile.addAction('Quit')

        # Tab menu
        self.menuTab = self.menubar.addMenu("Tab")
        self.actionCloseTab = self.menuTab.addAction('Close')
        self.actionPopOut = self.menuTab.addAction('Pop out')
        self.actionRenameTab = self.menuTab.addAction('Rename')
        self.menuTab.addSeparator()
        self.actionPopIn = self.menuTab.addAction('Pop in tabs...')
        self.actionMergeTabs = self.menuTab.addAction('Merge tabs...')
        self.menuTab.addSeparator()
        self.actionExtraMode = self.menuTab.addAction('Extra mode')
        self.actionExtraMode.setCheckable(True)

        # Server menu
        self.menuServer = self.menubar.addMenu("Server")
        self.actionRestartServer = self.menuServer.addAction('Restart server')
        self.actionStartStopServer = self.menuServer.addAction('Stop server')

        # Records menu
        self.menuRecords = self.menubar.addMenu("Records")
        self.actionTrimTabRecords = self.menuRecords.addAction('Trim records')
        self.actionSetMaxCapacity = self.menuRecords.addAction('Set max capacity')

        # Help menu
        self.menuHelp = self.menubar.addMenu("Help")
        self.actionAbout = self.menuHelp.addAction("About cutelog")

        self.change_actions_state()  # to disable all logger actions, since they don't function yet

    def setup_action_triggers(self):
        # File menu
        self.actionLoadRecords.triggered.connect(self.open_load_records_dialog)
        self.actionSaveRecords.triggered.connect(self.open_save_records_dialog)
        self.actionDarkTheme.toggled.connect(self.toggle_dark_theme)
        self.actionSingleTab.triggered.connect(self.set_single_tab_mode)
        # self.actionReloadStyle.triggered.connect(self.reload_stylesheet)
        self.actionSettings.triggered.connect(self.settings_dialog)
        self.actionQuit.triggered.connect(self.shutdown)

        # Tab meny
        self.actionCloseTab.triggered.connect(self.close_current_tab)
        self.actionPopOut.triggered.connect(self.pop_out_tab)
        self.actionRenameTab.triggered.connect(self.rename_tab_dialog)
        self.actionPopIn.triggered.connect(self.pop_in_tabs_dialog)
        self.actionMergeTabs.triggered.connect(self.merge_tabs_dialog)
        self.actionExtraMode.triggered.connect(self.toggle_extra_mode)

        # Server menu
        self.actionRestartServer.triggered.connect(self.restart_server)
        self.actionStartStopServer.triggered.connect(self.start_or_stop_server)

        # Records menu
        self.actionTrimTabRecords.triggered.connect(self.trim_records_dialog)
        self.actionSetMaxCapacity.triggered.connect(self.max_capacity_dialog)

        # About menu
        self.actionAbout.triggered.connect(self.about_dialog)

    def change_actions_state(self, index=None):
        logger, _ = self.current_logger_and_index()
        # if there are no loggers in tabs, these actions will be disabled:
        actions = [self.actionCloseTab, self.actionExtraMode, self.actionPopOut,
                   self.actionRenameTab, self.actionPopIn,
                   self.actionTrimTabRecords, self.actionSetMaxCapacity, self.actionSaveRecords]

        if not logger:
            for action in actions:
                action.setDisabled(True)
            self.actionExtraMode.setChecked(False)
            if len(self.popped_out_loggers) > 0:
                self.actionPopIn.setDisabled(False)
        else:
            for action in actions:
                action.setDisabled(False)
            if len(self.loggers_by_name) == self.loggerTabWidget.count():
                self.actionPopIn.setDisabled(True)
            self.actionExtraMode.setChecked(logger.extra_mode)

        # if all loggers are popped in
        if len(self.popped_out_loggers) == 0:
            self.actionPopIn.setDisabled(True)

        if len(self.loggers_by_name) <= 1:
            self.actionMergeTabs.setDisabled(True)
        else:
            self.actionMergeTabs.setDisabled(False)

    def set_single_tab_mode(self, enabled):
        self.single_tab_mode = enabled

    def setup_shortcuts(self):
        self.actionQuit.setShortcut('Ctrl+Q')
        self.actionDarkTheme.setShortcut('Ctrl+S')
        # self.actionReloadStyle.setShortcut('Ctrl+R')
        # self.actionSettings.setShortcut('Ctrl+A')
        self.actionCloseTab.setShortcut('Ctrl+W')

    def save_geometry(self):
        CONFIG.save_geometry(self.geometry())

    def restore_geometry(self):
        geometry = CONFIG.load_geometry()
        if geometry:
            self.resize(geometry.width(), geometry.height())

    def settings_dialog(self):
        d = SettingsDialog(self)
        d.setWindowModality(Qt.ApplicationModal)
        d.setAttribute(Qt.WA_DeleteOnClose, True)
        d.open()

    def about_dialog(self):
        d = AboutDialog(self)
        d.open()

    def reload_stylesheet(self):
        if self.dark_theme:
            self.reload_dark_style()
        else:
            self.reload_light_style()

    def reload_light_style(self):
        if CONFIG['light_theme_is_native']:
            self.set_style_to_stock()
            return
        f = QFile(":/light_theme.qss")
        f.open(QFile.ReadOnly | QFile.Text)
        ts = QTextStream(f)
        qss = ts.readAll()
        # f = open(Config.get_resource_path('light_theme.qss', 'resources/ui'), 'r')
        # qss = f.read()
        self.app.setStyleSheet(qss)

    def reload_dark_style(self):
        f = QFile(":/dark_theme.qss")
        f.open(QFile.ReadOnly | QFile.Text)
        ts = QTextStream(f)
        qss = ts.readAll()
        # f = open(Config.get_resource_path('dark_theme.qss', 'resources/ui'), 'r')
        # qss = f.read()
        self.app.setStyleSheet(qss)

    def set_style_to_stock(self):
        self.app.setStyleSheet('')

    def toggle_dark_theme(self, enabled):
        self.dark_theme = enabled
        self.reload_stylesheet()

        for logger in self.loggers_by_name.values():
            logger.set_dark_theme(enabled)

    def toggle_extra_mode(self, enabled):
        logger, _ = self.current_logger_and_index()
        if not logger:
            return
        logger.set_extra_mode(enabled)

    def start_server(self):
        self.log.debug('Starting the server')
        self.server = LogServer(self, self.on_connection, self.log)
        self.server.start()
        self.server_running = True
        self.actionStartStopServer.setText('Stop server')

    def stop_server(self):
        if self.server_running:
            self.log.debug('Stopping the server')
            self.server.close_server()
            self.server_running = False
            del self.server
            self.server = None
        self.actionStartStopServer.setText('Start server')

    def restart_server(self):
        self.log.debug('Restarting the server')
        self.stop_server()
        self.start_server()

    def start_or_stop_server(self):
        if self.server_running:
            self.stop_server()
        else:
            self.start_server()

    def on_connection(self, conn, conn_id):
        self.log.debug('New connection id={}'.format(conn_id))

        if self.single_tab_mode and len(self.loggers_by_name) > 0:
            new_logger = list(self.loggers_by_name.values())[0]
            new_logger.add_connection(conn)
        else:
            new_logger, index = self.create_logger(conn)
            self.loggerTabWidget.setCurrentIndex(index)

        conn.new_record.connect(new_logger.on_record)
        conn.connection_finished.connect(new_logger.remove_connection)

        if self.server.benchmark and conn_id == -1:
            from .listener import BenchmarkMonitor
            bm = BenchmarkMonitor(self, new_logger)
            bm.speed_readout.connect(self.set_status)
            conn.connection_finished.connect(bm.requestInterruption)
            self.server.threads.append(bm)
            bm.start()

    def create_logger(self, conn, name=None):
        name = self.make_logger_name_unique("Logger" if name is None else name)
        new_logger = LoggerTab(self.loggerTabWidget, name, conn, self.log, self)
        new_logger.set_dark_theme(self.dark_theme)
        self.loggers_by_name[name] = new_logger
        index = self.loggerTabWidget.addTab(new_logger, name)
        return new_logger, index

    def make_logger_name_unique(self, name):
        name_f = "{} {{}}".format(name)
        c = 1
        while name in self.loggers_by_name:
            name = name_f.format(c)
            c += 1
        return name

    def set_status(self, string, timeout=3000):
        self.statusBar().showMessage(string, timeout)

    def rename_tab_dialog(self):
        logger, index = self.current_logger_and_index()
        if not logger:
            return

        d = QInputDialog(self)
        d.setLabelText('Enter the new name for the "{}" tab:'.format(logger.name))
        d.setWindowTitle('Rename the "{}" tab'.format(logger.name))
        d.textValueSelected.connect(self.rename_current_tab)
        d.open()

    def rename_current_tab(self, new_name):
        logger, index = self.current_logger_and_index()
        if new_name in self.loggers_by_name and new_name != logger.name:
            show_warning_dialog(self, "Rename error",
                                'Logger named "{}" already exists.'.format(new_name))
            return
        self.log.debug('Renaming logger "{}" to "{}"'.format(logger.name, new_name))
        del self.loggers_by_name[logger.name]
        logger.name = new_name
        self.loggers_by_name[new_name] = logger
        logger.log.name = '.'.join(logger.log.name.split('.')[:-1]) + '.{}'.format(new_name)
        self.loggerTabWidget.setTabText(index, new_name)

    def trim_records_dialog(self):
        logger, index = self.current_logger_and_index()
        if not logger:
            return

        d = QInputDialog(self)
        d.setInputMode(QInputDialog.IntInput)
        d.setIntRange(0, 100000000)  # because it sets intMaximum to 99 by default. why??
        d.setLabelText('Keep this many records out of {}:'.format(logger.record_model.rowCount()))
        d.setWindowTitle('Trim tab records of "{}" logger'.format(logger.name))
        d.intValueSelected.connect(self.trim_current_tab_records)
        d.open()

    def trim_current_tab_records(self, n):
        logger, index = self.current_logger_and_index()
        logger.record_model.trim_except_last_n(n)

    def max_capacity_dialog(self):
        logger, index = self.current_logger_and_index()
        if not logger:
            return

        d = QInputDialog(self)
        d.setInputMode(QInputDialog.IntInput)
        d.setIntRange(0, 100000000)  # because it sets intMaximum to 99 by default. why??
        max_now = logger.record_model.max_capacity
        max_now = "not set" if max_now is None else max_now
        label_str = 'Set max capacity for "{}" logger\nCurrently {}. Set to 0 to disable:'
        d.setLabelText(label_str.format(logger.name, max_now))
        d.setWindowTitle('Set max capacity')
        d.intValueSelected.connect(self.set_max_capacity)
        d.open()

    def set_max_capacity(self, n):
        logger, index = self.current_logger_and_index()
        logger.set_max_capacity(n)

    def merge_tabs_dialog(self):
        d = MergeDialog(self, self.loggers_by_name)
        d.setWindowModality(Qt.WindowModal)
        d.merge_tabs_signal.connect(self.merge_tabs)
        d.show()

    def merge_tabs(self, dst, srcs, keep_alive):
        self.log.debug('Merging tabs: dst="{}", srcs={}, keep={}'.format(dst, srcs, keep_alive))

        dst_logger = self.loggers_by_name[dst]
        for src_name in srcs:
            src_logger = self.loggers_by_name[src_name]

            dst_logger.merge_with_records(src_logger.record_model.records)

            if keep_alive:
                for conn in src_logger.connections:
                    conn.new_record.disconnect(src_logger.on_record)
                    conn.connection_finished.disconnect(src_logger.remove_connection)
                    conn.new_record.connect(dst_logger.on_record)
                    dst_logger.add_connection(conn)
                src_logger.connections.clear()
            self.destroy_logger(src_logger)

    def close_current_tab(self):
        _, index = self.current_logger_and_index()
        if index is None:
            return
        self.close_tab(index)

    def close_tab(self, index):
        self.log.debug("Tab close requested: {}".format(index))
        logger = self.loggerTabWidget.widget(index)
        self.loggerTabWidget.removeTab(index)
        self.log.debug(logger.name)
        self.destroy_logger(logger)

    def destroy_logger(self, logger):
        del self.loggers_by_name[logger.name]
        logger.setParent(None)
        logger.destroy()
        del logger

    def close_popped_out_logger(self, logger):
        del self.loggers_by_name[logger.name]
        del self.popped_out_loggers[logger.name]
        del logger
        if len(self.popped_out_loggers):
            self.actionPopIn.setDisabled(True)

    def current_logger_and_index(self):
        index = self.loggerTabWidget.currentIndex()
        if index == -1:
            return None, None

        logger = self.loggerTabWidget.widget(index)
        return logger, index

    def pop_out_tab(self):
        logger, index = self.current_logger_and_index()
        if not logger:
            return
        self.log.debug("Tab pop out requested: {}".format(int(index)))

        logger.destroyed.connect(logger.closeEvent)
        logger.setAttribute(Qt.WA_DeleteOnClose, True)
        logger.setWindowFlags(Qt.Window)
        logger.setWindowTitle('cutelog: "{}"'.format(self.loggerTabWidget.tabText(index)))
        self.popped_out_loggers[logger.name] = logger
        self.loggerTabWidget.removeTab(index)
        logger.popped_out = True
        logger.show()
        center_widget_on_screen(logger)

    def pop_in_tabs_dialog(self):
        d = PopInDialog(self, self.loggers_by_name.values())
        d.pop_in_tabs.connect(self.pop_in_tabs)
        d.setWindowModality(Qt.ApplicationModal)
        d.open()

    def pop_in_tabs(self, names):
        for name in names:
            self.log.debug('Popping in logger "{}"'.format(name))
            logger = self.loggers_by_name[name]
            self.pop_in_tab(logger)

    def pop_in_tab(self, logger):
        logger.setWindowFlags(Qt.Widget)
        logger.setAttribute(Qt.WA_DeleteOnClose, False)
        logger.destroyed.disconnect(logger.closeEvent)
        logger.setWindowTitle(logger.name)
        logger.popped_out = False
        del self.popped_out_loggers[logger.name]
        index = self.loggerTabWidget.addTab(logger, logger.windowTitle())
        self.loggerTabWidget.setCurrentIndex(index)

    def open_load_records_dialog(self):
        d = QFileDialog(self)
        d.setFileMode(QFileDialog.ExistingFile)
        d.fileSelected.connect(self.load_records)
        d.setWindowTitle('Load records from...')
        d.open()

    def load_records(self, load_path):
        import json
        from os import path

        class RecordDecoder(json.JSONDecoder):
            def __init__(self, *args, **kwargs):
                json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

            def object_hook(self, obj):
                if '_created' in obj:
                    obj['created'] = obj['_created']
                    del obj['_created']
                    record = LogRecord(obj)
                    del record._logDict['created']
                else:
                    record = LogRecord(obj)
                return record

        name = path.basename(load_path)
        index = None

        try:
            with open(load_path, 'r') as f:
                records = json.load(f, cls=RecordDecoder)
                new_logger, index = self.create_logger(None, name)
                new_logger.merge_with_records(records)
                self.loggerTabWidget.setCurrentIndex(index)
            self.set_status('Records have been loaded into "{}" tab'.format(new_logger.name))
        except Exception as e:
            if index:
                self.close_tab(index)
            text = "Error while loading records: \n{}".format(e)
            self.log.error(text, exc_info=True)
            show_critical_dialog(self, "Couldn't load records", text)

    def open_save_records_dialog(self):
        from functools import partial
        logger, _ = self.current_logger_and_index()
        if not logger:
            return

        d = QFileDialog(self)
        d.selectFile(logger.name + '.log')
        d.setFileMode(QFileDialog.AnyFile)
        d.fileSelected.connect(partial(self.save_records, logger))
        d.setWindowTitle('Save records of "{}" tab to...'.format(logger.name))
        d.open()

    def save_records(self, logger, path):
        import json

        # needed because a deque is not serializable
        class RecordList(list):
            def __init__(self, records):
                self.records = records

            def __len__(self):
                return len(self.records)

            def __iter__(self):
                for record in self.records:
                    d = record._logDict
                    if not d.get('created', False) and not d.get('time', False):
                        d['_created'] = record.created
                    yield d

        try:
            records = logger.record_model.records
            record_list = RecordList(records)
            with open(path, 'w') as f:
                json.dump(record_list, f, indent=2)
            self.set_status('Records have been saved to "{}"'.format(path))

        except Exception as e:
            text = "Error while saving records: \n{}".format(e)
            self.log.error(text, exc_info=True)
            show_critical_dialog(self, "Couldn't save records", text)

    def closeEvent(self, event):
        self.log.info('Close event on main window')
        self.shutdown()
        event.ignore()  # prevents errors due to closing the program before server has stopped

    def destroy_all_tabs(self):
        self.log.debug('Destroying tabs')
        delete_this = list(self.loggers_by_name.values())  # to prevent changing during iteration
        for logger in delete_this:
            self.destroy_logger(logger)

    def shutdown(self):
        self.log.info('Shutting down')
        if self.shutting_down:
            self.log.error('Exiting forcefully')
            raise SystemExit
        self.shutting_down = True
        self.stop_server()
        self.save_geometry()
        self.destroy_all_tabs()
        self.app.quit()

    def signal_handler(self, *args):
        self.shutdown()
