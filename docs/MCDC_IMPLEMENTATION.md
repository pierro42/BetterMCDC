# MC/DC implementation description

This document describes how the tool computes MC/DC test sets: the definitions it implements, where each one is coded, its known limits, and how it is verified. It is written to support tool qualification (DO-178C / DO-330, or the IEC equivalents).

It does not qualify the tool by itself. The qualification level, the Tool Operational Requirements (TOR) and the acceptance of this evidence are decided in your plans with your certification authority.

For IEC 61508, [IEC_61508_ADEQUACY.md](IEC_61508_ADEQUACY.md) maps the tool and this evidence to the support-tool requirements of IEC 61508-3:2010. For DO-178C / DO-330, [DO178C_DO330_ADEQUACY.md](DO178C_DO330_ADEQUACY.md) does the same from the public FAA documents (preliminary).

## 1. Purpose and scope

**Input:** one decision, written as a Boolean expression of named Boolean inputs.

**Output:**
- **Truth table:** the full truth table.
- **Independence pairs:** for each condition, the pairs of test cases that show its independent effect on the output, in one of the three forms of S2: unique-cause, unique-cause + masking, or masking MC/DC.
- **Test set:** a smallest set of test cases, with expected outputs, that contains one independence pair for every condition that has one.
- **Uncoverable conditions:** the conditions for which no pair exists, with the reason (redundant, or coupled in the unique-cause forms).

**Outside the scope:**
- The tool doesn't measure coverage of source or object code. It analyses the decision as written.
- Relational conditions are inputs, not comparisons: `speed < 40` must be given as a Boolean input such as `speed_lt_40`. Two conditions that are related in the real code (for example `x < 10` and `x < 20`) are treated as independent.
- Short-circuit evaluation is modelled for `and then` / `or else`, and for every and / or with `--short-circuit` (§9). Choosing the evaluation that matches the code under test is the user's responsibility.

## 2. References

| Id | Document | Used for |
|---|---|---|
| S1 | NASA/TM-2001-210876, *A Practical Tutorial on Modified Condition/Decision Coverage*, Hayhurst, Veerhusen, Chilenski, Rierson, May 2001 | gate building blocks, worked examples, exercises, short-circuit logic (§3.6) (expected results) |
| S2 | DOT/FAA/AR-01/18, *An Investigation of Three Forms of the Modified Condition Decision Coverage (MCDC) Criterion*, Chilenski, April 2001 | definitions (glossary, §3.1.1, §3.1.2 with Figures 5 and 7, §3.2.1, §3.2.2, transition types §5.1), lower bounds (§5.1), minimal test sets of the airborne expressions (§6.1.1, Figures 28-30), independence tables (§7.1), airborne expressions (Appendix C) |
| S3 | DOT/FAA/AR-06/54, *Software Verification Tools Assessment Study*, June 2007 | MC/DC forms as seen by the FAA (Appendix A), short-circuit operators (§4.2.5, §4.3.2), one minimum test count (§4.3.2) |
| CAST-6 | Certification Authorities Software Team, *Rationale for Accepting Masking MC/DC in Certification Projects*, 2001 | acceptance of the masking form |

Retrieval URLs and dates are in [tests/SOURCES.md](../tests/SOURCES.md).

## 3. Software configuration

- **Language:** Python 3.11 or later; verified with Python 3.12.4 on Windows 11. The Python version is part of the tool's configuration, because the expression parser is Python's `ast` module.
- **Dependencies:** standard library only (`ast`, `tokenize`, `itertools`, `math`, `time`, `tomllib`, `string`, `argparse`).
- **Behaviour:**
  - Deterministic: the same input gives the same output.
  - The one exception is the minimal-set search, which stops after 2 s. A slower machine can then return a different, still valid, set (see §10).

| Module | Responsibility | Review against |
|---|---|---|
| `mcdc/decision.py` | input language → conditions and expression tree | §4 |
| `mcdc/tree.py` | expression tree, evaluation, executed nodes, `tree_xor`, `independence` (the three definitions), `canonical`, truth table | §5–§9 (definitions) |
| `mcdc/exact.py` | all pairs from the truth table, minimal set, lower bounds | §6–§10 |
| `mcdc/pair_search.py` | pair search for large expressions | §11 |
| `mcdc/analysis.py` | engine choice | §12 |
| `mcdc/report.py` | text / CSV output | §13 |
| `mcdc/scenario.py` | test scenario file from a template | [SCENARIO_GENERATION.md](SCENARIO_GENERATION.md) |
| `mcdc/version.py` | tool version | — |
| `main.py` | command line | — |

**The core definitions:** `tree_xor` and `independence` in `mcdc/tree.py`, about 25 lines; `is_masking_pair`, `is_unique_cause_pair` and `is_unique_cause_masking_pair` apply them to two test vectors (`PAIR_CHECK` maps each form to its function). They are the direct transcription of S2's definitions:
- The pair-search engine checks every pair it reports against them.
- The qualification suite checks them against the pairs published in S1 and S2.

## 4. Decision model (`mcdc/decision.py`)

### 4.1 Input language

The text `Output = <expression>` is first translated into Python syntax, then parsed with `ast.parse`.

**Translation** is done on tokens from Python's `tokenize`, so that names containing a keyword, such as `route` or `cond_et`, are not touched:
- `et`, `ou`, `non` (any case) → `and`, `or`, `not`;
- `&&`, `||` → `and`, `or`;
- `!` → `(not …)` around its operand, so that it binds tighter than every operator, as in C;
- `and then`, `or else` → `and`, `or`, recorded as short-circuit forms (§9). The k-th `and` / `or` of the Python text is the k-th operator written, which tells the tree builder which operators are short-circuit forms.

**Whitelist:** only these node types are accepted, and anything else is rejected with a message:
- the Boolean operators `and`, `or`, `not` (and the short-circuit forms `and then`, `or else`);
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
| `andthen`, `orelse` | short-circuit forms: same result, right child `b` evaluated only when needed (§9) |
| `eq`, `ne` | `==` (xnor) and `!=` (xor) on children `a`, `b` |

**Operator chains:** an n-ary `and` / `or` is split into a left-associated chain of binary operators (`a and b and c` = `(a and b) and c`), because S2's graph-coloring definition works on binary operators.

**Paths:** for each condition, its *path* is the list of nodes from its leaf up to the output. It is stored as a list (`path_nodes`) and as a bit mask over the nodes (`paths`).

**Evaluation:** `node_values` computes the value of every node. `node_executed` marks which nodes are executed. Without short-circuit forms every node is executed, as in S1's gates and S2 Fig. 6; with them, see §9.

## 5. Truth table (`mcdc/tree.py`, `truth_table`)

**Rows:** every combination of the input variables. Row *i* is the binary number formed by the inputs, with the first input as the most significant bit. That is also S2's numbering, e.g. `4:(TFF)`.

**`#` column:** the tool displays row *i* as `#` *i* + 1. Reduced tables keep these numbers, so every test case traces back to the full table.

**With short-circuit forms:** only the rows whose not-evaluated inputs are False are distinct tests (§9). The table lists those rows, with `X` for the inputs not evaluated.

## 6. Unique-cause MC/DC

**Definition (S2 §3.1.1):** a pair of test cases shows the independent effect of condition *k* when:
- the output differs between the two test cases;
- condition *k* differs;
- every other condition keeps the same value.

S2 §3.1.2 gives the same definition on the influence tree: the influence set is {*k*} and *k* "is the only condition which has a True in the influence tree".

**Implementation:** the influence-tree form, which also covers short-circuit forms (§9):
- **Direct check** (`is_unique_cause_pair`): evaluates both test vectors and builds the influence tree (§7). It accepts the pair if the influence set is [*k*] and *k* is the only changed condition.
- **All pairs** (`independence_pairs`): the same test for every (output False row, output True row) pair.

Without short-circuit forms, this is exactly the §3.1.1 statement above. It is checked against a direct implementation of that statement on the suite and on Appendix C (`ShortCircuit.test_same_definitions_without_short_circuit`).

**Coupled conditions (S2 §3.2.1):** changing a repeated variable changes all its conditions at once, so no pair can ever change one of them alone. Such conditions get no pair, and the tool reports `NONE - coupled with …, use --mcdc unique-cause+masking or masking`. This is the result S2 §3.2.1 states.

## 7. Masking MC/DC (graph coloring)

**Definition (S2 §3.1.2):** S2 gives a "graph coloring" procedure on the expression tree. For two test cases, a node is "changed" if its value differs between them. The *influence set* is the set of conditions whose whole path up to the output is changed. A pair shows condition *k* in masking MC/DC when the influence set is exactly {*k*}. The output then differs too, since the output node is on every path.

Changes of the other conditions are allowed as long as they are blocked by an operator whose value doesn't change: for example an `and` with another input at False. This is the "masking". The same analysis appears in S1 §3.2 as the gate-level analysis of the worked examples.

**Implementation:**
- **`node_masks(decision, inputs)`:** the values of all nodes, and which nodes are executed, as two bit masks (bit *n* = node *n*).
- **`tree_xor(masks_x, masks_y)`:** the influence tree, `changed = (vx ^ vy) & ex & ey` (§9; without short-circuit forms every node is executed and this is `vx ^ vy`).
- **`influence_set(decision, changed)`:** the conditions *k* where `paths[k] & ~changed == 0`, i.e. every node of the path changed.
- **`is_masking_pair(decision, x, y, k)`:** accepts the pair when the influence set is [*k*].
- **`independence_pairs`:** computes `node_masks` once per row. Then, for every (output False row, output True row) pair whose influence set has exactly one condition, it records that pair for that condition, if the form's extra rule holds (§6, §8).

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

## 8. Unique-cause + masking MC/DC

**Definition (S2 §3.2.2):** unique-cause + masking requires a unique cause for every uncoupled condition. For a strongly coupled condition, masking is allowed for that condition only, all other conditions remaining fixed. It is the form suggested by S2's reference 4, which S2 says has been used in airplane certifications.

S2 gives no formula for this form. It states it on the n-cube of the inputs instead:
- **§5.1, p.28-29:** an *edge* is a transition between two input combinations that differ in just one value. It is the only transition the unique-cause forms allow. The other transitions are face or internal *diagonals*, allowed by masking.
- **§7.1, p.55-57:** a unique-cause + masking coverage set exists when every condition has an *edge* independence pair.

The tool implements exactly that: a pair shows condition *k* in unique-cause + masking MC/DC when
1. the two test cases differ in exactly one input, the input of *k* (an edge), and
2. it is a masking pair for *k* (S2 §3.1.2, §7 above): the influence set is exactly {*k*}.

**Why this is §3.2.2:**
- **Uncoupled *k*:** only *k* changes, so the pair is exactly a unique-cause pair (the output changes because the output node is on *k*'s path). "A unique cause for all uncoupled conditions".
- **Coupled *k*:** the other occurrences of *k*'s input change with it and must be masked, since the influence set is {*k*}. Every other input keeps its value. "Masking allowed for that condition only, all other conditions remaining fixed".

**Implementation:**
- **Direct check** (`is_unique_cause_masking_pair`): the influence set must be [*k*], and every changed condition must be an occurrence of *k*'s input. Without short-circuit forms this is exactly "only the input of *k* changes", the edge rule (checked by `ShortCircuit.test_same_definitions_without_short_circuit`); with them, see §9.
- **All pairs** (`independence_pairs`): the same test for every (output False row, output True row) pair.
- **Pair search** (§11): without short-circuit forms, the other inputs keep their value in both tests (as in unique-cause), and other conditions with a fully changed path are rejected (as in masking).

**Worked example (S2 Table 33):** `(A and B) or (A and C)`. A (1st occurrence) has the masking pairs (2, 6) and (3, 6), and the table marks (2, 6) as an Edge:
- **(2, 6):** 2:(FTF) and 6:(TTF) differ in A only. `A and B` goes F→T; `A and C` stays F because C = F, so A (2nd occurrence) is masked. This is a unique-cause + masking pair.
- **(3, 6):** 3:(FTT) and 6:(TTF) differ in A and C. It is a masking pair (a face diagonal), but not a unique-cause + masking pair.

**Verified by:** `S2UniqueCauseMasking.*`. Tables 32-35 and Figures 40-41 of S2 §7.1 give, for five expressions, every independence pair with its transition type. The tool's unique-cause + masking pairs are exactly the Edge pairs. One printed pair of Table 35 contradicts the report's own definition and is documented in [tests/SOURCES.md](../tests/SOURCES.md).

## 9. Short-circuit forms (and then / or else)

**Definition (S2 glossary, "Short-Circuit Form Boolean Operator"):** the left-hand side is evaluated first, the right-hand side only when needed. For and-then, a False left-hand side returns False and the right-hand side is not evaluated; for or-else, a True left-hand side returns True without evaluating the right-hand side. S1 §3.6 says the same of Ada's `and then` / `or else` and C's `&&` / `||`.

**Input (§4.1):**
- `and then` and `or else` are always short-circuit forms;
- with `--short-circuit` (`parse_decision(text, short_circuit=True)`), every and / or is one, whatever its spelling (`and`, `et`, `&&`, …), as in C;
- without it, `and`, `or`, `&&`, `||` stay Boolean operators with both operands evaluated.

They become the tree nodes `andthen` / `orelse` (§4.3), with the same Boolean result as `and` / `or`.

**Executed nodes (S2 §3.1.2, rule b; `tree.node_executed`):** the output is executed. The operands of an executed operator are executed, except the right-hand side of an and-then whose left-hand side is False, or of an or-else whose left-hand side is True, which is "changed to Not-Executed" with everything below it.

**Influence tree (S2 Figure 5; `tree.tree_xor`):** a node is True in the influence tree when it is executed in both tests and its value differs. tree_xor gives F⊕F = F, F⊕T = T, T⊕F = T, T⊕T = F, and False for anything with Not-Executed. As bit masks: `changed = (vx ^ vy) & ex & ey`. Without short-circuit forms every node is executed and this is the plain XOR of §7.

**The three definitions, on the influence tree (`tree.independence`):**

| Form | Pair for condition *k* | Source |
|---|---|---|
| masking | the influence set (conditions with a path of all Trues to the root) is exactly {*k*} | S2 §3.1.2 |
| unique-cause | in addition, *k* is the only condition which has a True in the influence tree | S2 §3.1.2: "If additionally ci is the only condition which has a True in the influence tree (i.e., only ci changed between the two tests)" |
| unique-cause + masking | in addition to masking, every condition with a True in the influence tree is an occurrence of *k*'s input | S2 §3.2.2 (see below) |

- **Without short-circuit forms** these are exactly §6, §7 and §8: every leaf is executed, so "True in the influence tree" means "changed value". `ShortCircuit.test_same_definitions_without_short_circuit` checks this on the suite and on Appendix C.
- **Unique-cause with repeated conditions:** with short-circuit forms, a repeated condition can have a unique-cause pair when its other occurrence isn't executed in one of the tests. S2 counted exactly that (§6.1.1, Figure 28: "the short-circuit forms masked the cases when the repeated conditions both change value at the same time"). The tool finds the same two occurrences, expression C0827, needing 7 tests.
- **Unique-cause + masking** is given in words only (S2 §3.2.2), and S2's n-cube "edge" statement (§5.1, §7.1) is only illustrated without short-circuit forms. The tool reads "all other conditions remaining fixed" on the influence tree, like S2's unique-cause sentence: no condition of another input changes. Without short-circuit forms this is the edge rule. With them, Figure 29, which includes the 69 short-circuit expressions of Appendix C, is reproduced exactly (§14).

**Test cases:** an input that a test doesn't evaluate can take any value without changing any executed node, so tests that differ only there are the same test. The tool keeps one of them, with those inputs False (`tree.canonical`; `exact.test_rows`):
- **numbering:** S2 numbers test cases "interpreting a nonexecution due to short-circuit operators as 0" (glossary, Condition Combination);
- **display:** S1 §3.6 writes these inputs X, "don't care", and the tool prints `X` in its tables;
- **scenario files:** they get the `NOT_EVALUATED` text of the template, by default the FALSE text.

**Worked example (S2 Figure 7):** `A or else (B and C)`, tests x = FTF and y = TFT.

| Node | x | y | Influence tree |
|---|---|---|---|
| A | F | T | T |
| B | T | X | F |
| C | F | X | F |
| B and C | F | X | F |
| output (or else) | F | T | T |

In y, A is True, so `B and C` is not executed (X). Only A has a path of all Trues: the influence set is {A}. "Recall that for a condition to have influence, it must toggle between True and False in two executions." Checked by `ShortCircuit.test_figure_7`.

**Worked example (S1 Table 32):** `A and then B and then C and then D`. The tool's minimal set is TTTT, FXXX, TFXX, TTFX, TTTF, exactly Table 32, X included. Checked by `ShortCircuit.test_tables_32_and_33` (and Table 33 for or else).

**Lower bound:** with short-circuit forms only ⌈2√M⌉ is used, for every form, and the unique-cause forest pruning is off (§10). A pair may now change an input that isn't evaluated in one of the tests, so pairs are no longer n-cube edges, and the N + 1 and V + 1 arguments don't apply. "Proven minimal" then relies on the search finishing; for the Appendix C expressions it always does, and the minimal sizes match Figures 28-30.

**Pair search (§11):** the search tracks, for every node, whether it is executed: True, False or unknown. A branch is abandoned only when the definition is certainly violated:
- **k's path:** a node on k's path is certainly unchanged, i.e. not executed in one test, or executed in both with the same value;
- **masking and unique-cause + masking:** another condition's path is certainly fully changed;
- **unique-cause:** another condition is certainly changed;
- **unique-cause + masking:** a condition of another input is certainly changed.

Other details:
- **Inputs:** with short-circuit forms, inputs other than k's may differ in the unique-cause forms too, since they may be not executed.
- **Complete candidates:** each one is accepted only if the exact definition (`PAIR_CHECK`) holds.
- **Found pairs:** they are written as canonical tests, then self-checked again.

**Verified by:**
- **Unit cases:** `ShortCircuit.*`, which covers the glossary, Figures 5 and 7, S1 Example 7, Tables 32 and 33, and the `--short-circuit` option.
- **Truth tables:** `S2AppendixC.test_response_profiles`, including 55 short-circuit expressions with their not-executed rows.
- **Minimal sets:** `S2Figures28To30.*`.

## 10. Minimal test set (`mcdc/exact.py`)

**Problem:** choose one pair per coverable condition so that the number of distinct test cases is minimal.

**Search** (`minimal_mcdc_set`), branch and bound:
1. **Initial solution:** a greedy solution gives the first upper bound.
2. **Free conditions:** conditions already covered by the selected test cases cost nothing and are assigned at once.
3. **Branching:** on the open condition with the fewest options. Pairs that add one new test case are tried first, then pairs that add two (only if that can still beat the best set).
4. **Pruning:**
   - a branch stops as soon as it can't beat the best set found;
   - in unique-cause mode, an extra bound is used. Unique-cause pairs are edges of the hypercube in distinct dimensions, so the chosen pairs form a forest: each new condition adds a test case or joins two trees. It is **not** used for unique-cause + masking: the edges of coupled conditions share a direction and can form a cycle (see below).
5. **Stop:** when the best set reaches the lower bound below, or after 2 s.

With short-circuit forms the forest pruning is off, and only the ⌈2√M⌉ bound is used (§9).

**Lower bounds (S2 §5.1), `lower_bound`:**

| Form | Bound | Source |
|---|---|---|
| unique-cause | N + 1 tests for N coverable conditions | S2 Theorem 1 |
| masking | ⌈2√M⌉ tests for M coverable conditions, computed exactly with `math.isqrt` | S2 Theorem 4 |
| unique-cause + masking | max(V + 1, ⌈2√M⌉), V = number of distinct inputs among the M coverable conditions | proved below; equals Theorem 1 (N + 1) when no input is repeated |

Theorem 4 holds with M = the number of conditions that have at least one pair. Each masking pair joins one False and one True test case and serves a single condition. With *a* False and *b* True test cases there are at most *a·b* pairs, so *a·b ≥ M* and *a + b ≥ 2√M*.

**Unique-cause + masking bound, and why S2 Theorem 2 is not used.** S2 Theorem 2 (p.31) states that this form needs at least M + 1 tests for M occurrences. The report's own definition contradicts it:
- `(B and not D) or (not B and D)` has M = 4 occurrences but only 4 possible tests, and each occurrence has an edge pair among them;
- the S2 Fig. 10 expression `(A and B) or (A and C) or (B and C)` (M = 6) has a 6-test set.

Both are detailed in [tests/SOURCES.md](../tests/SOURCES.md). Using M + 1 would make the tool stop the search too early and claim a set is minimal when it may not be. The tool uses two bounds that are proved:
- **⌈2√M⌉:** every unique-cause + masking pair is a masking pair, so the Theorem 4 argument above applies.
- **V + 1:** pick one chosen pair per input. These V pairs are n-cube edges in V different directions. A cycle in the n-cube crosses each direction an even number of times, so they can't form one: they are a forest with V edges, which has at least V + 1 test cases.

**Result:** the set, the chosen pair for each condition, and a flag. The flag means:
- **"proven minimal":** the search finished, or the set reached the lower bound.
- **"not proven minimal":** the 2 s limit was reached first. The set is still valid (one valid pair per coverable condition), and the lower bound is printed.

## 11. Pair-search engine for large expressions (`mcdc/pair_search.py`)

**Why:** the exact engine needs the 2^n-row truth table and compares up to 4^n row pairs, which is out of reach above about 12 inputs. Above `--max-exact` inputs (default 10), the pair-search engine is used instead. Its goal is completeness, not a minimal set.

**Search for one pair** (`_search_pair`):
- **Depth-first:** it searches two input vectors x and y at once, assigning one variable per level. The condition's own variable comes first, with x and y different.
- **Values per level:**
  - other variables, masking: one of 4 combinations in (x, y);
  - other variables, unique-cause and unique-cause + masking: the same value in x and y (without short-circuit forms);
  - unique-cause and the condition's variable is repeated, without short-circuit forms: the answer is "impossible" at once (S2 §3.2.1).
- **Short-circuit forms:** executed nodes are tracked too, and the pruning rules of §9 apply.
- **3-valued evaluation:** at each level, nodes are evaluated with True / False / unknown (`_partial_values`). An `and` with a known False input is False, an `or` with a known True input is True.
- **Pruning:** a branch is abandoned as soon as it can no longer give a valid pair:
  - a node on the condition's path is known and unchanged;
  - in masking and unique-cause + masking modes, another condition's path is known and fully changed.
- **Validity:** when every variable is assigned, the pair is accepted only if the exact definition of its form (`PAIR_CHECK`) holds. The pruning only abandons branches that certainly can't give a valid pair, so "impossible" is a proof.
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
3. **Self-check:** before a pair is accepted, its tests are written in canonical form (§9) and checked with the definition of its form (`PAIR_CHECK`: `is_masking_pair`, `is_unique_cause_masking_pair` or `is_unique_cause_pair`). A failure stops the tool with `internal error`, so an invalid pair can't be output.

**Limitation:** the set is valid but not minimised. For example, a 76-condition expression of S2 Appendix C gives 78 test cases in masking mode, against a lower bound of 18.

## 12. Engine choice (`mcdc/analysis.py`)

`analyse_mcdc(decision, mode, max_exact=10, time_limit=2.0, budget=20000)`:
- **Up to `max_exact` inputs:** exact engine (§6–§10). Every condition is "covered" or "impossible", and each condition's number of possible pairs is known.
- **Above:** pair-search engine (§11).

The summary names the engine used.

## 13. Output (`mcdc/report.py`)

- **Table:**
  - the `#` column (truth-table row), one column per input variable, then the output column;
  - values are `1` / `0`, and `X` for an input that the test doesn't evaluate (short-circuit forms, §9);
  - `--csv` prints the same table as CSV.
- **Summary**, per condition:
  - the chosen pair (`#i / #j`), the output change, and the number of possible pairs (exact engine);
  - `masked:` the other conditions that also changed in that pair (executed in both tests, different value);
  - or `NONE` with the reason, or `UNKNOWN`.
- **`Minimum` line:** the set size, and "proven minimal" or the lower bound.

## 14. Verification

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
| Unique-cause + masking | `S2UniqueCauseMasking.*` | S2 §7.1 Tables 32-35: every masking pair, and the Edge pairs = unique-cause + masking pairs; coverage sets per form; Figs. 40-41; the §3.2.2 definition on every expression |
| Lower bounds | `S2MinimumNumberOfTests.*` | no set below S2 Theorems 1 and 4; Theorem 2 not used; **derived**: true minimum by trying every subset (≤ 4 inputs) = the tool's minimum |
| Truth tables | `S2AppendixC.*` | 878 real airborne expressions, 55 with short-circuit forms: truth table = published response profile, not-executed rows included |
| Minimal test sets | `S2Figures28To30.*` | S2 Figures 28-30: for the three forms and 2 to 6 conditions, the occurrences of the 1112 airborne expressions per minimal set size, all 47 plotted values; S2's statements on them |
| Short-circuit forms | `ShortCircuit.*` | S2 glossary, Figures 5 and 7; S1 Example 7, Tables 32-33; S3 §4.3.2 minimum of 4 tests; the definitions equal §3.1.1 and the edge rule without short-circuit forms; `--short-circuit` |
| Input language | `InputSyntax.*` | `&&` / `\|\|` / `!` give the same results as `and` / `or` / `not`; `!` precedence |
| Pair-search engine | `PairSearchEngine.*` | same coverable / impossible conclusions as the exact engine on every published case, in the three forms; published pairs pass the direct checks |
| Engine cross-check | `AppendixCCrossCheck.*` | **not a published oracle**: both engines agree up to 8 inputs; above (up to 76 conditions), every condition ends covered or impossible with valid pairs; three forms |

The last run was on 2026-11-17, with Python 3.12.4 on Windows 11: 68 tests (48 qualification, 18 scenario generation and tool version, 2 TOR traceability), all passed, in under a minute.

**Validation record:** to keep evidence of a run, use

```bash
python tests/run_validation.py
```

It runs the same suite and writes `output/validation_record_<version>_<date>-<time>.md` with the items of IEC 61508-3 7.4.4.7 a) to g):
- the date and time;
- the version and digest of each document of this manual;
- the tool version, the SHA-256 of the tool files and the git commit;
- each TOR of §16 with the result of its tests;
- the Python version and the machine;
- each test with its result;
- the discrepancies.

Its exit status is 0 only if every test passed and every test named in §16 exists (`tests/test_traceability.py` checks the latter too). Keep the records under configuration management.

**Inconsistencies in the source**, detailed in [tests/SOURCES.md](../tests/SOURCES.md):
- four Appendix C entries contradict themselves and are excluded (C0604, C0793, C0794, C0839);
- the Occurs column lists 47 more one-condition occurrences than Figure 28 and the report's total;
- Table 35 prints a pair, (1, 3), that is not an independence pair under any form;
- Theorem 2 (M + 1 tests for unique-cause + masking) is contradicted by the report's own definition and is not used.

**Mutation check (2026-11-17):** deliberate errors were introduced, one at a time, in a copy of the tool, and the suite failed each time:
- unique-cause + masking pairs not restricted to edges;
- the direct check accepting diagonals;
- Theorem 2 used as the bound;
- short-circuit forms: tree_xor ignoring Not-Executed; the right operand always executed; or-else skipping on a False left operand; unique-cause without the "only *k* changed" rule; unique-cause + masking allowing other inputs; non-canonical rows used as tests (caught once the check on the distinct tests of S1 Table 32 was added); the unique-cause shortcut for coupled conditions kept in the pair search; `and then` parsed as `and`.

One mutation is not caught: keeping the N + 1 bound with short-circuit forms. No published case, and no case in a search of 19,000 random short-circuit expressions of up to 4 inputs, has a unique-cause or unique-cause + masking set below N + 1 (or V + 1). So that bound may well hold, but it isn't proved, and the tool doesn't use it (§9). Using a lower proved bound can only make the tool search longer before saying "proven minimal"; it can't make it claim a non-minimal set as minimal.

## 15. Assumptions and limitations (to state in the TOR)

1. **Independent inputs:** conditions are independent Boolean inputs. Relational conditions, and the weak coupling of S2 Appendix B, are not modelled.
2. **Evaluation of and / or:** `&&`, `||`, `and`, `or` are Boolean (both operands evaluated) unless `--short-circuit` is given; `and then` / `or else` are always short-circuit forms. The user must choose what matches the code under test (S1 §3.6: in C, `&&` and `||` are short-circuit; compiler options can also change the evaluation).
3. **Unsupported constructs:** comparators, bit-wise operations, the conditional expression `c ? a : b` (S3 §4.2.5), latches and loops (S1 §3.1.5–3.1.7, §3.7, Exercise 3.5).
4. **Unique-cause + masking has no published formula:** S2 §3.2.2 defines it in words. The tool uses the n-cube statement of S2 §5.1 and §7.1 (§8), read on the influence tree with short-circuit forms (§9). The original suggestion (S2's reference 4, Chilenski and Miller, 1994) was not available.
5. **Lower bound with short-circuit forms:** only ⌈2√M⌉ (§9); a set is "proven minimal" when the search finishes.
6. **No exact minimum published for large expressions:** S2's Figures 28-30 give it for the Appendix C expressions up to 6 conditions (reproduced); above, only S2's lower bounds. "Proven minimal" means the exhaustive search finished or reached that bound.
7. **2 s search limit:** it is machine-dependent. When it stops the search, the set is valid but "not proven minimal".
8. **Pair-search sets are not minimised:** above `--max-exact` inputs (§11), and a condition can be `UNKNOWN` if its search exceeds the budget.
9. **Python version:** it is part of the configuration (§3). Rerun the suite after any change of Python version or of the tool.
10. **Tool version:** `mcdc/version.py` holds the version. Change it with every change of `main.py` or `mcdc/`, and produce a new validation record (§14). The SHA-256 in the record identifies the tool files that were validated.

## 16. Proposed tool operational requirements

A starting point for your TOR, with the code and tests that cover each requirement. Adapt the wording and IDs to your plans.

| Id | Requirement | Code | Verified by |
|---|---|---|---|
| TOR-01 | The tool shall accept a decision written with and/or/not (also et/ou/non and &&/\|\|/!), and then, or else, ==, !=, True, False and parentheses, and reject any other syntax with a message. | `decision.py` | `InputSyntax.*`, all cases parsed in `test_qualification.py` |
| TOR-02 | The tool shall treat each occurrence of a variable as a separate condition. | `decision.py`, `tree.py` | `S2Definitions.test_figure_10_coupled`, `test_section_3_2_1_coupled_unique_cause`, `S2AppendixC.test_condition_counts` |
| TOR-03 | The tool shall compute the truth table of the decision. | `tree.truth_table` | `S2AppendixC.test_response_profiles`, `S1BuildingBlocks.*` |
| TOR-04 | The tool shall identify unique-cause independence pairs as defined in S2 §3.1.1. | `tree.is_unique_cause_pair`, `exact.independence_pairs` | `S2Definitions.test_section_3_1_1_unique_cause_pairs`, `test_section_3_2_1_coupled_unique_cause`, `S1WorkedExamples.test_example_2_and_2a` |
| TOR-05 | The tool shall identify masking independence pairs as defined by S2 §3.1.2 (graph coloring). | `tree.is_masking_pair`, `exact.independence_pairs` | `S2Definitions.test_section_3_1_1_masking_pairs`, `test_figure_6`, `test_figures_8_and_9`, `test_figure_10_coupled`, `S1WorkedExamples.*` |
| TOR-06 | The tool shall output a test set that contains an independence pair for every condition that has one, and report every other condition with the reason. | `exact.minimal_mcdc_set`, `pair_search.pair_search_set`, `report.py` | `S1BuildingBlocks.*`, `S1WorkedExamples.*`, `PairSearchEngine.*`, `AppendixCCrossCheck.*` |
| TOR-07 | The tool shall report the test set as proven minimal only when no smaller set exists. | `exact.minimal_mcdc_set`, `exact.lower_bound` | `S1BuildingBlocks.test_and_gate`, `test_or_gate`, `test_xor_gate`, `S2MinimumNumberOfTests.*` |
| TOR-08 | Above the exact-engine limit, the tool shall report each condition as covered, impossible or unknown, and only output pairs that satisfy TOR-04 / TOR-05 / TOR-10. | `pair_search.py` | `PairSearchEngine.*`, `AppendixCCrossCheck.test_large_expressions` |
| TOR-09 | Each test case shall show its truth-table row number, its input values and its expected output. | `report.print_table` | `test_scenario.CommandLine.test_csv_output_stays_clean`; review of the output |
| TOR-10 | The tool shall identify unique-cause + masking independence pairs as defined in S2 §3.2.2, stated on the n-cube in §5.1 and §7.1 (edge transition and graph-coloring pair). | `tree.is_unique_cause_masking_pair`, `exact.independence_pairs` | `S2UniqueCauseMasking.*` |
| TOR-11 | The tool shall evaluate `and then` / `or else` (and every and / or with `--short-circuit`) as short-circuit forms (S2 glossary), apply the definitions of TOR-04, TOR-05 and TOR-10 to the influence tree of S2 §3.1.2 with tree_xor (Figure 5), and show each input that a test doesn't evaluate as X. | `decision.py`, `tree.node_executed`, `tree.tree_xor`, `tree.independence`, `tree.canonical` | `ShortCircuit.*`, `S2AppendixC.test_response_profiles`, `S2Figures28To30.*` |
| TOR-12 | For the decisions up to the exact-engine limit, the tool shall give a test set of minimal size. | `exact.minimal_mcdc_set` | `S2Figures28To30.test_figures_28_29_30`, `S1BuildingBlocks.*`, `S2MinimumNumberOfTests.test_minimal_sets_by_exhaustive_search` |
| TOR-13 | The tool shall write a scenario file from a template as described in [SCENARIO_GENERATION.md](SCENARIO_GENERATION.md): the texts in the documented order, one input text per input, the values written with the TRUE / FALSE / NOT_EVALUATED texts, the expected output of each test case; and reject a template with an unknown key, an unknown or out-of-scope placeholder or an invalid `$`. | `scenario.py`, `main.py` | `ScenarioText.*`, `TemplateErrors.*`, `CommandLine.test_gen_scen_writes_the_file`, `CommandLine.test_template_error_stops_before_writing` |
| TOR-14 | The tool shall give its version (`--version`), and write the version and the command line into the scenario where the template asks for them (`${tool_version}`, `${tool_command}`). | `version.py`, `main.py`, `scenario.py` | `CommandLine.test_version_and_command_recorded`, `ScenarioText.test_tool_version_and_command`, `TemplateErrors.test_placeholder_out_of_scope` |
