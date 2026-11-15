# -*- coding: utf-8 -*-
"""
Extract the logic expressions of DOT/FAA/AR-01/18, Appendix C ("Airborne
software logic profile") into tests/data/ar0118_appendix_c.tsv.

Input: the text of the report produced by `pdftotext -layout` (poppler).
    pdftotext -layout AR-01-18.pdf ar0118.txt
    python tests/tools/extract_ar0118_appendix_c.py ar0118.txt

Each expression keeps its original (abstracted Ada) text, the Appendix C
section and page it was printed on, the number of conditions stated by its
section heading ("Expressions With N Conditions"), and its "response
profile" when the section gives one. A response profile is the column of results of the
truth table, first condition being the most significant bit
(e.g. "Bv and (Bv2 or Bv3)" is listed under "7:FFFFFTTT").

The Ada text is converted to this tool's grammar:
  - and, or, not and parentheses are kept as operators;
  - every other piece of text between operators is a *condition*
    (e.g. "Ev = El", "Iv not in It"). Identical text = same condition;
  - "Bv = True" / "Bv /= False" -> Bv, "Bv = False" / "Bv /= True" -> not Bv,
    where Bv is a Boolean variable code (Bv, Bv2, ...);
  - "Bv = Bv2" -> (Bv == Bv2), "Bv /= Bv2" -> (Bv != Bv2): two conditions;
  - a relational condition and its complement are one condition:
    "X /= Y" -> not (X = Y), "X >= Y" -> not (X < Y), "X <= Y" -> not (X > Y),
    "X not in Y" -> not (X in Y);
  - expressions using short-circuit forms (and then, or else), xor, a call
    syntax inside a condition, or "= not" are not converted (the converted
    column is left empty).
"""

import re
import sys
from pathlib import Path

STATEMENT_CODES = r"(?:\(\)|'b|:=>|::=|:=|=>|exit|if|return|while)"
# Statement / Occurs columns at the end of a line ("II" is a print artifact on page C-59)
TRAILING = re.compile(r"\s+" + STATEMENT_CODES + r"(?:\s+\d+)?\s*$|\s{2,}(?:\d+|II)\s*$")
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


TOKEN = re.compile(r"\(|\)|[^\s()]+")


def convert(raw):
    """Ada abstracted expression -> this tool's grammar, or None."""
    if re.search(r"\band then\b|\bor else\b|\bxor\b", raw, re.IGNORECASE):
        return None              # short-circuit forms; xor has no direct equivalent here
    if re.search(r"=\s*not\b", raw):
        return None              # "Bv = not (Bv2)": a condition containing an operator
    tokens = TOKEN.findall(raw.replace("{", " {").split(" {")[0])
    out, atom, atoms = [], [], {}

    def close_atom():
        if not atom:
            return True
        text = " ".join(atom)
        atom.clear()
        m = re.fullmatch(r"(Bv\d*)\s*(=|/=)\s*(True|False|true|false)", text)
        if m:
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
        if low in ("and", "or", "not"):
            close_atom()
            out.append(low)
        elif tok == "(":
            if atom:
                return None          # call or index syntax inside a condition
            out.append("(")
        elif tok == ")":
            close_atom()
            out.append(")")
        else:
            atom.append(tok)
        i += 1
    close_atom()
    text = " ".join(out).replace("( ", "(").replace(" )", ")")
    return "R = " + text


def main():
    source = Path(sys.argv[1]).read_text(encoding="latin-1").splitlines()
    entries = parse_report(source)
    out = Path(__file__).resolve().parents[1] / "data" / "ar0118_appendix_c.tsv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# Source: DOT/FAA/AR-01/18 (Chilenski, 2001), Appendix C.\n")
        f.write("# Generated by tests/tools/extract_ar0118_appendix_c.py - do not edit by hand.\n")
        f.write("id\tsection\tpage\tconditions\tprofile_number\tprofile\traw\tconverted\n")
        for n, e in enumerate(entries, 1):
            converted = convert(e["raw"]) or ""
            f.write(f"C{n:04d}\t{e['section']}\t{e['page']}\t{e['conditions']}\t"
                    f"{e['number'] or ''}\t{e['profile'] or ''}\t{e['raw']}\t{converted}\n")
    print(f"{len(entries)} expressions written to {out}")


if __name__ == "__main__":
    main()
