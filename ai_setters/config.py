"""Small project configuration loader."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "ai_setter_config.json"
DEFAULT_CONFIG = {
    "data_source": "kilter_db",
    "screenshots_dir": "kilter_climbs_data/app_screenshots_dataset",
    "kilter_db_path": "kilter_climbs_data/oct2025-app-climbs.db",
    "kilter_product_size_id": 10,
    "kilter_layout_id": 1,
    "model_training_limit": 3000,
    "webapp_climb_limit": 50000,
    "full_training_limit": None,
    "neural_training": {
        "epochs": 35,
        "batch_size": 512,
        "learning_rate": 3e-4,
        "weight_decay": 1e-4,
        "hidden_dim": 768,
        "dropout": 0.15,
        "mask_probability": 0.25,
        "grade_loss_weight": 0.75,
        "validation_fraction": 0.15,
    },
}


def load_config() -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            config.update(loaded)
    if os.environ.get("AI_SETTER_DATA_SOURCE"):
        config["data_source"] = os.environ["AI_SETTER_DATA_SOURCE"]
    return config


def resolve_config_path(key: str) -> Path:
    value = load_config()[key]
    path = Path(value)
    return path if path.is_absolute() else ROOT / path
