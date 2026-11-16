"""
This is the skeletton that builds test scenario file.

LIST of available values:
    expression: the expression under test (passed as an argument on the main program)
    test_number: the current test number (starting with STARTING_TEST_NUMBER)
    input_name: the name of the boolean input
    input_value: the value of the boolean input set in a test case 
    output_name: the name of the boolean output
    output_value: the value of the boolean output set in a test case 

"""

#General variables
CODE_UNDER_TEST="Mycode_UnderTest"
VARIATION="30"
STARTING_TEST_NUMBER="1"

#Formatting
TEST_PREAMBLE=f"""
//    The following program will test the code under test "{CODE_UNDER_TEST}" with variation "{VARIATION}".
//    The expression tested is: {expression}"""

TEST_EPILOGUE=f"""
//    End of the tests.
"""

TEST_CASE_START=f"""
// Test case number {test_number}
{ printf("Test case number %i", {test_number});
"""

TEST_CASE_END=f"""}
"""


TEST_CASE_INPUT_SET=f"""{input_name} = {input_value};
"""
TEST_CASE_OUTPUT_SET=f"""{output_name} = {output_value};
"""

TEST_CASE_PROCESS=f""" mycode.process();
"""

TEST_CASE_OUTPUT_CHECK=f"""CHECK({output_name},{output_value});
"""

#Output file
OUTPUT_FILENAME=f"Test_scenario_{CODE_UNDER_TEST}_{VARIATION}.cpp" 