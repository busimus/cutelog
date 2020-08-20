import sys

import qtpy


if not qtpy.PYQT5 and not qtpy.PYSIDE2:
    if sys.platform == 'linux':
        sys.exit("Error: a compatible Qt library couldn't be imported.\n"
                 "Please install python3-pyqt5 (or just python-pyqt5) from your package manager.")
    else:  # this technically shouldn't ever happen
        sys.exit("Error: a compatible Qt library couldn't be imported.\n"
                 "Please install it by running `pip install pyqt5")


def main():
    import signal
    from .config import ROOT_LOG
    from .main_window import MainWindow
    from .resources import qCleanupResources
    from qtpy.QtGui import QIcon
    from qtpy.QtWidgets import QApplication

    if sys.platform == 'win32':
        import ctypes
        appid = 'busimus.cutelog'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(':/cutelog.png'))
    mw = MainWindow(ROOT_LOG, app)
    signal.signal(signal.SIGINT, mw.signal_handler)

    sys.exit(app.exec_())
    qCleanupResources()


if __name__ == '__main__':
    main()
