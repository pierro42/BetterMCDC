# MC/DC test case generator

Command-line tool that takes a Boolean expression and gives the test cases needed to test it:

- **Truth table:** the full truth table, with the variable names as column headers.
- **MC/DC test set:** the minimal set of test cases, with expected results, that satisfies MC/DC (Modified Condition / Decision Coverage), in any of the three forms defined by the FAA report: masking, unique-cause + masking, or unique-cause.
- **Repeated variables:** expressions where a variable appears more than once, such as `(a and b) or (not c and a)`, are handled.
- **Test scenario file:** optionally, the test cases written as a scenario file (C++, or any other text format) through a user template. See [docs/SCENARIO_GENERATION.md](docs/SCENARIO_GENERATION.md).

The MC/DC definitions come from the FAA and NASA reports used in certification. [docs/MCDC_IMPLEMENTATION.md](docs/MCDC_IMPLEMENTATION.md) describes how they are implemented, and [tests/SOURCES.md](tests/SOURCES.md) traces the qualification test suite to those reports. [docs/IEC_61508_ADEQUACY.md](docs/IEC_61508_ADEQUACY.md) maps the tool to the support-tool requirements of IEC 61508-3.

## Why?

I wanted to implement a way to automatically generate tests against a known boolean equation that could be found in a specification document.

Open source software / Free software producing MC/DC analysis and tests are either hard to use, or not qualified against IEC / DO standards.
This is the end goal of this tool.  

I made this tool with the help of the available free documentation, and ressources I own (not listed here), and code review / doc / improvements with Claude Opus 5.5 Extra.


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
| and, short-circuit | `and then` (or any and with `--short-circuit`) |
| or, short-circuit | `or else` (or any or with `--short-circuit`) |
| xor | `!=` |
| equivalence (xnor) | `==` |
| constants | `True`, `False` |
| grouping | `( )` |

Note: French spellings are added for my personnal case.

- **Variable names:** letters, digits and `_`, not starting with a digit. `et`, `ou` and `non` are keywords in any case, so they can't be variable names.
- **Mixing spellings:** allowed. `(a ou b) && !c` is valid.
- **Precedence:** as in Python: `not`, then `and`, then `or`. `==` and `!=` bind tighter than `not`, so add parentheses when you mean `(not a) == b`.
- **`!`:** binds tighter than every operator, as in C, so `!a == b` means `(!a) == b`.
- **Evaluation:** by default, `and` / `&&` and `or` / `||` are Boolean: both operands are always evaluated. `and then` and `or else` are short-circuit forms: the right operand is evaluated only when the left one doesn't decide the result. To analyse C code, where `&&` and `||` are short-circuit, add `--short-circuit`: every and / or is then evaluated that way. See [Short-circuit evaluation](#short-circuit-evaluation).
- **`then` and `else`:** right after `and` / `or` they are part of the operator, so they can't be variable names there.
- **Chained comparisons:** `a != b != c` is rejected as ambiguous. Write `(a != b) != c`.

Errors are reported with a message; syntax errors give the column in the text as you typed it:

```
main.py: error: invalid expression: unsupported syntax: 'a + b' (allowed: names, and/et/&&, or/ou/||, and then, or else, not/non/!, ==, !=, True, False)
```

### Conditions and repeated variables

MC/DC is about *conditions*: each occurrence of a variable in the expression is a separate condition. In `(a and bd) or (not c and a)` there are four conditions, labelled `a#1`, `bd`, `c`, `a#2`. `a#1` and `a#2` are *coupled*: they always have the same value. The truth table still has one column per variable.

## Options

| Option | Effect |
|---|---|
| `--mcdc` | reduce the table to a minimal masking MC/DC test set |
| `--mcdc unique-cause+masking` | the same with unique-cause + masking MC/DC |
| `--mcdc unique-cause` | the same with unique-cause MC/DC |
| `--short-circuit` | evaluate every and / or (also `et`, `ou`, `&&`, `\|\|`) as a short-circuit form, as in C |
| `--csv` | print the table as CSV (the summary is not printed) |
| `--max-exact N` | number of inputs up to which the whole truth table is analysed (default 10); see [Large expressions](#large-expressions) |
| `-gen_scen TEMPLATE` (or `--gen-scen`) | also write a test scenario file; see [docs/SCENARIO_GENERATION.md](docs/SCENARIO_GENERATION.md) |
| `--output-dir DIR` | folder for the scenario file (default: `output/` next to `main.py`) |
| `--version` | print the tool version |

## Reading the MC/DC summary

- **`#` column:** the row number in the full truth table, so a reduced table traces back to the full one. The first input is the most significant bit, and numbering starts at 1.
- **`X`:** with short-circuit forms, an input that the test doesn't evaluate ("don't care"). Its row number counts it as 0.
- **Independence pairs:** for each condition, the two test cases that show it independently affects the output.
  - `(N possible pair(s))` is how many valid pairs exist.
  - `masked:` lists the other conditions that also change within that pair; their effect is blocked by another operator. In unique-cause + masking, these can only be other occurrences of the same variable.
- **`NONE`:** no pair exists.
  - `redundant`: the condition never affects the output on its own, which is often a sign of a design error.
  - `coupled`: in unique-cause MC/DC a repeated variable can never change alone; use unique-cause + masking or masking. With short-circuit forms it can, when its other occurrences aren't evaluated in one of the two tests; `coupled` then means no such pair exists. In unique-cause + masking, no pair exists where only that variable changes; masking MC/DC may still cover it.
- **`Minimum`:**
  - `proven minimal` means no smaller set exists.
  - `not proven minimal` means the set is valid but may not be the smallest; the published lower bound is shown.

Example with a repeated variable in unique-cause mode:

```bash
python main.py "Out = (a and bd) or (not c and a)" --mcdc unique-cause
```

```
Independence pairs:
  a#1 : NONE - coupled with a#2: they always change together, use --mcdc unique-cause+masking or masking
  bd  : #6 / #8   Out 0 -> 1   (1 possible pair(s))
  c   : #5 / #6   Out 1 -> 0   (1 possible pair(s))
  a#2 : NONE - coupled with a#1: they always change together, use --mcdc unique-cause+masking or masking
```

The same expression in unique-cause + masking mode: each `a` is shown by changing only `a`, the other occurrence being masked.

```bash
python main.py "Out = (a and bd) or (not c and a)" --mcdc unique-cause+masking
```

```
Independence pairs:
  a#1 : #4 / #8   Out 0 -> 1   (1 possible pair(s))   masked: a#2
  bd  : #6 / #8   Out 0 -> 1   (1 possible pair(s))
  c   : #5 / #6   Out 1 -> 0   (1 possible pair(s))
  a#2 : #1 / #5   Out 0 -> 1   (1 possible pair(s))   masked: a#1
```

## Which form: masking, unique-cause + masking or unique-cause?

The FAA report defines three forms, from the strictest to the weakest:

| Form | Between the two tests of a pair |
|---|---|
| unique-cause | only the condition shown changes |
| unique-cause + masking | only the *variable* of the condition shown changes; its other occurrences must be masked |
| masking | any condition may change, as long as only the condition shown affects the output |

Without repeated variables, unique-cause and unique-cause + masking give exactly the same pairs.

Usually your plans and your structural coverage tool decide for you; otherwise use masking.

- **Your plans:** the form belongs in your PSAC and Software Verification Plan, agreed with your certification authority. Masking MC/DC was accepted by the authorities through the CAST-6 position paper (2001). The FAA report says unique-cause + masking has been used in airplane certifications.
- **Your coverage tool:** use the form it measures on the real code, or it will report gaps.
- **Repeated variables:** unique-cause cannot cover them at all; unique-cause + masking and masking can.
- **Test count:** masking needs at most as many tests as the other forms, and far fewer for large expressions. The published lower bounds are N + 1 tests for unique-cause and ⌈2√N⌉ for masking.
- **Review:** the unique-cause forms are easier to check by hand, since exactly one input changes per pair.

## Short-circuit evaluation

With `and then` / `or else`, or with `--short-circuit`, the right operand of an and / or is evaluated only when needed. An input that a test doesn't evaluate can't influence the result, so:
- such inputs are shown `X` ("don't care", as in the NASA tutorial), and tests that only differ there are the same test;
- a pair can change such an input freely: the FAA report's influence tree counts a condition as changed only when it is evaluated in both tests.

Example, `A and then B and then C and then D`: 5 tests instead of 16, exactly the NASA tutorial's Table 32.

```bash
python main.py "Z = A and then B and then C and then D" --mcdc
```

```
#  | A | B | C | D | Z
---+---+---+---+---+--
1  | 0 | X | X | X | 0
9  | 1 | 0 | X | X | 0
13 | 1 | 1 | 0 | X | 0
15 | 1 | 1 | 1 | 0 | 0
16 | 1 | 1 | 1 | 1 | 1
```

The evaluation must match the code under test: in C and C++, `&&` and `||` are short-circuit, so use `--short-circuit`; in Ada, `and` / `or` are Boolean and `and then` / `or else` are short-circuit. A scenario file gives such inputs the template's `NOT_EVALUATED` value (by default the FALSE text).

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
  version.py               tool version
input/test_setup_cpp.toml  example scenario template (C++)
input/test_setup_python.toml  example scenario template (Python)
examples/                  example code under test
output/                    generated scenario files and validation records
tests/                     qualification test suite (see tests/SOURCES.md)
docs/                      implementation, scenario and IEC 61508 documentation
ressources/                reference documents (PDF)
```

## Tests

Run from the project folder (under a minute):

```bash
python -m unittest discover -s tests -v
```

- **`tests/test_qualification.py`:** expected results transcribed from published FAA/NASA reports. [tests/SOURCES.md](tests/SOURCES.md) lists the source of each test.
- **`tests/test_scenario.py`:** scenario generation, command line and tool version.
- **`tests/test_traceability.py`:** every test named by the tool operational requirements exists.

To keep a validation record of a run (IEC 61508-3 7.4.4.7):

```bash
python tests/run_validation.py
```

It writes `output/validation_record_<version>_<date>-<time>.md`; see [docs/IEC_61508_ADEQUACY.md](docs/IEC_61508_ADEQUACY.md).



## Disclaimer

Keep in mind that this is not a officially qualified tool (yet?). This could be costly and I'm simply helping building a tool  

## Progress / TODO

- Add a paragraph for the python example i provided.
- Buy the remaining IEC files.
- Produce a thourough analysis of DO178/330 adequacy.  
- More to come !
