"""Dataset extraction and small analytics utilities for Kilter screenshots."""

from __future__ import annotations

import json
import re
import struct
import zlib
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from .climb_core import GRID_COLUMNS, GRID_ROWS, HOLD_TYPES, estimate_foot_sequence, estimate_hand_sequence, estimate_sequence, foot_candidates_for_hands, normalize_holds, sequence_metrics
from .config import load_config, resolve_config_path


ROOT = Path(__file__).resolve().parents[1]
KILTER_DATA_DIR = ROOT / "kilter_climbs_data"
SCREENSHOTS_DATA_DIR = ROOT / "kilter_climbs_data" / "app_screenshots_dataset"
TEMPLATE_PATH = ROOT / "kilter_climbs_output" / "output_template.png"
METADATA_PATH = ROOT / "webapp" / "data" / "source_climbs_metadata.json"
DATASET_CACHE_PATH = ROOT / "webapp" / "data" / "climbs_dataset.json"

BOARD_CROP = {"x": 0, "y": 300, "w": 750, "h": 925}
BOARD_SIZE_FEET = {"width": 12.0, "height": 12.0}
HOLD_SPACING_INCHES = {
    "x": (BOARD_SIZE_FEET["width"] * 12.0) / (GRID_COLUMNS - 1),
    "y": (BOARD_SIZE_FEET["height"] * 12.0) / (GRID_ROWS - 1),
}


def grade_to_v(grade: str | None) -> int | None:
    match = re.search(r"V(\d+)", grade or "", flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def load_metadata() -> dict[str, dict[str, Any]]:
    if not METADATA_PATH.exists():
        return {}
    with METADATA_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def build_dataset(refresh: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
    config = load_config()
    if config.get("data_source") == "kilter_db":
        from .kilter_db import load_db_records

        db_limit = limit if limit is not None else config.get("model_training_limit")
        return load_db_records(limit=int(db_limit) if db_limit else None, include_sequences=False)

    if DATASET_CACHE_PATH.exists() and not refresh:
        with DATASET_CACHE_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, list):
            for record in data:
                image_path = str(record.get("image_path") or "")
                if image_path.startswith("kilter_climbs_data/IMG_"):
                    record["image_path"] = image_path.replace("kilter_climbs_data/", "kilter_climbs_data/app_screenshots_dataset/", 1)
            return data
        return []

    metadata = load_metadata()
    records: list[dict[str, Any]] = []
    screenshots_dir = resolve_config_path("screenshots_dir")
    if not screenshots_dir.exists():
        screenshots_dir = KILTER_DATA_DIR
    for image_path in sorted(screenshots_dir.glob("*.png"))[:limit]:
        meta = metadata.get(image_path.name, {})
        holds = extract_holds_from_png(image_path)
        grade = meta.get("grade") or "Unknown"
        angle = str(meta.get("angle") or "50")
        record = {
            "id": image_path.stem,
            "name": meta.get("name") or image_path.stem.replace("_", " "),
            "grade": grade,
            "v_grade": grade_to_v(grade),
            "angle": angle,
            "stars": meta.get("stars", "Unknown"),
            "source": "kilter",
            "image_path": str(image_path.relative_to(ROOT)),
            "holds": holds,
        }
        hand_sequence = estimate_hand_sequence(holds, matching_allowed=bool(record.get("matching_allowed", True)), grade=grade)
        foot_sequence = estimate_foot_sequence(holds, hand_sequence)
        record["sequence"] = hand_sequence
        record["hand_sequence"] = hand_sequence
        record["foot_sequence"] = foot_sequence
        record["sequence_metrics"] = sequence_metrics(hand_sequence, foot_sequence)
        records.append(record)

    if limit is None:
        DATASET_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DATASET_CACHE_PATH.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2)
    return records


def load_dataset() -> list[dict[str, Any]]:
    return build_dataset(refresh=False)


def valid_hold_positions() -> set[tuple[int, int]]:
    if TEMPLATE_PATH.exists():
        return set(physical_hold_centers().keys())
    return {(x, y) for x in range(1, GRID_COLUMNS + 1) for y in range(1, GRID_ROWS + 1)}


@lru_cache(maxsize=1)
def physical_hold_centers() -> dict[tuple[int, int], tuple[float, float]]:
    if not TEMPLATE_PATH.exists():
        return {}
    return extract_physical_hold_centers_from_png(TEMPLATE_PATH)


@lru_cache(maxsize=1)
def physical_hold_metrics() -> dict[tuple[int, int], dict[str, float]]:
    if not TEMPLATE_PATH.exists():
        return {}
    return extract_physical_hold_metrics_from_png(TEMPLATE_PATH)


def hold_size_bins() -> dict[tuple[int, int], str]:
    metrics = physical_hold_metrics()
    if not metrics:
        return {hold: "medium" for hold in valid_hold_positions()}
    areas = sorted(metric["area"] for metric in metrics.values())
    small_cut = areas[len(areas) // 3]
    large_cut = areas[(2 * len(areas)) // 3]
    bins: dict[tuple[int, int], str] = {}
    for hold, metric in metrics.items():
        area = metric["area"]
        if area <= small_cut:
            bins[hold] = "small"
        elif area >= large_cut:
            bins[hold] = "large"
        else:
            bins[hold] = "medium"
    return bins


def extract_holds_from_png(path: Path) -> dict[str, list[list[int]]]:
    width, height, pixels = read_png_rgba8(path)
    labels = bytearray(width * height)
    type_index = {"Start": 1, "Any": 2, "Finish": 3, "Feet": 4}
    index_type = ["", "Start", "Any", "Finish", "Feet"]
    for y in range(290, min(1220, height)):
        for x in range(width):
            r, g, b, _a = pixels[y * width + x]
            hold_type = classify_hold_pixel(r, g, b)
            if hold_type:
                labels[y * width + x] = type_index[hold_type]

    holds = {hold_type: [] for hold_type in HOLD_TYPES}
    visited = bytearray(width * height)
    seen: set[tuple[str, int, int]] = set()
    for y in range(290, min(1220, height)):
        for x in range(width):
            index = y * width + x
            label = labels[index]
            if not label or visited[index]:
                continue
            component = flood_component(index, labels, visited, width, label)
            if component["count"] < 24 or component["width"] > 70 or component["height"] > 70:
                continue
            cx = component["sum_x"] / component["count"]
            cy = component["sum_y"] / component["count"]
            hx, hy = source_pixel_to_hold(cx, cy)
            hold_type = index_type[label]
            key = (hold_type, hx, hy)
            if 1 <= hx <= GRID_COLUMNS and 1 <= hy <= GRID_ROWS and key not in seen:
                holds[hold_type].append([hx, hy])
                seen.add(key)
    return holds


def extract_physical_holds_from_png(path: Path) -> set[tuple[int, int]]:
    return set(extract_physical_hold_centers_from_png(path).keys())


def extract_physical_hold_centers_from_png(path: Path) -> dict[tuple[int, int], tuple[float, float]]:
    return {hold: (metric["x"], metric["y"]) for hold, metric in extract_physical_hold_metrics_from_png(path).items()}


def extract_physical_hold_metrics_from_png(path: Path) -> dict[tuple[int, int], dict[str, float]]:
    width, height, pixels = read_png_rgba8(path)
    labels = bytearray(width * height)
    for y in range(300, min(1160, height)):
        for x in range(width):
            r, g, b, _a = pixels[y * width + x]
            if is_physical_hold_pixel(r, g, b):
                labels[y * width + x] = 1
    visited = bytearray(width * height)
    holds: dict[tuple[int, int], dict[str, float]] = {}
    for y in range(300, min(1160, height)):
        for x in range(width):
            index = y * width + x
            if not labels[index] or visited[index]:
                continue
            component = flood_component(index, labels, visited, width, 1)
            if component["count"] < 30 or component["width"] > 90 or component["height"] > 80:
                continue
            cx = component["sum_x"] / component["count"]
            cy = component["sum_y"] / component["count"]
            hx, hy = raw_source_pixel_to_hold(cx, cy)
            if 1 <= hx <= GRID_COLUMNS and 1 <= hy <= GRID_ROWS:
                holds[(hx, hy)] = {"x": cx, "y": cy, "area": float(component["count"]), "width": float(component["width"]), "height": float(component["height"])}
    return holds


def dataset_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    hold_usage: Counter[tuple[int, int]] = Counter()
    type_usage: dict[str, Counter[tuple[int, int]]] = {hold_type: Counter() for hold_type in HOLD_TYPES}
    transitions: Counter[tuple[tuple[int, int], tuple[int, int]]] = Counter()
    grades: Counter[str] = Counter()
    for record in records:
        grades[record.get("grade") or "Unknown"] += 1
        holds = normalize_holds(record.get("holds", {}))
        for hold_type, points in holds.items():
            for x, y in points:
                hold_usage[(x, y)] += 1
                type_usage[hold_type][(x, y)] += 1
        sequence = normalized_hand_sequence(record, holds)
        for current, nxt in zip(sequence, sequence[1:]):
            transitions[((current["x"], current["y"]), (nxt["x"], nxt["y"]))] += 1
    metrics = [
        record.get("sequence_metrics") or sequence_metrics(normalized_hand_sequence(record), record.get("foot_sequence"))
        for record in records
    ]
    metric_totals: dict[str, float] = {}
    for key in ("crosses", "dynos", "bumps", "average_move_distance", "average_interhand_distance", "max_interhand_distance", "foot_moves"):
        metric_totals[key] = sum(float(metric.get(key, 0)) for metric in metrics)
    aggregate_metrics = {
        key: value / len(metrics) if metrics else 0.0
        for key, value in metric_totals.items()
    }
    valid_holds = sorted(valid_hold_positions())
    return {
        "num_climbs": len(records),
        "grades": dict(grades),
        "hold_usage": {f"{x}:{y}": hold_usage[(x, y)] for (x, y) in valid_holds},
        "type_usage": {
            hold_type: {f"{x}:{y}": count for (x, y), count in counter.items()} for hold_type, counter in type_usage.items()
        },
        "transitions": {f"{a[0]}:{a[1]}->{b[0]}:{b[1]}": count for (a, b), count in transitions.items()},
        "hold_spacing_inches": HOLD_SPACING_INCHES,
        "sequence_metrics": aggregate_metrics,
        "hold_size_bins": {f"{x}:{y}": bin_name for (x, y), bin_name in hold_size_bins().items()},
    }


def local_heatmap(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    hand_next: dict[tuple[int, int], Counter[tuple[int, int]]] = defaultdict(Counter)
    foot_near: dict[tuple[int, int], Counter[tuple[int, int]]] = defaultdict(Counter)
    for record in records:
        holds = normalize_holds(record.get("holds", {}))
        sequence = normalized_hand_sequence(record, holds)
        for current, nxt in zip(sequence, sequence[1:]):
            hand_next[(current["x"], current["y"])][(nxt["x"], nxt["y"])] += 1
        for move in sequence:
            left = tuple(move["left"])
            right = tuple(move["right"])
            for hand in (left, right):
                for item in foot_candidates_for_hands(holds, left, right):
                    fx, fy = item["hold"]
                    foot_near[hand][(fx, fy)] += max(1, int(100 - item["penalty"]))
    output: dict[str, list[dict[str, Any]]] = {}
    for hold, counter in hand_next.items():
        output[f"{hold[0]}:{hold[1]}"] = [
            {"x": x, "y": y, "count": count, "type": "hand"} for (x, y), count in counter.most_common(8)
        ]
    for hold, counter in foot_near.items():
        output.setdefault(f"{hold[0]}:{hold[1]}", []).extend(
            {"x": x, "y": y, "count": count, "type": "foot"} for (x, y), count in counter.most_common(8)
        )
    return output


def normalized_hand_sequence(record: dict[str, Any], holds: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    sequence = record.get("hand_sequence") or record.get("sequence")
    if sequence and "left" in sequence[0] and "right" in sequence[0]:
        return sequence
    return estimate_hand_sequence(
        holds if holds is not None else record.get("holds", {}),
        matching_allowed=bool(record.get("matching_allowed", True)),
        grade=record.get("grade"),
    )


def classify_hold_pixel(r: int, g: int, b: int) -> str | None:
    if g > 190 and r < 150 and b < 150:
        return "Start"
    if b > 145 and g > 185 and r < 150:
        return "Any"
    if r > 170 and b > 145 and g < 150:
        return "Finish"
    if r > 170 and g > 130 and b < 130:
        return "Feet"
    return None


def is_physical_hold_pixel(r: int, g: int, b: int) -> bool:
    high = max(r, g, b)
    low = min(r, g, b)
    return 65 < high < 210 and high - low < 55


def source_pixel_to_hold(x: float, y: float) -> tuple[int, int]:
    centers = physical_hold_centers()
    if centers:
        hold, distance = nearest_physical_hold(x, y, centers)
        if distance <= 28:
            return hold
    return raw_source_pixel_to_hold(x, y)


def raw_source_pixel_to_hold(x: float, y: float) -> tuple[int, int]:
    return round((x - 0.7) / 20.8), round((1153.3 - y) / 20.8)


def hold_to_source_pixel(x: int, y: int) -> tuple[float, float]:
    center = physical_hold_centers().get((x, y))
    if center:
        return center
    return 20.8 * x + 0.7, 1153.3 - 20.8 * y


def nearest_physical_hold(
    x: float,
    y: float,
    centers: dict[tuple[int, int], tuple[float, float]],
) -> tuple[tuple[int, int], float]:
    hold, center = min(centers.items(), key=lambda item: (item[1][0] - x) ** 2 + (item[1][1] - y) ** 2)
    return hold, ((center[0] - x) ** 2 + (center[1] - y) ** 2) ** 0.5


def flood_component(start: int, labels: bytearray, visited: bytearray, width: int, label: int) -> dict[str, int]:
    stack = [start]
    visited[start] = 1
    min_x = max_x = start % width
    min_y = max_y = start // width
    count = 0
    sum_x = 0
    sum_y = 0
    while stack:
        current = stack.pop()
        x = current % width
        y = current // width
        count += 1
        sum_x += x
        sum_y += y
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        for neighbor in (current - 1, current + 1, current - width, current + width):
            if 0 <= neighbor < len(labels) and not visited[neighbor] and labels[neighbor] == label:
                visited[neighbor] = 1
                stack.append(neighbor)
    return {
        "count": count,
        "sum_x": sum_x,
        "sum_y": sum_y,
        "width": max_x - min_x + 1,
        "height": max_y - min_y + 1,
    }


def read_png_rgba8(path: Path) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    offset = 8
    width = height = bit_depth = color_type = None
    idat = bytearray()
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(">IIBBBBB", chunk)
            if interlace:
                raise ValueError("Interlaced PNGs are not supported")
        elif chunk_type == b"IDAT":
            idat.extend(chunk)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None or bit_depth is None or color_type != 6:
        raise ValueError("Only non-interlaced RGBA PNGs are supported")
    channels = 4
    bytes_per_sample = 2 if bit_depth == 16 else 1
    bytes_per_pixel = channels * bytes_per_sample
    stride = width * bytes_per_pixel
    raw = zlib.decompress(bytes(idat))
    rows: list[bytearray] = []
    pos = 0
    previous = bytearray(stride)
    for _row in range(height):
        filter_type = raw[pos]
        pos += 1
        current = bytearray(raw[pos : pos + stride])
        pos += stride
        unfilter(current, previous, bytes_per_pixel, filter_type)
        rows.append(current)
        previous = current
    pixels: list[tuple[int, int, int, int]] = []
    for row in rows:
        if bit_depth == 16:
            for i in range(0, len(row), 8):
                pixels.append((row[i], row[i + 2], row[i + 4], row[i + 6]))
        else:
            for i in range(0, len(row), 4):
                pixels.append((row[i], row[i + 1], row[i + 2], row[i + 3]))
    return width, height, pixels


def unfilter(row: bytearray, previous: bytearray, bpp: int, filter_type: int) -> None:
    for i in range(len(row)):
        left = row[i - bpp] if i >= bpp else 0
        up = previous[i]
        up_left = previous[i - bpp] if i >= bpp else 0
        if filter_type == 1:
            row[i] = (row[i] + left) & 0xFF
        elif filter_type == 2:
            row[i] = (row[i] + up) & 0xFF
        elif filter_type == 3:
            row[i] = (row[i] + ((left + up) // 2)) & 0xFF
        elif filter_type == 4:
            row[i] = (row[i] + paeth(left, up, up_left)) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"Unsupported PNG filter {filter_type}")


def paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c
