from copy import deepcopy
from functools import partial

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QBrush, QFont
from qtpy.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout,
                            QHeaderView, QInputDialog, QLabel, QMenu,
                            QTableWidget, QTableWidgetItem, QVBoxLayout,
                            QWidget)

from .config import CONFIG
from .level_edit_dialog import LevelEditDialog
from .log_levels import DEFAULT_LEVELS, get_default_level
from .utils import show_warning_dialog


class LevelsPresetDialog(QDialog):
    # name of the current preset; whether to set this preset as default; dict of Levels
    levels_changed = Signal(str, bool, dict)

    def __init__(self, parent, preset_name, levels):
        super().__init__(parent)

        self.preset_name = preset_name
        self.levels = deepcopy(levels)

        self.setupUi()
        self.update_output()

    def setupUi(self):
        self.resize(480, 340)
        self.vbox = QVBoxLayout(self)
        self.presetLabel = QLabel(self)
        self.table = QTableWidget(0, 4, self)
        self.setAsDefaultCheckbox = QCheckBox("Set as default preset", self)
        self.vbox.addWidget(self.presetLabel)
        self.vbox.addWidget(self.table)
        self.vbox.addWidget(self.setAsDefaultCheckbox)

        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setHorizontalHeaderLabels(["Show", "Level name", "Preview", "Preview (dark)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionsClickable(False)
        self.table.horizontalHeader().setSectionsMovable(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.open_level_edit_dialog)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)

        buttons = QDialogButtonBox.Reset | QDialogButtonBox.Save | QDialogButtonBox.Cancel
        self.buttonBox = QDialogButtonBox(buttons, self)
        self.vbox.addWidget(self.buttonBox)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.resetButton = self.buttonBox.button(QDialogButtonBox.Reset)
        self.resetButton.clicked.connect(self.reset)

    def update_output(self):
        self.presetLabel.setText("Preset: {}".format(self.preset_name))
        self.setAsDefaultCheckbox.setChecked(CONFIG['default_levels_preset'] == self.preset_name)
        self.table.clearContents()
        self.table.setRowCount(len(self.levels))

        for i, levelname in enumerate(self.levels):
            level = self.levels[levelname]
            checkbox = self.get_level_show_checkbox(level)
            nameItem = QTableWidgetItem(level.levelname)
            preview, previewDark = self.get_preview_items(level)

            self.table.setCellWidget(i, 0, checkbox)
            self.table.setItem(i, 1, nameItem)
            self.table.setItem(i, 2, preview)
            self.table.setItem(i, 3, previewDark)

    def get_level_show_checkbox(self, level):
        checkbox_widget = QWidget(self.table)
        checkbox_widget.setStyleSheet("QWidget { background-color:none;}")

        checkbox = QCheckBox()
        checkbox.setStyleSheet("QCheckBox::indicator { width: 15px; height: 15px;}")
        checkbox.setChecked(level.enabled)

        checkbox_layout = QHBoxLayout()
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.addWidget(checkbox)
        checkbox_widget.setLayout(checkbox_layout)
        return checkbox_widget

    def get_preview_items(self, level):
        previewItem = QTableWidgetItem("Log message")
        previewItem.setBackground(QBrush(level.bg, Qt.SolidPattern))
        previewItem.setForeground(QBrush(level.fg, Qt.SolidPattern))
        previewItemDark = QTableWidgetItem("Log message")
        previewItemDark.setBackground(QBrush(level.bgDark, Qt.SolidPattern))
        previewItemDark.setForeground(QBrush(level.fgDark, Qt.SolidPattern))
        font = QFont(CONFIG.logger_table_font, CONFIG.logger_table_font_size)
        fontDark = QFont(font)
        if 'bold' in level.styles:
            font.setBold(True)
        if 'italic' in level.styles:
            font.setItalic(True)
        if 'underline' in level.styles:
            font.setUnderline(True)
        if 'bold' in level.stylesDark:
            fontDark.setBold(True)
        if 'italic' in level.stylesDark:
            fontDark.setItalic(True)
        if 'underline' in level.stylesDark:
            fontDark.setUnderline(True)
        previewItem.setFont(font)
        previewItemDark.setFont(fontDark)
        return previewItem, previewItemDark

    def open_level_edit_dialog(self, index):
        levelname = self.table.item(index.row(), 1).data(Qt.DisplayRole)
        level = self.levels[levelname]
        d = LevelEditDialog(self, level)
        d.setWindowModality(Qt.NonModal)
        d.setWindowTitle('Level editor')
        d.level_changed.connect(self.update_output)
        d.open()

    def open_menu(self, position):
        menu = QMenu(self)

        preset_menu = menu.addMenu('Presets')
        preset_menu.addAction('New preset', self.new_preset_dialog)
        preset_menu.addSeparator()

        preset_names = CONFIG.get_levels_presets()

        if len(preset_names) == 0:
            action = preset_menu.addAction('No presets')
            action.setEnabled(False)
        else:
            delete_menu = menu.addMenu('Delete preset')
            for name in preset_names:
                preset_menu.addAction(name, partial(self.load_preset, name))
                delete_menu.addAction(name, partial(self.delete_preset, name))

        menu.addSeparator()
        menu.addAction('New level...', self.create_new_level_dialog)

        if len(self.table.selectedIndexes()) > 0:
            menu.addAction('Delete selected', self.delete_selected)

        menu.popup(self.table.viewport().mapToGlobal(position))

    def load_preset(self, name):
        new_levels = CONFIG.load_levels_preset(name)
        if not new_levels:
            return

        self.levels = new_levels
        self.preset_name = name
        self.update_output()

    def delete_preset(self, name):
        CONFIG.delete_levels_preset(name)
        if name == self.preset_name:
            self.reset()

    def delete_selected(self):
        selected = self.table.selectionModel().selectedRows()
        for index in selected:
            item = self.table.item(index.row(), 1)
            del self.levels[item.text()]
        self.update_output()

    def new_preset_dialog(self):
        d = QInputDialog(self)
        d.setLabelText('Enter the new name for the new preset:')
        d.setWindowTitle('Create new preset')
        d.textValueSelected.connect(self.create_new_preset)
        d.open()

    def create_new_preset(self, name):
        if name in CONFIG.get_levels_presets():
            show_warning_dialog(self, "Preset creation error",
                                'Preset named "{}" already exists.'.format(name))
            return
        if len(name.strip()) == 0:
            show_warning_dialog(self, "Preset creation error",
                                'This preset name is not allowed.'.format(name))
            return

        self.preset_name = name
        self.update_output()
        CONFIG.save_levels_preset(name, self.levels)

    def create_new_level_dialog(self):
        d = LevelEditDialog(self, creating_new_level=True, level_names=self.levels.keys())
        d.setWindowModality(Qt.NonModal)
        d.setWindowTitle('Level editor')
        d.level_changed.connect(self.level_changed)
        d.open()

    def level_changed(self, level):
        if level.levelname in self.levels:
            self.levels.copy_from(level)
        else:
            self.levels[level.levelname] = level
        self.update_output()

    def accept(self):
        for i, _ in enumerate(self.levels):
            checkbox = self.table.cellWidget(i, 0).children()[1]
            levelname = self.table.item(i, 1).text()
            self.levels[levelname].enabled = checkbox.isChecked()
        self.levels_changed.emit(self.preset_name,
                                 self.setAsDefaultCheckbox.isChecked(),
                                 self.levels)
        self.done(0)

    def reject(self):
        self.done(0)

    def reset(self):
        for levelname, level in self.levels.items():
            level.copy_from(get_default_level(levelname))
        self.update_output()
