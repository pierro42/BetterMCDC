# -*- coding: utf-8 -*-
"""
Exact engine: whole truth table, every independence pair, smallest test
set (branch and bound), and the lower bounds of [S2] 5.1.

References:
  [S1] NASA/TM-2001-210876, "A Practical Tutorial on Modified
       Condition/Decision Coverage", Hayhurst et al., May 2001.
  [S2] DOT/FAA/AR-01/18, "An Investigation of Three Forms of the Modified
       Condition Decision Coverage (MCDC) Criterion", Chilenski, April 2001.
"""

import itertools
import math
import time

from .tree import influence_set, node_mask


def independence_pairs(decision, rows, mode="masking"):
    """For each condition k, list the row pairs (i, j), i < j, that show k
    independently affects the result.

    unique-cause ([S2] 3.1.1): only condition k differs between the two
                  rows, and the result differs.
    masking      ([S2] 3.1.2, graph coloring): the results differ and k is
                  the only condition whose whole path up to the result
                  changes value; the changes of the other conditions are
                  blocked by an operator whose value stays the same."""
    m = len(decision.conditions)
    false_rows = [i for i, row in enumerate(rows) if not row[1]]
    true_rows = [i for i, row in enumerate(rows) if row[1]]
    pairs = {c: [] for c in decision.conditions}
    if mode == "masking":
        masks = [node_mask(decision, inputs) for inputs, _ in rows]
        for i, j in itertools.product(false_rows, true_rows):
            influence = influence_set(decision, masks[i], masks[j])
            if len(influence) == 1:
                pairs[decision.conditions[influence[0]]].append(tuple(sorted((i, j))))
        return pairs

    values = [sum(1 << k for k in range(m) if inputs[decision.variable[k]])
              for inputs, _ in rows]
    for i, j in itertools.product(false_rows, true_rows):
        diff = values[i] ^ values[j]
        # exactly one condition changed
        if diff and diff & (diff - 1) == 0:
            pairs[decision.conditions[diff.bit_length() - 1]].append(tuple(sorted((i, j))))
    return pairs


def lower_bound(mode, conditions):
    """Fewest tests that can cover `conditions` conditions ([S2] 5.1):
    unique-cause N + 1 (Theorem 1), masking RUTW(2*SQRT(M)) (Theorem 4).
    Theorem 4 holds because a masking pair joins one False and one True test
    and serves a single condition: a False and b True tests give at most
    a*b pairs, so a*b >= M and a + b >= 2*SQRT(M)."""
    if conditions == 0:
        return 0
    if mode == "unique-cause":
        return conditions + 1
    root = math.isqrt(4 * conditions)          # ceil(2*sqrt(M)) = ceil(sqrt(4M))
    return root if root * root == 4 * conditions else root + 1


def _is_covered(pair_list, selected):
    return next((p for p in pair_list
                 if p[0] in selected and p[1] in selected), None)


def _greedy(conds, pairs):
    """Quick (not always minimal) solution, used as the initial bound."""
    selected, choice = set(), {}
    for cond in conds:
        pair = _is_covered(pairs[cond], selected) or min(
            pairs[cond], key=lambda p: (p[0] not in selected) + (p[1] not in selected))
        choice[cond] = pair
        selected.update(pair)
    return selected, choice


def minimal_mcdc_set(pairs, forest_bound=True, time_limit=2.0):
    """Pick one independence pair per condition so that the total number
    of distinct test cases is minimal (branch and bound).

    `forest_bound` is only valid for unique-cause pairs: they are then
    hypercube edges in distinct dimensions, i.e. a forest.

    Returns (selected_rows, chosen_pair_per_condition, is_optimal)."""
    conds = sorted((c for c in pairs if pairs[c]), key=lambda c: len(pairs[c]))
    best_rows, best_choice = _greedy(conds, pairs)
    deadline = time.monotonic() + time_limit
    timed_out = False
    bound = lower_bound("unique-cause" if forest_bound else "masking", len(conds))
    # Rows that belong to pairs of many conditions are good hubs to share
    degree = {}
    for cond in conds:
        for row in {r for p in pairs[cond] for r in p}:
            degree[row] = degree.get(row, 0) + 1
    # Pairs of each condition: best hubs first, and indexed by row
    ranked = {c: sorted(pairs[c], key=lambda p: -degree[p[0]] - degree[p[1]])
              for c in conds}
    partners = {c: {} for c in conds}
    for cond in conds:
        for i, j in pairs[cond]:
            partners[cond].setdefault(i, []).append(j)
            partners[cond].setdefault(j, []).append(i)

    def covering_pair(cond, selected):
        for row in selected:
            for other in partners[cond].get(row, ()):
                if other in selected:
                    return min(row, other), max(row, other)
        return None

    def one_new_row(cond, selected):
        """Pairs of an open condition that add a single row, best hub first."""
        found = {(min(r, o), max(r, o)): o
                 for r in selected for o in partners[cond].get(r, ())}
        return sorted(found, key=lambda p: -degree[found[p]])

    def search(selected, choice):
        nonlocal best_rows, best_choice, timed_out
        if len(best_rows) <= bound or timed_out:
            return
        if time.monotonic() > deadline:
            timed_out = True
            return
        # Conditions already covered by the selected rows cost nothing
        choice = dict(choice)
        open_conds = []
        for cond in conds:
            if cond in choice:
                continue
            covered = covering_pair(cond, selected)
            if covered:
                choice[cond] = covered
            else:
                open_conds.append(cond)
        if not open_conds:
            if len(selected) < len(best_rows):
                best_rows, best_choice = set(selected), choice
            return
        needed = 1
        if forest_bound:
            # The len(choice) chosen edges span `selected` with `components`
            # trees; each new edge adds a row or merges two trees.
            components = len(selected) - len(choice)
            needed = max(1, len(open_conds) - components + 1)
        if len(selected) + needed >= len(best_rows):
            return
        # Branch on the most constrained condition: fewest cheap pairs.
        # Pairs adding one row come first, then those adding two (if allowed).
        cheap = {c: one_new_row(c, selected) for c in open_conds}
        cond = min(open_conds, key=lambda c: (len(cheap[c]), len(pairs[c]), c))
        options = cheap[cond]
        if len(selected) + 2 < len(best_rows):
            options = itertools.chain(options, (
                p for p in ranked[cond] if p[0] not in selected and p[1] not in selected))
        for pair in options:
            new_size = len(selected | set(pair))
            if new_size >= len(best_rows):
                if new_size == len(selected) + 2:
                    break            # all remaining options add two rows
                continue
            choice[cond] = pair
            search(selected | set(pair), choice)

    search(set(), {})
    return best_rows, best_choice, not timed_out or len(best_rows) <= bound
