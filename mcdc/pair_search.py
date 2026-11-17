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

from .tree import PAIR_CHECK, SHORT_CIRCUIT, apply_operator, canonical, row_number


class _BudgetExceeded(Exception):
    pass


def _partial_values(nodes, cond):
    """Node values when some conditions are unknown (None): an and with a
    False input is False, an or with a True input is True, and so on."""
    values = []
    for kind, a, b in nodes:
        base = SHORT_CIRCUIT.get(kind, kind)
        if kind == "cond":
            values.append(cond[a])
        elif kind == "const":
            values.append(a)
        elif kind == "not":
            values.append(None if values[a] is None else not values[a])
        else:
            va, vb = values[a], values[b]
            if base == "and" and (va is False or vb is False):
                values.append(False)
            elif base == "or" and (va is True or vb is True):
                values.append(True)
            elif va is None or vb is None:
                values.append(None)
            else:
                values.append(apply_operator(kind, va, vb))
    return values


def _partial_executed(nodes, values):
    """Whether each node is executed (tree.node_executed) when some values
    are unknown: True, False, or None (unknown)."""
    executed = [None] * len(nodes)
    executed[-1] = True
    for n in range(len(nodes) - 1, -1, -1):
        kind, a, b = nodes[n]
        if kind in ("cond", "const"):
            continue
        e = executed[n]
        executed[a] = e
        if b is None:
            continue
        if kind in SHORT_CIRCUIT:
            skips = kind == "orelse"         # left value that skips the right operand
            if e is False or values[a] is skips:
                executed[b] = False
            elif e is True and values[a] is not None:
                executed[b] = True
            else:
                executed[b] = None
        else:
            executed[b] = e
    return executed


def _search_pair(decision, k, mode, budget, fixed_x=None):
    """Depth-first search of two input vectors (x, y) forming an
    independence pair for condition k, without the truth table.

    A branch is abandoned only when it can no longer give a valid pair
    (tree.independence), i.e. as soon as one of these is known for sure:
      - a node on k's path is unchanged in the influence tree (not executed
        in one test, or executed in both with the same value);
      - (masking, unique-cause+masking) another condition's whole path is
        changed;
      - (unique-cause) another condition is changed; (unique-cause+masking)
        a condition of another input is changed.
    Without short-circuit forms every input but k's keeps its value in the
    unique-cause forms (an n-cube edge, [S2] 5.1). Once every input is set,
    the pair is accepted only if the exact definition (PAIR_CHECK) holds.

    Returns (status, (x, y) or None): "covered", "impossible" (the whole
    search space was explored) or "unknown" (budget exceeded). With fixed_x
    only y is searched, and "impossible" only means that this x has no
    partner."""
    n = len(decision.names)
    v = decision.variable[k]
    if (mode == "unique-cause" and not decision.short_circuit
            and decision.variable.count(v) > 1):
        return "impossible", None        # coupled condition, [S2] 3.2.1
    inputs_fixed = mode != "masking" and not decision.short_circuit
    others = [j for j in range(len(decision.conditions)) if j != k]
    path = decision.path_nodes[k]
    order = [v] + [u for u in range(n) if u != v]
    check = PAIR_CHECK[mode]
    cond = decision.conditions[k]
    x = list(fixed_x) if fixed_x is not None else [None] * n
    y = [None] * n
    steps = 0

    def possible():
        vx = _partial_values(decision.nodes, [x[u] for u in decision.variable])
        vy = _partial_values(decision.nodes, [y[u] for u in decision.variable])
        ex = _partial_executed(decision.nodes, vx)
        ey = _partial_executed(decision.nodes, vy)

        def unchanged(m):
            return (ex[m] is False or ey[m] is False
                    or (vx[m] is not None and vy[m] is not None and vx[m] == vy[m]))

        def changed(m):
            return (ex[m] is True and ey[m] is True and vx[m] is not None
                    and vy[m] is not None and vx[m] != vy[m])

        if any(unchanged(m) for m in path):
            return False
        for j in others:
            if mode != "unique-cause" and all(changed(m) for m in decision.path_nodes[j]):
                return False
            if changed(decision.path_nodes[j][0]) and (
                    mode == "unique-cause"
                    or (mode == "unique-cause+masking" and decision.variable[j] != v)):
                return False
        return True

    def options(u):
        if u == v:
            return [(False, True)] if fixed_x is None else [(x[v], not x[v])]
        if fixed_x is not None:
            return [(x[u], x[u])] if inputs_fixed else [(x[u], x[u]), (x[u], not x[u])]
        if inputs_fixed:
            return [(False, False), (True, True)]
        return [(False, False), (True, True), (False, True), (True, False)]

    def dfs(depth):
        nonlocal steps
        if depth == n:
            return check(decision, tuple(x), tuple(y), cond)
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
    check = PAIR_CHECK[mode]
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
        # Canonical tests (inputs not evaluated set to False, tree.canonical),
        # then self-check with the direct definition before the pair is reported
        found = tuple(canonical(decision, t) for t in found)
        if not check(decision, found[0], found[1], cond):
            raise AssertionError(f"internal error: invalid pair for {cond}")
        for t in found:
            if t not in tests:
                tests.append(t)
        status[cond] = "covered"
        choice[cond] = tuple(sorted(row_number(t) for t in found))
    return tests, choice, status
