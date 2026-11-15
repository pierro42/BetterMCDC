# -*- coding: utf-8 -*-
"""
Output: truth table / test-case table (text or CSV) and the MC/DC summary.
"""


def _cell(value):
    return "1" if value else "0"


def print_table(decision, tests, csv=False):
    """Print test cases given as (row, inputs, result). The '#' column is
    the 1-based row number in the full truth table, so reduced tables stay
    traceable."""
    headers = ["#"] + decision.names + [decision.output]
    lines = [[str(i + 1)] + [_cell(v) for v in inputs] + [_cell(result)]
             for i, inputs, result in tests]

    if csv:
        print(",".join(headers))
        for line in lines:
            print(",".join(line))
        return

    widths = [max([len(h)] + [len(line[c]) for line in lines])
              for c, h in enumerate(headers)]
    fmt = lambda cells: " | ".join(s.center(w) for s, w in zip(cells, widths))
    print(fmt(headers))
    print("-+-".join("-" * w for w in widths))
    for line in lines:
        print(fmt(line))


def print_mcdc_summary(decision, analysis, mode):
    conds = decision.conditions
    width = max(len(c) for c in conds)
    engine = ("exact (whole truth table)" if analysis.engine == "exact"
              else "pair search (no truth table)")
    print()
    print(f"Decision : {decision.output} = {decision.text}")
    print(f"Method   : {mode} MC/DC, {len(conds)} condition(s), {engine}")
    print()
    print("Independence pairs:")
    for k, cond in enumerate(conds):
        coupled = [c for c, v in zip(conds, decision.variable)
                   if v == decision.variable[k] and c != cond]
        status = analysis.status[cond]
        if status == "unknown":
            print(f"  {cond:<{width}} : UNKNOWN - search budget exceeded, coverage not proven")
            continue
        if status == "impossible":
            if coupled and mode == "unique-cause":
                reason = (f"coupled with {', '.join(coupled)}: they always change "
                          f"together, use --mcdc masking")
            else:
                reason = f"never independently affects {decision.output} (redundant)"
            print(f"  {cond:<{width}} : NONE - {reason}")
            continue
        i, j = analysis.choice[cond]
        (xi, ri), (xj, rj) = analysis.tests[i], analysis.tests[j]
        masked = [c for c, v in zip(conds, decision.variable)
                  if c != cond and xi[v] != xj[v]]
        count = (f"   ({analysis.pair_counts[cond]} possible pair(s))"
                 if analysis.pair_counts else "")
        note = f"   masked: {', '.join(masked)}" if masked else ""
        print(f"  {cond:<{width}} : #{i + 1} / #{j + 1}   "
              f"{decision.output} {_cell(ri)} -> {_cell(rj)}{count}{note}")
    print()
    size = len(analysis.tests)
    if analysis.optimal:
        print(f"Minimum  : {size} test(s), proven minimal")
    else:
        print(f"Minimum  : {size} test(s), not proven minimal "
              f"(lower bound: {analysis.lower_bound} test(s))")
    unknown = [c for c in conds if analysis.status[c] == "unknown"]
    if unknown:
        print(f"WARNING  : coverage not proven for {', '.join(unknown)}")
