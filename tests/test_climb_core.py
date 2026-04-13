import tempfile
import unittest
from pathlib import Path

from ai_setters.climb_core import ClimbValidationError, estimate_sequence, validate_climb
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


if __name__ == "__main__":
    unittest.main()
