"""Full preprocessing, PNG artifact generation, and model training pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import os
import pickle
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .climb_core import estimate_foot_sequence, estimate_hand_sequence, sequence_metrics
from .config import load_config
from .dataset import ROOT, dataset_summary, grade_to_v, local_heatmap
from .generators import EmpiricalSequentialSetter, GraphSetter, NeuralSetter, RandomSetter, build_move_grade_estimates
from .kilter_db import (
    OUTPUT_DATA_DIR,
    OUTPUT_FIGURES_DIR,
    OUTPUT_METRICS_DIR,
    connect,
    database_report,
    load_db_records,
    plot_grade_violin,
    render_sample_climbs_png,
    write_csv,
)
from .rendering import HOLD_COLORS, board_crop, board_point, render_climb_png, render_labeled_grid_png


SETTERS = ("random", "sequential", "graph", "neural")
GRADES = tuple(f"V{i}" for i in range(15))


def progress(label: str, step: int, total: int) -> None:
    width = 28
    filled = int(width * step / max(1, total))
    print(f"[{label:<24}] [{'#' * filled}{'.' * (width - filled)}] {step}/{total}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Optional DB row limit. Omit for the full 12x12 export.")
    parser.add_argument("--train-neural", action="store_true")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    args = parser.parse_args()

    config = load_config()
    total_steps = 10
    progress("load db", 1, total_steps)
    records = load_db_records(limit=args.limit, include_sequences=False)
    con = connect()
    for directory in (OUTPUT_DATA_DIR, OUTPUT_FIGURES_DIR, OUTPUT_METRICS_DIR, ROOT / "outputs" / "generated_climbs", ROOT / "outputs" / "models", ROOT / "outputs" / "sequence_review"):
        directory.mkdir(parents=True, exist_ok=True)

    progress("write csv", 2, total_steps)
    all_count = write_csv(records, OUTPUT_DATA_DIR / "all_kilter_climbs.csv")
    ascended_count = write_csv(records, OUTPUT_DATA_DIR / "ascended_kilter_climbs.csv", ascended_only=True)

    progress("db report", 3, total_steps)
    report = database_report(con, records, OUTPUT_METRICS_DIR / "kilter_db_field_report.json")
    plot_table_png("Kilter DB Table Population", table_population_rows(report), OUTPUT_METRICS_DIR / "kilter_db_field_report.png", width=18, height=12)

    progress("grade plots", 4, total_steps)
    plot_grade_violin(records, OUTPUT_FIGURES_DIR / "kilter_grade_by_angle_violin.png")
    plot_grade_angle_counts(records, OUTPUT_METRICS_DIR / "grade_angle_distribution_table.png")
    render_sample_climbs_png(records, OUTPUT_FIGURES_DIR / "db_sample_climbs_4up.png")
    render_labeled_grid_png(ROOT / "kilter_climbs_output" / "output_template_labeled_grid.png")

    progress("analytics", 5, total_steps)
    summary = dataset_summary(records)
    local = local_heatmap(records)
    render_hold_usage_heatmap_png(summary["hold_usage"], OUTPUT_FIGURES_DIR / "hold_usage_heatmap.png")
    plot_metric_summary(summary.get("sequence_metrics", {}), OUTPUT_METRICS_DIR / "dataset_sequence_metrics.png")
    plot_local_heatmap_summary(local, OUTPUT_METRICS_DIR / "local_heatmap_summary.png")

    progress("move graph", 6, total_steps)
    move_grades = build_move_grade_estimates(records)
    render_paired_move_graph_png(records, OUTPUT_FIGURES_DIR / "paired_move_graph.png", max_edges=900)
    plot_move_grade_summary(move_grades, OUTPUT_METRICS_DIR / "move_grade_estimates.png")

    progress("generate climbs", 7, total_steps)
    generated = generate_grade_set(records, ROOT / "outputs" / "generated_climbs")
    plot_generated_summary(generated, OUTPUT_METRICS_DIR / "generated_sequence_summary.png")

    progress("sequence samples", 8, total_steps)
    selected = select_sequence_review_climbs(records)
    write_sequence_review_set(selected, ROOT / "outputs" / "sequence_review" / "heuristic_100")

    neural_status: dict[str, Any] = {"status": "not_requested"}
    if args.train_neural:
        progress("train neural", 9, total_steps)
        neural_kwargs = dict(config.get("neural_training") or {})
        if args.epochs is not None:
            neural_kwargs["epochs"] = args.epochs
        if args.batch_size is not None:
            neural_kwargs["batch_size"] = args.batch_size
        neural_status = NeuralSetter(records, ROOT / "outputs" / "models" / "neural_setter.pt").train(
            ROOT / "outputs" / "models" / "neural_setter.pt",
            **neural_kwargs,
        )
        (ROOT / "outputs" / "models" / "neural_status.json").write_text(json.dumps(neural_status, indent=2), encoding="utf-8")
        if neural_status.get("grade_metrics"):
            plot_neural_grade_metrics(neural_status, OUTPUT_METRICS_DIR / "neural_grade_metrics.png")
            plot_neural_history(neural_status.get("history") or [], OUTPUT_FIGURES_DIR / "neural_training_history.png")
    else:
        (ROOT / "outputs" / "models" / "neural_status.json").write_text(json.dumps(neural_status, indent=2), encoding="utf-8")

    progress("manifest", 10, total_steps)
    manifest = {
        "records": len(records),
        "all_csv_rows": all_count,
        "ascended_csv_rows": ascended_count,
        "generated_png_climbs": len(generated),
        "sequence_review_climbs": len(selected),
        "neural_status": neural_status.get("status"),
        "config": config,
    }
    (ROOT / "outputs" / "preprocess_and_train_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


def generate_grade_set(records: list[dict[str, Any]], output_dir: Path) -> list[dict[str, Any]]:
    for setter in SETTERS:
        (output_dir / setter).mkdir(parents=True, exist_ok=True)
    models = {
        "random": RandomSetter(records),
        "sequential": EmpiricalSequentialSetter(records),
        "graph": GraphSetter(records),
        "neural": NeuralSetter(records, ROOT / "outputs" / "models" / "neural_setter.pt"),
    }
    models_dir = ROOT / "outputs" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    for name, model in models.items():
        if name != "neural":
            with (models_dir / f"{name}_setter.pkl").open("wb") as file:
                pickle.dump(model, file)
    generated = []
    for setter_name, model in models.items():
        for grade_index, grade in enumerate(GRADES):
            climb = model.create(grade=grade, angle="40", seed=1000 + grade_index, options={"hand_count": 8, "foot_count": 6})
            climb["setter"] = setter_name
            generated.append(climb)
            render_climb_png(
                climb,
                output_dir / setter_name / f"{setter_name}_{grade}.png",
                title=f"{setter_name} {grade} 40 deg",
            )
    return generated


def select_sequence_review_climbs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    for grade in range(3, 13):
        candidates = [
            record for record in records
            if record.get("v_grade") == grade and int(record.get("ascensionist_count") or 0) > 0
        ]
        candidates.sort(key=lambda r: (-int(r.get("ascensionist_count") or 0), -float(r.get("quality_average") or 0), str(r.get("created_at") or "")))
        selected.extend(candidates[:10])
    return selected[:100]


def write_sequence_review_set(records: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    labels = []
    hand_only = []
    hand_foot = []
    for index, record in enumerate(records, start=1):
        climb = dict(record)
        hand_sequence = estimate_hand_sequence(
            record["holds"],
            matching_allowed=bool(record.get("matching_allowed", True)),
            grade=record.get("grade"),
        )
        foot_sequence = estimate_foot_sequence(record["holds"], hand_sequence)
        climb["hand_sequence"] = hand_sequence
        climb["foot_sequence"] = foot_sequence
        climb["sequence_metrics"] = sequence_metrics(hand_sequence, foot_sequence)
        hand_entry = {
            "index": index,
            "uuid": record["uuid"],
            "name": record["name"],
            "grade": record["grade"],
            "angle": record["angle"],
            "matching_allowed": record.get("matching_allowed", True),
            "hand_sequence": hand_sequence,
        }
        foot_entry = {**hand_entry, "foot_sequence": foot_sequence}
        labels.append(foot_entry)
        hand_only.append(hand_entry)
        hand_foot.append(foot_entry)
        render_climb_png(climb, output_dir / f"{index:03d}_{record['uuid']}.png", title=f"{index:03d} {record['grade']} {record['name']}")
    (output_dir / "heuristic_sequences.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    (output_dir / "hand_only_sequences.json").write_text(json.dumps(hand_only, indent=2), encoding="utf-8")
    (output_dir / "hand_foot_sequences.json").write_text(json.dumps(hand_foot, indent=2), encoding="utf-8")


def render_hold_usage_heatmap_png(hold_usage: dict[str, int], path: Path) -> None:
    image = board_crop().convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    max_count = max(hold_usage.values(), default=1)
    for key, count in hold_usage.items():
        hx, hy = [int(part) for part in key.split(":")]
        x, y = board_point(hx, hy)
        intensity = count / max_count
        radius = 3 + 16 * intensity
        color = (255, int(220 * (1 - intensity)), 0, 160) if count else (40, 120, 255, 70)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    Image.alpha_composite(image, overlay).convert("RGB").save(path)


def render_paired_move_graph_png(records: list[dict[str, Any]], path: Path, max_edges: int = 900) -> None:
    image = board_crop().convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rendered = 0
    for record in records:
        sequence = record.get("hand_sequence") or estimate_hand_sequence(
            record.get("holds", {}),
            matching_allowed=bool(record.get("matching_allowed", True)),
            grade=record.get("grade"),
        )
        for current, nxt in zip(sequence, sequence[1:]):
            x1, y1 = board_point(current["x"], current["y"])
            x2, y2 = board_point(nxt["x"], nxt["y"])
            color = (83, 230, 230, 115) if nxt.get("hand") == "left" else (243, 162, 27, 115)
            draw.line((x1, y1, x2, y2), fill=color, width=2)
            draw.ellipse((x2 - 4, y2 - 4, x2 + 4, y2 + 4), fill=color)
            rendered += 1
            if rendered >= max_edges:
                break
        if rendered >= max_edges:
            break
    Image.alpha_composite(image, overlay).convert("RGB").save(path)


def plot_metric_summary(metrics: dict[str, Any], path: Path) -> None:
    rows = [(key, round(float(value), 3)) for key, value in metrics.items() if isinstance(value, (int, float))]
    plot_table_png("Dataset Sequence Metrics", rows, path)


def plot_generated_summary(generated: list[dict[str, Any]], path: Path) -> None:
    totals: dict[str, list[float]] = defaultdict(list)
    for climb in generated:
        for key, value in (climb.get("sequence_metrics") or {}).items():
            if isinstance(value, (int, float)):
                totals[key].append(float(value))
    rows = [(key, round(sum(values) / len(values), 3)) for key, values in totals.items() if values]
    plot_table_png("Generated Climb Sequence Metrics", rows, path)


def plot_move_grade_summary(move_grades: dict[str, dict[str, float]], path: Path) -> None:
    means = [value["mean"] for value in move_grades.values()]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(means, bins=np.arange(-0.5, 15.5, 1), color="#53e6e6", edgecolor="#111")
    ax.set_title("Estimated Move Grade Distribution")
    ax.set_xlabel("V grade mean")
    ax.set_ylabel("Move count")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_neural_grade_metrics(status: dict[str, Any], path: Path) -> None:
    metrics = status.get("grade_metrics") or {}
    actual = metrics.get("actual") or []
    predicted = metrics.get("predicted") or []
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].scatter(actual, predicted, s=12, alpha=0.55, color="#f3a21b")
    axes[0].plot([0, 14], [0, 14], color="#53e6e6", linestyle="--")
    axes[0].set_xlabel("Actual V grade")
    axes[0].set_ylabel("Predicted V grade")
    axes[0].set_title("Predicted vs Actual")
    rows = [(key, round(float(value), 4)) for key, value in metrics.items() if isinstance(value, (int, float)) and key not in {"predicted", "actual"}]
    axes[1].axis("off")
    axes[1].table(cellText=rows, colLabels=["metric", "value"], loc="center")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_neural_history(history: list[dict[str, float]], path: Path) -> None:
    if not history:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    epochs = [row["epoch"] for row in history]
    for key in ("loss", "reconstruction_loss", "grade_loss", "val_average_grade_deviation"):
        ax.plot(epochs, [row[key] for row in history], label=key)
    ax.set_xlabel("Epoch")
    ax.set_title("Neural Training History")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_grade_angle_counts(records: list[dict[str, Any]], path: Path) -> None:
    counts: dict[int, Counter[int]] = defaultdict(Counter)
    for record in records:
        if record.get("v_grade") is not None:
            counts[int(record["angle"])][int(record["v_grade"])] += 1
    angles = sorted(counts)
    matrix = np.array([[counts[angle][grade] for angle in angles] for grade in range(15)])
    fig, ax = plt.subplots(figsize=(12, 7))
    im = ax.imshow(matrix, cmap="turbo", aspect="auto")
    ax.set_xticks(range(len(angles)))
    ax.set_xticklabels([str(angle) for angle in angles], rotation=45)
    ax.set_yticks(range(15))
    ax.set_yticklabels([f"V{i}" for i in range(15)])
    ax.set_xlabel("Angle")
    ax.set_ylabel("Grade")
    ax.set_title("Grade Count by Angle")
    fig.colorbar(im, ax=ax, label="Climb-angle rows")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_local_heatmap_summary(local: dict[str, list[dict[str, Any]]], path: Path) -> None:
    rows = sorted(((key, len(values)) for key, values in local.items()), key=lambda item: item[1], reverse=True)[:40]
    plot_table_png("Top Holds with Local Transition/Foothold Data", rows, path, height=10)


def table_population_rows(report: dict[str, Any]) -> list[tuple[str, str]]:
    rows = []
    for table in report.get("tables", []):
        populated = table.get("populated", {})
        nonempty = sum(1 for value in populated.values() if value)
        rows.append((table["name"], f"{table['rows']} rows, {nonempty}/{len(populated)} populated columns"))
    return rows


def plot_table_png(title: str, rows: list[tuple[Any, Any]], path: Path, width: float = 10, height: float = 6) -> None:
    fig, ax = plt.subplots(figsize=(width, height))
    ax.axis("off")
    ax.set_title(title, fontweight="bold", pad=14)
    table = ax.table(cellText=[[str(a), str(b)] for a, b in rows], colLabels=["item", "value"], loc="center", cellLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.2)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
