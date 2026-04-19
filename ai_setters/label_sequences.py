"""Interactive hand-sequence labeling tool for 100 high-ascent Kilter climbs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from .climb_core import estimate_hand_sequence
from .dataset import ROOT
from .kilter_db import load_db_records
from .preprocess_and_train import select_sequence_review_climbs, write_sequence_review_set
from .rendering import HOLD_COLORS, board_crop, board_point, render_climb_png


OUTPUT_DIR = ROOT / "outputs" / "sequence_review"
PROGRESS_PATH = OUTPUT_DIR / "manual_sequences.json"


class SequenceLabeler:
    def __init__(self, climbs: list[dict[str, Any]]):
        self.climbs = climbs
        self.index = 0
        self.hand = "left"
        self.progress = self.load_progress()

    def load_progress(self) -> dict[str, Any]:
        if PROGRESS_PATH.exists():
            with PROGRESS_PATH.open("r", encoding="utf-8") as file:
                return json.load(file)
        return {"current_index": 0, "labels": {}}

    def save_progress(self) -> None:
        self.progress["current_index"] = self.index
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with PROGRESS_PATH.open("w", encoding="utf-8") as file:
            json.dump(self.progress, file, indent=2)
        self.save_current_image()

    def save_current_image(self) -> None:
        climb = dict(self.current)
        manual = self.progress["labels"].get(self.current["uuid"], {}).get("hand_sequence")
        if manual:
            climb["hand_sequence"] = manual
        render_climb_png(climb, OUTPUT_DIR / "manual_images" / f"{self.index + 1:03d}_{self.current['uuid']}.png", title=f"Manual {self.index + 1:03d} {self.current['grade']} {self.current['name']}")

    @property
    def current(self) -> dict[str, Any]:
        return self.climbs[self.index]

    def current_manual(self) -> list[dict[str, Any]]:
        labels = self.progress["labels"].setdefault(self.current["uuid"], {"hand_sequence": []})
        return labels["hand_sequence"]

    def add_hold(self, x: int, y: int) -> None:
        sequence = self.current_manual()
        move = len(sequence)
        sequence.append({
            "x": x,
            "y": y,
            "type": "Any",
            "hand": self.hand,
            "move": move,
            "label": f"{move}{'L' if self.hand == 'left' else 'R'}",
        })
        self.hand = "right" if self.hand == "left" else "left"

    def backspace(self) -> None:
        sequence = self.current_manual()
        if sequence:
            removed = sequence.pop()
            self.hand = removed.get("hand", "left")

    def next(self) -> None:
        self.save_progress()
        self.index = min(len(self.climbs) - 1, self.index + 1)
        self.hand = "left"

    def previous(self) -> None:
        self.save_progress()
        self.index = max(0, self.index - 1)
        self.hand = "left"

    def draw(self, axes) -> None:
        for ax in axes:
            ax.clear()
            ax.imshow(board_crop())
            ax.set_axis_off()
        climb = self.current
        heuristic = estimate_hand_sequence(
            climb["holds"],
            matching_allowed=bool(climb.get("matching_allowed", True)),
            grade=climb.get("grade"),
        )
        axes[0].set_title(f"Heuristic {self.index + 1}/100: {climb['grade']} {climb['name']}")
        axes[1].set_title(f"Manual: click holds, key L/R toggles, S saves, N/P nav, backspace undo, Q quit. Next hand: {self.hand}")
        draw_climb(axes[0], climb, heuristic)
        draw_climb(axes[1], climb, self.current_manual())


def draw_climb(ax, climb: dict[str, Any], sequence: list[dict[str, Any]]) -> None:
    for hold_type, color in HOLD_COLORS.items():
        rgb = tuple(channel / 255 for channel in color)
        for hx, hy in climb["holds"].get(hold_type, []):
            x, y = board_point(hx, hy)
            ax.add_patch(plt.Circle((x, y), 15, fill=False, edgecolor=rgb, linewidth=2.5))
    label_offsets: dict[tuple[int, int], int] = {}
    for move in sequence:
        x, y = board_point(move["x"], move["y"])
        key = (int(move["x"]), int(move["y"]))
        offset_index = label_offsets.get(key, 0)
        label_offsets[key] = offset_index + 1
        label = move.get("label") or f"{move.get('move', '')}{'L' if move.get('hand') == 'left' else 'R'}"
        ax.text(x + 15, y - 12 + offset_index * 13, label, color="white", fontsize=8, weight="bold", path_effects=[])


def nearest_hold(event) -> tuple[int, int] | None:
    if event.xdata is None or event.ydata is None:
        return None
    best = None
    best_d = 1e9
    for x in range(1, 36):
        for y in range(1, 40):
            px, py = board_point(x, y)
            d = ((px - event.xdata) ** 2 + (py - event.ydata) ** 2) ** 0.5
            if d < best_d:
                best = (x, y)
                best_d = d
    return best if best_d < 24 else None


def run_gui(limit: int | None = None) -> None:
    records = load_db_records(include_sequences=False)
    climbs = select_sequence_review_climbs(records)
    if limit:
        climbs = climbs[:limit]
    write_sequence_review_set(climbs, OUTPUT_DIR / "heuristic_100")
    labeler = SequenceLabeler(climbs)
    labeler.index = min(int(labeler.progress.get("current_index") or 0), len(climbs) - 1)
    fig, axes = plt.subplots(1, 2, figsize=(12, 8))

    def redraw() -> None:
        labeler.draw(axes)
        fig.canvas.draw_idle()

    def on_click(event) -> None:
        if event.inaxes != axes[1]:
            return
        hold = nearest_hold(event)
        if hold:
            labeler.add_hold(*hold)
            redraw()

    def on_key(event) -> None:
        key = (event.key or "").lower()
        if key == "l":
            labeler.hand = "left"
        elif key == "r":
            labeler.hand = "right"
        elif key in {"backspace", "delete"}:
            labeler.backspace()
        elif key == "s":
            labeler.save_progress()
        elif key == "n":
            labeler.next()
        elif key == "p":
            labeler.previous()
        elif key == "q":
            labeler.save_progress()
            plt.close(fig)
            return
        redraw()

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    redraw()
    plt.show()
    labeler.save_progress()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run_gui(args.limit)


if __name__ == "__main__":
    main()
