# -*- coding: utf-8 -*-
"""
Expression tree, evaluation, and the MC/DC independence-pair definitions.

The three definitions (is_masking_pair, is_unique_cause_pair,
is_unique_cause_masking_pair) are written on the influence tree of [S2]
3.1.2: the two expression trees are evaluated, then combined node by node
with tree_xor ([S2] Figure 5), which also handles the not-executed operands
of short-circuit operators. Both engines (exact.py and pair_search.py)
produce pairs that must satisfy them; PAIR_CHECK gives the definition of
each MC/DC form.

References:
  [S1] NASA/TM-2001-210876, "A Practical Tutorial on Modified
       Condition/Decision Coverage", Hayhurst et al., May 2001.
  [S2] DOT/FAA/AR-01/18, "An Investigation of Three Forms of the Modified
       Condition Decision Coverage (MCDC) Criterion", Chilenski, April 2001.
"""

import ast
import itertools

# Short-circuit forms ([S2] glossary, "Short-Circuit Form Boolean Operator"):
# the left operand is evaluated first, the right one only when needed.
SHORT_CIRCUIT = {"andthen": "and", "orelse": "or"}


def build_tree(expr, occurrences, short_circuit_at=None):
    """Expression tree as a list of nodes (kind, a, b), children before
    parents, the result being the last node. Kinds: cond (a = condition
    index), const (a = value), not (a = child), and / or / andthen / orelse
    / eq / ne (a = left child, b = right child). n-ary and/or are split into
    a left-associated chain of binary operators, as in the report:
    a and b and c = (a and b) and c.

    short_circuit_at(left, right) tells whether the operator between two
    operands of an ast.BoolOp is a short-circuit form.

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
            for before, value in zip(node.values, node.values[1:]):
                sc = short_circuit_at is not None and short_circuit_at(before, value)
                op = {"and": "andthen", "or": "orelse"}[kind] if sc else kind
                left = add(op, left, visit(value))
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
    """Boolean result of an operator. A short-circuit form returns the same
    result as its Boolean operator ([S2] glossary); only the evaluation of
    its right operand differs (node_executed)."""
    kind = SHORT_CIRCUIT.get(kind, kind)
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


def node_executed(nodes, values):
    """Whether each node is executed ([S2] 3.1.2 rule b): the result is
    executed; the operands of an executed operator are executed, except the
    right-hand side of an and-then whose left-hand side is False, or of an
    or-else whose left-hand side is True, which is not executed with
    everything below it."""
    executed = [False] * len(nodes)
    executed[-1] = True
    for n in range(len(nodes) - 1, -1, -1):
        kind, a, b = nodes[n]
        if kind in ("cond", "const"):
            continue
        executed[a] = executed[n]
        if b is not None:
            skipped = ((kind == "andthen" and not values[a])
                       or (kind == "orelse" and values[a]))
            executed[b] = executed[n] and not skipped
    return executed


def node_masks(decision, inputs):
    """Node values and executed nodes for an input vector, as two bitmasks
    (bit n = node n)."""
    values = node_values(decision.nodes, [inputs[v] for v in decision.variable])
    executed = node_executed(decision.nodes, values)
    return (sum(1 << n for n, value in enumerate(values) if value),
            sum(1 << n for n, ex in enumerate(executed) if ex))


def tree_xor(masks_x, masks_y):
    """Influence tree of two tests ([S2] 3.1.2 and Figure 5), as a bitmask:
    a node is True when it is executed in both tests and its value differs
    (tree_xor of F and T is T; anything with Not-Executed is F)."""
    (vx, ex), (vy, ey) = masks_x, masks_y
    return (vx ^ vy) & ex & ey


def influence_set(decision, changed):
    """[S2] 3.1.2: the conditions that have a path of all Trues to the root
    in the influence tree `changed`."""
    return [k for k, path in enumerate(decision.paths) if path & ~changed == 0]


def changed_conditions(decision, changed):
    """The conditions (leaves) that are True in the influence tree, i.e.
    executed in both tests with a different value."""
    return [k for k, path in enumerate(decision.path_nodes) if changed >> path[0] & 1]


def independence(decision, changed, k, mode):
    """True if the influence tree `changed` makes an independence pair for
    condition k in `mode`, as defined by [S2]:
      masking (3.1.2): the influence set is exactly {k};
      unique-cause (3.1.2): in addition, k is the only condition which has
          a True in the influence tree (only k changed between the tests);
      unique-cause+masking (3.2.2): in addition, every condition which has
          a True in the influence tree is an occurrence of k's input:
          masking is allowed for that condition only, all other conditions
          remaining fixed. Without short-circuit operators this is the
          "edge" transition of 5.1 and 7.1 (only k's input changes).
    The results of the two tests then differ, since the result is on every
    path."""
    if influence_set(decision, changed) != [k]:
        return False
    if mode == "masking":
        return True
    leaves = changed_conditions(decision, changed)
    if mode == "unique-cause":
        return leaves == [k]
    v = decision.variable[k]
    return all(decision.variable[j] == v for j in leaves)


def _pair(decision, x, y, cond, mode):
    k = decision.conditions.index(cond)
    return independence(decision, tree_xor(node_masks(decision, x), node_masks(decision, y)),
                        k, mode)


def is_masking_pair(decision, x, y, cond):
    """True if input vectors x and y form a masking MC/DC independence pair
    for condition `cond` ([S2] 3.1.2: the influence set is exactly {cond})."""
    return _pair(decision, x, y, cond, "masking")


def is_unique_cause_pair(decision, x, y, cond):
    """True if x and y form a unique-cause independence pair for `cond`
    ([S2] 3.1.2: the influence set is {cond} and cond is the only condition
    with a True in the influence tree). Without short-circuit operators this
    is the definition of 3.1.1: only that condition changes, and the result
    changes."""
    return _pair(decision, x, y, cond, "unique-cause")


def is_unique_cause_masking_pair(decision, x, y, cond):
    """True if x and y form a unique-cause + masking independence pair for
    `cond` ([S2] 3.2.2): a unique cause for an uncoupled condition, and for
    a strongly coupled condition masking is allowed for that condition only,
    all other conditions remaining fixed (see `independence`)."""
    return _pair(decision, x, y, cond, "unique-cause+masking")


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


def executed_inputs(decision, inputs):
    """For each input, whether it is evaluated by this test: at least one of
    its occurrences is executed. Always True without short-circuit forms."""
    values = node_values(decision.nodes, [inputs[v] for v in decision.variable])
    executed = node_executed(decision.nodes, values)
    result = [False] * len(decision.names)
    for k, path in enumerate(decision.path_nodes):
        if executed[path[0]]:
            result[decision.variable[k]] = True
    return tuple(result)


def canonical(decision, inputs):
    """The test with every input that is not evaluated set to False. [S2]
    numbers test cases "interpreting a nonexecution due to short-circuit
    operators as 0" (glossary, Condition Combination); [S1] 3.6 writes these
    inputs X, "don't care". Inputs that are not evaluated don't change any
    executed node, so a test and its canonical form are the same test."""
    executed = executed_inputs(decision, inputs)
    return tuple(bool(value) and ex for value, ex in zip(inputs, executed))


def row_number(inputs):
    """Row of an input vector in the full truth table (0-based)."""
    return sum(1 << (len(inputs) - 1 - v) for v, value in enumerate(inputs) if value)
