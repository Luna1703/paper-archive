"""
Image Loader and Validator module for Tigran Solomon's Paper Archive.
Provides non-destructive image loading, format verification, and normalization.
"""

from pathlib import Path
from typing import Union, Tuple, Optional
import os
from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class ImageLoadError(Exception):
    """Custom exception raised when image loading or validation fails."""
    pass


def validate_image_path(image_path: Union[str, Path]) -> Path:
    """
    Validates that the file exists and has a supported image extension.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: '{path.resolve()}'")
    if not path.is_file():
        raise ImageLoadError(f"Provided path is not a regular file: '{path.resolve()}'")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported_list = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ImageLoadError(
            f"Unsupported image format '{ext}'. Supported formats: {supported_list}"
        )

    return path


def load_and_validate_image(
    source: Union[str, Path, Image.Image],
    target_max_size: Optional[Tuple[int, int]] = (1200, 1200),
    convert_mode: str = "RGB"
) -> Image.Image:
    """
    Safely loads and validates an image without modifying the original.
    Performs format validation, EXIF orientation correction, and uniform resizing.

    Args:
        source: File path (str/Path) or an existing PIL Image.
        target_max_size: Optional (max_width, max_height) to scale working image.
        convert_mode: Target color mode ('RGB', 'RGBA', etc.). Default 'RGB'.

    Returns:
        PIL.Image: A new copy of the loaded, normalized image.
    """
    if isinstance(source, Image.Image):
        img_copy = source.copy()
    else:
        path = validate_image_path(source)
        try:
            with Image.open(path) as img:
                img_copy = img.copy()
        except Exception as e:
            raise ImageLoadError(f"Failed to decode image from '{path}': {e}") from e

    # Correct EXIF orientation if present (e.g. photos from mobile cameras)
    try:
        img_copy = ImageOps.exif_transpose(img_copy)
    except Exception:
        pass

    # Convert to desired mode while properly handling transparency
    if convert_mode == "RGB":
        if img_copy.mode in ("RGBA", "LA") or (img_copy.mode == "P" and "transparency" in img_copy.info):
            background = Image.new("RGB", img_copy.size, (255, 255, 255))
            alpha_img = img_copy.convert("RGBA")
            background.paste(alpha_img, mask=alpha_img.split()[3])
            img_copy = background
        else:
            img_copy = img_copy.convert("RGB")
    elif convert_mode != img_copy.mode:
        img_copy = img_copy.convert(convert_mode)

    # Resize to working resolution preserving aspect ratio
    if target_max_size:
        max_w, max_h = target_max_size
        img_copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

    return img_copy
