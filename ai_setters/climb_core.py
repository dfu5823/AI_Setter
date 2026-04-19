"""Core climb coordinate utilities for the Kilter web app."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any


HOLD_TYPES = ("Start", "Any", "Finish", "Feet")
HAND_HOLD_TYPES = ("Start", "Any", "Finish")
GRID_COLUMNS = 35
GRID_ROWS = 39
MAX_HAND_SPAN = 18.0
MAX_ABSOLUTE_MOVE = 21.0
CROSS_REACH_LIMIT = 10.0
MATCH_DISTANCE = 3.0
DEFAULT_CLIMBER_HEIGHT_UNITS = 22.0


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

    return {"name": name, "grade": grade, "angle": angle, "matching_allowed": bool(climb.get("matching_allowed", True)), "holds": holds}


def estimate_sequence(
    holds: dict[str, Any],
    hold_usage_preference: int = 4,
    matching_allowed: bool = True,
    grade: str | int | float | None = None,
) -> list[dict[str, Any]]:
    return estimate_hand_sequence(holds, hold_usage_preference, matching_allowed, grade)


def estimate_hand_sequence(
    holds: dict[str, Any],
    hold_usage_preference: int = 4,
    matching_allowed: bool = True,
    grade: str | int | float | None = None,
) -> list[dict[str, Any]]:
    normalized = normalize_holds(holds)
    hand_holds: list[tuple[int, int, str]] = []
    for hold_type in HAND_HOLD_TYPES:
        for x, y in normalized[hold_type]:
            hand_holds.append((x, y, hold_type))

    starts = sorted([hold for hold in hand_holds if hold[2] == "Start"], key=lambda h: (h[0], h[1]))
    middles = sorted([hold for hold in hand_holds if hold[2] == "Any"], key=lambda h: (h[1], h[0]))
    finishes = sorted([hold for hold in hand_holds if hold[2] == "Finish"], key=lambda h: (h[1], h[0]))

    ordered: list[tuple[int, int, str]] = order_hand_targets_stateful(starts, middles, finishes, hold_usage_preference)
    if not starts and ordered:
        starts = [ordered[0]]

    left = starts[0] if starts else (GRID_COLUMNS // 2 - 1, 1, "Start")
    right = starts[-1] if len(starts) > 1 else left
    sequence: list[dict[str, Any]] = []
    sequence.append(_move_dict(left, "left", 0, left, right, "start"))
    if right[:2] != left[:2]:
        sequence.append(_move_dict(right, "right", 0, left, right, "start"))
    else:
        sequence.append(_move_dict(right, "right", 0, left, right, "matched_start"))

    targets = [hold for hold in ordered if hold[2] != "Start"]
    sequence.extend(
        optimize_hand_assignments(
            targets,
            left,
            right,
            last_hand="",
            start_move=1,
            matching_allowed=matching_allowed,
            grade=grade,
        )
    )

    if finishes:
        left = (sequence[-1]["left"][0], sequence[-1]["left"][1], "Finish")
        right = (sequence[-1]["right"][0], sequence[-1]["right"][1], "Finish")
        move_number = int(sequence[-1]["move"]) + 1
        finish_points = {finish[:2] for finish in finishes}
        if len(finish_points) == 1:
            finish = finishes[-1]
            if left[:2] != finish[:2]:
                left = finish
                sequence.append(_move_dict(finish, "left", move_number, left, right, "finish_match" + ("+dyno" if hold_distance(left, right) > MAX_HAND_SPAN else "")))
                move_number += 1
            if right[:2] != finish[:2]:
                right = finish
                sequence.append(_move_dict(finish, "right", move_number, left, right, "finish_match"))
        elif left[:2] not in finish_points or right[:2] not in finish_points or left[:2] == right[:2]:
            occupied = {left[:2], right[:2]} & finish_points
            missing = [finish for finish in finishes if finish[:2] not in occupied]
            if missing:
                finish = missing[-1]
                hand = "left" if left[:2] not in finish_points else "right"
                if hand == "left":
                    left = finish
                else:
                    right = finish
                sequence.append(_move_dict(finish, hand, move_number, left, right, "finish_pair" + ("+dyno" if hold_distance(left, right) > MAX_HAND_SPAN else "")))

    return sequence


def optimize_hand_assignments(
    targets: list[tuple[int, int, str]],
    start_left: tuple[int, int, str],
    start_right: tuple[int, int, str],
    last_hand: str = "right",
    start_move: int = 1,
    beam_width: int = 64,
    matching_allowed: bool = True,
    grade: str | int | float | None = None,
) -> list[dict[str, Any]]:
    """Search over L/R assignments so later bad states can revise earlier moves."""
    states = [{
        "score": 0.0,
        "left": start_left,
        "right": start_right,
        "last_hand": last_hand,
        "last_event": "start",
        "path": [],
    }]
    grade_v = grade_to_number(grade)
    move_number = start_move
    for target in targets:
        next_states: list[dict[str, Any]] = []
        for state in states:
            if target[2] == "Any":
                skip_penalty = 700.0 if target[1] >= min(state["left"][1], state["right"][1]) else 280.0
                next_states.append({
                    "score": float(state["score"]) + skip_penalty,
                    "left": state["left"],
                    "right": state["right"],
                    "last_hand": state["last_hand"],
                    "last_event": state["last_event"],
                    "path": [*state["path"]],
                })
            for hand in ("left", "right"):
                transition = score_hand_transition(
                    state["left"],
                    state["right"],
                    target,
                    hand,
                    state["last_hand"],
                    state["last_event"],
                    matching_allowed,
                    grade_v,
                )
                if transition is None:
                    continue
                cost, event, new_left, new_right = transition
                move = _move_dict(target, hand, move_number, new_left, new_right, event)
                next_states.append({
                    "score": float(state["score"]) + cost,
                    "left": new_left,
                    "right": new_right,
                    "last_hand": hand,
                    "last_event": event,
                    "path": [*state["path"], move],
                })
        if not next_states:
            # Fall back to the greedy chooser if constraints leave no beam candidate.
            fallback = []
            left = start_left
            right = start_right
            hand = last_hand
            event = "start"
            for move_offset, target in enumerate(targets):
                hand, event = choose_next_hand(left, right, target, hand, event, matching_allowed, grade_v)
                if hand == "left":
                    left = target
                else:
                    right = target
                event = classify_hand_event(left, right, target, hand, hand, event)
                fallback.append(_move_dict(target, hand, start_move + move_offset, left, right, event))
            return fallback
        next_states.sort(key=lambda state: state["score"])
        states = next_states[:beam_width]
        if any(state["path"] and state["path"][-1].get("move") == move_number for state in states):
            move_number += 1
    return renumber_sequence(states[0]["path"]) if states else []


def score_hand_transition(
    left: tuple[int, int, str],
    right: tuple[int, int, str],
    target: tuple[int, int, str],
    hand: str,
    last_hand: str,
    last_event: str,
    matching_allowed: bool = True,
    grade_v: int | None = None,
) -> tuple[float, str, tuple[int, int, str], tuple[int, int, str]] | None:
    moving = left if hand == "left" else right
    stationary = right if hand == "left" else left
    new_left = target if hand == "left" else left
    new_right = right if hand == "left" else target
    event_parts: list[str] = []
    move_distance = hold_distance(moving, target)
    span = hold_distance(new_left, new_right)
    stationary_reach = hold_distance(stationary, target)
    if target[:2] == stationary[:2] and not matching_allowed:
        return None
    if span > MAX_ABSOLUTE_MOVE:
        return None
    score = move_distance + 0.75 * span
    current_low = min(left[1], right[1])
    if target[:2] == stationary[:2]:
        event_parts.append("match_discouraged")
        score += 130
    if target[1] < current_low:
        event_parts.append("down")
        score += 180 + 22 * (current_low - target[1])
    lower_hand = "left" if left[1] < right[1] else "right" if right[1] < left[1] else ""
    if lower_hand and hand != lower_hand and target[1] >= current_low:
        score += 600
    if hand == last_hand:
        if "bump" in str(last_event):
            return None
        event_parts.append("bump")
        score += 120
        if span > 12:
            easy_multiplier = 1.8 if grade_v is not None and grade_v <= 5 else 1.2 if grade_v is not None and grade_v <= 8 else 1.0
            score += easy_multiplier * (180 + 35 * (span - 12))
    if is_crossed(new_left, new_right):
        event_parts.append("cross")
        score += 450
        if stationary_reach > CROSS_REACH_LIMIT:
            score += 250
    if span > MAX_HAND_SPAN:
        event_parts.append("dyno")
        score += 1400 + 110 * (span - MAX_HAND_SPAN)
    if move_distance > MAX_HAND_SPAN:
        event_parts.append("dyno")
        dx = abs(target[0] - moving[0])
        dy_up = max(0.0, target[1] - moving[1])
        ratio = dx / max(move_distance, 1e-6)
        vertical_ratio = dy_up / max(move_distance, 1e-6)
        score += 250 + 45 * (move_distance - MAX_HAND_SPAN) + 260 * ratio - 140 * vertical_ratio
    if move_distance > MAX_ABSOLUTE_MOVE:
        event_parts.append("long_move")
        score += 140 + 70 * (move_distance - MAX_ABSOLUTE_MOVE)
    if span < MATCH_DISTANCE:
        event_parts.append("close_hands")
        score += 24 * (MATCH_DISTANCE - span)
    if hand != last_hand:
        score -= 5
    event = "+".join(dict.fromkeys(event_parts)) if event_parts else "hand_move"
    return score, event, new_left, new_right


def classify_hand_event(
    left: tuple[int, int, str],
    right: tuple[int, int, str],
    target: tuple[int, int, str],
    hand: str,
    last_hand: str,
    base_event: str,
) -> str:
    event_parts = [base_event]
    if hand == last_hand and "bump" not in event_parts:
        event_parts.append("bump")
    if is_crossed(left, right):
        event_parts.append("cross")
    if hold_distance(left, right) > MAX_HAND_SPAN:
        event_parts.append("dyno")
    if hold_distance(left, right) < MATCH_DISTANCE:
        event_parts.append("close_hands")
    return "+".join(dict.fromkeys(event_parts))


def order_hand_targets(
    starts: list[tuple[int, int, str]],
    middles: list[tuple[int, int, str]],
    finishes: list[tuple[int, int, str]],
    hold_usage_preference: int = 4,
) -> list[tuple[int, int, str]]:
    ordered: list[tuple[int, int, str]] = starts[:]
    remaining = middles[:]
    current = _mean_point(ordered) if ordered else (GRID_COLUMNS / 2, 1)
    preference = max(1, min(5, int(hold_usage_preference or 4)))
    while remaining:
        if preference >= 4:
            key = lambda hold: (
                hold[1] < current[1],
                max(0.0, current[1] - hold[1]) * 8,
                unvisited_down_penalty(hold, remaining),
                hypot(hold[0] - current[0], hold[1] - current[1]),
                hold[1],
                hold[0],
            )
        elif preference <= 2:
            key = lambda hold: (hold[1] < current[1] - 2, hold[1], hypot(hold[0] - current[0], hold[1] - current[1]), hold[0])
        else:
            key = lambda hold: (hold[1] < current[1] - 1, hypot(hold[0] - current[0], hold[1] - current[1]), hold[1], hold[0])
        next_hold = min(remaining, key=key)
        ordered.append(next_hold)
        remaining.remove(next_hold)
        current = (next_hold[0], next_hold[1])
    ordered.extend(finishes)
    return ordered


def order_hand_targets_stateful(
    starts: list[tuple[int, int, str]],
    middles: list[tuple[int, int, str]],
    finishes: list[tuple[int, int, str]],
    hold_usage_preference: int = 4,
) -> list[tuple[int, int, str]]:
    ordered: list[tuple[int, int, str]] = starts[:]
    remaining = middles[:]
    left = starts[0] if starts else (GRID_COLUMNS // 2 - 1, 1, "Start")
    right = starts[-1] if len(starts) > 1 else left
    last_hand = ""
    finish = finishes[-1] if finishes else None
    preference = max(1, min(5, int(hold_usage_preference or 4)))
    while remaining:
        scored = []
        for hold in remaining:
            best = best_transition_for_ordering(left, right, hold, last_hand)
            if best is None:
                scored.append((100000.0, hold, None))
                continue
            cost, hand, new_left, new_right = best
            finish_bias = hold_distance(hold, finish) * 0.2 if finish else 0.0
            downward = max(0.0, min(left[1], right[1]) - hold[1])
            stranded_lower = unvisited_down_penalty(hold, remaining) * 1.4
            use_bias = 0.0 if preference >= 4 else hold[1] * 0.2
            scored.append((cost + finish_bias + stranded_lower + downward * 20 + use_bias, hold, (hand, new_left, new_right)))
        scored.sort(key=lambda item: (item[0], item[1][1], item[1][0]))
        _score, hold, transition = scored[0]
        ordered.append(hold)
        remaining.remove(hold)
        if transition is not None:
            last_hand, left, right = transition
    ordered.extend(finishes)
    return ordered


def best_transition_for_ordering(
    left: tuple[int, int, str],
    right: tuple[int, int, str],
    target: tuple[int, int, str],
    last_hand: str,
) -> tuple[float, str, tuple[int, int, str], tuple[int, int, str]] | None:
    options = []
    for hand in ("left", "right"):
        moving = left if hand == "left" else right
        new_left = target if hand == "left" else left
        new_right = right if hand == "left" else target
        span = hold_distance(new_left, new_right)
        if span > MAX_ABSOLUTE_MOVE:
            continue
        move_distance = hold_distance(moving, target)
        cost = move_distance + span
        if move_distance > MAX_HAND_SPAN:
            dx = abs(target[0] - moving[0])
            cost += 120 + 35 * (move_distance - MAX_HAND_SPAN) + 15 * max(0, dx - 12)
        if is_crossed(new_left, new_right):
            cost += 120
        if hand == last_hand:
            cost += 180
        lower_hand = "left" if left[1] < right[1] else "right" if right[1] < left[1] else ""
        if lower_hand and hand != lower_hand and target[1] >= min(left[1], right[1]):
            cost += 350
        if target[1] < min(left[1], right[1]):
            cost += 500
        options.append((cost, hand, new_left, new_right))
    if not options:
        return None
    return min(options, key=lambda item: item[0])


def unvisited_down_penalty(candidate: tuple[int, int, str], remaining: list[tuple[int, int, str]]) -> float:
    lower_holds = [
        hold for hold in remaining
        if hold != candidate and hold[2] == "Any" and hold[1] < candidate[1]
    ]
    return sum((candidate[1] - hold[1]) * 12 for hold in lower_holds)


def choose_next_hand(
    left: tuple[int, int, str],
    right: tuple[int, int, str],
    target: tuple[int, int, str],
    last_hand: str,
    last_event: str = "",
    matching_allowed: bool = True,
    grade_v: int | None = None,
) -> tuple[str, str]:
    if target[:2] == left[:2]:
        return "left", "match_discouraged"
    if target[:2] == right[:2]:
        return "right", "match_discouraged"
    lower_hand = "left" if left[1] < right[1] else "right" if right[1] < left[1] else (
        "left" if hold_distance(left, target) <= hold_distance(right, target) else "right"
    )
    preferred = lower_hand
    alternate = "right" if preferred == "left" else "left"

    def state_for(hand: str) -> tuple[tuple[int, int, str], tuple[int, int, str]]:
        return (target, right) if hand == "left" else (left, target)

    def penalty(hand: str) -> tuple[float, str]:
        new_left, new_right = state_for(hand)
        stationary = right if hand == "left" else left
        span = hold_distance(new_left, new_right)
        move_distance = hold_distance(left if hand == "left" else right, target)
        if target[:2] == stationary[:2] and not matching_allowed:
            return 100000.0, "blocked_match"
        if move_distance > MAX_ABSOLUTE_MOVE or span > MAX_ABSOLUTE_MOVE:
            return 100000.0, "blocked_long_move"
        crossed = is_crossed(new_left, new_right)
        reach = hold_distance(stationary, target)
        event = "hand_move"
        score = span
        current_low = min(left[1], right[1])
        if target[1] < current_low:
            score += 180 + 22 * (current_low - target[1])
        if crossed:
            score += 30
            event = "cross"
            if reach > CROSS_REACH_LIMIT:
                score += 100
        if span > MAX_HAND_SPAN:
            score += 1400 + 110 * (span - MAX_HAND_SPAN)
            event = "dyno"
        if move_distance > MAX_HAND_SPAN:
            dx = abs(target[0] - (left[0] if hand == "left" else right[0]))
            ratio = dx / max(move_distance, 1e-6)
            score += 1500 + 1300 * ratio
            event = "dyno"
        if span < MATCH_DISTANCE:
            score += 90
        if hand == last_hand and not is_crossed(left, right):
            event = "bump" if event == "hand_move" else f"bump_{event}"
            score += 18
            if "bump" in str(last_event):
                score += 10000
            if span > 12:
                easy_multiplier = 1.8 if grade_v is not None and grade_v <= 5 else 1.0
                score += easy_multiplier * (180 + 35 * (span - 12))
        return score, event

    preferred_score, preferred_event = penalty(preferred)
    alternate_score, alternate_event = penalty(alternate)
    if alternate_score + 5 < preferred_score:
        return alternate, alternate_event
    if preferred_score > 40 and last_hand in {"left", "right"} and not is_crossed(left, right) and "bump" not in str(last_event):
        bump_hand = last_hand
        bump_score, bump_event = penalty(bump_hand)
        if bump_score < min(preferred_score, alternate_score) and hold_distance(*state_for(bump_hand)) <= MAX_HAND_SPAN:
            return bump_hand, bump_event
    return preferred, preferred_event


def renumber_sequence(sequence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for move_number, move in enumerate(sequence, start=1):
        if move.get("type") == "Start":
            number = 0
        else:
            number = move_number
        move["move"] = number
        move["label"] = f"{number}{'L' if move.get('hand') == 'left' else 'R'}"
    return sequence


def grade_to_number(grade: str | int | float | None) -> int | None:
    if isinstance(grade, (int, float)):
        return int(grade)
    if grade is None:
        return None
    import re

    match = re.search(r"V(\d+)", str(grade), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def estimate_foot_sequence(
    holds: dict[str, Any],
    hand_sequence: list[dict[str, Any]] | None = None,
    climber_height_units: float = DEFAULT_CLIMBER_HEIGHT_UNITS,
    foot_usage_preference: int = 3,
) -> list[dict[str, Any]]:
    normalized = normalize_holds(holds)
    hand_sequence = hand_sequence or estimate_hand_sequence(holds)
    sequence: list[dict[str, Any]] = []
    previous_left: tuple[int, int] | None = None
    previous_right: tuple[int, int] | None = None
    seen_states: set[tuple[int, tuple[int, int], tuple[int, int]]] = set()
    for move in hand_sequence:
        left_hand = tuple(move["left"])  # type: ignore[arg-type]
        right_hand = tuple(move["right"])  # type: ignore[arg-type]
        state_key = (int(move["move"]), left_hand, right_hand)
        if state_key in seen_states:
            continue
        seen_states.add(state_key)
        candidates = foot_candidates_for_hands(normalized, left_hand, right_hand, climber_height_units)
        no_penalty = [item for item in candidates if item["penalty"] <= 0]
        left_foot, right_foot = choose_beta_feet(
            candidates,
            left_hand,
            right_hand,
            previous_left,
            previous_right,
            require_no_penalty=True,
        )
        previous_left = left_foot
        previous_right = right_foot
        foot_moves = []
        if left_foot:
            foot_moves.append({"label": f"{move['move']}fL", "foot": "left", "x": left_foot[0], "y": left_foot[1], "penalty": foot_candidate_penalty(normalized, left_hand, right_hand, left_foot, climber_height_units)})
        if right_foot:
            foot_moves.append({"label": f"{move['move']}fR", "foot": "right", "x": right_foot[0], "y": right_foot[1], "penalty": foot_candidate_penalty(normalized, left_hand, right_hand, right_foot, climber_height_units)})
        sequence.append({
            "move": move["move"],
            "left": list(left_foot) if left_foot else None,
            "right": list(right_foot) if right_foot else None,
            "candidates": [{"x": item["hold"][0], "y": item["hold"][1], "penalty": item["penalty"], "source": item["source"]} for item in candidates[:3]],
            "foot_moves": foot_moves,
        })
    return sequence


def foot_candidates_for_hands(
    holds: dict[str, Any],
    left_hand: tuple[int, int],
    right_hand: tuple[int, int],
    climber_height_units: float = DEFAULT_CLIMBER_HEIGHT_UNITS,
) -> list[dict[str, Any]]:
    normalized = normalize_holds(holds)
    all_holds: dict[tuple[int, int], str] = {}
    for hold_type in ("Start", "Any", "Finish", "Feet"):
        for point in normalized[hold_type]:
            key = (int(point[0]), int(point[1]))
            all_holds[key] = "Feet" if hold_type == "Feet" else all_holds.get(key, hold_type)
    candidates = []
    for hold, source in all_holds.items():
        if hold in {left_hand, right_hand}:
            continue
        penalty = foot_candidate_penalty(normalized, left_hand, right_hand, hold, climber_height_units)
        if penalty is None:
            continue
        dist = min(hold_distance(hold, left_hand), hold_distance(hold, right_hand))
        candidates.append({"hold": hold, "source": source, "penalty": penalty, "distance": dist})
    no_penalty = [item for item in candidates if item["penalty"] <= 0]
    if len(no_penalty) >= 3:
        return sorted(no_penalty, key=lambda item: (-item["distance"], item["source"] != "Feet", item["hold"][1], item["hold"][0]))[:3]
    return sorted(candidates, key=lambda item: (item["penalty"], -item["distance"], item["source"] != "Feet", item["hold"][1], item["hold"][0]))[:3]


def foot_candidate_penalty(
    holds: dict[str, Any],
    left_hand: tuple[int, int],
    right_hand: tuple[int, int],
    foot: tuple[int, int],
    climber_height_units: float = DEFAULT_CLIMBER_HEIGHT_UNITS,
) -> float | None:
    min_vertical_drop = min(left_hand[1] - foot[1], right_hand[1] - foot[1])
    max_vertical_drop = max(left_hand[1] - foot[1], right_hand[1] - foot[1])
    euclid = min(hold_distance(foot, left_hand), hold_distance(foot, right_hand))
    if max_vertical_drop > 22 or euclid > 19:
        return None
    penalty = 0.0
    if euclid < 3:
        penalty += (3 - euclid) * 4
    if min_vertical_drop < 4:
        penalty += (4 - min_vertical_drop) * 18
    if max_vertical_drop > 18:
        penalty += (max_vertical_drop - 18) ** 2 * 8
    if euclid > 17:
        penalty += (euclid - 17) ** 2 * 16
    return penalty


def choose_beta_feet(
    candidates: list[dict[str, Any]],
    left_hand: tuple[int, int],
    right_hand: tuple[int, int],
    previous_left: tuple[int, int] | None = None,
    previous_right: tuple[int, int] | None = None,
    require_no_penalty: bool = True,
) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    pool = [item for item in candidates if not require_no_penalty or item["penalty"] <= 0]
    if not pool:
        return None, None
    midpoint = (left_hand[0] + right_hand[0]) / 2
    holds = [item["hold"] for item in pool]
    if previous_left in holds and previous_right in holds and previous_left != previous_right and foot_pair_penalty(previous_left, previous_right, midpoint) <= 0:
        return previous_left, previous_right
    best: tuple[float, tuple[int, int] | None, tuple[int, int] | None] = (float("inf"), None, None)
    options: list[tuple[tuple[int, int] | None, tuple[int, int] | None]] = [(None, None)]
    for hold in holds:
        if hold[0] <= midpoint:
            options.append((hold, None))
        if hold[0] >= midpoint:
            options.append((None, hold))
    for left in holds:
        for right in holds:
            if left != right:
                options.append(assign_feet_by_midpoint(left, right, midpoint))
    for left, right in options:
        if left is None and right is None:
            score = 1000
        elif left is None or right is None:
            score = 40
        else:
            score = foot_pair_penalty(left, right, midpoint)
        if score < best[0]:
            best = (score, left, right)
    return best[1], best[2]


def assign_feet_by_midpoint(a: tuple[int, int], b: tuple[int, int], midpoint: float) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    if a[0] <= midpoint < b[0]:
        return a, b
    if b[0] <= midpoint < a[0]:
        return b, a
    higher, lower = (a, b) if a[1] >= b[1] else (b, a)
    return (higher, lower) if higher[0] <= midpoint else (lower, higher)


def foot_pair_penalty(left: tuple[int, int], right: tuple[int, int], midpoint: float) -> float:
    penalty = 0.0
    if left[0] > right[0]:
        penalty += 20 + min(200, (left[0] - right[0]) * 16)
    if abs(left[0] - right[0]) < 0.5:
        penalty += 4
    span = hold_distance(left, right)
    if span > 16:
        penalty += (span - 16) ** 2 * (8 if span <= 22 else 80)
    return penalty


def sequence_metrics(hand_sequence: list[dict[str, Any]], foot_sequence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    crosses = sum(1 for move in hand_sequence if move.get("crossed"))
    dynos = sum(1 for move in hand_sequence if "dyno" in str(move.get("event", "")))
    bumps = sum(1 for move in hand_sequence if "bump" in str(move.get("event", "")))
    move_distances = [
        hypot(hand_sequence[i]["x"] - hand_sequence[i - 1]["x"], hand_sequence[i]["y"] - hand_sequence[i - 1]["y"])
        for i in range(1, len(hand_sequence))
    ]
    interhand = [hypot(move["left"][0] - move["right"][0], move["left"][1] - move["right"][1]) for move in hand_sequence]
    foot_moves = 0
    if foot_sequence:
        for current, nxt in zip(foot_sequence, foot_sequence[1:]):
            if current.get("left") != nxt.get("left"):
                foot_moves += 1
            if current.get("right") != nxt.get("right"):
                foot_moves += 1
    return {
        "moves": len(hand_sequence),
        "crosses": crosses,
        "dynos": dynos,
        "bumps": bumps,
        "average_move_distance": sum(move_distances) / len(move_distances) if move_distances else 0.0,
        "average_interhand_distance": sum(interhand) / len(interhand) if interhand else 0.0,
        "max_interhand_distance": max(interhand) if interhand else 0.0,
        "foot_moves": foot_moves,
    }


def is_crossed(left: tuple[int, int, str] | tuple[int, int], right: tuple[int, int, str] | tuple[int, int]) -> bool:
    return left[0] > right[0]


def hold_distance(a: tuple[int, int, str] | tuple[int, int], b: tuple[int, int, str] | tuple[int, int]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _move_dict(
    hold: tuple[int, int, str],
    hand: str,
    move_number: int,
    left: tuple[int, int, str],
    right: tuple[int, int, str],
    event: str,
) -> dict[str, Any]:
    return {
        "x": hold[0],
        "y": hold[1],
        "type": hold[2],
        "hand": hand,
        "move": move_number,
        "label": f"{move_number}{'L' if hand == 'left' else 'R'}",
        "left": [left[0], left[1]],
        "right": [right[0], right[1]],
        "node": {"left": [left[0], left[1]], "right": [right[0], right[1]]},
        "event": event,
        "crossed": is_crossed(left, right),
        "interhand_distance": hold_distance(left, right),
    }


def _mean_point(points: list[tuple[int, int, str]]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )
