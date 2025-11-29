"""Main application window."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ui.video_player import VideoPlayerWidget
from ui.frame_selector import FrameSelectorWidget
from ui.template_viewer import TemplateViewerWidget
from ui.generation_panel import GenerationPanelWidget
from core.video import VideoHandler
import config


class MainWindow(QMainWindow):
    """Main application window for Muoviti."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Muoviti - 2D Animation Asset Pipeline")
        self.setMinimumSize(1200, 800)

        # Initialize core components
        self.video_handler = VideoHandler(config.WORKSPACE)

        # Setup UI
        self._setup_menu()
        self._setup_central_widget()
        self._setup_status_bar()

        # Connect signals
        self._connect_signals()

    def _setup_menu(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_video = file_menu.addAction("&Open Video...")
        open_video.setShortcut("Ctrl+O")
        open_video.triggered.connect(self._open_video)

        download_video = file_menu.addAction("&Download from URL...")
        download_video.setShortcut("Ctrl+D")
        download_video.triggered.connect(self._download_video)

        file_menu.addSeparator()

        load_character = file_menu.addAction("Load &Character...")
        load_character.triggered.connect(self._load_character)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        # View menu
        view_menu = menubar.addMenu("&View")

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        settings_action = tools_menu.addAction("&Settings...")
        settings_action.triggered.connect(self._show_settings)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._show_about)

    def _setup_central_widget(self):
        """Setup main layout with splitters."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        # Main vertical splitter
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top section: Video + Frame Selector
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.video_player = VideoPlayerWidget(self.video_handler)
        self.frame_selector = FrameSelectorWidget()

        top_splitter.addWidget(self.video_player)
        top_splitter.addWidget(self.frame_selector)
        top_splitter.setSizes([600, 400])

        # Bottom section: Template Library + Generation
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.template_viewer = TemplateViewerWidget()
        self.generation_panel = GenerationPanelWidget()

        bottom_splitter.addWidget(self.template_viewer)
        bottom_splitter.addWidget(self.generation_panel)
        bottom_splitter.setSizes([500, 500])

        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_splitter)
        main_splitter.setSizes([450, 350])

        layout.addWidget(main_splitter)

    def _setup_status_bar(self):
        """Create status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _connect_signals(self):
        """Connect widget signals."""
        # Video player -> Frame selector
        self.video_player.frame_extracted.connect(self.frame_selector.add_frame)

        # Frame selector -> Generation panel (template generation)
        self.frame_selector.generate_template_requested.connect(
            self.generation_panel.start_template_generation
        )

        # Template viewer -> Generation panel
        self.template_viewer.template_selected.connect(
            self.generation_panel.set_template
        )

    def _open_video(self):
        """Open local video file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            str(config.VIDEOS_DIR),
            "Video Files (*.mp4 *.mkv *.webm *.avi *.mov);;All Files (*)",
        )
        if path:
            self.video_player.load_video(Path(path))
            self.status_bar.showMessage(f"Loaded: {Path(path).name}")

    def _download_video(self):
        """Download video from URL."""
        from PyQt6.QtWidgets import QInputDialog

        url, ok = QInputDialog.getText(
            self,
            "Download Video",
            "Enter YouTube URL:",
        )
        if ok and url:
            self.status_bar.showMessage("Downloading...")
            self.video_player.download_and_load(url)

    def _load_character(self):
        """Load character reference image."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Character",
            str(config.CHARACTERS_DIR),
            "Image Files (*.png *.jpg *.jpeg *.webp);;All Files (*)",
        )
        if path:
            self.generation_panel.set_character(Path(path))
            self.status_bar.showMessage(f"Character loaded: {Path(path).name}")

    def _show_settings(self):
        """Show settings dialog."""
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Muoviti",
            "Muoviti - 2D Animation Asset Pipeline\n\n"
            "Create pixel art animation templates from video references\n"
            "and apply them to AI-generated characters.\n\n"
            "Powered by Google Gemini image generation.",
        )
