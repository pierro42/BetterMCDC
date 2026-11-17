# -*- coding: utf-8 -*-
"""
Extract the logic expressions of DOT/FAA/AR-01/18, Appendix C ("Airborne
software logic profile") into tests/data/ar0118_appendix_c.tsv.

Input: the text of the report produced by pdftotext (xpdf 4.00), twice:
    pdftotext -layout AR-01-18.pdf ar0118.txt
    pdftotext -table AR-01-18.pdf ar0118_table.txt
    python tests/tools/extract_ar0118_appendix_c.py ar0118.txt ar0118_table.txt

Each expression keeps its original (abstracted Ada) text, the Appendix C
section and page it was printed on, the number of conditions stated by its
section heading ("Expressions With N Conditions"), its "response
profile" when the section gives one, and how many times it occurs in the
software (sum of its Occurs column). The occurrences are read from the
-table text, which keeps each Occurs value on its expression's row (the
-layout text sometimes moves it to a heading line); the two texts are
matched expression by expression. A response profile is the column of results of the
truth table, first condition being the most significant bit
(e.g. "Bv and (Bv2 or Bv3)" is listed under "7:FFFFFTTT").

The Ada text is converted to this tool's grammar:
  - and, or, not, and then, or else and parentheses are kept as operators
    ("and then" / "or else" are the tool's short-circuit forms);
  - every other piece of text between operators is a *condition*
    (e.g. "Ev = El", "Iv not in It"). Identical text = same condition;
  - "Bv = True" / "Bv /= False" -> Bv, "Bv = False" / "Bv /= True" -> not Bv,
    where Bv is a Boolean variable code (Bv, Bv2, ...);
  - "Bv = Bv2" -> (Bv == Bv2), "Bv /= Bv2" -> (Bv != Bv2): two conditions;
  - a relational condition and its complement are one condition:
    "X /= Y" -> not (X = Y), "X >= Y" -> not (X < Y), "X <= Y" -> not (X > Y),
    "X not in Y" -> not (X in Y);
  - "X xor Y" -> ((X) != (Y)) (see _render_xor);
  - "Bv = not (Bv2)" -> (Bv == (not Bv2)): two conditions;
  - parentheses after the start of a condition (call, index or arithmetic,
    e.g. "Fxv > (Fxv2-url)") are part of that condition's text.
"""

import re
import sys
from pathlib import Path

STATEMENT_CODES = r"(?:\(\)|'b|b'|:=>|::=|:=|=>|exit|if|return|while)"   # 'b is also printed b'
# Statement / Occurs columns at the end of a line ("II" is a print artifact on page C-59),
# and the column headings when the layout puts them on an expression's line
TRAILING = re.compile(r"\s+" + STATEMENT_CODES + r"(?:\s+\d+)?\s*$|\s{2,}(?:\d+|II)\s*$"
                      r"|\s{2,}Statement\s+Occurs\s*$")
PAGE = re.compile(r"^\s*C-(\d+)\s*$")
GROUP = re.compile(r"^\s*C\.(\d+)\s+Expressions With (\w+) Conditions?")
NUMBERS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6,
           "Seven": 7, "Eight": 8, "Nine": 9, "Ten": 10}
PROFILE = re.compile(r"^\s*(C\.[\d.]+)\s+.*Response Profile\s+(\d+):\s*([TFtf-]*)")
PROFILE_TAIL = re.compile(r"^\s*([TFtf-]+)\s*$")    # profile string wrapped to the next line
SKIP = re.compile(r"^\s*(Expression|Statement|Occurs|" + STATEMENT_CODES + r")(?=\s|$).*$"
                  r"|^\s*\d+\s*$")
BOOL_VAR = re.compile(r"^Bv\d*$")


def _clean(line):
    line = TRAILING.sub("", line.rstrip())
    return line.strip()


def _incomplete(text):
    depth = text.count("(") - text.count(")")
    return (depth > 0 or re.search(r"\b(and|or|xor|not|then|else)$", text) is not None
            or re.search(r"[=<>/]$", text) is not None)


def parse_report(lines):
    """Yield dicts with section, page, profile, raw expression."""
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("C.1 Expressions With One"))
    end = next(i for i, l in enumerate(lines)
               if i > start and "APPENDIX D" in l)
    section, profile, number, count = None, None, None, None
    pending, entries, current = [], [], None

    def flush():
        nonlocal current
        if current:
            pending.append(current)
            current = None

    for line in lines[start:end]:
        if profile == "" and PROFILE_TAIL.match(line):
            profile = PROFILE_TAIL.match(line).group(1)
            continue
        page = PAGE.match(line) or PAGE.match(_clean(line))
        if page:
            flush()
            for entry in pending:
                entry["page"] = f"C-{page.group(1)}"
            entries.extend(pending)
            pending.clear()
            continue
        header = PROFILE.match(line)
        if header:
            flush()
            section, number, profile = header.group(1), header.group(2), header.group(3)
            continue
        group = GROUP.match(line)
        if group:
            flush()
            section, number, profile = f"C.{group.group(1)}", None, None
            word = group.group(2)
            count = NUMBERS[word] if word in NUMBERS else int(word)
            continue
        if not line.strip() or SKIP.match(line):
            continue
        text = _clean(line)
        if not text:
            continue
        # continuation lines, and constraints such as "{url<url2}" on their own line
        if current and (_incomplete(current["raw"])
                        or re.match(r"^(and|or|xor)\b|^\{|^[=<>/]", text)):
            current["raw"] += " " + text
        else:
            flush()
            current = {"section": section, "number": number, "profile": profile,
                       "conditions": count, "raw": text, "page": ""}
    flush()
    entries.extend(pending)
    return entries


OCCURS_TAIL = re.compile(r"^(.*?)\s{2,}(" + STATEMENT_CODES + r")\s+(\d+)\s*$")
OCCURS_ONLY = re.compile(r"^\s*(" + STATEMENT_CODES + r")\s+(\d+)\s*$")
NOT_EXPRESSION = re.compile(r"^\s*C\.\d+(\.\d+)*\s|^\s*Expression\s+Statement|^\s*C-\d+\s*$"
                            r"|^\s*\d+\s*$|^\s*(Expression|Statement|Occurs)\s*$"
                            r"|^\s*[TFtf-]+\s*$")


def add_occurrences(table_lines, entries):
    """Set entry["occurs"] from the -table text: every row of the Appendix C
    expression listing, in order, with the Occurs values of its row and of
    the statement-only rows below it. The rows are matched to `entries` by
    their text (white space ignored); any difference stops the extraction."""
    start = next(i for i, l in enumerate(table_lines)
                 if l.strip().startswith("C.1 Expressions With One"))
    end = next(i for i, l in enumerate(table_lines) if i > start and "APPENDIX D" in l)
    rows = []                                          # [text, occurs]
    for line in table_lines[start:end]:
        if not line.strip() or NOT_EXPRESSION.match(line):
            continue
        only = OCCURS_ONLY.match(line)
        if only:
            rows[-1][1] += int(only.group(2))
            continue
        tail = OCCURS_TAIL.match(line)
        text, occurs = (tail.group(1).strip(), int(tail.group(3))) if tail else (line.strip(), 0)
        text = re.sub(r"\s{2,}(II|\d+)\s*$", "", text)
        rows.append([text, occurs])

    def compact(s):
        return re.sub(r"\s+", "", s)

    i = 0
    for entry in entries:
        target, text, occurs = compact(entry["raw"]), "", 0
        while i < len(rows) and len(text) < len(target):
            text += compact(rows[i][0])
            occurs += rows[i][1]
            i += 1
        if text != target:
            raise SystemExit(f"-table text does not match: {entry['raw']!r} / {text!r}")
        entry["occurs"] = occurs
    if i != len(rows):
        raise SystemExit(f"{len(rows) - i} rows of the -table text are not matched")


TOKEN = re.compile(r"\(|\)|[^\s()]+")


def _render_xor(tokens):
    """Rewrite Ada's xor as the tool's != operator. Ada doesn't allow xor
    and and/or at the same level without parentheses, so each level holding
    xor is a chain X1 xor X2 xor ... (left-associative), written
    ((X1) != (X2)) != (X3); the parentheses keep each operand whole (in the
    tool's grammar, as in Python, != binds tighter than not / and / or)."""
    def parse(i):
        items = []
        while i < len(tokens):
            if tokens[i] == "(":
                sub, i = parse(i + 1)
                items.append(sub)
            elif tokens[i] == ")":
                return items, i + 1
            else:
                items.append(tokens[i])
                i += 1
        return items, i

    def render(items):
        elements = ["(" + render(x) + ")" if isinstance(x, list) else x for x in items]
        if "xor" not in elements:
            return " ".join(elements)
        if any(e in ("and", "or", "and then", "or else") for e in elements):
            raise ValueError("xor mixed with and / or without parentheses")
        parts = [[]]
        for e in elements:
            if e == "xor":
                parts.append([])
            else:
                parts[-1].append(e)
        text = "(" + " ".join(parts[0]) + ")"
        for part in parts[1:]:
            text = "(" + text + " != (" + " ".join(part) + "))"
        return text

    return render(parse(0)[0])


def convert(raw):
    """Ada abstracted expression -> this tool's grammar, or None."""
    # "Bv = not (Bv2)": a relational operator between Booleans, kept whole
    raw = re.sub(r"\b(Bv\d*)\s*=\s*not\s*\(\s*(Bv\d*)\s*\)", r"\1 =not= \2", raw)
    tokens = TOKEN.findall(raw.replace("{", " {").split(" {")[0])
    out, atom, atoms = [], [], {}

    def close_atom():
        if not atom:
            return True
        text = " ".join(atom)
        atom.clear()
        m = re.fullmatch(r"(Bv\d*)\s*(=|/=)\s*(True|False|true|false)", text)
        not_equal = re.fullmatch(r"(Bv\d*) =not= (Bv\d*)", text)
        if not_equal:
            out.append(f"({not_equal.group(1)} == (not {not_equal.group(2)}))")
        elif m:
            negate = (m.group(2) == "=") != (m.group(3).lower() == "true")
            out.append(("not " if negate else "") + m.group(1))
        elif re.fullmatch(r"Bv\d*\s*(=|/=)\s*Bv\d*", text):
            left, op, right = re.fullmatch(r"(Bv\d*)\s*(=|/=)\s*(Bv\d*)", text).groups()
            out.append(f"({left} {'==' if op == '=' else '!='} {right})")
        elif BOOL_VAR.match(text):
            out.append(text)
        elif text in ("True", "False"):
            out.append(text)
        else:
            # A relational condition and its complement are the same
            # condition ("X /= Y" is "not (X = Y)", "X >= Y" is "not (X < Y)"...);
            # the condition takes the polarity of its first occurrence.
            key, positive = text, True
            m = re.fullmatch(r"(.+?)\s+(/=|>=|<=|not in|=|<|>|in)\s+(.+)", text)
            if m:
                complement = {"/=": "=", ">=": "<", "<=": ">", "not in": "in"}
                op = m.group(2)
                positive = op not in complement
                key = f"{m.group(1)} {complement.get(op, op)} {m.group(3)}"
            if key not in atoms:
                atoms[key] = (f"atom{len(atoms) + 1}", positive)
            name, first = atoms[key]
            out.append(name if positive == first else f"not {name}")

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        low = tok.lower()
        if low == "not" and i + 1 < len(tokens) and tokens[i + 1].lower() == "in":
            atom.extend(tokens[i:i + 2])
            i += 2
            continue
        second = {"and": "then", "or": "else"}.get(low)
        if second and i + 1 < len(tokens) and tokens[i + 1].lower() == second:
            close_atom()
            out.append(f"{low} {second}")       # short-circuit form
            i += 2
            continue
        if low in ("and", "or", "not", "xor"):
            close_atom()
            out.append(low)
        elif tok == "(":
            if atom:
                # call, index or arithmetic parentheses inside a condition,
                # e.g. "Fxv > (Fxv2-url)": part of the condition's text
                depth = 0
                while i < len(tokens):
                    depth += {"(": 1, ")": -1}.get(tokens[i], 0)
                    atom.append(tokens[i])
                    i += 1
                    if depth == 0:
                        break
                continue
            out.append("(")
        elif tok == ")":
            close_atom()
            out.append(")")
        else:
            atom.append(tok)
        i += 1
    close_atom()
    text = _render_xor(out).replace("( ", "(").replace(" )", ")")
    return "R = " + text


def main():
    source = Path(sys.argv[1]).read_text(encoding="latin-1").splitlines()
    entries = parse_report(source)
    add_occurrences(Path(sys.argv[2]).read_text(encoding="latin-1").splitlines(), entries)
    out = Path(__file__).resolve().parents[1] / "data" / "ar0118_appendix_c.tsv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# Source: DOT/FAA/AR-01/18 (Chilenski, 2001), Appendix C.\n")
        f.write("# Generated by tests/tools/extract_ar0118_appendix_c.py - do not edit by hand.\n")
        f.write("id\tsection\tpage\tconditions\tprofile_number\tprofile\traw\tconverted"
                "\toccurs\n")
        for n, e in enumerate(entries, 1):
            converted = convert(e["raw"]) or ""
            f.write(f"C{n:04d}\t{e['section']}\t{e['page']}\t{e['conditions']}\t"
                    f"{e['number'] or ''}\t{e['profile'] or ''}\t{e['raw']}\t{converted}"
                    f"\t{e['occurs']}\n")
    print(f"{len(entries)} expressions ({sum(e['occurs'] for e in entries)} occurrences) "
          f"written to {out}")


if __name__ == "__main__":
    main()
