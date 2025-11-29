#!/usr/bin/env python3
"""Muoviti - 2D Animation Asset Pipeline Tool."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
import config


def ensure_workspace():
    """Ensure workspace directories exist."""
    config.WORKSPACE.mkdir(parents=True, exist_ok=True)
    config.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    config.FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    config.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    config.CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    """Application entry point."""
    ensure_workspace()

    app = QApplication(sys.argv)
    app.setApplicationName("Muoviti")
    app.setOrganizationName("Muoviti")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
