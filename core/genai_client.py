"""Google GenAI client wrapper for image generation using Gemini 3 Pro Image."""

from pathlib import Path
from typing import Callable

from google import genai
from google.genai import types
from PIL import Image

import config
from core.grid_utils import calculate_sprite_size, create_reference_grid


# Resolution mapping for Gemini 3 Pro Image
RESOLUTION_MAP = {
    1024: "1K",
    2048: "2K",
    4096: "4K",
}


class MuovitiGenAI:
    """Wrapper for Google GenAI image generation using Gemini 3 Pro Image."""

    MODEL = "gemini-3-pro-image-preview"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.GENAI_API_KEY
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not set")

        self.client = genai.Client(api_key=self.api_key)

    def _save_response_image(self, response, output_path: Path) -> Path:
        """Extract and save image from response."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        for part in response.parts:
            if part.text is not None:
                continue
            image = part.as_image()
            if image:
                image.save(str(output_path))
                return output_path

        raise ValueError("No image in response")

    async def generate_template(
        self,
        source_frames: list[Path],
        generic_character: Path,
        grid_size: tuple[int, int],
        resolution: int = 2048,
        prompt_override: str | None = None,
        output_path: Path | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> Path:
        """
        Generate segmented template grid from source frames.

        Args:
            source_frames: List of frame image paths
            generic_character: Path to generic colored character reference
            grid_size: (cols, rows) for output grid
            resolution: Output resolution (1024, 2048, or 4096)
            prompt_override: Custom prompt (uses default if None)
            output_path: Where to save output (auto-generated if None)
            progress_callback: Optional callback for status updates

        Returns:
            Path to generated template image
        """
        cols, rows = grid_size

        if progress_callback:
            progress_callback("Preparing reference images...")

        # Create reference grid from source frames at target resolution
        # Frames are center-cropped to square and arranged in grid
        reference_grid = create_reference_grid(source_frames, cols, rows, resolution)
        reference_path = config.WORKSPACE / "temp" / "reference_grid.png"
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        reference_grid.save(reference_path)

        # Load generic character image
        generic_char_img = Image.open(generic_character)

        # Build prompt
        if prompt_override:
            prompt = prompt_override
        else:
            prompt = f"""The first image is a {cols}x{rows} grid of reference keyframes showing a subject in various poses.
The second image is a generic character made of colored body parts.

Create a {cols}x{rows} sprite sheet grid. For each cell:
1. Identify the pose and position of the main subject in the corresponding reference keyframe
2. Draw the generic character in that EXACT same pose and position
3. Match the limb positions precisely using the color-coded body parts:
   - Light blue = head
   - Orange = torso
   - Green = right arm, Purple = left arm
   - Yellow = right leg, Red = left leg

The output grid must have the same layout as the reference - each cell's pose must match the corresponding reference cell exactly.

Pixel art, Gameboy Advance style, pixel perfect, clean edges, no anti-aliasing, white background per cell."""

        if progress_callback:
            progress_callback("Generating template with Gemini 3 Pro Image...")

        # Build contents: prompt first, then reference grid, then generic character
        contents = [
            prompt,
            reference_grid,  # PIL Image - reference keyframes grid
            generic_char_img,  # PIL Image - generic character to use
        ]

        # Determine resolution string
        res_str = RESOLUTION_MAP.get(resolution, "2K")

        # Generate using Gemini 3 Pro Image
        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio="1:1",
                    image_size=res_str,
                ),
            ),
        )

        # Save output
        if output_path is None:
            output_path = config.TEMPLATES_DIR / f"template_{cols}x{rows}_{resolution}.png"

        if progress_callback:
            progress_callback("Saving template...")

        return self._save_response_image(response, output_path)

    async def apply_template(
        self,
        template: Path,
        character: Path,
        grid_size: tuple[int, int],
        resolution: int = 2048,
        prompt_override: str | None = None,
        output_path: Path | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> Path:
        """
        Apply template poses to character reference.

        Args:
            template: Path to template grid image (keyframe poses)
            character: Path to character reference image
            grid_size: (cols, rows) matching the template
            resolution: Output resolution
            prompt_override: Custom prompt (uses default if None)
            output_path: Where to save output
            progress_callback: Optional callback for status updates

        Returns:
            Path to generated character animation image
        """
        cols, rows = grid_size

        if progress_callback:
            progress_callback("Preparing images...")

        # Load images
        template_img = Image.open(template)
        character_img = Image.open(character)

        # Build prompt
        if prompt_override:
            prompt = prompt_override
        else:
            prompt = f"""The first image is a {cols}x{rows} keyframe template grid showing {cols * rows} poses using colored body parts.
The second image is the character to render.

Generate a {cols}x{rows} sprite sheet grid with EXACTLY {cols} columns and {rows} rows.

CRITICAL: Each cell in your output must match the EXACT pose from the corresponding cell in the template:
- Row 1, Col 1 of output = pose from Row 1, Col 1 of template
- Row 1, Col 2 of output = pose from Row 1, Col 2 of template
- And so on for all {cols * rows} cells.

The template uses color coding for body parts:
- Light blue = head position
- Orange = torso position
- Green = right arm, Purple = left arm
- Yellow = right leg, Red = left leg

Render the character in each pose matching the template exactly. Maintain the character's appearance (face, hair, clothing, colors) consistently across all frames.

Pixel art style, clean pixel edges, white background per cell."""

        if progress_callback:
            progress_callback("Generating character animation with Gemini 3 Pro Image...")

        # Build contents: prompt, keyframe template, character reference
        contents = [
            prompt,
            template_img,  # PIL Image - keyframe template with poses
            character_img,  # PIL Image - character to animate
        ]

        # Determine resolution string
        res_str = RESOLUTION_MAP.get(resolution, "2K")

        # Generate using Gemini 3 Pro Image
        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio="1:1",
                    image_size=res_str,
                ),
            ),
        )

        # Save output
        if output_path is None:
            char_name = character.stem
            output_path = config.OUTPUT_DIR / f"{char_name}_{cols}x{rows}_{resolution}.png"

        if progress_callback:
            progress_callback("Saving output...")

        return self._save_response_image(response, output_path)

    def test_connection(self) -> bool:
        """Test API connection."""
        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents="Say 'ok' and nothing else.",
            )
            return True
        except Exception as e:
            print(f"API connection test failed: {e}")
            return False
