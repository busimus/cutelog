import asyncio

from PyQt5 import uic
from PyQt5.QtCore import Qt, QFile, QTextStream
from PyQt5.QtWidgets import (QInputDialog, QMenuBar, QWidget)

from .listener import LogServer
from .logger_tab import LoggerTab
from .settings_dialog import SettingsDialog
from .about_dialog import AboutDialog
from .merge_dialog import MergeDialog
from .pop_in_dialog import PopInDialog
from .utils import show_warning_dialog, center_widget_on_screen
from .config import CONFIG


uif = CONFIG.get_ui_qfile('main_window.ui')
MainWindowBase = uic.loadUiType(uif)
uif.close()


class MainWindow(*MainWindowBase):

    def __init__(self, loop, log, app):
        self.loop = loop
        self.log = log.getChild('Main')
        self.app = app
        super().__init__()

        self.stop_signal = asyncio.Event()
        self.finished = asyncio.Event()
        self.dark_theme = CONFIG['dark_theme_default']

        self.loggers_by_name = {}  # maps name -> logger

        # used for starting/stopping the server
        self.server_running = False
        self.start_server_again = asyncio.Event()
        self.stop_reason = None

        self.setupUi()

        self.loop.create_task(self.run())

    def setupUi(self):
        super().setupUi(self)
        self.setup_menubar()
        self.setup_shortcuts()

        self.connectionTabWidget.tabCloseRequested.connect(self.close_tab)

        self.setWindowTitle('cutelog')

        self.actionQuit.triggered.connect(self.shutdown)

        self.actionRenameTab.triggered.connect(self.rename_tab)
        self.actionCloseTab.triggered.connect(self.close_current_tab)

        self.actionPopOut.triggered.connect(self.pop_out_tab)
        self.actionPopIn.triggered.connect(self.pop_in_tabs_dialog)
        self.actionDarkTheme.toggled.connect(self.toggle_dark_theme)

        # self.actionReloadStyle.triggered.connect(self.reload_stylesheet)
        self.actionRestartServer.triggered.connect(self.restart_server)
        self.actionStartStopServer.triggered.connect(self.start_or_stop_server)

        self.actionAbout.triggered.connect(self.about_dialog)
        self.actionSettings.triggered.connect(self.settings_dialog)
        self.actionMergeTabs.triggered.connect(self.merge_tabs_dialog)
        self.actionTrimTabRecords.triggered.connect(self.trim_records_dialog)
        self.actionSetMaxCapacity.triggered.connect(self.max_capacity_dialog)

        self.reload_stylesheet()

        self.restore_geometry()

        self.show()

    def setup_menubar(self):
        "Copied from pyuic-generated code to gain some control"
        self.menubar = QMenuBar(self)
        self.setMenuBar(self.menubar)

        # File menu
        self.menuFile = self.menubar.addMenu("File")
        self.actionDarkTheme = self.menuFile.addAction('Dark Theme')
        self.actionDarkTheme.setCheckable(True)
        self.actionDarkTheme.setChecked(self.dark_theme)
        # self.actionReloadStyle = self.menuFile.addAction('Reload style')
        self.actionSettings = self.menuFile.addAction('Settings')
        self.menuFile.addSeparator()
        self.actionQuit = self.menuFile.addAction('Quit')

        # Edit menu
        self.menuEdit = self.menubar.addMenu("Edit")

        self.menuEditTabs = self.menuEdit.addMenu("Tabs")
        self.actionCloseTab = self.menuEditTabs.addAction('Close')
        self.actionPopOut = self.menuEditTabs.addAction('Pop out')
        self.actionRenameTab = self.menuEditTabs.addAction('Rename')
        self.actionPopIn = self.menuEditTabs.addAction('Pop in tabs...')
        self.actionMergeTabs = self.menuEditTabs.addAction('Merge tabs...')

        self.menuEditServer = self.menuEdit.addMenu("Server")
        self.actionRestartServer = self.menuEditServer.addAction('Restart server')
        self.actionStartStopServer = self.menuEditServer.addAction('Stop server')

        self.menuEditRecords = self.menuEdit.addMenu("Records")
        self.actionTrimTabRecords = self.menuEditRecords.addAction('Trim records of this tab')
        self.actionSetMaxCapacity = self.menuEditRecords.addAction('Set max capacity for this tab')

        # Help menu
        self.menuHelp = self.menubar.addMenu("Help")
        self.actionAbout = self.menuHelp.addAction("About cutelog")

    def setup_shortcuts(self):
        self.actionQuit.setShortcut('Ctrl+Q')
        self.actionDarkTheme.setShortcut('Ctrl+S')
        # self.actionReloadStyle.setShortcut('Ctrl+R')
        self.actionSettings.setShortcut('Ctrl+A')
        self.actionCloseTab.setShortcut('Ctrl+W')

    def save_geometry(self):
        CONFIG.save_geometry(self.geometry())

    def restore_geometry(self):
        geometry = CONFIG.load_geometry()
        if geometry:
            # self.move(geometry.x(), geometry.y())  # i don't thing this is a good idea
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
        # @Improvement: make one common function for both/many? styles?
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

    def toggle_dark_theme(self, value):
        self.dark_theme = value
        self.reload_stylesheet()

        for logger in self.loggers_by_name.values():
            logger.set_dark_theme(value)

    async def run(self):
        while True:
            self.create_server()
            self.server.start()
            self.server_running = True
            await self.stop_signal.wait()
            self.server.close_server()
            self.server_running = False
            self.log.debug('Run got the stop_signal with reason {}'.format(self.stop_reason))
            if self.stop_reason == 'restart':
                # await self.wait_server_closed()
                continue
            elif self.stop_reason == 'pause':
                await self.start_server_again.wait()
                continue
            else:
                break

        self.log.info('Main window stopped')
        self.finished.set()

    def on_connection(self, conn, name, tab_closed):
        self.log.debug('New connection: "{}"'.format(name))
        one_tab_mode = CONFIG['one_tab_mode'] and len(self.loggers_by_name) > 0

        if one_tab_mode:
            new_logger = list(self.loggers_by_name.values())[0]
            new_tab = new_logger.parent_widget
        else:
            new_tab = QWidget(self)
            name = self.make_logger_name_unique(name)
            new_logger = LoggerTab(name, tab_closed, self.log, self.loop, self, new_tab)
            new_logger.set_dark_theme(self.dark_theme)

        conn.new_record.connect(new_logger.on_record)

        new_tab.logger = new_logger
        if not one_tab_mode:
            self.connectionTabWidget.addTab(new_tab, name)
            self.loggers_by_name[name] = new_logger

        if self.server.benchmark and name == 'benchmark':
            self.loop.create_task(new_logger.monitor())

    def make_logger_name_unique(self, name):
        name_f = "{} {{}}".format(name)
        c = 1
        while name in self.loggers_by_name:
            name = name_f.format(c)
            c += 1
        return name

    def create_server(self):
        self.log.debug('Creating the server')
        self.stop_reason = None
        self.stop_signal = asyncio.Event()  # putting .clear() here has some async weirdness
        self.start_server_again = asyncio.Event()
        self.server = LogServer(self, self.on_connection, self.log, self.stop_signal)

    def restart_server(self):
        "Stops the server, and run() creates and starts again it automatically"
        self.log.debug('Restarting the server')
        self.stop_reason = 'restart'
        self.stop_signal.set()

    # async def wait_server_closed(self):
    #     self.log.debug('Waiting for the server to close')
    #     self.actionRestartServer.setText('Stopping the server...')
    #     self.actionRestartServer.setEnabled(False)
    #     try:
    #         await asyncio.wait_for(self.server.wait_server_closed(), timeout=10)
    #     except asyncio.TimeoutError as e:
    #         self.log.error('Waiting for the server to close timed out after 10 seconds')
    #     else:
    #         self.log.debug('Waiting for server to close finished')
    #         self.actionRestartServer.setText('Restart server')
    #         self.actionRestartServer.setEnabled(True)

    def start_or_stop_server(self):
        if self.server_running:
            self.stop_reason = 'pause'
            self.stop_signal.set()
            self.actionStartStopServer.setText('Start server')
        else:
            self.start_server_again.set()
            self.actionStartStopServer.setText('Stop server')

    def set_status(self, string):
        self.statusBar().showMessage(string)

    def rename_tab(self):
        tab, logger, index = self.get_current_tab_logger_index()
        if not tab or not logger:
            return

        d = QInputDialog(self)
        d.setLabelText('Enter the new name for the "{}" tab:'.format(logger.name))
        d.setWindowTitle('Rename the "{}" tab'.format(logger.name))
        d.textValueSelected.connect(self.change_current_tab_name)
        d.open()

    def change_current_tab_name(self, new_name):
        tab, logger, index = self.get_current_tab_logger_index()
        if new_name in self.loggers_by_name and new_name != logger.name:
            show_warning_dialog(self, "Rename error",
                                'Logger named "{}" already exists.'.format(new_name))
            return
        self.log.debug('Renaming logger "{}" to "{}"'.format(logger.name, new_name))
        del self.loggers_by_name[logger.name]
        logger.name = new_name
        self.loggers_by_name[new_name] = logger
        logger.log.name = '.'.join(logger.log.name.split('.')[:-1]) + '.{}'.format(new_name)
        self.connectionTabWidget.setTabText(index, new_name)

    def trim_records_dialog(self):
        tab, logger, index = self.get_current_tab_logger_index()
        if not tab or not logger:
            return

        d = QInputDialog(self)
        d.setInputMode(QInputDialog.IntInput)
        d.setIntRange(0, 100000000)  # because it sets intMaximum to 99 by default. why??
        d.setLabelText('Keep this many records out of {}:'.format(logger.record_model.rowCount()))
        d.setWindowTitle('Trim tab records of "{}" logger'.format(logger.name))
        d.intValueSelected.connect(self.trim_current_tab_records)
        d.open()

    def trim_current_tab_records(self, n):
        tab, logger, index = self.get_current_tab_logger_index()
        logger.record_model.trim_except_last_n(n)

    def max_capacity_dialog(self):
        tab, logger, index = self.get_current_tab_logger_index()
        if not tab or not logger:
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
        tab, logger, index = self.get_current_tab_logger_index()
        logger.set_max_capacity(n)

    def merge_tabs_dialog(self):
        d = MergeDialog(self, self.loggers_by_name)
        d.setWindowModality(Qt.WindowModal)
        d.merge_tabs_signal.connect(self.merge_tabs)
        d.show()

    def merge_tabs(self, dst, srcs):
        self.log.debug('Merging tabs: dst="{}", srcs={}'.format(dst, srcs))

        dst_logger = self.loggers_by_name[dst]
        for src_name in srcs:
            src_logger = self.loggers_by_name[src_name]
            src_tab = src_logger.parent_widget

            dst_logger.merge_with_records(src_logger.record_model.records)

            self.destroy_logger(src_logger)
            self.destroy_tab(src_tab)

    def close_current_tab(self):
        _, _, index = self.get_current_tab_logger_index()
        if index is None:
            return
        self.close_tab(index)

    def close_tab(self, index):
        self.log.debug("Tab close requested: {}".format(index))
        tab = self.connectionTabWidget.widget(index)
        self.connectionTabWidget.removeTab(index)
        logger = self.destroy_tab(tab)
        self.destroy_logger(logger)

    def destroy_tab(self, tab):
        "Returns the logger of the tab"
        logger = tab.logger
        tab.setParent(None)
        del tab
        return logger

    def destroy_logger(self, logger):
        "Returns the parent QWidget of the logger"
        tab = logger.parent_widget
        logger.tab_closed_signal.set()
        del self.loggers_by_name[logger.name]
        del logger
        return tab

    def close_popped_out_logger(self, logger):
        del self.loggers_by_name[logger.name]
        del logger.parent_widget
        del logger

    def get_current_tab_logger_index(self):
        index = self.connectionTabWidget.currentIndex()
        if index == -1:
            return None, None, None

        tab = self.connectionTabWidget.widget(index)
        logger = tab.logger
        return tab, logger, index

    def pop_out_tab(self):
        tab, logger, index = self.get_current_tab_logger_index()
        if not tab:
            return
        self.log.debug("Tab pop out requested: {}".format(int(index)))

        tab.destroyed.connect(logger.closeEvent)
        tab.setAttribute(Qt.WA_DeleteOnClose, True)
        tab.setWindowFlags(Qt.Window)
        tab.setWindowTitle('cutelog: "{}"'.format(self.connectionTabWidget.tabText(index)))
        self.connectionTabWidget.removeTab(index)
        logger.popped_out = True
        tab.show()
        center_widget_on_screen(tab)

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
        tab = logger.parent_widget
        tab.setWindowFlags(Qt.Widget)
        tab.setAttribute(Qt.WA_DeleteOnClose, False)
        tab.destroyed.disconnect(logger.closeEvent)
        tab.setWindowTitle(logger.name)
        logger.popped_out = False
        self.connectionTabWidget.addTab(tab, tab.windowTitle())

    def closeEvent(self, event):
        self.log.info('Close event on main window')
        self.shutdown()
        event.ignore()  # prevents errors due to closing the program before server has stopped

    def destroy_all_tabs(self):
        self.log.debug('Destroying tabs')
        delete_this = list(self.loggers_by_name.values())  # to prevent changing during iteration
        for logger in delete_this:
            tab = self.destroy_logger(logger)
            self.destroy_tab(tab)

    def shutdown(self, signal=None):
        self.log.info('Shutting down')
        if not self.stop_signal.is_set():  # do this for the first time shutdown is called
            self.save_geometry()
            self.destroy_all_tabs()
            self.stop_reason = 'shutdown'
            self.stop_signal.set()
        else:
            self.log.error('Forcefully shutting down')
            raise SystemExit
