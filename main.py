# -*- coding: utf-8 -*-
"""
Created on Wed Oct 28 21:14:58 2026

@author: Pierre

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
"""

import argparse
import ast
import io
import itertools
import math
import re
import sys
import time
import tokenize
from typing import Callable, Dict, List, NamedTuple, Tuple


DEFAULT_EXPRESSION = "Outvar = (cond1 or cond2_mem) and (not cond1 and cond3)"
DEFAULT_MAX_EXACT = 10


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class Decision(NamedTuple):
    output: str                      # name of the output column
    names: List[str]                 # input variables, table columns
    conditions: List[str]            # labels: "a#1", "bd", "c", "a#2"
    variable: List[int]              # input index of each condition
    evaluate: Callable               # list of condition values -> result
    text: str                        # expression written with the labels
    nodes: List[tuple]               # expression tree, children before parents
    path_nodes: List[List[int]]      # nodes from each condition up to the result
    paths: List[int]                 # the same, as bitmasks over the nodes


# The only syntax accepted in an expression
_ALLOWED = (ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
            ast.Compare, ast.Eq, ast.NotEq, ast.Name, ast.Load, ast.Constant)
_ALLOWED_TEXT = "names, and/et/&&, or/ou/||, not/non/!, ==, !=, True, False"

_FRENCH = {"et": "and", "ou": "or", "non": "not"}
_TO_FRENCH = {v: k for k, v in _FRENCH.items()}
# "!" becomes "(not " and its operand gets a ")": as in C, ! binds tighter
# than every other operator (!a == b is (!a) == b)
_SYMBOLS = {"&&": " and ", "||": " or ", "!": "(not "}
_TO_SYMBOLS = {"and": "&&", "or": "||", "not": "!"}
_BEFORE_NOT = {"(", "=", "==", "!=", "!", "&", "|", "and", "or", "not"}


def _operand_end(tokens, i):
    """Index of the last token of the operand starting at tokens[i]: a name,
    a parenthesised group, or another ! and its operand. None if invalid."""
    if i >= len(tokens):
        return None
    if tokens[i].string == "!":
        return _operand_end(tokens, i + 1)
    if tokens[i].string == "(":
        depth = 0
        for j in range(i, len(tokens)):
            depth += {"(": 1, ")": -1}.get(tokens[j].string, 0)
            if depth == 0:
                return j
        return None
    return i if tokens[i].type == tokenize.NAME else None


def _replace_words(text, replace):
    """Replace whole words of a one-line `text`, found with Python's
    tokenizer so that names such as `route` or `cond_et` are left untouched.
    The operators && and || (two adjacent & or | tokens) and ! count as words;
    the operand of a replaced ! is closed with ")".
    `replace(word)` returns the new word, or None to keep it.

    Returns (new_text, shifts) where shifts lists (column in new_text,
    length change) for each replacement, to map error columns back."""
    tokens = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            tokens.append(tok)
    except (tokenize.TokenError, SyntaxError):
        pass                        # keep what was read, ast.parse reports the error
    closers = {}                    # token index -> number of ")" to add after it
    wrapped = set()                 # "!" tokens whose operand gets a ")"
    for i, tok in enumerate(tokens):
        if tok.string == "!" and replace("!") is not None:
            j = _operand_end(tokens, i + 1)
            previous = tokens[i - 1] if i else None
            unary = (previous is None or previous.string in _BEFORE_NOT
                     or previous.string.lower() in _FRENCH)
            if j is None and i + 1 < len(tokens) and tokens[i + 1].string == "(":
                continue            # unclosed "(": left to the parser's message
            if j is None or not unary:
                raise ValueError(f"'!' at column {tok.start[1] + 1} must be placed "
                                 f"before a name or a parenthesis, e.g. !a or !(a && b)")
            closers[j] = closers.get(j, 0) + 1
            wrapped.add(i)
    out, last, shifts = [], 0, []
    skip = False
    for i, tok in enumerate(tokens):
        following = tokens[i + 1] if i + 1 < len(tokens) else None
        if skip:
            skip = False
            continue
        start, end = tok.start[1], tok.end[1]
        if tok.type == tokenize.NAME:
            new = replace(tok.string)
        elif (tok.string in ("&", "|") and following is not None
              and following.string == tok.string and following.start == tok.end):
            new = replace(tok.string * 2)
            end, skip = following.end[1], True
        elif tok.string == "!":     # alone; "!=" is a separate token
            new = replace("!")
            if new is not None and i not in wrapped:
                new = " not "
        else:
            new = None
        if i in closers:
            new = (tok.string if new is None else new) + ")" * closers[i]
        if new is None:
            continue
        out.append(text[last:start])
        shifts.append((sum(len(s) for s in out), len(new) - (end - start)))
        out.append(new)
        last = end
    out.append(text[last:])
    return "".join(out), shifts


def parse_decision(text):
    """Parse "Output = <boolean expression>" into a Decision.
    Raises ValueError with a readable message if the text is not valid."""
    text = " ".join(text.splitlines()).strip()
    used = set()                    # which alternative spellings the user wrote

    def to_python(word):
        if word in _SYMBOLS:
            used.add("symbols")
            return _SYMBOLS[word]
        if word.lower() in _FRENCH:
            used.add("french")
            return _FRENCH[word.lower()]
        return None

    python_text, shifts = _replace_words(text, to_python)
    try:
        module = ast.parse(python_text, mode="exec")
    except SyntaxError as e:
        # report the column in the text as the user wrote it
        column = (e.offset or 1) - sum(d for start, d in shifts if start < (e.offset or 1) - 1)
        raise ValueError(f"syntax error at column {column}: {e.msg}") from None
    if len(module.body) != 1:
        raise ValueError("expected a single expression")
    stmt = module.body[0]
    if isinstance(stmt, ast.Assign):
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            raise ValueError("the left side of '=' must be a single output name")
        output, expr = stmt.targets[0].id, stmt.value
    elif isinstance(stmt, ast.Expr):
        output, expr = "result", stmt.value
    else:
        raise ValueError("expected 'Output = <expression>'")

    for node in ast.walk(expr):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"unsupported syntax: '{ast.unparse(node)}' "
                             f"(allowed: {_ALLOWED_TEXT})")
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
            raise ValueError(f"only True and False are allowed as constants, "
                             f"not '{ast.unparse(node)}'")
        if isinstance(node, ast.Compare) and len(node.ops) != 1:
            # Python reads a != b != c as (a != b) and (b != c)
            raise ValueError(f"chained comparison '{ast.unparse(node)}' is ambiguous, "
                             f"add parentheses, e.g. (a != b) != c")

    # Every occurrence of a variable is a condition, in reading order
    occurrences = sorted((node for node in ast.walk(expr) if isinstance(node, ast.Name)),
                         key=lambda node: (node.lineno, node.col_offset))
    if not occurrences:
        raise ValueError("the expression has no input variable")
    names = list(dict.fromkeys(node.id for node in occurrences))
    if output in names:
        raise ValueError(f"'{output}' is used both as output and as input")

    counts = {v: sum(node.id == v for node in occurrences) for v in names}
    seen = {}
    labels = []
    for node in occurrences:
        seen[node.id] = seen.get(node.id, 0) + 1
        labels.append(f"{node.id}#{seen[node.id]}" if counts[node.id] > 1 else node.id)
    variable = [names.index(node.id) for node in occurrences]

    # Display text: the k-th variable token is occurrence k (reading order),
    # and operators go back to the spelling the user wrote (French, && / ||)
    label_iter = iter(labels)
    spelling = {}
    if "french" in used:
        spelling.update(_TO_FRENCH)
    if "symbols" in used:
        spelling.update(_TO_SYMBOLS)

    def display(word):
        if word in names:
            return next(label_iter)
        return spelling.get(word)

    label_text = _replace_words(ast.unparse(expr), display)[0]
    label_text = re.sub(r"!\s+", "!", label_text)       # "! a" -> "!a" ("!=" has no space)

    nodes, leaf = _build_tree(expr, occurrences)
    path_nodes = [_path(nodes, leaf[k]) for k in range(len(occurrences))]
    paths = [sum(1 << n for n in path) for path in path_nodes]

    def evaluate(cond):
        return _node_values(nodes, cond)[-1]

    return Decision(output, names, labels, variable, evaluate, label_text,
                    nodes, path_nodes, paths)


# ---------------------------------------------------------------------------
# Expression tree (DOT/FAA/AR-01/18 section 3.1.2)
# ---------------------------------------------------------------------------

def _build_tree(expr, occurrences):
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


def _path(nodes, start):
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


def _apply(kind, a, b):
    if kind == "not":
        return not a
    if kind == "and":
        return a and b
    if kind == "or":
        return a or b
    if kind == "eq":
        return a == b
    return a != b


def _node_values(nodes, cond):
    """Value of every node for the condition values `cond`."""
    values = []
    for kind, a, b in nodes:
        if kind == "cond":
            values.append(bool(cond[a]))
        elif kind == "const":
            values.append(a)
        else:
            values.append(_apply(kind, values[a], values[b] if b is not None else None))
    return values


def node_mask(decision, inputs):
    """Node values for an input vector, as a bitmask (bit n = node n)."""
    values = _node_values(decision.nodes, [inputs[v] for v in decision.variable])
    return sum(1 << n for n, value in enumerate(values) if value)


def _influence(decision, mask_x, mask_y):
    """[S2] 3.1.2: the influence set of two tests, i.e. the conditions whose
    whole path up to the result changed value between the two tests."""
    changed = mask_x ^ mask_y
    return [k for k, path in enumerate(decision.paths) if path & ~changed == 0]


def is_masking_pair(decision, x, y, cond):
    """True if input vectors x and y form a masking MC/DC independence pair
    for condition `cond` ([S2] 3.1.2: the influence set is exactly {cond}).
    The results then differ, since the result is on every path."""
    k = decision.conditions.index(cond)
    return _influence(decision, node_mask(decision, x), node_mask(decision, y)) == [k]


def is_unique_cause_pair(decision, x, y, cond):
    """True if x and y form a unique-cause independence pair for `cond`
    ([S2] 3.1.1: only that condition changes, and the result changes)."""
    k = decision.conditions.index(cond)
    cx = [x[v] for v in decision.variable]
    cy = [y[v] for v in decision.variable]
    changed = [j for j in range(len(cx)) if cx[j] != cy[j]]
    return changed == [k] and bool(decision.evaluate(cx)) != bool(decision.evaluate(cy))


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# MC/DC, exact engine: whole truth table
# ---------------------------------------------------------------------------

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
            influence = _influence(decision, masks[i], masks[j])
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


# ---------------------------------------------------------------------------
# MC/DC, pair-search engine: no truth table, for large expressions
# ---------------------------------------------------------------------------

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
                values.append(_apply(kind, va, vb))
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


def _pair_search_set(decision, mode, budget):
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


# ---------------------------------------------------------------------------
# MC/DC analysis
# ---------------------------------------------------------------------------

class Analysis(NamedTuple):
    engine: str                          # "exact" or "pair-search"
    tests: Dict[int, tuple]              # row number -> (inputs, result)
    choice: Dict[str, Tuple[int, int]]   # condition -> rows of its pair
    status: Dict[str, str]               # condition -> covered / impossible / unknown
    pair_counts: Dict[str, int]          # condition -> number of pairs (exact engine)
    optimal: bool                        # the set is proven minimal
    lower_bound: int                     # [S2] 5.1, Theorem 1 or 4


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
        selected, choice, optimal = minimal_mcdc_set(
            pairs, forest_bound=mode == "unique-cause", time_limit=time_limit)
        status = {c: "covered" if pairs[c] else "impossible" for c in decision.conditions}
        covered = sum(1 for p in pairs.values() if p)
        return Analysis("exact", {i: rows[i] for i in sorted(selected)}, choice, status,
                        {c: len(p) for c, p in pairs.items()}, optimal,
                        lower_bound(mode, covered))

    tests, choice, status = _pair_search_set(decision, mode, budget)
    bound = lower_bound(mode, len(choice))
    found = {row_number(t): (t, bool(decision.evaluate([t[v] for v in decision.variable])))
             for t in tests}
    return Analysis("pair-search", dict(sorted(found.items())), choice, status, {},
                    len(found) <= bound, bound)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

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


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("expression", nargs="?", default=DEFAULT_EXPRESSION,
                        help='"Output = <boolean expression>" (quoted); '
                             f'default: "{DEFAULT_EXPRESSION}"')
    parser.add_argument("--mcdc", nargs="?", const="masking",
                        choices=["masking", "unique-cause"],
                        help="reduce the table to a minimal MC/DC test set "
                             "(default method: masking)")
    parser.add_argument("--csv", action="store_true",
                        help="print the table as CSV instead of aligned text")
    parser.add_argument("--max-exact", type=int, default=DEFAULT_MAX_EXACT, metavar="N",
                        help="number of inputs up to which the whole truth table is "
                             f"analysed (default: {DEFAULT_MAX_EXACT})")
    args = parser.parse_args()

    try:
        decision = parse_decision(args.expression)
    except ValueError as e:
        parser.error(f"invalid expression: {e}")
    n = len(decision.names)

    if not args.mcdc:
        if n > args.max_exact:
            parser.error(f"{n} inputs: the full truth table has 2^{n} rows; "
                         f"use --mcdc, or raise --max-exact")
        rows = truth_table(decision)
        print_table(decision, [(i, *r) for i, r in enumerate(rows)], csv=args.csv)
        return

    analysis = analyse_mcdc(decision, args.mcdc, args.max_exact)
    print_table(decision, [(i, *analysis.tests[i]) for i in analysis.tests], csv=args.csv)
    if not args.csv:
        print(f"\n{len(analysis.tests)} test case(s) instead of {2 ** n}.")
        print_mcdc_summary(decision, analysis, args.mcdc)
    elif "unknown" in analysis.status.values():
        print("WARNING: coverage not proven for some conditions "
              "(run without --csv for details)", file=sys.stderr)


if __name__ == "__main__":
    main()
