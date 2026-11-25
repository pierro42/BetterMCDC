# Adequacy with IEC 61508

This document maps the MC/DC tool and its evidence to IEC 61508-3:2010:
- the requirements on MC/DC coverage;
- the requirements on off-line software support tools, clause 7.4.4.

It is meant for the tool user's safety planning and for the functional safety assessor.

It does not qualify the tool by itself. The tool class, the level of reliance on the tool and the acceptance of this evidence are decided in your safety and verification plans, with your assessor.

**About the standard's text:** IEC 61508 is licensed text. This document paraphrases it, and cites clause and table numbers so that each statement can be checked against a licensed copy. The copies used are not in the repository: `ressources/licensed/` is excluded by `.gitignore`.

## 1. Documents

| Document | Edition | Used |
|---|---|---|
| IEC 61508-3 *Software requirements* | Edition 2.0, 2010-04 | yes: every clause and table cited here |
| IEC 61508-4 *Definitions and abbreviations* | 2010 edition not available | no (see below) |
| IEC 61508-7 *Overview of techniques and measures* | 2010 edition not available | no (see below) |
| [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) | this repository | the tool specification, its limits and its tool operational requirements (TOR) |
| [tests/SOURCES.md](../tests/SOURCES.md) | this repository | where every expected result of the test suite comes from |

**Parts 4 and 7: the 1997 drafts don't apply.** The copies of Parts 4 and 7 that were available are 1997 pre-publication drafts ("Version 4.0, 05/12/97"). They don't match the 2010 Part 3:
- **Part 4 (1997):** no definition of off-line support tools and no tool classes. 2010 Part 3 relies on the classes T1, T2 and T3, defined in 3.2.11 of the 2010 Part 4.
- **Part 7 (1997), C.5.8 "Structure based testing":** lists statements, branches, compound conditions, LCSAJ, data flow, call graph and entire path. MC/DC isn't among them, whereas 2010 Part 3 Table B.2 lists MC/DC and refers to C.5.8 for its description.

So this document uses neither draft as evidence. The statements that need the 2010 Parts 4 and 7 are marked **open** (§8).

## 2. In short

- **IEC 61508-3 does not define MC/DC and publishes no test data.** It names MC/DC coverage as a technique (Table B.2, §3), and leaves its description to Part 7. So the tool's algorithm can't be checked against the IEC text itself.
- **The tool checks its algorithm against the FAA and NASA reports.** It implements and tests the three forms of MC/DC defined in DOT/FAA/AR-01/18 and NASA/TM-2001-210876, against the expected results published there ([MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §14). Those reports are the reference definitions of MC/DC used in certification. Whether they are an acceptable definition of the MC/DC of Table B.2 is for your assessor to accept (open item O-2).
- **What IEC 61508-3 does specify is what is required of an off-line support tool (7.4.4).** §5 maps each requirement to the evidence in this repository, and shows which part is the tool user's.

## 3. Where MC/DC appears in IEC 61508-3

**Table B.2 "Dynamic analysis and testing", item 7d:** structural test coverage of conditions, MC/DC, 100 %.

| Table B.2 item | SIL 1 | SIL 2 | SIL 3 | SIL 4 |
|---|---|---|---|---|
| 7d structural test coverage (conditions, MC/DC) 100 % | R | R | R | HR |

R = recommended, HR = highly recommended.
- **Other coverage measures:** items 7a to 7c (entry points, statements, branches) are separate measures. This tool doesn't address them.
- **Where Table B.2 is used:** in Table A.5 (software module testing and integration, item 2) and Table A.9 (software verification, item 4). In both, "dynamic analysis and testing" is R at SIL 1 and HR at SIL 2 to 4.
- **When 100 % can't be reached:** a footnote to Table B.2 asks for an explanation. For the conditions of a decision, the tool gives one. Each condition that has no independence pair is reported with its reason: redundant, or coupled with another condition in the unique-cause forms (README, *Reading the MC/DC summary*).
- **The form of MC/DC:** Part 3 doesn't say which form of MC/DC is meant. Choosing unique-cause, unique-cause + masking or masking, and the evaluation of and / or, is a verification strategy decision. Record it in your verification planning (7.9.2.2 b and c). [README](../README.md) (*Which form*) and [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §6–§9 describe each form and its source.

**Table A.5 item 8, "test management and automation tools":** R at SIL 1, HR at SIL 2 to 4. This tool is one: it generates the test cases and, with a template, the test scenario.

## 4. Tool classification

**Off-line tool.** 7.4.4.1 makes an on-line support tool part of the safety-related system. This tool runs on a development computer, and its output is test data. So it is an **off-line support tool**: a verification tool, in the sense of the examples of 7.4.4.2 NOTE 2 b).

**Proposed class: T2.** 7.4.4.4 refers to 3.2.11 of Part 4 for the classes of off-line tools. The proposed class is **T2**, for these reasons:
- the tool supports the test of the software;
- an error in the tool can make a test set weaker, so that a defect isn't revealed;
- nothing the tool produces becomes part of the executable safety-related software. The scenario files are test code.

This is to confirm against the definition in 3.2.11 of the 2010 Part 4 (open item O-1).

What 7.4.4 requires for each class:

| Clause | T2 | T3 | This tool |
|---|---|---|---|
| 7.4.4.4 specification or product documentation | required | required | provided (§5) |
| 7.4.4.5 assessment of reliance and failure mechanisms | required | required | provided (§6) |
| 7.4.4.6 evidence of conformance to the specification | — | required | provided anyway; 7.4.4.6 NOTE 2 allows its use for T2 |
| 7.4.4.15 configuration records of tool use | required | required | means provided (§5) |
| 7.4.4.16 only qualified versions used | required | required | means provided (§5) |

## 5. Clause-by-clause matrix

"Supplier" is this tool and its documentation. "User" is the project that uses the tool. The status is:
- **Covered:** the evidence is in this repository.
- **Means provided:** the tool gives what the user needs, and the user keeps the record.
- **User:** the project's responsibility.
- **N/A:** not applicable.
- **Open:** see §8.

### 5.1 Off-line support tools (7.4.4)

| Clause | Requirement (paraphrased) | Party | Evidence | Status |
|---|---|---|---|---|
| 7.4.4.1 | On-line support tools are part of the safety-related system. | — | The tool is off-line (§4). | N/A |
| 7.4.4.2 | Off-line tools are selected as a coherent part of the software development activities. | User | Your software development plan. | User |
| 7.4.4.3 | The selection of off-line tools is justified. | User | Your plan; this document and [README](../README.md) give the tool's scope and limits. | User |
| 7.4.4.4 | T2 / T3 tools have a specification or product documentation that defines their behaviour, and any instructions or constraints on their use. | Supplier | **Behaviour:** [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §4–§13 (input language, truth table, the three MC/DC forms, short-circuit forms, minimal set, engines, output), §16 (TOR-01 to TOR-14); [SCENARIO_GENERATION.md](SCENARIO_GENERATION.md). **Instructions:** [README](../README.md). **Constraints:** [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §1 (scope) and §15 (assumptions and limitations), and §6 of this document. | Covered |
| 7.4.4.5 | An assessment determines the reliance placed on T2 / T3 tools and their failure mechanisms that could affect the executable software; mitigations are taken. | Both | §6 of this document. The user confirms the reliance in their context and applies the mitigations. | Covered (supplier side) |
| 7.4.4.6 | For T3 tools, evidence that the tool conforms to its specification: history of successful use and / or validation (7.4.4.7). NOTE 2 allows the same evidence for T2. | Supplier | Validation: the test suite (`tests/`), whose expected results all come from published sources ([tests/SOURCES.md](../tests/SOURCES.md)), and the validation record (7.4.4.7). History of use: none recorded yet. | Validation covered; history open (O-3) |
| 7.4.4.7 | The tool validation results are documented: a) chronological record, b) version of the product manual, c) functions validated, d) tools and equipment, e) pass / fail with reasons, f) test cases and results, g) discrepancies. | Supplier | `python tests/run_validation.py` writes a record with sections a) to g) (§5.3). | Covered |
| 7.4.4.8 | Where the evidence of 7.4.4.6 is unavailable, there are measures to control failures of the executable system caused by tool faults. | — | This concerns faults that a tool puts into the executable system. This tool's output doesn't go into it (§4). The mitigations of §6 apply anyway. | N/A |
| 7.4.4.9 | The compatibility of the tools of an integrated toolset is verified. | User | The scenario format is defined by your template ([SCENARIO_GENERATION.md](SCENARIO_GENERATION.md)). Check that the generated scenario builds and runs in your test harness. TOR-13 covers the rendering. | User |
| 7.4.4.10 to 7.4.4.14 | Programming languages, translators, coding standards and automatic code generation for the safety-related software. | — | The tool is not a language or translator for the safety-related software. The tool itself uses Python's standard library only. Its Python version is part of its configuration ([MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §3) and is recorded in each validation record. | N/A |
| 7.4.4.15 | Where T2 / T3 tools generate configuration items, configuration management records: a) the tool and its version, b) the items it was used for, c) how it was used (parameters, options). | User | **a)** `python main.py --version`, and `${tool_version}` in the scenario. **c)** `${tool_command}` writes the full command line (expression and options) into the scenario. The template file, which is the rest of how the tool was used, is a configuration item of yours. **b)** is your configuration baseline. The example templates write a) and c) in the scenario header, and `input/test_setup_cpp_functions.toml` also in the test list header. | Means provided |
| 7.4.4.16 | Only qualified versions of T2 / T3 tools are used. | User | Each validation record gives the tool version and the SHA-256 of the tool files. Running `tests/run_validation.py` on your copy shows its version and digest, to compare with your qualified record. | Means provided |
| 7.4.4.17 | Only tools compatible with each other and with the safety-related system are used. | User | Your configuration management. | User |
| 7.4.4.18 | Each new version of an off-line tool is qualified. Earlier evidence can be reused if the changes are identified and the new version is unlikely to contain significant new faults. | Both | **Supplier:** `mcdc/version.py` changes with every change of the tool ([MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §15 item 10). The git history identifies the changes (NOTE item 1). The full suite is rerun and a new record written (NOTE item 2). **User:** decide whether the evidence is enough for your use. | Covered (supplier side) |
| 7.4.4.19 | The division of responsibility for 7.4.4 is documented in the safety planning. | Both | §7 of this document, to be taken into your safety plan. | Covered (proposal) |

### 5.2 Techniques, testing and verification

| Clause | Requirement (paraphrased) | Party | Evidence | Status |
|---|---|---|---|---|
| Table A.3 items 4a / 4b | Certified tools (R at SIL 1, HR at SIL 2 to 4), or tools with increased confidence from use (HR). These are alternatives. | Both | The tool is not certified. Confidence from use isn't established yet (O-3). The validation evidence of 7.4.4.7 is what is provided today. | Open |
| Table A.5 item 8 | Test management and automation tools. | User | This tool, used as described in [README](../README.md). | User |
| Table B.2 item 7d | MC/DC coverage, 100 %. | Both | **Supplier:** for the decision as written, the tool gives a test set with an independence pair for every condition that has one, and the reason for the others (TOR-06). **User:** coverage is achieved on the code only if the tests are run on it, and the decision and its evaluation match the code. Measure it on the code (§6). | Means provided |
| 7.4.7.2 | Module verification shows that each module performs its intended function and no unintended function. | User | The tool's expected outputs are computed from the expression you give it. Take that expression from the design (§6, U1). | User |
| 7.4.7.3, 7.4.8.4 | The results of module and integration testing are documented. | User | The tool gives the test cases and expected outputs; you document the results of running them. | User |
| 7.4.8.2 b) | The integration test specification states the test cases and test data. | User | The test table (text or `--csv`) or the scenario file can be included in it. Each test case keeps its truth-table row number (`${row}`), for traceability. | Means provided |
| 7.5.2.7 | Test cases and their expected results are documented for later analysis. | User | Same as above: every test case comes with its expected output. | Means provided |
| 7.9.2.2 c) | The verification planning addresses the selection and use of verification tools. | User | Reference this document and the chosen MC/DC form (§3). | User |
| 7.9.2.5 b) | The verification documentation identifies what the verification was done against, including the tools used. | User | Tool version and command line, from the scenario header or `--version`. | Means provided |

### 5.3 The validation record (7.4.4.7)

```bash
python tests/run_validation.py
```

The command runs the whole test suite and writes `output/validation_record_<version>_<date>-<time>.md`. Its exit status is 0 only if every test passed, and every test named in the TOR table exists.

| 7.4.4.7 | What the record contains |
|---|---|
| a) chronological record of the validation activities | start, end and duration of the run; keep the records under configuration management, in date order |
| b) version of the tool product manual | last commit and SHA-256 of README.md, MCDC_IMPLEMENTATION.md, SCENARIO_GENERATION.md, this document and tests/SOURCES.md |
| c) tool functions validated | tool version, SHA-256 of the tool files, git commit; each TOR of [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §16 with its tests and their result |
| d) tools and equipment | Python implementation and version, operating system, machine, test framework, git version |
| e) result | passed, or failed with the failing tests and reasons |
| f) test cases and results | every test, its description (its docstring gives the source of its expected results) and its result |
| g) discrepancies | failures with their messages; TOR references to tests that don't exist; and a pointer to the documented inconsistencies of the published sources, which are not tool discrepancies |

## 6. Reliance and failure mechanisms (7.4.4.5)

**Reliance.** The tool chooses the test inputs for a decision, and computes the expected output of each test. Its output doesn't go into the executable software (§4). So a tool fault can't put an error into the software. It can only make the verification weaker:
- a test set that doesn't really achieve MC/DC;
- or a wrong expected output.

A wrong expected output usually makes a test fail on correct code, which is then investigated. It hides a defect only if the code has the same wrong behaviour.

**The main mitigation is independent of this tool:** run the tests on the code and measure MC/DC coverage there, with a coverage analyser. A test set that misses a condition then shows up as missing coverage, whatever the cause.

| Id | Failure | Effect on the verification | Detection in the tool and its tests | Mitigation by the user |
|---|---|---|---|---|
| F1 | The expression is parsed as a different decision (precedence of `!`, `==`, `and then`, French keywords) | tests for another decision | `InputSyntax.*`; the summary prints the decision as parsed, fully bracketed (`Decision :` line) | compare the `Decision :` line with the source; coverage measurement |
| F2 | Wrong truth table or expected output | a test fails on correct code, or rarely passes on wrong code | 878 published response profiles (`S2AppendixC`); S1 gates and examples | review the expected outputs against the requirements (U1) |
| F3 | A reported independence pair is not one | MC/DC claimed for a condition that isn't covered | the pair-search engine checks every pair it outputs (`PAIR_CHECK`); the published pair lists of S2 §3.1.1 and §7.1; the engine cross-check | coverage measurement on the code |
| F4 | A coverable condition is reported as having no pair | a gap accepted with a wrong explanation | published coverage results (S1 examples, S2 Figures 28-30), exhaustive search up to 4 inputs | check each "NONE" reason: a redundant condition is a design question |
| F5 | A set is reported as minimal and isn't | more tests than needed; no effect on safety | lower bounds and exhaustive search (`S2MinimumNumberOfTests`); S2 Figures 28-30 | none needed |
| F6 | Short-circuit evaluation modelled differently from the code, or the not-evaluated inputs mishandled | pairs that aren't independence pairs on the code | `ShortCircuit.*` (S1 §3.6, S2 Figures 5 and 7) | choose `and then` / `or else` / `--short-circuit` to match the language and compiler (S1 §3.6); coverage measurement |
| F7 | The scenario puts a value on the wrong input, or writes a wrong expected value; the test list misses or repeats a test case | tests that don't match the table, or a test case that is never run | `ScenarioText.*` checks the exact text of the scenario and the test list; `TemplateErrors.*` rejects bad templates before writing | review the first scenario of each template against the table, using `${row}`; run it on known-good code |
| F8 | A change of Python version or of the tool changes its behaviour | any of F1 to F7 | the validation record gives the Python version, tool version and digest | rerun `tests/run_validation.py` after any change (7.4.4.18) |
| F9 | The 2 s search limit stops the minimal-set search | a valid set, reported "not proven minimal" | reported in the `Minimum` line | none needed |

Two **conditions of use** are not tool faults. They must be in your verification plan, because no test of the tool can detect them:

| Id | Condition | Why | What to do |
|---|---|---|---|
| U1 | The expected outputs are computed from the expression you give the tool. | If that expression is copied from the code, the expected outputs reproduce the code. A wrong decision in the code then passes all its tests, so 7.4.7.2 (intended function) isn't shown. | Take the expression from the requirements or the design. Otherwise, review the expected outputs against the requirements. |
| U2 | Conditions are taken as independent Boolean inputs ([MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §15). | In the code, related conditions (`x < 10`, `x < 20`) can make some test vectors impossible. | Replace the impossible vectors, and give the reason as Table B.2's footnote asks. Coverage measurement shows what was reached. |

## 7. Division of responsibility (7.4.4.19)

This is a proposal, to be taken into your safety planning.

| Activity | Tool supplier (this repository) | Tool user (your project) |
|---|---|---|
| Tool specification and constraints (7.4.4.4) | README, MCDC_IMPLEMENTATION.md, SCENARIO_GENERATION.md | read them; respect §15 and U1, U2 |
| Classification and reliance (7.4.4.5) | proposal (§4, §6) | confirm the class and reliance with the assessor |
| Validation (7.4.4.6, 7.4.4.7) | test suite and `tests/run_validation.py` | run it on your installation; keep the record |
| Selection and justification (7.4.4.2, 7.4.4.3, 7.9.2.2) | this document | software development and verification plans |
| Choice of MC/DC form and of evaluation | definitions and guidance (README) | decide and record it |
| Configuration records (7.4.4.15 to 7.4.4.17) | `--version`, `${tool_version}`, `${tool_command}`, tool digest | keep them in your baseline; use only the qualified version |
| New versions (7.4.4.18) | new version number, change history, new record | requalify before use |
| Running the tests and measuring coverage (Table B.2, 7.4.7, 7.4.8) | — | yes |

## 8. Open items

| Id | Item | To close it |
|---|---|---|
| O-1 | The tool class (T2 proposed) rests on 3.2.11 of IEC 61508-4:2010, not available here. | Read 3.2.11 of the 2010 Part 4, and confirm the class or update §4 and §5. |
| O-2 | IEC 61508-3 doesn't define MC/DC; Part 7:2010 C.5.8 describes it, not available here. The tool implements the FAA/NASA definitions. | Read C.5.8 of the 2010 Part 7 (and C.4.3, C.4.4, C.4.7, cited by Tables A.3 and A.5). Check that its description is met by the chosen form, and get the assessor's acceptance. |
| O-3 | No history of use yet (7.4.4.6, Table A.3 4b). | Record the projects and versions the tool is used with, and the problems found. |

## 9. Other standards

- **DO-178C / DO-330 (airborne software):** see [DO178C_DO330_ADEQUACY.md](DO178C_DO330_ADEQUACY.md). It is preliminary, built from the public FAA documents; the clause-by-clause matrix against DO-330 needs the RTCA texts.
