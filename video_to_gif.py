#!/usr/bin/env python3
"""
Video to GIF Converter with Quality Options and Test Video Generator
"""

import argparse
import sys
import re
import os
import subprocess
import shutil
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple, List
from datetime import datetime


class QualityLevel(Enum):
    """Quality levels for GIF optimization."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Resolution:
    """Resolution class for validating and storing video resolution."""
    width: int
    height: int
    
    # Common aspect ratios and their common resolutions
    COMMON_RESOLUTIONS = {
        "16:9": [(1920, 1080), (1280, 720), (854, 480), (640, 360)],
        "4:3": [(1024, 768), (800, 600), (640, 480)],
        "1:1": [(1080, 1080), (720, 720), (480, 480)],
        "21:9": [(2560, 1080), (1920, 810)],
        "9:16": [(1080, 1920), (720, 1280)],
    }
    
    @classmethod
    def from_string(cls, resolution_str: str) -> "Resolution":
        """Parse resolution string (e.g., '640x480') and validate it."""
        match = re.match(r"^(\d+)x(\d+)$", resolution_str.lower().strip())
        if not match:
            raise ValueError(
                f"Invalid resolution format: '{resolution_str}'. Expected format: WIDTHxHEIGHT (e.g., 640x480)"
            )
        
        width = int(match.group(1))
        height = int(match.group(2))
        
        if width < 1 or height < 1:
            raise ValueError("Resolution dimensions must be positive integers.")
        
        instance = cls(width, height)
        
        # Check if aspect ratio is common
        if not instance.is_common_aspect_ratio():
            print(f"Warning: Resolution {resolution_str} has an uncommon aspect ratio.", file=sys.stderr)
            print("Common resolutions for similar aspect ratios:", file=sys.stderr)
            for aspect, resolutions in cls.COMMON_RESOLUTIONS.items():
                print(f"  {aspect}: {', '.join(f'{w}x{h}' for w, h in resolutions[:3])}", file=sys.stderr)
        
        return instance
    
    def is_common_aspect_ratio(self, tolerance: float = 0.05) -> bool:
        """Check if the aspect ratio is a common one."""
        aspect = self.width / self.height
        
        common_aspects = {
            16/9: "16:9",
            4/3: "4:3",
            1/1: "1:1",
            21/9: "21:9",
            9/16: "9:16",
        }
        
        for common_aspect, _ in common_aspects.items():
            if abs(aspect - common_aspect) / common_aspect < tolerance:
                return True
        return False
    
    def __str__(self) -> str:
        return f"{self.width}x{self.height}"


# ANSI Color codes
class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_summary_table(title: str, rows: List[Tuple[str, str, str]], input_label: str = "Input", output_label: str = "Output"):
    """
    Print a colored formatted summary table.
    
    Args:
        title: Table title
        rows: List of (label, input_value, output_value) tuples
        input_label: Header for input column
        output_label: Header for output column
    """
    # Calculate column widths
    label_width = max(len(row[0]) for row in rows)
    input_width = max(max(len(row[1]) for row in rows), len(input_label))
    output_width = max(max(len(row[2]) for row in rows), len(output_label))
    
    # Add padding
    label_width += 2
    input_width += 2
    output_width += 2
    
    total_width = label_width + input_width + output_width + 4
    
    # Print table with colors
    print()
    print(f"{Colors.CYAN}{'=' * total_width}{Colors.RESET}")
    print(f"{Colors.CYAN}|{Colors.RESET} {Colors.BOLD}{Colors.CYAN}{title.center(total_width - 2)}{Colors.RESET} {Colors.CYAN}|{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * total_width}{Colors.RESET}")
    
    # Header
    print(f"{Colors.CYAN}|{Colors.RESET} {Colors.BOLD}{'Parameter':^{label_width}}{Colors.RESET} {Colors.CYAN}|{Colors.RESET} {Colors.BOLD}{Colors.YELLOW}{input_label:^{input_width}}{Colors.RESET} {Colors.CYAN}|{Colors.RESET} {Colors.BOLD}{Colors.GREEN}{output_label:^{output_width}}{Colors.RESET} {Colors.CYAN}|{Colors.RESET}")
    print(f"{Colors.CYAN}{'-' * total_width}{Colors.RESET}")
    
    # Rows
    for label, input_val, output_val in rows:
        print(f"{Colors.CYAN}|{Colors.RESET} {label:^{label_width}} {Colors.CYAN}|{Colors.RESET} {Colors.YELLOW}{input_val:^{input_width}}{Colors.RESET} {Colors.CYAN}|{Colors.RESET} {Colors.GREEN}{output_val:^{output_width}}{Colors.RESET} {Colors.CYAN}|{Colors.RESET}")
    
    print(f"{Colors.CYAN}{'=' * total_width}{Colors.RESET}")
    print()


class TestVideoGenerator:
    """Generates test videos with configurable parameters using FFmpeg."""
    
    # Valid background colors mapped to FFmpeg color names
    COLOR_MAP = {
        'red': 'red',
        'green': 'green',
        'blue': 'blue',
        'black': 'black',
        'white': 'white',
        'yellow': 'yellow',
        'cyan': 'cyan',
        'magenta': 'magenta',
        'orange': 'orange',
        'purple': 'purple',
        'pink': 'pink',
        'gray': 'gray',
        'grey': 'gray',
        'brown': 'brown',
        'transparent': 'transparent'
    }
    
    def __init__(
        self,
        duration: float,
        resolution: Resolution = None,
        bg_color: str = "red",
        fps: int = 10
    ):
        """
        Initialize the test video generator.
        
        Args:
            duration: Video duration in seconds (must be > 1)
            resolution: Video resolution (default: 640x480)
            bg_color: Background color (default: red)
            fps: Frames per second (default: 10)
        
        Raises:
            ValueError: If parameters are invalid
        """
        if duration <= 1:
            raise ValueError(f"Duration must be greater than 1 second. Got: {duration}")
        
        if resolution is None:
            resolution = Resolution(640, 480)
        
        if fps < 1:
            raise ValueError(f"FPS must be at least 1. Got: {fps}")
        
        bg_color_lower = bg_color.lower()
        if bg_color_lower not in self.COLOR_MAP:
            valid_colors = ', '.join(sorted(set(self.COLOR_MAP.keys())))
            raise ValueError(
                f"Invalid background color: '{bg_color}'. "
                f"Valid colors: {valid_colors}"
            )
        
        self.duration = duration
        self.resolution = resolution
        self.bg_color = self.COLOR_MAP[bg_color_lower]
        self.fps = fps
        
        # Check if FFmpeg is available
        if not shutil.which("ffmpeg"):
            raise RuntimeError("FFmpeg is not installed or not in PATH. Please install FFmpeg.")
    
    def _get_gradient_filter(self) -> str:
        """Generate FFmpeg filter for animated colorful gradient."""
        # Create a colorful animated gradient using geq filter
        # This creates a shifting rainbow gradient effect
        return (
            f"geq="
            f"r='clip(128+128*sin(2*PI*(X+T*{self.fps})/W),0,255)':"
            f"g='clip(128+128*sin(2*PI*(Y+T*{self.fps})/H),0,255)':"
            f"b='clip(128+128*sin(2*PI*(X+Y+T*{self.fps})/(W+H)),0,255)'"
        )
    
    def _get_text_filter(self) -> str:
        """Generate FFmpeg filter for animated text overlay."""
        font_size = max(24, min(self.resolution.width // 20, 48))
        small_font_size = max(16, min(self.resolution.width // 30, 32))
        
        # Create text showing duration, resolution, and elapsed time
        # Escape colons in text by using \\:
        return (
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='Test Video':"
            f"fontcolor=white:fontsize={font_size}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-50:"
            f"box=1:boxcolor=black@0.5:boxborderw=10,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"text='Duration {self.duration}s | {self.resolution} | {self.fps}fps':"
            f"fontcolor=yellow:fontsize={small_font_size}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+20:"
            f"box=1:boxcolor=black@0.5:boxborderw=5,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"text='%{{pts\\:hms}}':"
            f"fontcolor=cyan:fontsize={small_font_size}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+60:"
            f"box=1:boxcolor=black@0.5:boxborderw=5"
        )
    
    def _get_audio_filter(self) -> str:
        """Generate FFmpeg filter for test audio (sine wave beep)."""
        # Create a 1000Hz sine wave with pulsed volume
        # Use a simpler approach: sine wave with tremolo effect for beeping
        return (
            f"sine=frequency=1000:duration={self.duration},"
            f"tremolo=f=1:d=0.1"
        )
    
    def generate(self, output_path: Optional[str] = None) -> str:
        """
        Generate the test video using FFmpeg.
        
        Args:
            output_path: Optional custom path where the video will be saved.
                        If not provided, auto-generates filename with format:
                        test_video_{duration}sec_{resolution}_{date}_{time}.mp4
        
        Returns:
            Path to the generated video
        """
        # Create test_samples directory if it doesn't exist
        test_samples_dir = "test_samples"
        os.makedirs(test_samples_dir, exist_ok=True)
        
        # Auto-generate filename if not provided
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            duration_sec = int(self.duration)
            filename = f"test_video_{duration_sec}sec_{self.resolution}_{timestamp}.mp4"
            output_path = os.path.join(test_samples_dir, filename)
        else:
            # If output_path is just a filename, put it in test_samples
            if os.path.dirname(output_path) == "":
                output_path = os.path.join(test_samples_dir, output_path)
            
            # Ensure output has .mp4 extension
            if not output_path.endswith('.mp4'):
                output_path += '.mp4'
        
        # Build FFmpeg command
        gradient_filter = self._get_gradient_filter()
        text_filter = self._get_text_filter()
        audio_filter = self._get_audio_filter()
        
        # Combine video filters
        video_filter = f"{gradient_filter},{text_filter}"
        
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file if exists
            "-f", "lavfi",
            "-i", f"color=c={self.bg_color}:s={self.resolution}:d={self.duration}:r={self.fps}",
            "-f", "lavfi",
            "-i", audio_filter,
            "-vf", video_filter,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            output_path
        ]
        
        # Run FFmpeg
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr}", file=sys.stderr)
            raise RuntimeError(f"Failed to generate test video: {e}")
        
        # Get file size
        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)
        
        # Print summary table
        rows = [
            ("Duration", "-", f"{self.duration}s"),
            ("Resolution", "-", str(self.resolution)),
            ("Frame Rate", "-", f"{self.fps} fps"),
            ("Background", "-", self.bg_color),
            ("Audio", "-", "1kHz beep (1s interval)"),
            ("Output Path", "-", output_path),
            ("File Size", "-", f"{file_size_mb:.2f} MB"),
        ]
        print_summary_table("TEST VIDEO GENERATION SUMMARY", rows)
        
        return output_path
    
    def __repr__(self) -> str:
        return (
            f"TestVideoGenerator("
            f"duration={self.duration}, "
            f"resolution={self.resolution}, "
            f"bg_color='{self.bg_color}', "
            f"fps={self.fps})"
        )


class GIFConverter:
    """Converts video files to GIF with quality options."""
    
    def __init__(self, quality: QualityLevel = QualityLevel.MEDIUM):
        """
        Initialize the GIF converter.
        
        Args:
            quality: Quality level for the output GIF
        """
        self.quality = quality
        
        # Check if FFmpeg is available
        if not shutil.which("ffmpeg"):
            raise RuntimeError("FFmpeg is not installed or not in PATH. Please install FFmpeg.")
    
    def _get_video_info(self, input_path: str) -> dict:
        """Get video information using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-show_entries", "format=duration,size",
            "-of", "default=noprint_wrappers=1",
            input_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = {}
            for line in result.stdout.strip().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    info[key] = value
            return info
        except subprocess.CalledProcessError:
            return {}
    
    def convert(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Convert a video to GIF.
        
        Args:
            input_path: Path to the input video
            output_path: Optional custom path for the output GIF.
                        If not provided, auto-generates filename with format:
                        {input_name}_{duration}sec_{resolution}_{date}_{time}.gif
        
        Returns:
            Path to the generated GIF
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Get input video info
        input_info = self._get_video_info(input_path)
        input_duration = input_info.get('duration', 'N/A')
        input_resolution = f"{input_info.get('width', 'N/A')}x{input_info.get('height', 'N/A')}"
        input_fps = input_info.get('r_frame_rate', 'N/A')
        if '/' in str(input_fps):
            num, den = input_fps.split('/')
            input_fps = f"{float(num) / float(den):.2f}"
        input_size_mb = float(input_info.get('size', 0)) / (1024 * 1024)
        
        # Auto-generate output filename if not provided
        if output_path is None:
            # Create output directory if it doesn't exist
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            
            # Get input filename without extension
            input_name = os.path.splitext(os.path.basename(input_path))[0]
            
            # Generate filename with format: name_duration_resolution_date_time.gif
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            duration_sec = int(float(input_duration)) if input_duration != 'N/A' else 0
            output_path = os.path.join(output_dir, f"{input_name}_{duration_sec}sec_{input_resolution}_{timestamp}.gif")
        else:
            # If output_path is just a filename, put it in output directory
            if os.path.dirname(output_path) == "":
                output_dir = "output"
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, output_path)
            
            # Ensure output has .gif extension
            if not output_path.endswith('.gif'):
                output_path += '.gif'
        
        print(f"Converting {input_path} to GIF with {self.quality.value} quality...")
        
        start_time = datetime.now()
        
        if self.quality == QualityLevel.LOW:
            output_path = self._convert_low_quality(input_path, output_path)
        elif self.quality == QualityLevel.MEDIUM:
            output_path = self._convert_medium_quality(input_path, output_path)
        elif self.quality == QualityLevel.HIGH:
            output_path = self._convert_high_quality(input_path, output_path)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Get output file size
        output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        
        # Print summary table
        rows = [
            ("Duration", input_duration if input_duration != 'N/A' else '-', "-"),
            ("Resolution", input_resolution if 'N/A' not in input_resolution else '-', "-"),
            ("Frame Rate", f"{input_fps} fps" if input_fps != 'N/A' else '-', "-"),
            ("Quality Level", "-", self.quality.value),
            ("File Size", f"{input_size_mb:.2f} MB" if input_size_mb > 0 else '-', f"{output_size_mb:.2f} MB"),
            ("Processing Time", "-", f"{processing_time:.2f}s"),
            ("Output Path", "-", output_path),
        ]
        print_summary_table("GIF CONVERSION SUMMARY", rows)
        
        return output_path
    
    def _convert_low_quality(self, input_path: str, output_path: str) -> str:
        """
        Low quality: Basic optimization.
        Uses reduced colors and basic compression.
        """
        print("  Using basic optimization (reduced colors, basic compression)")
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vf", "fps=10,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=64[p];[s1][p]paletteuse",
            "-loop", "0",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr}", file=sys.stderr)
            raise RuntimeError(f"Failed to convert video: {e}")
        
        return output_path
    
    def _convert_medium_quality(self, input_path: str, output_path: str) -> str:
        """
        Medium quality: Current optimization.
        Balanced quality and file size.
        """
        print("  Using current optimization (balanced quality and file size)")
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vf", "fps=15,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse",
            "-loop", "0",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr}", file=sys.stderr)
            raise RuntimeError(f"Failed to convert video: {e}")
        
        return output_path
    
    def _convert_high_quality(self, input_path: str, output_path: str) -> str:
        """
        High quality: Advanced dithering with color reduction.
        Uses Bayer dithering and optimized color palette.
        """
        print("  Using advanced dithering with color reduction")
        print("  Features: Bayer dithering, optimized color palette, enhanced sharpness")
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vf", "fps=30,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse=dither=bayer",
            "-loop", "0",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr}", file=sys.stderr)
            raise RuntimeError(f"Failed to convert video: {e}")
        
        return output_path


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Video to GIF Converter with Quality Options and Test Video Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.mp4 output.gif -q high
  %(prog)s --generate-test -d 5 -r 1280x720 -b blue -f 30 test.mp4
        """
    )
    
    # Quality flag
    parser.add_argument(
        "-q", "--quality",
        type=str,
        choices=[q.value for q in QualityLevel],
        default="medium",
        help="GIF quality level (default: medium)\n"
             "  low:    Basic optimization with reduced colors\n"
             "  medium: Current optimization (balanced)\n"
             "  high:   Advanced dithering with color reduction"
    )
    
    # Test video generation subcommand
    parser.add_argument(
        "--generate-test",
        action="store_true",
        help="Generate a test video instead of converting"
    )
    
    parser.add_argument(
        "-d", "--duration",
        type=float,
        help="Test video duration in seconds (required for test generation, must be > 1)"
    )
    
    parser.add_argument(
        "-r", "--resolution",
        type=str,
        default="640x480",
        help="Test video resolution (default: 640x480). Format: WIDTHxHEIGHT"
    )
    
    parser.add_argument(
        "-b", "--bg-color",
        type=str,
        default="red",
        help="Test video background color (default: red). "
             "Valid colors: red, green, blue, black, white, yellow, cyan, magenta, orange, purple, pink, gray, brown"
    )
    
    parser.add_argument(
        "-f", "--fps",
        type=int,
        default=10,
        help="Test video frames per second (default: 10)"
    )
    
    parser.add_argument(
        "input",
        nargs="?",
        help="Input video file path for conversion"
    )
    
    parser.add_argument(
        "output",
        nargs="?",
        help="Optional output file path. If not provided, auto-generates filename with format: name_duration_resolution_date_time.{gif|mp4}"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Handle test video generation
    if args.generate_test:
        if args.duration is None:
            print("Error: --duration is required when generating test videos.", file=sys.stderr)
            sys.exit(1)
        
        try:
            resolution = Resolution.from_string(args.resolution)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        
        try:
            generator = TestVideoGenerator(
                duration=args.duration,
                resolution=resolution,
                bg_color=args.bg_color,
                fps=args.fps
            )
        except (ValueError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Use optional input argument as custom output path, or auto-generate
        try:
            generator.generate(args.input)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return
    
    # Handle video to GIF conversion
    if not args.input:
        print("Error: input video path is required for conversion.", file=sys.stderr)
        print("Use --generate-test to generate a test video.", file=sys.stderr)
        sys.exit(1)
    
    try:
        quality = QualityLevel(args.quality)
        converter = GIFConverter(quality=quality)
        # output is optional - will auto-generate if not provided
        converter.convert(args.input, args.output)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
