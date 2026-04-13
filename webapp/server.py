"""Dependency-light local web app server for AI Setter."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_setters.climb_core import ClimbValidationError, estimate_sequence, validate_climb

STATIC_DIR = ROOT / "webapp" / "static"
KILTER_DATA_DIR = ROOT / "kilter_climbs_data"
KILTER_OUTPUT_DIR = ROOT / "kilter_climbs_output"
SAVED_CLIMBS_PATH = ROOT / "webapp" / "data" / "saved_climbs.json"
SOURCE_METADATA_PATH = ROOT / "webapp" / "data" / "source_climbs_metadata.json"


def list_source_climbs() -> list[dict[str, str]]:
    metadata = load_source_metadata()
    return [
        {
            "id": image_path.stem,
            "name": metadata.get(image_path.name, {}).get("name") or image_path.stem.replace("_", " "),
            "grade": metadata.get(image_path.name, {}).get("grade") or "Unknown",
            "angle": metadata.get(image_path.name, {}).get("angle") or "50",
            "sourceImage": f"/kilter_climbs_data/{image_path.name}",
        }
        for image_path in sorted(KILTER_DATA_DIR.glob("*.png"))
    ]


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
        elif path == "/api/climbs":
            self._send_json({"sourceClimbs": list_source_climbs(), "savedClimbs": load_saved_climbs()})
        else:
            self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/climbs":
            self._handle_save_climb()
        elif parsed.path == "/api/sequence":
            payload = self._read_json()
            self._send_json({"sequence": estimate_sequence(payload.get("holds", {}))})
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
        self._send_json({"climb": saved, "sequence": estimate_sequence(saved["holds"])}, status=201)

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
        for image_path in sorted(KILTER_DATA_DIR.glob("*.png")):
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
