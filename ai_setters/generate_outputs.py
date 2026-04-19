"""Generate climb samples and dataset analytics artifacts."""

from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path
from typing import Any

from PIL import Image

from .climb_core import estimate_hand_sequence
from .dataset import BOARD_CROP, TEMPLATE_PATH, dataset_summary, hold_to_source_pixel, load_dataset, local_heatmap
from .generators import build_move_grade_estimates, generate_climb


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT / "outputs"


def generate_outputs(count: int = 32, output_dir: Path = OUTPUTS_DIR, train_neural: bool = False) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_dir = output_dir / "generated_climbs"
    figures_dir = output_dir / "figures"
    metrics_dir = output_dir / "metrics"
    models_dir = output_dir / "models"
    for directory in (generated_dir, figures_dir, metrics_dir, models_dir):
        directory.mkdir(parents=True, exist_ok=True)

    records = load_dataset()
    setters = ["random", "sequential", "graph", "neural"]
    generated = [
        generate_climb(setters[index % len(setters)], grade="V5", angle="50", seed=index, options={"hand_count": 8, "foot_count": 6})
        for index in range(count)
    ]
    for index, climb in enumerate(generated, start=1):
        (generated_dir / f"generated_{index:03d}.json").write_text(json.dumps(climb, indent=2), encoding="utf-8")

    summary = dataset_summary(records)
    local = local_heatmap(records)
    move_grades = build_move_grade_estimates(records)
    generated_metrics = generated_sequence_summary(generated)
    (metrics_dir / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (metrics_dir / "local_heatmap.json").write_text(json.dumps(local, indent=2), encoding="utf-8")
    (metrics_dir / "move_grade_estimates.json").write_text(json.dumps(move_grades, indent=2), encoding="utf-8")
    (metrics_dir / "generated_sequence_summary.json").write_text(json.dumps(generated_metrics, indent=2), encoding="utf-8")
    (figures_dir / "generated_4up.svg").write_text(render_4up_svg(generated[:4]), encoding="utf-8")
    (figures_dir / "paired_move_graph.svg").write_text(render_move_graph_svg(move_grades, records[:40]), encoding="utf-8")
    (figures_dir / "hold_usage_heatmap.svg").write_text(render_heatmap_svg(summary["hold_usage"]), encoding="utf-8")
    (figures_dir / "interactive_hold_heatmap.html").write_text(render_interactive_heatmap_html(summary, local), encoding="utf-8")

    neural_status = {"status": "not_requested"}
    if train_neural:
        from .generators import NeuralSetter

        neural_status = NeuralSetter(records).train(models_dir / "neural_setter.pt")
        if neural_status.get("grade_metrics"):
            (metrics_dir / "neural_grade_metrics.json").write_text(json.dumps(neural_status["grade_metrics"], indent=2), encoding="utf-8")
            (figures_dir / "neural_grade_bias.svg").write_text(render_grade_bias_svg(neural_status["grade_metrics"]), encoding="utf-8")
    (models_dir / "neural_status.json").write_text(json.dumps(neural_status, indent=2), encoding="utf-8")

    manifest = {
        "count": count,
        "generated_dir": str(generated_dir),
        "figures_dir": str(figures_dir),
        "metrics_dir": str(metrics_dir),
        "model_status": neural_status,
        "generated_sequence_summary": generated_metrics,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def render_4up_svg(climbs: list[dict[str, Any]]) -> str:
    cells = []
    for index, climb in enumerate(climbs):
        x0 = 20 + (index % 2) * 510
        y0 = 54 + (index // 2) * 780
        cells.append(f'<text x="{x0}" y="{y0 - 12}" fill="white" font-size="16">{escape(climb["name"])} {escape(climb["grade"])}</text>')
        cells.append(board_image_svg(x0, y0, 360, 444))
        for hold_type, color in (("Start", "#62d852"), ("Any", "#53e6e6"), ("Finish", "#bd45ff"), ("Feet", "#f3a21b")):
            for hx, hy in climb["holds"].get(hold_type, []):
                px, py = board_point(hx, hy, x0, y0, 360, 444)
                cells.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="8" fill="none" stroke="{color}" stroke-width="3"/>')
        label_offsets: dict[tuple[int, int], int] = {}
        for move in climb.get("hand_sequence") or climb.get("sequence") or []:
            px, py = board_point(move["x"], move["y"], x0, y0, 360, 444)
            key = (int(move["x"]), int(move["y"]))
            offset_index = label_offsets.get(key, 0)
            label_offsets[key] = offset_index + 1
            label = escape(move.get("label") or f'{move.get("move", "")}{"L" if move.get("hand") == "left" else "R"}')
            color = "#ffffff" if move.get("hand") == "left" else "#111111"
            outline = "#111111" if move.get("hand") == "left" else "#ffffff"
            cells.append(f'<text x="{px + 9:.1f}" y="{py - 8 + offset_index * 11:.1f}" fill="{color}" stroke="{outline}" stroke-width="0.8" font-size="9" font-weight="700">{label}</text>')
        metrics = climb.get("sequence_metrics") or {}
        metric_text = f'crosses={metrics.get("crosses", 0)} dynos={metrics.get("dynos", 0)} bumps={metrics.get("bumps", 0)} avg_move={float(metrics.get("average_move_distance", 0)):.2f} avg_interhand={float(metrics.get("average_interhand_distance", 0)):.2f} foot_moves={metrics.get("foot_moves", 0)}'
        cells.append(f'<text x="{x0}" y="{y0 + 454}" fill="#f1f1f1" font-size="10">{escape(metric_text)}</text>')
        explanation = climb.get("selection_explanation") or "\n".join(climb.get("selection_notes") or [])
        for note_index, note in enumerate(wrap_text(explanation, width=72)[:15]):
            weight = "font-weight=\"700\"" if note.startswith(("Model description", "Hold-By-Hold Explanation")) else ""
            cells.append(f'<text x="{x0}" y="{y0 + 465 + 15 * note_index}" fill="#d8d8d8" font-size="10" {weight}>{escape(note)}</text>')
    return svg_document(1020, 1580, "\n".join(cells))


def render_move_graph_svg(move_grades: dict[str, dict[str, float]], records: list[dict[str, Any]]) -> str:
    cells = [board_image_svg(0, 0, 750, 925)]
    rendered = 0
    for record in records:
        sequence = record.get("hand_sequence") or record.get("sequence") or estimate_hand_sequence(
            record.get("holds", {}),
            matching_allowed=bool(record.get("matching_allowed", True)),
            grade=record.get("grade"),
        )
        if sequence and ("left" not in sequence[0] or "right" not in sequence[0]):
            sequence = estimate_hand_sequence(
                record.get("holds", {}),
                matching_allowed=bool(record.get("matching_allowed", True)),
                grade=record.get("grade"),
            )
        for current, nxt in zip(sequence, sequence[1:]):
            if rendered >= 120:
                break
            x1, y1 = board_point(current["x"], current["y"], 0, 0, 750, 925)
            x2, y2 = board_point(nxt["x"], nxt["y"], 0, 0, 750, 925)
            color = "#53e6e6" if nxt.get("hand") == "left" else "#f3a21b"
            opacity = 0.22 + min(0.55, float(record.get("v_grade") or 5) / 20)
            cells.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="2" stroke-opacity="{opacity:.2f}"/>')
            rendered += 1
        if rendered >= 120:
            break
    cells.append('<text x="12" y="24" fill="white" font-size="16" font-weight="700">Paired-node move graph sample: cyan=L hand moves, orange=R hand moves, opacity tracks climb grade sample.</text>')
    cells.append(f'<text x="12" y="48" fill="#d8d8d8" font-size="12">Move grade estimates: {len(move_grades)} exact/close-match weighted edges.</text>')
    return svg_document(750, 925, "\n".join(cells))


def generated_sequence_summary(climbs: list[dict[str, Any]]) -> dict[str, Any]:
    per_climb = []
    totals: dict[str, float] = {}
    for climb in climbs:
        metrics = climb.get("sequence_metrics") or {}
        per_climb.append({"name": climb.get("name"), "setter": climb.get("setter"), "metrics": metrics})
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                totals[key] = totals.get(key, 0.0) + float(value)
    overall = {key: value / len(climbs) if climbs else 0.0 for key, value in totals.items()}
    return {"overall_average": overall, "per_climb": per_climb}


def render_grade_bias_svg(metrics: dict[str, Any]) -> str:
    actual = metrics.get("actual") or []
    predicted = metrics.get("predicted") or []
    cells = ['<text x="20" y="30" fill="white" font-size="16" font-weight="700">Neural grade prediction validation</text>']
    cells.append(f'<text x="20" y="54" fill="#d8d8d8" font-size="12">avg_abs_error={float(metrics.get("average_grade_deviation", 0)):.2f}, bias={float(metrics.get("average_bias", 0)):.2f}, within_2={float(metrics.get("within_2_grade_accuracy", 0)):.2f}</text>')
    cells.append('<line x1="70" y1="520" x2="520" y2="520" stroke="#888"/><line x1="70" y1="520" x2="70" y2="70" stroke="#888"/>')
    cells.append('<line x1="70" y1="520" x2="520" y2="70" stroke="#53e6e6" stroke-dasharray="6 6"/>')
    for truth, pred in zip(actual, predicted):
        x = 70 + (float(truth) / 14) * 450
        y = 520 - (float(pred) / 14) * 450
        cells.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#f3a21b" fill-opacity="0.72"/>')
    return svg_document(600, 560, "\n".join(cells))


def render_heatmap_svg(hold_usage: dict[str, int]) -> str:
    max_count = max(hold_usage.values(), default=1)
    cells = [board_image_svg(0, 0, 750, 925)]
    for key, count in hold_usage.items():
        hx, hy = [int(part) for part in key.split(":")]
        x, y = board_point(hx, hy, 0, 0, 750, 925)
        intensity = count / max_count
        radius = 3 + 13 * intensity
        if count:
            color = f"rgb(255,{round(220 * (1 - intensity))},0)"
            opacity = "0.62"
        else:
            color = "rgb(40,120,255)"
            opacity = "0.28"
        cells.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" fill-opacity="{opacity}"/>')
    return svg_document(750, 925, "\n".join(cells))


def render_interactive_heatmap_html(summary: dict[str, Any], local: dict[str, list[dict[str, Any]]]) -> str:
    centers = {
        key: board_point(int(key.split(":")[0]), int(key.split(":")[1]), 0, 0, 750, 925)
        for key in summary["hold_usage"]
    }
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Hold heatmap</title></head>
<body style="background:#111;color:white;font-family:Arial">
<h1>Interactive hold heatmap</h1>
<canvas id="c" width="750" height="925" style="border:1px solid #555"></canvas>
<pre id="info"></pre>
<script>
const usage = {json.dumps(summary["hold_usage"])};
const local = {json.dumps(local)};
const centers = {json.dumps(centers)};
const board = new Image();
board.src = {json.dumps(board_data_uri())};
const c = document.getElementById('c');
const ctx = c.getContext('2d');
function point(hx, hy) {{ return centers[`${{hx}}:${{hy}}`] || [20.8 * hx + 0.7, 1153.3 - 20.8 * hy - 300]; }}
function draw(active) {{
  ctx.fillStyle = '#050505'; ctx.fillRect(0,0,c.width,c.height);
  if (board.complete) ctx.drawImage(board, 0, 0, 750, 925);
  const max = Math.max(1, ...Object.values(usage));
  for (const [key, count] of Object.entries(usage)) {{
    const [hx, hy] = key.split(':').map(Number); const [x,y] = point(hx,hy);
    ctx.fillStyle = count > 0 ? `rgba(255,${{Math.round(220*(1-count/max))}},0,0.62)` : 'rgba(40,120,255,0.28)';
    ctx.beginPath(); ctx.arc(x,y,3+13*count/max,0,Math.PI*2); ctx.fill();
  }}
  if (active && local[active]) for (const item of local[active]) {{
    const [x,y] = point(item.x,item.y); ctx.strokeStyle = item.type === 'foot' ? '#f3a21b' : '#53e6e6';
    ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x,y,18,0,Math.PI*2); ctx.stroke();
  }}
}}
c.addEventListener('mousemove', (event) => {{
  const rect = c.getBoundingClientRect(); const mx = event.clientX - rect.left; const my = event.clientY - rect.top;
  let best = null, bestD = Infinity;
  for (const key of Object.keys(usage)) {{
    const [hx, hy] = key.split(':').map(Number); const [x,y] = point(hx,hy); const d = Math.hypot(x-mx,y-my);
    if (d < bestD) {{ best = key; bestD = d; }}
  }}
  draw(bestD < 25 ? best : null);
  document.getElementById('info').textContent = bestD < 25 ? `${{best}}\\n${{JSON.stringify(local[best] || [], null, 2)}}` : '';
}});
board.onload = () => draw();
draw();
</script></body></html>"""


def svg_document(width: int, height: int, body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#111"/>{body}</svg>\n'


def board_point(hx: int, hy: int, x0: int, y0: int, width: int, height: int) -> tuple[float, float]:
    source_x, source_y = hold_to_source_pixel(hx, hy)
    return x0 + ((source_x - BOARD_CROP["x"]) / BOARD_CROP["w"]) * width, y0 + ((source_y - BOARD_CROP["y"]) / BOARD_CROP["h"]) * height


def board_image_svg(x0: int, y0: int, width: int, height: int) -> str:
    return (
        f'<image x="{x0}" y="{y0}" width="{width}" height="{height}" preserveAspectRatio="none" '
        f'href="{board_data_uri()}"/>'
    )


def board_data_uri() -> str:
    with Image.open(TEMPLATE_PATH) as image:
        crop = image.crop((
            BOARD_CROP["x"],
            BOARD_CROP["y"],
            BOARD_CROP["x"] + BOARD_CROP["w"],
            BOARD_CROP["y"] + BOARD_CROP["h"],
        ))
        output = io.BytesIO()
        crop.save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def escape(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap_text(text: str, width: int = 80) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).splitlines():
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            if len(current) + 1 + len(word) > width:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}"
        lines.append(current)
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--output-dir", type=Path, default=OUTPUTS_DIR)
    parser.add_argument("--train-neural", action="store_true")
    args = parser.parse_args()
    print(json.dumps(generate_outputs(args.count, args.output_dir, args.train_neural), indent=2))


if __name__ == "__main__":
    main()
