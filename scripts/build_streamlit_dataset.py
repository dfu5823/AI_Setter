#!/usr/bin/env python3
"""Build a compact Kilter climb dataset for Streamlit deployment."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = ROOT / "outputs" / "data" / "all_kilter_climbs.csv"
OUTPUT_JSON = ROOT / "webapp" / "data" / "streamlit_climbs.json"
TOP_PER_ANGLE_GRADE = 10
TOP_PER_ANGLE = 1000
FALLBACK_TOP_PER_ANGLE = 500
MAX_ARTIFACT_BYTES = 95 * 1024 * 1024


def safe_int(value: object, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value))
    except (TypeError, ValueError):
        return default


def ascents(row: dict[str, str]) -> int:
    return safe_int(row.get("ascensionist_count"), 0)


def row_key(row: dict[str, str]) -> str:
    climb_id = row.get("uuid") or row.get("id") or row.get("name") or ""
    return f"{climb_id}:{safe_int(row.get('angle'), -1)}"


def normalize_row(row: dict[str, str]) -> dict[str, Any]:
    try:
        holds = json.loads(row.get("holds") or "{}")
    except json.JSONDecodeError:
        holds = {}
    climb_id = row.get("uuid") or row.get("id") or row.get("name") or ""
    angle = safe_int(row.get("angle"), -1)
    return {
        "id": f"{climb_id}:{angle}",
        "uuid": climb_id,
        "name": row.get("name") or climb_id,
        "grade": row.get("grade") or "Unknown",
        "v_grade": safe_int(row.get("v_grade"), 99),
        "angle": angle,
        "stars": safe_float(row.get("stars") or row.get("quality_average"), 0.0),
        "source": "kilter_db_subset",
        "ascensionist_count": ascents(row),
        "setter_username": row.get("setter_username") or "",
        "matching_allowed": str(row.get("matching_allowed") or "true").lower() in {"1", "true", "yes"},
        "holds": holds,
    }


def build(top_per_angle: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_angle_grade: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    by_angle: dict[int, list[dict[str, str]]] = defaultdict(list)

    with SOURCE_CSV.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            angle = safe_int(row.get("angle"), -1)
            grade = safe_int(row.get("v_grade"), 99)
            by_angle_grade[(angle, grade)].append(row)
            by_angle[angle].append(row)

    selected: dict[str, dict[str, str]] = {}
    for rows in by_angle_grade.values():
        for row in sorted(rows, key=ascents, reverse=True)[:TOP_PER_ANGLE_GRADE]:
            selected[row_key(row)] = row
    for angle, rows in by_angle.items():
        for row in sorted(rows, key=ascents, reverse=True)[:top_per_angle]:
            selected[row_key(row)] = row

    climbs = [normalize_row(row) for row in selected.values()]
    climbs.sort(key=lambda row: (row["angle"], row["v_grade"], -row["ascensionist_count"], row["name"].lower()))
    metadata = {
        "source": str(SOURCE_CSV.relative_to(ROOT)),
        "selection": {
            "top_per_angle_grade": TOP_PER_ANGLE_GRADE,
            "top_per_angle": top_per_angle,
        },
        "count": len(climbs),
    }
    return climbs, metadata


def write_artifact(top_per_angle: int) -> dict[str, Any]:
    climbs, metadata = build(top_per_angle)
    payload = {"metadata": metadata, "climbs": climbs}
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    metadata["bytes"] = OUTPUT_JSON.stat().st_size
    return metadata


def main() -> None:
    if not SOURCE_CSV.exists():
        raise SystemExit(f"Missing source CSV: {SOURCE_CSV}")
    metadata = write_artifact(TOP_PER_ANGLE)
    if metadata["bytes"] > MAX_ARTIFACT_BYTES:
        metadata = write_artifact(FALLBACK_TOP_PER_ANGLE)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
