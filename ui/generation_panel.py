"""Generation panel for character animation creation."""

import asyncio
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import config
from core.genai_client import MuovitiGenAI
from core.pixel_snapper import PixelSnapper
from core.grid_utils import calculate_sprite_size
from ui.frame_selector import FrameSelection


class GenerationWorker(QThread):
    """Background worker for generation tasks."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(Path)
    error = pyqtSignal(str)

    def __init__(
        self,
        client: MuovitiGenAI,
        mode: str,  # "template" or "character"
        **kwargs,
    ):
        super().__init__()
        self.client = client
        self.mode = mode
        self.kwargs = kwargs

    def run(self):
        """Execute generation."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            if self.mode == "template":
                result = loop.run_until_complete(
                    self.client.generate_template(
                        progress_callback=lambda s: self.progress.emit(s),
                        **self.kwargs,
                    )
                )
            else:
                result = loop.run_until_complete(
                    self.client.apply_template(
                        progress_callback=lambda s: self.progress.emit(s),
                        **self.kwargs,
                    )
                )

            loop.close()
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))


class GenerationPanelWidget(QWidget):
    """Panel for configuring and executing image generation."""

    generation_complete = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.character_path: Path | None = None
        self.template_path: Path | None = None
        self.output_path: Path | None = None
        self.worker: GenerationWorker | None = None

        self._setup_ui()

    def _setup_ui(self):
        """Create panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Generation")
        group_layout = QVBoxLayout(group)

        # Character selection
        char_layout = QHBoxLayout()
        char_layout.addWidget(QLabel("Character:"))

        self.char_path_label = QLabel("None selected")
        self.char_path_label.setStyleSheet("color: #888;")
        char_layout.addWidget(self.char_path_label, 1)

        self.btn_browse_char = QPushButton("Browse...")
        self.btn_browse_char.clicked.connect(self._browse_character)
        char_layout.addWidget(self.btn_browse_char)

        group_layout.addLayout(char_layout)

        # Character preview
        self.char_preview = QLabel()
        self.char_preview.setFixedSize(100, 100)
        self.char_preview.setFrameStyle(QLabel.Shape.Box)
        self.char_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.char_preview.setScaledContents(True)
        group_layout.addWidget(self.char_preview)

        # Template selection
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Template:"))

        self.template_path_label = QLabel("None selected")
        self.template_path_label.setStyleSheet("color: #888;")
        template_layout.addWidget(self.template_path_label, 1)

        self.btn_browse_template = QPushButton("Browse...")
        self.btn_browse_template.clicked.connect(self._browse_template)
        template_layout.addWidget(self.btn_browse_template)

        group_layout.addLayout(template_layout)

        # Resolution selector
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Resolution:"))

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["1024x1024", "2048x2048", "4096x4096"])
        self.resolution_combo.setCurrentText("2048x2048")
        self.resolution_combo.currentTextChanged.connect(self._update_sprite_info)
        res_layout.addWidget(self.resolution_combo)

        res_layout.addStretch()
        group_layout.addLayout(res_layout)

        # Grid size selector
        grid_layout = QHBoxLayout()
        grid_layout.addWidget(QLabel("Grid:"))

        self.grid_combo = QComboBox()
        self.grid_combo.addItems([
            "2x2", "3x3", "4x4", "4x6", "5x5", "6x5", "4x8", "8x4",
        ])
        self.grid_combo.setCurrentText("4x4")
        self.grid_combo.currentTextChanged.connect(self._update_sprite_info)
        grid_layout.addWidget(self.grid_combo)

        self.sprite_info_label = QLabel()
        grid_layout.addWidget(self.sprite_info_label)

        grid_layout.addStretch()
        group_layout.addLayout(grid_layout)

        self._update_sprite_info()

        # Prompt editor (collapsible)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText("Custom prompt (leave empty for default)")
        self.prompt_edit.setMaximumHeight(80)
        group_layout.addWidget(self.prompt_edit)

        # Options
        options_layout = QHBoxLayout()

        self.pixel_snap_check = QCheckBox("Apply Pixel Snapper")
        self.pixel_snap_check.setChecked(True)
        options_layout.addWidget(self.pixel_snap_check)

        options_layout.addStretch()
        group_layout.addLayout(options_layout)

        # Generate button
        self.btn_generate = QPushButton("Generate")
        self.btn_generate.clicked.connect(self._start_generation)
        group_layout.addWidget(self.btn_generate)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v")
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        group_layout.addWidget(self.progress_bar)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #888;")
        group_layout.addWidget(self.status_label)

        # Output preview
        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)

        self.output_preview = QLabel("Output will appear here")
        self.output_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_preview.setMinimumSize(200, 200)
        preview_scroll.setWidget(self.output_preview)

        group_layout.addWidget(preview_scroll, 1)

        # Save button
        self.btn_save = QPushButton("Save Output")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_output)
        group_layout.addWidget(self.btn_save)

        layout.addWidget(group)

    def _get_resolution(self) -> int:
        """Get selected resolution as int."""
        text = self.resolution_combo.currentText()
        return int(text.split("x")[0])

    def _get_grid_size(self) -> tuple[int, int]:
        """Get selected grid size."""
        text = self.grid_combo.currentText()
        cols, rows = map(int, text.split("x"))
        return cols, rows

    def _update_sprite_info(self):
        """Update sprite size info label."""
        resolution = self._get_resolution()
        cols, rows = self._get_grid_size()
        sprite_size = calculate_sprite_size(resolution, cols, rows)
        self.sprite_info_label.setText(f"-> {sprite_size}x{sprite_size}px sprites")

    def _browse_character(self):
        """Browse for character image."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Character",
            str(config.CHARACTERS_DIR),
            "Image Files (*.png *.jpg *.jpeg *.webp);;All Files (*)",
        )
        if path:
            self.set_character(Path(path))

    def _browse_template(self):
        """Browse for template image."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Template",
            str(config.TEMPLATES_DIR),
            "Image Files (*.png *.jpg *.jpeg *.webp);;All Files (*)",
        )
        if path:
            self.set_template(Path(path))

    def set_character(self, path: Path):
        """Set character reference image."""
        self.character_path = path
        self.char_path_label.setText(path.name)
        self.char_path_label.setStyleSheet("")

        # Update preview
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            self.char_preview.setPixmap(pixmap.scaled(
                96, 96,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def set_template(self, path: Path):
        """Set template image."""
        self.template_path = path
        self.template_path_label.setText(path.name)
        self.template_path_label.setStyleSheet("")

    def start_template_generation(self, selection: FrameSelection):
        """Start template generation from frame selection - immediately calls API."""
        # Update grid combo to match selection
        grid_text = f"{selection.grid_cols}x{selection.grid_rows}"
        idx = self.grid_combo.findText(grid_text)
        if idx >= 0:
            self.grid_combo.setCurrentIndex(idx)

        # Check for generic character
        if not config.GENERIC_CHARACTER_PATH.exists():
            self.status_label.setText(f"Error: Generic character not found at {config.GENERIC_CHARACTER_PATH}")
            return

        resolution = self._get_resolution()
        cols, rows = selection.grid_cols, selection.grid_rows

        # Ask user for template name
        suffix = f"_{cols}x{rows}_{resolution}.png"
        name, ok = QInputDialog.getText(
            self,
            "Template Name",
            f"Enter template name (will be saved as [name]{suffix}):",
            text="template",
        )
        if not ok or not name.strip():
            return

        # Build output path in templates folder
        template_filename = f"{name.strip()}{suffix}"
        output_path = config.TEMPLATES_DIR / template_filename

        # Initialize API client
        try:
            client = MuovitiGenAI()
        except ValueError as e:
            self.status_label.setText(f"Error: {e}")
            return

        prompt = self.prompt_edit.toPlainText().strip() or None

        # Create worker for template generation (Flow 1: keyframes -> generic character template)
        self.worker = GenerationWorker(
            client=client,
            mode="template",
            source_frames=selection.frames,
            generic_character=config.GENERIC_CHARACTER_PATH,
            grid_size=(cols, rows),
            resolution=resolution,
            prompt_override=prompt,
            output_path=output_path,
        )

        # Connect signals
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_template_generation_finished)
        self.worker.error.connect(self._on_generation_error)

        # Update UI
        self.btn_generate.setEnabled(False)
        self.progress_bar.show()
        self.status_label.setText("Generating template...")

        self.worker.start()

    def _start_generation(self):
        """Start generation process (Flow 2: template + character -> animation)."""
        # Flow 2 requires both character and template
        if not self.character_path:
            self.status_label.setText("Select a character image first")
            return

        if not self.template_path:
            self.status_label.setText("Select a template first")
            return

        try:
            client = MuovitiGenAI()
        except ValueError as e:
            self.status_label.setText(f"Error: {e}")
            return

        resolution = self._get_resolution()
        cols, rows = self._get_grid_size()
        prompt = self.prompt_edit.toPlainText().strip() or None

        # Character application mode (Flow 2: template + character -> animation)
        self.worker = GenerationWorker(
            client=client,
            mode="character",
            template=self.template_path,
            character=self.character_path,
            grid_size=(cols, rows),
            resolution=resolution,
            prompt_override=prompt,
        )

        # Connect signals
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_generation_finished)
        self.worker.error.connect(self._on_generation_error)

        # Update UI
        self.btn_generate.setEnabled(False)
        self.progress_bar.show()
        self.status_label.setText("Starting...")

        self.worker.start()

    def _on_progress(self, message: str):
        """Handle progress update."""
        self.status_label.setText(message)

    def _on_template_generation_finished(self, output_path: Path):
        """Handle template generation complete (Flow 1: keyframes -> template)."""
        self.output_path = output_path

        # Apply pixel snapper if enabled
        if self.pixel_snap_check.isChecked():
            try:
                self.status_label.setText("Applying pixel snapper...")
                snapper = PixelSnapper()
                snapped_path = output_path.with_stem(output_path.stem + "_snapped")
                self.output_path = snapper.process(output_path, snapped_path)
            except Exception as e:
                self.status_label.setText(f"Pixel snap failed: {e}")

        # Update preview
        pixmap = QPixmap(str(self.output_path))
        if not pixmap.isNull():
            self.output_preview.setPixmap(pixmap.scaled(
                400, 400,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

        # Update UI
        self.progress_bar.hide()
        self.btn_generate.setEnabled(True)
        self.status_label.setText(f"Template saved: {self.output_path.name}")

        # Auto-select this template for Flow 2
        self.set_template(self.output_path)

        self.generation_complete.emit(self.output_path)

    def _on_generation_finished(self, output_path: Path):
        """Handle generation complete."""
        self.output_path = output_path

        # Apply pixel snapper if enabled
        if self.pixel_snap_check.isChecked():
            try:
                self.status_label.setText("Applying pixel snapper...")
                snapper = PixelSnapper()
                snapped_path = output_path.with_stem(output_path.stem + "_snapped")
                self.output_path = snapper.process(output_path, snapped_path)
            except Exception as e:
                self.status_label.setText(f"Pixel snap failed: {e}")

        # Update preview
        pixmap = QPixmap(str(self.output_path))
        if not pixmap.isNull():
            self.output_preview.setPixmap(pixmap.scaled(
                400, 400,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

        # Update UI
        self.progress_bar.hide()
        self.btn_generate.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.status_label.setText(f"Complete: {self.output_path.name}")

        self.generation_complete.emit(self.output_path)

    def _on_generation_error(self, error: str):
        """Handle generation error."""
        self.progress_bar.hide()
        self.btn_generate.setEnabled(True)
        self.status_label.setText(f"Error: {error}")

    def _save_output(self):
        """Save output to chosen location."""
        if not self.output_path:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Output",
            str(config.OUTPUT_DIR / self.output_path.name),
            "PNG Files (*.png);;All Files (*)",
        )
        if path:
            import shutil
            shutil.copy(self.output_path, path)
            self.status_label.setText(f"Saved: {Path(path).name}")
