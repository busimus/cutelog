import enum
import logging
import os
import sys
from collections import namedtuple
from distutils.version import StrictVersion

from pkg_resources import get_distribution, resource_filename
from qtpy import QT_VERSION
from qtpy.QtCore import QCoreApplication, QFile, QObject, QSettings, Qt, Signal

if sys.platform == 'win':
    DEFAULT_FONT = 'MS Shell Dlg 2'
elif sys.platform == 'darwin':
    DEFAULT_FONT = 'Helvetica Neue'
else:
    DEFAULT_FONT = 'Sans'

try:
    import msgpack
    MSGPACK_SUPPORT = True
except ImportError:
    MSGPACK_SUPPORT = False

try:
    import cbor
    CBOR_SUPPORT = True
except ImportError:
    CBOR_SUPPORT = False


# @Future: when Qt 5.6 becomes standard, remove this:
QT_VER = QT_VERSION.split('.')
if QT_VER[0] == '5' and int(QT_VER[1]) < 6:
    QT55_COMPAT = True
else:
    QT55_COMPAT = False


# Maybe there should be one common enum with all options instead of
# one enum for each thing? I guess I'll decide when there will be
# more than one thing in total.
class Exc_Indication(enum.IntEnum):
    RED_BG = 0
    MSG_ICON = 1
    ICON_AND_RED_BG = 2


# There must be a better way to do this, right?
Option = namedtuple('Option', ['name', 'type', 'default'])
OPTION_SPEC = (
    # SETTINGS WINDOW:
    # Appearance
    ('dark_theme_default',           bool, False),
    ('logger_table_font',            str,  DEFAULT_FONT),
    ('logger_table_font_size',       int,  9),
    ('text_view_dialog_font',        str,  'Courier New'),
    ('text_view_dialog_font_size',   int,  12),
    ('logger_row_height',            int,  15),
    ('exception_indication',         int,  Exc_Indication.RED_BG),
    ('time_format_string',           str,  "%Y-%m-%d %H:%M:%S.%f"),

    # Search
    ('search_open_default',          bool, False),
    ('search_regex_default',         bool, False),
    ('search_casesensitive_default', bool, False),
    ('search_wildcard_default',      bool, False),

    # Server
    ('listen_host',                  str,  '0.0.0.0'),
    ('listen_port',                  int,  19996),
    ('single_tab_mode_default',      bool, False),
    ('extra_mode_default',           bool, False),
    ('default_serialization_format', str,  'pickle'),

    # Advanced
    ('console_logging_level',        int,   30),
    ('benchmark',                    bool,  False),
    ('benchmark_interval',           float, 0.0005),
    ('light_theme_is_native',        bool,  False),

    # NON-SETTINGS OPTIONS:
    # Header
    ('default_header_preset',        str,  'Stock'),
    ('default_levels_preset',        str,  'Stock'),
    ('cutelog_version',              str,  ''),
)


class Config(QObject):
    "Configuration provider for the whole program, wrapper for QSettings"

    row_height_changed = Signal(int)

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

        # options that need fast access are also defined as attributes, which
        # are updated by calling update_attributes()
        # (on paper it's 4 times faster, but I don't think it matters in my case)
        self.logger_table_font = None
        self.logger_table_font_size = None
        self.logger_row_height = None
        self.benchmark_interval = None

        self.update_attributes()

    def post_init(self):
        running_version = StrictVersion(QCoreApplication.applicationVersion())
        config_version = self.options['cutelog_version']
        if config_version == "" or config_version != running_version:
            self.save_running_version()

    def __getitem__(self, name):
        # self.log.debug('Getting "{}"'.format(name))
        value = self.options.get(name)
        if value is None:
            raise Exception('No option with name "{}"'.format(name))
        # self.log.debug('Returning "{}"'.format(value))
        return value

    def __setitem__(self, name, value):
        # self.log.debug('Setting "{}"'.format(name))
        if name not in self.options:
            raise Exception('No option with name "{}"'.format(name))
        self.options[name] = value

    def set_option(self, name, value):
        self[name] = value
        self.qsettings.beginGroup('Configuration')
        self.qsettings.setValue(name, value)
        self.qsettings.endGroup()

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
        host = self.options.get('listen_host')
        port = self.options.get('listen_port')
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
        self.emit_needed_changes(new_options)
        self.options.update(new_options)
        if save:
            self.save_options()
        self.update_attributes(new_options)

    def update_attributes(self, options=None):
        "Updates fast attributes and everything else outside of self.options"
        if options is None:
            options = self.options

        self.benchmark_interval = options.get('benchmark_interval', self.benchmark_interval)
        self.logger_table_font = options.get('logger_table_font', self.logger_table_font)
        self.logger_table_font_size = options.get('logger_table_font_size', self.logger_table_font_size)
        self.logger_row_height = options.get('logger_row_height', self.logger_row_height)
        self.set_logging_level(options.get('console_logging_level', ROOT_LOG.level))

    def emit_needed_changes(self, new_options):
        new_row_height = new_options.get('logger_row_height')
        old_row_height = self.options.get('logger_row_height')
        if new_row_height != old_row_height:
            self.logger_row_height = new_row_height
            self.row_height_changed.emit(new_row_height)

    def save_options(self, sync=False):
        self.log.debug('Saving options')
        self.qsettings.beginGroup('Configuration')
        for option in self.option_spec:
            self.qsettings.setValue(option.name, self.options[option.name])
        self.qsettings.endGroup()
        if sync:  # syncing is probably not necessary here, so the default is False
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

    def get_levels_presets(self):
        self.qsettings.beginGroup('Levels_Presets')
        result = self.qsettings.childGroups()
        self.qsettings.endGroup()
        return result

    def save_levels_preset(self, name, levels):
        self.log.debug('Saving levels preset "{}"'.format(name))
        s = self.qsettings
        s.beginGroup('Levels_Presets')
        s.beginWriteArray(name, len(levels))
        for i, levelname in enumerate(levels):
            level = levels[levelname]
            s.setArrayIndex(i)
            dump = level.dumps()
            s.setValue('level', dump)
        s.endArray()
        s.endGroup()

    def load_levels_preset(self, name):
        from .log_levels import LogLevel
        self.log.debug('Loading levels preset "{}"'.format(name))
        s = self.qsettings
        if name not in self.get_levels_presets():
            return None
        s.beginGroup('Levels_Presets')
        size = s.beginReadArray(name)
        result = {}
        for i in range(size):
            s.setArrayIndex(i)
            new_level = LogLevel(None).loads(s.value('level'))
            result[new_level.levelname] = new_level
        s.endArray()
        s.endGroup()
        return result

    def delete_levels_preset(self, name):
        s = self.qsettings
        s.beginGroup('Levels_Presets')
        s.remove(name)
        s.endGroup()

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
            # read the comment in Column.dumps() for reasoning
            if i == len(columns) - 1:
                col.width = 10
                # dump = col.dumps(width=10)
            dump = col.dumps()
            s.setValue('column', dump)
        s.endArray()
        s.endGroup()

    def load_header_preset(self, name):
        from .logger_table_header import Column
        self.log.debug('Loading header preset "{}"'.format(name))
        s = self.qsettings
        if name not in self.get_header_presets():
            return None
        s.beginGroup('Header_Presets')
        size = s.beginReadArray(name)
        result = []
        for i in range(size):
            s.setArrayIndex(i)
            new_column = Column().loads(s.value('column'))
            result.append(new_column)
        s.endArray()
        s.endGroup()
        return result

    def delete_header_preset(self, name):
        s = self.qsettings
        s.beginGroup('Header_Presets')
        s.remove(name)
        s.endGroup()

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

    def save_running_version(self):
        version = QCoreApplication.applicationVersion()
        self.log.debug("Updating the config version to {}".format(version))
        s = self.qsettings
        s.beginGroup('Configuration')
        s.setValue('cutelog_version', version)
        self.options['cutelog_version'] = version
        s.endGroup()
        self.sync()

    def restore_defaults(self):
        self.qsettings.clear()
        self.sync()


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
CONFIG.post_init()
