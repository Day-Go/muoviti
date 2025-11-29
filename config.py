"""Muoviti configuration."""

import os
from pathlib import Path

# Workspace paths
WORKSPACE = Path(__file__).parent / "workspace"
VIDEOS_DIR = WORKSPACE / "videos"
FRAMES_DIR = WORKSPACE / "frames"
TEMPLATES_DIR = WORKSPACE / "templates"
CHARACTERS_DIR = WORKSPACE / "characters"
OUTPUT_DIR = WORKSPACE / "output"

# API configuration
GENAI_API_KEY = os.environ.get("GOOGLE_API_KEY", "YOUR_API_KEY_HERE")

# Grid defaults
DEFAULT_GRID = (4, 4)
RESOLUTIONS = [1024, 2048, 4096]
DEFAULT_RESOLUTION = 2048

# Pixel snapper
PIXEL_SNAPPER_EXECUTABLE = "pixel-snapper"
PIXEL_SNAPPER_PALETTE = 32

# Generic character template path
GENERIC_CHARACTER_PATH = WORKSPACE / "generic_character.png"

# Supported formats
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
