"""Core climb coordinate utilities for the Kilter web app."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any


HOLD_TYPES = ("Start", "Any", "Finish", "Feet")
HAND_HOLD_TYPES = ("Start", "Any", "Finish")
GRID_COLUMNS = 35
GRID_ROWS = 39


class ClimbValidationError(ValueError):
    """Raised when a climb cannot be saved or animated."""


@dataclass(frozen=True)
class SequencedMove:
    x: int
    y: int
    hold_type: str
    hand: str

    def as_dict(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "type": self.hold_type, "hand": self.hand}


def normalize_holds(raw_holds: dict[str, Any]) -> dict[str, list[list[int]]]:
    holds: dict[str, list[list[int]]] = {hold_type: [] for hold_type in HOLD_TYPES}
    for hold_type, raw_points in (raw_holds or {}).items():
        if hold_type not in HOLD_TYPES:
            continue
        for point in raw_points or []:
            if isinstance(point, dict):
                x = point.get("x")
                y = point.get("y")
            else:
                x, y = point[:2]
            holds[hold_type].append([int(x), int(y)])
    return holds


def validate_climb(climb: dict[str, Any]) -> dict[str, Any]:
    name = str(climb.get("name") or climb.get("Name") or "").strip()
    if not name:
        raise ClimbValidationError("Climb name is required.")

    grade = str(climb.get("grade") or climb.get("Grade") or "Unknown").strip()
    angle = str(climb.get("angle") or climb.get("Angle") or "Unknown").strip()
    holds = normalize_holds(climb.get("holds") or climb.get("Holds") or {})

    seen: set[tuple[int, int, str]] = set()
    for hold_type in HOLD_TYPES:
        deduped: list[list[int]] = []
        for x, y in holds[hold_type]:
            if not 1 <= x <= GRID_COLUMNS or not 1 <= y <= GRID_ROWS:
                raise ClimbValidationError(f"{hold_type} hold ({x}, {y}) is outside the board.")
            key = (x, y, hold_type)
            if key not in seen:
                seen.add(key)
                deduped.append([x, y])
        holds[hold_type] = deduped

    if len(holds["Start"]) > 2:
        raise ClimbValidationError("A climb can have at most two start holds.")
    if len(holds["Finish"]) > 2:
        raise ClimbValidationError("A climb can have at most two finish holds.")
    if not holds["Start"]:
        raise ClimbValidationError("A climb needs at least one start hold.")
    if not holds["Finish"]:
        raise ClimbValidationError("A climb needs at least one finish hold.")

    return {"name": name, "grade": grade, "angle": angle, "holds": holds}


def estimate_sequence(holds: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = normalize_holds(holds)
    hand_holds: list[tuple[int, int, str]] = []
    for hold_type in HAND_HOLD_TYPES:
        for x, y in normalized[hold_type]:
            hand_holds.append((x, y, hold_type))

    starts = sorted([hold for hold in hand_holds if hold[2] == "Start"], key=lambda h: (h[0], h[1]))
    middles = sorted([hold for hold in hand_holds if hold[2] == "Any"], key=lambda h: (h[1], h[0]))
    finishes = sorted([hold for hold in hand_holds if hold[2] == "Finish"], key=lambda h: (h[1], h[0]))

    ordered: list[tuple[int, int, str]] = starts[:]
    remaining = middles[:]
    current = _mean_point(ordered) if ordered else (GRID_COLUMNS / 2, 1)
    while remaining:
        next_hold = min(remaining, key=lambda hold: (hypot(hold[0] - current[0], hold[1] - current[1]), hold[1], hold[0]))
        ordered.append(next_hold)
        remaining.remove(next_hold)
        current = (next_hold[0], next_hold[1])
    ordered.extend(finishes)

    sequence: list[SequencedMove] = []
    left_x = starts[0][0] if starts else GRID_COLUMNS / 2 - 1
    right_x = starts[-1][0] if len(starts) > 1 else GRID_COLUMNS / 2 + 1
    for index, hold in enumerate(ordered):
        x, y, hold_type = hold
        if hold_type == "Start" and len(starts) > 1:
            hand = "left" if index == 0 else "right"
        elif hold_type == "Finish" and sequence and sequence[-1].hold_type == "Finish":
            hand = "right" if sequence[-1].hand == "left" else "left"
        else:
            hand = "left" if abs(x - left_x) <= abs(x - right_x) else "right"
        if hand == "left":
            left_x = x
        else:
            right_x = x
        sequence.append(SequencedMove(x=x, y=y, hold_type=hold_type, hand=hand))

    if finishes and len(finishes) == 1:
        finish_x, finish_y, hold_type = finishes[0]
        last_hand = sequence[-1].hand if sequence else "left"
        sequence.append(
            SequencedMove(
                x=finish_x,
                y=finish_y,
                hold_type=hold_type,
                hand="right" if last_hand == "left" else "left",
            )
        )

    return [move.as_dict() for move in sequence]


def _mean_point(points: list[tuple[int, int, str]]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )
