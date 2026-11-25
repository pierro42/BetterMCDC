# -*- coding: utf-8 -*-
"""
Qualification test suite for the MC/DC analysis (package mcdc).

Every expected result below is transcribed from one of these published
documents; nothing is derived from the tool itself (see tests/SOURCES.md):

  [S1] NASA/TM-2001-210876, "A Practical Tutorial on Modified
       Condition/Decision Coverage", Hayhurst, Veerhusen, Chilenski,
       Rierson, May 2001.
  [S2] DOT/FAA/AR-01/18, "An Investigation of Three Forms of the Modified
       Condition Decision Coverage (MCDC) Criterion", Chilenski, April 2001.
  [S3] DOT/FAA/AR-06/54, "Software Verification Tools Assessment Study",
       June 2007 (one statement, section 4.3.2).

Test vectors are written as in the sources ("TFTF": first condition first)
and row numbers are computed from them: first input = most significant bit,
which is also S2's numbering (e.g. "4:(TFF)").

Run from the project folder:
    python -m unittest discover -s tests -v
"""

import csv
import itertools
import math
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcdc  # noqa: E402

DATA = Path(__file__).resolve().parent / "data" / "ar0118_appendix_c.tsv"


# ---------------------------------------------------------------------------
# Helpers (they only transcribe notation, they compute no expected result)
# ---------------------------------------------------------------------------

def vec(text):
    """'TFTF' -> (True, False, True, False)"""
    return tuple(c == "T" for c in text)


def row(text):
    """'TFTF' -> truth table row number (first input = most significant bit)"""
    return int(text.replace("T", "1").replace("F", "0"), 2)


def pair(a, b):
    return tuple(sorted((row(a), row(b))))


def exact(text, mode):
    """Run the exact engine: decision, truth table, independence pairs."""
    decision = mcdc.parse_decision(text)
    rows = mcdc.truth_table(decision)
    return decision, rows, mcdc.independence_pairs(decision, rows, mode)


def uncovered(pairs, tests, conditions=None):
    """Conditions that have no independence pair made of two of `tests`."""
    selected = {row(t) for t in tests}
    return {c for c in (conditions or pairs)
            if not any(i in selected and j in selected for i, j in pairs[c])}


def lower_bound(mode, conditions):
    """[S2] section 5.1, Theorem 1 (unique-cause: N + 1) and Theorem 4
    (masking: RUTW(2*SQRT(M)))."""
    if conditions == 0:
        return 0
    if mode == "unique-cause":
        return conditions + 1
    return math.ceil(2 * math.sqrt(conditions))


ALL_EXPRESSIONS = []        # every expression of the suite, for the generic checks


def case(text):
    ALL_EXPRESSIONS.append(text)
    return text


# ---------------------------------------------------------------------------
# [S1] section 3.1 - MC/DC building blocks
# ---------------------------------------------------------------------------

AND3 = case("D = A and B and C")
OR3 = case("D = A or B or C")
XOR2 = case("C = A != B")
NOT1 = case("B = not A")


class S1BuildingBlocks(unittest.TestCase):

    def check_minimum(self, text, mode, expected_rows):
        decision, rows, pairs = exact(text, mode)
        selected, _, optimal = mcdc.minimal_mcdc_set(pairs, forest_bound=mode == "unique-cause")
        self.assertTrue(optimal)
        self.assertEqual(selected, {row(t) for t in expected_rows})

    def test_and_gate(self):
        """[S1] 3.1.1 and Table 5, p.16: an n-input and gate needs a specific
        set of n+1 tests: all inputs true, and each input exclusively false."""
        for mode in ("unique-cause", "masking"):
            with self.subTest(mode=mode):
                self.check_minimum(AND3, mode, ["TTT", "FTT", "TFT", "TTF"])
                rows = mcdc.truth_table(mcdc.parse_decision(AND3))
                for t, out in zip(["TTT", "FTT", "TFT", "TTF"], "TFFF"):
                    self.assertEqual(rows[row(t)][1], out == "T")

    def test_or_gate(self):
        """[S1] 3.1.2 and Table 6, p.16-17: an n-input or gate needs a specific
        set of n+1 tests: all inputs false, and each input exclusively true."""
        for mode in ("unique-cause", "masking"):
            with self.subTest(mode=mode):
                self.check_minimum(OR3, mode, ["FFF", "TFF", "FTF", "FFT"])
                rows = mcdc.truth_table(mcdc.parse_decision(OR3))
                for t, out in zip(["FFF", "TFF", "FTF", "FFT"], "FTTT"):
                    self.assertEqual(rows[row(t)][1], out == "T")

    def test_xor_gate(self):
        """[S1] 3.1.3 and Table 7, p.17: for a two-input xor any combination of
        three of the four tests provides MC/DC; three tests are the minimum."""
        table7 = {1: "TT", 2: "TF", 3: "FT", 4: "FF"}
        outputs = {1: "F", 2: "T", 3: "T", 4: "F"}
        for mode in ("unique-cause", "masking"):
            with self.subTest(mode=mode):
                decision, rows, pairs = exact(XOR2, mode)
                for n, t in table7.items():
                    self.assertEqual(rows[row(t)][1], outputs[n] == "T")
                for combo in ((1, 2, 3), (1, 2, 4), (1, 3, 4), (2, 3, 4)):
                    self.assertEqual(uncovered(pairs, [table7[n] for n in combo]), set())
                selected, _, optimal = mcdc.minimal_mcdc_set(
                    pairs, forest_bound=mode == "unique-cause")
                self.assertEqual(len(selected), 3)
                self.assertTrue(optimal)

    def test_not_gate(self):
        """[S1] 3.1.4, p.17-18: input false -> output true, input true ->
        output false."""
        for mode in ("unique-cause", "masking"):
            with self.subTest(mode=mode):
                decision, rows, pairs = exact(NOT1, mode)
                self.assertEqual(rows[row("F")][1], True)
                self.assertEqual(rows[row("T")][1], False)
                self.check_minimum(NOT1, mode, ["F", "T"])


# ---------------------------------------------------------------------------
# [S1] sections 3.2 and 3.3 - worked examples (masking MC/DC, gate analysis)
# ---------------------------------------------------------------------------

EX1 = case("A = (B and C) or D")
EX2 = case("Z = (A or B) and (C or D)")
EX3 = case("Z = (A and not B) or (C != D)")       # xor written as !=
EX33A = case("Z = (A and not B) or (C or D)")
EX33B = case("Start_GT = Maint_Rqst and Maint_Valid and WOW and not (Engine_1_On or Engine_2_On)")
EX33C = case("WOW = (Squat_L and Squat_R) or (Airspeed_lt_40 and Airspeed_Valid)")
EX33D = case("Gain_select = Air_Data_Valid and In_Air")


class S1WorkedExamples(unittest.TestCase):

    def check_outputs(self, rows, tests, outputs):
        for t, out in zip(tests, outputs):
            self.assertEqual(rows[row(t)][1], out == "T", t)

    def test_example_1(self):
        """[S1] 3.2, Tables 11, 15, 16, p.25-29: A := (B and C) or D.
        Test cases 1, 2, 3 and 5 satisfy MC/DC; test case 4 does not
        contribute. Only test cases 1, 2 and 5 are valid for the and gate
        (3 and 4 are masked by D = true)."""
        tc = {1: "TTF", 2: "FTF", 3: "FTT", 4: "TTT", 5: "TFF"}
        decision, rows, pairs = exact(EX1, "masking")
        self.check_outputs(rows, [tc[n] for n in (1, 2, 3, 4, 5)], "TFTTF")
        self.assertEqual(uncovered(pairs, [tc[n] for n in (1, 2, 3, 5)]), set())
        self.assertEqual(uncovered(pairs, list(tc.values())), set())
        # the and gate inputs B and C: no valid pair inside the 5 tests uses 3 or 4
        inside = {row(t) for t in tc.values()}
        for cond in ("B", "C"):
            used = {r for p in pairs[cond] if set(p) <= inside for r in p}
            self.assertTrue(used <= {row(tc[1]), row(tc[2]), row(tc[5])}, cond)

    def test_example_2_and_2a(self):
        """[S1] 3.3, Tables 17-20, p.29-31: Z := (A or B) and (C or D).
        Example 2's tests provide (masking) MC/DC with the independence pairs
        of Table 20; example 2A (test 2 changed to TFFT) also provides MC/DC
        and is the only one that complies with unique-cause."""
        ex2 = ["FFTF", "FTFT", "TFFF", "FTTF", "TFTF"]
        ex2a = ["FFTF", "TFFT", "TFFF", "FTTF", "TFTF"]
        table20_ex2 = {"A": ("FFTF", "TFTF"), "B": ("FFTF", "FTTF"),
                       "C": ("TFFF", "TFTF"), "D": ("FTFT", "TFFF")}
        table20_ex2a = {"A": ("FFTF", "TFTF"), "B": ("FFTF", "FTTF"),
                        "C": ("TFFF", "TFTF"), "D": ("TFFT", "TFFF")}
        decision, rows, masking = exact(EX2, "masking")
        self.check_outputs(rows, ex2, "FTFTT")
        self.assertEqual(rows[row("TFFT")][1], True)
        self.assertEqual(uncovered(masking, ex2), set())
        self.assertEqual(uncovered(masking, ex2a), set())
        for cond, (a, b) in table20_ex2.items():
            self.assertIn(pair(a, b), masking[cond], cond)
        for cond, (a, b) in table20_ex2a.items():
            self.assertIn(pair(a, b), masking[cond], cond)

        _, _, unique = exact(EX2, "unique-cause")
        self.assertEqual(uncovered(unique, ex2a), set())
        self.assertNotEqual(uncovered(unique, ex2), set())
        for cond, (a, b) in table20_ex2a.items():
            self.assertIn(pair(a, b), unique[cond], cond)

    def test_example_3(self):
        """[S1] 3.3, Tables 21-22, p.32-34: Z := (A and not B) or (C xor D).
        The 5 tests of Table 21 miss the and gate case "A false, not B true";
        test cases 1, 2, 4, 5 and (FFTT) provide MC/DC."""
        tc = {1: "TTFF", 2: "TFFF", 3: "FTFF", 4: "FTFT", 5: "FTTF"}
        decision, rows, pairs = exact(EX3, "masking")
        self.check_outputs(rows, [tc[n] for n in (1, 2, 3, 4, 5)], "FTFTT")
        self.assertEqual(uncovered(pairs, list(tc.values())), {"A"})
        self.assertEqual(uncovered(pairs, [tc[1], tc[2], tc[4], tc[5], "FFTT"]), set())

    def test_exercise_3_3a(self):
        """[S1] Exercise 3.3a p.34, solution Appendix A p.65-66:
        Z := (A and not B) or (C or D) with the tests of Table 21: "a test
        case is still needed where the and gate has A false and not B true",
        and the tests do not detect that or2 should have been an xor.
        (The solution's last sentence, "1, 2, 4, and 5 plus (FFTT) provide
        MC/DC for example 3", is about example 3, tested above.)"""
        tc = {1: "TTFF", 2: "TFFF", 3: "FTFF", 4: "FTFT", 5: "FTTF"}
        decision, rows, pairs = exact(EX33A, "masking")
        self.assertEqual(uncovered(pairs, list(tc.values())), {"A"})
        ex3_rows = mcdc.truth_table(mcdc.parse_decision(EX3))
        for t in tc.values():
            self.assertEqual(rows[row(t)][1], ex3_rows[row(t)][1], t)

    def test_exercise_3_3b(self):
        """[S1] Exercise 3.3b p.34, solution Appendix A p.67-68 (ground test):
        the testing of the or gate is incomplete (case FT missing), i.e.
        Engine_2_On is not shown; the and and not gates are covered."""
        tests = ["TTTFF", "FTTFF", "TFTFF", "TTTTT", "TTTTF", "TTFFF"]
        decision, rows, pairs = exact(EX33B, "masking")
        self.check_outputs(rows, tests, "TFFFFF")
        self.assertEqual(uncovered(pairs, tests), {"Engine_2_On"})

    def test_exercise_3_3c(self):
        """[S1] Exercise 3.3c p.35, solution Appendix A p.68-69 (weight on
        wheels). The relational condition (Airspeed < 40.0) is the Boolean
        input Airspeed_lt_40 (35 knots -> T, 45 knots -> F). Solution: the
        and1 gate case FT is missing (Squat_L not shown); and2, or and the
        comparator are covered."""
        # Squat_L, Squat_R, Airspeed < 40, Airspeed_Valid
        tests = ["TTTT", "FTTT", "TFFT", "TFTF", "TTFF"]
        decision, rows, pairs = exact(EX33C, "masking")
        self.check_outputs(rows, tests, "TTFFT")
        self.assertEqual(uncovered(pairs, tests), {"Squat_L"})

    def test_exercise_3_3d(self):
        """[S1] Exercise 3.3d p.35-36, solution Appendix A p.69-70 (gains):
        Air_Data_Valid and In_Air: the three tests TT, FT, TF show MC/DC; the
        first two alone are not sufficient."""
        decision, rows, pairs = exact(EX33D, "masking")
        self.assertEqual(uncovered(pairs, ["TT", "FT", "TF"]), set())
        self.assertNotEqual(uncovered(pairs, ["TT", "FT"]), set())


# ---------------------------------------------------------------------------
# [S2] section 3 - definitions and graph-coloring examples
# ---------------------------------------------------------------------------

S2_A_OR_BC = case("F = A or (B and C)")
S2_FIG8 = case("F = A and (B != (C or D))")      # B xor (C or D)
S2_FIG9 = case("F = A and (B == (C or D))")      # B = (C or D)
S2_FIG10 = case("F = (A and B) or (A and C) or (B and C)")


class S2Definitions(unittest.TestCase):

    def test_section_3_1_1_unique_cause_pairs(self):
        """[S2] 3.1.1, p.15: for A or (B and C), unique-cause gives exactly
        three independence pairs for A: (0:FFF, 4:TFF), (1:FFT, 5:TFT),
        (2:FTF, 6:TTF)."""
        _, _, pairs = exact(S2_A_OR_BC, "unique-cause")
        self.assertEqual(sorted(pairs["A"]), [(0, 4), (1, 5), (2, 6)])

    def test_section_3_1_1_masking_pairs(self):
        """[S2] 3.1.1, p.15: masking MC/DC allows B and C to change between
        (FF), (FT), (TF) while A is toggled: exactly nine pairs for A."""
        _, _, pairs = exact(S2_A_OR_BC, "masking")
        expected = sorted((f, t) for f in (0, 1, 2) for t in (4, 5, 6))
        self.assertEqual(sorted(pairs["A"]), expected)

    def test_figure_6(self):
        """[S2] 3.1.2, Figure 6, p.17-18: A or (B and C), tests 2:(FTF) and
        5:(TFT): the influence set is (A) only, although all three conditions
        changed."""
        _, _, pairs = exact(S2_A_OR_BC, "masking")
        self.assertIn(pair("FTF", "TFT"), pairs["A"])
        self.assertNotIn(pair("FTF", "TFT"), pairs["B"])
        self.assertNotIn(pair("FTF", "TFT"), pairs["C"])

    def test_figures_8_and_9(self):
        """[S2] 3.1.2, Figures 8 and 9, p.18-19: tests 10:(TFTF) and 13:(TTFT)
        show the independence of B in A and (B xor (C or D)) and in
        A and (B = (C or D))."""
        for text in (S2_FIG8, S2_FIG9):
            with self.subTest(text=text):
                _, _, pairs = exact(text, "masking")
                self.assertIn(pair("TFTF", "TTFT"), pairs["B"])

    def test_figure_10_coupled(self):
        """[S2] 3.1.2, Figure 10, p.19: (A and B) or (A and C) or (B and C),
        tests 4:(TFF) and 6:(TTF) show the independence of the first
        occurrence of B."""
        decision, _, pairs = exact(S2_FIG10, "masking")
        self.assertEqual(decision.conditions, ["A#1", "B#1", "A#2", "C#1", "B#2", "C#2"])
        self.assertIn(pair("TFF", "TTF"), pairs["B#1"])

    def test_section_3_2_1_coupled_unique_cause(self):
        """[S2] 3.2.1, p.20: with unique-cause, no coverage set is possible for
        strongly coupled conditions. Every condition of the Figure 10
        expression is coupled."""
        _, _, pairs = exact(S2_FIG10, "unique-cause")
        self.assertEqual({c: p for c, p in pairs.items() if p}, {})


# ---------------------------------------------------------------------------
# [S2] sections 3.2.2, 5.1 and 7.1 - Unique-Cause + Masking MC/DC
# ---------------------------------------------------------------------------
#
# [S2] 3.2.2 (p.20): a unique cause for every uncoupled condition; for a
# strongly coupled condition, masking allowed for that condition only, all
# other conditions remaining fixed. [S2] 5.1 (p.28-29) and 7.1 (p.54-58)
# state it on the n-cube of the inputs: an "edge" transition (the two tests
# differ in just one value) is the only one allowed by the unique-cause
# forms, and a Unique-Cause + Masking coverage set exists when every
# condition has an edge independence pair.
#
# Tables 32-35 (p.55-58) list every independence pair of four expressions
# with its transition type. Transcribed below: "E" = Edge, "D" = Face or
# Internal Diagonal. Rows are numbered as in the report (A = most
# significant bit). In Table 34, the pair (4, 5) is printed on the line of
# "C (1st occurrence)" (the text layer adds a stray "B" to that label).

S2_T32 = case("F = A and (B or C)")                 # also Table 14 (5.1, p.29)
S2_T33 = case("F = (A and B) or (A and C)")
S2_T34 = case("F = (A and not B and C) or (A and B and not C) or (A and B and C)")
S2_T35 = case("F = (A and B) or (not A and C)")
S2_FIG40 = case("F = (A and B) or (A and not B)")
S2_FIG41 = case("F = (not A and not B) or (not A and B) or (A and not B)")

S2_TABLES = {
    S2_T32: {"A": [(1, 5, "E"), (1, 6, "D"), (1, 7, "D"), (2, 5, "D"), (2, 6, "E"),
                   (2, 7, "D"), (3, 5, "D"), (3, 6, "D"), (3, 7, "E")],
             "B": [(4, 6, "E")],
             "C": [(4, 5, "E")]},
    S2_T33: {"A#1": [(2, 6, "E"), (3, 6, "D")],
             "B": [(4, 6, "E")],
             "A#2": [(1, 5, "E"), (3, 5, "D")],
             "C": [(4, 5, "E")]},
    S2_T34: {"A#1": [(1, 5, "E")], "B#1": [], "C#1": [(4, 5, "E")],
             "A#2": [(2, 6, "E")], "B#2": [(4, 6, "E")], "C#2": [],
             "A#3": [(3, 7, "E")], "B#3": [], "C#3": []},
    S2_T35: {"A#1": [(2, 6, "E"), (2, 7, "D")],
             "B": [(4, 6, "E"), (4, 7, "D"), (5, 6, "D"), (5, 7, "E")],
             "A#2": [(1, 5, "E"), (1, 3, "E")],
             "C": [(0, 1, "E"), (0, 3, "D"), (1, 2, "D"), (2, 3, "E")]},
}

# Printed pairs that contradict the report's own definition
SOURCE_INCONSISTENT_PAIRS = {
    (S2_T35, "A#2", (1, 3)): "Table 35 prints (1, 3) as an Edge pair of A (2nd "
                             "occurrence), but rows 1 (FFT) and 3 (FTT) differ in B, "
                             "not A, and both give True: no form of 3.1.1 accepts it.",
}


def published(text, cond, kinds="ED"):
    """Pairs of S2_TABLES for `cond`, of the given transition kinds, without
    the inconsistent ones."""
    return sorted((i, j) for i, j, kind in S2_TABLES[text][cond]
                  if kind in kinds and (text, cond, (i, j)) not in SOURCE_INCONSISTENT_PAIRS)


class S2UniqueCauseMasking(unittest.TestCase):

    def test_tables_32_to_35_masking_pairs(self):
        """[S2] 7.1, Tables 32-35: every independence pair listed (any
        transition type) is exactly the tool's masking pair list. Exception:
        the inconsistent pair of Table 35 (see SOURCE_INCONSISTENT_PAIRS)
        must not be a pair; A (2nd occurrence) is then only checked to
        contain the other published pair (tests/SOURCES.md has a hand check
        of the tool's other pair, (3, 5))."""
        for text, table in S2_TABLES.items():
            decision, _, pairs = exact(text, "masking")
            self.assertEqual(decision.conditions, list(table))
            for cond in table:
                with self.subTest(text=text, cond=cond):
                    inconsistent = [p for t, c, p in SOURCE_INCONSISTENT_PAIRS
                                    if (t, c) == (text, cond)]
                    if inconsistent:
                        for p in inconsistent:
                            self.assertNotIn(p, pairs[cond])
                        self.assertLessEqual(set(published(text, cond)), set(pairs[cond]))
                    else:
                        self.assertEqual(sorted(pairs[cond]), published(text, cond))

    def test_tables_32_to_35_unique_cause_masking_pairs(self):
        """[S2] 7.1, Tables 32-35: the Unique-Cause + Masking pairs are
        exactly the Edge pairs of the tables."""
        for text, table in S2_TABLES.items():
            _, _, pairs = exact(text, "unique-cause+masking")
            for cond in table:
                with self.subTest(text=text, cond=cond):
                    self.assertEqual(sorted(pairs[cond]), published(text, cond, "E"))

    def test_section_7_1_coverage_sets(self):
        """[S2] 7.1, p.55-57: A and (B or C) has a Unique-Cause and a
        Unique-Cause + Masking coverage set; (A and B) or (A and C) and
        (A and B) or (not A and C) have no Unique-Cause test set but have a
        Unique-Cause + Masking and a Masking coverage set; the Table 34
        expression has no coverage set for any form."""
        expected = {S2_T32: {"unique-cause": True, "unique-cause+masking": True,
                             "masking": True},
                    S2_T33: {"unique-cause": False, "unique-cause+masking": True,
                             "masking": True},
                    S2_T35: {"unique-cause": False, "unique-cause+masking": True,
                             "masking": True},
                    S2_T34: {"unique-cause": False, "unique-cause+masking": False,
                             "masking": False}}
        for text, forms in expected.items():
            for mode, exists in forms.items():
                with self.subTest(text=text, mode=mode):
                    _, _, pairs = exact(text, mode)
                    self.assertEqual(all(pairs.values()), exists)

    def test_figure_40(self):
        """[S2] 7.1, Figure 40, p.54: (A and B) or (A and not B). The first
        occurrence of A is shown by the transition (1,1) - (0,1); the first
        occurrence of B can't be shown ((1,1) - (1,0) doesn't change the
        result); the expression can't be MC/DC tested under any definition."""
        for mode in mcdc.MODES:
            with self.subTest(mode=mode):
                _, _, pairs = exact(S2_FIG40, mode)
                if mode != "unique-cause":     # A is coupled: no unique-cause pair (3.2.1)
                    self.assertIn(pair("TT", "FT"), pairs["A#1"])
                self.assertEqual(pairs["B#1"], [])
                self.assertFalse(all(pairs.values()))

    def test_figure_41(self):
        """[S2] 7.1, Figure 41, p.54-55: (not A and not B) or (not A and B) or
        (A and not B). The second occurrence of A is shown by (0,1) - (1,1),
        the third occurrence of B by (1,0) - (1,1); the independence of the
        other conditions can't be shown."""
        for mode in ("unique-cause+masking", "masking"):
            with self.subTest(mode=mode):
                _, _, pairs = exact(S2_FIG41, mode)
                self.assertEqual({c: p for c, p in pairs.items() if p},
                                 {"A#2": [pair("FT", "TT")], "B#3": [pair("TF", "TT")]})

    def test_section_3_2_2_definition(self):
        """[S2] 3.2.2, p.20, on every expression of the suite:
        - an uncoupled condition requires a unique cause: its Unique-Cause +
          Masking pairs are exactly its Unique-Cause pairs;
        - a coupled condition may be masked for that condition only, all
          other conditions remaining fixed: its pairs are the Masking pairs
          where only its own input changes."""
        for text in ALL_EXPRESSIONS:
            decision, rows, ucm = exact(text, "unique-cause+masking")
            _, _, uc = exact(text, "unique-cause")
            _, _, masking = exact(text, "masking")
            for k, cond in enumerate(decision.conditions):
                with self.subTest(text=text, cond=cond):
                    v = decision.variable[k]
                    if decision.variable.count(v) == 1:
                        self.assertEqual(ucm[cond], uc[cond])
                    else:
                        only_v = [(i, j) for i, j in masking[cond]
                                  if [u for u in range(len(decision.names))
                                      if rows[i][0][u] != rows[j][0][u]] == [v]]
                        self.assertEqual(ucm[cond], only_v)

    def test_published_pairs_direct_check(self):
        """The direct check is_unique_cause_masking_pair accepts every Edge
        pair of Tables 32-35 and rejects every diagonal one, which
        is_masking_pair accepts."""
        for text in S2_TABLES:
            decision, rows, _ = exact(text, "masking")
            for cond in S2_TABLES[text]:
                for kinds, expected in (("E", True), ("D", False)):
                    for i, j in published(text, cond, kinds):
                        with self.subTest(text=text, cond=cond, pair=(i, j)):
                            x, y = rows[i][0], rows[j][0]
                            self.assertTrue(mcdc.is_masking_pair(decision, x, y, cond))
                            self.assertEqual(
                                mcdc.is_unique_cause_masking_pair(decision, x, y, cond),
                                expected)


# ---------------------------------------------------------------------------
# [S2] section 5.1 - minimum number of tests
# ---------------------------------------------------------------------------

class S2MinimumNumberOfTests(unittest.TestCase):

    def test_theorems_1_and_4(self):
        """[S2] 5.1, Theorems 1 and 4, p.27-33: a unique-cause set needs at
        least N + 1 tests, a masking set at least RUTW(2*SQRT(M)) tests, for
        N (M) conditions with an independence pair. Theorem 1 also covers
        Unique-Cause + Masking when each input occurs once. The minimal sets
        found by the tool (analyse_mcdc, with its own bounds) can never be
        smaller."""
        for text in ALL_EXPRESSIONS:
            for mode in mcdc.MODES:
                with self.subTest(text=text, mode=mode):
                    decision, _, pairs = exact(text, mode)
                    covered = [c for c, p in pairs.items() if p]
                    result = mcdc.analyse_mcdc(decision, mode)
                    self.assertEqual(set(result.choice), set(covered))
                    if mode == "unique-cause" or (
                            mode == "unique-cause+masking"
                            and len(set(decision.variable)) == len(decision.variable)):
                        bound = lower_bound("unique-cause", len(covered))
                    else:
                        # a Unique-Cause + Masking set is also a Masking set
                        bound = lower_bound("masking", len(covered))
                    self.assertGreaterEqual(len(result.tests), bound)

    def test_theorem_2_not_applied(self):
        """[S2] 5.1, Theorem 2, p.31 says a Unique-Cause + Masking set needs at
        least M + 1 tests for M occurrences. (B and not D) or (not B and D) has
        M = 4 occurrences but only 4 possible tests, and each occurrence has a
        Unique-Cause + Masking pair among them (hand check in
        tests/SOURCES.md; each pair is also checked here by the direct
        definition). The tool must therefore not use Theorem 2: it finds the
        4-test set and proves it minimal. Derived check, not a published
        result."""
        decision, rows, pairs = exact("F = (B and not D) or (not B and D)",
                                      "unique-cause+masking")
        self.assertEqual(len(decision.conditions), 4)
        for cond, plist in pairs.items():
            self.assertTrue(plist, cond)
            for i, j in plist:
                self.assertTrue(mcdc.is_unique_cause_masking_pair(
                    decision, rows[i][0], rows[j][0], cond))
        result = mcdc.analyse_mcdc(decision, "unique-cause+masking")
        self.assertEqual(len(result.tests), 4)
        self.assertTrue(result.optimal)
        self.assertLessEqual(result.lower_bound, 4)

    def test_minimal_sets_by_exhaustive_search(self):
        """Derived check, independent of the branch and bound: for every
        expression of the suite with at most 4 inputs, the smallest set found
        by trying every subset of rows (smallest first) has the same size as
        the tool's set, and the tool's lower bound is not above it. A bound
        that is too high would make the tool stop early and claim a
        non-minimal set as proven minimal."""
        for text in ALL_EXPRESSIONS:
            decision = mcdc.parse_decision(text)
            if len(decision.names) > 4:
                continue
            for mode in mcdc.MODES:
                with self.subTest(text=text, mode=mode):
                    _, rows, pairs = exact(text, mode)
                    needed = [p for p in pairs.values() if p]
                    smallest = next(
                        size for size in range(len(rows) + 1)
                        for subset in itertools.combinations(range(len(rows)), size)
                        if all(any(i in subset and j in subset for i, j in p)
                               for p in needed))
                    result = mcdc.analyse_mcdc(decision, mode)
                    self.assertEqual(len(result.tests), smallest)
                    self.assertTrue(result.optimal)
                    self.assertLessEqual(result.lower_bound, smallest)


# ---------------------------------------------------------------------------
# [S2] Appendix C - truth tables of real airborne expressions
# ---------------------------------------------------------------------------

def appendix_c():
    with DATA.open(encoding="utf-8") as f:
        lines = [line for line in f if not line.startswith("#")]
    return list(csv.DictReader(lines, delimiter="\t"))


# Entries whose published data contradicts itself or the printed expression
SOURCE_INCONSISTENT = {
    "C0604": "Profile 16:FFFTFFFF (string and number agree) has its only True on "
             "a row where 'not Bv and not Bv2' is False.",
    "C0793": "Section C.4.13 heading: printed string FFFFFFFTFTFTFTFF (340) does not "
             "match its number 341. This expression's truth table is 341.",
    "C0794": "Same C.4.13 heading (340 / 341). This expression's truth table is 340: "
             "the two expressions listed under the heading have different truth tables.",
    "C0839": "Profile number 28627 does not match the printed string "
             "FTTTFFFFFFFFFFFF (28672).",
}


class S2AppendixC(unittest.TestCase):

    def test_condition_counts(self):
        """[S2] Appendix C: each section heading states the number of
        conditions; the converted expressions must have that many inputs."""
        for entry in appendix_c():
            if entry["converted"]:
                with self.subTest(id=entry["id"], raw=entry["raw"]):
                    decision = mcdc.parse_decision(entry["converted"])
                    self.assertEqual(len(decision.names), int(entry["conditions"]))

    # Profiles checked by test_response_profiles (regression of the extraction)
    PROFILES_CHECKED = 878     # every entry with a profile except SOURCE_INCONSISTENT

    def test_response_profiles(self):
        """[S2] Appendix C, p.C-3: the response profile is the result column of
        the truth table, first condition = most significant bit. For every
        converted expression listed under a profile:
        - transcription (profiles without "-"): the profile number has a 1
          exactly where the string has T or t. Profiles with "-" (infeasible
          combinations) are listed under the number of the context-free
          function, which need not match the string (e.g. C0757);
        - result: the tool's truth table gives the same T/F at every position
          not marked "-";
        - short-circuit forms: the report prints some results in lower case
          without defining it. In every profile, the lower-case positions are
          exactly the rows that are not a distinct test under the report's
          numbering, which counts "a nonexecution due to short-circuit
          operators as 0" (glossary): rows giving True to an input that the
          test doesn't evaluate (tree.canonical). Checked as such."""
        checked = 0
        for entry in appendix_c():
            profile = entry["profile"]
            if not profile or entry["id"] in SOURCE_INCONSISTENT:
                continue
            with self.subTest(id=entry["id"], raw=entry["raw"]):
                if "-" not in profile:
                    bits = format(int(entry["profile_number"]), f"0{len(profile)}b")
                    for letter, bit in zip(profile, bits):
                        self.assertEqual(bit == "1", letter in "Tt", "transcription")
                decision = mcdc.parse_decision(entry["converted"])
                for (inputs, result), letter in zip(mcdc.truth_table(decision), profile):
                    if letter == "-":
                        continue
                    expected = "T" if result else "F"
                    if mcdc.canonical(decision, inputs) != inputs:
                        expected = expected.lower()
                    self.assertEqual(letter, expected, mcdc.row_number(inputs))
                checked += 1
        self.assertEqual(checked, self.PROFILES_CHECKED)


# ---------------------------------------------------------------------------
# [S2] section 6.1.1, Figures 28-30 - minimum test sets of the Appendix C
# expressions (context free), weighted by their occurrences
# ---------------------------------------------------------------------------
#
# For each number of conditions N (2 to 6) and each form, the figures give how
# many expression occurrences need a minimal coverage set of a given size
# ("0" = no coverage set). Transcribed from PDF pages 56-58 (report p.39-41).
# The labels are placed beside each dot; in Figure 30 three labels (344,
# 119, 16) print between two grid lines, and are placed by the text of
# 6.1.1: "the majority of test sets are still of size N + 1" (344 at 5 for
# N = 4, 119 at 6 for N = 5) and "A few expressions did go below the N + 1
# line ... (85 of 20,030)", which holds only with 16 at 6 for N = 6.

FIGURE_28 = {2: {3: 2255, 0: 7}, 3: {4: 653, 0: 32}, 4: {5: 382, 7: 2, 0: 7},
             5: {6: 120, 0: 11}, 6: {7: 78, 0: 1}}
FIGURE_29 = {2: {3: 2255, 4: 2, 0: 5}, 3: {4: 654, 5: 1, 6: 18, 0: 12},
             4: {5: 382, 6: 4, 7: 3, 10: 1, 0: 1}, 5: {6: 121, 7: 6, 8: 1, 9: 2, 0: 1},
             6: {7: 78, 9: 1}}
FIGURE_30 = {2: {3: 2255, 4: 2, 0: 5}, 3: {4: 671, 5: 1, 6: 9, 0: 4},
             4: {4: 46, 5: 344, 10: 1}, 5: {5: 9, 6: 119, 7: 2, 8: 1},
             6: {5: 14, 6: 16, 7: 49}}
FIGURES = {"unique-cause": FIGURE_28, "unique-cause+masking": FIGURE_29, "masking": FIGURE_30}


class S2Figures28To30(unittest.TestCase):
    """[S2] 6.1: "These expressions ... were exhaustively examined ... to
    determine the absolute smallest test set that would satisfy each of the
    MCDC definitions." The Appendix C expressions include 69 with
    short-circuit forms (and then / or else), evaluated as such by the
    report (6.1.1, comment on figure 28)."""

    @classmethod
    def setUpClass(cls):
        cls.sizes = {}             # (id, mode) -> size of the minimal set, 0 if none
        for entry in appendix_c():
            if 1 <= int(entry["conditions"]) <= 6:
                decision = mcdc.parse_decision(entry["converted"])
                for mode in mcdc.MODES:
                    result = mcdc.analyse_mcdc(decision, mode, time_limit=30)
                    assert result.optimal, (entry["id"], mode)
                    complete = all(s == "covered" for s in result.status.values())
                    cls.sizes[entry["id"], mode] = len(result.tests) if complete else 0

    def test_occurrence_totals(self):
        """The occurrences of the Appendix C expressions with N = 2 to 6
        conditions add up to the column totals of Figure 28. (N = 1 differs:
        see SOURCES.md.)"""
        totals = {}
        for entry in appendix_c():
            n = int(entry["conditions"])
            totals[n] = totals.get(n, 0) + int(entry["occurs"])
        for n, column in FIGURE_28.items():
            self.assertEqual(totals[n], sum(column.values()), n)

    def test_figures_28_29_30(self):
        """Figures 28 (unique-cause), 29 (unique-cause + masking) and 30
        (masking): for each N, the occurrences per minimal set size."""
        for mode, figure in FIGURES.items():
            for n, expected in figure.items():
                with self.subTest(mode=mode, conditions=n):
                    found = {}
                    for entry in appendix_c():
                        if int(entry["conditions"]) == n:
                            size = self.sizes[entry["id"], mode]
                            found[size] = found.get(size, 0) + int(entry["occurs"])
                    self.assertEqual(found, expected)

    def test_one_condition(self):
        """Figures 28-30, N = 1: every one-condition expression needs 2 tests
        in every form."""
        for entry in appendix_c():
            if int(entry["conditions"]) == 1:
                for mode in mcdc.MODES:
                    self.assertEqual(self.sizes[entry["id"], mode], 2, entry["id"])

    def test_section_6_1_1_statements(self):
        """[S2] 6.1.1, p.39-40: two four-condition expressions with
        short-circuit forms and coupled conditions require more than N + 1
        unique-cause tests (expression C0827, which occurs twice: 7 tests);
        with masking, 85 occurrences go below N + 1 and none below
        RUTW(2*SQRT(N))."""
        entry = next(e for e in appendix_c() if e["id"] == "C0827")
        self.assertEqual((entry["conditions"], entry["occurs"]), ("4", "2"))
        self.assertIn("and then", entry["converted"])
        self.assertEqual(self.sizes["C0827", "unique-cause"], 7)
        below, under_bound = 0, 0
        for entry in appendix_c():
            n = int(entry["conditions"])
            if 1 <= n <= 6:
                size = self.sizes[entry["id"], "masking"]
                if 0 < size < n + 1:
                    below += int(entry["occurs"])
                if 0 < size < lower_bound("masking", n):
                    under_bound += int(entry["occurs"])
        self.assertEqual(below, 85)
        self.assertEqual(under_bound, 0)


# ---------------------------------------------------------------------------
# Short-circuit forms: [S1] section 3.6, [S2] glossary, 3.1.2, Figures 5, 7
# ---------------------------------------------------------------------------

AND_THEN4 = case("Z = A and then B and then C and then D")
OR_ELSE4 = case("Z = A or else B or else C or else D")
S2_FIG7 = case("F = A or else (B and C)")
AND_THEN_OR_ELSE = case("Z = (A and then B) or else C")    # [S3] 4.3.2


def tests_x(texts):
    """[S1] notation with X ("don't care"): 'TXXF' -> canonical row (X = F,
    which is also [S2]'s numbering of a nonexecution as 0)."""
    return {row(t.replace("X", "F")) for t in texts}


class ShortCircuit(unittest.TestCase):

    def test_glossary_short_circuit_forms(self):
        """[S2] glossary, Short-Circuit Form Boolean Operator: and-then with a
        False left-hand side returns False without evaluating the right-hand
        side, otherwise returns the right-hand side; or-else with a True
        left-hand side returns True without evaluating the right-hand side,
        otherwise returns the right-hand side."""
        for text, skip in (("R = a and then b", False), ("R = a or else b", True)):
            decision = mcdc.parse_decision(text)
            for inputs, result in mcdc.truth_table(decision):
                with self.subTest(text=text, inputs=inputs):
                    a, b = inputs
                    self.assertEqual(result, skip if a == skip else b)
                    self.assertEqual(mcdc.executed_inputs(decision, inputs),
                                     (True, a != skip))

    def test_figure_5_tree_xor(self):
        """[S2] 3.1.2, Figure 5 (PDF p.34): tree_xor of F and T is T, of T
        and T or F and F is F, and anything with Not-Executed is F."""
        def masks(value):          # one node: (value bit, executed bit)
            return (0, 0) if value == "NE" else (int(value == "T"), 1)
        table = {("F", "F"): 0, ("F", "T"): 1, ("T", "F"): 1, ("T", "T"): 0}
        for lhs in ("F", "T", "NE"):
            for rhs in ("F", "T", "NE"):
                expected = table.get((lhs, rhs), 0)
                for value_ne in (0, 1):        # the value of a Not-Executed node doesn't matter
                    x = (value_ne, 0) if lhs == "NE" else masks(lhs)
                    y = (value_ne, 0) if rhs == "NE" else masks(rhs)
                    self.assertEqual(mcdc.tree_xor(x, y) & 1, expected, (lhs, rhs))

    def test_figure_7(self):
        """[S2] 3.1.2, Figure 7, p.18: A or else (B and C), tests 2:(FTF) and
        5:(TFT). (a) every node executed: OR F, A F, AND F, B T, C F;
        (b) OR T, A T, and AND, B, C not executed; (c) influence tree: OR T,
        A T, AND F, B F, C F. The influence set is (A)."""
        decision = mcdc.parse_decision(S2_FIG7)
        kinds = [kind for kind, _, _ in decision.nodes]
        self.assertEqual(kinds, ["cond", "cond", "cond", "and", "orelse"])
        a, b, c, and_, or_ = range(5)

        def annotations(masks):
            value, executed = masks
            return {n: ("T" if value >> n & 1 else "F") if executed >> n & 1 else "X"
                    for n in range(5)}
        mx = mcdc.node_masks(decision, vec("FTF"))
        my = mcdc.node_masks(decision, vec("TFT"))
        self.assertEqual(annotations(mx), {or_: "F", a: "F", and_: "F", b: "T", c: "F"})
        self.assertEqual(annotations(my), {or_: "T", a: "T", and_: "X", b: "X", c: "X"})
        changed = mcdc.tree_xor(mx, my)
        self.assertEqual({n: bool(changed >> n & 1) for n in range(5)},
                         {or_: True, a: True, and_: False, b: False, c: False})
        self.assertTrue(mcdc.is_masking_pair(decision, vec("FTF"), vec("TFT"), "A"))

    def test_example_7(self):
        """[S1] 3.6, Example 7, p.43-44, Z := A and then B and then C and then
        D. Table 29 (TTTT, TTTF, TTFT, TFTT, FTTT) provides MC/DC, with no
        difference between the and gate and the and then gate; Table 31
        (TTTT, TTTF, TTFF, TFFF, FFFF) also provides MC/DC, because the
        operands are evaluated as short circuit logic."""
        table29 = ["TTTT", "TTTF", "TTFT", "TFTT", "FTTT"]
        table31 = ["TTTT", "TTTF", "TTFF", "TFFF", "FFFF"]
        for text, table in ((AND_THEN4, table29), ("Z = A and B and C and D", table29),
                            (AND_THEN4, table31)):
            with self.subTest(text=text, table=table):
                decision, rows, pairs = exact(text, "masking")
                self.assertEqual([rows[row(t)][1] for t in table], [True] + [False] * 4)
                # each test as the tool numbers it (inputs not evaluated -> F)
                tests = {mcdc.row_number(mcdc.canonical(decision, vec(t))) for t in table}
                self.assertEqual({c for c in pairs
                                  if not any(i in tests and j in tests for i, j in pairs[c])},
                                 set())

    def test_tables_32_and_33(self):
        """[S1] 3.6, Tables 32 and 33, p.45: the minimum tests for a
        four-input and gate (A and then B and then C and then D) and or gate
        (A or else B or else C or else D) with short circuit logic, X being
        "don't care"."""
        for text, expected in ((AND_THEN4, ["TTTT", "FXXX", "TFXX", "TTFX", "TTTF"]),
                               (OR_ELSE4, ["FFFF", "TXXX", "FTXX", "FFTX", "FFFT"])):
            with self.subTest(text=text):
                decision = mcdc.parse_decision(text)
                result = mcdc.analyse_mcdc(decision, "masking")
                self.assertTrue(result.optimal)
                self.assertEqual(set(result.tests), tests_x(expected))
                for t in expected:     # X exactly where the input is not evaluated
                    inputs = vec(t.replace("X", "F"))
                    self.assertEqual(mcdc.executed_inputs(decision, inputs),
                                     tuple(c != "X" for c in t))
                # Derived: with X as don't care, these five tests are all the
                # distinct tests of the gate (every other row of the 16 only
                # differs from one of them in an X position)
                rows = mcdc.truth_table(decision)
                self.assertEqual(set(mcdc.test_rows(decision, rows)), tests_x(expected))

    def test_ar0654_section_4_3_2(self):
        """[S3] 4.3.2, p.19-20: for (A and then B) or else C, "A minimum of
        four test cases are needed to achieve MCDC for this expression". The
        three tests the report gives for the other reading (each
        short-circuited condition as a separate decision, DO-248B DP #13)
        are then not an MC/DC set. The report names no form, so the minimum
        is checked in the three forms."""
        texts = (AND_THEN_OR_ELSE, "Z = (A and B) or C")
        for text in texts:
            decision = mcdc.parse_decision(text, short_circuit=True)
            for mode in mcdc.MODES:
                with self.subTest(text=text, mode=mode):
                    result = mcdc.analyse_mcdc(decision, mode)
                    self.assertTrue(result.optimal)
                    self.assertEqual(len(result.tests), 4)
        # (A=F, B=?, C=F), (A=T, B=F, C=T), (A=T, B=T, C=?), with ? not
        # evaluated, numbered as F (see Notation in SOURCES.md)
        decision = mcdc.parse_decision(AND_THEN_OR_ELSE)
        rows = mcdc.truth_table(decision)
        for mode in mcdc.MODES:
            with self.subTest(mode=mode, tests="the report's three tests"):
                pairs = mcdc.independence_pairs(decision, rows, mode)
                self.assertTrue(uncovered(pairs, ["FFF", "TFT", "TTF"]))

    def test_same_definitions_without_short_circuit(self):
        """The definitions are written on the influence tree ([S2] 3.1.2).
        Without short-circuit forms they must equal the direct statements:
        unique-cause = only the condition changes and the result changes
        ([S2] 3.1.1); unique-cause + masking = a masking pair where only the
        condition's input changes (an edge, [S2] 5.1 and 7.1). Checked on
        every expression of the suite and of Appendix C with up to 5 inputs."""
        texts = list(ALL_EXPRESSIONS) + [e["converted"] for e in appendix_c()
                                         if int(e["conditions"]) <= 5]
        for text in texts:
            decision = mcdc.parse_decision(text)
            if decision.short_circuit or len(decision.names) > 5:
                continue
            rows = mcdc.truth_table(decision)
            uc = mcdc.independence_pairs(decision, rows, "unique-cause")
            ucm = mcdc.independence_pairs(decision, rows, "unique-cause+masking")
            masking = mcdc.independence_pairs(decision, rows, "masking")
            for k, cond in enumerate(decision.conditions):
                with self.subTest(text=text, cond=cond):
                    direct_uc, edges = [], []
                    for i, j in itertools.combinations(range(len(rows)), 2):
                        (xi, ri), (xj, rj) = rows[i], rows[j]
                        ci = [xi[v] for v in decision.variable]
                        cj = [xj[v] for v in decision.variable]
                        if ri != rj and [n for n in range(len(ci)) if ci[n] != cj[n]] == [k]:
                            direct_uc.append((i, j))
                    for i, j in masking[cond]:
                        if [u for u in range(len(decision.names))
                                if rows[i][0][u] != rows[j][0][u]] == [decision.variable[k]]:
                            edges.append((i, j))
                    self.assertEqual(sorted(uc[cond]), direct_uc)
                    self.assertEqual(sorted(ucm[cond]), sorted(edges))

    def test_short_circuit_option(self):
        """Tool requirement (input language): with short_circuit=True every
        and / or (also et / ou / && / ||) is a short-circuit form, i.e. the
        same tree as written with and then / or else."""
        explicit = mcdc.parse_decision("Z = (a and then b) or else not (c or else d)")
        for text in ("Z = (a and b) or not (c or d)", "Z = (a && b) || !(c || d)",
                     "Z = (a et b) ou non (c ou d)"):
            with self.subTest(text=text):
                decision = mcdc.parse_decision(text, short_circuit=True)
                self.assertEqual(decision.nodes, explicit.nodes)
                self.assertTrue(decision.short_circuit)
                self.assertFalse(mcdc.parse_decision(text).short_circuit)


# ---------------------------------------------------------------------------
# Input syntax: && and || are the Boolean and / or
# ---------------------------------------------------------------------------

class InputSyntax(unittest.TestCase):
    """Tool requirement, not a published MC/DC result: an expression written
    with &&, || and ! is the same decision as with and / or / not. The
    expected results are those of the keyword form, checked above against
    [S1]/[S2]."""

    def test_symbols_equal_keywords(self):
        for text in ALL_EXPRESSIONS:
            # and then / or else have no symbol: they are kept
            symbols = re.sub(r"\bor\b(?! else)", "||", re.sub(r"\band\b(?! then)", "&&", text))
            symbols = re.sub(r"\bnot\s+", "!", symbols)
            if symbols == text:
                continue
            for mode in mcdc.MODES:
                with self.subTest(text=symbols, mode=mode):
                    d1, rows1, pairs1 = exact(text, mode)
                    d2, rows2, pairs2 = exact(symbols, mode)
                    self.assertEqual(d2.conditions, d1.conditions)
                    self.assertEqual(rows2, rows1)
                    self.assertEqual(pairs2, pairs1)

    def test_not_binds_like_c(self):
        """As in C, ! applies to the name or parenthesis right after it,
        before any other operator: !a == b is (!a) == b."""
        for symbols, keywords in (("R = !a == b", "R = (not a) == b"),
                                  ("R = b != !c", "R = b != (not c)"),
                                  ("R = !(a && b) || !!c", "R = (not (a and b)) or not (not c)"),
                                  # also right after the short-circuit forms
                                  ("R = a and then !b", "R = a and then (not b)"),
                                  ("R = a or else !(b && c)", "R = a or else (not (b and c))")):
            with self.subTest(text=symbols):
                self.assertEqual(mcdc.parse_decision(symbols).nodes,
                                 mcdc.parse_decision(keywords).nodes)

    def test_xor_spellings_equal_not_equal(self):
        """xor, ^ and ouexclusif (in any case) are the xor operator !=: every
        published case written with != (XOR2 [S1] Table 7, EX3, S2_FIG8)
        gives the same conditions, truth table and pairs with each spelling."""
        cases = [text for text in ALL_EXPRESSIONS if "!=" in text]
        self.assertGreaterEqual(len(cases), 3)
        for text in cases:
            for spelling in ("xor", "^", "ouexclusif", "OuExclusif"):
                written = text.replace("!=", spelling)
                for mode in mcdc.MODES:
                    with self.subTest(text=written, mode=mode):
                        d1, rows1, pairs1 = exact(text, mode)
                        d2, rows2, pairs2 = exact(written, mode)
                        self.assertEqual(d2.nodes, d1.nodes)
                        self.assertEqual(d2.conditions, d1.conditions)
                        self.assertEqual(rows2, rows1)
                        self.assertEqual(pairs2, pairs1)

    def test_xor_precedence(self):
        """^ (xor, ouexclusif) binds as != does: tighter than not, and, or;
        ! still applies to the next operand only; a ^ b ^ c is (a ^ b) ^ c."""
        for written, meaning in (("R = a ^ b ^ c", "R = (a != b) != c"),
                                 ("R = a xor b ouexclusif c", "R = (a != b) != c"),
                                 ("R = (a ^ b) == c", "R = (a != b) == c"),
                                 ("R = a xor (b == c)", "R = a != (b == c)"),
                                 ("R = a and b xor c", "R = a and (b != c)"),
                                 ("R = a ^ b || c", "R = (a != b) or c"),
                                 ("R = a and then b ^ c", "R = a and then (b != c)"),
                                 ("R = not a xor b", "R = not (a != b)"),
                                 ("R = !a ^ b", "R = (not a) != b"),
                                 ("R = a ouexclusif !b", "R = a != (not b)")):
            with self.subTest(text=written):
                self.assertEqual(mcdc.parse_decision(written).nodes,
                                 mcdc.parse_decision(meaning).nodes)

    def test_xor_with_comparison_needs_parentheses(self):
        """Python reads a ^ b == c as (a ^ b) == c and C as a ^ (b == c): a
        xor operand of == or != without parentheses is rejected. Any other
        operator is rejected with the expression that uses it."""
        for text in ("R = a ^ b == c", "R = a == b xor c", "R = a != b ouexclusif c",
                     "R = a == !b ^ c", "R = (a) ^ b == c", "R = a == (b ^ c) ^ d"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "mixes xor with == or !="):
                    mcdc.parse_decision(text)
        for text, quoted in (("R = a & b", "a & b"), ("R = a + b", "a + b"),
                             ("R = -a", "-a"), ("R = ~a", "~a"), ("R = a < b", "a < b"),
                             ("R = a ^ b + c", "b + c")):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError,
                                            re.escape(f"unsupported syntax: '{quoted}'")):
                    mcdc.parse_decision(text)

    def test_display_keeps_meaning(self):
        """The decision text shown in the report is written with the
        spellings the user typed, and keeps the parentheses that the
        precedence of C needs: read again, it is the same decision."""
        for text, shown in (("R = !(a == b)", "!(a == b)"), ("R = !(a ^ b)", "!(a ^ b)"),
                            ("R = !a == b", "(!a) == b"), ("R = not (a == b)", "not (a == b)"),
                            ("R = (a xor b) == c", "(a xor b) == c"),
                            ("R = a ^ (b != c)", "a ^ (b != c)"),
                            ("R = a ouexclusif b", "a ouexclusif b")):
            with self.subTest(text=text):
                self.assertEqual(mcdc.parse_decision(text).text, shown)
        extra = ["R = !(a && b) == c", "R = !(a != b) ^ !c", "R = non (a ouexclusif b) et c",
                 "R = (a ^ b) != (c xor d)", "R = a or else !(b ^ c)"]
        for text in ALL_EXPRESSIONS + extra:
            decision = mcdc.parse_decision(text)
            if any("#" in label for label in decision.conditions):
                continue                    # a#1 can't be read again as a name
            with self.subTest(text=text):
                again = mcdc.parse_decision(f"{decision.output} = {decision.text}")
                self.assertEqual(again.nodes, decision.nodes)


# ---------------------------------------------------------------------------
# Pair-search engine: the published cases again, without the truth table
# ---------------------------------------------------------------------------

class PairSearchEngine(unittest.TestCase):
    """Every published case above, run with the pair-search engine forced
    (max_exact=0): the conditions the sources show as coverable must be
    covered, by pairs that are valid by direct evaluation, and the conditions
    the sources show as impossible must be reported impossible."""

    def test_same_coverage_as_exact_engine(self):
        for text in ALL_EXPRESSIONS:
            for mode in mcdc.MODES:
                with self.subTest(text=text, mode=mode):
                    decision, rows, pairs = exact(text, mode)
                    result = mcdc.analyse_mcdc(decision, mode, max_exact=0)
                    self.assertEqual(result.engine, "pair-search")
                    for cond, plist in pairs.items():
                        expected = "covered" if plist else "impossible"
                        self.assertEqual(result.status[cond], expected, cond)
                    check = mcdc.PAIR_CHECK[mode]
                    for cond, (i, j) in result.choice.items():
                        self.assertTrue(check(decision, result.tests[i][0],
                                              result.tests[j][0], cond), cond)
                        self.assertIn((i, j), pairs[cond], cond)

    def test_section_3_1_1_choice_in_published_list(self):
        """[S2] 3.1.1: whatever pair the search picks for A must be one of the
        published pairs."""
        decision = mcdc.parse_decision(S2_A_OR_BC)
        published = {"unique-cause": {(0, 4), (1, 5), (2, 6)},
                     # A is uncoupled: unique cause required ([S2] 3.2.2)
                     "unique-cause+masking": {(0, 4), (1, 5), (2, 6)},
                     "masking": {(f, t) for f in (0, 1, 2) for t in (4, 5, 6)}}
        for mode, expected in published.items():
            with self.subTest(mode=mode):
                result = mcdc.analyse_mcdc(decision, mode, max_exact=0)
                self.assertIn(result.choice["A"], expected)

    def test_published_pairs_pass_direct_check(self):
        """The pairs published in [S1] Table 20 and [S2] Figures 6, 8, 9, 10
        must pass the direct pair check used by the pair-search engine."""
        cases = [(EX2, "D", "FTFT", "TFFF"), (EX2, "D", "TFFT", "TFFF"),
                 (EX2, "A", "FFTF", "TFTF"), (S2_A_OR_BC, "A", "FTF", "TFT"),
                 (S2_FIG8, "B", "TFTF", "TTFT"), (S2_FIG9, "B", "TFTF", "TTFT"),
                 (S2_FIG10, "B#1", "TFF", "TTF")]
        for text, cond, a, b in cases:
            with self.subTest(text=text, cond=cond):
                decision = mcdc.parse_decision(text)
                self.assertTrue(mcdc.is_masking_pair(decision, vec(a), vec(b), cond))


# ---------------------------------------------------------------------------
# Engine cross-check on the real expressions of [S2] Appendix C
# (the expressions are published; their MC/DC answer is not: see SOURCES.md)
# ---------------------------------------------------------------------------

class AppendixCCrossCheck(unittest.TestCase):

    EXACT_LIMIT = 8      # inputs up to which both engines are compared

    def test_engines_agree(self):
        """Up to EXACT_LIMIT inputs, both engines must agree on which
        conditions can be covered."""
        for entry in appendix_c():
            if not entry["converted"] or int(entry["conditions"]) > self.EXACT_LIMIT:
                continue
            decision = mcdc.parse_decision(entry["converted"])
            for mode in mcdc.MODES:
                with self.subTest(id=entry["id"], mode=mode):
                    reference = mcdc.analyse_mcdc(decision, mode, max_exact=self.EXACT_LIMIT)
                    search = mcdc.analyse_mcdc(decision, mode, max_exact=0)
                    self.assertEqual(reference.engine, "exact")
                    self.assertEqual(search.status, reference.status)

    def test_large_expressions(self):
        """Above EXACT_LIMIT inputs (up to 76 in Appendix C): every condition
        ends covered or proven impossible, and every chosen pair passes the
        direct check."""
        for entry in appendix_c():
            if not entry["converted"] or int(entry["conditions"]) <= self.EXACT_LIMIT:
                continue
            decision = mcdc.parse_decision(entry["converted"])
            for mode in mcdc.MODES:
                with self.subTest(id=entry["id"], mode=mode):
                    result = mcdc.analyse_mcdc(decision, mode, max_exact=0)
                    self.assertNotIn("unknown", result.status.values())
                    check = mcdc.PAIR_CHECK[mode]
                    for cond, (i, j) in result.choice.items():
                        self.assertTrue(check(decision, result.tests[i][0],
                                              result.tests[j][0], cond))


if __name__ == "__main__":
    unittest.main()
