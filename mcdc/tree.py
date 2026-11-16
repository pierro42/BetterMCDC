# -*- coding: utf-8 -*-
"""
Expression tree, evaluation, and the MC/DC independence-pair definitions.

is_masking_pair, is_unique_cause_pair and is_unique_cause_masking_pair are
the direct transcription of the definitions of [S2] 3.1.2, 3.1.1 and
3.2.2. Both engines (exact.py and pair_search.py) produce pairs that must
satisfy them; PAIR_CHECK gives the definition of each MC/DC form.

References:
  [S1] NASA/TM-2001-210876, "A Practical Tutorial on Modified
       Condition/Decision Coverage", Hayhurst et al., May 2001.
  [S2] DOT/FAA/AR-01/18, "An Investigation of Three Forms of the Modified
       Condition Decision Coverage (MCDC) Criterion", Chilenski, April 2001.
"""

import ast
import itertools


def build_tree(expr, occurrences):
    """Expression tree as a list of nodes (kind, a, b), children before
    parents, the result being the last node. Kinds: cond (a = condition
    index), const (a = value), not (a = child), and / or / eq / ne (a, b =
    children). n-ary and/or are split into a left-associated chain of binary
    operators, as in the report: a and b and c = (a and b) and c.

    Returns (nodes, leaf) where leaf[k] is the node of condition k."""
    condition = {id(node): k for k, node in enumerate(occurrences)}
    nodes, leaf = [], [None] * len(occurrences)

    def add(kind, a, b=None):
        nodes.append((kind, a, b))
        return len(nodes) - 1

    def visit(node):
        if isinstance(node, ast.Name):
            k = condition[id(node)]
            leaf[k] = add("cond", k)
            return leaf[k]
        if isinstance(node, ast.Constant):
            return add("const", node.value)
        if isinstance(node, ast.UnaryOp):
            return add("not", visit(node.operand))
        if isinstance(node, ast.BoolOp):
            kind = "and" if isinstance(node.op, ast.And) else "or"
            left = visit(node.values[0])
            for value in node.values[1:]:
                left = add(kind, left, visit(value))
            return left
        # Compare with a single operator (checked by parse_decision)
        kind = "eq" if isinstance(node.ops[0], ast.Eq) else "ne"
        return add(kind, visit(node.left), visit(node.comparators[0]))

    visit(expr)
    return nodes, leaf


def path_to_root(nodes, start):
    """Nodes from `start` up to the result (the last node)."""
    parent = {}
    for n, (kind, a, b) in enumerate(nodes):
        if kind not in ("cond", "const"):
            parent[a] = n
            if b is not None:
                parent[b] = n
    path = [start]
    while path[-1] in parent:
        path.append(parent[path[-1]])
    return path


def apply_operator(kind, a, b):
    if kind == "not":
        return not a
    if kind == "and":
        return a and b
    if kind == "or":
        return a or b
    if kind == "eq":
        return a == b
    return a != b


def node_values(nodes, cond):
    """Value of every node for the condition values `cond`."""
    values = []
    for kind, a, b in nodes:
        if kind == "cond":
            values.append(bool(cond[a]))
        elif kind == "const":
            values.append(a)
        else:
            values.append(apply_operator(kind, values[a], values[b] if b is not None else None))
    return values


def node_mask(decision, inputs):
    """Node values for an input vector, as a bitmask (bit n = node n)."""
    values = node_values(decision.nodes, [inputs[v] for v in decision.variable])
    return sum(1 << n for n, value in enumerate(values) if value)


def influence_set(decision, mask_x, mask_y):
    """[S2] 3.1.2: the influence set of two tests, i.e. the conditions whose
    whole path up to the result changed value between the two tests."""
    changed = mask_x ^ mask_y
    return [k for k, path in enumerate(decision.paths) if path & ~changed == 0]


def is_masking_pair(decision, x, y, cond):
    """True if input vectors x and y form a masking MC/DC independence pair
    for condition `cond` ([S2] 3.1.2: the influence set is exactly {cond}).
    The results then differ, since the result is on every path."""
    k = decision.conditions.index(cond)
    return influence_set(decision, node_mask(decision, x), node_mask(decision, y)) == [k]


def is_unique_cause_pair(decision, x, y, cond):
    """True if x and y form a unique-cause independence pair for `cond`
    ([S2] 3.1.1: only that condition changes, and the result changes)."""
    k = decision.conditions.index(cond)
    cx = [x[v] for v in decision.variable]
    cy = [y[v] for v in decision.variable]
    changed = [j for j in range(len(cx)) if cx[j] != cy[j]]
    return changed == [k] and bool(decision.evaluate(cx)) != bool(decision.evaluate(cy))


def is_unique_cause_masking_pair(decision, x, y, cond):
    """True if x and y form a unique-cause + masking independence pair for
    `cond` ([S2] 3.2.2): a unique cause for an uncoupled condition, and for
    a strongly coupled condition masking is allowed for that condition only,
    all other conditions remaining fixed.

    [S2] 5.1 and 7.1 state it on the n-cube of the inputs: the pair must be
    an *edge* (the two tests differ in just one input) and a valid
    independence pair (the graph coloring of 3.1.2). So: only the input of
    `cond` changes, and the influence set is exactly {cond}. For an
    uncoupled condition this is exactly a unique-cause pair."""
    k = decision.conditions.index(cond)
    changed = [v for v in range(len(x)) if bool(x[v]) != bool(y[v])]
    return changed == [decision.variable[k]] and is_masking_pair(decision, x, y, cond)


# The MC/DC forms of [S2] 3.2, from the weakest to the strongest
MODES = ("masking", "unique-cause+masking", "unique-cause")
PAIR_CHECK = {"masking": is_masking_pair,
              "unique-cause+masking": is_unique_cause_masking_pair,
              "unique-cause": is_unique_cause_pair}


def truth_table(decision):
    """Evaluate the decision on every combination of its inputs.

    Returns rows where rows[i] = (inputs_tuple, result). Row i is the
    binary number formed by the inputs, first input being the most
    significant bit."""
    rows = []
    for combo in itertools.product([False, True], repeat=len(decision.names)):
        cond = [combo[v] for v in decision.variable]
        rows.append((combo, bool(decision.evaluate(cond))))
    return rows


def row_number(inputs):
    """Row of an input vector in the full truth table (0-based)."""
    return sum(1 << (len(inputs) - 1 - v) for v, value in enumerate(inputs) if value)
