import logging
import os
import sys
from collections import namedtuple

from pkg_resources import get_distribution, resource_filename
from PyQt5.QtCore import (QT_VERSION_STR, QCoreApplication, QFile, QObject,
                          QSettings, Qt, pyqtSignal)


if sys.platform == 'win':
    DEFAULT_FONT = 'MS Shell Dlg 2'
elif sys.platform == 'darwin':
    DEFAULT_FONT = 'Helvetica Neue'
else:
    DEFAULT_FONT = 'Sans'


# @Future: when Qt 5.6 becomes standard, remove this:
QT_VER = QT_VERSION_STR.split('.')
if QT_VER[0] == '5' and int(QT_VER[1]) < 6:
    QT55_COMPAT = True
else:
    QT55_COMPAT = False


# There must be a better way to do this, right?
Option = namedtuple('Option', ['name', 'type', 'default'])
OPTION_SPEC = (
    # Appearance
    ('dark_theme_default',         bool, False),
    ('logger_table_font',          str,  DEFAULT_FONT),
    ('logger_table_font_size',     int,  9),
    ('text_view_dialog_font',      str,  'Courier New'),
    ('text_view_dialog_font_size', int,  12),
    ('logger_row_height',          int,  20),

    # Search
    ('search_open_default',          bool, False),
    ('search_regex_default',         bool, False),
    ('search_casesensitive_default', bool, False),
    ('search_wildcard_default',      bool, False),

    # Server
    ('listen_host',  str,  '0.0.0.0'),
    ('listen_port',  int,  19996),
    ('one_tab_mode', bool, False),

    # Advanced
    ('console_logging_level', int,   30),
    ('loop_event_delay',      float, 0.005),
    ('benchmark',             bool,  False),
    ('benchmark_interval',    float, 0.0005),
    ('light_theme_is_native', bool,  False),
)


class Config(QObject):
    "Configuration provider for the whole program, wapper for QSettings"

    row_height_changed = pyqtSignal(int)

    def __init__(self, log=None):
        super().__init__()
        if log:
            self.log = log.getChild('Conf')
            self.log.setLevel(30)
        else:
            self.log = logging.getLogger()
            self.log.setLevel(99)
        self.log.debug('Initializing')
        self.qsettings = QSettings()
        self.qsettings.setIniCodec('UTF-8')

        self.options = None
        self.option_spec = self.load_option_spec()
        self.options = self.load_options()
        self.full_name = "{} {}".format(QCoreApplication.applicationName(),
                                        QCoreApplication.applicationVersion())

        # options that need fast access are also definded as attributes, which
        # are updated by calling update_attributes()
        # (on paper it's 4 times faster, but i don't think it matters in my case)
        self.logger_table_font = None
        self.logger_table_font_size = None
        self.loop_event_delay = None
        self.benchmark_interval = None

        self.update_attributes()

    def __getitem__(self, name):
        # self.log.debug('Getting "{}"'.format(name))
        value = self.options.get(name, None)
        if value is None:
            raise Exception('No option with name "{}"'.format(name))
        # self.log.debug('Returning "{}"'.format(value))
        return value

    @staticmethod
    def get_resource_path(name, directory='ui'):
        data_dir = resource_filename('cutelog', directory)
        path = os.path.join(data_dir, name)
        if not os.path.exists(path):
            raise FileNotFoundError('Resource file not found in this path: "{}"'.format(path))
        return path

    def get_ui_qfile(self, name):
        file = QFile(':/ui/{}'.format(name))
        if not file.exists():
            raise FileNotFoundError('ui file not found: ":/ui/{}"'.format(name))
        file.open(QFile.ReadOnly)
        return file

    @property
    def listen_address(self):
        host = self.options.get('listen_host', None)
        port = self.options.get('listen_port', None)
        if host is None or port is None:
            raise Exception('Listen host or port not in options: "{}:{}"'.format(host, port))
        return (host, port)

    def load_option_spec(self):
        option_spec = []
        for spec in OPTION_SPEC:
            option = Option(*spec)
            option_spec.append(option)
        return option_spec

    def load_options(self):
        self.log.debug('Loading options')
        options = {}
        self.qsettings.beginGroup('Configuration')
        for option in self.option_spec:
            value = self.qsettings.value(option.name, option.default)
            if option.type == bool:
                value = str(value).lower()  # needed because QSettings stores bools as strings
                value = True if value == "true" or value is True else False
            else:
                value = option.type(value)
            options[option.name] = value
        self.qsettings.endGroup()
        return options

    def update_options(self, new_options, save=True):
        self.options.update(new_options)
        if save:
            self.save_options()
        self.update_attributes(new_options)

    def update_attributes(self, options=None):
        "Updates fast attributes and everything else outside of self.options"
        if options:
            # here will be things that only need to be updated when they actually changed
            new_row_height = options.get('logger_row_height', self.options['logger_row_height'])
            if new_row_height != self.options['logger_row_height']:
                self.row_height_changed.emit(new_row_height)
        else:
            options = self.options

        self.loop_event_delay = options.get('loop_event_delay', self.loop_event_delay)
        self.benchmark_interval = options.get('benchmark_interval', self.benchmark_interval)
        self.logger_table_font = options.get('logger_table_font', self.logger_table_font)
        self.logger_table_font_size = options.get('logger_table_font_size', self.logger_table_font_size)
        self.set_logging_level(options.get('console_logging_level', ROOT_LOG.level))

    def save_options(self):
        self.log.debug('Saving options')
        self.qsettings.beginGroup('Configuration')
        for option in self.option_spec:
            self.qsettings.setValue(option.name, self.options[option.name])
        self.qsettings.endGroup()
        self.sync()

    def sync(self):
        self.log.debug('Syncing QSettings')
        self.qsettings.sync()

    def set_settings_value(self, name, value):
        self.qsettings.beginGroup('Configuration')
        self.qsettings.setValue(name, value)
        self.qsettings.endGroup()

    def set_logging_level(self, level):
        global ROOT_LOG
        ROOT_LOG.setLevel(level)
        self.log.setLevel(level)

    # def save_levels_preset(self, levels, preset_name):
    #     pass

    def get_header_presets(self):
        self.qsettings.beginGroup('Header_Presets')
        result = self.qsettings.childGroups()
        self.qsettings.endGroup()
        return result

    def save_header_preset(self, name, columns):
        self.log.debug('Saving header preset "{}"'.format(name))
        s = self.qsettings
        s.beginGroup('Header_Presets')
        s.beginWriteArray(name, len(columns))
        for i, col in enumerate(columns):
            s.setArrayIndex(i)
            s.setValue('column', col.dump_to_string())
        s.endArray()
        s.endGroup()

    def load_header_preset(self, name):
        from .logger_table_header import Column
        self.log.debug('Loading header preset "{}"'.format(name))
        s = self.qsettings
        result = []
        if name not in self.get_header_presets():
            return None
        s.beginGroup('Header_Presets')
        size = s.beginReadArray(name)
        for i in range(size):
            s.setArrayIndex(i)
            new_column = Column(load=s.value('column'))
            result.append(new_column)
        s.endArray()
        s.endGroup()
        return result

    def save_geometry(self, geometry):
        s = self.qsettings
        s.beginGroup('Geometry')
        s.setValue('Main_Window_Geometry', geometry)
        s.endGroup()
        self.sync()

    def load_geometry(self):
        s = self.qsettings
        s.beginGroup('Geometry')
        geometry = s.value('Main_Window_Geometry')
        s.endGroup()
        return geometry


def init_qt_info():
    QCoreApplication.setOrganizationName('busimus')
    QCoreApplication.setOrganizationDomain('busz.me')
    QCoreApplication.setApplicationName('cutelog')
    version = get_distribution(QCoreApplication.applicationName()).version
    QCoreApplication.setApplicationVersion(version)
    if not QT55_COMPAT:  # this attribute was introduced in Qt 5.6
        QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)


def init_logging():
    log = logging.getLogger('CL')
    term_handler = logging.StreamHandler()

    try:
        import colorlog
        fmt = colorlog.ColoredFormatter('%(asctime)s %(log_color)s[%(name)12s:%(lineno)3s'
                                        ' %(funcName)18s ]\t%(levelname)-.6s  %(message)s')
    except ImportError:
        fmt = logging.Formatter('%(asctime)s [%(name)12s:%(lineno)3s '
                                '%(funcName)18s ]\t%(levelname)-.6s  %(message)s')

    term_handler.setFormatter(fmt)
    log.addHandler(term_handler)
    log.setLevel(logging.DEBUG)
    return log


init_qt_info()
ROOT_LOG = init_logging()
CONFIG = Config(ROOT_LOG)
