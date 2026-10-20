"""
Mode B: Polaroid Snap Processor for Tigran Solomon's Paper Archive.
Emulates vintage Polaroid instant film (SX-70 / 600) with color LUT curves,
film grain, radial vignetting, organic light leaks, authentic paper frame,
handwritten archival signature, and 90s Quartz Date Back LCD stamp.
"""

import math
import random
from pathlib import Path
from typing import Union, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from image_loader import load_and_validate_image

ASSETS_DIR = Path(__file__).parent / "assets" / "fonts"
HANDWRITING_FONT = ASSETS_DIR / "Caveat-Regular.ttf"
VT323_FONT = ASSETS_DIR / "VT323-Regular.ttf"


def get_font(font_path: Path, size: int) -> ImageFont.ImageFont:
    """Safely loads a TTF font or falls back to PIL default font."""
    if font_path.exists():
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception:
            pass
    return ImageFont.load_default()


def apply_polaroid_curves(img_rgb: Image.Image) -> Image.Image:
    """
    Applies Polaroid-style tonal curves:
    - Lifted blacks (faded shadows, ~30-38 minimum value)
    - Softened highlight contrast
    - Warm white balance shift (rich amber/cream highlights)
    - Subtle cyan-blue shift in deep shadows (vintage film chemistry)
    """
    arr = np.array(img_rgb, dtype=np.float32)

    # Separate channels (R, G, B)
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]

    # Lift blacks: minimum output is around 30, maximum around 250
    # Red: slightly boosted midtones & highlights (warmth)
    r_curve = 32.0 + (r / 255.0) ** 0.88 * (252.0 - 32.0)

    # Green: gentle vintage curve
    g_curve = 28.0 + (g / 255.0) ** 0.95 * (245.0 - 28.0)

    # Blue: lifted shadows (cyan tint), subdued highlights (yellow/amber whites)
    b_curve = 36.0 + (b / 255.0) ** 1.15 * (228.0 - 36.0)

    # Lower overall contrast slightly (film fade)
    faded = np.stack([r_curve, g_curve, b_curve], axis=-1)
    faded = np.clip(faded, 0, 255).astype(np.uint8)

    # Subtle saturation boost in warm tones
    hsv = cv2.cvtColor(faded, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.08, 0, 255)
    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)

    return Image.fromarray(result)


def apply_film_grain(img: Image.Image, intensity: float = 0.08) -> Image.Image:
    """
    Overlays fine Gaussian film grain on the image.
    """
    arr = np.array(img, dtype=np.float32)
    h, w, c = arr.shape
    noise = np.random.normal(0, 25.0, (h, w, 1))
    noisy = arr + (noise * intensity * 2.5)
    noisy = np.clip(noisy, 0, 255).astype(np.uint8)
    return Image.fromarray(noisy)


def apply_radial_vignette(img: Image.Image, strength: float = 0.40) -> Image.Image:
    """
    Applies smooth radial vignetting (falloff towards corners).
    """
    w, h = img.size
    cx, cy = w / 2.0, h / 2.0
    max_dist = math.sqrt(cx**2 + cy**2)

    # Generate radial coordinate grid
    y_idx, x_idx = np.ogrid[:h, :w]
    dist_map = np.sqrt((x_idx - cx)**2 + (y_idx - cy)**2) / max_dist

    # Vignette profile: sharp center, smooth falloff towards borders
    vignette = 1.0 - np.clip((dist_map - 0.4) / 0.7, 0.0, 1.0) * strength
    vignette = vignette[:, :, np.newaxis]

    arr = np.array(img, dtype=np.float32) * vignette
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def apply_light_leak(img: Image.Image, num_leaks: int = 1) -> Image.Image:
    """
    Adds 1-2 organic vintage light leak gradients on the photo edge.
    Warm orange / yellow / vermilion flares mimicking light entering film cassette.
    """
    w, h = img.size
    arr = np.array(img, dtype=np.float32)

    for _ in range(num_leaks):
        # Choose random edge or corner
        edge = random.choice(["top_right", "top_left", "right", "bottom_left"])
        if edge == "top_right":
            ox, oy = int(w * random.uniform(0.7, 1.0)), int(h * random.uniform(0.0, 0.2))
        elif edge == "top_left":
            ox, oy = int(w * random.uniform(0.0, 0.3)), int(h * random.uniform(0.0, 0.2))
        elif edge == "right":
            ox, oy = int(w * random.uniform(0.85, 1.0)), int(h * random.uniform(0.3, 0.7))
        else:
            ox, oy = int(w * random.uniform(0.0, 0.2)), int(h * random.uniform(0.7, 1.0))

        radius = max(w, h) * random.uniform(0.55, 0.85)

        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - ox)**2 + (y_idx - oy)**2)
        factor = np.clip(1.0 - (dist / radius), 0.0, 1.0)
        # Smooth cosine-like falloff
        factor = (factor ** 1.8) * random.uniform(0.28, 0.48)

        # Light leak color: warm golden-orange to amber
        leak_color = np.array([255.0, 140.0 + random.uniform(-20, 40), 20.0 + random.uniform(0, 30)])

        # Screen blend mode: 255 - ((255 - base) * (255 - blend) / 255)
        leak_layer = factor[:, :, np.newaxis] * leak_color
        arr = 255.0 - ((255.0 - arr) * (255.0 - leak_layer) / 255.0)

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# 7-Segment LED display representation for Quartz Date Back
SEGMENTS_MAP = {
    '0': [1, 1, 1, 1, 1, 1, 0],  # a, b, c, d, e, f, g
    '1': [0, 1, 1, 0, 0, 0, 0],
    '2': [1, 1, 0, 1, 1, 0, 1],
    '3': [1, 1, 1, 1, 0, 0, 1],
    '4': [0, 1, 1, 0, 0, 1, 1],
    '5': [1, 0, 1, 1, 0, 1, 1],
    '6': [1, 0, 1, 1, 1, 1, 1],
    '7': [1, 1, 1, 0, 0, 0, 0],
    '8': [1, 1, 1, 1, 1, 1, 1],
    '9': [1, 1, 1, 1, 0, 1, 1],
    '-': [0, 0, 0, 0, 0, 0, 1],
    ' ': [0, 0, 0, 0, 0, 0, 0],
}


def draw_quartz_lcd_digit(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    char: str,
    seg_len: float,
    seg_thick: float,
    slant: float = 3.5,
    color: Tuple[int, int, int, int] = (255, 140, 15, 240),
    unlit_color: Tuple[int, int, int, int] = (60, 20, 0, 40)
):
    """
    Renders an authentic 7-segment digital quartz display digit
    with realistic slant, segment gaps, and subtle unlit segments.
    """
    if char not in SEGMENTS_MAP:
        return

    segs = SEGMENTS_MAP[char]
    L = seg_len
    T = seg_thick
    G = T * 0.35  # Gap between segments

    # Slant offset function based on vertical coordinate
    def pt(px: float, py: float) -> Tuple[float, float]:
        norm_y = (py - y) / (2 * L)
        return (px + (1.0 - norm_y) * slant, py)

    # Segment coordinates:
    # a: top horizontal
    poly_a = [pt(x + G, y), pt(x + L - G, y), pt(x + L - G - T/2, y + T), pt(x + G + T/2, y + T)]
    # b: top right vertical
    poly_b = [pt(x + L, y + G), pt(x + L, y + L - G), pt(x + L - T, y + L - G - T/2), pt(x + L - T, y + G + T/2)]
    # c: bottom right vertical
    poly_c = [pt(x + L, y + L + G), pt(x + L, y + 2*L - G), pt(x + L - T, y + 2*L - G - T/2), pt(x + L - T, y + L + G + T/2)]
    # d: bottom horizontal
    poly_d = [pt(x + G + T/2, y + 2*L - T), pt(x + L - G - T/2, y + 2*L - T), pt(x + L - G, y + 2*L), pt(x + G, y + 2*L)]
    # e: bottom left vertical
    poly_e = [pt(x, y + L + G), pt(x + T, y + L + G + T/2), pt(x + T, y + 2*L - G - T/2), pt(x, y + 2*L - G)]
    # f: top left vertical
    poly_f = [pt(x, y + G), pt(x + T, y + G + T/2), pt(x + T, y + L - G - T/2), pt(x, y + L - G)]
    # g: middle horizontal
    poly_g = [pt(x + G + T/2, y + L - T/2), pt(x + L - G - T/2, y + L - T/2), pt(x + L - G, y + L), pt(x + L - G - T/2, y + L + T/2), pt(x + G + T/2, y + L + T/2), pt(x + G, y + L)]

    all_polys = [poly_a, poly_b, poly_c, poly_d, poly_e, poly_f, poly_g]

    # Draw unlit segments first for realistic LCD look
    for poly in all_polys:
        draw.polygon(poly, fill=unlit_color)

    # Draw active lit segments
    for is_on, poly in zip(segs, all_polys):
        if is_on:
            draw.polygon(poly, fill=color)


def render_quartz_date_stamp(date_str: str, scale: float = 1.0) -> Image.Image:
    """
    Renders 90s Quartz Date Back timestamp (e.g. "'98 10 24")
    with neon amber glow and soft optical bloom.
    """
    seg_len = 16.0 * scale
    seg_thick = 4.2 * scale
    digit_w = seg_len + (seg_thick * 1.5)
    digit_h = 2 * seg_len + 10
    char_spacing = 6.0 * scale
    word_spacing = 18.0 * scale

    # Calculate total width
    total_w = 0
    for ch in date_str:
        if ch == ' ':
            total_w += word_spacing
        elif ch in ("'", "`"):
            total_w += seg_len * 0.4 + char_spacing
        else:
            total_w += digit_w + char_spacing

    pad = int(24 * scale)
    canvas_w = int(total_w + (pad * 2))
    canvas_h = int(digit_h + (pad * 2))

    # Create sharp layer and glow layer
    sharp_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    glow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    draw_sharp = ImageDraw.Draw(sharp_layer)
    draw_glow = ImageDraw.Draw(glow_layer)

    curr_x = pad
    curr_y = pad

    amber_core = (255, 175, 40, 245)
    amber_glow = (255, 110, 0, 180)

    for ch in date_str:
        if ch == ' ':
            curr_x += word_spacing
        elif ch in ("'", "`"):
            # Render apostrophe
            apost_poly = [
                (curr_x + 2, curr_y + 2),
                (curr_x + seg_thick + 2, curr_y),
                (curr_x + seg_thick, curr_y + seg_thick * 2),
                (curr_x, curr_y + seg_thick * 2.5),
            ]
            draw_sharp.polygon(apost_poly, fill=amber_core)
            draw_glow.polygon(apost_poly, fill=amber_glow)
            curr_x += seg_len * 0.4 + char_spacing
        else:
            draw_quartz_lcd_digit(
                draw_sharp, curr_x, curr_y, ch,
                seg_len, seg_thick, slant=4.5 * scale,
                color=amber_core, unlit_color=(50, 18, 0, 45)
            )
            draw_quartz_lcd_digit(
                draw_glow, curr_x, curr_y, ch,
                seg_len, seg_thick, slant=4.5 * scale,
                color=amber_glow, unlit_color=(0, 0, 0, 0)
            )
            curr_x += digit_w + char_spacing

    # Blur glow layer to create optical luminescence
    blurred_glow = glow_layer.filter(ImageFilter.GaussianBlur(radius=int(4 * scale)))
    final_stamp = Image.alpha_composite(blurred_glow, sharp_layer)
    return final_stamp


def generate_polaroid_date_string(user_date: Optional[str] = None) -> str:
    """
    Returns date string in classic 90s quartz date back format:
    e.g. "'96 10 24". If not provided, generates random date between 1990-1999.
    """
    if user_date:
        clean = str(user_date).strip()
        # If user passed "1998-10-24" or "98-10-24"
        parts = clean.replace("/", "-").replace(".", "-").split("-")
        if len(parts) == 3:
            y, m, d = parts[0], parts[1], parts[2]
            yy = y[-2:]
            return f"'{yy} {int(m):02d} {int(d):02d}"
        return clean

    # Random year between 1990 and 1999
    yr = random.randint(90, 99)
    mo = random.randint(1, 12)
    dy = random.randint(1, 28)
    return f"'{yr} {mo:02d} {dy:02d}"


def create_paper_grain_texture(width: int, height: int, opacity: float = 0.06) -> Image.Image:
    """
    Generates paper texture with fine grain and fibrous noise for Polaroid frame.
    """
    noise = np.random.normal(128, 22, (height, width)).astype(np.uint8)
    texture = Image.fromarray(noise, mode="L").convert("RGBA")

    # Set opacity
    alpha = int(255 * opacity)
    texture.putalpha(alpha)
    return texture


def process_polaroid(
    source_image: Union[str, Path, Image.Image],
    custom_date: Optional[str] = None,
    custom_caption: Optional[str] = None,
    aspect_ratio: str = "1:1",
    enable_light_leak: bool = True,
    enable_vignette: bool = True,
    canvas_width: int = 1000
) -> Image.Image:
    """
    Mode B: Polaroid Snap Processor.

    Args:
        source_image: Input image path or PIL Image.
        custom_date: Optional custom date string for the 90s LCD display.
        custom_caption: Optional handwritten caption on bottom frame
                        (defaults to "Tigran Solomon's Paper Archive").
        aspect_ratio: '1:1' (classic square) or '4:5'.
        enable_light_leak: Whether to add 1-2 random warm light leaks.
        enable_vignette: Whether to add radial vignetting.
        canvas_width: Width of the output Polaroid frame in px (default 1000).

    Returns:
        PIL.Image (RGB) with the styled Polaroid photograph.
    """
    # 1. Load and prepare source image
    input_img = load_and_validate_image(source_image, target_max_size=(1400, 1400), convert_mode="RGB")

    # 2. Setup Polaroid frame dimensions
    # Classic Polaroid SX-70 / 600 proportions:
    # Outer frame: ~ 1 : 1.22 ratio
    # Left/Right/Top margins: ~ 6.5% of total width
    # Bottom margin: ~ 25-30% of total frame height
    side_margin = int(canvas_width * 0.065)
    top_margin = int(canvas_width * 0.065)
    photo_w = canvas_width - (side_margin * 2)

    if aspect_ratio == "4:5":
        photo_h = int(photo_w * (5.0 / 4.0))
        bottom_margin = int(canvas_width * 0.28)
    else:  # 1:1 square
        photo_h = photo_w
        # Bottom margin ~ 28% of total height
        bottom_margin = int(photo_h * 0.36)

    total_height = top_margin + photo_h + bottom_margin

    # 3. Crop and resize photo to fit cutout (center crop)
    img_aspect = input_img.width / input_img.height
    cutout_aspect = photo_w / photo_h

    if img_aspect > cutout_aspect:
        # Source is wider, crop horizontal sides
        new_w = int(input_img.height * cutout_aspect)
        offset = (input_img.width - new_w) // 2
        cropped_img = input_img.crop((offset, 0, offset + new_w, input_img.height))
    else:
        # Source is taller, crop top/bottom
        new_h = int(input_img.width / cutout_aspect)
        offset = (input_img.height - new_h) // 2
        cropped_img = input_img.crop((0, offset, input_img.width, offset + new_h))

    resized_photo = cropped_img.resize((photo_w, photo_h), Image.Resampling.LANCZOS)

    # 4. Color grading and analog effects
    styled_photo = apply_polaroid_curves(resized_photo)

    if enable_vignette:
        styled_photo = apply_radial_vignette(styled_photo, strength=0.38)

    styled_photo = apply_film_grain(styled_photo, intensity=0.07)

    if enable_light_leak:
        num_leaks = random.choice([1, 2])
        styled_photo = apply_light_leak(styled_photo, num_leaks=num_leaks)

    # 5. Overlay 90s Quartz Date Back LCD stamp
    date_text = generate_polaroid_date_string(custom_date)
    date_stamp = render_quartz_date_stamp(date_text, scale=canvas_width / 1000.0)

    # Stamp position: bottom right inside photo
    stamp_x = photo_w - date_stamp.width - int(18 * (canvas_width / 1000.0))
    stamp_y = photo_h - date_stamp.height - int(14 * (canvas_width / 1000.0))

    styled_photo_rgba = styled_photo.convert("RGBA")
    styled_photo_rgba.alpha_composite(date_stamp, (stamp_x, stamp_y))

    # 6. Build the authentic paper frame
    # Vintage polaroid paper off-white color: #FAF7F2
    frame_color = (250, 247, 242)
    polaroid_frame = Image.new("RGB", (canvas_width, total_height), frame_color)

    # Draw subtle inner bevel / shadow around the photo cutout
    photo_x = side_margin
    photo_y = top_margin

    # Paste styled photo onto frame
    polaroid_frame.paste(styled_photo_rgba.convert("RGB"), (photo_x, photo_y))

    # Inner shadow line around photo cutout (simulating emulsion mounting recess)
    frame_draw = ImageDraw.Draw(polaroid_frame)
    frame_draw.rectangle(
        [photo_x - 1, photo_y - 1, photo_x + photo_w, photo_y + photo_h],
        outline=(210, 205, 198),
        width=1
    )
    frame_draw.line(
        [(photo_x, photo_y), (photo_x + photo_w, photo_y)],
        fill=(180, 175, 168),
        width=1
    )
    frame_draw.line(
        [(photo_x, photo_y), (photo_x, photo_y + photo_h)],
        fill=(190, 185, 178),
        width=1
    )

    # 7. Apply paper grain texture overlay to the frame
    paper_grain = create_paper_grain_texture(canvas_width, total_height, opacity=0.07)
    polaroid_frame_rgba = polaroid_frame.convert("RGBA")
    polaroid_frame = Image.alpha_composite(polaroid_frame_rgba, paper_grain).convert("RGB")
    frame_draw = ImageDraw.Draw(polaroid_frame)

    # 8. Handwritten / Brand signature on bottom margin
    caption = (custom_caption or "Tigran Solomon's Paper Archive").strip()
    font_size = int(48 * (canvas_width / 1000.0))
    hand_font = get_font(HANDWRITING_FONT, font_size)

    # Ink color: soft black/charcoal like ballpoint pen or archival ink
    ink_color = (42, 40, 38)

    bbox = frame_draw.textbbox((0, 0), caption, font=hand_font)
    caption_w = bbox[2] - bbox[0]
    caption_h = bbox[3] - bbox[1]

    # Center horizontally on bottom margin
    caption_x = (canvas_width - caption_w) // 2
    caption_y = photo_y + photo_h + (bottom_margin - caption_h) // 2 - int(6 * (canvas_width / 1000.0))

    frame_draw.text((caption_x, caption_y), caption, font=hand_font, fill=ink_color)

    return polaroid_frame
