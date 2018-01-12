from functools import partial

from PyQt5.QtWidgets import (QCheckBox, QColorDialog, QDialog,
                             QDialogButtonBox, QFormLayout, QGridLayout,
                             QGroupBox, QLabel, QLineEdit, QPushButton,
                             QSizePolicy, QSpacerItem)

from .log_levels import DEFAULT_LEVELS, LogLevel


class LevelEditDialog(QDialog):
    def __init__(self, parent, level=None, creating_new_level=False):
        super().__init__(parent)

        if level:
            self.level = level
        else:
            self.level = level = LogLevel(0, 'NOTSET')

        self.creating_new_level = creating_new_level

        self.load_level()
        self.setupUi()
        self.update_output()

    def setupUi(self):
        self.resize(350, 280)
        self.gridLayout = QGridLayout(self)
        self.levelNameLabel = QLabel("Level name", self)
        self.gridLayout.addWidget(self.levelNameLabel, 0, 0)
        self.levelNumberLabel = QLabel("Level number", self)
        self.gridLayout.addWidget(self.levelNumberLabel, 0, 1)

        self.levelNameLine = QLineEdit(self)
        self.levelNoLine = QLineEdit(self)
        self.gridLayout.addWidget(self.levelNameLine, 1, 0)
        self.gridLayout.addWidget(self.levelNoLine, 1, 1)

        self.groupBox = QGroupBox("Light mode", self)
        self.gridLayout.addWidget(self.groupBox, 2, 0)
        self.groupBoxDark = QGroupBox("Dark mode", self)
        self.gridLayout.addWidget(self.groupBoxDark, 2, 1)

        self.formLayout = QFormLayout(self.groupBox)
        self.groupBox.setLayout(self.formLayout)
        self.fgColorPreview = QLineEdit(self)
        self.formLayout.addRow("Foreground", self.fgColorPreview)
        self.bgColorPreview = QLineEdit(self)
        self.formLayout.addRow("Background", self.bgColorPreview)
        self.boldCheckBox = QCheckBox(self.groupBox)
        self.formLayout.addRow("Bold", self.boldCheckBox)
        self.italicCheckBox = QCheckBox(self.groupBox)
        self.formLayout.addRow("Italic", self.italicCheckBox)
        self.underlineCheckBox = QCheckBox(self.groupBox)
        self.formLayout.addRow("Underline", self.underlineCheckBox)

        self.formLayoutDark = QFormLayout(self.groupBoxDark)
        self.groupBoxDark.setLayout(self.formLayoutDark)
        self.fgColorPreviewDark = QLineEdit(self)
        self.formLayoutDark.addRow("Foreground", self.fgColorPreviewDark)
        self.bgColorPreviewDark = QLineEdit(self)
        self.formLayoutDark.addRow("Background", self.bgColorPreviewDark)
        self.boldCheckBoxDark = QCheckBox(self.groupBoxDark)
        self.formLayoutDark.addRow("Bold", self.boldCheckBoxDark)
        self.italicCheckBoxDark = QCheckBox(self.groupBox)
        self.formLayoutDark.addRow("Italic", self.italicCheckBoxDark)
        self.underlineCheckBoxDark = QCheckBox(self.groupBox)
        self.formLayoutDark.addRow("Underline", self.underlineCheckBoxDark)

        self.spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.gridLayout.addItem(self.spacer, 3, 0, 1, 2)

        self.previewLabel = QLabel("Preview", self)
        self.gridLayout.addWidget(self.previewLabel, 4, 0, 1, 2)
        self.previewLine = QLineEdit(self)
        self.gridLayout.addWidget(self.previewLine, 5, 0)
        self.previewLineDark = QLineEdit(self)
        self.gridLayout.addWidget(self.previewLineDark, 5, 1)

        self.resetButton = QPushButton('Reset')
        self.gridLayout.addWidget(self.resetButton, 6, 0)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        self.gridLayout.addWidget(self.buttonBox, 6, 1)

        self.setup_widget_attributes()
        self.setup_widget_connections()

    def setup_widget_attributes(self):

        self.fgColorPreview.setReadOnly(True)
        self.bgColorPreview.setReadOnly(True)
        self.fgColorPreviewDark.setReadOnly(True)
        self.bgColorPreviewDark.setReadOnly(True)

        self.previewLine.setText("Log message")
        self.previewLineDark.setText("Log message")

        self.resetButton.setMaximumWidth(60)
        self.resetButton.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        self.levelNameLine.setText(self.level.levelname)
        self.levelNoLine.setText(str(self.level.levelno))

        if not self.creating_new_level:
            self.levelNoLine.setReadOnly(True)
            self.levelNoLine.setDisabled(True)

        self.set_checkboxes_state()

    def setup_widget_connections(self):
        self.boldCheckBox.toggled.connect(self.toggle_bold)
        self.italicCheckBox.toggled.connect(self.toggle_italic)
        self.underlineCheckBox.toggled.connect(self.toggle_underline)

        self.boldCheckBoxDark.toggled.connect(partial(self.toggle_bold, dark=True))
        self.italicCheckBoxDark.toggled.connect(partial(self.toggle_italic, dark=True))
        self.underlineCheckBoxDark.toggled.connect(partial(self.toggle_underline, dark=True))

        # couldn't find a way to make this any better
        self.fgColorPreview.mouseReleaseEvent = partial(self.open_color_dialog, 'fg')
        self.bgColorPreview.mouseReleaseEvent = partial(self.open_color_dialog, 'bg')
        self.fgColorPreviewDark.mouseReleaseEvent = partial(self.open_color_dialog, 'fgDark')
        self.bgColorPreviewDark.mouseReleaseEvent = partial(self.open_color_dialog, 'bgDark')

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.resetButton.clicked.connect(self.reset_level)

    def set_checkboxes_state(self):
        self.boldCheckBox.setChecked(self.bold)
        self.italicCheckBox.setChecked(self.italic)
        self.underlineCheckBox.setChecked(self.underline)

        self.boldCheckBoxDark.setChecked(self.boldDark)
        self.italicCheckBoxDark.setChecked(self.italicDark)
        self.underlineCheckBoxDark.setChecked(self.underlineDark)

    def load_level(self):
        level = self.level
        self.bg = level.bg
        self.fg = level.fg
        self.bgDark = level.bgDark
        self.fgDark = level.fgDark

        self.bold = 'bold' in level.styles
        self.italic = 'italic' in level.styles
        self.underline = 'underline' in level.styles

        self.boldDark = 'bold' in level.stylesDark
        self.italicDark = 'italic' in level.stylesDark
        self.underlineDark = 'underline' in level.stylesDark

    def reset_level(self):
        if self.level.levelno in DEFAULT_LEVELS:
            replacement = DEFAULT_LEVELS[self.level.levelno]
        else:
            replacement = LogLevel(0, 'NOTSET')

        self.level.copy_level(replacement)
        self.load_level()
        self.set_checkboxes_state()
        self.update_output()

    def toggle_bold(self, value, dark=False):
        if not dark:
            self.bold = value
        else:
            self.boldDark = value
        self.update_output()

    def toggle_italic(self, value, dark=False):
        if not dark:
            self.italic = value
        else:
            self.italicDark = value
        self.update_output()

    def toggle_underline(self, value, dark=False):
        if not dark:
            self.underline = value
        else:
            self.underlineDark = value
        self.update_output()

    def open_color_dialog(self, attr_name, mouse_event):
        d = QColorDialog(self)
        d.setCurrentColor(getattr(self, attr_name))
        f = partial(self.set_color, attr_name)
        d.colorSelected.connect(f)  # d.open(f) doesn't pass color for some reason
        d.open()

    def set_color(self, attr_name, color):
        setattr(self, attr_name, color)
        self.update_output()

    def accept(self):
        self.level.styles = set()
        if self.bold:
            self.level.styles.add('bold')
        if self.italic:
            self.level.styles.add('italic')
        if self.underline:
            self.level.styles.add('underline')

        self.level.stylesDark = set()
        if self.boldDark:
            self.level.stylesDark.add('bold')
        if self.italicDark:
            self.level.stylesDark.add('italic')
        if self.underlineDark:
            self.level.stylesDark.add('underline')

        self.level.bg = self.bg
        self.level.fg = self.fg
        self.level.bgDark = self.bgDark
        self.level.fgDark = self.fgDark

        self.level.levelname = self.levelNameLine.text()
        if self.creating_new_level:
            self.level.levelno = self.levelNoLine.text()

        self.done(0)

    def reject(self):
        self.done(0)

    def update_output(self):
        # Setting the pallette doesn't override the global stylesheet,
        # which is why I can't just set pallete with needed colors here.

        self.previewLine.setStyleSheet("""QLineEdit {{
                                               color: {};
                                               background: {}
                                          }}""".format(self.fg.name(), self.bg.name()))

        self.previewLineDark.setStyleSheet("""QLineEdit {{
                                                   color: {};
                                                   background: {}
                                              }}""".format(self.fgDark.name(), self.bgDark.name()))

        self.bgColorPreview.setStyleSheet('QLineEdit {{background: {} }}'.format(self.bg.name()))
        self.fgColorPreview.setStyleSheet('QLineEdit {{background: {} }}'.format(self.fg.name()))

        self.bgColorPreviewDark.setStyleSheet('QLineEdit {{ background: {} }}'.format(self.bgDark.name()))
        self.fgColorPreviewDark.setStyleSheet('QLineEdit {{ background: {} }}'.format(self.fgDark.name()))

        font = self.previewLine.font()
        font.setBold(self.bold)
        font.setItalic(self.italic)
        font.setUnderline(self.underline)
        self.previewLine.setFont(font)

        fontDark = self.previewLineDark.font()
        fontDark.setBold(self.boldDark)
        fontDark.setItalic(self.italicDark)
        fontDark.setUnderline(self.underlineDark)
        self.previewLineDark.setFont(fontDark)
