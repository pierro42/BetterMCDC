# -*- coding: utf-8 -*-
"""
Input language: "Output = <boolean expression>" -> Decision.

Accepted: variable names, and / et / &&, or / ou / ||, not / non / !,
== (xnor), != / xor / ouexclusif / ^ (xor), True, False and parentheses.
Each occurrence of a variable is a condition (a#1, a#2 when a variable is
repeated).

xor, ouexclusif and ^ are the same operator as != on Booleans; they become
Python's ^ and an "ne" node of the tree. Python and C don't give ^ the same
precedence against == and != (Python reads a ^ b == c as (a ^ b) == c, C as
a ^ (b == c)), so a ^ operand of == or != must be in parentheses.

Short-circuit forms ([S2] glossary): "and then" and "or else" always
evaluate their right operand only when needed. With short_circuit=True,
every and / or (also written et / ou / && / ||) is a short-circuit form, as
&& and || are in C.
"""

import ast
import copy
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
            ast.Compare, ast.Eq, ast.NotEq, ast.BinOp, ast.BitXor,
            ast.Name, ast.Load, ast.Constant)
_ALLOWED_TEXT = ("names, and/et/&&, or/ou/||, and then, or else, not/non/!, ==, "
                 "!=/xor/ouexclusif/^, True, False")
_SHORT_CIRCUIT_WORDS = {"and": "then", "or": "else"}

_FRENCH = {"et": "and", "ou": "or", "non": "not"}
_TO_FRENCH = {v: k for k, v in _FRENCH.items()}
# xor (lower case, like and / or / not) and ouexclusif (any case, like the
# other French words) are written ^ for Python
_XOR = "xor"
_XOR_FRENCH = "ouexclusif"
# "!" becomes "(not " and its operand gets a ")": as in C, ! binds tighter
# than every other operator (!a == b is (!a) == b)
_SYMBOLS = {"&&": " and ", "||": " or ", "!": "(not "}
_TO_SYMBOLS = {"and": "&&", "or": "||", "not": "!"}
# tokens after which a "!" is a unary not ("then" / "else" end "and then" / "or else")
_BEFORE_NOT = {"(", "=", "==", "!=", "!", "&", "|", "^", "and", "or", "not", "then", "else",
               _XOR}


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
    The operators && and || (two adjacent & or | tokens), ! and ^ count as
    words; the operand of a replaced ! is closed with ")".
    `replace(word)` returns the new word, or None to keep it.

    Returns (new_text, shifts) where shifts lists (new_start, new_end,
    old_start, old_end) for each replacement, in order: its span in new_text
    and in text, to map positions back (_typed_position)."""
    tokens = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            # Python 3.11 returns "!" as an ERRORTOKEN and the blank before
            # it as another ERRORTOKEN; blanks are not words, so drop them
            if tok.type == tokenize.ERRORTOKEN and not tok.string.strip():
                continue
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
                     or previous.string.lower() in _FRENCH
                     or previous.string.lower() == _XOR_FRENCH)
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
        elif tok.string == "^":     # alone; "^=" is a separate token
            new = replace("^")
        else:
            new = None
        if i in closers:
            new = (tok.string if new is None else new) + ")" * closers[i]
        if new is None:
            continue
        out.append(text[last:start])
        new_start = sum(len(s) for s in out)
        shifts.append((new_start, new_start + len(new), start, end))
        out.append(new)
        last = end
    out.append(text[last:])
    return "".join(out), shifts


def _typed_position(shifts, position, end=False):
    """Index in the text as typed of `position` in the text returned by
    _replace_words. The text between replacements is copied unchanged; a
    position inside a replaced word gives the start of the word as typed, or
    its end with end=True (for the end of a span)."""
    typed = position
    for new_start, new_end, old_start, old_end in shifts:
        if position < new_start:
            break
        if position < new_end or (end and position == new_end):
            return old_end if end else old_start
        typed = old_end + (position - new_end)
    return typed


_MARK = "\x00"                     # can't be in a name: used for placeholders


def _unparse(expr):
    """ast.unparse, keeping the parentheses that a reader of the C
    precedence needs: around a ==, != or ^ under a not (C's ! applies to the
    next operand only), and around a ^ under == or != (C reads ^ after == and
    !=). ast.unparse drops them because Python doesn't need them."""
    parts = []

    class Keep(ast.NodeTransformer):
        def hold(self, node, kinds):
            if not isinstance(node, kinds):
                return node
            parts.append(node)
            return ast.Name(id=f"{_MARK}{len(parts) - 1}{_MARK}", ctx=ast.Load())

        def visit_UnaryOp(self, node):
            self.generic_visit(node)
            node.operand = self.hold(node.operand, (ast.Compare, ast.BinOp))
            return node

        def visit_Compare(self, node):
            self.generic_visit(node)
            node.left = self.hold(node.left, ast.BinOp)
            node.comparators = [self.hold(c, ast.BinOp) for c in node.comparators]
            return node

    text = ast.unparse(Keep().visit(copy.deepcopy(expr)))
    # a part is held after the parts inside it, so replace the outer ones first
    for k in reversed(range(len(parts))):
        text = text.replace(f"{_MARK}{k}{_MARK}", f"({ast.unparse(parts[k])})")
    return text


def _parenthesized(source, node):
    """Is `node` written in parentheses in the one-line `source`, given as
    UTF-8 bytes (ast offsets are in UTF-8 bytes)?"""
    before = source[:node.col_offset].rstrip()
    after = source[node.end_col_offset:].lstrip()
    return before.endswith(b"(") and after.startswith(b")")


def parse_decision(text, short_circuit=False):
    """Parse "Output = <boolean expression>" into a Decision.
    With short_circuit=True every and / or is a short-circuit form ("and
    then" / "or else" always are).
    Raises ValueError with a readable message if the text is not valid."""
    text = " ".join(text.splitlines()).strip()
    used = set()                    # which alternative spellings the user wrote
    operators = []                  # (spelling, short-circuit) of each and / or, in order
    xors = []                       # spelling of each ^ / xor / ouexclusif, in order

    def to_python(word):
        if word == "^":
            xors.append(word)
            return None
        if word == _XOR or word.lower() == _XOR_FRENCH:
            xors.append(word)
            return " ^ "
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
        column = _typed_position(shifts, (e.offset or 1) - 1) + 1
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

    # an operator (ast.USub, ast.Lt, ast.BitAnd...) has no text of its own:
    # quote the expression that uses it
    parent = {id(child): node for node in ast.walk(expr) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(expr):
        if not isinstance(node, _ALLOWED):
            quoted = ast.unparse(node) or ast.unparse(parent.get(id(node), expr))
            raise ValueError(f"unsupported syntax: '{quoted}' (allowed: {_ALLOWED_TEXT})")
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
            raise ValueError(f"only True and False are allowed as constants, "
                             f"not '{ast.unparse(node)}'")
        if isinstance(node, ast.Compare) and len(node.ops) != 1:
            # Python reads a != b != c as (a != b) and (b != c)
            raise ValueError(f"chained comparison '{ast.unparse(node)}' is ambiguous, "
                             f"add parentheses, e.g. (a != b) != c")
        if isinstance(node, ast.Compare):
            source = python_text.encode("utf-8")
            for operand in [node.left] + node.comparators:
                if isinstance(operand, ast.BinOp) and not _parenthesized(source, operand):
                    # Python reads a ^ b == c as (a ^ b) == c, C as a ^ (b == c);
                    # quote the comparison as typed (ast offsets are in UTF-8 bytes)
                    chars = lambda offset: len(source[:offset].decode("utf-8"))
                    start = _typed_position(shifts, chars(node.col_offset))
                    end = _typed_position(shifts, chars(node.end_col_offset), end=True)
                    written = " ".join(text[start:end].split())
                    raise ValueError(f"'{written}' mixes xor with == or != without "
                                     f"parentheses, which Python and C read differently: "
                                     f"write (a ^ b) == c or a ^ (b == c)")

    # Every occurrence of a variable is a condition, in reading order
    occurrences = sorted((node for node in ast.walk(expr) if isinstance(node, ast.Name)),
                         key=lambda node: (node.lineno, node.col_offset))
    if not occurrences:
        raise ValueError("the expression has no input variable")
    names = list(dict.fromkeys(node.id for node in occurrences))
    if output in names:
        raise ValueError(f"'{output}' is used both as output and as input")
    if "then" in names:
        # "and then" is an operator: a variable called then could be read as
        # its second word (else is a Python keyword already)
        raise ValueError("'then' can't be a variable name: it is part of the 'and then' "
                         "operator")

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
    xor_iter = iter(xors)
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
        if word == "^":
            typed = next(xor_iter)
            return None if typed == word else typed
        return spelling.get(word)

    label_text = _replace_words(_unparse(expr), display)[0]
    label_text = re.sub(r"!\s+", "!", label_text)       # "! a" -> "!a" ("!=" has no space)

    nodes, leaf = build_tree(expr, occurrences, short_circuit_at)
    path_nodes = [path_to_root(nodes, leaf[k]) for k in range(len(occurrences))]
    paths = [sum(1 << n for n in path) for path in path_nodes]

    def evaluate(cond):
        return node_values(nodes, cond)[-1]

    has_short_circuit = any(kind in ("andthen", "orelse") for kind, _, _ in nodes)
    return Decision(output, names, labels, variable, evaluate, label_text,
                    nodes, path_nodes, paths, has_short_circuit)
