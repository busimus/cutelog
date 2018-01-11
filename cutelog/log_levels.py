from copy import deepcopy

from PyQt5.QtGui import QColor

# from .config import CONFIG


class LogLevel:
    def __init__(self, levelno, levelname, enabled=True,
                 fg=None, bg=None,
                 fgDark=None, bgDark=None, styles=set(), stylesDark=None):
        self.levelno = levelno
        self.levelname = levelname

        self.enabled = enabled
        self.styles = styles
        if not stylesDark:
            self.stylesDark = deepcopy(styles)
        else:
            self.stylesDark = stylesDark

        self.msg_count = 0  # @MaybeDelete: is this necessary?

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

    def set_enabled(self, value):
        self.enabled = value

    def copy_level(self, other_level):
        for attr in self.__dict__:
            if attr in ['levelno', 'levelname', 'msg_count', 'enabled']:
                continue
            self.__dict__[attr] = deepcopy(other_level.__dict__[attr])

    def __repr__(self):
        return f"{self.__class__.__name__}(levelname={self.levelname}, "\
                "levelno={self.levelno}, enabled={self.enabled})"


DEFAULT_LEVELS = \
    {
        50: LogLevel(50, 'CRITICAL', fg=QColor(255, 0, 0),     bg=QColor(0, 0, 0),
                     fgDark=QColor(255, 0, 0), styles={'bold'}),
        40: LogLevel(40, 'ERROR',    bg=QColor(255, 190, 190), fgDark=QColor(255, 169, 169)),
        30: LogLevel(30, 'WARNING',  bg=QColor(255, 255, 180), fgDark=QColor(255, 255, 129)),
        20: LogLevel(20, 'INFO',     bg=QColor(200, 255, 200), fgDark=QColor(169, 255, 169)),
        10: LogLevel(10, 'DEBUG',    fg=QColor(145, 145, 145), fgDark=QColor(169, 169, 169)),
    }


class LevelFilter:
    def __init__(self):
        self.levels = deepcopy(DEFAULT_LEVELS)
        self.ranges = []
        self.all_pass = False

    def add_level(self, level):
        self.levels[level.levelno] = level

    def enable_level(self, level):
        self.numbers.add(level)

    def disable_level(self, level):
        try:
            self.numbers.remove(level)
        except KeyError:
            pass

    def enable_range(self, min, max):
        self.ranges.append((min, max))

    def disable_range(self, min, max):
        try:
            self.ranges.remove((min, max))
        except KeyError:
            pass

    def set_all_pass(self, value):
        self.all_pass = value

    def __contains__(self, levelno):
        if self.all_pass:
            return True

        level = self.levels.get(levelno)
        if level and level.enabled:
            return True

        for level_range in self.ranges:
            if level_range[0] <= levelno <= level_range[1]:
                return True

        return False
