"""Pixel snapper wrapper for fixing AI-generated pixel art."""

import subprocess
import shutil
from pathlib import Path

import config


class PixelSnapper:
    """Wrapper for the pixel-snapper CLI tool."""

    def __init__(self, executable: str | None = None):
        self.executable = executable or config.PIXEL_SNAPPER_EXECUTABLE

        # Check if available
        if not shutil.which(self.executable):
            # Try common locations
            possible_paths = [
                Path.home() / ".cargo" / "bin" / "pixel-snapper",
                Path("/usr/local/bin/pixel-snapper"),
            ]
            for p in possible_paths:
                if p.exists():
                    self.executable = str(p)
                    break

    def is_available(self) -> bool:
        """Check if pixel-snapper is available."""
        return shutil.which(self.executable) is not None

    def process(
        self,
        input_path: Path,
        output_path: Path,
        palette_size: int | None = None,
    ) -> Path:
        """
        Run pixel-snapper to fix mixels in an image.

        Args:
            input_path: Path to input image
            output_path: Path for output image
            palette_size: Optional color palette size (default from config)

        Returns:
            Path to processed image

        Raises:
            RuntimeError: If pixel-snapper fails or is not available
        """
        if not self.is_available():
            raise RuntimeError(
                f"pixel-snapper not found. Install from: "
                f"https://github.com/Hugo-Dz/spritefusion-pixel-snapper"
            )

        palette = palette_size or config.PIXEL_SNAPPER_PALETTE
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.executable,
            str(input_path),
            str(output_path),
            str(palette),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"pixel-snapper failed: {result.stderr}")

        return output_path

    def process_batch(
        self,
        input_paths: list[Path],
        output_dir: Path,
        palette_size: int | None = None,
    ) -> list[Path]:
        """
        Process multiple images.

        Args:
            input_paths: List of input image paths
            output_dir: Directory for output images
            palette_size: Optional color palette size

        Returns:
            List of paths to processed images
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        results = []

        for input_path in input_paths:
            output_path = output_dir / f"{input_path.stem}_snapped{input_path.suffix}"
            self.process(input_path, output_path, palette_size)
            results.append(output_path)

        return results
