"""Grid and sprite sheet utilities."""

from pathlib import Path
from PIL import Image


def calculate_sprite_size(resolution: int, cols: int, rows: int) -> int:
    """Calculate individual sprite dimensions for a square grid cell."""
    return resolution // max(cols, rows)


def calculate_grid_resolution(sprite_size: int, cols: int, rows: int) -> tuple[int, int]:
    """Calculate total grid dimensions from sprite size."""
    return (sprite_size * cols, sprite_size * rows)


def slice_grid(image_path: Path, cols: int, rows: int, output_dir: Path) -> list[Path]:
    """
    Split sprite sheet into individual frames.

    Returns list of paths to extracted frames in row-major order.
    """
    img = Image.open(image_path)
    width, height = img.size
    cell_width = width // cols
    cell_height = height // rows

    output_dir.mkdir(parents=True, exist_ok=True)
    frames = []

    for row in range(rows):
        for col in range(cols):
            left = col * cell_width
            upper = row * cell_height
            right = left + cell_width
            lower = upper + cell_height

            cell = img.crop((left, upper, right, lower))
            frame_path = output_dir / f"frame_{row:02d}_{col:02d}.png"
            cell.save(frame_path)
            frames.append(frame_path)

    return frames


def compose_grid(frames: list[Path], cols: int, rows: int, sprite_size: int) -> Image.Image:
    """
    Compose individual frames into a sprite sheet.

    Frames should be provided in row-major order.
    """
    grid_width = cols * sprite_size
    grid_height = rows * sprite_size
    grid = Image.new("RGBA", (grid_width, grid_height), (0, 0, 0, 0))

    for idx, frame_path in enumerate(frames):
        if idx >= cols * rows:
            break
        row = idx // cols
        col = idx % cols

        frame = Image.open(frame_path)
        frame = frame.resize((sprite_size, sprite_size), Image.Resampling.LANCZOS)

        x = col * sprite_size
        y = row * sprite_size
        grid.paste(frame, (x, y))

    return grid


def center_crop_square(image: Image.Image) -> Image.Image:
    """Center crop image to square aspect ratio."""
    width, height = image.size
    size = min(width, height)

    left = (width - size) // 2
    top = (height - size) // 2
    right = left + size
    bottom = top + size

    return image.crop((left, top, right, bottom))


def create_reference_grid(
    frames: list[Path],
    cols: int,
    rows: int,
    resolution: int = 2048,
) -> Image.Image:
    """
    Create composite image from selected frames for API input.

    Each frame is center-cropped to square and resized to fit evenly
    in a square grid at the target resolution.

    Args:
        frames: List of frame image paths
        cols: Number of columns in grid
        rows: Number of rows in grid
        resolution: Target resolution for the output grid (square)

    Returns:
        Square grid image at target resolution
    """
    if not frames:
        raise ValueError("No frames provided")

    # Calculate cell size for square grid
    cell_size = resolution // max(cols, rows)
    grid_size = cell_size * max(cols, rows)

    grid = Image.new("RGB", (grid_size, grid_size), (255, 255, 255))

    for idx, frame_path in enumerate(frames):
        if idx >= cols * rows:
            break
        row = idx // cols
        col = idx % cols

        # Load, center crop to square, resize to cell size
        frame = Image.open(frame_path).convert("RGB")
        frame = center_crop_square(frame)
        frame = frame.resize((cell_size, cell_size), Image.Resampling.LANCZOS)

        x = col * cell_size
        y = row * cell_size
        grid.paste(frame, (x, y))

    return grid


def resize_to_resolution(image: Image.Image, resolution: int) -> Image.Image:
    """Resize image to fit within resolution (square) while maintaining aspect ratio."""
    width, height = image.size
    scale = resolution / max(width, height)
    new_width = int(width * scale)
    new_height = int(height * scale)
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def pad_to_square(image: Image.Image, fill_color: tuple = (255, 255, 255, 255)) -> Image.Image:
    """Pad image to make it square, centering the original."""
    width, height = image.size
    size = max(width, height)

    padded = Image.new("RGBA", (size, size), fill_color)
    x = (size - width) // 2
    y = (size - height) // 2
    padded.paste(image, (x, y))

    return padded
