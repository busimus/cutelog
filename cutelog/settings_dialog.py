from datetime import datetime

from qtpy.QtGui import QDoubleValidator, QFont, QIntValidator, QValidator
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QMessageBox

from .config import CONFIG, MSGPACK_SUPPORT, CBOR_SUPPORT
from .utils import loadUi, show_info_dialog


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_widget = parent
        self.server_restart_needed = False
        self.time_format_validator = TimeFormatValidator(self)
        self.setupUi()

    def setupUi(self):
        self.ui = loadUi(CONFIG.get_ui_qfile("settings_dialog.ui"), baseinstance=self)
        self.applyButton = self.buttonBox.button(QDialogButtonBox.Apply)
        self.applyButton.clicked.connect(self.save_to_config)
        self.restoreDefaultsButton = self.buttonBox.button(QDialogButtonBox.RestoreDefaults)
        self.restoreDefaultsButton.clicked.connect(self.confirm_restore_defaults)

        self.listenHostLine.textChanged.connect(self.server_options_changed)
        self.listenPortLine.textChanged.connect(self.server_options_changed)

        self.setup_tooltips()

        self.load_from_config()

    def setup_tooltips(self):
        self.benchmarkCheckBox.setToolTip('Has effect after restarting the server, '
                                          '<b>for testing purposes only</b>.')

        self.singleTabCheckBox.setToolTip("Forces all connections into one tab. "
                                          "Useful for when you're restarting one "
                                          "program very often.")

    def load_from_config(self):
        # Appearance page
        self.darkThemeDefaultCheckBox.setChecked(CONFIG['dark_theme_default'])

        self.loggerTableFont.setCurrentFont(QFont(CONFIG['logger_table_font']))
        self.loggerTableFontSize.setValue(CONFIG['logger_table_font_size'])
        self.textViewFont.setCurrentFont(QFont(CONFIG['text_view_dialog_font']))
        self.textViewFontSize.setValue(CONFIG['text_view_dialog_font_size'])
        self.loggerTableRowHeight.setValue(CONFIG['logger_row_height'])
        self.excIndicationComboBox.setCurrentIndex(CONFIG['exception_indication'])
        self.timeFormatLine.setText(CONFIG['time_format_string'])
        self.timeFormatLine.setValidator(self.time_format_validator)
        self.timeFormatLine.textChanged.connect(self.time_format_valid)

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
        self.extraModeCheckBox.setChecked(CONFIG['extra_mode_default'])
        if MSGPACK_SUPPORT:
            self.serializationFormatCombo.addItem("msgpack")
        if CBOR_SUPPORT:
            self.serializationFormatCombo.addItem("cbor")
        i = self.serializationFormatCombo.findText(CONFIG['default_serialization_format'])
        if i != -1:
            self.serializationFormatCombo.setCurrentIndex(i)

        # Advanced page
        self.logLevelLine.setValidator(QIntValidator(0, 1000, self))
        self.logLevelLine.setText(str(CONFIG['console_logging_level']))
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
        o['logger_row_height'] = self.loggerTableRowHeight.value()
        if self.timeFormatLine.hasAcceptableInput():
            o['time_format_string'] = self.timeFormatLine.text()

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
        o['extra_mode_default'] = self.extraModeCheckBox.isChecked()
        o['default_serialization_format'] = self.serializationFormatCombo.currentText()

        # Advanced
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

    def confirm_restore_defaults(self):
        m = QMessageBox(QMessageBox.Question, "Restore to defaults",
                        "Restore settings to the default state?\n"
                        "You'll need to restart the program.",
                        QMessageBox.Yes | QMessageBox.No, self)
        m.setDefaultButton(QMessageBox.No)
        yesButton = m.button(QMessageBox.Yes)
        yesButton.clicked.connect(self.restore_defaults)
        m.show()

    def restore_defaults(self):
        CONFIG.restore_defaults()
        self.done(0)

    def time_format_valid(self, fmt):
        if self.timeFormatLine.hasAcceptableInput():
            self.timeFormatLine.setStyleSheet("QLineEdit {}")
            return True
        else:
            self.timeFormatLine.setStyleSheet("QLineEdit {color: red}")
            return False


class TimeFormatValidator(QValidator):
    def __init__(self, parent):
        super().__init__(parent)

    def validate(self, fmt_string, pos):
        try:
            datetime.now().strftime(fmt_string)
            return self.Acceptable, fmt_string, pos
        except Exception:
            return self.Intermediate, fmt_string, pos
