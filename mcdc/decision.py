# -*- coding: utf-8 -*-
"""
Input language: "Output = <boolean expression>" -> Decision.

Accepted: variable names, and / et / &&, or / ou / ||, not / non / !,
== and != (xor), True, False and parentheses. Each occurrence of a variable
is a condition (a#1, a#2 when a variable is repeated).

Short-circuit forms ([S2] glossary): "and then" and "or else" always
evaluate their right operand only when needed. With short_circuit=True,
every and / or (also written et / ou / && / ||) is a short-circuit form, as
&& and || are in C.
"""

import ast
import io
import re
import tokenize
from typing import Callable, List, NamedTuple

from .tree import build_tree, node_values, path_to_root


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
    short_circuit: bool = False      # the tree has and-then / or-else nodes


# The only syntax accepted in an expression
_ALLOWED = (ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
            ast.Compare, ast.Eq, ast.NotEq, ast.Name, ast.Load, ast.Constant)
_ALLOWED_TEXT = ("names, and/et/&&, or/ou/||, and then, or else, not/non/!, ==, !=, "
                 "True, False")
_SHORT_CIRCUIT_WORDS = {"and": "then", "or": "else"}

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
            second = _SHORT_CIRCUIT_WORDS.get(tok.string)
            if (second is not None and following is not None
                    and following.type == tokenize.NAME and following.string == second):
                new = replace(f"{tok.string} {second}")     # and then / or else
                if new is not None:
                    end, skip = following.end[1], True
            else:
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


def parse_decision(text, short_circuit=False):
    """Parse "Output = <boolean expression>" into a Decision.
    With short_circuit=True every and / or is a short-circuit form ("and
    then" / "or else" always are).
    Raises ValueError with a readable message if the text is not valid."""
    text = " ".join(text.splitlines()).strip()
    used = set()                    # which alternative spellings the user wrote
    operators = []                  # (spelling, short-circuit) of each and / or, in order

    def to_python(word):
        if word in ("and then", "or else"):
            operators.append((word, True))
            return f" {word.split()[0]} "
        if word in ("and", "or"):
            operators.append((word, short_circuit))
            return None
        if word in ("&&", "||"):
            operators.append((word, short_circuit))
        elif word.lower() in ("et", "ou"):
            operators.append((word, short_circuit))
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

    # Which and / or are short-circuit forms: the k-th "and" / "or" keyword
    # of the Python text is the k-th operator the user wrote. ast offsets are
    # in UTF-8 bytes.
    keywords = [len(python_text[:tok.start[1]].encode("utf-8"))
                for tok in tokenize.generate_tokens(io.StringIO(python_text).readline)
                if tok.type == tokenize.NAME and tok.string in ("and", "or")]
    if len(keywords) != len(operators):
        raise ValueError("internal error: and / or operators not matched")
    sc_offsets = [offset for offset, (_, sc) in zip(keywords, operators) if sc]

    def short_circuit_at(left, right):
        return any(left.end_col_offset <= offset < right.col_offset for offset in sc_offsets)

    # Display text: the k-th variable token is occurrence k (reading order),
    # each and / or is written as the user wrote it, and not goes back to the
    # spelling the user used (French, !)
    label_iter = iter(labels)
    operator_iter = iter(operators)
    spelling = {}
    if "french" in used:
        spelling.update(_TO_FRENCH)
    if "symbols" in used:
        spelling.update(_TO_SYMBOLS)

    def display(word):
        if word in names:
            return next(label_iter)
        if word in ("and", "or"):
            typed = next(operator_iter)[0]
            return None if typed == word else typed
        return spelling.get(word)

    label_text = _replace_words(ast.unparse(expr), display)[0]
    label_text = re.sub(r"!\s+", "!", label_text)       # "! a" -> "!a" ("!=" has no space)

    nodes, leaf = build_tree(expr, occurrences, short_circuit_at)
    path_nodes = [path_to_root(nodes, leaf[k]) for k in range(len(occurrences))]
    paths = [sum(1 << n for n in path) for path in path_nodes]

    def evaluate(cond):
        return node_values(nodes, cond)[-1]

    has_short_circuit = any(kind in ("andthen", "orelse") for kind, _, _ in nodes)
    return Decision(output, names, labels, variable, evaluate, label_text,
                    nodes, path_nodes, paths, has_short_circuit)
