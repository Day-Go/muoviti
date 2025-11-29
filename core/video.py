"""Video handling: download, metadata, frame extraction."""

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoMetadata:
    """Video file metadata."""
    path: Path
    duration: float  # seconds
    fps: float
    frame_count: int
    width: int
    height: int


class VideoHandler:
    """Handles video downloading, metadata extraction, and frame extraction."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.videos_dir = workspace / "videos"
        self.frames_dir = workspace / "frames"
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)

    async def download_youtube(
        self,
        url: str,
        progress_callback: callable = None,
    ) -> Path:
        """
        Download video via yt-dlp with progress reporting.

        Args:
            url: YouTube URL
            progress_callback: Optional callback(percent: float, status: str)

        Returns:
            Path to downloaded video file
        """
        import re

        output_template = str(self.videos_dir / "%(title)s.%(ext)s")

        cmd = [
            "yt-dlp",
            # Prefer H.264 (avc1) for compatibility - avoids AV1/VP9 hardware decode issues
            "-f", "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[vcodec^=avc]+bestaudio/best[vcodec^=avc1]/best",
            "--merge-output-format", "mp4",
            "-o", output_template,
            "--newline",  # Progress on separate lines
            "--no-playlist",
            url,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        filepath = None
        progress_pattern = re.compile(r'\[download\]\s+(\d+\.?\d*)%')
        destination_pattern = re.compile(r'\[download\] Destination: (.+)')
        merge_pattern = re.compile(r'\[Merger\] Merging formats into "(.+)"')
        already_pattern = re.compile(r'\[download\] (.+) has already been downloaded')

        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line = line.decode().strip()

            # Parse progress percentage
            match = progress_pattern.search(line)
            if match and progress_callback:
                percent = float(match.group(1))
                progress_callback(percent, f"Downloading: {percent:.1f}%")

            # Capture destination path
            match = destination_pattern.search(line)
            if match:
                filepath = match.group(1)

            # Capture merged output path
            match = merge_pattern.search(line)
            if match:
                filepath = match.group(1)
                if progress_callback:
                    progress_callback(99.0, "Merging audio/video...")

            # Already downloaded
            match = already_pattern.search(line)
            if match:
                filepath = match.group(1)
                if progress_callback:
                    progress_callback(100.0, "Already downloaded")

        await process.wait()

        if process.returncode != 0:
            raise RuntimeError("yt-dlp download failed")

        if not filepath:
            raise RuntimeError("Could not determine output file path")

        if progress_callback:
            progress_callback(100.0, "Complete")

        return Path(filepath)

    def get_metadata(self, video_path: Path) -> VideoMetadata:
        """Extract video metadata using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        # Find video stream
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            raise ValueError("No video stream found")

        # Parse frame rate (e.g., "30/1" or "30000/1001")
        fps_str = video_stream.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = map(int, fps_str.split("/"))
            fps = num / den if den else 30.0
        else:
            fps = float(fps_str)

        duration = float(data.get("format", {}).get("duration", 0))
        frame_count = int(video_stream.get("nb_frames", 0))
        if frame_count == 0:
            frame_count = int(duration * fps)

        return VideoMetadata(
            path=video_path,
            duration=duration,
            fps=fps,
            frame_count=frame_count,
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
        )

    def extract_frame(self, video_path: Path, time_sec: float, output: Path | None = None) -> Path:
        """
        Extract single frame at timestamp.

        Args:
            video_path: Path to video file
            time_sec: Timestamp in seconds
            output: Optional output path. If None, auto-generated in frames_dir.

        Returns:
            Path to extracted frame
        """
        if output is None:
            # Generate unique filename based on video and timestamp
            video_name = video_path.stem
            frame_name = f"{video_name}_{time_sec:.3f}.png"
            output = self.frames_dir / frame_name

        output.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",  # Overwrite
            "-ss", str(time_sec),
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(output),
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output

    def extract_frames_batch(
        self,
        video_path: Path,
        times: list[float],
        output_dir: Path | None = None,
    ) -> list[Path]:
        """
        Batch extract frames at multiple timestamps.

        Args:
            video_path: Path to video file
            times: List of timestamps in seconds
            output_dir: Optional output directory

        Returns:
            List of paths to extracted frames
        """
        if output_dir is None:
            output_dir = self.frames_dir / video_path.stem

        output_dir.mkdir(parents=True, exist_ok=True)
        frames = []

        for idx, time_sec in enumerate(times):
            output = output_dir / f"frame_{idx:04d}.png"
            self.extract_frame(video_path, time_sec, output)
            frames.append(output)

        return frames

    def time_to_frame(self, time_sec: float, fps: float) -> int:
        """Convert timestamp to frame number."""
        return int(time_sec * fps)

    def frame_to_time(self, frame_num: int, fps: float) -> float:
        """Convert frame number to timestamp."""
        return frame_num / fps
