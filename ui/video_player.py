"""Video player widget with frame-by-frame navigation."""

import re
import subprocess
from pathlib import Path

from PyQt6.QtCore import QThread, QTimer, QUrl, pyqtSignal, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.video import VideoHandler, VideoMetadata


class DownloadWorker(QThread):
    """Background worker for downloading videos."""

    progress = pyqtSignal(float, str)  # percent, status
    finished = pyqtSignal(Path)
    error = pyqtSignal(str)

    def __init__(self, url: str, output_dir: Path):
        super().__init__()
        self.url = url
        self.output_dir = output_dir

    def run(self):
        """Execute download with progress parsing."""
        output_template = str(self.output_dir / "%(title)s.%(ext)s")

        cmd = [
            "yt-dlp",
            # Prefer H.264 (avc1) for compatibility, fall back to other codecs
            "-f", "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[vcodec^=avc]+bestaudio/best[vcodec^=avc1]/best",
            "--merge-output-format", "mp4",
            "-o", output_template,
            "--newline",
            "--no-playlist",
            self.url,
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            filepath = None
            progress_pattern = re.compile(r'\[download\]\s+(\d+\.?\d*)%')
            destination_pattern = re.compile(r'\[download\] Destination: (.+)')
            merge_pattern = re.compile(r'\[Merger\] Merging formats into "(.+)"')
            already_pattern = re.compile(r'\[download\] (.+) has already been downloaded')

            for line in process.stdout:
                line = line.strip()

                # Parse progress
                match = progress_pattern.search(line)
                if match:
                    percent = float(match.group(1))
                    self.progress.emit(percent, f"Downloading: {percent:.1f}%")

                # Capture destination
                match = destination_pattern.search(line)
                if match:
                    filepath = match.group(1)

                # Capture merged output
                match = merge_pattern.search(line)
                if match:
                    filepath = match.group(1)
                    self.progress.emit(99.0, "Merging audio/video...")

                # Already downloaded
                match = already_pattern.search(line)
                if match:
                    filepath = match.group(1)
                    self.progress.emit(100.0, "Already downloaded")

            process.wait()

            if process.returncode != 0:
                self.error.emit("yt-dlp download failed")
                return

            if not filepath:
                self.error.emit("Could not determine output file path")
                return

            self.progress.emit(100.0, "Complete")
            self.finished.emit(Path(filepath))

        except Exception as e:
            self.error.emit(str(e))


class VideoPlayerWidget(QWidget):
    """Video player with playback controls and frame extraction."""

    frame_extracted = pyqtSignal(Path, int)  # path, frame_number
    video_loaded = pyqtSignal(dict)  # metadata dict

    def __init__(self, video_handler: VideoHandler, parent=None):
        super().__init__(parent)
        self.video_handler = video_handler
        self.metadata: VideoMetadata | None = None
        self._seeking = False
        self._download_worker: DownloadWorker | None = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Create player UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Group box
        group = QGroupBox("Video Player")
        group_layout = QVBoxLayout(group)

        # Video widget
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(400, 300)
        group_layout.addWidget(self.video_widget, 1)

        # Media player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        # Timeline slider
        timeline_layout = QHBoxLayout()

        self.time_label = QLabel("00:00:00")
        self.time_label.setFixedWidth(70)
        timeline_layout.addWidget(self.time_label)

        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 1000)
        timeline_layout.addWidget(self.timeline)

        self.duration_label = QLabel("00:00:00")
        self.duration_label.setFixedWidth(70)
        timeline_layout.addWidget(self.duration_label)

        group_layout.addLayout(timeline_layout)

        # Playback controls
        controls_layout = QHBoxLayout()

        self.btn_prev_10 = QPushButton("<<")
        self.btn_prev_10.setToolTip("Back 10 frames (Shift+Left)")
        self.btn_prev_10.setFixedWidth(40)
        controls_layout.addWidget(self.btn_prev_10)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setToolTip("Back 1 frame (Left)")
        self.btn_prev.setFixedWidth(40)
        controls_layout.addWidget(self.btn_prev)

        self.btn_play = QPushButton("Play")
        self.btn_play.setFixedWidth(60)
        controls_layout.addWidget(self.btn_play)

        self.btn_next = QPushButton(">")
        self.btn_next.setToolTip("Forward 1 frame (Right)")
        self.btn_next.setFixedWidth(40)
        controls_layout.addWidget(self.btn_next)

        self.btn_next_10 = QPushButton(">>")
        self.btn_next_10.setToolTip("Forward 10 frames (Shift+Right)")
        self.btn_next_10.setFixedWidth(40)
        controls_layout.addWidget(self.btn_next_10)

        controls_layout.addStretch()

        # Frame number display
        frame_label = QLabel("Frame:")
        controls_layout.addWidget(frame_label)

        self.frame_spinbox = QSpinBox()
        self.frame_spinbox.setRange(0, 0)
        self.frame_spinbox.setFixedWidth(80)
        controls_layout.addWidget(self.frame_spinbox)

        controls_layout.addStretch()

        # Mark/Extract button
        self.btn_mark = QPushButton("Mark Frame")
        self.btn_mark.setToolTip("Extract current frame (Space)")
        self.btn_mark.setFixedWidth(100)
        controls_layout.addWidget(self.btn_mark)

        group_layout.addLayout(controls_layout)

        # Download progress bar (hidden by default)
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setTextVisible(True)
        self.download_progress.hide()
        group_layout.addWidget(self.download_progress)

        self.download_status = QLabel()
        self.download_status.setStyleSheet("color: #888;")
        self.download_status.hide()
        group_layout.addWidget(self.download_status)

        layout.addWidget(group)

        # Enable keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _connect_signals(self):
        """Connect internal signals."""
        # Player signals
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)

        # Control buttons
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_prev.clicked.connect(self._step_prev)
        self.btn_next.clicked.connect(self._step_next)
        self.btn_prev_10.clicked.connect(self._step_prev_10)
        self.btn_next_10.clicked.connect(self._step_next_10)
        self.btn_mark.clicked.connect(self._extract_current_frame)

        # Timeline
        self.timeline.sliderPressed.connect(self._on_slider_pressed)
        self.timeline.sliderReleased.connect(self._on_slider_released)
        self.timeline.sliderMoved.connect(self._on_slider_moved)

        # Frame spinbox
        self.frame_spinbox.valueChanged.connect(self._on_frame_changed)

    def load_video(self, path: Path):
        """Load video from local path."""
        self.metadata = self.video_handler.get_metadata(path)
        self.player.setSource(QUrl.fromLocalFile(str(path)))

        # Update UI
        self.frame_spinbox.setRange(0, self.metadata.frame_count - 1)
        self._update_duration_label()

        self.video_loaded.emit({
            "path": str(path),
            "duration": self.metadata.duration,
            "fps": self.metadata.fps,
            "frame_count": self.metadata.frame_count,
            "width": self.metadata.width,
            "height": self.metadata.height,
        })

    def download_and_load(self, url: str):
        """Download video from URL and load it."""
        # Show progress UI
        self.download_progress.setValue(0)
        self.download_progress.show()
        self.download_status.setText("Starting download...")
        self.download_status.show()

        # Create and start download worker
        self._download_worker = DownloadWorker(url, self.video_handler.videos_dir)
        self._download_worker.progress.connect(self._update_download_progress)
        self._download_worker.finished.connect(self._on_download_complete)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.start()

    def _update_download_progress(self, percent: float, status: str):
        """Update download progress bar."""
        self.download_progress.setValue(int(percent))
        self.download_status.setText(status)

    def _on_download_complete(self, path: Path):
        """Handle download completion."""
        self.download_progress.hide()
        self.download_status.hide()
        self.load_video(path)

    def _on_download_error(self, error: str):
        """Handle download error."""
        self.download_progress.hide()
        self.download_status.setText(f"Error: {error}")
        self.download_status.setStyleSheet("color: red;")

    def _toggle_play(self):
        """Toggle play/pause."""
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _step_prev(self):
        """Step back 1 frame."""
        self._step_frames(-1)

    def _step_next(self):
        """Step forward 1 frame."""
        self._step_frames(1)

    def _step_prev_10(self):
        """Step back 10 frames."""
        self._step_frames(-10)

    def _step_next_10(self):
        """Step forward 10 frames."""
        self._step_frames(10)

    def _step_frames(self, count: int):
        """Step forward/backward by frame count."""
        if not self.metadata:
            return

        self.player.pause()
        current_frame = self.frame_spinbox.value()
        new_frame = max(0, min(current_frame + count, self.metadata.frame_count - 1))

        time_ms = int(self.video_handler.frame_to_time(new_frame, self.metadata.fps) * 1000)
        self.player.setPosition(time_ms)

    def _extract_current_frame(self):
        """Extract current frame and emit signal."""
        if not self.metadata:
            return

        current_time = self.player.position() / 1000.0  # ms to seconds
        frame_num = self.video_handler.time_to_frame(current_time, self.metadata.fps)

        path = self.video_handler.extract_frame(self.metadata.path, current_time)
        self.frame_extracted.emit(path, frame_num)

    def _on_duration_changed(self, duration: int):
        """Handle duration change."""
        self.timeline.setRange(0, duration)

    def _on_position_changed(self, position: int):
        """Handle position change."""
        if not self._seeking:
            self.timeline.setValue(position)
            self._update_time_label(position)

            if self.metadata:
                frame = self.video_handler.time_to_frame(
                    position / 1000.0, self.metadata.fps
                )
                self.frame_spinbox.blockSignals(True)
                self.frame_spinbox.setValue(frame)
                self.frame_spinbox.blockSignals(False)

    def _on_playback_state_changed(self, state):
        """Handle playback state change."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("Pause")
        else:
            self.btn_play.setText("Play")

    def _on_slider_pressed(self):
        """Handle slider press."""
        self._seeking = True

    def _on_slider_released(self):
        """Handle slider release."""
        self._seeking = False
        self.player.setPosition(self.timeline.value())

    def _on_slider_moved(self, position: int):
        """Handle slider move."""
        self._update_time_label(position)

    def _on_frame_changed(self, frame: int):
        """Handle frame spinbox change."""
        if not self.metadata:
            return

        time_ms = int(self.video_handler.frame_to_time(frame, self.metadata.fps) * 1000)
        self.player.setPosition(time_ms)

    def _update_time_label(self, position_ms: int):
        """Update current time label."""
        secs = position_ms // 1000
        mins = secs // 60
        hours = mins // 60
        self.time_label.setText(f"{hours:02d}:{mins % 60:02d}:{secs % 60:02d}")

    def _update_duration_label(self):
        """Update duration label."""
        if not self.metadata:
            return

        secs = int(self.metadata.duration)
        mins = secs // 60
        hours = mins // 60
        self.duration_label.setText(f"{hours:02d}:{mins % 60:02d}:{secs % 60:02d}")

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Space:
            self._extract_current_frame()
        elif event.key() == Qt.Key.Key_Left:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._step_frames(-10)
            else:
                self._step_frames(-1)
        elif event.key() == Qt.Key.Key_Right:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._step_frames(10)
            else:
                self._step_frames(1)
        elif event.key() == Qt.Key.Key_K:
            self._toggle_play()
        else:
            super().keyPressEvent(event)
