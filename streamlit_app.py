"""Streamlit entrypoint for deploying AI Setter from GitHub."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from ai_setters.climb_core import (
    ClimbValidationError,
    estimate_foot_sequence,
    estimate_hand_sequence,
    sequence_metrics,
    validate_climb,
)
from ai_setters.generators import EmpiricalSequentialSetter, GraphSetter, NeuralSetter, RandomSetter, generate_climb
from ai_setters.rendering import render_climb_png
from webapp.server import load_saved_climbs, save_climb


ROOT = Path(__file__).resolve().parent
FALLBACK_DATASET = ROOT / "webapp" / "data" / "climbs_dataset.json"
DEPLOYMENT_DATASET = ROOT / "webapp" / "data" / "streamlit_climbs.json"


st.set_page_config(page_title="AI Setter", page_icon="AS", layout="wide")


@st.cache_data(show_spinner=False)
def bundled_climbs(
    angle: str,
    min_grade: int,
    max_grade: int,
    source: str,
    sort: str,
    name: str,
    limit: int,
) -> tuple[list[dict], int]:
    dataset_path = DEPLOYMENT_DATASET if DEPLOYMENT_DATASET.exists() else FALLBACK_DATASET
    if not dataset_path.exists():
        return [], 0
    with dataset_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    records = payload.get("climbs", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        return [], 0

    name_filter = name.strip().lower()
    selected = []
    for record in records:
        row_angle = str(record.get("angle") or "")
        row_grade = record.get("v_grade")
        try:
            row_grade_int = int(row_grade) if row_grade is not None else 99
        except (TypeError, ValueError):
            row_grade_int = 99
        if source == "user":
            continue
        if angle and row_angle != angle:
            continue
        if row_grade_int < min_grade or row_grade_int > max_grade:
            continue
        if name_filter and name_filter not in str(record.get("name") or "").lower():
            continue
        selected.append({**record, "source": record.get("source") or "kilter"})

    def sort_key(record: dict) -> tuple:
        grade = record.get("v_grade")
        stars = record.get("stars") if isinstance(record.get("stars"), (int, float)) else 0
        ascents = record.get("ascensionist_count") or 0
        name_value = str(record.get("name") or "").lower()
        if sort in {"gradeAsc", "gradeDesc"}:
            return (int(grade) if grade is not None else 99, name_value)
        if sort in {"ascentsAsc", "ascentsDesc"}:
            return (int(ascents), name_value)
        if sort in {"starsAsc", "starsDesc"}:
            return (float(stars), name_value)
        return (name_value, int(grade) if grade is not None else 99)

    selected.sort(key=sort_key, reverse=sort in {"gradeDesc", "ascentsDesc", "starsDesc"})
    return selected[:limit], len(selected)


@st.cache_data(show_spinner=False)
def load_source_results(
    angle: str,
    min_grade: int,
    max_grade: int,
    source: str,
    sort: str,
    name: str,
    limit: int,
) -> tuple[list[dict], int, str | None]:
    climbs, total = bundled_climbs(angle, min_grade, max_grade, source, sort, name, limit)
    if DEPLOYMENT_DATASET.exists():
        return climbs, total, None
    return climbs, total, "Using the small screenshot fallback dataset because the deployment Kilter subset is unavailable."


def climb_label(climb: dict) -> str:
    grade = climb.get("grade") or "Unknown"
    angle = climb.get("angle") or "?"
    name = climb.get("name") or climb.get("id") or "Untitled"
    return f"{name} | {grade} | {angle} deg"


def hydrate_sequence(climb: dict) -> dict:
    hydrated = dict(climb)
    matching_allowed = bool(hydrated.get("matching_allowed", True))
    grade = hydrated.get("grade")
    if not hydrated.get("hand_sequence") and not hydrated.get("sequence"):
        hydrated["hand_sequence"] = estimate_hand_sequence(hydrated.get("holds", {}), matching_allowed=matching_allowed, grade=grade)
        hydrated["sequence"] = hydrated["hand_sequence"]
    if not hydrated.get("foot_sequence"):
        hydrated["foot_sequence"] = estimate_foot_sequence(hydrated.get("holds", {}), hydrated.get("hand_sequence") or hydrated.get("sequence") or [])
    if not hydrated.get("sequence_metrics"):
        hydrated["sequence_metrics"] = sequence_metrics(hydrated.get("hand_sequence") or [], hydrated.get("foot_sequence") or [])
    return hydrated


@st.cache_data(show_spinner=False)
def fallback_training_records() -> list[dict]:
    dataset_path = DEPLOYMENT_DATASET if DEPLOYMENT_DATASET.exists() else FALLBACK_DATASET
    if not dataset_path.exists():
        return []
    with dataset_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    records = payload.get("climbs", payload) if isinstance(payload, dict) else payload
    return records if isinstance(records, list) else []


def generate_climb_for_streamlit(setter: str, grade: str, angle: str, seed: int, options: dict) -> dict:
    try:
        return generate_climb(setter, grade=grade, angle=angle, seed=seed, options=options)
    except Exception:
        records = fallback_training_records()
        setter_key = setter.lower()
        if setter_key == "random":
            model = RandomSetter(records)
        elif setter_key == "sequential":
            model = EmpiricalSequentialSetter(records)
        elif setter_key == "graph":
            model = GraphSetter(records)
        elif setter_key == "neural":
            model = NeuralSetter(records)
        else:
            raise ValueError(f"Unknown setter: {setter}")
        climb = validate_climb(model.create(grade=grade, angle=angle, seed=seed, options=options))
        climb["setter"] = setter
        return hydrate_sequence(climb)


def render_climb(climb: dict, annotate_sequence: bool = True) -> Path:
    climb = hydrate_sequence(climb)
    title = climb_label(climb)
    output_path = Path(tempfile.gettempdir()) / "ai_setter_streamlit_climb.png"
    render_climb_png(climb, output_path, title=title, annotate_sequence=annotate_sequence, size=(650, 802))
    return output_path


def parse_points(text: str) -> list[list[int]]:
    points = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        x_raw, y_raw = line.replace(" ", "").split(",", 1)
        points.append([int(x_raw), int(y_raw)])
    return points


def current_climb() -> dict | None:
    return st.session_state.get("current_climb")


st.title("AI Setter")
st.caption("Find board climbs, generate new climbs, and estimate hand and foot beta.")

tab_find, tab_generate, tab_set, tab_beta = st.tabs(["Find climbs", "Generate climb", "Set a climb", "Beta"])

with tab_find:
    filters = st.container(border=True)
    col_a, col_b, col_c, col_d = filters.columns([1, 1, 1, 1])
    angle = col_a.selectbox("Angle", [str(value) for value in range(0, 75, 5)], index=8, key="find_angle")
    min_grade, max_grade = col_b.slider("Grade range", min_value=0, max_value=16, value=(0, 16), key="find_grade")
    source = col_c.selectbox("Source", ["all", "kilter", "user"], format_func={"all": "All climbs", "kilter": "Kilter data", "user": "User set"}.get)
    sort = col_d.selectbox(
        "Sort",
        ["ascentsDesc", "name", "gradeAsc", "gradeDesc", "ascentsAsc", "starsDesc", "starsAsc"],
        format_func={
            "ascentsDesc": "Ascents descending",
            "name": "Name",
            "gradeAsc": "Grade ascending",
            "gradeDesc": "Grade descending",
            "ascentsAsc": "Ascents ascending",
            "starsDesc": "Stars descending",
            "starsAsc": "Stars ascending",
        }.get,
    )
    name = filters.text_input("Search by name", "")
    limit = filters.slider("Result limit", min_value=25, max_value=500, value=150, step=25)

    source_climbs, total, warning = load_source_results(angle, min_grade, max_grade, source, sort, name, limit)
    saved_climbs = [] if source == "kilter" else [{**climb, "source": "user"} for climb in load_saved_climbs()]
    climbs = saved_climbs + ([] if source == "user" else source_climbs)
    if warning:
        st.warning(warning)
    st.write(f"{total + len(saved_climbs):,} matching climbs")

    if climbs:
        selected = st.selectbox("Climb", climbs, format_func=climb_label)
        st.session_state.current_climb = hydrate_sequence(selected)
        left, right = st.columns([0.58, 0.42], vertical_alignment="top")
        left.image(str(render_climb(st.session_state.current_climb)))
        with right:
            climb = st.session_state.current_climb
            st.subheader(climb.get("name") or "Untitled")
            st.write(f"Grade: **{climb.get('grade', 'Unknown')}**")
            st.write(f"Angle: **{climb.get('angle', 'Unknown')} deg**")
            if climb.get("stars") not in (None, "Unknown", ""):
                st.write(f"Stars: **{climb.get('stars')}**")
            if climb.get("ascensionist_count") is not None:
                st.write(f"Ascents: **{climb.get('ascensionist_count')}**")
            holds = climb.get("holds", {})
            st.write("Holds")
            st.json({key: len(holds.get(key, [])) for key in ("Start", "Any", "Finish", "Feet")}, expanded=False)
    else:
        st.info("No climbs matched those filters.")

with tab_generate:
    col_a, col_b, col_c, col_d = st.columns(4)
    setter = col_a.selectbox("Setter", ["random", "sequential", "graph", "neural"])
    grade = col_b.selectbox("Grade", [f"V{i}" for i in range(17)], index=5)
    gen_angle = col_c.selectbox("Angle", [str(value) for value in range(0, 75, 5)], index=10, key="gen_angle")
    seed = col_d.number_input("Seed", min_value=0, max_value=1_000_000, value=1, step=1)
    col_e, col_f, col_g = st.columns(3)
    hand_count = col_e.slider("Hand holds", 4, 14, 8)
    foot_count = col_f.slider("Foot holds", 0, 12, 6)
    matching_allowed = col_g.checkbox("Allow matching", value=True)

    if st.button("Generate climb", type="primary"):
        options = {"hand_count": hand_count, "foot_count": foot_count, "matching_allowed": matching_allowed}
        try:
            generated = generate_climb_for_streamlit(setter, grade=grade, angle=gen_angle, seed=int(seed), options=options)
        except Exception as exc:
            st.error(f"Could not generate climb: {exc}")
        else:
            st.session_state.current_climb = hydrate_sequence(generated)

    if current_climb():
        st.image(str(render_climb(current_climb())))
        if current_climb().get("selection_notes"):
            st.info(current_climb()["selection_notes"])

with tab_set:
    st.write("Enter hold coordinates as `x,y`, one hold per line.")
    col_a, col_b, col_c = st.columns(3)
    new_name = col_a.text_input("Name", "New Climb")
    new_grade = col_b.text_input("Grade", "V5")
    new_angle = col_c.text_input("Angle", "40")
    start_text = st.text_area("Start holds", "10,6\n14,6")
    any_text = st.text_area("Any holds", "12,12\n18,18\n20,25")
    finish_text = st.text_area("Finish holds", "18,35")
    feet_text = st.text_area("Feet", "9,5\n15,10")
    if st.button("Preview and save climb"):
        try:
            climb = validate_climb(
                {
                    "name": new_name,
                    "grade": new_grade,
                    "angle": new_angle,
                    "matching_allowed": True,
                    "holds": {
                        "Start": parse_points(start_text),
                        "Any": parse_points(any_text),
                        "Finish": parse_points(finish_text),
                        "Feet": parse_points(feet_text),
                    },
                }
            )
            saved = save_climb(climb)
        except (ValueError, ClimbValidationError) as exc:
            st.error(str(exc))
        else:
            st.session_state.current_climb = hydrate_sequence(saved)
            st.success("Climb saved for this deployment session.")
    if current_climb():
        st.image(str(render_climb(current_climb())))

with tab_beta:
    climb = current_climb()
    if not climb:
        st.info("Select or generate a climb first.")
    else:
        climb = hydrate_sequence(climb)
        st.subheader(climb_label(climb))
        st.image(str(render_climb(climb, annotate_sequence=True)))
        metrics = climb.get("sequence_metrics") or {}
        if metrics:
            st.write("Metrics")
            st.json(metrics, expanded=False)
        col_a, col_b = st.columns(2)
        col_a.write("Hand sequence")
        col_a.dataframe(climb.get("hand_sequence") or climb.get("sequence") or [], width="stretch")
        col_b.write("Foot sequence")
        col_b.dataframe(climb.get("foot_sequence") or [], width="stretch")
