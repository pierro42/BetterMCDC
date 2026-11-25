# -*- coding: utf-8 -*-
"""
Test scenario generation from a user template (TOML file).

The template has three tables:
  [variables]  user values, usable as ${NAME} in every text
  [settings]   STARTING_TEST_NUMBER, TRUE, FALSE, NOT_EVALUATED, OUTPUT_FILENAME,
               LIST_OUTPUT_FILENAME (optional: the test list file)
  [format]     the texts written to the scenario (all optional):
               TEST_PREAMBLE, TEST_CASE_START, TEST_CASE_INPUT_SET,
               TEST_CASE_OUTPUT_SET, TEST_CASE_PROCESS,
               TEST_CASE_OUTPUT_CHECK, TEST_CASE_END, TEST_EPILOGUE;
               and to the test list (only with LIST_OUTPUT_FILENAME):
               TEST_LIST_PREAMBLE, TEST_LIST_CASE, TEST_LIST_EPILOGUE

Placeholders are ${name} (Python string.Template); $$ is a literal $.
${tool_version} and ${tool_command} record the tool version and the
command line in the scenario (IEC 61508-3 7.4.4.15).
The scenario is written in this order:

  TEST_PREAMBLE
  for each test case:
      TEST_CASE_START
      TEST_CASE_INPUT_SET      once per input, in table order
      TEST_CASE_OUTPUT_SET
      TEST_CASE_PROCESS
      TEST_CASE_OUTPUT_CHECK
      TEST_CASE_END
  TEST_EPILOGUE

and the test list, a second file that can e.g. call each test case:

  TEST_LIST_PREAMBLE
  TEST_LIST_CASE               once per test case, same order and numbers
  TEST_LIST_EPILOGUE
"""

import string
import tomllib
from typing import Dict, NamedTuple, Optional

from .tree import executed_inputs
from .version import __version__

# Placeholders the tool provides, and where they can be used
_GLOBAL = {"expression", "output_name", "tool_version", "tool_command"}
# ${tool_command} has quotes: not for a file name; ${expression} is made safe (_filename)
_FILENAME = _GLOBAL - {"tool_command"}
_PER_TEST = _GLOBAL | {"test_number", "row", "output_value", "output_inverse"}
_INPUT = _PER_TEST | {"input_name", "input_value"}
FORMAT_KEYS = {
    "TEST_PREAMBLE": _GLOBAL,
    "TEST_CASE_START": _PER_TEST,
    "TEST_CASE_INPUT_SET": _INPUT,
    "TEST_CASE_OUTPUT_SET": _PER_TEST,
    "TEST_CASE_PROCESS": _PER_TEST,
    "TEST_CASE_OUTPUT_CHECK": _PER_TEST,
    "TEST_CASE_END": _PER_TEST,
    "TEST_EPILOGUE": _GLOBAL,
    "TEST_LIST_PREAMBLE": _GLOBAL,
    "TEST_LIST_CASE": _PER_TEST,
    "TEST_LIST_EPILOGUE": _GLOBAL,
}
LIST_KEYS = ("TEST_LIST_PREAMBLE", "TEST_LIST_CASE", "TEST_LIST_EPILOGUE")
SETTING_KEYS = ("STARTING_TEST_NUMBER", "TRUE", "FALSE", "NOT_EVALUATED", "OUTPUT_FILENAME",
                "LIST_OUTPUT_FILENAME")
_BUILTIN = _INPUT


class ScenarioTemplate(NamedTuple):
    variables: Dict[str, str]                # [variables]
    start: int                               # STARTING_TEST_NUMBER
    true: str                                # text written for True
    false: str                               # text written for False
    filename: string.Template                # OUTPUT_FILENAME
    texts: Dict[str, string.Template]        # [format], every key present
    not_evaluated: str = "0"                 # text for an input the test doesn't evaluate
    list_filename: Optional[string.Template] = None   # LIST_OUTPUT_FILENAME, if given


def _table(data, name):
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"'{name}' must be a table: [{name}]")
    return value


def _text(value, where):
    """A scalar template value as text (numbers allowed, e.g. FAMILY = 30)."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"{where} must be a text or a number")
    return str(value)


def _compile(text, where, allowed):
    """string.Template for `text`, checking every placeholder is allowed."""
    template = string.Template(text)
    for match in template.pattern.finditer(text):
        if match.group("invalid") is not None:
            line = text.count("\n", 0, match.start("invalid")) + 1
            raise ValueError(f"{where}, line {line}: invalid '$' (write $$ for a literal $, "
                             f"${{name}} for a placeholder)")
    for name in template.get_identifiers():
        if name in allowed:
            continue
        if name in _BUILTIN:
            keys = [k for k, scope in FORMAT_KEYS.items() if name in scope]
            raise ValueError(f"{where}: ${{{name}}} can only be used in {', '.join(keys)}")
        raise ValueError(f"{where}: unknown placeholder ${{{name}}} (not a [variables] "
                         f"name nor one of: {', '.join(sorted(_BUILTIN))})")
    return template


def load_template(path):
    """Read and check a scenario template file. Raises ValueError (or
    OSError if the file can't be read) with a readable message."""
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"not a valid TOML file: {e}") from None
    unknown = set(data) - {"variables", "settings", "format"}
    if unknown:
        raise ValueError(f"unknown table(s): {', '.join(sorted(unknown))} "
                         f"(expected [variables], [settings], [format])")
    variables, settings, texts = (_table(data, name) for name in ("variables", "settings", "format"))

    for name in variables:
        if not name.isidentifier() or not name.isascii():
            raise ValueError(f"[variables] {name}: a variable name must be letters, "
                             f"digits and _ (not starting with a digit)")
        if name in _BUILTIN:
            raise ValueError(f"[variables] {name}: this name is a placeholder of the tool")
    variables = {name: _text(value, f"[variables] {name}") for name, value in variables.items()}

    unknown = [k for k in settings if k not in SETTING_KEYS]
    if unknown:
        raise ValueError(f"[settings] unknown key(s): {', '.join(unknown)} "
                         f"(expected: {', '.join(SETTING_KEYS)})")
    start = settings.get("STARTING_TEST_NUMBER", 1)
    # not negative: ${test_number} is often part of a name, e.g. Test_..._${test_number}
    if isinstance(start, bool) or not isinstance(start, int) or start < 0:
        raise ValueError("[settings] STARTING_TEST_NUMBER must be a whole number, 0 or "
                         "more, e.g. 1")
    true = _text(settings.get("TRUE", "1"), "[settings] TRUE")
    false = _text(settings.get("FALSE", "0"), "[settings] FALSE")
    # an input that a test doesn't evaluate (short-circuit forms): any value
    # works; by default the FALSE text, as the tool numbers it (tree.canonical)
    not_evaluated = _text(settings.get("NOT_EVALUATED", false), "[settings] NOT_EVALUATED")
    if "OUTPUT_FILENAME" not in settings:
        raise ValueError("[settings] OUTPUT_FILENAME is missing")
    allowed = set(variables)
    filename = _compile(_text(settings["OUTPUT_FILENAME"], "[settings] OUTPUT_FILENAME"),
                        "[settings] OUTPUT_FILENAME", allowed | _FILENAME)

    unknown = [k for k in texts if k not in FORMAT_KEYS]
    if unknown:
        raise ValueError(f"[format] unknown key(s): {', '.join(unknown)} "
                         f"(expected: {', '.join(FORMAT_KEYS)})")
    compiled = {}
    for key, scope in FORMAT_KEYS.items():
        value = texts.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"[format] {key} must be a text, e.g. {key} = '''...'''")
        compiled[key] = _compile(value, f"[format] {key}", allowed | scope)

    # the test list is optional; its texts alone would be silently ignored
    list_filename = None
    if "LIST_OUTPUT_FILENAME" in settings:
        list_filename = _compile(_text(settings["LIST_OUTPUT_FILENAME"],
                                       "[settings] LIST_OUTPUT_FILENAME"),
                                 "[settings] LIST_OUTPUT_FILENAME", allowed | _FILENAME)
    else:
        given = [key for key in LIST_KEYS if key in texts]
        if given:
            raise ValueError(f"[format] {', '.join(given)}: the test list needs its file "
                             f"name, [settings] LIST_OUTPUT_FILENAME")
    return ScenarioTemplate(variables, start, true, false, filename, compiled, not_evaluated,
                            list_filename)


def _expression_text(expression):
    return " ".join(expression.splitlines()).strip()


def _common_values(template, decision, expression, command):
    """Placeholders that have the same value in every text."""
    return dict(template.variables, expression=_expression_text(expression),
                output_name=decision.output, tool_version=__version__, tool_command=command)


def _test_cases(template, common, tests):
    """(inputs, placeholders) of each test case, numbered from
    STARTING_TEST_NUMBER: the scenario and the test list use the same
    numbers."""
    value = lambda v: template.true if v else template.false
    for n, (row, inputs, result) in enumerate(tests):
        yield inputs, dict(common, test_number=str(template.start + n), row=str(row + 1),
                           output_value=value(result), output_inverse=value(not result))


def render_scenario(template, decision, tests, expression, command=""):
    """Scenario text for `tests`, a list of (row, inputs, result) as given
    to print_table (row is 0-based; ${row} is the 1-based '#' of the tables).
    `expression` is the expression as the user typed it, `command` the
    command line that produced the scenario (${tool_command})."""
    value = lambda v: template.true if v else template.false
    common = _common_values(template, decision, expression, command)
    out = [template.texts["TEST_PREAMBLE"].substitute(common)]
    for inputs, case in _test_cases(template, common, tests):
        out.append(template.texts["TEST_CASE_START"].substitute(case))
        evaluated = executed_inputs(decision, inputs)
        for name, v, ex in zip(decision.names, inputs, evaluated):
            out.append(template.texts["TEST_CASE_INPUT_SET"].substitute(
                case, input_name=name,
                input_value=value(v) if ex else template.not_evaluated))
        for key in ("TEST_CASE_OUTPUT_SET", "TEST_CASE_PROCESS",
                    "TEST_CASE_OUTPUT_CHECK", "TEST_CASE_END"):
            out.append(template.texts[key].substitute(case))
    out.append(template.texts["TEST_EPILOGUE"].substitute(common))
    return "".join(out)


def render_test_list(template, decision, tests, expression, command=""):
    """Test list text for the same `tests` as render_scenario:
    TEST_LIST_PREAMBLE, TEST_LIST_CASE once per test case (same order and
    ${test_number} as the scenario), TEST_LIST_EPILOGUE."""
    common = _common_values(template, decision, expression, command)
    out = [template.texts["TEST_LIST_PREAMBLE"].substitute(common)]
    for _, case in _test_cases(template, common, tests):
        out.append(template.texts["TEST_LIST_CASE"].substitute(case))
    out.append(template.texts["TEST_LIST_EPILOGUE"].substitute(common))
    return "".join(out)


# characters that a file name can't contain on Windows (|| and ! appear in
# expressions); ${expression} gets "_" instead of them in a file name
_NOT_IN_FILENAME = str.maketrans({c: "_" for c in '\\/:*?"<>|'})


def _filename(name, template, decision, expression):
    return name.substitute(template.variables,
                           expression=_expression_text(expression).translate(_NOT_IN_FILENAME),
                           output_name=decision.output, tool_version=__version__)


def output_filename(template, decision, expression):
    """OUTPUT_FILENAME with its placeholders replaced."""
    return _filename(template.filename, template, decision, expression)


def list_output_filename(template, decision, expression):
    """LIST_OUTPUT_FILENAME with its placeholders replaced, or None when
    the template has no test list."""
    if template.list_filename is None:
        return None
    return _filename(template.list_filename, template, decision, expression)
