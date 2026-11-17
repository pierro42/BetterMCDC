# -*- coding: utf-8 -*-
"""
Output: truth table / test-case table (text or CSV) and the MC/DC summary.
"""

from .tree import executed_inputs, node_masks, tree_xor

NOT_EVALUATED = "X"     # [S1] 3.6, Tables 32-33: "X represents don't care"


def _cell(value):
    return "1" if value else "0"


def print_table(decision, tests, csv=False):
    """Print test cases given as (row, inputs, result). The '#' column is
    the 1-based row number in the full truth table, so reduced tables stay
    traceable. With short-circuit forms, an input that the test doesn't
    evaluate is written X (its row number counts it as 0)."""
    headers = ["#"] + decision.names + [decision.output]
    lines = []
    for i, inputs, result in tests:
        executed = executed_inputs(decision, inputs)
        lines.append([str(i + 1)]
                     + [_cell(v) if ex else NOT_EVALUATED for v, ex in zip(inputs, executed)]
                     + [_cell(result)])

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
    evaluation = ", short-circuit evaluation" if decision.short_circuit else ""
    print(f"Method   : {mode} MC/DC{evaluation}, {len(conds)} condition(s), {engine}")
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
            if coupled and mode == "unique-cause" and not decision.short_circuit:
                reason = (f"coupled with {', '.join(coupled)}: they always change "
                          f"together, use --mcdc unique-cause+masking or masking")
            elif coupled and mode == "unique-cause":
                # with short-circuit forms a repeated condition can have a
                # unique-cause pair, but only where its other occurrences are
                # not evaluated in one of the two tests
                reason = (f"coupled with {', '.join(coupled)}: no pair where it is the "
                          f"only condition that changes, see --mcdc unique-cause+masking "
                          f"or masking")
            elif coupled and mode == "unique-cause+masking":
                name = decision.names[decision.variable[k]]
                reason = (f"coupled with {', '.join(coupled)}: no pair where only "
                          f"{name} changes (see --mcdc masking)")
            else:
                reason = f"never independently affects {decision.output} (redundant)"
            print(f"  {cond:<{width}} : NONE - {reason}")
            continue
        i, j = analysis.choice[cond]
        (xi, ri), (xj, rj) = analysis.tests[i], analysis.tests[j]
        # other conditions that changed (executed in both tests, different value)
        changed = tree_xor(node_masks(decision, xi), node_masks(decision, xj))
        masked = [c for c, path in zip(conds, decision.path_nodes)
                  if c != cond and changed >> path[0] & 1]
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
