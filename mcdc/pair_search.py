# -*- coding: utf-8 -*-
"""
Pair-search engine, for large expressions: no truth table, one independence
pair is searched directly for each condition. Its job is completeness
(every condition covered, proven impossible, or reported unknown), not a
minimal set. Every pair is checked against the definitions of tree.py
before it is reported.

References:
  [S1] NASA/TM-2001-210876, "A Practical Tutorial on Modified
       Condition/Decision Coverage", Hayhurst et al., May 2001.
  [S2] DOT/FAA/AR-01/18, "An Investigation of Three Forms of the Modified
       Condition Decision Coverage (MCDC) Criterion", Chilenski, April 2001.
"""

from .tree import apply_operator, is_masking_pair, is_unique_cause_pair, row_number


class _BudgetExceeded(Exception):
    pass


def _partial_values(nodes, cond):
    """Node values when some conditions are unknown (None): an and with a
    False input is False, an or with a True input is True, and so on."""
    values = []
    for kind, a, b in nodes:
        if kind == "cond":
            values.append(cond[a])
        elif kind == "const":
            values.append(a)
        elif kind == "not":
            values.append(None if values[a] is None else not values[a])
        else:
            va, vb = values[a], values[b]
            if kind == "and" and (va is False or vb is False):
                values.append(False)
            elif kind == "or" and (va is True or vb is True):
                values.append(True)
            elif va is None or vb is None:
                values.append(None)
            else:
                values.append(apply_operator(kind, va, vb))
    return values


def _search_pair(decision, k, mode, budget, fixed_x=None):
    """Depth-first search of two input vectors (x, y) forming an
    independence pair for condition k, without the truth table.

    A branch is abandoned as soon as a node on k's path is known not to
    change, or (masking) another condition is known to have its whole path
    changed. Returns (status, (x, y) or None): "covered", "impossible" (the
    whole search space was explored) or "unknown" (budget exceeded). With
    fixed_x only y is searched, and "impossible" only means that this x has
    no partner."""
    n = len(decision.names)
    v = decision.variable[k]
    if mode == "unique-cause" and decision.variable.count(v) > 1:
        return "impossible", None        # coupled condition, [S2] 3.2.1
    others = [decision.path_nodes[j] for j in range(len(decision.conditions)) if j != k]
    path = decision.path_nodes[k]
    order = [v] + [u for u in range(n) if u != v]
    x = list(fixed_x) if fixed_x is not None else [None] * n
    y = [None] * n
    steps = 0

    def possible():
        vx = _partial_values(decision.nodes, [x[u] for u in decision.variable])
        vy = _partial_values(decision.nodes, [y[u] for u in decision.variable])
        if any(vx[m] is not None and vx[m] == vy[m] for m in path):
            return False
        if mode == "masking":
            for other in others:
                if all(vx[m] is not None and vy[m] is not None and vx[m] != vy[m]
                       for m in other):
                    return False
        return True

    def options(u):
        if u == v:
            return [(False, True)] if fixed_x is None else [(x[v], not x[v])]
        if fixed_x is not None:
            return [(x[u], x[u])] if mode == "unique-cause" else [(x[u], x[u]), (x[u], not x[u])]
        if mode == "unique-cause":
            return [(False, False), (True, True)]
        return [(False, False), (True, True), (False, True), (True, False)]

    def dfs(depth):
        nonlocal steps
        if depth == n:
            return True                  # every node known: the pair is valid
        steps += 1
        if steps > budget:
            raise _BudgetExceeded
        u = order[depth]
        for a, b in options(u):
            x[u], y[u] = a, b
            if possible() and dfs(depth + 1):
                return True
        if fixed_x is None:
            x[u] = None
        y[u] = None
        return False

    try:
        if dfs(0):
            return "covered", (tuple(x), tuple(y))
        return "impossible", None
    except _BudgetExceeded:
        return "unknown", None


def pair_search_set(decision, mode, budget):
    """One independence pair per condition, reusing the tests already
    selected when possible. Not guaranteed minimal."""
    tests, choice, status = [], {}, {}
    check = is_masking_pair if mode == "masking" else is_unique_cause_pair
    for k, cond in enumerate(decision.conditions):
        found = None
        for x in list(tests):            # first try a partner for a selected test
            st, found = _search_pair(decision, k, mode, max(1, budget // 50), fixed_x=x)
            if found:
                break
        if not found:
            status[cond], found = _search_pair(decision, k, mode, budget)
            if not found:
                continue
        # Self-check with the direct definition before the pair is reported
        if not check(decision, found[0], found[1], cond):
            raise AssertionError(f"internal error: invalid pair for {cond}")
        for t in found:
            if t not in tests:
                tests.append(t)
        status[cond] = "covered"
        choice[cond] = tuple(sorted(row_number(t) for t in found))
    return tests, choice, status
