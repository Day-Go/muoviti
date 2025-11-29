"""Template viewer and library widget."""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import config


class TemplateThumbnail(QWidget):
    """Clickable template thumbnail."""

    clicked = pyqtSignal(Path)

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Thumbnail image
        self.image_label = QLabel()
        self.image_label.setFixedSize(100, 100)
        self.image_label.setScaledContents(True)
        self.image_label.setFrameStyle(QLabel.Shape.Box)

        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            self.image_label.setPixmap(pixmap.scaled(
                96, 96,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

        layout.addWidget(self.image_label)

        # Name label
        name_label = QLabel(path.stem)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setMaximumWidth(100)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        """Handle click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.path)


class TemplateViewerWidget(QWidget):
    """Widget for viewing and managing template library."""

    template_selected = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.templates: list[Path] = []
        self.selected_path: Path | None = None

        self._setup_ui()
        self._load_templates()

    def _setup_ui(self):
        """Create viewer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Template Library")
        group_layout = QVBoxLayout(group)

        # Toolbar
        toolbar = QHBoxLayout()

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._load_templates)
        toolbar.addWidget(self.btn_refresh)

        self.btn_import = QPushButton("Import...")
        self.btn_import.clicked.connect(self._import_template)
        toolbar.addWidget(self.btn_import)

        toolbar.addStretch()
        group_layout.addLayout(toolbar)

        # Template grid (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self.grid_widget)

        group_layout.addWidget(scroll, 1)

        # Selected template preview
        preview_group = QGroupBox("Selected Template")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("Select a template")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(150)
        preview_layout.addWidget(self.preview_label)

        # Template name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))

        self.name_edit = QLineEdit()
        self.name_edit.setReadOnly(True)
        name_layout.addWidget(self.name_edit)

        self.btn_rename = QPushButton("Rename")
        self.btn_rename.setEnabled(False)
        self.btn_rename.clicked.connect(self._rename_template)
        name_layout.addWidget(self.btn_rename)

        preview_layout.addLayout(name_layout)

        # Use button
        self.btn_use = QPushButton("Use Template")
        self.btn_use.setEnabled(False)
        self.btn_use.clicked.connect(self._use_template)
        preview_layout.addWidget(self.btn_use)

        group_layout.addWidget(preview_group)

        layout.addWidget(group)

    def _load_templates(self):
        """Load templates from workspace."""
        # Clear existing
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.templates.clear()

        # Find template images
        if config.TEMPLATES_DIR.exists():
            for ext in config.IMAGE_EXTENSIONS:
                self.templates.extend(config.TEMPLATES_DIR.glob(f"*{ext}"))

        # Sort by modification time (newest first)
        self.templates.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Create thumbnails
        cols = 3
        for idx, path in enumerate(self.templates):
            row = idx // cols
            col = idx % cols

            thumb = TemplateThumbnail(path)
            thumb.clicked.connect(self._on_template_clicked)
            self.grid_layout.addWidget(thumb, row, col)

    def _on_template_clicked(self, path: Path):
        """Handle template thumbnail click."""
        self.selected_path = path

        # Update preview
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            self.preview_label.setPixmap(pixmap.scaled(
                300, 300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

        self.name_edit.setText(path.stem)
        self.name_edit.setReadOnly(False)
        self.btn_rename.setEnabled(True)
        self.btn_use.setEnabled(True)

    def _import_template(self):
        """Import template from external location."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Template",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp);;All Files (*)",
        )
        if path:
            import shutil
            src = Path(path)
            dst = config.TEMPLATES_DIR / src.name
            shutil.copy(src, dst)
            self._load_templates()

    def _rename_template(self):
        """Rename selected template."""
        if not self.selected_path:
            return

        new_name = self.name_edit.text().strip()
        if not new_name:
            return

        new_path = self.selected_path.parent / f"{new_name}{self.selected_path.suffix}"
        if new_path != self.selected_path:
            self.selected_path.rename(new_path)
            self.selected_path = new_path
            self._load_templates()

    def _use_template(self):
        """Emit selected template for use in generation."""
        if self.selected_path:
            self.template_selected.emit(self.selected_path)

    def add_template(self, path: Path):
        """Add a new template to the library."""
        if path.parent != config.TEMPLATES_DIR:
            import shutil
            dst = config.TEMPLATES_DIR / path.name
            shutil.copy(path, dst)
            path = dst

        self._load_templates()

        # Select the new template
        self._on_template_clicked(path)
