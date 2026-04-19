"""PNG rendering helpers for coordinate-backed Kilter climbs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .dataset import BOARD_CROP, TEMPLATE_PATH, hold_to_source_pixel


HOLD_COLORS = {
    "Start": (98, 216, 82),
    "Any": (83, 230, 230),
    "Finish": (189, 69, 255),
    "Feet": (243, 162, 27),
}


def board_crop(size: tuple[int, int] = (750, 925)) -> Image.Image:
    with Image.open(TEMPLATE_PATH).convert("RGB") as image:
        crop = image.crop((
            BOARD_CROP["x"],
            BOARD_CROP["y"],
            BOARD_CROP["x"] + BOARD_CROP["w"],
            BOARD_CROP["y"] + BOARD_CROP["h"],
        ))
    return crop.resize(size, Image.Resampling.LANCZOS)


def board_point(hx: int, hy: int, size: tuple[int, int] = (750, 925), offset: tuple[int, int] = (0, 0)) -> tuple[float, float]:
    source_x, source_y = hold_to_source_pixel(hx, hy)
    return (
        offset[0] + ((source_x - BOARD_CROP["x"]) / BOARD_CROP["w"]) * size[0],
        offset[1] + ((source_y - BOARD_CROP["y"]) / BOARD_CROP["h"]) * size[1],
    )


def render_climb_png(
    climb: dict[str, Any],
    path: Path,
    title: str | None = None,
    annotate_sequence: bool = True,
    size: tuple[int, int] = (750, 925),
) -> None:
    margin_top = 42 if title else 0
    image = Image.new("RGB", (size[0], size[1] + margin_top), (17, 17, 17))
    image.paste(board_crop(size), (0, margin_top))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    if title:
        draw.text((10, 12), title, fill=(255, 255, 255), font=font)
    matching_allowed = climb.get("matching_allowed", True)
    badge = "MATCH OK" if matching_allowed else "NO MATCH"
    badge_fill = (82, 216, 82) if matching_allowed else (255, 96, 96)
    badge_y = 12 if title else 10
    draw.text((size[0] - 92, badge_y), badge, fill=badge_fill, font=font, stroke_width=1, stroke_fill=(0, 0, 0))
    for hold_type, color in HOLD_COLORS.items():
        for hx, hy in climb.get("holds", {}).get(hold_type, []):
            x, y = board_point(int(hx), int(hy), size, (0, margin_top))
            draw.ellipse((x - 14, y - 14, x + 14, y + 14), outline=color, width=4)
    if annotate_sequence:
        label_offsets: dict[tuple[int, int], int] = {}
        for move in climb.get("hand_sequence") or climb.get("sequence") or []:
            x, y = board_point(int(move["x"]), int(move["y"]), size, (0, margin_top))
            key = (int(move["x"]), int(move["y"]))
            offset_index = label_offsets.get(key, 0)
            label_offsets[key] = offset_index + 1
            label = move.get("label") or f"{move.get('move', '')}{'L' if move.get('hand') == 'left' else 'R'}"
            fill = (255, 255, 255) if move.get("hand") == "left" else (20, 20, 20)
            stroke = (20, 20, 20) if move.get("hand") == "left" else (255, 255, 255)
            draw.text((x + 16, y - 18 + offset_index * 12), str(label), fill=fill, font=font, stroke_width=1, stroke_fill=stroke)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def render_labeled_grid_png(path: Path) -> None:
    with Image.open(TEMPLATE_PATH).convert("RGB") as image:
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        crop_left = BOARD_CROP["x"]
        crop_bottom = BOARD_CROP["y"] + BOARD_CROP["h"]
        crop_top = BOARD_CROP["y"]
        crop_right = BOARD_CROP["x"] + BOARD_CROP["w"]
        for x in range(1, 36):
            px, _ = hold_to_source_pixel(x, 1)
            draw.line((px, crop_top, px, crop_bottom), fill=(35, 160, 160), width=1)
            label = str(x)
            bbox = draw.textbbox((0, 0), label, font=font)
            draw.text((px - (bbox[2] - bbox[0]) / 2, crop_bottom + 8), label, fill=(255, 255, 255), font=font, stroke_width=1, stroke_fill=(0, 0, 0))
        for y in range(1, 40):
            _, py = hold_to_source_pixel(1, y)
            draw.line((crop_left, py, crop_right, py), fill=(35, 160, 160), width=1)
            label = str(y)
            bbox = draw.textbbox((0, 0), label, font=font)
            draw.text((max(2, crop_left - (bbox[2] - bbox[0]) - 8), py - (bbox[3] - bbox[1]) / 2), label, fill=(255, 255, 255), font=font, stroke_width=1, stroke_fill=(0, 0, 0))
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
