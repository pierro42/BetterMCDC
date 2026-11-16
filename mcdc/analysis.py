# -*- coding: utf-8 -*-
"""
MC/DC analysis: chooses the exact engine or the pair-search engine.

References:
  [S1] NASA/TM-2001-210876, "A Practical Tutorial on Modified
       Condition/Decision Coverage", Hayhurst et al., May 2001.
  [S2] DOT/FAA/AR-01/18, "An Investigation of Three Forms of the Modified
       Condition Decision Coverage (MCDC) Criterion", Chilenski, April 2001.
"""

from typing import Dict, NamedTuple, Tuple

from .exact import independence_pairs, lower_bound, minimal_mcdc_set
from .pair_search import pair_search_set
from .tree import row_number, truth_table

DEFAULT_MAX_EXACT = 10


def _bound(decision, mode, covered):
    """Lower bound for the covered conditions (exact.lower_bound)."""
    inputs = {decision.variable[decision.conditions.index(c)] for c in covered}
    return lower_bound(mode, len(covered), len(inputs))


class Analysis(NamedTuple):
    engine: str                          # "exact" or "pair-search"
    tests: Dict[int, tuple]              # row number -> (inputs, result)
    choice: Dict[str, Tuple[int, int]]   # condition -> rows of its pair
    status: Dict[str, str]               # condition -> covered / impossible / unknown
    pair_counts: Dict[str, int]          # condition -> number of pairs (exact engine)
    optimal: bool                        # the set is proven minimal
    lower_bound: int                     # [S2] 5.1, see exact.lower_bound


def analyse_mcdc(decision, mode="masking", max_exact=DEFAULT_MAX_EXACT,
                 time_limit=2.0, budget=20000):
    """MC/DC test set for the decision.

    Up to `max_exact` inputs: whole truth table, every independence pair,
    smallest set (proven minimal unless the time limit is reached).
    Above: pair-search engine, one pair per condition found directly; the
    set is not guaranteed minimal, and a condition whose search exceeds
    `budget` steps is reported "unknown" (never silently dropped)."""
    if len(decision.names) <= max_exact:
        rows = truth_table(decision)
        pairs = independence_pairs(decision, rows, mode)
        bound = _bound(decision, mode, [c for c in pairs if pairs[c]])
        selected, choice, optimal = minimal_mcdc_set(
            pairs, forest_bound=mode == "unique-cause", time_limit=time_limit, bound=bound)
        status = {c: "covered" if pairs[c] else "impossible" for c in decision.conditions}
        return Analysis("exact", {i: rows[i] for i in sorted(selected)}, choice, status,
                        {c: len(p) for c, p in pairs.items()}, optimal, bound)

    tests, choice, status = pair_search_set(decision, mode, budget)
    bound = _bound(decision, mode, list(choice))
    found = {row_number(t): (t, bool(decision.evaluate([t[v] for v in decision.variable])))
             for t in tests}
    return Analysis("pair-search", dict(sorted(found.items())), choice, status, {},
                    len(found) <= bound, bound)
