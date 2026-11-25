# Qualification test suite: sources and traceability

Run from the project folder (Python standard library only, under a minute):

```
python -m unittest discover -s tests -v
```

## References

| Id | Document | Where | Retrieved |
|---|---|---|---|
| S1 | NASA/TM-2001-210876, *A Practical Tutorial on Modified Condition/Decision Coverage*, K. J. Hayhurst, D. S. Veerhusen, J. J. Chilenski, L. K. Rierson, May 2001 | https://shemesh.larc.nasa.gov/fm/papers/Hayhurst-2001-tm210876-MCDC.pdf | 2026-11-15 |
| S2 | DOT/FAA/AR-01/18, *An Investigation of Three Forms of the Modified Condition Decision Coverage (MCDC) Criterion*, J. J. Chilenski, April 2001 | https://rosap.ntl.bts.gov/view/dot/42764 | 2026-11-15 |
| S3 | DOT/FAA/AR-06/54, *Software Verification Tools Assessment Study*, June 2007 (one statement, §4.3.2) | https://www.faa.gov/sites/faa.gov/files/aircraft/air_cert/design_approvals/air_software/AR-06-54_VerificationTools.pdf | 2026-11-18 |

No standard (DO-178C, DO-330, IEC 61508, ISO 26262) publishes a test-data set. These two FAA/NASA reports are the
source of every expected result in the suite, with one statement of S3. They use the definitions the tool implements:
- **Masking MC/DC:** graph coloring, S2 §3.1.2, which is also the gate analysis of S1 §3.2: the influence set is {k}.
- **Unique-cause MC/DC:** S2 §3.1.1, §3.1.2 ("only ci has a True in the influence tree") and §3.2.1.
- **Unique-cause + masking MC/DC:** S2 §3.2.2, stated on the n-cube in §5.1 and §7.1: an *edge* pair (only one input changes) that is a valid graph-coloring pair.
- **Short-circuit forms (and then / or else):** S2 glossary, §3.1.2 rule b and Figure 5 (`tree_xor`, Not-Executed), S1 §3.6. The three definitions are applied to the influence tree, where a node is changed only if it is executed in both tests.
- **Minimum number of tests:** S2 §5.1, Theorems 1 and 4. Theorem 2 is contradicted by the report's own data and is not used (see [S2 §5.1 Theorem 2](#s2-51-theorem-2)).

## Code under test

`main.py` is only the command line; the tests call the `mcdc` package directly.

| Module | Contents | Review against |
|---|---|---|
| `mcdc/decision.py` | input language → conditions and expression tree | tool requirements (input language) |
| `mcdc/tree.py` | evaluation, executed nodes, `tree_xor`, `independence` (the three definitions), `canonical`, truth table | S2 glossary, §3.1.1, §3.1.2 (rule b, Figure 5), §3.2.2 (with §5.1 and §7.1), line by line |
| `mcdc/exact.py` | all pairs from the truth table, minimal set, `lower_bound` | S2 §3.1, §5.1 |
| `mcdc/pair_search.py` | engine for large expressions | every pair it reports is checked with `tree.py` before output |
| `mcdc/analysis.py` | engine choice (`--max-exact`) | |
| `mcdc/report.py` | text / CSV output | |
| `mcdc/scenario.py` | test scenario file from a TOML template (`-gen_scen`) | tool requirements (scenario generation), `tests/test_scenario.py` |

## Notation used in the tests

- **Test vectors:** written as in the sources, first condition first ("TFTF"). Row numbers come from them with the first input as the most significant bit, which is also S2's numbering ("4:(TFF)").
- **xor:** written `!=`, the tool's xor operator.
- **X (S1 §3.6):** an input that the test doesn't evaluate ("don't care"). The tool numbers such a test with X = F, as S2 numbers "a nonexecution due to short-circuit operators as 0" (glossary, Condition Combination).
- **Exercise 3.3c:** the relational condition `Airspeed < 40.0` is the Boolean input `Airspeed_lt_40`, with 35 knots → T and 45 knots → F, as the S1 solution does on its comparator line.

## Traceability

| Test (`test_qualification.py`) | Source | Checked |
|---|---|---|
| `S1BuildingBlocks.test_and_gate` | S1 §3.1.1, Table 5, p.16 | 3-input and: the minimal set is exactly TTT, FTT, TFT, TTF (both forms) |
| `S1BuildingBlocks.test_or_gate` | S1 §3.1.2, Table 6, p.16-17 | 3-input or: the minimal set is exactly FFF, TFF, FTF, FFT |
| `S1BuildingBlocks.test_xor_gate` | S1 §3.1.3, Table 7, p.17 | any 3 of the 4 tests give MC/DC; minimum = 3 |
| `S1BuildingBlocks.test_not_gate` | S1 §3.1.4, p.17-18 | both tests are needed |
| `S1WorkedExamples.test_example_1` | S1 §3.2, Tables 11, 15, 16, p.25-29 | tests 1, 2, 3, 5 give MC/DC; only 1, 2, 5 are valid for the and gate |
| `S1WorkedExamples.test_example_2_and_2a` | S1 §3.3, Tables 17-20, p.29-31 | both sets give masking MC/DC; Table 20 pairs found; only 2A is unique-cause |
| `S1WorkedExamples.test_example_3` | S1 §3.3, Tables 21-22, p.32-34 | Table 21 misses A; 1, 2, 4, 5 + FFTT give MC/DC |
| `S1WorkedExamples.test_exercise_3_3a` | S1 Ex. 3.3a p.34, sol. p.65-66 | A missing; or2→xor error not detected by the tests |
| `S1WorkedExamples.test_exercise_3_3b` | S1 Ex. 3.3b p.34, sol. p.67-68 | only Engine_2_On is not shown |
| `S1WorkedExamples.test_exercise_3_3c` | S1 Ex. 3.3c p.35, sol. p.68-69 | only Squat_L is not shown |
| `S1WorkedExamples.test_exercise_3_3d` | S1 Ex. 3.3d p.35, sol. p.69-70 | TT, FT, TF give MC/DC; TT, FT do not |
| `S2Definitions.test_section_3_1_1_unique_cause_pairs` | S2 §3.1.1, p.15 | A or (B and C): exactly the 3 published pairs for A |
| `S2Definitions.test_section_3_1_1_masking_pairs` | S2 §3.1.1, p.15 | exactly the 9 published masking pairs for A |
| `S2Definitions.test_figure_6` | S2 §3.1.2, Fig. 6, p.17-18 | (FTF, TFT) shows A only |
| `S2Definitions.test_figures_8_and_9` | S2 §3.1.2, Figs. 8-9, p.18-19 | (TFTF, TTFT) shows B |
| `S2Definitions.test_figure_10_coupled` | S2 §3.1.2, Fig. 10, p.19 | repeated variables: (TFF, TTF) shows the first B |
| `S2Definitions.test_section_3_2_1_coupled_unique_cause` | S2 §3.2.1, p.20 | unique-cause: no pair for coupled conditions |
| `S2UniqueCauseMasking.test_tables_32_to_35_masking_pairs` | S2 §7.1, Tables 32-35, p.55-58 | every listed independence pair (any transition type) = the tool's masking pairs, exactly; Table 35 exception below |
| `S2UniqueCauseMasking.test_tables_32_to_35_unique_cause_masking_pairs` | S2 §7.1, Tables 32-35 | the unique-cause + masking pairs are exactly the pairs listed as "Edge" |
| `S2UniqueCauseMasking.test_section_7_1_coverage_sets` | S2 §7.1, p.55-57 | which of the three forms has a coverage set, for each of the four expressions |
| `S2UniqueCauseMasking.test_figure_40` | S2 §7.1, Fig. 40, p.54 | (A and B) or (A and not B): first A shown by (1,1)-(0,1), first B never; no coverage set under any form |
| `S2UniqueCauseMasking.test_figure_41` | S2 §7.1, Fig. 41, p.54-55 | only the second A ((0,1)-(1,1)) and the third B ((1,0)-(1,1)) can be shown |
| `S2UniqueCauseMasking.test_section_3_2_2_definition` | S2 §3.2.2, p.20 | on every expression of the suite: uncoupled condition → its pairs are its unique-cause pairs; coupled condition → its masking pairs where only its own input changes |
| `S2UniqueCauseMasking.test_published_pairs_direct_check` | S2 §7.1, Tables 32-35 | `is_unique_cause_masking_pair` accepts every Edge pair and rejects every diagonal one (which `is_masking_pair` accepts) |
| `S2MinimumNumberOfTests.test_theorems_1_and_4` | S2 §5.1, Theorems 1 and 4, p.27-33 | every set ≥ N + 1 (unique-cause, and unique-cause + masking without repeated inputs) or ⌈2√M⌉ (masking, and unique-cause + masking with repeated inputs, whose sets are also masking sets) |
| `S2MinimumNumberOfTests.test_theorem_2_not_applied` | S2 §5.1, Theorem 2, p.31 | **derived check**: Theorem 2 is not used (see below) |
| `S2MinimumNumberOfTests.test_minimal_sets_by_exhaustive_search` | — | **derived check**: for every expression of the suite with ≤ 4 inputs and each form, the size found by trying every subset of rows = the tool's size, proven minimal, with a lower bound not above it |
| `S2AppendixC.test_condition_counts` | S2 App. C, section headings | each of the 1112 expressions has the stated number of conditions |
| `S2AppendixC.test_response_profiles` | S2 App. C, p.C-3 (definition), C-4 to C-60 | 878 real airborne expressions, 55 of them with short-circuit forms: truth table = published response profile (see below) |
| `S2Figures28To30.test_occurrence_totals` | S2 App. C Occurs column, §6.1.1 Fig. 28 | the occurrences of the expressions with 2 to 6 conditions add up to the figure's column totals |
| `S2Figures28To30.test_figures_28_29_30` | S2 §6.1.1, Figs. 28, 29, 30, p.39-41 | for each form and N = 2 to 6: the number of occurrences per minimal test set size, and with no coverage set, exactly as plotted (47 values) |
| `S2Figures28To30.test_one_condition` | S2 §6.1.1, Figs. 28-30 | every one-condition expression: 2 tests in every form |
| `S2Figures28To30.test_section_6_1_1_statements` | S2 §6.1.1, p.39-40 | the 2 four-condition short-circuit expressions with coupled conditions needing 7 unique-cause tests (C0827, occurs twice); masking: 85 occurrences below N + 1, none below ⌈2√N⌉ |
| `ShortCircuit.test_glossary_short_circuit_forms` | S2 glossary, Short-Circuit Form | and then / or else: result, and right-hand side evaluated only when needed |
| `ShortCircuit.test_figure_5_tree_xor` | S2 §3.1.2, Fig. 5, p.17 | the 9 cells of the tree_xor table |
| `ShortCircuit.test_figure_7` | S2 §3.1.2, Fig. 7, p.18 | A or else (B and C), (FTF, TFT): both evaluated trees, the influence tree, influence set (A) |
| `ShortCircuit.test_example_7` | S1 §3.6, Example 7, Tables 29 and 31, p.43-44 | both test sets give MC/DC for A and then B and then C and then D; Table 29 also for the and gate |
| `ShortCircuit.test_tables_32_and_33` | S1 §3.6, Tables 32-33, p.45 | the minimal sets of the 4-input and-then and or-else gates, X included, proven minimal; **derived**: these 5 tests are all the distinct tests of each gate |
| `ShortCircuit.test_same_definitions_without_short_circuit` | S2 §3.1.1, §5.1, §7.1 | **derived check**: without short-circuit forms, the influence-tree definitions give exactly the direct statements (only k changes; only k's input changes) on the suite and on Appendix C up to 5 inputs |
| `ShortCircuit.test_ar0654_section_4_3_2` | S3 §4.3.2, p.19-20 | (A and then B) or else C: minimum of 4 tests, proven, in the three forms, also without short-circuit forms; **derived**: the report's 3 tests (separate-decision reading of DO-248B DP #13) are not an MC/DC set |
| `ShortCircuit.test_short_circuit_option` | tool requirement (input language) | `--short-circuit` makes every and / or (et / ou / && / \|\|) a short-circuit form |
| `InputSyntax.test_symbols_equal_keywords` | tool requirement (input language) | every case above written with `&&` / `\|\|` / `!` gives the same conditions, truth table and pairs as with `and` / `or` / `not` (and then / or else kept) |
| `InputSyntax.test_not_binds_like_c` | tool requirement (input language) | `!` binds tighter than every other operator, as in C: `!a == b` is `(!a) == b`; `!` is also accepted right after `and then` / `or else` |
| `InputSyntax.test_xor_spellings_equal_not_equal` | tool requirement (input language), on the published xor cases | every case above written with `!=` (S1 Table 7 two-input xor, EX3, S2 Figure 8) gives the same tree, conditions, truth table and pairs with `xor`, `^` and `ouexclusif` |
| `InputSyntax.test_xor_precedence` | tool requirement (input language) | `^` binds as `!=`: tighter than not / and / or, `!` still applies to the next operand only, `a ^ b ^ c` is `(a ^ b) ^ c` |
| `InputSyntax.test_xor_with_comparison_needs_parentheses` | tool requirement (input language) | `a ^ b == c` (read differently by Python and C) is rejected without parentheses; other operators (`&`, `+`, `-`, `~`, `<`) are rejected with the expression quoted |
| `InputSyntax.test_errors_point_at_the_text_as_typed` | tool requirement (input language) | syntax error columns and the quoted comparison of the xor message refer to the text as typed, also on replaced operators (`&&`, `et`, `xor`, `ouexclusif`, `!`) |
| `InputSyntax.test_then_is_a_keyword` | tool requirement (input language) | `then` (second word of `and then`) is rejected as a variable name; `Then` is an ordinary name |
| `InputSyntax.test_display_keeps_meaning` | tool requirement (report) | the displayed decision keeps the spellings typed and the parentheses C needs (`!(a == b)`); every case above without repeated variables, read again from its displayed text, gives the same tree |
| `PairSearchEngine.*` | all the cases above | in each of the three forms, the pair-search engine reaches the same coverable/impossible conclusions, with valid pairs, and its pair for S2 §3.1.1 is one of the published pairs |
| `AppendixCCrossCheck.*` | expressions of S2 App. C | **engine cross-check, not a published oracle**: see below |
| `test_scenario.ScenarioText.test_mcdc_scenario` | tool requirement (scenario generation); vectors from S1 §3.1.1, Table 5 | the 3-input and set rendered with a template gives the exact expected text (section order, one line per input, numbering, `${row}`, inverse output, TRUE/FALSE texts, `{ } " % \ $$` literal) and file name |
| `test_scenario.ScenarioText.*` (other) | tool requirement (scenario generation) | full truth table without `--mcdc`, defaults, `${expression}` as typed, `NOT_EVALUATED` for inputs a test doesn't evaluate (vectors from S1 Table 32) |
| `test_scenario.TemplateErrors.*` | tool requirement (scenario generation) | a wrong template (unknown or out-of-scope placeholder, bad `$`, unknown key, bad value, not TOML) is rejected with the key named |
| `test_scenario.CommandLine.*` | tool requirement (command line) | `-gen_scen` / `--gen-scen` write the file (default folder `output/`, or `--output-dir`); `--csv` output stays clean; a template error stops before anything is written; no expression → help; a repeated condition without a unique-cause pair is reported as coupled, not redundant (with and without short-circuit forms) |

## S2 §7.1 data (unique-cause + masking)

**Transcription:** Tables 32-35 were read with `pdftotext -table` (PDF pages 73-75), which keeps the rows aligned; the plain text extraction scrambles them. In Table 34 the text layer adds a stray "B" after "C (1st occurrence)"; the pair (4, 5) on that line is C's.

**Table 35 inconsistency** (`SOURCE_INCONSISTENT_PAIRS`): the table prints (1, 3) as an Edge pair of A (2nd occurrence) in (A and B) or (not A and C). Rows 1 (FFT) and 3 (FTT) differ in B, not A, and both give True, so no form of S2 §3.1.1 accepts it. The test checks that (1, 3) is *not* a pair, and that the other published pair (1, 5) is found. The tool's other masking pair for A (2nd occurrence) is (3, 5), checked here by hand with the S2 §3.1.2 graph coloring:

| Node | 3:(FTT) | 5:(TFT) | Changed |
|---|---|---|---|
| A (both leaves), B | F, T | T, F | yes |
| C | T | T | no |
| A and B | F | F | **no** |
| not A | T | F | yes |
| not A and C | T | F | yes |
| output (or) | T | F | yes |

Only the path of A (2nd occurrence) (A → not A → not A and C → or) is fully changed, so the influence set is {A (2nd occurrence)}. The two rows differ in two inputs, so it is a diagonal pair: a masking pair but not a unique-cause + masking pair. That matches the table's Edge pairs for this condition once (1, 3) is removed.

<a id="s2-51-theorem-2"></a>
## S2 §5.1 Theorem 2

Theorem 2 (p.31) says that unique-cause + masking needs at least M + 1 tests for M occurrences. The report's own definition contradicts it:

- **(B and not D) or (not B and D):** M = 4 occurrences but only 2 inputs, so 4 possible tests. Every occurrence has an edge pair among them: B#1 (FF, TF), D#1 (TF, TT), B#2 (FT, TT), D#2 (FF, FT). For B#1, for example: B toggles, `B and not D` goes F→T, `not B and D` stays F (D = F), so the influence set is {B#1}. 4 tests < M + 1 = 5.
- **S2 Fig. 10, (A and B) or (A and C) or (B and C):** M = 6, and the tool finds a 6-test unique-cause + masking set (< 7). Each of its pairs passes `is_unique_cause_masking_pair`, and `test_minimal_sets_by_exhaustive_search` confirms 6 by trying every subset of rows.

The edges of coupled conditions can form a cycle in the n-cube (B#1, D#1, B#2, D#2 above form a square), which the theorem's proof doesn't allow for. The tool uses max(V + 1, ⌈2√M⌉) instead, V being the number of distinct inputs among the M conditions; the proof is in `exact.lower_bound` and docs/MCDC_IMPLEMENTATION.md §10. Without repeated inputs V = M, and this is Theorem 1.

## S2 Appendix C data

`data/ar0118_appendix_c.tsv` is generated from the report text by `tools/extract_ar0118_appendix_c.py` (see its docstring for the exact conversion rules).

**What it contains:** 1112 expressions with their section, page, stated number of conditions, response profile and number of occurrences in the software. All of them are converted to the tool's grammar; 69 use the short-circuit forms `and then` / `or else`.

**Two texts of the report are used** (both from `pdftotext`, xpdf 4.00): the `-layout` text for the expressions and profiles, and the `-table` text for the Occurs column, because the `-layout` text sometimes moves an Occurs value onto a heading line. The two are matched expression by expression; any difference stops the extraction. The totals then match Figure 28 for 2 to 6 conditions.

**How expressions are converted:** following the report's own counting, each relational expression (e.g. `Ev = El`) is one condition, and its complement (`Ev /= El`) is the same condition negated. This reproduces both the stated number of conditions and the profiles. `xor` becomes the tool's `!=` (parenthesised, since Ada doesn't mix xor with and / or), `Bv = not (Bv2)` becomes `(Bv == (not Bv2))`, and parentheses inside a condition (e.g. `Fxv > (Fxv2-url)`) stay part of its text.

**Which profiles are checked:** every profile, 878 entries once the four inconsistent ones are left out:
- **result:** the tool's truth table gives the same T/F at every position, except positions marked `-` (combinations infeasible in context, which the tool doesn't model);
- **transcription:** for profiles without `-`, the profile number has a 1 exactly where the string has T or t. Profiles with `-` are listed under the number of the context-free function, which need not match their string (e.g. C0757, `------FF--FFFFTF` under number 1);
- **lower-case letters:** they only appear with short-circuit forms, and the report doesn't define them. In every profile they are exactly the rows that are not a distinct test under the report's numbering of a nonexecution as 0: rows that give True to an input the test doesn't evaluate. The test checks this, so the tool's not-executed inputs are checked on the 55 profiles of short-circuit expressions (46 without `-`, 9 with; 53 of them contain lower-case letters).

Four entries are excluded because the report contradicts itself, which is listed in `SOURCE_INCONSISTENT`:

| Id | Inconsistency in the source |
|---|---|
| C0604 | profile 16:FFFTFFFF (string and number agree) has its only T on a row where `not Bv and not Bv2` is False |
| C0793, C0794 | heading C.4.13: printed string FFFFFFFTFTFTFTFF (340) ≠ number 341. C0793's truth table is 341, C0794's (`(Bv xor (Bv2 and Bv3)) and Bv4`) is 340: the two expressions under this heading have different truth tables |
| C0839 | profile number 28627 ≠ printed string (28672; the string matches the expression) |

**Extraction defects fixed** while adding the occurrences (the conversions are unchanged): the statement code `'b` is also printed `b'`, which had stayed in the text of C0075; the column heading "Statement Occurs" had stayed in the text of C0352 and C0482.

## S2 §6.1.1, Figures 28-30

The figures plot, for 1 to 6 conditions and each form, how many expression occurrences of Appendix C need a minimal coverage set of each size, or have none ("context free": every combination feasible). S2 computed them exhaustively. The test computes the same with the tool and compares every plotted value (47 of them):

| Figure | Form | N = 2 | N = 3 | N = 4 | N = 5 | N = 6 |
|---|---|---|---|---|---|---|
| 28 | unique-cause | 3: 2255, none: 7 | 4: 653, none: 32 | 5: 382, 7: 2, none: 7 | 6: 120, none: 11 | 7: 78, none: 1 |
| 29 | unique-cause + masking | 3: 2255, 4: 2, none: 5 | 4: 654, 5: 1, 6: 18, none: 12 | 5: 382, 6: 4, 7: 3, 10: 1, none: 1 | 6: 121, 7: 6, 8: 1, 9: 2, none: 1 | 7: 78, 9: 1 |
| 30 | masking | 3: 2255, 4: 2, none: 5 | 4: 671, 5: 1, 6: 9, none: 4 | 4: 46, 5: 344, 10: 1 | 5: 9, 6: 119, 7: 2, 8: 1 | 5: 14, 6: 16, 7: 49 |

"size: occurrences". This checks, on real airborne expressions and including the 69 with short-circuit forms, the three definitions, the not-executed handling, and the minimality of the sets.

**Transcription:** the labels are placed beside each dot; read with `pdftotext -layout` (PDF pages 56-58). Three labels of Figure 30 (344, 119, 16) print between two grid lines. They are placed by the text of §6.1.1: "the majority of test sets are still of size N + 1" (344 at 5 for N = 4, 119 at 6 for N = 5), and "85 of 20,030" occurrences below N + 1, which only adds up with 16 at 6 for N = 6.

**Inconsistency in the source:** the Occurs column lists 16,538 one-condition occurrences, Figure 28 plots 16,491, and the report's total of 20,256 expressions is 47 below the column's 20,303 too. The 47 can't be identified (no statement type adds up to 47), so the one-condition count is not compared; every one-condition expression needs 2 tests in every form, as plotted. The text's "20,030" for 1 to 6 conditions also differs from Figure 28's 20,039.

**The engine cross-check is not a published oracle.** Appendix C gives the expressions but no MC/DC answers, so `AppendixCCrossCheck` only checks the tool against itself:
- **Up to 8 inputs (1046 expressions):** the pair-search engine must agree with the exact engine on which conditions are coverable.
- **Above 8 inputs (66 expressions, up to 76 conditions):** every condition must end covered or proven impossible, and every pair must pass the direct definition check (`is_masking_pair` / `is_unique_cause_masking_pair` / `is_unique_cause_pair`). Those checks are themselves validated against the published pairs in `PairSearchEngine.test_published_pairs_pass_direct_check` and `S2UniqueCauseMasking.test_published_pairs_direct_check`.

Both checks run for the three forms.

Decide whether to count this category as qualification evidence.

## Excluded from the sources (not expressible in the tool's grammar)

- **S1 §3.1.5 comparator, §3.1.6 if-then-else, §3.1.7 loops, §3.7 bit-wise operations:** not Boolean decisions of this grammar.
- **S1 Exercise 3.5, reset-overrides-set latch:** the output feeds back into the decision.
- **S2 Appendix B, weakly coupled relational conditions:** the tool treats conditions as independent Boolean inputs.
- **S2 §7.2, Table 36:** the context-dependent version of Table 35 removes infeasible combinations of weakly coupled conditions, which the tool doesn't model.

## Known gaps: limitations to state in the Tool Operational Requirements

- **No published exact minimum for large expressions:** no source gives the exact minimum set for large expressions, only the S2 §5.1 lower bounds. A set reported "proven minimal" reached that bound, or the exhaustive search finished.
- **No published formal definition of unique-cause + masking:** S2 §3.2.2 defines it in words. The tool uses the n-cube statement of §5.1 and §7.1 (edge transitions), which reproduces every pair of Tables 32-35 except the misprinted one. The original suggestion (S2's reference 4, Chilenski and Miller, 1994) was not available.
- **The exact engine's minimal-set search stops after 2 s:** when it stops, the set is valid but "not proven minimal", and its size can depend on the machine's speed.
- **The pair-search engine (more than `--max-exact` inputs, default 10) doesn't minimise:** in masking mode its sets are well above the S2 Theorem 4 bound (76 conditions: 78 tests, bound 18). Its job is completeness: every condition is covered, proven impossible, or reported UNKNOWN if its search budget is exceeded. It is never dropped silently.
- **`&&`, `||` and `!` are Boolean and / or / not by default:** `and then` / `or else` are always short-circuit forms, and `--short-circuit` makes every and / or one, as `&&` / `||` are in C. Choosing the right evaluation for the code under test is the user's responsibility.
- **Short-circuit forms with unique-cause + masking:** S2 defines unique-cause with Not-Executed values (§3.1.2) but gives unique-cause + masking only in words (§3.2.2). The tool applies the same reading to the influence tree: every changed condition must be an occurrence of k's input. Without short-circuit forms this is exactly the edge rule of §5.1 and §7.1; with them, Figure 29 (which includes the 69 short-circuit expressions) is reproduced exactly.
- **Lower bound with short-circuit forms:** only ⌈2√M⌉ is used (the N + 1 and V + 1 arguments assume n-cube edges, and pairs with short-circuit forms may change inputs that are not evaluated). "Proven minimal" then relies on the search finishing.
- **The suite tests the tool in its environment:** the Python version is part of the tool's configuration.
