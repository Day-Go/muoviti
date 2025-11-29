"""Frame selector widget for collecting and arranging extracted frames."""

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDrag, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


@dataclass
class FrameSelection:
    """Selected frames with grid configuration."""
    frames: list[Path]
    grid_cols: int
    grid_rows: int


class FrameThumbnail(QLabel):
    """Draggable frame thumbnail."""

    clicked = pyqtSignal(int)  # index
    drag_started = pyqtSignal(int)  # source index

    def __init__(self, index: int, path: Path, parent=None):
        super().__init__(parent)
        self.index = index
        self.path = path

        self.setFixedSize(80, 80)
        self.setScaledContents(True)
        self.setFrameStyle(QLabel.Shape.Box)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)

        # Load thumbnail
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            self.setPixmap(pixmap.scaled(
                76, 76,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        else:
            self.setText(f"{index + 1}")

    def mousePressEvent(self, event):
        """Handle click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)

    def mouseMoveEvent(self, event):
        """Start drag operation."""
        if event.buttons() & Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(self.index))
            drag.setMimeData(mime)

            # Use thumbnail as drag pixmap
            if self.pixmap():
                drag.setPixmap(self.pixmap().scaled(60, 60))

            self.drag_started.emit(self.index)
            drag.exec(Qt.DropAction.MoveAction)


class FrameSelectorWidget(QWidget):
    """Widget for selecting and arranging frames before template generation."""

    generate_template_requested = pyqtSignal(FrameSelection)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames: list[Path] = []
        self.thumbnails: list[FrameThumbnail] = []

        self._setup_ui()

    def _setup_ui(self):
        """Create selector UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Frame Selector")
        group_layout = QVBoxLayout(group)

        # Grid configuration
        config_layout = QHBoxLayout()

        config_layout.addWidget(QLabel("Grid:"))

        self.grid_combo = QComboBox()
        self.grid_combo.addItems([
            "2x2", "3x3", "4x4", "4x6", "5x5", "6x5", "4x8", "8x4",
        ])
        self.grid_combo.setCurrentText("4x4")
        self.grid_combo.currentTextChanged.connect(self._on_grid_changed)
        config_layout.addWidget(self.grid_combo)

        config_layout.addStretch()

        self.frame_count_label = QLabel("0 frames")
        config_layout.addWidget(self.frame_count_label)

        group_layout.addLayout(config_layout)

        # Scrollable frame grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(4)
        scroll.setWidget(self.grid_widget)

        group_layout.addWidget(scroll, 1)

        # Action buttons
        button_layout = QHBoxLayout()

        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.clicked.connect(self.clear_frames)
        button_layout.addWidget(self.btn_clear)

        button_layout.addStretch()

        self.btn_generate = QPushButton("Generate Template")
        self.btn_generate.setEnabled(False)
        self.btn_generate.clicked.connect(self._on_generate_clicked)
        button_layout.addWidget(self.btn_generate)

        group_layout.addLayout(button_layout)

        layout.addWidget(group)

        # Initialize grid placeholders
        self._rebuild_grid()

    def _get_grid_size(self) -> tuple[int, int]:
        """Get current grid dimensions (cols, rows)."""
        text = self.grid_combo.currentText()
        cols, rows = map(int, text.split("x"))
        return cols, rows

    def _rebuild_grid(self):
        """Rebuild the grid layout with current frames."""
        # Clear existing
        for thumb in self.thumbnails:
            thumb.deleteLater()
        self.thumbnails.clear()

        # Clear layout
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols, rows = self._get_grid_size()
        total_slots = cols * rows

        # Create grid cells
        for idx in range(total_slots):
            row = idx // cols
            col = idx % cols

            if idx < len(self.frames):
                # Frame thumbnail
                thumb = FrameThumbnail(idx, self.frames[idx])
                thumb.clicked.connect(self._on_thumbnail_clicked)
                thumb.drag_started.connect(self._on_drag_started)
                self.thumbnails.append(thumb)
                self.grid_layout.addWidget(thumb, row, col)
            else:
                # Empty placeholder
                placeholder = QLabel(str(idx + 1))
                placeholder.setFixedSize(80, 80)
                placeholder.setFrameStyle(QLabel.Shape.Box)
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder.setStyleSheet("color: #888; border: 1px dashed #888;")
                placeholder.setAcceptDrops(True)
                self.grid_layout.addWidget(placeholder, row, col)

        self._update_frame_count()

    def _update_frame_count(self):
        """Update frame count label."""
        cols, rows = self._get_grid_size()
        total = cols * rows
        self.frame_count_label.setText(f"{len(self.frames)}/{total} frames")
        self.btn_generate.setEnabled(len(self.frames) > 0)

    def _on_grid_changed(self, text: str):
        """Handle grid size change."""
        self._rebuild_grid()

    def _on_thumbnail_clicked(self, index: int):
        """Handle thumbnail click - remove frame."""
        if 0 <= index < len(self.frames):
            self.frames.pop(index)
            self._rebuild_grid()

    def _on_drag_started(self, index: int):
        """Handle drag start."""
        pass  # Could add visual feedback

    def _on_generate_clicked(self):
        """Handle generate button click."""
        if not self.frames:
            return

        cols, rows = self._get_grid_size()
        selection = FrameSelection(
            frames=list(self.frames),
            grid_cols=cols,
            grid_rows=rows,
        )
        self.generate_template_requested.emit(selection)

    def add_frame(self, path: Path, frame_num: int = 0):
        """Add a frame to the selection."""
        cols, rows = self._get_grid_size()
        total_slots = cols * rows

        if len(self.frames) < total_slots:
            self.frames.append(path)
            self._rebuild_grid()

    def clear_frames(self):
        """Clear all frames."""
        self.frames.clear()
        self._rebuild_grid()

    def get_selection(self) -> FrameSelection | None:
        """Get current frame selection."""
        if not self.frames:
            return None

        cols, rows = self._get_grid_size()
        return FrameSelection(
            frames=list(self.frames),
            grid_cols=cols,
            grid_rows=rows,
        )
