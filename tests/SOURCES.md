# Qualification test suite: sources and traceability

Run from the project folder (Python standard library only, about 25 s):

```
python -m unittest discover -s tests -v
```

## References

| Id | Document | Where | Retrieved |
|---|---|---|---|
| S1 | NASA/TM-2001-210876, *A Practical Tutorial on Modified Condition/Decision Coverage*, K. J. Hayhurst, D. S. Veerhusen, J. J. Chilenski, L. K. Rierson, May 2001 | https://shemesh.larc.nasa.gov/fm/papers/Hayhurst-2001-tm210876-MCDC.pdf | 2026-11-15 |
| S2 | DOT/FAA/AR-01/18, *An Investigation of Three Forms of the Modified Condition Decision Coverage (MCDC) Criterion*, J. J. Chilenski, April 2001 | https://rosap.ntl.bts.gov/view/dot/42764 | 2026-11-15 |

No standard (DO-178C, DO-330, IEC 61508, ISO 26262) publishes a test-data set. These two FAA/NASA reports are the
source of every expected result in the suite. They use the definitions the tool implements:
- **Unique-cause MC/DC:** S2 §3.1.1 and §3.2.1.
- **Masking MC/DC:** graph coloring, S2 §3.1.2, which is also the gate analysis of S1 §3.2.
- **Unique-cause + masking MC/DC:** S2 §3.2.2, stated on the n-cube in §5.1 and §7.1: an *edge* pair (only one input changes) that is a valid graph-coloring pair.
- **Minimum number of tests:** S2 §5.1, Theorems 1 and 4. Theorem 2 is contradicted by the report's own data and is not used (see [S2 §5.1 Theorem 2](#s2-51-theorem-2)).

## Code under test

`main.py` is only the command line; the tests call the `mcdc` package directly.

| Module | Contents | Review against |
|---|---|---|
| `mcdc/decision.py` | input language → conditions and expression tree | tool requirements (input language) |
| `mcdc/tree.py` | evaluation, truth table, `is_masking_pair`, `is_unique_cause_pair`, `is_unique_cause_masking_pair` | S2 §3.1.1, §3.1.2, §3.2.2 (with §5.1 and §7.1), line by line |
| `mcdc/exact.py` | all pairs from the truth table, minimal set, `lower_bound` | S2 §3.1, §5.1 |
| `mcdc/pair_search.py` | engine for large expressions | every pair it reports is checked with `tree.py` before output |
| `mcdc/analysis.py` | engine choice (`--max-exact`) | |
| `mcdc/report.py` | text / CSV output | |
| `mcdc/scenario.py` | test scenario file from a TOML template (`-gen_scen`) | tool requirements (scenario generation), `tests/test_scenario.py` |

## Notation used in the tests

- **Test vectors:** written as in the sources, first condition first ("TFTF"). Row numbers come from them with the first input as the most significant bit, which is also S2's numbering ("4:(TFF)").
- **xor:** written `!=`, the tool's xor operator.
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
| `S2AppendixC.test_condition_counts` | S2 App. C, section headings | each converted expression has the stated number of conditions |
| `S2AppendixC.test_response_profiles` | S2 App. C, p.C-3 (definition), C-4 to C-60 | 702 real airborne expressions: truth table = published response profile |
| `InputSyntax.test_symbols_equal_keywords` | tool requirement (input language) | every case above written with `&&` / `\|\|` / `!` gives the same conditions, truth table and pairs as with `and` / `or` / `not` |
| `InputSyntax.test_not_binds_like_c` | tool requirement (input language) | `!` binds tighter than every other operator, as in C: `!a == b` is `(!a) == b` |
| `PairSearchEngine.*` | all the cases above | in each of the three forms, the pair-search engine reaches the same coverable/impossible conclusions, with valid pairs, and its pair for S2 §3.1.1 is one of the published pairs |
| `AppendixCCrossCheck.*` | expressions of S2 App. C | **engine cross-check, not a published oracle**: see below |
| `test_scenario.ScenarioText.test_mcdc_scenario` | tool requirement (scenario generation); vectors from S1 §3.1.1, Table 5 | the 3-input and set rendered with a template gives the exact expected text (section order, one line per input, numbering, `${row}`, inverse output, TRUE/FALSE texts, `{ } " % \ $$` literal) and file name |
| `test_scenario.ScenarioText.*` (other) | tool requirement (scenario generation) | full truth table without `--mcdc`, defaults, `${expression}` as typed |
| `test_scenario.TemplateErrors.*` | tool requirement (scenario generation) | a wrong template (unknown or out-of-scope placeholder, bad `$`, unknown key, bad value, not TOML) is rejected with the key named |
| `test_scenario.CommandLine.*` | tool requirement (command line) | `-gen_scen` / `--gen-scen` write the file (default folder `output/`, or `--output-dir`); `--csv` output stays clean; a template error stops before anything is written; no expression → help |

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

The edges of coupled conditions can form a cycle in the n-cube (B#1, D#1, B#2, D#2 above form a square), which the theorem's proof doesn't allow for. The tool uses max(V + 1, ⌈2√M⌉) instead, V being the number of distinct inputs among the M conditions; the proof is in `exact.lower_bound` and docs/MCDC_IMPLEMENTATION.md §9. Without repeated inputs V = M, and this is Theorem 1.

## S2 Appendix C data

`data/ar0118_appendix_c.tsv` is generated from the report text by `tools/extract_ar0118_appendix_c.py` (see its docstring for the exact conversion rules).

**What it contains:** 1112 expressions with their section, page, stated number of conditions and response profile. 1023 of them are converted to the tool's grammar. The other 89 are not converted:
- 69 use `and then` / `or else`;
- 16 use `xor`;
- 2 have a call or index syntax inside a condition;
- 2 are `Bv = not (Bv2)`.

**How expressions are converted:** following the report's own counting, each relational expression (e.g. `Ev = El`) is one condition, and its complement (`Ev /= El`) is the same condition negated. This reproduces both the stated number of conditions and the profiles.

**Which profiles are checked:** only profiles made of T/F, 705 entries. Profiles containing `-` (infeasible combinations) or lower-case letters (short-circuit, not executed) aren't used. Three entries are excluded because the report contradicts itself, which is listed in `SOURCE_INCONSISTENT`:

| Id | Inconsistency in the source |
|---|---|
| C0604 | profile 16:FFFTFFFF (string and number agree) has its only T on a row where `not Bv and not Bv2` is False |
| C0793 | printed string FFFFFFFTFTFTFTFF ≠ profile number 341 (the number matches the expression) |
| C0839 | profile number 28627 ≠ printed string (28672; the string matches the expression) |

**The engine cross-check is not a published oracle.** Appendix C gives the expressions but no MC/DC answers, so `AppendixCCrossCheck` only checks the tool against itself:
- **Up to 8 inputs (963 expressions):** the pair-search engine must agree with the exact engine on which conditions are coverable.
- **Above 8 inputs (60 expressions, up to 76 conditions):** every condition must end covered or proven impossible, and every pair must pass the direct definition check (`is_masking_pair` / `is_unique_cause_masking_pair` / `is_unique_cause_pair`). Those checks are themselves validated against the published pairs in `PairSearchEngine.test_published_pairs_pass_direct_check` and `S2UniqueCauseMasking.test_published_pairs_direct_check`.

Both checks run for the three forms.

Decide whether to count this category as qualification evidence.

## Excluded from the sources (not expressible in the tool's grammar)

- **S1 §3.1.5 comparator, §3.1.6 if-then-else, §3.1.7 loops, §3.7 bit-wise operations:** not Boolean decisions of this grammar.
- **S1 §3.6 and S2 Fig. 7, short-circuit forms (`or else`, `and then`):** the tool evaluates `and`/`or` (also written `&&` / `||`) as Boolean operators with both sides, as S2 Fig. 6 and S1's gates do.
- **S1 Exercise 3.5, reset-overrides-set latch:** the output feeds back into the decision.
- **S2 Appendix B, weakly coupled relational conditions:** the tool treats conditions as independent Boolean inputs.
- **S2 §7.2, Table 36:** the context-dependent version of Table 35 removes infeasible combinations of weakly coupled conditions, which the tool doesn't model.

## Known gaps: limitations to state in the Tool Operational Requirements

- **No published exact minimum for large expressions:** no source gives the exact minimum set for large expressions, only the S2 §5.1 lower bounds. A set reported "proven minimal" reached that bound, or the exhaustive search finished.
- **No published formal definition of unique-cause + masking:** S2 §3.2.2 defines it in words. The tool uses the n-cube statement of §5.1 and §7.1 (edge transitions), which reproduces every pair of Tables 32-35 except the misprinted one. The original suggestion (S2's reference 4, Chilenski and Miller, 1994) was not available.
- **The exact engine's minimal-set search stops after 2 s:** when it stops, the set is valid but "not proven minimal", and its size can depend on the machine's speed.
- **The pair-search engine (more than `--max-exact` inputs, default 10) doesn't minimise:** in masking mode its sets are well above the S2 Theorem 4 bound (76 conditions: 78 tests, bound 18). Its job is completeness: every condition is covered, proven impossible, or reported UNKNOWN if its search budget is exceeded. It is never dropped silently.
- **`&&`, `||` and `!` are Boolean and / or / not:** both operands are always part of the decision, and `!` binds as in C. The short-circuit forms (`and then`, `or else`, S2 Fig. 5 not-executed values) are not supported.
- **The suite tests the tool in its environment:** the Python version is part of the tool's configuration.
