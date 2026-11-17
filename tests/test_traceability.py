# -*- coding: utf-8 -*-
"""
Traceability of the tool operational requirements (TOR) to the tests.

Every test named in the "Verified by" column of docs/MCDC_IMPLEMENTATION.md
section 16 must exist, and every TOR must name at least one test, so that
the validation record (tests/run_validation.py, IEC 61508-3 7.4.4.7 c)
links each tool function to tests that are actually run.

Run from the project folder:
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import run_validation  # noqa: E402


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


class TorTraceability(unittest.TestCase):
    def test_every_tor_names_existing_tests(self):
        suite = unittest.TestLoader().discover(start_dir=str(TESTS), top_level_dir=str(TESTS))
        records = {t: {"status": "PASS"} for t in test_ids(suite)}
        traced = run_validation.trace_tors(records)
        self.assertGreaterEqual(len(traced), 13)
        self.assertEqual([t[0] for t in traced], [f"TOR-{n:02d}" for n in range(1, len(traced) + 1)])
        for tor, _, _, tests, result, unresolved in traced:
            with self.subTest(tor=tor):
                self.assertEqual(unresolved, [])
                self.assertTrue(tests)
                self.assertEqual(result, "PASS")

    def test_reference_forms(self):
        """The forms of reference used in the TOR table."""
        tid = "test_qualification.S2Definitions.test_figure_6"
        for reference, expected in (("S2Definitions.*", True), ("S2Definitions.test_figure_6", True),
                                    ("test_figure_6", True), ("test_qualification.py", True),
                                    ("test_qualification.S2Definitions.test_figure_6", True),
                                    ("S2Definitions", False), ("test_figure", False),
                                    ("S1BuildingBlocks.*", False), ("test_scenario.py", False)):
            with self.subTest(reference=reference):
                self.assertEqual(run_validation.matches(reference, tid), expected)


if __name__ == "__main__":
    unittest.main()
