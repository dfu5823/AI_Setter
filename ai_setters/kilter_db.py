"""Extract and report on the Kilter app SQLite database."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.patches import PathPatch
from PIL import Image, ImageDraw, ImageFont

from .climb_core import HOLD_TYPES, estimate_foot_sequence, estimate_hand_sequence, sequence_metrics
from .config import load_config, resolve_config_path
from .dataset import ROOT, TEMPLATE_PATH, grade_to_v, hold_to_source_pixel
from .generate_outputs import board_image_svg, board_point, escape, svg_document
from .rendering import render_climb_png, render_labeled_grid_png


OUTPUT_DATA_DIR = ROOT / "outputs" / "data"
OUTPUT_FIGURES_DIR = ROOT / "outputs" / "figures"
OUTPUT_METRICS_DIR = ROOT / "outputs" / "metrics"
ROLE_MAP = {12: "Start", 13: "Any", 14: "Finish", 15: "Feet"}
ROLE_ORDER = {"Start": 0, "Any": 1, "Finish": 2, "Feet": 3}
FRAME_RE = re.compile(r"p(\d+)r(\d+)")
V_ORDER = [f"V{i}" for i in range(15)]


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or resolve_config_path("kilter_db_path")
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def placement_coordinate_map(con: sqlite3.Connection, product_size_id: int = 10, layout_id: int = 1) -> dict[int, dict[str, Any]]:
    rows = con.execute(
        """
        select p.id placement_id, p.hole_id, p.set_id, h.name hole_name, h.x db_x, h.y db_y,
               l.position led_position
        from placements p
        join holes h on h.id = p.hole_id
        join leds l on l.hole_id = h.id and l.product_size_id = ?
        where p.layout_id = ?
        """,
        (product_size_id, layout_id),
    ).fetchall()
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        x = int(row["db_x"])
        y = int(row["db_y"])
        if x % 4 != 0 or y % 4 != 0:
            continue
        repo = (x // 4, y // 4)
        if 1 <= repo[0] <= 35 and 1 <= repo[1] <= 39:
            out[int(row["placement_id"])] = {**dict(row), "x": repo[0], "y": repo[1]}
    return out


def parse_frames(frames: str, placement_map: dict[int, dict[str, Any]]) -> dict[str, list[list[int]]]:
    holds = {hold_type: [] for hold_type in HOLD_TYPES}
    seen: set[tuple[str, int, int]] = set()
    for placement_text, role_text in FRAME_RE.findall(frames or ""):
        placement_id = int(placement_text)
        role_id = int(role_text)
        hold_type = ROLE_MAP.get(role_id)
        placement = placement_map.get(placement_id)
        if not hold_type or not placement:
            continue
        key = (hold_type, int(placement["x"]), int(placement["y"]))
        if key not in seen:
            holds[hold_type].append([key[1], key[2]])
            seen.add(key)
    for hold_type in HOLD_TYPES:
        holds[hold_type].sort(key=lambda p: (p[1], p[0]))
    return holds


def difficulty_map(con: sqlite3.Connection) -> dict[int, str]:
    return {int(row["difficulty"]): str(row["boulder_name"]) for row in con.execute("select * from difficulty_grades")}


def beta_link_map(con: sqlite3.Connection) -> dict[tuple[str, int | None], list[dict[str, Any]]]:
    links: dict[tuple[str, int | None], list[dict[str, Any]]] = defaultdict(list)
    for row in con.execute("select * from beta_links where is_listed = 1"):
        links[(row["climb_uuid"], row["angle"])].append(dict(row))
        links[(row["climb_uuid"], None)].append(dict(row))
    return links


def iter_12x12_original_climbs(con: sqlite3.Connection, include_sequences: bool = False) -> Iterable[dict[str, Any]]:
    config = load_config()
    product_size_id = int(config.get("kilter_product_size_id") or 10)
    layout_id = int(config.get("kilter_layout_id") or 1)
    placements = placement_coordinate_map(con, product_size_id, layout_id)
    grades = difficulty_map(con)
    links = beta_link_map(con)
    query = """
        select c.uuid, c.layout_id, c.setter_id, c.setter_username, c.name, c.description,
               c.hsm, c.edge_left, c.edge_right, c.edge_bottom, c.edge_top, c.angle climb_angle,
               c.frames_count, c.frames_pace, c.frames, c.is_draft, c.is_listed, c.created_at, c.is_nomatch,
               cs.angle, cs.display_difficulty, cs.benchmark_difficulty, cs.ascensionist_count,
               cs.difficulty_average, cs.quality_average, cs.fa_username, cs.fa_at
        from climb_stats cs
        join climbs c on c.uuid = cs.climb_uuid
        where c.layout_id = ?
          and c.is_draft = 0
          and c.is_listed = 1
          and c.edge_left >= 0 and c.edge_right <= 144 and c.edge_bottom >= 0 and c.edge_top <= 156
        order by cs.angle, cs.display_difficulty, cs.ascensionist_count desc, cs.quality_average desc, c.created_at
    """
    for row in con.execute(query, (layout_id,)):
        holds = parse_frames(row["frames"], placements)
        if not any(holds.values()):
            continue
        difficulty = int(round(float(row["display_difficulty"]))) if row["display_difficulty"] is not None else None
        grade = grades.get(difficulty or -1, "")
        v_grade = grade_to_v(grade)
        beta_links = links.get((row["uuid"], row["angle"]), []) or links.get((row["uuid"], None), [])
        record = {
            "uuid": row["uuid"],
            "name": row["name"],
            "description": row["description"],
            "layout_id": row["layout_id"],
            "product_size_id": product_size_id,
            "setter_id": row["setter_id"],
            "setter_username": row["setter_username"],
            "grade": grade,
            "v_grade": v_grade,
            "display_difficulty": row["display_difficulty"],
            "benchmark_difficulty": row["benchmark_difficulty"],
            "angle": row["angle"],
            "ascensionist_count": row["ascensionist_count"],
            "difficulty_average": row["difficulty_average"],
            "quality_average": row["quality_average"],
            "stars": row["quality_average"],
            "first_ascensionist": row["fa_username"],
            "fa_at": row["fa_at"],
            "matching_allowed": not bool(row["is_nomatch"]),
            "is_nomatch": row["is_nomatch"],
            "beta_videos": beta_links,
            "comments": row["description"] or "",
            "created_at": row["created_at"],
            "hsm": row["hsm"],
            "edge_left": row["edge_left"],
            "edge_right": row["edge_right"],
            "edge_bottom": row["edge_bottom"],
            "edge_top": row["edge_top"],
            "frames": row["frames"],
            "holds": holds,
        }
        if include_sequences:
            hand_sequence = estimate_hand_sequence(holds, matching_allowed=record["matching_allowed"], grade=grade)
            foot_sequence = estimate_foot_sequence(holds, hand_sequence)
            record["hand_sequence"] = hand_sequence
            record["foot_sequence"] = foot_sequence
            record["sequence_metrics"] = sequence_metrics(hand_sequence, foot_sequence)
        yield record


def write_csv(records: Iterable[dict[str, Any]], path: Path, ascended_only: bool = False) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "uuid", "name", "description", "layout_id", "product_size_id", "setter_id", "setter_username",
        "grade", "v_grade", "display_difficulty", "benchmark_difficulty", "angle", "ascensionist_count",
        "difficulty_average", "quality_average", "stars", "first_ascensionist", "fa_at", "matching_allowed",
        "is_nomatch", "beta_videos", "comments", "created_at", "hsm", "edge_left", "edge_right", "edge_bottom",
        "edge_top", "holds", "Start", "Any", "Finish", "Feet", "frames",
    ]
    count = 0
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            if ascended_only and (int(record.get("ascensionist_count") or 0) < 10 or float(record.get("quality_average") or 0) < 2):
                continue
            row = dict(record)
            for hold_type in HOLD_TYPES:
                row[hold_type] = json.dumps(record["holds"].get(hold_type, []), separators=(",", ":"))
            row["holds"] = json.dumps(record["holds"], separators=(",", ":"))
            row["beta_videos"] = json.dumps(record.get("beta_videos") or [], separators=(",", ":"))
            writer.writerow(row)
            count += 1
    return count


def database_report(con: sqlite3.Connection, records: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    tables = con.execute("select name, type from sqlite_master where type in ('table','view') order by name").fetchall()
    table_report = []
    for table in tables:
        name = table["name"]
        cols = con.execute(f"pragma table_info({name})").fetchall()
        row_count = con.execute(f"select count(*) from {name}").fetchone()[0]
        populated = {}
        for col in cols:
            colname = col["name"]
            populated[colname] = con.execute(f"select count(*) from {name} where {colname} is not null").fetchone()[0]
        table_report.append({"name": name, "rows": row_count, "columns": [dict(col) for col in cols], "populated": populated})
    angle_grade_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        angle_grade_counts[str(record["angle"])][record["grade"] or "Unknown"] += 1
    report = {
        "database": str(resolve_config_path("kilter_db_path")),
        "target": "Kilter Board Original, 12 x 12 with kickboard, product_size_id=10, layout_id=1",
        "record_count": len(records),
        "tables": table_report,
        "grade_distribution_by_angle": {angle: dict(counter) for angle, counter in sorted(angle_grade_counts.items(), key=lambda item: int(item[0]))},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown_report(report, output_path.with_suffix(".md"))
    return report


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Kilter DB Exploration Report",
        "",
        f"Database: `{report['database']}`",
        f"Target subset: {report['target']}",
        f"Exported climb-angle rows: {report['record_count']}",
        "",
        "## Tables And Populated Fields",
    ]
    for table in report["tables"]:
        lines.append(f"### {table['name']} ({table['rows']} rows)")
        for col in table["columns"]:
            lines.append(f"- `{col['name']}` {col['type']}: populated {table['populated'][col['name']]}/{table['rows']}")
    lines.append("")
    lines.append("## Grade Distribution By Angle")
    for angle, counts in report["grade_distribution_by_angle"].items():
        total = sum(counts.values())
        lines.append(f"- {angle} degrees: {total} rows; {counts}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_grade_violin(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bg = "#f4efe5"
    cmap = mpl.cm.get_cmap("turbo")
    angles = sorted({int(record["angle"]) for record in records if record.get("v_grade") is not None})
    grouped = {angle: [int(record["v_grade"]) for record in records if record.get("angle") == angle and record.get("v_grade") is not None] for angle in angles}
    fig, ax = plt.subplots(figsize=(15, 7), facecolor=bg)
    ax.set_facecolor(bg)
    positions = np.arange(len(angles))
    counts = [len(grouped[angle]) for angle in angles]
    max_count = max(counts) if counts else 1
    data = [grouped[angle] for angle in angles]
    widths = [max(0.14, 0.9 * len(grouped[angle]) / max_count) for angle in angles]
    vp = ax.violinplot(data, positions=positions, widths=widths, showmeans=False, showmedians=True)
    for idx, body in enumerate(vp["bodies"]):
        avg_grade = float(np.mean(data[idx])) if data[idx] else 0
        apply_violin_gradient(ax, body, cmap, avg_grade, 14)
        ax.text(positions[idx], max(data[idx]) + 0.35, str(len(data[idx])), ha="center", va="bottom", fontsize=10, fontweight="bold", color="#17324d")
    vp["cmedians"].set_color("#4b1d14")
    ax.set_xticks(positions)
    ax.set_xticklabels([f"{angle}°" for angle in angles], rotation=15, ha="right")
    ax.set_yticks(range(15))
    ax.set_yticklabels(V_ORDER)
    ax.set_ylim(-0.5, 14.8)
    ax.set_xlim(-0.6, len(angles) - 0.4)
    ax.set_ylabel("V grade", fontweight="bold", fontsize=13)
    ax.set_xlabel("Board angle", fontweight="bold", fontsize=13)
    ax.set_title("Climb Grades Distribution", fontweight="bold", fontsize=20)
    ax.grid(alpha=0.25)
    add_discrete_grade_legend(fig, ax, cmap)
    fig.suptitle("Kilter 12x12 Original Database", x=0.02, ha="left", fontsize=22, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 0.96, 0.94])
    fig.savefig(path, dpi=220, facecolor=bg)
    plt.close(fig)


def apply_violin_gradient(ax: plt.Axes, body, cmap: mpl.colors.Colormap, center_value: float, vmax: float) -> None:
    path = body.get_paths()[0]
    verts = path.vertices
    x0, x1 = verts[:, 0].min(), verts[:, 0].max()
    y0, y1 = verts[:, 1].min(), verts[:, 1].max()
    gradient = np.linspace(max(center_value - 1.5, 0), min(center_value + 1.5, vmax), 256).reshape(256, 1)
    im = ax.imshow(gradient, extent=[x0, x1, y0, y1], origin="lower", aspect="auto", cmap=cmap, alpha=0.8, zorder=body.get_zorder() - 0.2)
    im.set_clip_path(PathPatch(path, transform=ax.transData))
    body.set_facecolor("none")
    body.set_edgecolor("#5c5b63")
    body.set_linewidth(1.2)
    body.set_alpha(1)


def add_discrete_grade_legend(fig: plt.Figure, ax: plt.Axes, cmap: mpl.colors.Colormap) -> None:
    listed = mpl.colors.ListedColormap([cmap(i / 14) for i in range(15)])
    norm = mpl.colors.BoundaryNorm(np.arange(-0.5, 15.5, 1), listed.N)
    sm = ScalarMappable(norm=norm, cmap=listed)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.02, ticks=range(15))
    cbar.ax.set_yticklabels(V_ORDER)
    cbar.set_label("V grade", fontweight="bold")


def render_sample_climbs(records: list[dict[str, Any]], path: Path, limit: int = 4) -> None:
    cells = []
    for index, record in enumerate(records[:limit]):
        x0 = 20 + (index % 2) * 390
        y0 = 42 + (index // 2) * 520
        cells.append(f'<text x="{x0}" y="{y0 - 14}" fill="white" font-size="14" font-weight="700">{escape(record["name"])} {escape(record["grade"])} {record["angle"]}°</text>')
        cells.append(board_image_svg(x0, y0, 340, 419))
        for hold_type, color in (("Start", "#62d852"), ("Any", "#53e6e6"), ("Finish", "#bd45ff"), ("Feet", "#f3a21b")):
            for hx, hy in record["holds"].get(hold_type, []):
                px, py = board_point(hx, hy, x0, y0, 340, 419)
                cells.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="none" stroke="{color}" stroke-width="3"/>')
                cells.append(f'<text x="{px + 8:.1f}" y="{py - 8:.1f}" fill="white" stroke="#111" stroke-width="0.7" font-size="8">{hx},{hy}</text>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg_document(800, 1080, "\n".join(cells)), encoding="utf-8")


def render_sample_climbs_png(records: list[dict[str, Any]], path: Path, limit: int = 4) -> None:
    cells: list[Image.Image] = []
    for record in records[:limit]:
        climb = dict(record)
        climb["hand_sequence"] = estimate_hand_sequence(
            record["holds"],
            matching_allowed=bool(record.get("matching_allowed", True)),
            grade=record.get("grade"),
        )
        temp_path = path.parent / f".tmp_{record['uuid']}.png"
        render_climb_png(climb, temp_path, title=f"{record['name']} {record['grade']} {record['angle']} deg")
        cells.append(Image.open(temp_path).convert("RGB"))
        temp_path.unlink(missing_ok=True)
    width = 2 * 750
    height = 2 * 967
    out = Image.new("RGB", (width, height), (17, 17, 17))
    for index, image in enumerate(cells):
        out.paste(image, ((index % 2) * 750, (index // 2) * 967))
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)


def render_labeled_grid(path: Path) -> None:
    render_labeled_grid_png(path)


def load_db_records(limit: int | None = None, include_sequences: bool = False) -> list[dict[str, Any]]:
    con = connect()
    records = []
    for index, record in enumerate(iter_12x12_original_climbs(con, include_sequences=include_sequences)):
        if limit is not None and index >= limit:
            break
        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Optional cap for faster smoke tests.")
    parser.add_argument("--skip-csv", action="store_true")
    parser.add_argument("--include-sequences", action="store_true")
    args = parser.parse_args()
    con = connect()
    records = load_db_records(args.limit, include_sequences=args.include_sequences)
    OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_METRICS_DIR.mkdir(parents=True, exist_ok=True)
    if not args.skip_csv:
        all_count = write_csv(records, OUTPUT_DATA_DIR / "all_kilter_climbs.csv")
        ascended_count = write_csv(records, OUTPUT_DATA_DIR / "ascended_kilter_climbs.csv", ascended_only=True)
    else:
        all_count = ascended_count = 0
    report = database_report(con, records, OUTPUT_METRICS_DIR / "kilter_db_field_report.json")
    plot_grade_violin(records, OUTPUT_FIGURES_DIR / "kilter_grade_by_angle_violin.png")
    render_sample_climbs(records, OUTPUT_FIGURES_DIR / "db_sample_climbs_4up.svg")
    render_sample_climbs_png(records, OUTPUT_FIGURES_DIR / "db_sample_climbs_4up.png")
    render_labeled_grid(ROOT / "kilter_climbs_output" / "output_template_labeled_grid.png")
    manifest = {
        "records": len(records),
        "all_csv_rows": all_count,
        "ascended_csv_rows": ascended_count,
        "report": str(OUTPUT_METRICS_DIR / "kilter_db_field_report.json"),
        "report_md": str(OUTPUT_METRICS_DIR / "kilter_db_field_report.md"),
        "violin_plot": str(OUTPUT_FIGURES_DIR / "kilter_grade_by_angle_violin.png"),
        "sample_overlay": str(OUTPUT_FIGURES_DIR / "db_sample_climbs_4up.svg"),
        "sample_overlay_png": str(OUTPUT_FIGURES_DIR / "db_sample_climbs_4up.png"),
        "labeled_grid": str(ROOT / "kilter_climbs_output" / "output_template_labeled_grid.png"),
        "grade_distribution_angles": sorted(report["grade_distribution_by_angle"].keys(), key=int),
    }
    (ROOT / "outputs" / "kilter_db_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
