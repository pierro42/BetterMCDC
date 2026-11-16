# MC/DC test case generator

Command-line tool that takes a Boolean expression and gives the test cases needed to test it:

- **Truth table:** the full truth table, with the variable names as column headers.
- **MC/DC test set:** the minimal set of test cases, with expected results, that satisfies MC/DC (Modified Condition / Decision Coverage), in masking or unique-cause form.
- **Repeated variables:** expressions where a variable appears more than once, such as `(a and b) or (not c and a)`, are handled.
- **Test scenario file:** optionally, the test cases written as a scenario file (C++, or any other text format) through a user template. See [docs/SCENARIO_GENERATION.md](docs/SCENARIO_GENERATION.md).

The MC/DC definitions come from the FAA and NASA reports used in certification. [docs/MCDC_IMPLEMENTATION.md](docs/MCDC_IMPLEMENTATION.md) describes how they are implemented, and [tests/SOURCES.md](tests/SOURCES.md) traces the qualification test suite to those reports.

## Requirements

- Python 3.11 or later (tested with 3.12.4).
- Standard library only: nothing to install.

## Quick start

Full truth table:

```bash
python main.py "Out = (a and b) or c"
```

```
# | a | b | c | Out
--+---+---+---+----
1 | 0 | 0 | 0 |  0
2 | 0 | 0 | 1 |  1
...
8 | 1 | 1 | 1 |  1
```

Minimal masking MC/DC test set:

```bash
python main.py "Out = (a and b) or c" --mcdc
```

```
# | a | b | c | Out
--+---+---+---+----
2 | 0 | 0 | 1 |  1
3 | 0 | 1 | 0 |  0
5 | 1 | 0 | 0 |  0
7 | 1 | 1 | 0 |  1

4 test case(s) instead of 8.

Decision : Out = a and b or c
Method   : masking MC/DC, 3 condition(s), exact (whole truth table)

Independence pairs:
  a : #3 / #7   Out 0 -> 1   (1 possible pair(s))
  b : #5 / #7   Out 0 -> 1   (1 possible pair(s))
  c : #2 / #3   Out 1 -> 0   (9 possible pair(s))   masked: b

Minimum  : 4 test(s), proven minimal
```

Running `python main.py` with no expression prints the help.

## Writing an expression

The expression is one quoted argument, `"Output = <expression>"`. `Output` is the name of the result column. Without `Output =`, the result column is called `result`.

| Meaning | Accepted spellings |
|---|---|
| and | `and`, `et`, `&&` |
| or | `or`, `ou`, `\|\|` |
| not | `not`, `non`, `!` |
| xor | `!=` |
| equivalence (xnor) | `==` |
| constants | `True`, `False` |
| grouping | `( )` |

- **Variable names:** letters, digits and `_`, not starting with a digit. `et`, `ou` and `non` are keywords in any case, so they can't be variable names.
- **Mixing spellings:** allowed. `(a ou b) && !c` is valid.
- **Precedence:** as in Python: `not`, then `and`, then `or`. `==` and `!=` bind tighter than `not`, so add parentheses when you mean `(not a) == b`.
- **`!`:** binds tighter than every operator, as in C, so `!a == b` means `(!a) == b`.
- **Evaluation:** `&&` and `||` are Boolean and/or. Both operands are part of the decision; there is no short-circuit evaluation.
- **Chained comparisons:** `a != b != c` is rejected as ambiguous. Write `(a != b) != c`.

Errors are reported with a message; syntax errors give the column in the text as you typed it:

```
main.py: error: invalid expression: unsupported syntax: 'a + b' (allowed: names, and/et/&&, or/ou/||, not/non/!, ==, !=, True, False)
```

### Conditions and repeated variables

MC/DC is about *conditions*: each occurrence of a variable in the expression is a separate condition. In `(a and bd) or (not c and a)` there are four conditions, labelled `a#1`, `bd`, `c`, `a#2`. `a#1` and `a#2` are *coupled*: they always have the same value. The truth table still has one column per variable.

## Options

| Option | Effect |
|---|---|
| `--mcdc` | reduce the table to a minimal masking MC/DC test set |
| `--mcdc unique-cause` | the same with unique-cause MC/DC |
| `--csv` | print the table as CSV (the summary is not printed) |
| `--max-exact N` | number of inputs up to which the whole truth table is analysed (default 10); see [Large expressions](#large-expressions) |
| `-gen_scen TEMPLATE` (or `--gen-scen`) | also write a test scenario file; see [docs/SCENARIO_GENERATION.md](docs/SCENARIO_GENERATION.md) |
| `--output-dir DIR` | folder for the scenario file (default: `output/` next to `main.py`) |

## Reading the MC/DC summary

- **`#` column:** the row number in the full truth table, so a reduced table traces back to the full one. The first input is the most significant bit, and numbering starts at 1.
- **Independence pairs:** for each condition, the two test cases that show it independently affects the output.
  - `(N possible pair(s))` is how many valid pairs exist.
  - `masked:` lists the other conditions that also change within that pair; in masking MC/DC their effect is blocked by another operator.
- **`NONE`:** no pair exists.
  - `redundant`: the condition never affects the output on its own, which is often a sign of a design error.
  - `coupled`: in unique-cause MC/DC a repeated variable can never change alone. Use masking MC/DC.
- **`Minimum`:**
  - `proven minimal` means no smaller set exists.
  - `not proven minimal` means the set is valid but may not be the smallest; the published lower bound is shown.

Example with a repeated variable in unique-cause mode:

```bash
python main.py "Out = (a and bd) or (not c and a)" --mcdc unique-cause
```

```
Independence pairs:
  a#1 : NONE - coupled with a#2: they always change together, use --mcdc masking
  bd  : #6 / #8   Out 0 -> 1   (1 possible pair(s))
  c   : #5 / #6   Out 1 -> 0   (1 possible pair(s))
  a#2 : NONE - coupled with a#1: they always change together, use --mcdc masking
```

## Masking or unique-cause?

Both forms are accepted for DO-178C. Usually your plans and your structural coverage tool decide for you; otherwise use masking.

- **Your plans:** the form belongs in your PSAC and Software Verification Plan, agreed with your certification authority. Masking MC/DC was accepted by the authorities through the CAST-6 position paper (2001).
- **Your coverage tool:** use the form it measures on the real code, or it will report gaps.
- **Repeated variables:** unique-cause cannot cover them at all; only masking can.
- **Test count:** masking needs at most as many tests, and far fewer for large expressions. The published lower bounds are N + 1 tests for unique-cause and ⌈2√N⌉ for masking.
- **Review:** unique-cause pairs are easier to check by hand, since exactly one input changes.

## Large expressions

Up to `--max-exact` inputs (default 10), the tool builds the whole truth table, lists every independence pair and searches for the smallest test set.

Above that, it uses a pair-search engine that never builds the truth table. It searches one valid pair per condition directly, so expressions with tens of conditions take about a second. Its priority is completeness: every condition ends **covered**, **proven impossible**, or **UNKNOWN** (search budget exceeded, with a warning). None is dropped silently. The set it gives is valid but usually well above the minimum.

Without `--mcdc`, an expression with more than `--max-exact` inputs is refused, because its full truth table would have 2^N rows.

## Project layout

```
main.py                    command line
mcdc/                      the tool
  decision.py              input language -> conditions and expression tree
  tree.py                  evaluation, truth table, MC/DC pair definitions
  exact.py                 exact engine and minimal test set
  pair_search.py           engine for large expressions
  analysis.py              engine choice
  report.py                text / CSV output
  scenario.py              test scenario generation
input/test_setup.toml      example scenario template (C++)
output/                    generated scenario files
tests/                     qualification test suite (see tests/SOURCES.md)
docs/                      implementation and scenario documentation
ressources/                reference documents (PDF)
```

## Tests

Run from the project folder (about 25 s):

```bash
python -m unittest discover -s tests -v
```

- **`tests/test_qualification.py`:** expected results transcribed from published FAA/NASA reports. [tests/SOURCES.md](tests/SOURCES.md) lists the source of each test.
- **`tests/test_scenario.py`:** scenario generation and command line.
