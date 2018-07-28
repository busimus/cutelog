import json
from copy import deepcopy

from qtpy.QtGui import QColor

from .config import CONFIG


class LogLevel:
    def __init__(self, levelname, enabled=True, fg=None, bg=None,
                 fgDark=None, bgDark=None, styles=set(), stylesDark=None, load=None):
        if load:
            self.loads(load)
            return

        self.levelname = levelname

        self.enabled = enabled
        self.styles = styles
        if not stylesDark:
            self.stylesDark = deepcopy(styles)
        else:
            self.stylesDark = stylesDark

        if not fg:
            self.fg = QColor(0, 0, 0)
        else:
            self.fg = fg
        if not bg:
            self.bg = QColor(255, 255, 255)
        else:
            self.bg = bg

        if not fgDark:
            self.fgDark = QColor(255, 255, 255)
        else:
            self.fgDark = fgDark
        if not bgDark:
            self.bgDark = QColor(0, 0, 0)
        else:
            self.bgDark = bgDark

    def set_enabled(self, enabled):
        self.enabled = enabled

    def copy_from(self, other_level):
        for attr in self.__dict__:
            if attr in ['levelname']:
                continue
            self.__dict__[attr] = deepcopy(other_level.__dict__[attr])

    def dumps(self):
        d = deepcopy(self.__dict__)
        d['styles'] = list(d['styles'])
        d['stylesDark'] = list(d['stylesDark'])
        d['fg'], d['fgDark'] = d['fg'].name(), d['fgDark'].name()
        d['bg'], d['bgDark'] = d['bg'].name(), d['bgDark'].name()
        return json.dumps(d, ensure_ascii=False, separators=(',', ':'))

    def loads(self, string):
        self.__dict__ = json.loads(string)
        self.styles = set(self.styles)
        self.stylesDark = set(self.stylesDark)
        self.fg, self.fgDark = QColor(self.fg), QColor(self.fgDark)
        self.bg, self.bgDark = QColor(self.bg), QColor(self.bgDark)
        return self

    def __repr__(self):
        return "{}(levelname={}, enabled={})".format(self.__class__.__name__, self.levelname,
                                                     self.enabled)


DEFAULT_LEVELS = \
    {
        'DEBUG':    LogLevel('DEBUG',    fg=QColor(145, 145, 145), fgDark=QColor(169, 169, 169)),
        'INFO':     LogLevel('INFO',     bg=QColor(200, 255, 200), fgDark=QColor(169, 255, 169)),
        'WARNING':  LogLevel('WARNING',  bg=QColor(255, 255, 180), fgDark=QColor(255, 255, 129)),
        'ERROR':    LogLevel('ERROR',    bg=QColor(255, 190, 190), fgDark=QColor(255, 169, 169)),
        'CRITICAL': LogLevel('CRITICAL', fg=QColor(255, 0, 0),     bg=QColor(0, 0, 0),
                             fgDark=QColor(255, 0, 0), styles={'bold'}),
    }

NO_LEVEL = LogLevel("NO_LEVEL")


def get_default_level(name):
    if name in DEFAULT_LEVELS:
        return DEFAULT_LEVELS[name]
    # some Go compat
    elif name in ('FATAL', 'PANIC'):
        return DEFAULT_LEVELS['CRITICAL']
    elif name == 'WARN':
        return DEFAULT_LEVELS['WARNING']
    else:
        return NO_LEVEL


class LevelFilter:
    def __init__(self):
        self.preset_name = CONFIG['default_levels_preset']
        self.levels = CONFIG.load_levels_preset(self.preset_name)
        if not self.levels:
            self.levels = deepcopy(DEFAULT_LEVELS)

    def set_level(self, level):
        self.levels[level.levelname] = level

    def merge_with(self, new_levels):
        # This is done because self.levels gets passed to other things.
        # I'm lazy, so lets just modify it inplace instead.
        self.levels.clear()
        self.levels.update(new_levels)

    def __contains__(self, levelname):
        if levelname is None:
            return True

        level = self.levels.get(levelname)
        if level and level.enabled:
            return True

        return False
