from PyQt5 import uic
from PyQt5.QtWidgets import QMessageBox, QDialogButtonBox
from PyQt5.QtGui import QFont, QIntValidator, QDoubleValidator

from .utils import show_info_dialog
from .config import CONFIG


uif = CONFIG.get_ui_qfile('settings_dialog.ui')
SettingsDialogBase = uic.loadUiType(uif)
uif.close()


class SettingsDialog(*SettingsDialogBase):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_widget = parent
        self.server_restart_needed = False
        self.setupUi()

    def setupUi(self):
        super().setupUi(self)
        self.applyButton = self.buttonBox.button(QDialogButtonBox.Apply)
        self.applyButton.clicked.connect(self.save_to_config)

        self.setup_tooltips()

        self.load_from_config()

    def setup_tooltips(self):
        self.loopEventDelayLine.setToolTip('Determines how fast UI updates. '
                                           'Recommended vaules: <b>between 0 and 0.0075</b>.<br>'
                                           'Smaller number means smoother UI, but '
                                           'might hinder performance of some things.')

        self.benchmarkCheckBox.setToolTip('Has effect after restarting the server, '
                                          '<b>for testing purposes only</b>.')

        self.singleTabCheckBox.setToolTip("Forces all connections into one tab. "
                                          "Useful for when you're restarting one "
                                          "program very often.")
        self.singleTabLabel.setBuddy(self.singleTabCheckBox)  # @Hmmm: why doesn't this work?

    def load_from_config(self):
        # Appearance page
        self.darkThemeDefaultCheckBox.setChecked(CONFIG['dark_theme_default'])

        self.loggerTableFont.setCurrentFont(QFont(CONFIG['logger_table_font']))
        self.loggerTableFontSize.setValue(CONFIG['logger_table_font_size'])
        self.textViewFont.setCurrentFont(QFont(CONFIG['text_view_dialog_font']))
        self.textViewFontSize.setValue(CONFIG['text_view_dialog_font_size'])
        self.loggerTableRowHeight.setValue(CONFIG['logger_row_height'])
        self.excIndicationComboBox.setCurrentIndex(CONFIG['exception_indication'])

        # Search
        self.searchOpenDefaultCheckBox.setChecked(CONFIG['search_open_default'])
        self.searchRegexDefaultCheckBox.setChecked(CONFIG['search_regex_default'])
        self.searchCaseSensitiveDefaultCheckBox.setChecked(CONFIG['search_casesensitive_default'])
        self.searchWildcardDefaultCheckBox.setChecked(CONFIG['search_wildcard_default'])

        # Server page
        self.listenHostLine.setText(CONFIG['listen_host'])
        self.listenPortLine.setValidator(QIntValidator(0, 65535, self))
        self.listenPortLine.setText(str(CONFIG['listen_port']))
        self.singleTabCheckBox.setChecked(CONFIG['single_tab_mode_default'])

        # Advanced page
        self.logLevelLine.setValidator(QIntValidator(0, 1000, self))
        self.logLevelLine.setText(str(CONFIG['console_logging_level']))
        self.loopEventDelayLine.setValidator(QDoubleValidator(0, 1, 9, self))
        self.loopEventDelayLine.setText(str(CONFIG['loop_event_delay']))
        self.benchmarkCheckBox.setChecked(CONFIG['benchmark'])
        self.benchmarkIntervalLine.setValidator(QDoubleValidator(0, 1000, 9, self))
        self.benchmarkIntervalLine.setText(str(CONFIG['benchmark_interval']))
        self.lightThemeNativeCheckBox.setChecked(CONFIG['light_theme_is_native'])
        self.server_restart_needed = False

    def save_to_config(self):
        o = {}
        # Appearance
        o['dark_theme_default'] = self.darkThemeDefaultCheckBox.isChecked()
        o['logger_table_font'] = self.loggerTableFont.currentFont().family()
        o['logger_table_font_size'] = self.loggerTableFontSize.value()
        o['text_view_dialog_font'] = self.textViewFont.currentFont().family()
        o['text_view_dialog_font_size'] = self.textViewFontSize.value()
        o['exception_indication'] = self.excIndicationComboBox.currentIndex()
        new_row_height = self.loggerTableRowHeight.value()
        if new_row_height != CONFIG['logger_row_height']:  # to prevent resizing unnecessarily
            o['logger_row_height'] = new_row_height

        # Search
        o['search_open_default'] = self.searchOpenDefaultCheckBox.isChecked()
        o['search_regex_default'] = self.searchRegexDefaultCheckBox.isChecked()
        o['search_casesensitive_default'] = self.searchCaseSensitiveDefaultCheckBox.isChecked()
        o['search_wildcard_default'] = self.searchWildcardDefaultCheckBox.isChecked()

        # Server
        o['listen_host'] = self.listenHostLine.text()
        o['listen_port'] = int(self.listenPortLine.text())
        o['console_logging_level'] = int(self.logLevelLine.text())
        o['single_tab_mode_default'] = self.singleTabCheckBox.isChecked()

        # Advanced
        o['loop_event_delay'] = float(self.loopEventDelayLine.text())
        o['benchmark_interval'] = float(self.benchmarkIntervalLine.text())
        o['benchmark'] = self.benchmarkCheckBox.isChecked()
        o['light_theme_is_native'] = self.lightThemeNativeCheckBox.isChecked()
        CONFIG.update_options(o)

    def accept(self):
        self.save_to_config()
        if self.server_restart_needed:
            show_info_dialog(self.parent_widget, 'Warning',
                             'You need to restart the server for the changes to take effect')
        self.done(0)

    def reject(self):
        self.done(0)

    def server_options_changed(self):
        self.server_restart_needed = True

    def display_warning(self):
        m = QMessageBox(self.parent_widget)
        m.setText('You need to restart the server for the changes to take effect')
        m.setWindowTitle('Warning')
        m.setIcon(QMessageBox.Information)
        m.show()
