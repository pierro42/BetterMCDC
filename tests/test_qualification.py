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

Test vectors are written as in the sources ("TFTF": first condition first)
and row numbers are computed from them: first input = most significant bit,
which is also S2's numbering (e.g. "4:(TFF)").

Run from the project folder:
    python -m unittest discover -s tests -v
"""

import csv
import itertools
import math
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
    "C0793": "Printed string FFFFFFFTFTFTFTFF does not match the profile number 341.",
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

    def test_response_profiles(self):
        """[S2] Appendix C, p.C-3: the response profile is the result column of
        the truth table. Every converted expression listed under a profile of
        only T/F must have exactly that truth table."""
        checked = 0
        for entry in appendix_c():
            profile = entry["profile"]
            if not entry["converted"] or not profile or set(profile) - set("TF"):
                continue
            if entry["id"] in SOURCE_INCONSISTENT:
                continue
            with self.subTest(id=entry["id"], raw=entry["raw"]):
                self.assertEqual(int(profile.replace("T", "1").replace("F", "0"), 2),
                                 int(entry["profile_number"]), "transcription")
                rows = mcdc.truth_table(mcdc.parse_decision(entry["converted"]))
                self.assertEqual("".join("T" if r else "F" for _, r in rows), profile)
                checked += 1
        self.assertGreater(checked, 600)


# ---------------------------------------------------------------------------
# Input syntax: && and || are the Boolean and / or
# ---------------------------------------------------------------------------

class InputSyntax(unittest.TestCase):
    """Tool requirement, not a published MC/DC result: an expression written
    with &&, || and ! is the same decision as with and / or / not. The
    expected results are those of the keyword form, checked above against
    [S1]/[S2]."""

    def test_symbols_equal_keywords(self):
        import re
        for text in ALL_EXPRESSIONS:
            symbols = re.sub(r"\bor\b", "||", re.sub(r"\band\b", "&&", text))
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
                                  ("R = !(a && b) || !!c", "R = (not (a and b)) or not (not c)")):
            with self.subTest(text=symbols):
                self.assertEqual(mcdc.parse_decision(symbols).nodes,
                                 mcdc.parse_decision(keywords).nodes)


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
