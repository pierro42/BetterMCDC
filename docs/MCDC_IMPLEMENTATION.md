# MC/DC implementation description

This document describes how the tool computes MC/DC test sets: the definitions it implements, where each one is coded, its known limits, and how it is verified. It is written to support tool qualification (DO-178C / DO-330, or the IEC equivalents).

It does not qualify the tool by itself. The qualification level, the Tool Operational Requirements (TOR) and the acceptance of this evidence are decided in your plans with your certification authority.

## 1. Purpose and scope

**Input:** one decision, written as a Boolean expression of named Boolean inputs.

**Output:**
- **Truth table:** the full truth table.
- **Independence pairs:** for each condition, the pairs of test cases that show its independent effect on the output, in unique-cause or masking MC/DC form.
- **Test set:** a smallest set of test cases, with expected outputs, that contains one independence pair for every condition that has one.
- **Uncoverable conditions:** the conditions for which no pair exists, with the reason (redundant, or coupled in unique-cause form).

**Outside the scope:**
- The tool doesn't measure coverage of source or object code. It analyses the decision as written.
- Relational conditions are inputs, not comparisons: `speed < 40` must be given as a Boolean input such as `speed_lt_40`. Two conditions that are related in the real code (for example `x < 10` and `x < 20`) are treated as independent.
- There is no short-circuit evaluation. `and then` / `or else` and the "not evaluated" values of S2 are not modelled.

## 2. References

| Id | Document | Used for |
|---|---|---|
| S1 | NASA/TM-2001-210876, *A Practical Tutorial on Modified Condition/Decision Coverage*, Hayhurst, Veerhusen, Chilenski, Rierson, May 2001 | gate building blocks, worked examples, exercises (expected results) |
| S2 | DOT/FAA/AR-01/18, *An Investigation of Three Forms of the Modified Condition Decision Coverage (MCDC) Criterion*, Chilenski, April 2001 | formal definitions (§3.1.1, §3.1.2, §3.2.1), lower bounds (§5.1), airborne expressions (Appendix C) |
| CAST-6 | Certification Authorities Software Team, *Rationale for Accepting Masking MC/DC in Certification Projects*, 2001 | acceptance of the masking form |

Retrieval URLs and dates are in [tests/SOURCES.md](../tests/SOURCES.md).

## 3. Software configuration

- **Language:** Python 3.11 or later; verified with Python 3.12.4 on Windows 11. The Python version is part of the tool's configuration, because the expression parser is Python's `ast` module.
- **Dependencies:** standard library only (`ast`, `tokenize`, `itertools`, `math`, `time`, `tomllib`, `string`, `argparse`).
- **Behaviour:**
  - Deterministic: the same input gives the same output.
  - The one exception is the minimal-set search, which stops after 2 s. A slower machine can then return a different, still valid, set (see §8).

| Module | Responsibility | Review against |
|---|---|---|
| `mcdc/decision.py` | input language → conditions and expression tree | §4 |
| `mcdc/tree.py` | expression tree, evaluation, truth table, `is_unique_cause_pair`, `is_masking_pair` | §5, §6, §7 (definitions) |
| `mcdc/exact.py` | all pairs from the truth table, minimal set, lower bounds | §6, §7, §8 |
| `mcdc/pair_search.py` | pair search for large expressions | §9 |
| `mcdc/analysis.py` | engine choice | §10 |
| `mcdc/report.py` | text / CSV output | §11 |
| `main.py` | command line | — |

**The core definitions:** `is_unique_cause_pair` and `is_masking_pair` in `mcdc/tree.py`, about 15 lines. They are the direct transcription of S2's definitions:
- The pair-search engine checks every pair it reports against them.
- The qualification suite checks them against the pairs published in S1 and S2.

## 4. Decision model (`mcdc/decision.py`)

### 4.1 Input language

The text `Output = <expression>` is first translated into Python syntax, then parsed with `ast.parse`.

**Translation** is done on tokens from Python's `tokenize`, so that names containing a keyword, such as `route` or `cond_et`, are not touched:
- `et`, `ou`, `non` (any case) → `and`, `or`, `not`;
- `&&`, `||` → `and`, `or`;
- `!` → `(not …)` around its operand, so that it binds tighter than every operator, as in C.

**Whitelist:** only these node types are accepted, and anything else is rejected with a message:
- the Boolean operators `and`, `or`, `not`;
- one-operator comparisons `==` and `!=`;
- names;
- the constants `True` and `False`.

**Rejected explicitly:**
- chained comparisons (`a != b != c`);
- non-Boolean constants;
- an expression with no input;
- an output name that is also an input.

**Error positions:** syntax errors are reported at their column in the text as typed, mapped back through the translation.

### 4.2 Conditions

**Definition:** a condition is each occurrence of an input variable, in reading order. Following S2, a repeated variable gives several conditions, labelled `a#1`, `a#2`, …. Conditions of the same variable are *coupled*: they always take the same value.

**Columns:** the truth table has one column per variable, in order of first appearance. The output is evaluated from the condition values, each condition taking the value of its variable.

### 4.3 Expression tree

The parsed expression becomes a list of nodes `(kind, a, b)`, children before parents, with the output as the last node.

| Kind | Meaning |
|---|---|
| `cond` | leaf, condition number `a` |
| `const` | leaf, constant `True` / `False`; never changes, is not a condition |
| `not` | negation of child `a` |
| `and`, `or` | binary operator on children `a`, `b` |
| `eq`, `ne` | `==` (xnor) and `!=` (xor) on children `a`, `b` |

**Operator chains:** an n-ary `and` / `or` is split into a left-associated chain of binary operators (`a and b and c` = `(a and b) and c`), because S2's graph-coloring definition works on binary operators.

**Paths:** for each condition, its *path* is the list of nodes from its leaf up to the output. It is stored as a list (`path_nodes`) and as a bit mask over the nodes (`paths`).

**Evaluation** (`node_values`) computes every node with both operands always evaluated, as S1's gates and S2 Fig. 6 do.

## 5. Truth table (`mcdc/tree.py`, `truth_table`)

**Rows:** every combination of the input variables. Row *i* is the binary number formed by the inputs, with the first input as the most significant bit. That is also S2's numbering, e.g. `4:(TFF)`.

**`#` column:** the tool displays row *i* as `#` *i* + 1. Reduced tables keep these numbers, so every test case traces back to the full table.

## 6. Unique-cause MC/DC

**Definition (S2 §3.1.1):** a pair of test cases shows the independent effect of condition *k* when:
- the output differs between the two test cases;
- condition *k* differs;
- every other condition keeps the same value.

**Implementation:**
- **Direct check** (`is_unique_cause_pair`): computes the condition values of both test vectors. It accepts the pair if the only differing condition is *k* and the outputs differ.
- **All pairs** (`independence_pairs`, unique-cause branch):
  - each row is encoded as a bit mask of its condition values;
  - for every (output False row, output True row) pair, the XOR of the two masks must have exactly one bit set (`d != 0 and d & (d - 1) == 0`);
  - that bit is the condition shown.

**Coupled conditions (S2 §3.2.1):** changing a repeated variable changes all its conditions at once, so no pair can ever change one of them alone. Such conditions get no pair, and the tool reports `NONE - coupled with …, use --mcdc masking`. This is the result S2 §3.2.1 states.

## 7. Masking MC/DC (graph coloring)

**Definition (S2 §3.1.2):** S2 gives a "graph coloring" procedure on the expression tree. For two test cases, a node is "changed" if its value differs between them. The *influence set* is the set of conditions whose whole path up to the output is changed. A pair shows condition *k* in masking MC/DC when the influence set is exactly {*k*}. The output then differs too, since the output node is on every path.

Changes of the other conditions are allowed as long as they are blocked by an operator whose value doesn't change: for example an `and` with another input at False. This is the "masking". The same analysis appears in S1 §3.2 as the gate-level analysis of the worked examples.

**Implementation:**
- **`node_mask(decision, inputs)`:** the values of all nodes for a test vector, as a bit mask (bit *n* = value of node *n*).
- **`influence_set(decision, mask_x, mask_y)`:** with `changed = mask_x ^ mask_y`, it returns the conditions *k* where `paths[k] & ~changed == 0`, i.e. every node of the path changed.
- **`is_masking_pair(decision, x, y, k)`:** accepts the pair when `influence_set(...) == [k]`.
- **`independence_pairs`** (masking branch): computes `node_mask` once per row. Then, for every (output False row, output True row) pair whose influence set has exactly one condition, it records that pair for that condition.

**Worked example (S2 Fig. 6):** `A or (B and C)`, test cases x = FTF and y = TFT.

| Node | x | y | Changed |
|---|---|---|---|
| A | F | T | yes |
| B | T | F | yes |
| C | F | T | yes |
| B and C | F | F | **no** |
| output (or) | F | T | yes |

- Path of A: A → output, all changed, so A is in the influence set.
- Paths of B and C: they go through `B and C`, which is unchanged, so B and C are not in it.
- The influence set is {A}, so (FTF, TFT) shows A. This is S2's result, checked by `S2Definitions.test_figure_6`.

**Repeated variables:** each occurrence is its own leaf with its own path, so a coupled condition can be shown when the path of its twin is blocked. S2 Fig. 10, `(A and B) or (A and C) or (B and C)`: the pair (TFF, TTF) shows the first B. This is checked by `S2Definitions.test_figure_10_coupled`.

**Constants** never change, so a path through a constant's operator depends only on the other operand, as in the definition.

## 8. Minimal test set (`mcdc/exact.py`)

**Problem:** choose one pair per coverable condition so that the number of distinct test cases is minimal.

**Search** (`minimal_mcdc_set`), branch and bound:
1. **Initial solution:** a greedy solution gives the first upper bound.
2. **Free conditions:** conditions already covered by the selected test cases cost nothing and are assigned at once.
3. **Branching:** on the open condition with the fewest options. Pairs that add one new test case are tried first, then pairs that add two (only if that can still beat the best set).
4. **Pruning:**
   - a branch stops as soon as it can't beat the best set found;
   - in unique-cause mode, an extra bound is used. Unique-cause pairs are edges of the hypercube in distinct dimensions, so the chosen pairs form a forest: each new condition adds a test case or joins two trees.
5. **Stop:** when the best set reaches the lower bound below, or after 2 s.

**Lower bounds (S2 §5.1), `lower_bound`:**

| Form | Bound | Source |
|---|---|---|
| unique-cause | N + 1 tests for N coverable conditions | S2 Theorem 1 |
| masking | ⌈2√M⌉ tests for M coverable conditions, computed exactly with `math.isqrt` | S2 Theorem 4 |

Theorem 4 holds with M = the number of conditions that have at least one pair. Each masking pair joins one False and one True test case and serves a single condition. With *a* False and *b* True test cases there are at most *a·b* pairs, so *a·b ≥ M* and *a + b ≥ 2√M*.

**Result:** the set, the chosen pair for each condition, and a flag. The flag means:
- **"proven minimal":** the search finished, or the set reached the lower bound.
- **"not proven minimal":** the 2 s limit was reached first. The set is still valid (one valid pair per coverable condition), and the lower bound is printed.

## 9. Pair-search engine for large expressions (`mcdc/pair_search.py`)

**Why:** the exact engine needs the 2^n-row truth table and compares up to 4^n row pairs, which is out of reach above about 12 inputs. Above `--max-exact` inputs (default 10), the pair-search engine is used instead. Its goal is completeness, not a minimal set.

**Search for one pair** (`_search_pair`):
- **Depth-first:** it searches two input vectors x and y at once, assigning one variable per level. The condition's own variable comes first, with x and y different.
- **Values per level:**
  - other variables, masking: one of 4 combinations in (x, y);
  - other variables, unique-cause: the same value in x and y;
  - unique-cause and the condition's variable is repeated: the answer is "impossible" at once (S2 §3.2.1).
- **3-valued evaluation:** at each level, nodes are evaluated with True / False / unknown (`_partial_values`). An `and` with a known False input is False, an `or` with a known True input is True.
- **Pruning:** a branch is abandoned as soon as it can no longer give a valid pair:
  - a node on the condition's path is known and unchanged;
  - in masking mode, another condition's path is known and fully changed.
- **Validity:** when every variable is assigned, every node is known, so the pruning rules imply the definition. The path of *k* fully changed and no other path fully changed is exactly influence set = {*k*}.
- **Step budget:** each search has one (20 000 steps, or 400 when reusing a test).

**Result per condition:**

| Status | Meaning |
|---|---|
| covered | a pair was found |
| impossible | the whole search space was explored without a valid pair: proof that the condition can't be shown |
| unknown | the step budget was exceeded; reported as `UNKNOWN` with a `WARNING` line, never dropped silently |

**Building the set** (`pair_search_set`):
1. **Reuse:** for each condition, it first tries to reuse a test case already selected, searching only its partner.
2. **Free search:** if that fails, it searches freely.
3. **Self-check:** before a pair is accepted, it is checked with `is_masking_pair` / `is_unique_cause_pair`. A failure stops the tool with `internal error`, so an invalid pair can't be output.

**Limitation:** the set is valid but not minimised. For example, a 76-condition expression of S2 Appendix C gives 78 test cases in masking mode, against a lower bound of 18.

## 10. Engine choice (`mcdc/analysis.py`)

`analyse_mcdc(decision, mode, max_exact=10, time_limit=2.0, budget=20000)`:
- **Up to `max_exact` inputs:** exact engine (§6–§8). Every condition is "covered" or "impossible", and each condition's number of possible pairs is known.
- **Above:** pair-search engine (§9).

The summary names the engine used.

## 11. Output (`mcdc/report.py`)

- **Table:**
  - the `#` column (truth-table row), one column per input variable, then the output column;
  - values are `1` / `0`;
  - `--csv` prints the same table as CSV.
- **Summary**, per condition:
  - the chosen pair (`#i / #j`), the output change, and the number of possible pairs (exact engine);
  - `masked:` the other conditions whose variable also differs in that pair;
  - or `NONE` with the reason, or `UNKNOWN`.
- **`Minimum` line:** the set size, and "proven minimal" or the lower bound.

## 12. Verification

The test suite is in `tests/` and uses `unittest` from the standard library. Run it from the project folder:

```bash
python -m unittest discover -s tests -v
```

**Expected results:** in `tests/test_qualification.py`, every expected result is transcribed from S1 or S2, with document, section, table or figure and page in each test's docstring. [tests/SOURCES.md](../tests/SOURCES.md) is the traceability table. The categories are:

| Category | Tests | Checks |
|---|---|---|
| Gate building blocks | `S1BuildingBlocks.*` | minimal sets of and / or / xor / not gates (S1 §3.1) |
| Worked examples | `S1WorkedExamples.*` | S1 examples 1, 2, 2A, 3 and exercises 3.3a–d: which test sets give MC/DC, which conditions are missing |
| Definitions | `S2Definitions.*` | the complete pair lists of S2 §3.1.1 (3 unique-cause, 9 masking), Figs. 6, 8, 9, 10, coupled conditions (§3.2.1) |
| Lower bounds | `S2MinimumNumberOfTests.*` | no minimal set below S2 Theorems 1 and 4 |
| Truth tables | `S2AppendixC.*` | 702 real airborne expressions: truth table = published response profile |
| Input language | `InputSyntax.*` | `&&` / `\|\|` / `!` give the same results as `and` / `or` / `not`; `!` precedence |
| Pair-search engine | `PairSearchEngine.*` | same coverable / impossible conclusions as the exact engine on every published case; published pairs pass the direct checks |
| Engine cross-check | `AppendixCCrossCheck.*` | **not a published oracle**: both engines agree up to 8 inputs; above (up to 76 conditions), every condition ends covered or impossible with valid pairs |

The last run was on 2026-11-16, with Python 3.12.4 on Windows 11: 41 tests (27 qualification, 14 scenario generation), all passed, in about 23 s.

**Inconsistencies in the source:** three Appendix C entries contradict themselves in S2 and are excluded (C0604, C0793, C0839). The details are in [tests/SOURCES.md](../tests/SOURCES.md).

## 13. Assumptions and limitations (to state in the TOR)

1. **Independent inputs:** conditions are independent Boolean inputs. Relational conditions, and the weak coupling of S2 Appendix B, are not modelled.
2. **No short-circuit evaluation:** `&&` and `||` are Boolean and/or; `and then`, `or else` and the not-evaluated values of S2 Fig. 5 are not supported.
3. **Unsupported forms and constructs:** the unique-cause + masking form of S2 §3.2.2 is not implemented, and neither are comparators, bit-wise operations, latches or loops (S1 §3.1.5–3.1.7, §3.7, Exercise 3.5).
4. **No exact minimum published for large expressions:** no source gives one, only S2's lower bounds. "Proven minimal" means the exhaustive search finished or reached that bound.
5. **2 s search limit:** it is machine-dependent. When it stops the search, the set is valid but "not proven minimal".
6. **Pair-search sets are not minimised:** above `--max-exact` inputs (§9), and a condition can be `UNKNOWN` if its search exceeds the budget.
7. **Python version:** it is part of the configuration (§3). Rerun the suite after any change of Python version or of the tool.

## 14. Proposed tool operational requirements

A starting point for your TOR, with the code and tests that cover each requirement. Adapt the wording and IDs to your plans.

| Id | Requirement | Code | Verified by |
|---|---|---|---|
| TOR-01 | The tool shall accept a decision written with and/or/not (also et/ou/non and &&/\|\|/!), ==, !=, True, False and parentheses, and reject any other syntax with a message. | `decision.py` | `InputSyntax.*`, all cases parsed in `test_qualification.py` |
| TOR-02 | The tool shall treat each occurrence of a variable as a separate condition. | `decision.py`, `tree.py` | `S2Definitions.test_figure_10_coupled`, `test_section_3_2_1_coupled_unique_cause`, `S2AppendixC.test_condition_counts` |
| TOR-03 | The tool shall compute the truth table of the decision. | `tree.truth_table` | `S2AppendixC.test_response_profiles`, `S1BuildingBlocks.*` |
| TOR-04 | The tool shall identify unique-cause independence pairs as defined in S2 §3.1.1. | `tree.is_unique_cause_pair`, `exact.independence_pairs` | `S2Definitions.test_section_3_1_1_unique_cause_pairs`, `test_section_3_2_1_coupled_unique_cause`, `S1WorkedExamples.test_example_2_and_2a` |
| TOR-05 | The tool shall identify masking independence pairs as defined by S2 §3.1.2 (graph coloring). | `tree.is_masking_pair`, `exact.independence_pairs` | `S2Definitions.test_section_3_1_1_masking_pairs`, `test_figure_6`, `test_figures_8_and_9`, `test_figure_10_coupled`, `S1WorkedExamples.*` |
| TOR-06 | The tool shall output a test set that contains an independence pair for every condition that has one, and report every other condition with the reason. | `exact.minimal_mcdc_set`, `pair_search.pair_search_set`, `report.py` | `S1BuildingBlocks.*`, `S1WorkedExamples.*`, `PairSearchEngine.*`, `AppendixCCrossCheck.*` |
| TOR-07 | The tool shall report the test set as proven minimal only when no smaller set exists. | `exact.minimal_mcdc_set`, `exact.lower_bound` | `S1BuildingBlocks.test_and_gate`, `test_or_gate`, `test_xor_gate`, `S2MinimumNumberOfTests.test_theorems_1_and_4` |
| TOR-08 | Above the exact-engine limit, the tool shall report each condition as covered, impossible or unknown, and only output pairs that satisfy TOR-04 / TOR-05. | `pair_search.py` | `PairSearchEngine.*`, `AppendixCCrossCheck.test_large_expressions` |
| TOR-09 | Each test case shall show its truth-table row number, its input values and its expected output. | `report.print_table` | `test_scenario.CommandLine.test_csv_output_stays_clean`; review of the output |
