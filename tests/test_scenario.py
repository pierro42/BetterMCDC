# -*- coding: utf-8 -*-
"""
Tests of the test scenario generation (-gen_scen, mcdc/scenario.py).

These are tool requirement tests (template format and generated text), not
MC/DC oracles. The MC/DC test vectors used come from a published result:
for a 3-input and gate the minimal set is exactly TTT, FTT, TFT, TTF
([S1] NASA/TM-2001-210876, section 3.1.1, Table 5), so the whole expected
scenario text is fixed by the template below.

Run from the project folder:
    python -m unittest discover -s tests -v
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import mcdc  # noqa: E402

AND3 = "Z = a and b and c"

TEMPLATE = r"""
[variables]
NAME = "Uut"
FAMILY = 30

[settings]
STARTING_TEST_NUMBER = 5
TRUE = "TRUE"
FALSE = "FALSE"
OUTPUT_FILENAME = "Test_${NAME}_${FAMILY}_${output_name}.cpp"

[format]
TEST_PREAMBLE = '''// ${NAME} "${FAMILY}": ${expression}
'''
TEST_CASE_START = '''{ printf("Test %i\n", ${test_number}); // row #${row}
'''
TEST_CASE_INPUT_SET = '''  ${input_name} = ${input_value};
'''
TEST_CASE_OUTPUT_SET = '''  ${output_name} = ${output_inverse};
'''
TEST_CASE_PROCESS = '''  uut.process(); // costs $$0
'''
TEST_CASE_OUTPUT_CHECK = '''  CHECK(${output_name}, ${output_value});
'''
TEST_CASE_END = '''}
'''
TEST_EPILOGUE = '''// end
'''
"""

# S1 Table 5 set in truth-table order: FTT (#4), TFT (#6), TTF (#7), TTT (#8)
EXPECTED_AND3 = r"""// Uut "30": Z = a and b and c
{ printf("Test %i\n", 5); // row #4
  a = FALSE;
  b = TRUE;
  c = TRUE;
  Z = TRUE;
  uut.process(); // costs $0
  CHECK(Z, FALSE);
}
{ printf("Test %i\n", 6); // row #6
  a = TRUE;
  b = FALSE;
  c = TRUE;
  Z = TRUE;
  uut.process(); // costs $0
  CHECK(Z, FALSE);
}
{ printf("Test %i\n", 7); // row #7
  a = TRUE;
  b = TRUE;
  c = FALSE;
  Z = TRUE;
  uut.process(); // costs $0
  CHECK(Z, FALSE);
}
{ printf("Test %i\n", 8); // row #8
  a = TRUE;
  b = TRUE;
  c = TRUE;
  Z = FALSE;
  uut.process(); // costs $0
  CHECK(Z, TRUE);
}
// end
"""


class TemplateFiles(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, text, name="template.toml"):
        path = Path(self.dir.name) / name
        path.write_text(text, encoding="utf-8")
        return path

    def load(self, text):
        return mcdc.load_template(self.write(text))


class ScenarioText(TemplateFiles):
    def test_mcdc_scenario(self):
        """The S1 Table 5 set, rendered with the template, gives the exact
        expected text: order of the sections, one input line per input,
        numbering from STARTING_TEST_NUMBER, ${row}, inverse output, TRUE /
        FALSE texts, C braces, quotes, %, \\n and $$ kept literally."""
        decision = mcdc.parse_decision(AND3)
        analysis = mcdc.analyse_mcdc(decision, "masking")
        tests = [(i, *analysis.tests[i]) for i in analysis.tests]
        self.assertEqual([i + 1 for i, _, _ in tests], [4, 6, 7, 8])
        template = self.load(TEMPLATE)
        self.assertEqual(mcdc.render_scenario(template, decision, tests, AND3), EXPECTED_AND3)
        self.assertEqual(mcdc.output_filename(template, decision, AND3), "Test_Uut_30_Z.cpp")

    def test_full_truth_table_and_defaults(self):
        """Without --mcdc every row is a test case; omitted texts are empty,
        numbering starts at 1 and values are 1 / 0 by default."""
        decision = mcdc.parse_decision("Out = a or b")
        tests = [(i, *r) for i, r in enumerate(mcdc.truth_table(decision))]
        template = self.load("[settings]\nOUTPUT_FILENAME = 'x.txt'\n[format]\n"
                             "TEST_CASE_START = '${test_number}:'\n"
                             "TEST_CASE_INPUT_SET = '${input_value}'\n"
                             "TEST_CASE_OUTPUT_CHECK = '=${output_value}/${output_inverse} '\n")
        self.assertEqual(mcdc.render_scenario(template, decision, tests, "Out = a or b"),
                         "1:00=0/1 2:01=1/0 3:10=1/0 4:11=1/0 ")

    def test_expression_as_typed(self):
        """${expression} is the expression as the user wrote it (French /
        symbols kept), on one line."""
        text = "Out = (a || b)\n&& non c"
        decision = mcdc.parse_decision(text)
        template = self.load("[settings]\nOUTPUT_FILENAME = 'x'\n"
                             "[format]\nTEST_PREAMBLE = '${expression}'\n")
        self.assertEqual(mcdc.render_scenario(template, decision, [], text),
                         "Out = (a || b) && non c")


    def test_not_evaluated_inputs(self):
        """Short-circuit forms: an input that the test doesn't evaluate gets
        the NOT_EVALUATED text (by default the FALSE text). The test cases are
        [S1] 3.6 Table 32 for A and then B: TT, FX, TF."""
        text = "Z = A and then B"
        decision = mcdc.parse_decision(text)
        analysis = mcdc.analyse_mcdc(decision, "masking")
        tests = [(i, *analysis.tests[i]) for i in analysis.tests]
        base = ("[settings]\nOUTPUT_FILENAME = 'x'\nTRUE = 'T'\nFALSE = 'F'\n{extra}"
                "[format]\nTEST_CASE_INPUT_SET = '${{input_value}}'\n"
                "TEST_CASE_END = ' '\n")
        for extra, expected in (("", "FF TF TT "), ("NOT_EVALUATED = 'X'\n", "FX TF TT ")):
            with self.subTest(extra=extra):
                template = self.load(base.format(extra=extra))
                self.assertEqual(mcdc.render_scenario(template, decision, tests, text), expected)

    def test_tool_version_and_command(self):
        """${tool_version} is the tool version and ${tool_command} the
        command line given to render_scenario, in every text; OUTPUT_FILENAME
        can use ${tool_version} (IEC 61508-3 7.4.4.15: tool version and use
        recorded with each generated item)."""
        decision = mcdc.parse_decision(AND3)
        template = self.load("[settings]\nOUTPUT_FILENAME = 'v${tool_version}.cpp'\n"
                             "[format]\nTEST_PREAMBLE = '${tool_version}|${tool_command}|'\n"
                             "TEST_CASE_END = '${tool_version} '\n")
        tests = [(7, [True, True, True], True)]
        version = mcdc.__version__
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(mcdc.render_scenario(template, decision, tests, AND3, "main.py x"),
                         f"{version}|main.py x|{version} ")
        self.assertEqual(mcdc.render_scenario(template, decision, tests, AND3),
                         f"{version}||{version} ")
        self.assertEqual(mcdc.output_filename(template, decision, AND3), f"v{version}.cpp")


class TemplateErrors(TemplateFiles):
    """A wrong template is rejected when it is loaded, with the key named."""

    BASE = "[settings]\nOUTPUT_FILENAME = 'x'\n"

    def check(self, text, message):
        with self.assertRaisesRegex(ValueError, message):
            self.load(text)

    def test_unknown_placeholder(self):
        self.check(self.BASE + "[format]\nTEST_CASE_END = '${nope}'\n",
                   r"\[format\] TEST_CASE_END: unknown placeholder \$\{nope\}")

    def test_placeholder_out_of_scope(self):
        self.check(self.BASE + "[format]\nTEST_PREAMBLE = '${input_name}'\n",
                   r"TEST_PREAMBLE: \$\{input_name\} can only be used in TEST_CASE_INPUT_SET")
        self.check("[settings]\nOUTPUT_FILENAME = '${test_number}.cpp'\n",
                   r"OUTPUT_FILENAME: \$\{test_number\} can only be used in")
        self.check("[settings]\nOUTPUT_FILENAME = '${tool_command}.cpp'\n",
                   r"OUTPUT_FILENAME: \$\{tool_command\} can only be used in")

    def test_invalid_dollar(self):
        self.check(self.BASE + "[format]\nTEST_CASE_END = '''}\nprice $5'''\n",
                   r"TEST_CASE_END, line 2: invalid '\$'")

    def test_unknown_keys(self):
        self.check(self.BASE + "[format]\nTEST_CASE_BEGIN = 'x'\n",
                   r"\[format\] unknown key\(s\): TEST_CASE_BEGIN")
        self.check(self.BASE + "STARTING_NUMBER = 1\n",
                   r"\[settings\] unknown key\(s\): STARTING_NUMBER")
        self.check(self.BASE + "[formats]\n", r"unknown table\(s\): formats")

    def test_bad_values(self):
        self.check("[settings]\n", r"OUTPUT_FILENAME is missing")
        self.check(self.BASE + "STARTING_TEST_NUMBER = '1'\n", r"STARTING_TEST_NUMBER must be")
        self.check(self.BASE + "[variables]\nrow = 'x'\n", r"\[variables\] row: this name is")
        self.check(self.BASE + "[format]\nTEST_CASE_END = 3\n", r"TEST_CASE_END must be a text")

    def test_not_toml(self):
        self.check("TEST_CASE_START = f\"\"\"{ printf\"\"\"\n", r"not a valid TOML file")


class CommandLine(TemplateFiles):
    def run_main(self, *args, expression=AND3):
        command = [sys.executable, str(ROOT / "main.py")] + ([expression] if expression else [])
        return subprocess.run(command + list(args), cwd=self.dir.name,
                              capture_output=True, text=True)

    def test_gen_scen_writes_the_file(self):
        template = self.write(TEMPLATE)
        out = Path(self.dir.name) / "scenarios"          # created by the tool
        for flag in ("-gen_scen", "--gen-scen"):
            result = self.run_main("--mcdc", flag, str(template), "--output-dir", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"Scenario written to {out / 'Test_Uut_30_Z.cpp'} (4 test case(s))",
                          result.stdout)
            written = (out / "Test_Uut_30_Z.cpp").read_text(encoding="utf-8")
            self.assertEqual(written, EXPECTED_AND3)

    def test_version_and_command_recorded(self):
        """--version prints the tool version; the scenario records the
        version and the command line as typed (IEC 61508-3 7.4.4.15)."""
        result = self.run_main("--version", expression=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"main.py {mcdc.__version__}")
        template = self.write("[settings]\nOUTPUT_FILENAME = 'rec.txt'\n"
                              "[format]\nTEST_PREAMBLE = '${tool_version} ${tool_command}'\n")
        out = Path(self.dir.name) / "out"
        result = self.run_main("--mcdc", "-gen_scen", str(template), "--output-dir", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        quote = lambda path: f'"{path}"' if " " in str(path) else str(path)
        self.assertEqual((out / "rec.txt").read_text(encoding="utf-8"),
                         f'{mcdc.__version__} main.py "{AND3}" --mcdc -gen_scen '
                         f'{quote(template)} --output-dir {quote(out)}')

    def test_default_output_folder(self):
        """Without --output-dir the scenario goes to the 'output' folder next
        to main.py, whatever the current folder."""
        name = f"test_default_output_folder_{id(self)}.txt"
        target = ROOT / "output" / name
        self.addCleanup(lambda: target.unlink(missing_ok=True))
        template = self.write(f"[settings]\nOUTPUT_FILENAME = '{name}'\n"
                              "[format]\nTEST_EPILOGUE = 'end'\n")
        result = self.run_main("-gen_scen", str(template))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "end")
        self.assertFalse((Path(self.dir.name) / name).exists())

    def test_coupled_condition_message(self):
        """A repeated condition without a unique-cause pair is reported as
        coupled, never as redundant, when other forms can cover it, with or
        without short-circuit forms. ([S2] Table 33 expression: masking
        covers A (2nd occurrence) with (1, 5) and (3, 5).)"""
        text = "F = (A and B) or (A and C)"
        for extra, line in (((), "A#1 : NONE - coupled with A#2: they always change together"),
                            (("--short-circuit",),
                             "A#2 : NONE - coupled with A#1: no pair where it is the only "
                             "condition that changes")):
            with self.subTest(extra=extra):
                result = self.run_main("--mcdc", "unique-cause", *extra, expression=text)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(line, result.stdout)
                self.assertNotIn("redundant", result.stdout)

    def test_no_expression_prints_help(self):
        result = self.run_main(expression=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("usage:"))
        self.assertNotIn("Outvar |", result.stdout)

    def test_csv_output_stays_clean(self):
        result = self.run_main("--mcdc", "--csv", "-gen_scen", str(self.write(TEMPLATE)),
                               "--output-dir", self.dir.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "#,a,b,c,Z")
        self.assertEqual(len(result.stdout.splitlines()), 5)
        self.assertIn("Scenario written to", result.stderr)

    def test_template_error_stops_before_writing(self):
        result = self.run_main("--mcdc", "-gen_scen", str(self.write("[settings]\n")))
        self.assertEqual(result.returncode, 2)
        self.assertIn("OUTPUT_FILENAME is missing", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
