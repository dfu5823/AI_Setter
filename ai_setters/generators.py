"""Coordinate-backed climb generators."""

from __future__ import annotations

import json
import pickle
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .climb_core import (
    GRID_COLUMNS,
    GRID_ROWS,
    estimate_foot_sequence,
    estimate_hand_sequence,
    estimate_sequence,
    foot_candidate_penalty,
    hold_distance,
    normalize_holds,
    sequence_metrics,
    validate_climb,
)
from .config import load_config
from .dataset import ROOT, grade_to_v, hold_size_bins, load_dataset, valid_hold_positions


class RandomSetter:
    name = "random"

    def __init__(self, records: list[dict[str, Any]] | None = None, valid_holds: set[tuple[int, int]] | None = None):
        self.records = records if records is not None else load_dataset()
        self.valid_holds = sorted(valid_holds if valid_holds is not None else valid_hold_positions())
        self.size_bins = hold_size_bins()

    def create(self, grade: str = "V5", angle: str = "50", seed: int | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        rng = random.Random(seed)
        options = options or {}
        hand_count = int(options.get("hand_count") or rng.randint(6, 9))

        allowed_holds = self._difficulty_holds(grade, rng)
        low_zone = [h for h in allowed_holds if 1 <= h[1] <= 9] or [h for h in self.valid_holds if 1 <= h[1] <= 9]
        starts = self._reachable_pair(rng, low_zone, max_span=18)
        current = mean_point(starts)
        any_holds: list[tuple[int, int]] = []
        for step in range(max(1, hand_count - len(starts) - 1)):
            target_y = int(round(10 + (step + 1) * (20 / max(1, hand_count - 3))))
            reach_limit = self._sample_reach_limit(rng)
            candidates = [
                hold
                for hold in allowed_holds
                if hold not in starts and abs(hold[1] - target_y) <= 5 and distance(hold, current) <= reach_limit
            ]
            if not candidates:
                candidates = [hold for hold in allowed_holds if hold not in starts and 8 <= hold[1] <= 31 and distance(hold, current) <= 18]
            if not candidates:
                candidates = [hold for hold in allowed_holds if hold not in starts and hold[1] >= current[1] and distance(hold, current) <= 18]
            if not candidates:
                break
            nxt = self._weighted_reach_choice(rng, candidates, current, reach_limit)
            any_holds.append(nxt)
            current = nxt

        finish_reach_limit = self._sample_reach_limit(rng)
        finish_candidates = [hold for hold in allowed_holds if hold[1] >= 30 and distance(hold, current) <= finish_reach_limit]
        if not finish_candidates:
            finish_candidates = [hold for hold in allowed_holds if hold[1] >= current[1] and distance(hold, current) <= 18]
        finishes = self._reachable_pair(rng, finish_candidates or [current], max_span=18)
        any_holds = [hold for hold in any_holds if hold not in finishes]

        hand_path = starts + any_holds + finishes
        climb = climb_dict("Random Setter", grade, angle, starts, any_holds, finishes, [])
        climb["holds"]["Feet"] = [list(hold) for hold in generated_feet_from_hands(climb, grade, rng)]
        hydrate_sequences(climb, options)
        return climb

    def _difficulty_holds(self, grade: str, rng: random.Random) -> list[tuple[int, int]]:
        v_grade = grade_to_v(grade)
        if v_grade is None:
            weights = {"small": 0.2, "medium": 0.4, "large": 0.4}
        elif v_grade <= 0:
            weights = {"small": 0.0, "medium": 0.0, "large": 1.0}
        elif v_grade >= 10:
            weights = {"small": 0.58, "medium": 0.42, "large": 0.0}
        else:
            hard = v_grade / 10
            weights = {"small": max(0.0, hard - 0.25), "medium": 0.25 + 0.45 * hard, "large": max(0.0, 1.0 - 0.9 * hard)}
        sampled = []
        for hold in self.valid_holds:
            bin_name = self.size_bins.get(hold, "medium")
            if rng.random() < weights.get(bin_name, 0.0):
                sampled.append(hold)
        return sampled or [hold for hold in self.valid_holds if self.size_bins.get(hold, "medium") in {"medium", "large"}] or self.valid_holds

    def _reachable_pair(self, rng: random.Random, candidates: list[tuple[int, int]], max_span: float) -> list[tuple[int, int]]:
        first = rng.choice(candidates)
        nearby = [hold for hold in candidates if hold != first and distance(hold, first) <= max_span]
        if nearby and rng.random() < 0.65:
            return sorted([first, rng.choice(nearby)])
        return [first]

    def _sample_reach_limit(self, rng: random.Random) -> float:
        return min(18.0, max(1.0, rng.gauss(9.0, 3.0)))

    def _weighted_reach_choice(
        self,
        rng: random.Random,
        candidates: list[tuple[int, int]],
        current: tuple[float, float],
        target_distance: float,
    ) -> tuple[int, int]:
        weights = [1 / (1 + abs(distance(candidate, current) - target_distance)) for candidate in candidates]
        return rng.choices(candidates, weights=weights, k=1)[0]


class EmpiricalSequentialSetter:
    name = "sequential"

    def __init__(self, records: list[dict[str, Any]] | None = None, valid_holds: set[tuple[int, int]] | None = None):
        self.records = records if records is not None else load_dataset()
        self.valid_holds = sorted(valid_holds if valid_holds is not None else valid_hold_positions())
        self.transitions: dict[tuple[int, int], Counter[tuple[int, int]]] = defaultdict(Counter)
        self.pair_transitions: dict[tuple[int | None, int | None, tuple[int, int], tuple[int, int], int, int], Counter[tuple[str, tuple[int, int]]]] = defaultdict(Counter)
        self.grade_angle_records: dict[tuple[int | None, int | None], list[dict[str, Any]]] = defaultdict(list)
        self.start_counts: Counter[tuple[int, int]] = Counter()
        self.finish_counts: Counter[tuple[int, int]] = Counter()
        self.foot_counts: Counter[tuple[int, int]] = Counter()
        self.train(self.records)

    def train(self, records: list[dict[str, Any]]) -> None:
        for record in records:
            holds = normalize_holds(record.get("holds", {}))
            sequence = record.get("hand_sequence") or record.get("sequence") or fast_training_sequence(holds)
            grade_bucket = grade_to_v(record.get("grade"))
            angle_bucket = angle_to_bucket(record.get("angle"))
            self.grade_angle_records[(grade_bucket, angle_bucket)].append(record)
            for start in holds["Start"]:
                self.start_counts[tuple(start)] += 1
            for finish in holds["Finish"]:
                self.finish_counts[tuple(finish)] += 1
            for foot in holds["Feet"]:
                self.foot_counts[tuple(foot)] += 1
            for current, nxt in zip(sequence, sequence[1:]):
                self.transitions[(current["x"], current["y"])][(nxt["x"], nxt["y"])] += 1
                key = (grade_bucket, angle_bucket, tuple(current["left"]), tuple(current["right"]), current.get("move", 0), len(sequence))
                self.pair_transitions[key][(nxt["hand"], (nxt["x"], nxt["y"]))] += 1

    def create(self, grade: str = "V5", angle: str = "50", seed: int | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        rng = random.Random(seed)
        options = options or {}
        target_hands = int(options.get("hand_count") or 8)
        records = self._neighbor_records(grade, angle)
        start_counts = Counter(tuple(hold) for record in records for hold in normalize_holds(record.get("holds", {}))["Start"]) or self.start_counts
        finish_counts = Counter(tuple(hold) for record in records for hold in normalize_holds(record.get("holds", {}))["Finish"]) or self.finish_counts
        start = weighted_choice(rng, start_counts) or rng.choice([h for h in self.valid_holds if h[1] <= 9])
        second_start = None
        nearby_starts = [hold for hold in start_counts if hold != start and distance(hold, start) <= 18]
        if nearby_starts and rng.random() < 0.55:
            second_start = weighted_choice(rng, Counter({hold: start_counts[hold] for hold in nearby_starts}))
        hands = [start] + ([second_start] if second_start else [])
        current = mean_point(hands)
        for _ in range(target_hands - 2):
            counter = self._conditioned_transition_counter(records, current)
            candidates = [
                hold for hold in (counter or {})
                if hold not in hands and generation_move_valid(current, hold) and hold[1] >= current[1] - 2
            ]
            if counter and candidates:
                nxt = weighted_choice(rng, Counter({
                    hold: max(0.01, counter[hold] / (1.0 + generation_move_penalty(current, hold)))
                    for hold in candidates
                }))
            else:
                pool = [hold for hold in self.valid_holds if hold not in hands and hold[1] >= current[1] - 1 and generation_move_valid(current, hold)]
                if not pool:
                    break
                nxt = weighted_generation_choice(rng, pool, current)
            if nxt not in hands:
                hands.append(nxt)
            current = nxt
        finish_candidates = [hold for hold in finish_counts if generation_move_valid(current, hold) and hold[1] >= current[1] - 1]
        finish = weighted_choice(rng, Counter({hold: finish_counts[hold] for hold in finish_candidates})) if finish_candidates else None
        if finish is None:
            finish_pool = [h for h in self.valid_holds if h[1] >= max(30, current[1]) and generation_move_valid(current, h)]
            finish = weighted_generation_choice(rng, finish_pool, current) if finish_pool else current
        if finish not in hands:
            hands.append(finish)
        climb = climb_dict("Sequential Setter", grade, angle, [hands[0]] + hands[1:2], hands[2:-1] if len(hands) > 2 else [], [hands[-1]], [])
        climb["holds"]["Feet"] = [list(hold) for hold in generated_feet_from_hands(climb, grade, rng)]
        hydrate_sequences(climb, options)
        return climb

    def _neighbor_records(self, grade: str, angle: str, min_records: int = 8) -> list[dict[str, Any]]:
        target_grade = grade_to_v(grade)
        target_angle = angle_to_bucket(angle)
        if target_grade is None:
            return self.records
        for grade_radius in range(0, 15):
            for angle_radius in (0, 10, 20, 40, 90):
                selected = [
                    record for record in self.records
                    if grade_to_v(record.get("grade")) is not None
                    and abs((grade_to_v(record.get("grade")) or 0) - target_grade) <= grade_radius
                    and (target_angle is None or angle_to_bucket(record.get("angle")) is None or abs((angle_to_bucket(record.get("angle")) or target_angle) - target_angle) <= angle_radius)
                ]
                if len(selected) >= min_records:
                    return selected
        return self.records

    def _conditioned_transition_counter(self, records: list[dict[str, Any]], current: tuple[float, float]) -> Counter[tuple[int, int]]:
        counter: Counter[tuple[int, int]] = Counter()
        for record in records:
            sequence = record.get("hand_sequence") or record.get("sequence") or fast_training_sequence(normalize_holds(record.get("holds", {})))
            for src, dst in zip(sequence, sequence[1:]):
                if distance((src["x"], src["y"]), current) <= 2.5:
                    counter[(dst["x"], dst["y"])] += 1
        return counter


class GraphSetter(EmpiricalSequentialSetter):
    name = "graph"

    def __init__(self, records: list[dict[str, Any]] | None = None, valid_holds: set[tuple[int, int]] | None = None):
        super().__init__(records, valid_holds)
        self._move_grade_summary: dict[str, Any] | None = None

    def create(self, grade: str = "V5", angle: str = "50", seed: int | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        rng = random.Random(seed)
        options = options or {}
        max_steps = int(options.get("hand_count") or 8)
        records = self._neighbor_records(grade, angle)
        start_counts = Counter(tuple(hold) for record in records for hold in normalize_holds(record.get("holds", {}))["Start"]) or self.start_counts
        finish_counts = Counter(tuple(hold) for record in records for hold in normalize_holds(record.get("holds", {}))["Finish"]) or self.finish_counts
        starts = [hold for hold, _count in start_counts.most_common(30)] or [h for h in self.valid_holds if h[1] <= 9]
        finishes = set(hold for hold, _count in finish_counts.most_common(40)) or set(h for h in self.valid_holds if h[1] >= 30)
        current = rng.choice(starts)
        hands = [current]
        for _ in range(max_steps - 1):
            if current in finishes and current[1] >= 30:
                break
            counter = self._conditioned_transition_counter(records, current)
            ranked = [
                hold for hold, _count in counter.most_common()
                if hold not in hands and hold[1] >= current[1] - 2 and generation_move_valid(current, hold)
            ]
            if not ranked:
                ranked = [hold for hold in self.valid_holds if hold not in hands and hold[1] >= current[1] - 1 and generation_move_valid(current, hold)]
            if not ranked:
                break
            current = weighted_generation_choice(rng, ranked[: min(24, len(ranked))], current)
            hands.append(current)
        if not any(hold in finishes for hold in hands):
            reachable_finishes = [hold for hold in finishes if generation_move_valid(hands[-1], hold) and hold[1] >= hands[-1][1] - 1]
            if reachable_finishes:
                finish = min(reachable_finishes, key=lambda h: generation_move_penalty(hands[-1], h))
                hands.append(finish)
        climb = climb_dict("Graph Setter", grade, angle, [hands[0]], hands[1:-1], [hands[-1]], [])
        climb["holds"]["Feet"] = [list(hold) for hold in generated_feet_from_hands(climb, grade, rng)]
        hydrate_sequences(climb, options)
        climb["move_grade_summary"] = self.graph_summary()
        return climb

    def graph_summary(self) -> dict[str, Any]:
        edges = sum(len(counter) for counter in self.transitions.values())
        return {"nodes": len(self.transitions), "pair_nodes": len(self.pair_transitions), "edges": edges}

    def move_grade_summary(self) -> dict[str, Any]:
        if self._move_grade_summary is not None:
            return self._move_grade_summary
        grades = build_move_grade_estimates(self.records)
        self._move_grade_summary = {"moves": len(grades), "mean_move_grade": sum(item["mean"] for item in grades.values()) / len(grades) if grades else 0}
        return self._move_grade_summary


class NeuralSetter:
    name = "neural"

    def __init__(self, records: list[dict[str, Any]] | None = None, checkpoint_path: Path | None = None):
        self.records = records if records is not None else load_dataset()
        self.checkpoint_path = checkpoint_path
        self.fallback = GraphSetter(self.records)

    def encode(self, climb: dict[str, Any]) -> list[list[list[int]]]:
        holds = normalize_holds(climb.get("holds", {}))
        channels = []
        for hold_type in ("Start", "Any", "Finish", "Feet"):
            grid = [[0 for _x in range(GRID_COLUMNS)] for _y in range(GRID_ROWS)]
            for x, y in holds[hold_type]:
                grid[y - 1][x - 1] = 1
            channels.append(grid)
        return channels

    def decode(self, tensor: list[list[list[float]]], threshold: float = 0.5) -> dict[str, list[list[int]]]:
        holds = {"Start": [], "Any": [], "Finish": [], "Feet": []}
        for channel, hold_type in enumerate(("Start", "Any", "Finish", "Feet")):
            for y, row in enumerate(tensor[channel], start=1):
                for x, value in enumerate(row, start=1):
                    if value >= threshold:
                        holds[hold_type].append([x, y])
        return holds

    def train(self, output_path: Path, epochs: int | None = None, **overrides: Any) -> dict[str, Any]:
        try:
            import torch
            from torch import nn
            from torch.utils.data import DataLoader, TensorDataset
        except Exception as exc:  # pragma: no cover - depends on optional dependency
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps({"status": "skipped", "reason": str(exc)}, indent=2), encoding="utf-8")
            return {"status": "skipped", "reason": str(exc)}
        training_config = dict(load_config().get("neural_training") or {})
        training_config.update({key: value for key, value in overrides.items() if value is not None})
        epochs = int(epochs if epochs is not None else training_config.get("epochs", 35))
        training_config["epochs"] = epochs
        batch_size = int(training_config.get("batch_size", 512))
        learning_rate = float(training_config.get("learning_rate", 3e-4))
        weight_decay = float(training_config.get("weight_decay", 1e-4))
        hidden_dim = int(training_config.get("hidden_dim", 768))
        dropout = float(training_config.get("dropout", 0.15))
        mask_probability = float(training_config.get("mask_probability", 0.25))
        grade_loss_weight = float(training_config.get("grade_loss_weight", 0.75))
        validation_fraction = float(training_config.get("validation_fraction", 0.15))
        training_pairs = [
            (torch.tensor(self.encode(record), dtype=torch.float32).flatten(), grade_to_v(record.get("grade")))
            for record in self.records
            if record.get("holds") and grade_to_v(record.get("grade")) is not None
        ]
        tensors = [pair[0] for pair in training_pairs]
        if not tensors:
            return {"status": "skipped", "reason": "no training records"}
        data = torch.stack(tensors)
        grades = torch.tensor([float(pair[1]) / 14.0 for pair in training_pairs], dtype=torch.float32).view(-1, 1)
        permutation = torch.randperm(len(data))
        data = data[permutation]
        grades = grades[permutation]
        split = max(1, int((1.0 - validation_fraction) * len(data)))
        train_data, val_data = data[:split], data[split:] if split < len(data) else data[:1]
        train_grades, val_grades = grades[:split], grades[split:] if split < len(grades) else grades[:1]
        train_loader = DataLoader(TensorDataset(train_data, train_grades), batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(TensorDataset(val_data, val_grades), batch_size=batch_size)

        class MaskedSetterNet(nn.Module):
            def __init__(self, input_dim: int):
                super().__init__()
                self.encoder = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout))
                self.reconstruct = nn.Linear(hidden_dim, input_dim)
                self.grade = nn.Sequential(nn.Linear(hidden_dim, hidden_dim // 2), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden_dim // 2, 1), nn.Sigmoid())

            def forward(self, x):
                latent = self.encoder(x)
                return self.reconstruct(latent), self.grade(latent)

        model = MaskedSetterNet(data.shape[1])
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
        positives = train_data.sum()
        negatives = train_data.numel() - positives
        pos_weight = (negatives / positives.clamp_min(1)).clamp(1, 200)
        reconstruction_loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        grade_loss_fn = nn.SmoothL1Loss()
        history: list[dict[str, float]] = []
        for epoch in range(epochs):
            model.train()
            epoch_loss = 0.0
            epoch_reconstruction = 0.0
            epoch_grade = 0.0
            batches = 0
            for batch_x, batch_grade in train_loader:
                mask = (torch.rand_like(batch_x) > mask_probability).float()
                reconstruction_logits, grade_pred = model(batch_x * mask)
                reconstruction_loss = reconstruction_loss_fn(reconstruction_logits, batch_x)
                grade_loss = grade_loss_fn(grade_pred, batch_grade)
                loss = reconstruction_loss + grade_loss_weight * grade_loss
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                epoch_loss += float(loss.detach())
                epoch_reconstruction += float(reconstruction_loss.detach())
                epoch_grade += float(grade_loss.detach())
                batches += 1
            model.eval()
            with torch.no_grad():
                val_errors = []
                val_reconstruction_losses = []
                for batch_x, batch_grade in val_loader:
                    reconstruction_logits, grade_pred = model(batch_x)
                    val_reconstruction_losses.append(float(reconstruction_loss_fn(reconstruction_logits, batch_x).detach()))
                    val_errors.extend((grade_pred.view(-1) * 14 - batch_grade.view(-1) * 14).tolist())
            mean_val_abs = sum(abs(error) for error in val_errors) / len(val_errors) if val_errors else 0.0
            history.append({
                "epoch": float(epoch + 1),
                "loss": epoch_loss / max(1, batches),
                "reconstruction_loss": epoch_reconstruction / max(1, batches),
                "grade_loss": epoch_grade / max(1, batches),
                "val_reconstruction_loss": sum(val_reconstruction_losses) / len(val_reconstruction_losses) if val_reconstruction_losses else 0.0,
                "val_average_grade_deviation": mean_val_abs,
            })
        with torch.no_grad():
            predictions = []
            truths = []
            val_reconstruction_losses = []
            for batch_x, batch_grade in val_loader:
                val_reconstruction, val_pred = model(batch_x)
                val_reconstruction_losses.append(float(reconstruction_loss_fn(val_reconstruction, batch_x).detach()))
                predictions.extend((val_pred.view(-1) * 14).tolist())
                truths.extend((batch_grade.view(-1) * 14).tolist())
            prediction = torch.tensor(predictions).clamp(0, 14)
            truth = torch.tensor(truths)
            errors = prediction - truth
            grade_metrics = {
                "validation_count": int(len(truth)),
                "average_grade_deviation": float(errors.abs().mean()),
                "accuracy": float((errors.abs() < 0.5).float().mean()),
                "within_1_grade_accuracy": float((errors.abs() <= 1).float().mean()),
                "within_2_grade_accuracy": float((errors.abs() <= 2).float().mean()),
                "within_3_grade_accuracy": float((errors.abs() <= 3).float().mean()),
                "average_bias": float(errors.mean()),
                "prediction_std": float(prediction.std(unbiased=False)),
                "validation_reconstruction_loss": sum(val_reconstruction_losses) / len(val_reconstruction_losses) if val_reconstruction_losses else 0.0,
                "predicted": [float(value) for value in prediction],
                "actual": [float(value) for value in truth],
            }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"model_state": model.state_dict(), "history": history, "grade_metrics": grade_metrics, "training_config": training_config}, output_path)
        return {"status": "trained", "history": history, "checkpoint": str(output_path), "grade_metrics": grade_metrics, "training_config": training_config}

    def create(self, grade: str = "V5", angle: str = "50", seed: int | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        climb = self.fallback.create(grade=grade, angle=angle, seed=seed, options=options)
        climb["name"] = "Neural Setter"
        status_path = ROOT / "outputs" / "models" / "neural_status.json"
        checkpoint_exists = self.checkpoint_path is not None and self.checkpoint_path.exists()
        status: dict[str, Any] = {}
        if status_path.exists():
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                status = {}
        climb["diagnostics"] = {
            "model": "masked-autoencoder",
            "checkpoint": str(self.checkpoint_path) if self.checkpoint_path else None,
            "checkpoint_exists": checkpoint_exists,
            "trained_status": status.get("status"),
            "fallback": True,
            "note": "Checkpoint is loaded as the final saved neural artifact; generation still uses graph decoding fallback until autoregressive neural decoding is trusted.",
        }
        return climb


def load_saved_setter(name: str, fallback: Any) -> Any:
    path = ROOT / "outputs" / "models" / f"{name}_setter.pkl"
    if not path.exists():
        return fallback
    try:
        with path.open("rb") as file:
            return pickle.load(file)
    except Exception:
        return fallback


def generate_climb(setter: str, grade: str = "V5", angle: str = "50", seed: int | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
    records = load_dataset()
    setter_key = setter.lower().replace("_", "-")
    model: RandomSetter | EmpiricalSequentialSetter | GraphSetter | NeuralSetter
    if setter_key in {"random", "random-setter"}:
        model = load_saved_setter("random", RandomSetter(records))
        climb = model.create(grade, angle, seed, options)
    elif setter_key in {"sequential", "sequential-setter"}:
        model = load_saved_setter("sequential", EmpiricalSequentialSetter(records))
        climb = model.create(grade, angle, seed, options)
    elif setter_key in {"graph", "graph-setter"}:
        model = load_saved_setter("graph", GraphSetter(records))
        climb = model.create(grade, angle, seed, options)
    elif setter_key in {"neural", "neural-network", "neural-network-setter"}:
        model = NeuralSetter(records, Path("outputs/models/neural_setter.pt"))
        climb = model.create(grade, angle, seed, options)
    else:
        raise ValueError(f"Unknown setter: {setter}")
    validated = validate_climb(climb)
    matching_allowed = bool(climb.get("matching_allowed", True))
    validated["matching_allowed"] = matching_allowed
    validated["sequence"] = climb.get("sequence") or estimate_sequence(validated["holds"], matching_allowed=matching_allowed, grade=validated.get("grade"))
    validated["hand_sequence"] = climb.get("hand_sequence") or validated["sequence"]
    validated["foot_sequence"] = climb.get("foot_sequence") or estimate_foot_sequence(validated["holds"], validated["hand_sequence"])
    validated["sequence_metrics"] = climb.get("sequence_metrics") or sequence_metrics(validated["hand_sequence"], validated["foot_sequence"])
    validated["setter"] = setter
    if climb.get("diagnostics"):
        validated["diagnostics"] = climb["diagnostics"]
    if climb.get("move_grade_summary"):
        validated["move_grade_summary"] = climb["move_grade_summary"]
    validated["selection_notes"] = selection_notes(setter, validated)
    validated["selection_explanation"] = selection_explanation(setter_key, validated, model)
    return validated


def climb_dict(
    name: str,
    grade: str,
    angle: str,
    starts: list[tuple[int, int]],
    any_holds: list[tuple[int, int]],
    finishes: list[tuple[int, int]],
    feet: list[tuple[int, int]],
) -> dict[str, Any]:
    climb = {
        "name": name,
        "grade": grade,
        "angle": angle,
        "holds": {
            "Start": [list(hold) for hold in starts[:2]],
            "Any": [list(hold) for hold in any_holds],
            "Finish": [list(hold) for hold in finishes[:2]],
            "Feet": [list(hold) for hold in feet],
        },
    }
    hydrate_sequences(climb, {})
    return climb


def hydrate_sequences(climb: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
    options = options or {}
    hand_preference = int(options.get("hand_usage_preference") or options.get("hold_usage_preference") or 4)
    foot_preference = int(options.get("foot_usage_preference") or 3)
    height_units = float(options.get("climber_height_units") or 22)
    hand_sequence = estimate_hand_sequence(
        climb["holds"],
        hand_preference,
        matching_allowed=bool(climb.get("matching_allowed", True)),
        grade=climb.get("grade"),
    )
    foot_sequence = estimate_foot_sequence(climb["holds"], hand_sequence, height_units, foot_preference)
    climb["sequence"] = hand_sequence
    climb["hand_sequence"] = hand_sequence
    climb["foot_sequence"] = foot_sequence
    climb["sequence_metrics"] = sequence_metrics(hand_sequence, foot_sequence)
    return climb


def ordered_hand_sequence(
    starts: list[tuple[int, int]],
    any_holds: list[tuple[int, int]],
    finishes: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    sequence: list[dict[str, Any]] = []
    left_x = starts[0][0] if starts else GRID_COLUMNS / 2 - 1
    right_x = starts[-1][0] if len(starts) > 1 else GRID_COLUMNS / 2 + 1
    for index, (x, y, hold_type) in enumerate(
        [(x, y, "Start") for x, y in starts]
        + [(x, y, "Any") for x, y in any_holds]
        + [(x, y, "Finish") for x, y in finishes]
    ):
        if hold_type == "Start" and len(starts) > 1:
            hand = "left" if index == 0 else "right"
        elif hold_type == "Finish" and sequence and sequence[-1]["type"] == "Finish":
            hand = "right" if sequence[-1]["hand"] == "left" else "left"
        else:
            hand = "left" if abs(x - left_x) <= abs(x - right_x) else "right"
        if hand == "left":
            left_x = x
        else:
            right_x = x
        sequence.append({"x": x, "y": y, "type": hold_type, "hand": hand})
    return sequence


def weighted_choice(rng: random.Random, counter: Counter[tuple[int, int]]) -> tuple[int, int] | None:
    if not counter:
        return None
    total = sum(counter.values())
    draw = rng.uniform(0, total)
    upto = 0.0
    for item, weight in counter.items():
        upto += weight
        if upto >= draw:
            return item
    return next(iter(counter))


def angle_to_bucket(angle: Any) -> int | None:
    try:
        return int(round(float(str(angle).replace("degrees", "").strip()) / 5) * 5)
    except (TypeError, ValueError):
        return None


def fast_training_sequence(holds: dict[str, list[tuple[int, int]]]) -> list[dict[str, Any]]:
    ordered: list[tuple[int, int, str]] = []
    for hold_type in ("Start", "Any", "Finish"):
        ordered.extend((int(x), int(y), hold_type) for x, y in holds.get(hold_type, []))
    ordered.sort(key=lambda hold: (hold[1], hold[0], {"Start": 0, "Any": 1, "Finish": 2}.get(hold[2], 9)))
    sequence: list[dict[str, Any]] = []
    left = ordered[0][:2] if ordered else (18, 1)
    right = ordered[1][:2] if len(ordered) > 1 and ordered[1][2] == "Start" else left
    last_hand = "right"
    for index, (x, y, hold_type) in enumerate(ordered):
        if index == 0:
            hand = "left"
            left = (x, y)
        elif hold_type == "Start" and index == 1:
            hand = "right"
            right = (x, y)
        else:
            hand = "left" if last_hand == "right" else "right"
            if hand == "left":
                left = (x, y)
            else:
                right = (x, y)
        last_hand = hand
        sequence.append({
            "x": x,
            "y": y,
            "type": hold_type,
            "hand": hand,
            "left": left,
            "right": right,
            "move": max(0, index),
        })
    return sequence


def build_move_grade_estimates(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    observations: dict[tuple[tuple[int, int], tuple[int, int], tuple[int, int], str], list[float]] = defaultdict(list)
    for record in records:
        v_grade = grade_to_v(record.get("grade"))
        if v_grade is None:
            continue
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
            hand = nxt["hand"]
            stationary = tuple(current["right"] if hand == "left" else current["left"])
            start = (current["x"], current["y"])
            finish = (nxt["x"], nxt["y"])
            observations[(stationary, start, finish, hand)].append(float(v_grade))
    grouped: dict[tuple[str, tuple[int, int], tuple[int, int]], list[tuple[tuple[int, int], list[float]]]] = defaultdict(list)
    for (stationary, start, finish, hand), values in observations.items():
        grouped[(hand, stationary, finish)].append((start, values))
    estimates: dict[str, dict[str, float]] = {}
    for (hand, stationary, finish), start_values in grouped.items():
        include_close = len(start_values) <= 250
        for start, values in start_values:
            weighted: list[tuple[float, float]] = [(1.0, grade) for grade in values]
            if include_close:
                for other_start, other_values in start_values:
                    if other_start == start:
                        continue
                    delta = hold_distance(start, other_start)
                    if delta < 30:
                        match_rate = max(1 / 30, 1 - delta / 30)
                        weighted.extend((match_rate, grade) for grade in other_values)
            denom = sum(weight for weight, _grade in weighted) or 1.0
            mean = sum(weight * grade for weight, grade in weighted) / denom
            key = f"{hand}:{stationary[0]}:{stationary[1]}:{start[0]}:{start[1]}->{finish[0]}:{finish[1]}"
            estimates[key] = {"mean": min(14.0, max(0.0, mean)), "std": 3.0, "samples": float(len(values)), "weighted_samples": denom}
    return estimates


def mean_point(points: list[tuple[int, int]]) -> tuple[float, float]:
    return (sum(point[0] for point in points) / len(points), sum(point[1] for point in points) / len(points))


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def generation_move_valid(a: tuple[float, float], b: tuple[float, float]) -> bool:
    dx = abs(float(b[0]) - float(a[0]))
    dy = float(b[1]) - float(a[1])
    return distance(a, b) <= 20.0 and dx <= 18.0 and dy >= -4.0


def generation_move_penalty(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = abs(float(b[0]) - float(a[0]))
    dy = float(b[1]) - float(a[1])
    dist = distance(a, b)
    penalty = abs(dist - 9.0) * 0.6
    if dist > 14.0:
        penalty += (dist - 14.0) * 3.0
    if dx > 12.0:
        penalty += (dx - 12.0) * 4.5
    if dy < 0:
        penalty += abs(dy) * 12.0
    elif dy < 2:
        penalty += (2.0 - dy) * 1.5
    return penalty


def weighted_generation_choice(rng: random.Random, candidates: list[tuple[int, int]], current: tuple[float, float]) -> tuple[int, int]:
    weights = [1.0 / (1.0 + generation_move_penalty(current, candidate)) for candidate in candidates]
    return rng.choices(candidates, weights=weights, k=1)[0]


def nearest_distance(hold: tuple[int, int], others: list[tuple[int, int]]) -> float:
    if not others:
        return 0.0
    return min(distance(hold, other) for other in others)


def generated_feet_quota(grade: str | None, move_number: int = 0, rng: random.Random | None = None) -> int:
    v_grade = grade_to_v(grade)
    if move_number == 0:
        if v_grade is None or v_grade <= 5:
            return 3
        if v_grade <= 9:
            return 2
        return 1 + int((rng or random).random() < 0.35)
    if v_grade is None or v_grade <= 5:
        return 2
    if v_grade <= 9:
        return 1 + int((rng or random).random() < 0.5)
    return 1


def generated_feet_from_hands(climb: dict[str, Any], grade: str | None = None, rng: random.Random | None = None) -> list[tuple[int, int]]:
    rng = rng or random.Random()
    holds = normalize_holds(climb.get("holds", {}))
    hand_sequence = estimate_hand_sequence(
        holds,
        matching_allowed=bool(climb.get("matching_allowed", True)),
        grade=climb.get("grade") or grade,
    )
    all_valid = sorted(valid_hold_positions())
    hand_holds = {tuple(hold) for hold_type in ("Start", "Any", "Finish") for hold in holds[hold_type]}
    selected: list[tuple[int, int]] = []
    for move in hand_sequence:
        left_hand = tuple(move["left"])
        right_hand = tuple(move["right"])
        quota = generated_feet_quota(grade, int(move.get("move") or 0), rng)
        existing = set(selected) | hand_holds
        already_set = [
            hold for hold in existing
            if hold not in {left_hand, right_hand}
            and foot_candidate_penalty(holds, left_hand, right_hand, hold) == 0
        ]
        needed = max(0, quota - len(already_set))
        while needed > 0:
            candidates = [
                hold for hold in all_valid
                if hold not in selected
                and hold not in hand_holds
                and hold not in {left_hand, right_hand}
                and foot_candidate_penalty(holds, left_hand, right_hand, hold) == 0
            ]
            if not candidates:
                break
            choice = weighted_foot_choice(rng, candidates, left_hand, right_hand, grade)
            selected.append(choice)
            needed -= 1
    return sorted(selected, key=lambda hold: (hold[1], hold[0]))


def weighted_foot_choice(
    rng: random.Random,
    candidates: list[tuple[int, int]],
    left_hand: tuple[int, int],
    right_hand: tuple[int, int],
    grade: str | None = None,
) -> tuple[int, int]:
    v_grade = grade_to_v(grade)
    hardness = min(1.0, max(0.0, (v_grade if v_grade is not None else 7) / 14.0))
    midpoint_x = (left_hand[0] + right_hand[0]) / 2
    midpoint_y = (left_hand[1] + right_hand[1]) / 2
    preferred_drop = rng.gauss(12.5, 1.8 + 3.2 * hardness)
    preferred_x = rng.gauss(midpoint_x, 3.5 + 8.0 * hardness)
    sigma_x = 4.0 + 11.0 * hardness
    sigma_y = 2.8 + 7.0 * hardness
    uniform_mix = 0.08 + 0.72 * hardness
    weights = []
    for hold in candidates:
        horizontal_error = abs(hold[0] - preferred_x)
        drop_error = abs((midpoint_y - hold[1]) - preferred_drop)
        centered_bonus = 1.35 if abs(hold[0] - midpoint_x) <= 10 else 0.7
        low_bonus = 1.3 if 10 <= midpoint_y - hold[1] <= 15 else 0.75
        normal_weight = (
            pow(2.718281828, -0.5 * ((horizontal_error / sigma_x) ** 2 + (drop_error / sigma_y) ** 2))
            * centered_bonus
            * low_bonus
        )
        weights.append(uniform_mix + (1.0 - uniform_mix) * normal_weight)
    return rng.choices(candidates, weights=weights, k=1)[0]


def selection_notes(setter: str, climb: dict[str, Any]) -> list[str]:
    sequence = climb.get("sequence") or []
    if setter in {"random", "random-setter"}:
        return [
            "Random setter: sampled valid physical holds with start in low zone.",
            "Each hand move uses a clipped normal reach draw centered at 9 hold units and capped to [1, 18].",
            "After the hand sequence is known, feet are sampled from non-penalized physical holds with grade-dependent quotas and a low-centered preference.",
            "Finish is selected from high or upward reachable candidates.",
        ]
    if setter in {"sequential", "sequential-setter"}:
        return [
            "Sequential setter: chose start and finish from empirical corpus frequencies.",
            "Middle hands are sampled from heuristic nearest-neighbor transition distributions.",
            f"Generated {len(sequence)} sequenced hand contacts from training-set transition counts, then added only the foot holds needed to satisfy grade-dependent beta quotas.",
        ]
    if setter in {"graph", "graph-setter"}:
        return [
            "Graph setter: holds are nodes and heuristic hand moves are weighted directed edges.",
            "Generated a constrained weighted walk from a start-zone node toward a finish-zone node.",
            "Feet are sampled after the hand subgraph is generated from non-penalized physical holds, not from corpus foot frequency.",
        ]
    return [
        "Neural setter: uses the masked-autoencoder interface.",
        "If no decoded checkpoint sample is available, it falls back to the graph setter while preserving neural diagnostics.",
        "Generated climb remains coordinate-backed and editable.",
    ]


def selection_explanation(
    setter: str,
    climb: dict[str, Any],
    model: RandomSetter | EmpiricalSequentialSetter | GraphSetter | NeuralSetter,
) -> str:
    sequence = [(move["x"], move["y"], move["type"]) for move in climb.get("sequence", [])]
    holds = normalize_holds(climb.get("holds", {}))
    if setter in {"sequential", "sequential-setter"} and isinstance(model, EmpiricalSequentialSetter):
        model_description = (
            "Model description: empirical sequential setter samples a start hold from corpus start frequencies, "
            "then repeatedly samples the next hand from the outgoing transition Counter for the current hold after "
            "filtering to upward/nearby candidates, and finally samples the minimum needed non-penalized feet from a grade-dependent low-centered distribution."
        )
        details = sequential_details(sequence, holds, model)
    elif setter in {"graph", "graph-setter"} and isinstance(model, GraphSetter):
        summary = model.graph_summary()
        model_description = (
            f"Model description: graph setter represents holds as {summary['nodes']} observed nodes and "
            f"{summary['edges']} weighted directed transition edges, then performs a constrained weighted walk "
            "from a frequent start-zone node toward a frequent finish-zone node before adding grade-dependent low-centered non-penalized feet."
        )
        details = graph_details(sequence, holds, model)
    elif setter in {"neural", "neural-network", "neural-network-setter"} and isinstance(model, NeuralSetter):
        channel_counts = {hold_type: len(points) for hold_type, points in holds.items()}
        fallback = bool(climb.get("diagnostics", {}).get("fallback"))
        model_description = (
            "Model description: neural setter uses a four-channel masked-autoencoder representation "
            "(Start, Any, Finish, Feet) over the coordinate grid and currently emits a coordinate-backed graph "
            f"fallback when checkpoint decoding is unavailable or untrusted; fallback={fallback}, "
            f"channel_counts={channel_counts}."
        )
        details = graph_details(sequence, holds, model.fallback)
    else:
        model_description = (
            "Model description: random setter samples only detected physical Kilter holds, constrains starts, "
            "hand moves, and finish candidates by Euclidean hold-unit reach windows where next-hand reach is drawn from "
            "a normal distribution centered at 9 and clipped to [1, 18], then samples only needed feet from non-penalized low-centered positions."
        )
        details = random_details(sequence, holds)
    return f"{model_description}\nHold-By-Hold Explanation:\n" + "\n".join(details)


def sequential_details(
    sequence: list[tuple[int, int, str]],
    holds: dict[str, list[tuple[int, int]]],
    model: EmpiricalSequentialSetter,
) -> list[str]:
    details: list[str] = []
    start_total = sum(model.start_counts.values()) or 1
    finish_total = sum(model.finish_counts.values()) or 1
    for index, (x, y, hold_type) in enumerate(sequence, start=1):
        hold = (x, y)
        if index == 1:
            probability = model.start_counts[hold] / start_total
            details.append(f"{index}. {hold_type} {hold}: start_count={model.start_counts[hold]}, total_starts={start_total}, p={probability:.4f}.")
        else:
            prev = (sequence[index - 2][0], sequence[index - 2][1])
            counter = model.transitions.get(prev, Counter())
            denom = sum(counter.values()) or 1
            probability = counter[hold] / denom
            details.append(
                f"{index}. {hold_type} {hold}: transition_from={prev}, edge_count={counter[hold]}, outgoing_total={denom}, p={probability:.4f}."
            )
    for index, foot in enumerate(holds["Feet"], start=1):
        foot_key = tuple(foot)
        details.append(f"Foot {index}. {foot_key}: sampled after sequencing from non-penalized physical footholds; preferred 10-15 units below and within 10 horizontal units of the active hand midpoint, with flatter sampling for harder grades.")
    if holds["Finish"]:
        finish = tuple(holds["Finish"][-1])
        details.append(
            f"Finish prior {finish}: finish_count={model.finish_counts[finish]}, total_finishes={finish_total}, p={model.finish_counts[finish] / finish_total:.4f}."
        )
    return details


def graph_details(
    sequence: list[tuple[int, int, str]],
    holds: dict[str, list[tuple[int, int]]],
    model: GraphSetter,
) -> list[str]:
    details: list[str] = []
    start_pool = model.start_counts.most_common(30)
    start_total = sum(count for _hold, count in start_pool) or 1
    for index, (x, y, hold_type) in enumerate(sequence, start=1):
        hold = (x, y)
        if index == 1:
            details.append(f"{index}. {hold_type} {hold}: top30_start_count={model.start_counts[hold]}, top30_start_total={start_total}, p={model.start_counts[hold] / start_total:.4f}.")
        else:
            prev = (sequence[index - 2][0], sequence[index - 2][1])
            counter = model.transitions.get(prev, Counter())
            ranked = [candidate for candidate, _count in counter.most_common() if candidate[1] >= prev[1] - 3]
            ranked = ranked[: min(12, len(ranked))]
            denom = sum(counter[candidate] for candidate in ranked) or 1
            probability = counter[hold] / denom if hold in ranked else 0.0
            details.append(
                f"{index}. {hold_type} {hold}: graph_edge_from={prev}, edge_count={counter[hold]}, ranked_candidate_count={len(ranked)}, ranked_total={denom}, p={probability:.4f}."
            )
    for index, foot in enumerate(holds["Feet"], start=1):
        foot_key = tuple(foot)
        details.append(f"Foot {index}. {foot_key}: sampled after graph hand path generation from non-penalized physical footholds with grade-dependent low-centered weighting.")
    return details


def random_details(sequence: list[tuple[int, int, str]], holds: dict[str, list[tuple[int, int]]]) -> list[str]:
    details: list[str] = []
    for index, (x, y, hold_type) in enumerate(sequence, start=1):
        if index == 1:
            details.append(f"{index}. {hold_type} {(x, y)}: sampled from low-zone valid-hold candidates.")
        else:
            prev = (sequence[index - 2][0], sequence[index - 2][1])
            details.append(f"{index}. {hold_type} {(x, y)}: sampled from valid holds with clipped-normal target reach centered at 9 and cap 18 from {prev}; actual_distance={distance((x, y), prev):.2f}.")
    hand_path = [(x, y) for x, y, _hold_type in sequence]
    for index, foot in enumerate(holds["Feet"], start=1):
        foot_key = tuple(foot)
        details.append(f"Foot {index}. {foot_key}: sampled from non-penalized physical foot candidates after hand sequencing; nearest_hand_path_distance={nearest_distance(foot_key, hand_path):.2f}.")
    return details
