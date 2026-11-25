# -*- coding: utf-8 -*-
# Created on Wed Oct 28 21:14:58 2026
# @author: Pierre
"""
Truth table generator for a boolean expression, with an optional
MC/DC (Modified Condition / Decision Coverage) reduction.

The expression is given as a string, "Output = <expression>", e.g.
    "Outvar = (cond1 or cond2_mem) and (not cond1 and cond3)"
Allowed: variable names, and, or, not, ==, != (xor), True, False, ( ).
xor and ^ are accepted for != (ouexclusif in French); an xor operand of
== or != must be in parentheses, e.g. (a xor b) == c.
French keywords are accepted too: et, ou, non, ouexclusif (any case), e.g.
    "Outvar = (cond1 ou cond2_mem) et (non cond1 et cond3)"
so et, ou, non, ouexclusif and xor can't be used as variable names.
&&, || and ! are accepted as Boolean and / or / not (both operands are
part of the decision, exactly like and / or), e.g.
    "Outvar = (cond1 || cond2_mem) && (!cond1 && cond3)"
Short-circuit evaluation ([S2] glossary, [S1] 3.6): "and then" and
"or else" evaluate their right operand only when needed, e.g.
    "Out = a and then (b or else c)"
With --short-circuit, every and / or (et / ou / && / ||) is evaluated that
way, as && and || are in C. An input that a test doesn't evaluate is
shown X ("don't care").
The "Output =" part is optional (the output is then called "result").
Inputs appear in the table in order of first appearance.

A *condition* is each occurrence of a variable in the expression, so in
`(a and bd) or (not c and a)` there are 4 conditions: a#1, bd, c, a#2.
a#1 and a#2 are "coupled": they can never change independently.

MC/DC definitions follow DOT/FAA/AR-01/18 (Chilenski, 2001): unique-cause
(section 3.1.1), masking by graph coloring (section 3.1.2), and
unique-cause + masking (section 3.2.2), with the not-executed operands
of short-circuit forms handled by tree_xor (Figure 5). Up to
--max-exact inputs the whole truth table is analysed and the smallest test
set is searched; above, each independence pair is searched directly.

Usage:
    python main.py "Out = (a and bd) or not c"                      # full truth table
    python main.py "Out = (a and bd) or not c" --mcdc               # masking MC/DC
    python main.py "Out = (a and bd) or not c" --mcdc unique-cause  # unique-cause MC/DC
    python main.py "Out = (a and bd) or not c" --mcdc unique-cause+masking
    python main.py "Out = (a and bd) or not c" --mcdc --csv         # same, as CSV
    python main.py "Out = (a && bd) || !c" --mcdc --short-circuit   # C evaluation
    python main.py "Out = (a and bd) or not c" --mcdc -gen_scen input/test_setup_cpp.toml
                                    # also write a test scenario in the output folder
                                    # (template format: see input/test_setup_cpp.toml)
"""

import argparse
import os
import sys
from pathlib import Path

from mcdc import (DEFAULT_MAX_EXACT, MODES, __version__, analyse_mcdc, list_output_filename,
                  load_template, output_filename, parse_decision, print_mcdc_summary,
                  print_table, render_scenario, render_test_list, test_rows, truth_table)

EXAMPLE_EXPRESSION = "Outvar = (cond1 or cond2_mem) and (not cond1 and cond3)"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def command_line(argv):
    """The command line as text, for ${tool_command}: arguments with spaces
    or quotes are written between double quotes."""
    def quote(arg):
        if arg and not any(c.isspace() or c in "\"'" for c in arg):
            return arg
        return '"' + arg.replace('"', '\\"') + '"'
    return " ".join(["main.py"] + [quote(arg) for arg in argv])


def same_file(path1, path2):
    """Do the two paths name the same file (case-insensitive on Windows)?
    The files may not exist yet."""
    name = lambda path: os.path.normcase(os.path.abspath(path))
    return name(path1) == name(path2)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("expression", nargs="?",
                        help='"Output = <boolean expression>" (quoted), e.g. '
                             f'"{EXAMPLE_EXPRESSION}"')
    parser.add_argument("--mcdc", nargs="?", const="masking",
                        choices=list(MODES),
                        help="reduce the table to a minimal MC/DC test set "
                             "(default method: masking)")
    parser.add_argument("--csv", action="store_true",
                        help="print the table as CSV instead of aligned text")
    parser.add_argument("--max-exact", type=int, default=DEFAULT_MAX_EXACT, metavar="N",
                        help="number of inputs up to which the whole truth table is "
                             f"analysed (default: {DEFAULT_MAX_EXACT})")
    parser.add_argument("--short-circuit", action="store_true",
                        help="evaluate every and / or (also et, ou, &&, ||) as a "
                             "short-circuit form, as && and || are in C; 'and then' "
                             "and 'or else' are always short-circuit")
    parser.add_argument("-gen_scen", "--gen-scen", metavar="TEMPLATE",
                        help="also write a test scenario of the test cases, formatted "
                             "by a TOML template file (e.g. input/test_setup_cpp.toml), "
                             "and a test list file if the template has LIST_OUTPUT_FILENAME")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, metavar="DIR",
                        help="folder where the scenario and the test list are written (default: the "
                             "'output' folder next to main.py, created if needed)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()
    if args.expression is None:
        parser.print_help()
        return

    try:
        decision = parse_decision(args.expression, short_circuit=args.short_circuit)
    except ValueError as e:
        parser.error(f"invalid expression: {e}")
    n = len(decision.names)
    template = None
    if args.gen_scen:
        # checked before the analysis, so a template error is reported at once
        try:
            template = load_template(args.gen_scen)
        except (OSError, ValueError) as e:
            parser.error(f"scenario template {args.gen_scen}: {e}")
        # a relative file name goes into the output folder, an absolute one is kept
        path = args.output_dir / output_filename(template, decision, args.expression)
        list_name = list_output_filename(template, decision, args.expression)
        list_path = args.output_dir / list_name if list_name is not None else None
        if list_path is not None and same_file(path, list_path):
            parser.error(f"scenario template {args.gen_scen}: LIST_OUTPUT_FILENAME gives the "
                         f"same file as OUTPUT_FILENAME ({path}); the test list would "
                         f"overwrite the scenario")

    if not args.mcdc:
        if n > args.max_exact:
            parser.error(f"{n} inputs: the full truth table has 2^{n} rows; "
                         f"use --mcdc, or raise --max-exact")
        rows = truth_table(decision)
        # with short-circuit forms, one row per distinct test (exact.test_rows)
        tests = [(i, *rows[i]) for i in test_rows(decision, rows)]
        print_table(decision, tests, csv=args.csv)
    else:
        analysis = analyse_mcdc(decision, args.mcdc, args.max_exact)
        tests = [(i, *analysis.tests[i]) for i in analysis.tests]
        print_table(decision, tests, csv=args.csv)
        if not args.csv:
            print(f"\n{len(analysis.tests)} test case(s) instead of {2 ** n}.")
            print_mcdc_summary(decision, analysis, args.mcdc)
        elif "unknown" in analysis.status.values():
            print("WARNING: coverage not proven for some conditions "
                  "(run without --csv for details)", file=sys.stderr)

    if template:
        command = command_line(sys.argv[1:])
        files = [("scenario", path, render_scenario)]
        if list_path is not None:
            files.append(("test list", list_path, render_test_list))
        stream = sys.stderr if args.csv else sys.stdout     # so that the CSV output stays clean
        print(file=stream)
        for what, file_path, render in files:
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(render(template, decision, tests, args.expression, command))
            except OSError as e:
                parser.error(f"can't write the {what}: {e}")
            print(f"{what.capitalize()} written to {file_path} ({len(tests)} test case(s))",
                  file=stream)


if __name__ == "__main__":
    main()
