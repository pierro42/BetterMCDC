# Adequacy with DO-178C and DO-330

This document maps the MC/DC tool and its evidence to the airborne software framework:
- DO-178C / ED-12C, *Software Considerations in Airborne Systems and Equipment Certification*;
- DO-330 / ED-215, *Software Tool Qualification Considerations*;
- the FAA material that recognizes them.

It is meant for the tool user's plans (PSAC, Tool Qualification Plan) and for the certification authority.

**Status: preliminary.** DO-178C, DO-330 and DO-248C are licensed RTCA / EUROCAE documents that were not available when this was written. Everything here comes from the public FAA documents listed in §1, and no statement is made about what the RTCA texts say beyond what those documents quote. Each point that needs an RTCA text is marked **open** (§8). Like [IEC_61508_ADEQUACY.md](IEC_61508_ADEQUACY.md), this document doesn't qualify the tool by itself.

## 1. Documents

| Id | Document | Status | Used for |
|---|---|---|---|
| AC | FAA AC 20-115D, *Airborne Software Development Assurance Using EUROCAE ED-12( ) and RTCA DO-178( )*, 07/21/2017 | public, used | which documents are recognized, tool qualification (¶10), TQL correlation (Table 2) |
| ORD | FAA Order 8110.49A, *Software Approval Guidelines*, 3/29/2018 | public, used | document dates, definitions, tools at conformity inspection |
| S3 | DOT/FAA/AR-06/54, *Software Verification Tools Assessment Study*, June 2007 | public, used | DO-178B MC/DC and tool qualification wording it quotes, MC/DC forms, short-circuit operators |
| S1, S2 | NASA/TM-2001-210876; DOT/FAA/AR-01/18 | public, used | the MC/DC definitions the tool implements ([MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §2) |
| DO-178C / ED-12C | December 13, 2011 / January 2012 | licensed, **not available** | MC/DC definition (glossary), Table A-7, §12.2 tool qualification, Table 12-1 |
| DO-330 / ED-215 | December 13, 2011 / January 2012 | licensed, **not available** | tool qualification objectives (Annex A tables), life cycle data |
| DO-248C / ED-94C | December 13, 2011 / January 2012 | licensed, **not available** | FAQs and discussion papers on MC/DC and tools |
| CAST-6 | *Rationale for Accepting Masking MC/DC in Certification Projects*, 2001 | public (archived), **not available** | acceptance of masking MC/DC |

The dates of DO-178C, DO-248C and DO-330 are those given by AC ¶11.c and ORD chapter 1 ¶3.c.

## 2. In short

- **The framework.** AC 20-115D recognizes DO-178C and DO-330 (AC ¶1.b), and DO-248C as a supporting document (AC ¶1.c). For tool qualification, it states the following (AC ¶10):
  - DO-178C §12.2 and DO-330 provide an acceptable method;
  - DO-330 has its own complete set of objectives, activities and life cycle data.
- **This tool is a verification tool.** Its output, test cases with expected results, is not part of the airborne software.
- **The likely qualification level is TQL-4 or TQL-5.** AC Table 2 correlates DO-178B verification tools with DO-178C tool criteria 2 or 3, which give TQL-4 or TQL-5 (§4). Which criterion applies, and whether the tool needs qualifying at all, depends on how you use it. The rules are in DO-178C §12.2 and Table 12-1 (open D-1).
- **On MC/DC, the tool follows the FAA reports.** It implements the three forms that the FAA's reports describe ([S2], [S3] Appendix A): unique-cause (the literal reading of the DO-178B wording), masking (accepted through CAST-6) and unique-cause + masking. Its expected results are checked against the published ones. Whether the DO-178C glossary definition reads the same way is open (D-2).
- **Short-circuit forms are a known area of interpretation.** [S3] reports that DO-248B suggested a separate-decision reading. The tool implements the whole-decision reading of S1 §3.6 and S2 (§5). DO-248C's position is open (D-3).

## 3. MC/DC as the FAA documents state it

**DO-178B definition.** [S3] §3.1.1 quotes the DO-178B glossary definition of MC/DC. A condition shows its independent effect by "varying just that condition while holding fixed all other possible conditions". [S3] §3.1.1 calls this reading unique-cause MC/DC. It adds that masking MC/DC "has gained acceptance by regulatory authorities", through CAST-6 ([S3] §3.1.2).

**The three forms.** [S3] Appendix A describes three variants: unique-cause (UCM), masking (MSM) and unique-cause + masking (USM). They match the tool's three forms:

| [S3] Appendix A | Tool (`--mcdc`) | Defined in | Tool documentation |
|---|---|---|---|
| Unique-Cause MCDC (UCM): all other conditions held fixed, coupled or not | `unique-cause` | S2 §3.1.1 | [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §6 |
| Masking MCDC (MSM): the other conditions set so that the effect of the changed condition is observed at the output | `masking` | S2 §3.1.2 (graph coloring) | §7 |
| Unique-Cause + Masking (USM): masking, with the other noncoupled conditions held fixed | `unique-cause+masking` | S2 §3.2.2 | §8 |

**Coupled conditions.** [S3] Appendix A also distinguishes strongly and weakly coupled conditions. The tool models the strong coupling of a repeated variable (each occurrence is a condition). It doesn't model weak coupling such as `Y < 1` and `Y < 10`. That limitation is stated in [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §15 item 1.

**Software level.** Under DO-178B, [S3] §3.1.1 reports that Table A-7 requires MC/DC for Level A only. The corresponding DO-178C objective and its table entry are open (D-2).

**Source and object code.** [S3] §4.9 notes that MC/DC reached at source level doesn't guarantee MC/DC at object code level, and the reverse. The tool works on the decision as written. Analysing coverage of the object code (CAST-17, DO-248B DP #12, cited by [S3]) remains the user's verification activity.

## 4. Tool qualification

**When a tool needs qualifying.** [S3] §3.1.3 summarizes DO-178B §12.2: tool qualification is needed when a tool eliminates, reduces or automates a process "without its output being verified". So whether this tool needs qualifying depends on its use:

| Use of the tool | Its output verified by | Qualification |
|---|---|---|
| It proposes test cases. The tests are run on the code, and MC/DC is measured there by a coverage analysis tool or process that has its own credit. | the structural coverage analysis, which shows any condition the tests miss | possibly not needed, to confirm against DO-178C §12.2 (D-1) |
| Its result replaces a verification activity, for example "these tests give MC/DC" claimed without coverage analysis, or its expected outputs used without review | nothing | needed, at the TQL given by DO-178C §12.2.2 and Table 12-1 (D-1) |

**Qualification level.** AC 20-115D ¶10.c(1) says that DO-178C sets five tool qualification levels, from the tool's use and its potential impact (DO-178C §12.2.2 and Table 12-1). AC Table 2 correlates the DO-178B qualification types with the DO-178C criteria and TQLs:

| DO-178B tool type | Software level | DO-178C tool criteria | TQL (DO-330) |
|---|---|---|---|
| Development | A / B / C / D | 1 | TQL-1 / TQL-2 / TQL-3 / TQL-4 |
| Verification | A, B | 2 | TQL-4 |
| Verification | C, D | 2 | TQL-5 |
| Verification | all | 3 | TQL-5 |

As a verification tool, this tool falls under criteria 2 or 3, so it would need **TQL-5**, or **TQL-4** under criteria 2 at levels A and B. The definitions of criteria 2 and 3 are in DO-178C §12.2.2, which isn't available here (D-1). The proposed level is therefore not stated yet.

**What qualification means for a verification tool.** [S3] §3.1.3 quotes DO-178B §12.2.2: a verification tool is qualified by showing that it "complies with its Tool Operational Requirements under normal operational conditions". [S3] §4.10 adds that most of the uncertainty is in defining acceptable Tool Operational Requirements and how deeply to verify them. Under DO-178C, the objectives for each TQL are in the DO-330 Annex A tables (AC ¶6.a), and the data to submit is listed in DO-330 §9.0.a (AC ¶6.b). Mapping the evidence below to those objectives is open (D-4).

**Evidence available in this repository:**

| Need | Evidence |
|---|---|
| Tool Operational Requirements | [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §16, TOR-01 to TOR-14, each with the code and tests that cover it |
| Behaviour, limits, operational conditions | [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §1 (scope), §3 (configuration: Python version, standard library only, determinism), §4–§13, §15 (assumptions and limitations); [README](../README.md) |
| Verification of the TOR against expected results | `tests/test_qualification.py`, where every expected result is transcribed from S1, S2 or S3 ([tests/SOURCES.md](../tests/SOURCES.md)); `tests/test_scenario.py`; `tests/test_traceability.py`, which checks that every TOR names existing tests |
| Record of a verification run | `python tests/run_validation.py`: the date, the tool version and the SHA-256 of its files, the documents and their versions, each TOR with its result, the environment, each test with its result, and the discrepancies ([MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §14) |
| Robustness of the test suite | the mutation check of [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §14: deliberate errors in the definitions are each caught by the suite |
| Configuration identification | `main.py --version`; `${tool_version}` and `${tool_command}` record the version and command line in each generated scenario; SHA-256 of the tool files in the record; git history |
| Changes to the tool | new version number for each change, git history, rerun of the suite. AC ¶10.c(2)(a) and (3)(a)(ii) refer to a tool change impact analysis, under DO-330 §11.2.2 / §11.2.3 for a change to the tool's environment or to the tool itself. |
| Known errors of the sources | [tests/SOURCES.md](../tests/SOURCES.md): the inconsistencies of S2 that the tests exclude, and why |

**Not provided, because it's the applicant's:**
- the Tool Qualification Plan and the PSAC entries (AC ¶8.a(2) for supplements);
- the tool's configuration in the life cycle environment;
- the qualification records of the project;
- the conformity evidence that tools needing qualification have been qualified (ORD chapter 4 ¶3.a(4)).

## 5. Short-circuit forms

[S3] §4.2.5 and §4.3.2 treat short-circuit operators as an open issue of coverage:
- In C, `&&` and `||` always short-circuit. In Ada, `and then` / `or else` do, while `and` / `or` evaluate both operands.
- DO-248B DP #13 suggested treating each short-circuited condition as a separate decision.
- With nested short-circuit forms, the two readings differ. For `(A and then B) or else C`, [S3] states that "A minimum of four test cases are needed to achieve MCDC". It then gives three tests that satisfy the separate-decision reading.

The tool implements the whole-decision reading of S1 §3.6 and S2 (§3.1.2 rule b and Figure 5) ([MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §9):
- For `(A and then B) or else C`, it gives 4 tests, proven minimal, in all three forms.
- [S3]'s three tests don't make an MC/DC set under that reading.
- Both points are checked by `ShortCircuit.test_ar0654_section_4_3_2`.

So for some decisions, a project that follows the separate-decision reading would accept fewer tests than the tool proposes. Whether DO-248C keeps, changes or withdraws the DP #13 position is open (D-3).

The conditional expression of C (`c ? a : b`), which [S3] §4.2.5 also discusses, isn't accepted by the tool ([MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md) §15 item 3).

## 6. Failure modes and conditions of use

These are the same as for IEC 61508 ([IEC_61508_ADEQUACY.md](IEC_61508_ADEQUACY.md) §6): F1 to F9 for the tool, U1 and U2 for its use. Two of them matter most for DO-178C:

- **U1, requirements-based testing.** The expected outputs are computed from the expression you give the tool. If that expression is copied from the code, the tests reproduce the code. Take it from the requirements, or review the expected outputs against them. This rests on DO-178C's principle of requirements-based testing; the section to cite is open (D-2).
- **The main mitigation is structural coverage analysis.** Measuring MC/DC on the code when the tests run shows any condition the tool's set doesn't cover, whatever the cause. It is also what can make qualification unnecessary (§4).

## 7. Division of responsibility

| Activity | Tool supplier (this repository) | Applicant |
|---|---|---|
| Tool Operational Requirements | TOR-01 to TOR-14 as a starting point | adopt or adapt them in the tool qualification data |
| Need for qualification and TQL | analysis of §4 | decide in the PSAC / Tool Qualification Plan, with the certification authority |
| Choice of MC/DC form and of the evaluation of and / or | definitions and guidance ([README](../README.md)) | decide and record it in the Software Verification Plan |
| Verification of the tool | test suite, validation record, mutation check | run it in the project environment and keep the record |
| Configuration | version, digest, `${tool_version}`, `${tool_command}` | control the tool, its templates and its outputs |
| Changes | new version, change history, new record | change impact analysis and requalification (AC ¶10.c) |
| Use | documentation of limits (§15, U1, U2) | requirements-based expressions, coverage analysis on the code |

## 8. Open items

| Id | Item | Needs | Then |
|---|---|---|---|
| D-1 | When a tool needs qualification, the tool criteria and the TQL (DO-178C §12.2, §12.2.2, Table 12-1) | DO-178C | state the criterion and TQL for each use of §4; update §2 and §7 |
| D-2 | The MC/DC definition of the DO-178C glossary, the coverage objectives of Table A-7, and the sections on structural coverage analysis and requirements-based testing | DO-178C | compare the definition with the three forms (§3); cite the objective numbers |
| D-3 | DO-248C on MC/DC: masking, coupled conditions, short-circuit forms (successor of DO-248B DP #13), definition of a decision | DO-248C | check §5 and the tool's reading; record any difference as a TOR or limitation |
| D-4 | The DO-330 objectives for TQL-5 (and TQL-4), the tool qualification life cycle data, and the change impact analysis (§11.2) | DO-330 | a clause-by-clause matrix like [IEC_61508_ADEQUACY.md](IEC_61508_ADEQUACY.md) §5 |
| D-5 | CAST-6, the acceptance of masking MC/DC | CAST-6 (archived) | cite it directly instead of through [S3] and S2 |
