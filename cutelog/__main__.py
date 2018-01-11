import asyncio
import signal
import sys


try:
    import PyQt5.QtCore
    PyQt5.QtCore
except ImportError:
    if sys.platform == 'linux':
        sys.exit("Error: PyQt5 couldn't be imported.\n"
                 "Please install python3-pyqt5 (or just python-pyqt5) from your package manager.")
    else:  # this technically shouldn't ever happen
        sys.exit("Error: PyQt5 couldn't be imported.\n"
                 "Please install it by running `pip install pyqt5`")

from PyQt5.QtCore import pyqtRemoveInputHook
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

# !! resources and config must be imported before main_window !!
from .resources import qCleanupResources
from .config import CONFIG, ROOT_LOG
from .main_window import MainWindow


class Application(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.log = ROOT_LOG
        self.setWindowIcon(QIcon(':/cutelog.png'))
        self.config = CONFIG

    async def process_events(self):
        while not self.main_finished.is_set():
            await asyncio.sleep(self.config.loop_event_delay)
            self.processEvents()

    def run(self):
        pyqtRemoveInputHook()  # to prevent Qt conflicting with pdb debug
        self.loop = asyncio.get_event_loop()
        self.loop.set_debug(False)

        main = MainWindow(self.loop, self.log, self)
        self.main_finished = main.finished
        try:
            self.loop.add_signal_handler(signal.SIGINT, main.shutdown, None)
        except NotImplementedError:  # for Windows
            pass
        self.loop.run_until_complete(self.process_events())
        qCleanupResources()


def main():
    app = Application(sys.argv)
    app.run()


if __name__ == '__main__':
    main()
