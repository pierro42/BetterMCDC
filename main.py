# -*- coding: utf-8 -*-
# Created on Wed Oct 28 21:14:58 2026
# @author: Pierre
"""
Truth table generator for a boolean expression, with an optional
MC/DC (Modified Condition / Decision Coverage) reduction.

The expression is given as a string, "Output = <expression>", e.g.
    "Outvar = (cond1 or cond2_mem) and (not cond1 and cond3)"
Allowed: variable names, and, or, not, ==, != (xor), True, False, ( ).
French keywords are accepted too: et, ou, non (any case), e.g.
    "Outvar = (cond1 ou cond2_mem) et (non cond1 et cond3)"
so et, ou and non can't be used as variable names.
&&, || and ! are accepted as Boolean and / or / not (both operands are
part of the decision, exactly like and / or), e.g.
    "Outvar = (cond1 || cond2_mem) && (!cond1 && cond3)"
The "Output =" part is optional (the output is then called "result").
Inputs appear in the table in order of first appearance.

A *condition* is each occurrence of a variable in the expression, so in
`(a and bd) or (not c and a)` there are 4 conditions: a#1, bd, c, a#2.
a#1 and a#2 are "coupled": they can never change independently.

MC/DC definitions follow DOT/FAA/AR-01/18 (Chilenski, 2001): unique-cause
(section 3.1.1) and masking by graph coloring (section 3.1.2). Up to
--max-exact inputs the whole truth table is analysed and the smallest test
set is searched; above, each independence pair is searched directly.

Usage:
    python main.py "Out = (a and bd) or not c"                      # full truth table
    python main.py "Out = (a and bd) or not c" --mcdc               # masking MC/DC
    python main.py "Out = (a and bd) or not c" --mcdc unique-cause  # unique-cause MC/DC
    python main.py "Out = (a and bd) or not c" --mcdc --csv         # same, as CSV
    python main.py "Out = (a and bd) or not c" --mcdc -gen_scen input/test_setup.toml
                                    # also write a test scenario in the output folder
                                    # (template format: see input/test_setup.toml)
"""

import argparse
import sys
from pathlib import Path

from mcdc import (DEFAULT_MAX_EXACT, analyse_mcdc, load_template, output_filename,
                  parse_decision, print_mcdc_summary, print_table, render_scenario,
                  truth_table)

EXAMPLE_EXPRESSION = "Outvar = (cond1 or cond2_mem) and (not cond1 and cond3)"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("expression", nargs="?",
                        help='"Output = <boolean expression>" (quoted), e.g. '
                             f'"{EXAMPLE_EXPRESSION}"')
    parser.add_argument("--mcdc", nargs="?", const="masking",
                        choices=["masking", "unique-cause"],
                        help="reduce the table to a minimal MC/DC test set "
                             "(default method: masking)")
    parser.add_argument("--csv", action="store_true",
                        help="print the table as CSV instead of aligned text")
    parser.add_argument("--max-exact", type=int, default=DEFAULT_MAX_EXACT, metavar="N",
                        help="number of inputs up to which the whole truth table is "
                             f"analysed (default: {DEFAULT_MAX_EXACT})")
    parser.add_argument("-gen_scen", "--gen-scen", metavar="TEMPLATE",
                        help="also write a test scenario of the test cases, formatted "
                             "by a TOML template file (e.g. input/test_setup.toml)")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, metavar="DIR",
                        help="folder where the scenario is written (default: the "
                             "'output' folder next to main.py, created if needed)")
    args = parser.parse_args()
    if args.expression is None:
        parser.print_help()
        return

    try:
        decision = parse_decision(args.expression)
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

    if not args.mcdc:
        if n > args.max_exact:
            parser.error(f"{n} inputs: the full truth table has 2^{n} rows; "
                         f"use --mcdc, or raise --max-exact")
        rows = truth_table(decision)
        tests = [(i, *r) for i, r in enumerate(rows)]
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
        # a relative OUTPUT_FILENAME goes into the output folder, an absolute one is kept
        path = args.output_dir / output_filename(template, decision, args.expression)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(render_scenario(template, decision, tests, args.expression))
        except OSError as e:
            parser.error(f"can't write the scenario: {e}")
        # on stderr with --csv, so that the CSV output stays clean
        print(f"\nScenario written to {path} ({len(tests)} test case(s))",
              file=sys.stderr if args.csv else sys.stdout)


if __name__ == "__main__":
    main()
