"""
Tigran Solomon's Paper Archive - Main Entry Point & CLI.

Provides unified interface:
  process_image(image_path, mode, custom_text=None, custom_date=None, ...)
and a full-featured CLI for batch or single processing.
"""

import sys
import argparse
from pathlib import Path
from typing import Union, Optional, List, Dict, Any

from image_loader import load_and_validate_image, ImageLoadError, SUPPORTED_EXTENSIONS
from receipt_processor import process_receipt
from polaroid_processor import process_polaroid
from PIL import Image


def process_image(
    image_path: Union[str, Path],
    mode: str,
    custom_text: Optional[str] = None,
    custom_date: Optional[str] = None,
    output_path: Optional[Union[str, Path]] = None,
    **kwargs: Any
) -> Image.Image:
    """
    Main processing function for Tigran Solomon's Paper Archive.

    Args:
        image_path: Path to the input image (jpg, png, webp).
        mode: Archive mode:
              - 'A' or 'receipt': Thermal Receipt Archive
              - 'B' or 'polaroid': Vintage Polaroid Snap
        custom_text: Optional custom text/items for receipt, or bottom caption for polaroid.
        custom_date: Optional custom date string.
        output_path: Optional path to save the resulting image file.
        **kwargs: Additional mode-specific options:
                  - paper_width: (Receipt) 580 or 800 (default 580).
                  - dither_method: (Receipt) 'floyd' or 'atkinson'.
                  - apply_torn_edges: (Receipt) bool (default True).
                  - aspect_ratio: (Polaroid) '1:1' or '4:5' (default '1:1').
                  - enable_light_leak: (Polaroid) bool (default True).
                  - enable_vignette: (Polaroid) bool (default True).

    Returns:
        PIL.Image: The processed stylized image.

    Raises:
        FileNotFoundError: If input image doesn't exist.
        ValueError: If mode or arguments are invalid.
        ImageLoadError: If image cannot be read or has an unsupported format.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Source image not found: '{path.resolve()}'")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported_str = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ImageLoadError(
            f"Unsupported image format '{ext}'. Supported formats: {supported_str}"
        )

    mode_clean = str(mode).strip().upper()

    if mode_clean in ("A", "RECEIPT", "MODE_A", "MODE-A"):
        paper_width = kwargs.get("paper_width", 580)
        dither_method = kwargs.get("dither_method", "floyd")
        apply_torn_edges = kwargs.get("apply_torn_edges", True)
        custom_title = kwargs.get("custom_title", None)

        result = process_receipt(
            source_image=path,
            paper_width=paper_width,
            dither_method=dither_method,
            custom_title=custom_title,
            custom_text=custom_text,
            custom_date=custom_date,
            apply_torn_edges=apply_torn_edges
        )

    elif mode_clean in ("B", "POLAROID", "MODE_B", "MODE-B"):
        aspect_ratio = kwargs.get("aspect_ratio", "1:1")
        enable_light_leak = kwargs.get("enable_light_leak", True)
        enable_vignette = kwargs.get("enable_vignette", True)
        canvas_width = kwargs.get("canvas_width", 1000)

        result = process_polaroid(
            source_image=path,
            custom_date=custom_date,
            custom_caption=custom_text,
            aspect_ratio=aspect_ratio,
            enable_light_leak=enable_light_leak,
            enable_vignette=enable_vignette,
            canvas_width=canvas_width
        )
    else:
        raise ValueError(
            f"Invalid mode '{mode}'. Choose Mode 'A' (Receipt Archive) or Mode 'B' (Polaroid Snap)."
        )

    # Save output if path specified
    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        # Choose format and quality
        if out_p.suffix.lower() in (".jpg", ".jpeg"):
            if result.mode == "RGBA":
                bg = Image.new("RGB", result.size, (255, 255, 255))
                bg.paste(result, mask=result.split()[3])
                bg.save(out_p, quality=95)
            else:
                result.convert("RGB").save(out_p, quality=95)
        else:
            result.save(out_p)

    return result


def parse_cli_args():
    parser = argparse.ArgumentParser(
        prog="paper_archive",
        description="Tigran Solomon's Paper Archive - Analog Photo Stylization Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Mode A: 1-Bit Thermal Receipt
  python main.py photo.jpg -m A -o receipt.png --text "MEMORY 01\nANALOG TAPE\nFILM SCAN"

  # Mode B: 90s Polaroid Snap
  python main.py portrait.png -m B -o polaroid.png --date "1998-04-18" --text "Tigran Solomon's Paper Archive"
        """
    )

    parser.add_argument("image_path", help="Path to input photo (.jpg, .jpeg, .png, .webp)")
    parser.add_argument(
        "-m", "--mode",
        required=True,
        help="Stylization mode: 'A' (Receipt Archive) or 'B' (Polaroid Snap)"
    )
    parser.add_argument(
        "-t", "--text",
        default=None,
        help="Custom text: item list for receipt (newline-separated) or caption for Polaroid"
    )
    parser.add_argument(
        "-d", "--date",
        default=None,
        help="Custom date string (e.g. '1998-04-18' or '98 10 24')"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output file path (default: archive_{mode}_{input_stem}.png)"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Width in px: 580 or 800 for receipt, 1000 for polaroid"
    )
    parser.add_argument(
        "--dither",
        choices=["floyd", "atkinson"],
        default="floyd",
        help="(Mode A) Dithering algorithm: 'floyd' (Floyd-Steinberg) or 'atkinson'"
    )
    parser.add_argument(
        "--aspect",
        choices=["1:1", "4:5"],
        default="1:1",
        help="(Mode B) Photo aspect ratio: '1:1' (classic square) or '4:5'"
    )
    parser.add_argument(
        "--no-torn-edges",
        action="store_true",
        help="(Mode A) Disable perforated/torn zigzag edges"
    )
    parser.add_argument(
        "--no-light-leak",
        action="store_true",
        help="(Mode B) Disable vintage light leak flare"
    )

    return parser.parse_args()


def main():
    if len(sys.argv) == 1:
        # Show help if invoked with no arguments
        print("=" * 60)
        print("  Tigran Solomon's Paper Archive - Visual Stylization Tool")
        print("=" * 60)
        print("Usage:")
        print("  python main.py <path_to_image> -m <A|B> [-o output.png] [-t text] [-d date]")
        print("\nRun 'python main.py --help' for all options.")
        sys.exit(0)

    try:
        args = parse_cli_args()
    except SystemExit:
        raise

    # Determine default output filename if not given
    input_path = Path(args.image_path)
    if not args.output:
        mode_tag = args.mode.upper()
        out_filename = f"archive_mode_{mode_tag}_{input_path.stem}.png"
        output_path = input_path.parent / out_filename
    else:
        output_path = Path(args.output)

    # Prepare extra kwargs
    extra_kwargs = {}
    if args.width:
        if args.mode.upper() in ("A", "RECEIPT"):
            extra_kwargs["paper_width"] = args.width
        else:
            extra_kwargs["canvas_width"] = args.width

    if args.dither:
        extra_kwargs["dither_method"] = args.dither

    if args.aspect:
        extra_kwargs["aspect_ratio"] = args.aspect

    if args.no_torn_edges:
        extra_kwargs["apply_torn_edges"] = False

    if args.no_light_leak:
        extra_kwargs["enable_light_leak"] = False

    # Execute processing with friendly error handling
    try:
        print(f"[*] Processing image: {input_path}")
        print(f"[*] Selected Mode: {args.mode.upper()}")

        result = process_image(
            image_path=input_path,
            mode=args.mode,
            custom_text=args.text,
            custom_date=args.date,
            output_path=output_path,
            **extra_kwargs
        )

        print(f"[+] Archive generated successfully!")
        print(f"[+] Output saved to: {output_path.resolve()}")
        print(f"[+] Dimensions: {result.size[0]}x{result.size[1]}px | Mode: {result.mode}")

    except FileNotFoundError as err:
        print(f"[ERROR] File not found: {err}", file=sys.stderr)
        sys.exit(1)
    except ImageLoadError as err:
        print(f"[ERROR] Image error: {err}", file=sys.stderr)
        sys.exit(1)
    except ValueError as err:
        print(f"[ERROR] Configuration error: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"[ERROR] Unexpected processing failure: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
