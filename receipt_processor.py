"""
Mode A: Receipt Archive Processor for Tigran Solomon's Paper Archive.
Transforms an input photo into an authentic 1-bit dithered thermal print receipt
with customizable header, itemized receipt list, QR code, and perforated/torn edges.
"""

import time
import random
import os
from pathlib import Path
from typing import Union, Optional, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode

from image_loader import load_and_validate_image


ASSETS_DIR = Path(__file__).parent / "assets" / "fonts"
DEFAULT_PIXEL_FONT = ASSETS_DIR / "VT323-Regular.ttf"
ALT_PIXEL_FONT = ASSETS_DIR / "PressStart2P-Regular.ttf"


def get_font(font_path: Path, size: int) -> ImageFont.ImageFont:
    """Safely loads a TTF font or falls back to PIL default font."""
    if font_path.exists():
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception:
            pass
    return ImageFont.load_default()


def adjust_contrast_histogram_stretch(
    img_gray: Image.Image,
    low_percentile: float = 2.0,
    high_percentile: float = 98.0
) -> Image.Image:
    """
    Applies percentile-based histogram stretching to enhance contrast
    and ensure facial and subject details remain clear prior to dithering.
    """
    arr = np.array(img_gray, dtype=np.float32)
    p_low = np.percentile(arr, low_percentile)
    p_high = np.percentile(arr, high_percentile)

    if p_high > p_low:
        stretched = np.clip((arr - p_low) / (p_high - p_low) * 255.0, 0, 255)
    else:
        stretched = arr

    return Image.fromarray(stretched.astype(np.uint8), mode="L")


def apply_floyd_steinberg_dithering(img_gray: Image.Image) -> Image.Image:
    """
    Applies classic Floyd-Steinberg error diffusion dithering (1-bit output).
    Error diffusion coefficients:
      [x+1, y]     += err * 7/16
      [x-1, y+1]   += err * 3/16
      [x,   y+1]   += err * 5/16
      [x+1, y+1]   += err * 1/16
    """
    arr = np.array(img_gray, dtype=np.float32)
    h, w = arr.shape

    # Process row by row with error distribution
    for y in range(h):
        for x in range(w):
            old_val = arr[y, x]
            new_val = 255.0 if old_val >= 128.0 else 0.0
            arr[y, x] = new_val
            err = old_val - new_val

            if x + 1 < w:
                arr[y, x + 1] += err * (7.0 / 16.0)
            if y + 1 < h:
                if x - 1 >= 0:
                    arr[y + 1, x - 1] += err * (3.0 / 16.0)
                arr[y + 1, x] += err * (5.0 / 16.0)
                if x + 1 < w:
                    arr[y + 1, x + 1] += err * (1.0 / 16.0)

    binary_arr = (np.clip(arr, 0, 255) >= 128).astype(np.uint8) * 255
    return Image.fromarray(binary_arr, mode="L")


def apply_atkinson_dithering(img_gray: Image.Image) -> Image.Image:
    """
    Applies Atkinson error diffusion dithering (popularized by MacPaint).
    Retains higher contrast and clean mid-tones.
    Diffusion weight: 1/8 to 6 neighboring pixels.
    """
    arr = np.array(img_gray, dtype=np.float32)
    h, w = arr.shape

    for y in range(h):
        for x in range(w):
            old_val = arr[y, x]
            new_val = 255.0 if old_val >= 128.0 else 0.0
            arr[y, x] = new_val
            err = (old_val - new_val) / 8.0

            if x + 1 < w:
                arr[y, x + 1] += err
            if x + 2 < w:
                arr[y, x + 2] += err
            if y + 1 < h:
                if x - 1 >= 0:
                    arr[y + 1, x - 1] += err
                arr[y + 1, x] += err
                if x + 1 < w:
                    arr[y + 1, x + 1] += err
            if y + 2 < h:
                arr[y + 2, x] += err

    binary_arr = (np.clip(arr, 0, 255) >= 128).astype(np.uint8) * 255
    return Image.fromarray(binary_arr, mode="L")


def generate_archive_id() -> str:
    """Generates an archive ID in ARC-{timestamp}-{random4} format."""
    ts = int(time.time())
    rand_suffix = f"{random.randint(0, 0xFFFF):04X}"
    return f"ARC-{ts}-{rand_suffix}"


def generate_qr_code(payload: str, box_size: int = 5, border: int = 2) -> Image.Image:
    """Generates a clean 1-bit QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("L")
    return qr_img


def create_torn_edge_mask(width: int, height: int, tooth_height: int = 12, tooth_width: int = 16) -> Image.Image:
    """
    Creates an alpha mask with serrated/torn zigzag edges at the top and bottom.
    White = opaque receipt paper, Black (0) = transparent background.
    """
    mask = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(mask)

    # Top edge zigzag cut (transparent above zigzag teeth)
    top_poly = [(0, 0)]
    x = 0
    up = True
    while x <= width:
        y = tooth_height if up else 0
        top_poly.append((x, y))
        x += tooth_width
        up = not up
    top_poly.extend([(width, 0), (0, 0)])
    draw.polygon(top_poly, fill=0)

    # Bottom edge zigzag cut (transparent below zigzag teeth)
    bot_poly = [(0, height)]
    x = 0
    up = True
    while x <= width:
        y = (height - tooth_height) if up else height
        bot_poly.append((x, y))
        x += tooth_width
        up = not up
    bot_poly.extend([(width, height), (0, height)])
    draw.polygon(bot_poly, fill=0)

    return mask


def process_receipt(
    source_image: Union[str, Path, Image.Image],
    paper_width: int = 580,
    dither_method: str = "floyd",
    custom_title: Optional[str] = None,
    custom_text: Optional[Union[str, List[str]]] = None,
    custom_date: Optional[str] = None,
    apply_torn_edges: bool = True,
    contrast_stretch: bool = True
) -> Image.Image:
    """
    Mode A: Receipt Archive Generator.

    Args:
        source_image: Path to image or PIL Image object.
        paper_width: Thermal paper ribbon width in px (580 for 58mm, 800 for 80mm).
        dither_method: 'floyd' (Floyd-Steinberg) or 'atkinson'.
        custom_title: Optional custom header title (defaults to "TIGRAN SOLOMON'S PAPER ARCHIVE").
        custom_text: Optional items text/list to display in the receipt block.
        custom_date: Optional receipt date/time string (default: current local time).
        apply_torn_edges: If True, adds jagged/perforated top and bottom edges.
        contrast_stretch: If True, applies histogram normalization before dithering.

    Returns:
        PIL.Image in 1-bit or RGBA mode ready for export/printing.
    """
    # 1. Load and prepare source image
    input_img = load_and_validate_image(source_image, target_max_size=(1024, 1024), convert_mode="RGB")
    gray_img = input_img.convert("L")

    if contrast_stretch:
        gray_img = adjust_contrast_histogram_stretch(gray_img, low_percentile=2.0, high_percentile=98.0)

    # Determine photo width on the receipt ribbon
    side_margin = 36 if paper_width <= 580 else 54
    target_photo_w = paper_width - (side_margin * 2)

    # Scale photo proportionally to target width
    aspect = gray_img.height / gray_img.width
    target_photo_h = int(target_photo_w * aspect)
    # Don't let the photo become excessively tall
    max_photo_h = int(paper_width * 1.35)
    if target_photo_h > max_photo_h:
        target_photo_h = max_photo_h
        target_photo_w = int(target_photo_h / aspect)
        side_margin = (paper_width - target_photo_w) // 2

    resized_gray = gray_img.resize((target_photo_w, target_photo_h), Image.Resampling.LANCZOS)

    # 2. Dither the image
    if dither_method.lower() == "atkinson":
        dithered_photo = apply_atkinson_dithering(resized_gray)
    else:
        dithered_photo = apply_floyd_steinberg_dithering(resized_gray)

    # 3. Prepare receipt metadata and text content
    archive_id = generate_archive_id()
    if custom_date:
        date_str = str(custom_date).strip()
    else:
        date_str = time.strftime("%Y-%m-%d  %H:%M:%S")

    title = (custom_title or "TIGRAN SOLOMON'S PAPER ARCHIVE").upper()

    # Default atmospheric items if user didn't supply custom text
    default_items = [
        ("01", "SILVER HALIDE GRAIN", "ANALOG"),
        ("01", "THERMAL EMULSION 58MM", "SENSITIZED"),
        ("01", "1-BIT DIFFUSION MATRIX", "FLOYD-ST"),
        ("01", "LATENT IMAGE PRINT", "EXTRACTED"),
        ("01", "CHRONO ARCHIVE ARTIFACT", "ARCHIVED"),
    ]

    items_list = []
    if custom_text:
        if isinstance(custom_text, str):
            lines = [line.strip() for line in custom_text.splitlines() if line.strip()]
        else:
            lines = [str(item).strip() for item in custom_text if str(item).strip()]

        for idx, line in enumerate(lines, 1):
            qty = f"{idx:02d}"
            desc = line[:26].upper()
            items_list.append((qty, desc, "OK"))
    else:
        items_list = default_items

    # 4. Generate QR code
    qr_payload = f"{archive_id} | {title} | {date_str}"
    qr_img = generate_qr_code(qr_payload, box_size=4 if paper_width <= 580 else 6, border=2)

    # 5. Measure layout and heights
    font_title = get_font(DEFAULT_PIXEL_FONT, 32 if paper_width <= 580 else 44)
    font_sub = get_font(DEFAULT_PIXEL_FONT, 20 if paper_width <= 580 else 26)
    font_body = get_font(DEFAULT_PIXEL_FONT, 22 if paper_width <= 580 else 28)
    font_bold = get_font(DEFAULT_PIXEL_FONT, 24 if paper_width <= 580 else 30)
    font_small = get_font(DEFAULT_PIXEL_FONT, 18 if paper_width <= 580 else 22)

    # Estimate receipt vertical layout
    top_padding = 40
    header_h = 130
    photo_box_h = target_photo_h + 30
    items_h = 70 + (len(items_list) * 26) + 70
    qr_section_h = qr_img.height + 70
    footer_h = 80
    bottom_padding = 40

    canvas_h = top_padding + header_h + photo_box_h + items_h + qr_section_h + footer_h + bottom_padding

    # Create white canvas
    receipt = Image.new("L", (paper_width, canvas_h), 255)
    draw = ImageDraw.Draw(receipt)

    cursor_y = top_padding

    # Helper function to draw centered text
    def draw_centered(text: str, y: int, font: ImageFont.ImageFont, fill: int = 0):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x = (paper_width - text_w) // 2
        draw.text((x, y), text, font=font, fill=fill)
        return bbox[3] - bbox[1]

    # Header decorative elements
    divider_line = "- " * ((paper_width - 40) // 16)
    solid_divider = "=" * ((paper_width - 40) // 12)

    cursor_y += 10
    draw_centered("* * * * * * * * * * * * * * * * *", cursor_y, font_small)
    cursor_y += 24

    draw_centered(title, cursor_y, font_title)
    cursor_y += 38

    draw_centered("ANALOG MEMORY RETRIEVAL DIVISION", cursor_y, font_sub)
    cursor_y += 24
    draw_centered(f"TERMINAL #01 // {paper_width}PX THERMAL TAPE", cursor_y, font_small)
    cursor_y += 24

    draw_centered(solid_divider, cursor_y, font_small)
    cursor_y += 22

    # Photo area with border
    photo_x = (paper_width - target_photo_w) // 2
    photo_y = cursor_y + 8

    # Border around photo
    draw.rectangle(
        [photo_x - 4, photo_y - 4, photo_x + target_photo_w + 3, photo_y + target_photo_h + 3],
        outline=0,
        width=2
    )
    receipt.paste(dithered_photo, (photo_x, photo_y))
    cursor_y = photo_y + target_photo_h + 18

    draw_centered(f"[ FIGURE 01: LATENT ARTIFACT CAPTURE ]", cursor_y, font_small)
    cursor_y += 26
    draw_centered(divider_line, cursor_y, font_small)
    cursor_y += 24

    # Receipt table header
    margin_x = side_margin
    content_w = paper_width - (margin_x * 2)

    col_qty_x = margin_x
    col_desc_x = margin_x + 48
    col_val_x = margin_x + content_w - 70

    draw.text((col_qty_x, cursor_y), "QTY", font=font_bold, fill=0)
    draw.text((col_desc_x, cursor_y), "DESCRIPTION", font=font_bold, fill=0)
    draw.text((col_val_x, cursor_y), "STAT", font=font_bold, fill=0)
    cursor_y += 28

    draw.line([(margin_x, cursor_y), (margin_x + content_w, cursor_y)], fill=0, width=1)
    cursor_y += 12

    # Receipt items
    for qty, desc, val in items_list:
        draw.text((col_qty_x, cursor_y), qty, font=font_body, fill=0)
        draw.text((col_desc_x, cursor_y), desc, font=font_body, fill=0)
        draw.text((col_val_x, cursor_y), val, font=font_body, fill=0)
        cursor_y += 26

    cursor_y += 8
    draw.line([(margin_x, cursor_y), (margin_x + content_w, cursor_y)], fill=0, width=1)
    cursor_y += 14

    # Financial / Archival totals
    draw.text((col_desc_x, cursor_y), "ARCHIVE INTEGRITY:", font=font_bold, fill=0)
    draw.text((col_val_x - 10, cursor_y), "100%", font=font_bold, fill=0)
    cursor_y += 26

    draw.text((col_desc_x, cursor_y), "AUTHENTICITY:", font=font_bold, fill=0)
    draw.text((col_val_x - 10, cursor_y), "PASS", font=font_bold, fill=0)
    cursor_y += 28

    draw_centered(solid_divider, cursor_y, font_small)
    cursor_y += 22

    # Metadata block: Archive ID & Timestamp
    draw_centered(f"INDEX NO: {archive_id}", cursor_y, font_bold)
    cursor_y += 26
    draw_centered(f"TIMESTAMP: {date_str}", cursor_y, font_sub)
    cursor_y += 32

    # QR Code insertion
    qr_x = (paper_width - qr_img.width) // 2
    receipt.paste(qr_img, (qr_x, cursor_y))
    cursor_y += qr_img.height + 12

    draw_centered("SCAN TO ACCESS PAPER ARCHIVE", cursor_y, font_small)
    cursor_y += 24

    draw_centered(". . . . . . . . . . . . . . . . .", cursor_y, font_small)
    cursor_y += 20
    draw_centered("KEEP AWAY FROM DIRECT HEAT & SUNLIGHT", cursor_y, font_small)
    cursor_y += 24
    draw_centered("* * * THANK YOU FOR ARCHIVING * * *", cursor_y, font_small)
    cursor_y += 32

    # Crop receipt to actual used height with comfortable margin for bottom teeth
    final_h = cursor_y + 20

    # Apply torn / serrated edge mask if requested
    if apply_torn_edges:
        receipt = receipt.crop((0, 0, paper_width, final_h))
        mask = create_torn_edge_mask(paper_width, final_h, tooth_height=12, tooth_width=16)
        rgba_receipt = Image.new("RGBA", (paper_width, final_h), (255, 255, 255, 0))
        receipt_rgb = receipt.convert("RGBA")
        rgba_receipt.paste(receipt_rgb, (0, 0), mask=mask)
        return rgba_receipt

    receipt = receipt.crop((0, 0, paper_width, final_h))
    return receipt.convert("1")
