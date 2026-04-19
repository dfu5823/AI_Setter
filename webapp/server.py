"""Dependency-light local web app server for AI Setter."""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_setters.climb_core import ClimbValidationError, estimate_foot_sequence, estimate_hand_sequence, estimate_sequence, sequence_metrics, validate_climb
from ai_setters.config import load_config, resolve_config_path
from ai_setters.dataset import build_dataset, dataset_summary, load_dataset, local_heatmap

STATIC_DIR = ROOT / "webapp" / "static"
KILTER_DATA_DIR = ROOT / "kilter_climbs_data"
SCREENSHOTS_DATA_DIR = resolve_config_path("screenshots_dir")
KILTER_OUTPUT_DIR = ROOT / "kilter_climbs_output"
OUTPUTS_DIR = ROOT / "outputs"
ALL_KILTER_CLIMBS_CSV = OUTPUTS_DIR / "data" / "all_kilter_climbs.csv"
SAVED_CLIMBS_PATH = ROOT / "webapp" / "data" / "saved_climbs.json"
SOURCE_METADATA_PATH = ROOT / "webapp" / "data" / "source_climbs_metadata.json"


def _query_int(query: dict[str, list[str]], key: str, default: int | None = None) -> int | None:
    try:
        value = query.get(key, [None])[0]
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def list_source_climbs(query: dict[str, list[str]] | None = None) -> tuple[list[dict], int]:
    query = query or {}
    config = load_config()
    source_filter = query.get("source", ["all"])[0]
    if source_filter == "user":
        return [], 0
    if config.get("data_source") == "kilter_db":
        if ALL_KILTER_CLIMBS_CSV.exists():
            return list_source_climbs_from_csv(query)

        from ai_setters.kilter_db import load_db_records

        angle = _query_int(query, "angle")
        min_grade = _query_int(query, "minGrade", 0)
        max_grade = _query_int(query, "maxGrade", 16)
        sort = query.get("sort", ["name"])[0]
        name_filter = (query.get("name", [""])[0] or "").strip().lower()
        source_limit = _query_int(query, "limit", 400)
        # The config cap is only a fallback for unfiltered startup calls. Search requests
        # must scan enough records to include the selected angle, especially the default 40.
        records = load_db_records(limit=None if angle is not None else int(config.get("webapp_climb_limit") or 50000), include_sequences=False)
        filtered_records = [
            record for record in records
            if (angle is None or int(record.get("angle") or -999) == angle)
            and (min_grade is None or int(record.get("v_grade") if record.get("v_grade") is not None else 99) >= min_grade)
            and (max_grade is None or int(record.get("v_grade") if record.get("v_grade") is not None else 99) <= max_grade)
            and (not name_filter or name_filter in str(record.get("name") or "").lower())
        ]
        filtered_records.sort(key=lambda record: _server_sort_key(record, sort))
        if sort in {"gradeDesc", "ascentsDesc", "starsDesc"}:
            filtered_records.reverse()
        records = filtered_records[:source_limit]
        climbs = []
        for index, record in enumerate(records):
            climb_id = str(record.get("uuid") or record.get("id") or index)
            angle = record.get("angle")
            climbs.append({
                "id": f"{climb_id}:{record.get('angle', '')}",
                "uuid": record.get("uuid") or climb_id,
                "name": record.get("name") or climb_id,
                "grade": record.get("grade") or "Unknown",
                "v_grade": record.get("v_grade"),
                "angle": angle if angle is not None else "Unknown",
                "stars": record.get("stars", "Unknown"),
                "source": "kilter_db",
                "ascensionist_count": record.get("ascensionist_count"),
                "setter_username": record.get("setter_username"),
                "matching_allowed": record.get("matching_allowed", True),
                "holds": record.get("holds", {}),
            })
        return climbs, len(filtered_records)

    metadata = load_source_metadata()
    screenshots_dir = SCREENSHOTS_DATA_DIR if SCREENSHOTS_DATA_DIR.exists() else KILTER_DATA_DIR
    climbs = [
        {
            "id": image_path.stem,
            "name": metadata.get(image_path.name, {}).get("name") or image_path.stem.replace("_", " "),
            "grade": metadata.get(image_path.name, {}).get("grade") or "Unknown",
            "angle": metadata.get(image_path.name, {}).get("angle") or "50",
                "source": "screenshot",
                "matching_allowed": True,
                "sourceImage": f"/kilter_climbs_data/app_screenshots_dataset/{image_path.name}",
            }
        for image_path in sorted(screenshots_dir.glob("*.png"))
    ]
    return climbs, len(climbs)


def _server_sort_key(record: dict, sort: str) -> tuple:
    grade = _safe_int(record.get("v_grade"), 99)
    ascents = _safe_int(record.get("ascensionist_count"), 0)
    stars = _safe_float(record.get("stars") or record.get("quality_average"), 0.0)
    name = str(record.get("name") or "")
    if sort in {"gradeAsc", "gradeDesc"}:
        return (grade, name)
    if sort in {"ascentsAsc", "ascentsDesc"}:
        return (ascents, name)
    if sort in {"starsAsc", "starsDesc"}:
        return (stars, name)
    return (name.lower(), grade)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _csv_bool(value: object, default: bool = True) -> bool:
    if value in (None, ""):
        return default
    return str(value).lower() in {"1", "true", "yes"}


def list_source_climbs_from_csv(query: dict[str, list[str]]) -> tuple[list[dict], int]:
    angle = _query_int(query, "angle")
    min_grade = _query_int(query, "minGrade", 0)
    max_grade = _query_int(query, "maxGrade", 16)
    sort = query.get("sort", ["name"])[0]
    name_filter = (query.get("name", [""])[0] or "").strip().lower()
    source_limit = _query_int(query, "limit", 400) or 400
    matches: list[dict] = []
    with ALL_KILTER_CLIMBS_CSV.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            row_angle = _safe_int(row.get("angle"), -999)
            row_grade = _safe_int(row.get("v_grade"), 99)
            if angle is not None and row_angle != angle:
                continue
            if min_grade is not None and row_grade < min_grade:
                continue
            if max_grade is not None and row_grade > max_grade:
                continue
            if name_filter and name_filter not in str(row.get("name") or "").lower():
                continue
            matches.append(row)
    matches.sort(key=lambda record: _server_sort_key(record, sort))
    if sort in {"gradeDesc", "ascentsDesc", "starsDesc"}:
        matches.reverse()
    climbs = []
    for index, record in enumerate(matches[:source_limit]):
        climb_id = str(record.get("uuid") or record.get("id") or index)
        try:
            holds = json.loads(record.get("holds") or "{}")
        except json.JSONDecodeError:
            holds = {}
        climbs.append({
            "id": f"{climb_id}:{record.get('angle', '')}",
            "uuid": record.get("uuid") or climb_id,
            "name": record.get("name") or climb_id,
            "grade": record.get("grade") or "Unknown",
            "v_grade": _safe_int(record.get("v_grade"), 99),
            "angle": _safe_int(record.get("angle"), -1),
            "stars": _safe_float(record.get("stars") or record.get("quality_average"), 0.0),
            "source": "kilter_db",
            "ascensionist_count": _safe_int(record.get("ascensionist_count"), 0),
            "setter_username": record.get("setter_username"),
            "matching_allowed": _csv_bool(record.get("matching_allowed"), True),
            "holds": holds,
        })
    return climbs, len(matches)


def load_source_metadata() -> dict[str, dict[str, str]]:
    if not SOURCE_METADATA_PATH.exists():
        return {}
    with SOURCE_METADATA_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def parse_ocr_metadata(text: str) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = ""
    grade = ""
    for index, line in enumerate(lines):
        if "kk" in line.lower() or re.search(r"\b\d+[abc][+-]?/V\d+\b", line, flags=re.IGNORECASE):
            grade_match = re.search(r"\b\d+[abc][+-]?/V\d+\b", line, flags=re.IGNORECASE)
            if grade_match:
                grade = grade_match.group(0)
            if index > 0:
                previous = re.sub(r"[^A-Za-z0-9 '&!?.-]", "", lines[index - 1]).strip()
                if 2 <= len(previous) <= 60:
                    name = previous
            break
    if not name:
        for line in lines:
            cleaned = re.sub(r"[^A-Za-z0-9 '&!?.-]", "", line).strip()
            if 2 <= len(cleaned) <= 60 and not re.search(r"(AT&T|PM|AM|Boards|Logbook|Settings)", cleaned):
                name = cleaned
                break
    return {"name": name, "grade": grade}


def extract_source_metadata(image_path: Path, timeout: float = 2.0) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["tesseract", str(image_path), "stdout", "--psm", "11"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return {}
    return parse_ocr_metadata(result.stdout)


def load_saved_climbs() -> list[dict]:
    if not SAVED_CLIMBS_PATH.exists():
        return []
    with SAVED_CLIMBS_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, list) else []


def save_climb(climb: dict) -> dict:
    validated = validate_climb(climb)
    saved_climbs = [item for item in load_saved_climbs() if item.get("name") != validated["name"]]
    saved_climbs.append(validated)
    SAVED_CLIMBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SAVED_CLIMBS_PATH.open("w", encoding="utf-8") as file:
        json.dump(saved_climbs, file, indent=2)
    return validated


class AppHandler(BaseHTTPRequestHandler):
    server_version = "AISetterWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/":
            self._send_file(STATIC_DIR / "index.html")
        elif path.startswith("/static/"):
            self._send_file(STATIC_DIR / path.removeprefix("/static/"))
        elif path.startswith("/kilter_climbs_data/"):
            self._send_file(KILTER_DATA_DIR / path.removeprefix("/kilter_climbs_data/"))
        elif path.startswith("/kilter_climbs_output/"):
            self._send_file(KILTER_OUTPUT_DIR / path.removeprefix("/kilter_climbs_output/"))
        elif path.startswith("/outputs/"):
            self._send_file(OUTPUTS_DIR / path.removeprefix("/outputs/"))
        elif path == "/api/climbs":
            source_climbs, total_count = list_source_climbs(parse_qs(parsed.query))
            self._send_json({"sourceClimbs": source_climbs, "sourceTotal": total_count, "savedClimbs": load_saved_climbs()})
        elif path == "/api/dataset-summary":
            records = load_dataset()
            self._send_json({"summary": dataset_summary(records), "localHeatmap": local_heatmap(records)})
        else:
            self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/climbs":
            self._handle_save_climb()
        elif parsed.path == "/api/sequence":
            payload = self._read_json()
            sequence = estimate_hand_sequence(
                payload.get("holds", {}),
                matching_allowed=bool(payload.get("matching_allowed", True)),
                grade=payload.get("grade"),
            )
            feet = estimate_foot_sequence(payload.get("holds", {}), sequence)
            self._send_json({"sequence": sequence, "hand_sequence": sequence, "foot_sequence": feet, "metrics": sequence_metrics(sequence, feet)})
        elif parsed.path == "/api/generate-climb":
            self._handle_generate_climb()
        elif parsed.path == "/api/generate-outputs":
            from ai_setters.generate_outputs import generate_outputs

            payload = self._read_json()
            manifest = generate_outputs(count=int(payload.get("count") or 32), train_neural=bool(payload.get("trainNeural")))
            self._send_json({"manifest": manifest})
        elif parsed.path == "/api/rebuild-dataset":
            records = build_dataset(refresh=True)
            self._send_json({"records": len(records)})
        else:
            self._send_json({"error": "Not found"}, status=404)

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _handle_save_climb(self) -> None:
        try:
            saved = save_climb(self._read_json())
        except ClimbValidationError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        sequence = estimate_sequence(saved["holds"], matching_allowed=bool(saved.get("matching_allowed", True)), grade=saved.get("grade"))
        feet = estimate_foot_sequence(saved["holds"], sequence)
        self._send_json({"climb": saved, "sequence": sequence, "hand_sequence": sequence, "foot_sequence": feet, "metrics": sequence_metrics(sequence, feet)}, status=201)

    def _handle_generate_climb(self) -> None:
        from ai_setters.generators import generate_climb

        payload = self._read_json()
        try:
            climb = generate_climb(
                setter=str(payload.get("setter") or "random"),
                grade=str(payload.get("grade") or "V5"),
                angle=str(payload.get("angle") or "50"),
                seed=payload.get("seed"),
                options=payload.get("options") or {},
            )
        except (ValueError, ClimbValidationError) as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        self._send_json({"climb": climb, "diagnostics": climb.get("diagnostics", {})})

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8")) if body else {}

    def _send_json(self, payload: dict, status: int = 200) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            if not str(resolved).startswith(str(ROOT)) or not resolved.is_file():
                raise FileNotFoundError
            content = resolved.read_bytes()
        except FileNotFoundError:
            self._send_json({"error": "Not found"}, status=404)
            return
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--refresh-metadata", action="store_true")
    args = parser.parse_args()
    if args.refresh_metadata:
        metadata = load_source_metadata()
        screenshots_dir = SCREENSHOTS_DATA_DIR if SCREENSHOTS_DATA_DIR.exists() else KILTER_DATA_DIR
        for image_path in sorted(screenshots_dir.glob("*.png")):
            extracted = extract_source_metadata(image_path)
            metadata[image_path.name] = extracted
            print(f"{image_path.name}: {extracted.get('name') or image_path.stem}")
        SOURCE_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SOURCE_METADATA_PATH.open("w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=2)
        return
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"AI Setter web app running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
