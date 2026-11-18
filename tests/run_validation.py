# -*- coding: utf-8 -*-
"""
Tool validation record, as listed in IEC 61508-3:2010 7.4.4.7 a) to g).

Runs the whole test suite (the same tests as
`python -m unittest discover -s tests`) and writes a Markdown record:

    python tests/run_validation.py [--output-dir DIR]

The record goes to the 'output' folder by default, named
validation_record_<version>_<date>-<time>.md. The exit status is 0 when
every test passed, 1 otherwise. Keep the records under your configuration
management: together they are the chronological record of the validation.

Each tool operational requirement (TOR) of docs/MCDC_IMPLEMENTATION.md
section 16 is linked to the tests named in its "Verified by" column, so a
reference to a test that doesn't exist shows up as a discrepancy.
"""

import argparse
import datetime
import hashlib
import platform
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
sys.path.insert(0, str(ROOT))
from mcdc import __version__  # noqa: E402

TOR_DOCUMENT = "docs/MCDC_IMPLEMENTATION.md"
# the "tool product manual" of 7.4.4.7 b)
MANUAL = ["README.md", TOR_DOCUMENT, "docs/SCENARIO_GENERATION.md",
          "docs/IEC_61508_ADEQUACY.md", "docs/DO178C_DO330_ADEQUACY.md", "tests/SOURCES.md"]
# the files that make up the tool
TOOL_FILES = ["main.py"] + sorted(p.relative_to(ROOT).as_posix()
                                  for p in (ROOT / "mcdc").glob("*.py"))
WATCHED = ["main.py", "mcdc", "tests", "docs", "input", "README.md"]


def _content(path):
    """File bytes with line ends normalised, so that a checkout with CRLF
    line ends gives the same digest."""
    return (ROOT / path).read_bytes().replace(b"\r\n", b"\n")


def file_digest(path):
    return hashlib.sha256(_content(path)).hexdigest()


def tool_digest():
    """SHA-256 over the names and contents of the tool files."""
    h = hashlib.sha256()
    for path in TOOL_FILES:
        h.update(path.encode("utf-8") + b"\0" + _content(path) + b"\0")
    return h.hexdigest()


def git(*args):
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                                text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


class RecordingResult(unittest.TestResult):
    """Keeps the result, time and failure details of every test."""

    def __init__(self):
        super().__init__()
        self.records = {}               # test id -> dict
        self.order = []

    def _record(self, test):
        key = test.id()
        if key not in self.records:
            self.records[key] = {"status": "PASS", "seconds": 0.0, "details": [],
                                 "description": test.shortDescription() or ""}
            self.order.append(key)
        return self.records[key]

    def _fail(self, test, status, text):
        record = self._record(test)
        if record["status"] != "ERROR":
            record["status"] = status
        record["details"].append(text)

    def startTest(self, test):
        super().startTest(test)
        self._record(test)
        self._start = time.perf_counter()

    def stopTest(self, test):
        self._record(test)["seconds"] = time.perf_counter() - self._start
        super().stopTest(test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._fail(test, "FAIL", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._fail(test, "ERROR", self._exc_info_to_string(err, test))

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            status = "FAIL" if issubclass(err[0], test.failureException) else "ERROR"
            self._fail(test, status, f"{subtest.id()}\n{self._exc_info_to_string(err, test)}")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        record = self._record(test)
        record["status"] = "SKIPPED"
        record["details"].append(reason)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._fail(test, "FAIL", "unexpected success")


def tor_table():
    """(id, requirement, verified-by cell) of each TOR row."""
    rows = []
    for line in (ROOT / TOR_DOCUMENT).read_text(encoding="utf-8").splitlines():
        if line.startswith("| TOR-"):
            cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)[1:-1]]
            rows.append((cells[0], cells[1], cells[-1]))
    return rows


def matches(reference, test_id):
    """Does `reference` (as written in the TOR table: Class.*, Class.test,
    module.Class.test, test_name or module.py) name the test `test_id`?"""
    parts, ids = reference.split("."), test_id.split(".")
    if reference.endswith(".py"):
        return ids[0] == parts[0]
    if parts[-1] == "*":
        p = parts[:-1]
        return any(ids[i:i + len(p)] == p for i in range(len(ids) - len(p)))
    return ids[-len(parts):] == parts


def trace_tors(records):
    """For each TOR: its tests, their overall result, and the references
    that match no test."""
    traced = []
    for tor, requirement, cell in tor_table():
        tests, unresolved = [], []
        for reference in re.findall(r"`([^`]+)`", cell):
            found = [t for t in records if matches(reference, t)]
            if not found:
                unresolved.append(reference)
            tests += [t for t in found if t not in tests]
        statuses = {records[t]["status"] for t in tests}
        if not tests:
            result = "NO TEST"
        elif statuses <= {"PASS"}:
            result = "PASS"
        else:
            result = "FAIL"
        traced.append((tor, requirement, cell, tests, result, unresolved))
    return traced


def _cell(text):
    return " ".join(str(text).split()).replace("|", "\\|")


def write_record(path, result, started, finished):
    records = result.records
    traced = trace_tors(records)
    failed = [t for t in result.order if records[t]["status"] not in ("PASS",)]
    untraced = [(tor, ref) for tor, _, _, _, _, refs in traced for ref in refs]
    passed = (not failed and not untraced and result.wasSuccessful()
              and result.testsRun > 0)
    commit = git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain", "--", *WATCHED)
    lines = []
    out = lines.append

    out("# Tool validation record")
    out("")
    out(f"**Tool:** MC/DC test-set generator, version {__version__}.  ")
    out(f"**Result:** {'PASSED' if passed else 'FAILED'}: {result.testsRun} test(s) run, "
        f"{len(failed)} not passed.  ")
    out("**Standard:** IEC 61508-3:2010, 7.4.4.7 a) to g); see docs/IEC_61508_ADEQUACY.md.")
    out("")

    out("## a) Chronological record of the validation activities")
    out("")
    out("| Activity | Started | Finished | Duration |")
    out("|---|---|---|---|")
    out(f"| Run of the whole test suite (`tests/run_validation.py`) | "
        f"{started.isoformat(timespec='seconds')} | {finished.isoformat(timespec='seconds')} | "
        f"{(finished - started).total_seconds():.1f} s |")
    out("")
    out("Each run writes a new record. The records kept under configuration management, "
        "in date order, are the chronological record.")
    out("")

    out("## b) Version of the tool product manual")
    out("")
    out("| Document | Last commit | SHA-256 |")
    out("|---|---|---|")
    for doc in MANUAL:
        if not (ROOT / doc).exists():
            out(f"| {doc} | missing | — |")
            continue
        last = git("log", "-1", "--format=%h %cs", "--", doc) or "not committed"
        changed = git("status", "--porcelain", "--", doc)
        out(f"| {doc} | {last}{' (modified since)' if changed else ''} | `{file_digest(doc)}` |")
    out("")

    out("## c) Tool functions validated")
    out("")
    out(f"- **Tool version:** {__version__}")
    out(f"- **Tool files:** {', '.join(TOOL_FILES)}")
    out(f"- **SHA-256 of the tool files:** `{tool_digest()}` (names and contents, "
        "LF line ends)")
    out(f"- **Git commit:** {commit or 'unknown'}"
        f"{' with uncommitted changes' if dirty else ''}")
    out("")
    out(f"Functions: the tool operational requirements of {TOR_DOCUMENT} section 16, "
        "with the tests named in their 'Verified by' column.")
    out("")
    out("| TOR | Requirement | Verified by | Tests run | Result |")
    out("|---|---|---|---|---|")
    for tor, requirement, cell, tests, status, _ in traced:
        out(f"| {tor} | {_cell(requirement)} | {_cell(cell)} | {len(tests)} | {status} |")
    out("")

    out("## d) Tools and equipment used")
    out("")
    out(f"- **Python:** {platform.python_implementation()} {platform.python_version()} "
        f"({sys.executable})")
    out(f"- **Operating system:** {platform.platform()}")
    out(f"- **Machine:** {platform.machine()}, {platform.processor() or 'processor unknown'}")
    out(f"- **Test framework:** unittest (Python standard library)")
    out(f"- **Git:** {git('--version') or 'not available'}")
    out("")

    out("## e) Result of the validation")
    out("")
    if passed:
        out(f"The tool has **passed** the validation: all {result.testsRun} tests passed, and "
            "each test's expected results are those given in its docstring.")
    else:
        out("The tool has **failed** the validation, for these reasons:")
        out("")
        for t in failed:
            out(f"- `{t}`: {records[t]['status']}")
        if untraced:
            out("- a TOR names a test that doesn't exist (see g)")
        if result.testsRun == 0:
            out("- no test was run")
    out("")

    out("## f) Test cases and their results")
    out("")
    out("Each test's docstring gives its source and expected results (tests/SOURCES.md).")
    out("")
    out("| # | Test | Description | Result | Time (s) |")
    out("|---|---|---|---|---|")
    for n, t in enumerate(result.order, 1):
        r = records[t]
        out(f"| {n} | `{t}` | {_cell(r['description'])} | {r['status']} | {r['seconds']:.2f} |")
    out("")

    out("## g) Discrepancies between expected and actual results")
    out("")
    if not failed and not untraced:
        out("None.")
        out("")
    for t in failed:
        out(f"### `{t}`: {records[t]['status']}")
        out("")
        for detail in records[t]["details"]:
            out("```")
            out(detail.rstrip())
            out("```")
        out("")
    if untraced:
        out("### Traceability")
        out("")
        for tor, ref in untraced:
            out(f"- {tor} names `{ref}`, which matches no test.")
        out("")
    out("Known inconsistencies in the published sources are not tool discrepancies; they are "
        "listed, with how the tests handle them, in tests/SOURCES.md.")
    out("")

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output", metavar="DIR",
                        help="folder for the record (default: the 'output' folder)")
    args = parser.parse_args()

    suite = unittest.TestLoader().discover(start_dir=str(TESTS), top_level_dir=str(TESTS))
    result = RecordingResult()
    started = datetime.datetime.now().astimezone()
    print(f"Running the test suite of the MC/DC tool {__version__}...")
    suite.run(result)
    finished = datetime.datetime.now().astimezone()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / (f"validation_record_{__version__}_"
                              f"{started.strftime('%Y%m%d-%H%M%S')}.md")
    passed = write_record(path, result, started, finished)
    print(f"{result.testsRun} test(s), {'PASSED' if passed else 'FAILED'}. Record: {path}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
