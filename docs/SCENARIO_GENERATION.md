# Test scenario generation

With `-gen_scen`, the tool writes its test cases to a scenario file: a C++ test fragment, or any other text format. All formatting is in a **template file** that you write. You don't need to change any Python code.

```bash
python main.py "Out = (a and b) or c" --mcdc -gen_scen input/test_setup_cpp.toml
```

```
...
Scenario written to D:\dev\python\MCDC\output\Test_scenario_Mycode_UnderTest_30.cpp (4 test case(s))
```

**Which test cases are written:**
- **With `--mcdc`** (or `--mcdc unique-cause`): the MC/DC test set.
- **Without `--mcdc`:** every row of the truth table.

They are written in the order of the printed table, i.e. in truth-table row order.

## Where the file goes

The file name comes from `OUTPUT_FILENAME` in the template. It is written to:

- **the `output/` folder next to `main.py`** (the default), whichever folder you run from;
- **the folder given with `--output-dir DIR`**;
- **the path itself**, when `OUTPUT_FILENAME` is an absolute path.

Missing folders are created. An existing file with the same name is overwritten. The file is written in UTF-8 with Unix line endings (LF).

## The template file

The template is a [TOML](https://toml.io) file with three tables. [input/test_setup_cpp.toml](../input/test_setup_cpp.toml) is a complete example.

```toml
[variables]
CODE_UNDER_TEST = "Mycode_UnderTest"
FAMILY = "30"

[settings]
STARTING_TEST_NUMBER = 1
TRUE = "TRUE"
FALSE = "FALSE"
OUTPUT_FILENAME = "Test_scenario_${CODE_UNDER_TEST}_${FAMILY}.cpp"

[format]
TEST_CASE_START = '''
// Test case number ${test_number}
{ printf("Test case number %i", ${test_number});
'''
TEST_CASE_INPUT_SET = '''${input_name} = ${input_value};
'''
# ... the other texts
```

### `[variables]`: your own values

Any name you like, with a text or a number as its value. Each one can be used as `${NAME}` in every text and in `OUTPUT_FILENAME`. Typical uses are the code under test's name (`CODE_UNDER_TEST`) and a family or variation number added to the file name for tracking (`FAMILY`).

Names are letters, digits and `_`, not starting with a digit. They can't reuse a placeholder name of the tool (see below).

### `[settings]`

| Key | Meaning | Default |
|---|---|---|
| `STARTING_TEST_NUMBER` | number of the first test case. Use e.g. `25` to append the scenario to an existing one that ends at test 24 | `1` |
| `TRUE` | how a True value is written, e.g. `"TRUE"`, `"true"`, `"1"` | `"1"` |
| `FALSE` | how a False value is written, e.g. `"FALSE"`, `"false"`, `"0"` | `"0"` |
| `NOT_EVALUATED` | value written for an input that the test doesn't evaluate (short-circuit forms; `X` in the tool's tables). Any value works, since the input isn't evaluated | the `FALSE` text |
| `OUTPUT_FILENAME` | name of the generated file; can use `[variables]`, `${expression}`, `${output_name}` and `${tool_version}` | required |

### `[format]`: the texts

| Key | Written |
|---|---|
| `TEST_PREAMBLE` | once, at the beginning |
| `TEST_CASE_START` | at the start of each test case |
| `TEST_CASE_INPUT_SET` | once per input, in the table's column order: how an input is set |
| `TEST_CASE_OUTPUT_SET` | how the output is preset before processing |
| `TEST_CASE_PROCESS` | how the code under test is run |
| `TEST_CASE_OUTPUT_CHECK` | how the output is checked |
| `TEST_CASE_END` | at the end of each test case |
| `TEST_EPILOGUE` | once, at the very end |

Every text is optional: a missing one writes nothing. The file is assembled in this order:

```
TEST_PREAMBLE
for each test case:
    TEST_CASE_START
    TEST_CASE_INPUT_SET        (once per input)
    TEST_CASE_OUTPUT_SET
    TEST_CASE_PROCESS
    TEST_CASE_OUTPUT_CHECK
    TEST_CASE_END
TEST_EPILOGUE
```

Nothing is added between the texts, not even a line break, so end each text with the line breaks you want.

## Placeholders

A placeholder is written `${name}` and replaced by its value.

| Placeholder | Value | Can be used in |
|---|---|---|
| `${NAME}` from `[variables]` | as written in `[variables]` | everywhere |
| `${expression}` | the expression as you passed it to `main.py`, on one line | everywhere |
| `${output_name}` | the output name (`Out` in `Out = …`) | everywhere |
| `${tool_version}` | the tool version, as `main.py --version` prints it | everywhere |
| `${tool_command}` | the `main.py` command line that wrote the scenario, with the arguments that contain spaces or quotes between `"` | everywhere but `OUTPUT_FILENAME` |
| `${test_number}` | the test case number, from `STARTING_TEST_NUMBER` | all `TEST_CASE_*` texts |
| `${row}` | the test case's `#` in the tool's truth table, to trace the scenario back to the table | all `TEST_CASE_*` texts |
| `${output_value}` | the expected output value | all `TEST_CASE_*` texts |
| `${output_inverse}` | the inverse of the expected value | all `TEST_CASE_*` texts |
| `${input_name}`, `${input_value}` | one input and its value | `TEST_CASE_INPUT_SET` only |

Values are written with the `TRUE` / `FALSE` texts. With short-circuit forms (`and then`, `or else`, `--short-circuit`), an input that the test doesn't evaluate gets the `NOT_EVALUATED` text.

`${output_inverse}` is meant for `TEST_CASE_OUTPUT_SET`. Presetting the output to the opposite of the expected value makes the check fail if the code under test doesn't write its output at all.

`${tool_version}` and `${tool_command}` record in the scenario which version of the tool produced it, and how. IEC 61508-3 7.4.4.15 asks for this record for every item a tool generates (see [IEC_61508_ADEQUACY.md](IEC_61508_ADEQUACY.md)). Put them in a comment of `TEST_PREAMBLE`, as both example templates do.

## Writing texts: TOML rules that matter

- **Literal text:** put the text between `'''` and `'''`. Everything inside is kept exactly; `{`, `}`, `"`, `%` and `\` need no escaping.
- **Leading line break:** a line break right after the opening `'''` is ignored. To start a text with an empty line, leave one more empty line:

  ```toml
  TEST_CASE_START = '''

  // Test case number ${test_number}
  '''
  ```
  writes an empty line, then the comment line.
- **Literal `$`:** write `$$`. A `$` followed by anything other than `$`, `{name}` or a name is an error.
- **Comments:** lines starting with `#` outside the `'''` texts are comments.
- **Short texts:** a text on one line can use single quotes: `TEST_CASE_PROCESS = 'mycode.process();'` (no line break at the end).

## Error messages

The template is checked completely before the analysis starts, and nothing is written if it contains an error. The message names the table and key:

```
main.py: error: scenario template input/bad.toml: [format] TEST_PREAMBLE: ${input_name} can only be used in TEST_CASE_INPUT_SET
```

**Detected errors:**
- **Placeholders:**
  - an unknown placeholder (misspelled, or not defined in `[variables]`);
  - a placeholder used outside its scope, e.g. `${test_number}` in `OUTPUT_FILENAME`;
  - an invalid `$`, with the line inside the text.
- **Keys:**
  - an unknown key in `[settings]` or `[format]` (e.g. `TEST_CASE_BEGIN`), or an unknown table;
  - `OUTPUT_FILENAME` missing.
- **Values:**
  - `STARTING_TEST_NUMBER` not a whole number;
  - a `[variables]` name that is invalid or reuses a placeholder name of the tool;
  - a text that is not a string.
- **File:** not valid TOML (the message gives the line and column), or can't be read.

## Complete example

Template: [input/test_setup_cpp.toml](../input/test_setup_cpp.toml). Command:

```bash
python main.py "Out = (a and b) or c" --mcdc -gen_scen input/test_setup_cpp.toml
```

The MC/DC set is rows #2, #3, #5 and #7. Generated `output/Test_scenario_Mycode_UnderTest_30.cpp` (beginning):

```cpp
//    The following program will test the code under test "Mycode_UnderTest" with family "30".
//    The expression tested is: Out = (a and b) or c
//    Generated by the MC/DC tool 1.0.1: main.py "Out = (a and b) or c" --mcdc -gen_scen input/test_setup_cpp.toml

// Test case number 1 (truth table row #2)
{ printf("Test case number %i", 1);
a = FALSE;
b = FALSE;
c = TRUE;
Out = FALSE;
mycode.process();
CHECK(Out,TRUE);
}

// Test case number 2 (truth table row #3)
{ printf("Test case number %i", 2);
a = FALSE;
b = TRUE;
c = FALSE;
Out = TRUE;
mycode.process();
CHECK(Out,FALSE);
}
...

//    End of the tests.
```

## Tips

- **One template per target:** keep one template per test framework or code under test, and choose it on the command line.
- **Appending to an existing scenario:** set `STARTING_TEST_NUMBER` to the next free number, and give `OUTPUT_FILENAME` a different name (e.g. with `FAMILY`), so the existing file isn't overwritten.
- **Other languages:** the template is plain text, so the same mechanism works for C, Ada, Python, a CSV for a test bench, and so on.

## Limits

- **One output:** the scenario sets every input and checks the one output of the decision.
- **Boolean values only:** the only per-value choice is the `TRUE` / `FALSE` text.
- **No warning on overwrite:** an existing file with the same name is replaced.
- **Verification:** the generator is checked by `tests/test_scenario.py` (generated text, template errors, command line). Those are tool requirement tests: the MC/DC content of the test cases is verified by the qualification suite (see [MCDC_IMPLEMENTATION.md](MCDC_IMPLEMENTATION.md)).
