"""Refresh generated climb PNGs and heuristic sequence review artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .dataset import ROOT, grade_to_v
from .kilter_db import load_db_records
from .preprocess_and_train import generate_grade_set, select_sequence_review_climbs, write_sequence_review_set


DEFAULT_CSV = ROOT / "outputs" / "data" / "all_kilter_climbs.csv"


def load_records_from_csv(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            holds = json.loads(row.get("holds") or "{}")
            record = dict(row)
            record["holds"] = holds
            record["v_grade"] = int(row["v_grade"]) if str(row.get("v_grade") or "").isdigit() else grade_to_v(row.get("grade"))
            record["ascensionist_count"] = int(float(row.get("ascensionist_count") or 0))
            record["quality_average"] = float(row.get("quality_average") or 0)
            record["stars"] = record["quality_average"]
            record["matching_allowed"] = str(row.get("matching_allowed", "True")).lower() in {"1", "true", "yes"}
            records.append(record)
            if limit and len(records) >= limit:
                break
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Optional record limit for faster generated-set training.")
    parser.add_argument("--setter-limit", type=int, default=50000, help="Record cap for fitting generated-climb setters.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Existing exported Kilter CSV to load.")
    parser.add_argument("--db", action="store_true", help="Load from the SQLite DB instead of the exported CSV.")
    args = parser.parse_args()

    if args.db or not args.csv.exists():
        print("Loading records from Kilter DB.", flush=True)
        records = load_db_records(limit=args.limit, include_sequences=False)
    else:
        print(f"Loading records from {args.csv}.", flush=True)
        records = load_records_from_csv(args.csv, limit=args.limit)

    setter_records = records[: args.setter_limit] if args.setter_limit else records
    print(f"Refreshing generated climb PNGs from {len(setter_records)} setter-training records.", flush=True)
    generated = generate_grade_set(setter_records, ROOT / "outputs" / "generated_climbs")
    print(f"Generated {len(generated)} climb PNGs.", flush=True)

    print("Refreshing heuristic 100 sequence review.", flush=True)
    selected = select_sequence_review_climbs(records)
    write_sequence_review_set(selected, ROOT / "outputs" / "sequence_review" / "heuristic_100")
    print(f"Refreshed {len(selected)} heuristic sequence review climbs.", flush=True)


if __name__ == "__main__":
    main()
