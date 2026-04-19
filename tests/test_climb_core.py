import tempfile
import unittest
from pathlib import Path

from ai_setters.climb_core import ClimbValidationError, estimate_foot_sequence, estimate_hand_sequence, estimate_sequence, foot_candidate_penalty, normalize_holds, validate_climb
from ai_setters.dataset import dataset_summary, extract_holds_from_png, hold_size_bins, valid_hold_positions
from ai_setters.generators import EmpiricalSequentialSetter, GraphSetter, NeuralSetter, RandomSetter, generate_climb
from webapp import server


VALID_CLIMB = {
    "name": "Test Line",
    "grade": "V5",
    "angle": "50",
    "holds": {
        "Start": [[14, 4], [18, 4]],
        "Any": [[17, 12], [20, 20]],
        "Finish": [[21, 34]],
        "Feet": [[13, 2], [19, 8]],
    },
}


class ClimbCoreTest(unittest.TestCase):
    def test_validate_climb_accepts_coordinate_backed_climb(self):
        climb = validate_climb(VALID_CLIMB)
        self.assertEqual(climb["name"], "Test Line")
        self.assertEqual(climb["holds"]["Start"], [[14, 4], [18, 4]])

    def test_validate_climb_rejects_more_than_two_start_holds(self):
        climb = {**VALID_CLIMB, "holds": {**VALID_CLIMB["holds"], "Start": [[1, 1], [2, 1], [3, 1]]}}
        with self.assertRaisesRegex(ClimbValidationError, "at most two start"):
            validate_climb(climb)

    def test_validate_climb_rejects_more_than_two_finish_holds(self):
        climb = {**VALID_CLIMB, "holds": {**VALID_CLIMB["holds"], "Finish": [[1, 38], [2, 38], [3, 38]]}}
        with self.assertRaisesRegex(ClimbValidationError, "at most two finish"):
            validate_climb(climb)

    def test_estimate_sequence_moves_bottom_to_top_and_matches_finish(self):
        sequence = estimate_sequence(VALID_CLIMB["holds"])
        self.assertEqual(sequence[0]["type"], "Start")
        self.assertEqual(sequence[-1]["type"], "Finish")
        self.assertEqual(sequence[-2]["type"], "Finish")
        self.assertGreaterEqual(sequence[-1]["y"], sequence[0]["y"])

    def test_server_save_climb_persists_coordinates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_path = server.SAVED_CLIMBS_PATH
            server.SAVED_CLIMBS_PATH = Path(tmpdir) / "saved_climbs.json"
            try:
                saved = server.save_climb(VALID_CLIMB)
                self.assertEqual(saved["holds"]["Any"], [[17, 12], [20, 20]])
                reloaded = server.load_saved_climbs()
                self.assertEqual(reloaded[0]["name"], "Test Line")
            finally:
                server.SAVED_CLIMBS_PATH = original_path

    def test_parse_ocr_metadata_uses_name_before_grade_line(self):
        text = "50 degrees\nA Few Fun Moves\n6b/V4 kkk\nextra wall text"
        self.assertEqual(server.parse_ocr_metadata(text)["name"], "A Few Fun Moves")
        self.assertEqual(server.parse_ocr_metadata(text)["grade"], "6b/V4")

    def test_extract_holds_from_png_does_not_double_count_example(self):
        holds = extract_holds_from_png(Path("kilter_climbs_data/app_screenshots_dataset/IMG_5780.png"))
        valid = valid_hold_positions()
        self.assertEqual(len(holds["Finish"]), 1)
        self.assertGreaterEqual(len(holds["Start"]), 1)
        self.assertLessEqual(len(holds["Start"]), 2)
        self.assertFalse([hold for points in holds.values() for hold in points if tuple(hold) not in valid])

    def test_dataset_summary_includes_zero_usage_physical_top_row(self):
        valid = valid_hold_positions()
        max_y = max(y for _x, y in valid)
        summary = dataset_summary([])
        top_keys = {f"{x}:{y}" for x, y in valid if y == max_y}
        self.assertTrue(top_keys)
        self.assertTrue(top_keys.issubset(summary["hold_usage"]))
        self.assertTrue(all(summary["hold_usage"][key] == 0 for key in top_keys))

    def test_random_setter_respects_required_hold_counts(self):
        climb = RandomSetter(records=[]).create(seed=7)
        validated = validate_climb(climb)
        self.assertLessEqual(len(validated["holds"]["Start"]), 2)
        self.assertLessEqual(len(validated["holds"]["Finish"]), 2)

    def test_random_setter_hand_sequence_edges_are_within_eighteen_units(self):
        climb = generate_climb("random", seed=7, options={"hand_count": 8, "foot_count": 4})
        sequence = climb["sequence"]
        for current, nxt in zip(sequence, sequence[1:]):
            dist = ((current["x"] - nxt["x"]) ** 2 + (current["y"] - nxt["y"]) ** 2) ** 0.5
            self.assertLessEqual(dist, 18)
        all_holds = [tuple(hold) for holds in climb["holds"].values() for hold in holds]
        for index, hold in enumerate(all_holds):
            nearest = min(
                ((hold[0] - other[0]) ** 2 + (hold[1] - other[1]) ** 2) ** 0.5
                for other_index, other in enumerate(all_holds)
                if other_index != index
            )
            self.assertLessEqual(nearest, 18)

    def test_random_setter_uses_large_holds_for_v0(self):
        climb = RandomSetter(records=[]).create(grade="V0", seed=7, options={"hand_count": 6, "foot_count": 2})
        bins = hold_size_bins()
        hand_holds = [tuple(hold) for hold_type in ("Start", "Any", "Finish") for hold in climb["holds"][hold_type]]
        self.assertTrue(hand_holds)
        self.assertTrue(all(bins.get(hold) == "large" for hold in hand_holds))

    def test_generated_feet_satisfy_grade_dependent_non_penalized_quotas(self):
        for grade, minimum in (("V3", 2), ("V8", 1), ("V11", 1)):
            climb = generate_climb("random", grade=grade, seed=12, options={"hand_count": 7})
            holds = normalize_holds(climb["holds"])
            available_feet = {tuple(hold) for hold_type in ("Start", "Any", "Finish", "Feet") for hold in holds[hold_type]}
            all_physical = valid_hold_positions()
            for move in climb["hand_sequence"]:
                left = tuple(move["left"])
                right = tuple(move["right"])
                possible = [
                    hold for hold in all_physical
                    if hold not in {left, right}
                    and foot_candidate_penalty(holds, left, right, hold) == 0
                ]
                usable = [
                    hold for hold in available_feet
                    if hold not in {left, right}
                    and foot_candidate_penalty(holds, left, right, hold) == 0
                ]
                if move["move"] > 0 and len(possible) >= minimum:
                    self.assertGreaterEqual(len(usable), minimum, (grade, move["label"], usable, climb["holds"]))

    def test_generated_feet_are_not_excessive_for_hard_climbs(self):
        climb = generate_climb("random", grade="V11", seed=15, options={"hand_count": 8})
        self.assertLessEqual(len(climb["holds"]["Feet"]), len(climb["hand_sequence"]) + 1)

    def test_sequence_includes_pair_state_and_metrics(self):
        climb = generate_climb("sequential", seed=4, options={"hand_count": 6, "foot_count": 4})
        self.assertTrue(climb["hand_sequence"])
        self.assertIn("left", climb["hand_sequence"][0])
        self.assertIn("right", climb["hand_sequence"][0])
        self.assertEqual([step["move"] for step in climb["foot_sequence"]], sorted({move["move"] for move in climb["hand_sequence"]}))
        self.assertIn("average_interhand_distance", climb["sequence_metrics"])

    def test_hand_sequence_search_revises_earlier_moves_to_avoid_later_bumps_and_crosses(self):
        holds = {
            "Start": [[14, 16], [18, 16]],
            "Any": [[18, 20], [10, 22], [14, 28], [14, 30], [18, 34]],
            "Finish": [[18, 38], [22, 38]],
            "Feet": [[14, 6], [16, 8], [8, 10], [16, 12], [8, 14], [20, 22]],
        }
        sequence = estimate_hand_sequence(holds)
        labels = [move["label"] for move in sequence]
        events = {move["label"]: move["event"] for move in sequence}
        self.assertEqual(labels[2:7], ["1R", "2L", "3R", "4L", "5R"])
        self.assertNotIn("bump", events["2L"])
        self.assertFalse(next(move for move in sequence if move["label"] == "5R")["crossed"])

    def test_hand_sequence_orders_targets_to_avoid_downward_bump(self):
        holds = {
            "Start": [[18, 10]],
            "Any": [[14, 16], [18, 20], [10, 22], [8, 26], [14, 28], [8, 32]],
            "Finish": [[12, 38]],
            "Feet": [],
        }
        sequence = estimate_hand_sequence(holds)
        labels = [(move["label"], [move["x"], move["y"]], move["event"]) for move in sequence]
        self.assertNotIn("down", " ".join(label[2] for label in labels))
        self.assertEqual(labels[-2][1], [12, 38])

    def test_hand_sequence_skips_optional_hold_requiring_too_long_horizontal_move(self):
        holds = {
            "Start": [[6, 12], [8, 12]],
            "Any": [[31, 13], [12, 18], [16, 22]],
            "Finish": [[18, 30]],
            "Feet": [],
        }
        sequence = estimate_hand_sequence(holds, grade="V4")
        self.assertNotIn([31, 13], [[move["x"], move["y"]] for move in sequence])
        for current, nxt in zip(sequence, sequence[1:]):
            self.assertLessEqual(((current["x"] - nxt["x"]) ** 2 + (current["y"] - nxt["y"]) ** 2) ** 0.5, 21)

    def test_hand_sequence_respects_no_matching_flag(self):
        holds = {
            "Start": [[14, 10], [18, 10]],
            "Any": [[16, 18]],
            "Finish": [[16, 28]],
            "Feet": [],
        }
        sequence = estimate_hand_sequence(holds, matching_allowed=False)
        self.assertFalse(any(move["left"] == move["right"] and move["move"] > 0 and "finish_match" not in move["event"] for move in sequence))
        self.assertEqual(sequence[-1]["left"], sequence[-1]["right"])

    def test_overcook_sequence_matches_single_finish_and_has_move_keyed_feet(self):
        holds = {
            "Start": [[27, 19], [32, 24]],
            "Any": [[8, 30], [22, 30], [24, 30], [2, 34], [12, 34]],
            "Finish": [[2, 38]],
            "Feet": [[35, 7], [4, 18], [2, 20], [1, 21]],
        }
        sequence = estimate_hand_sequence(holds, grade="8a/V11", matching_allowed=False)
        feet = estimate_foot_sequence(holds, sequence)
        self.assertEqual(sequence[-1]["left"], sequence[-1]["right"])
        self.assertEqual(sequence[-1]["left"], [2, 38])
        self.assertEqual([step["move"] for step in feet], sorted({move["move"] for move in sequence}))
        self.assertTrue(any(step["foot_moves"] for step in feet if step["move"] > 0))

    def test_hand_sequence_avoids_blocked_lowball_choss_first_move(self):
        holds = {
            "Start": [[26, 6], [32, 8]],
            "Any": [[6, 14], [12, 16], [20, 18], [8, 28]],
            "Finish": [[2, 36]],
            "Feet": [[9, 1], [34, 2], [9, 5], [1, 9]],
        }
        sequence = estimate_hand_sequence(holds, grade="8a/V11")
        labels = [(move["label"], move["hand"], [move["x"], move["y"]], move["event"]) for move in sequence]
        self.assertEqual(labels[2][0:3], ("1L", "left", [20, 18]))
        self.assertEqual(labels[3][0:3], ("2R", "right", [12, 16]))
        self.assertEqual(labels[4][0:3], ("3L", "left", [6, 14]))
        self.assertEqual(labels[5][0:3], ("4R", "right", [8, 28]))
        self.assertEqual(labels[6][0:3], ("5L", "left", [2, 36]))
        self.assertNotIn("blocked_long_move", " ".join(event for _label, _hand, _hold, event in labels))

    def test_sequential_and_graph_setters_generate_valid_climbs(self):
        records = [{"holds": VALID_CLIMB["holds"], "sequence": estimate_sequence(VALID_CLIMB["holds"])}]
        for setter in (EmpiricalSequentialSetter(records), GraphSetter(records)):
            generated = validate_climb(setter.create(seed=3))
            self.assertTrue(generated["holds"]["Start"])
            self.assertTrue(generated["holds"]["Finish"])

    def test_neural_setter_tensor_round_trip(self):
        setter = NeuralSetter(records=[])
        encoded = setter.encode(VALID_CLIMB)
        decoded = setter.decode(encoded)
        self.assertEqual(decoded["Start"], VALID_CLIMB["holds"]["Start"])
        self.assertEqual(decoded["Finish"], VALID_CLIMB["holds"]["Finish"])

    def test_generate_climb_dispatch(self):
        climb = generate_climb("graph", seed=11, options={"hand_count": 6, "foot_count": 4})
        self.assertEqual(climb["setter"], "graph")
        self.assertTrue(climb["sequence"])
        self.assertTrue(climb["selection_notes"])
        self.assertIn("Model description:", climb["selection_explanation"])
        self.assertIn("Hold-By-Hold Explanation:", climb["selection_explanation"])


if __name__ == "__main__":
    unittest.main()
