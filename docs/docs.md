Here’s a comprehensive list of all possible MCP tools for Robot Framework automation, covering a wide range of functionalities that your agent (GPT, Claude, etc.) can utilize. These tools span from reading, running, analyzing, and generating test cases, to enhancing and debugging your test scripts.

Complete MCP Tools List for Robot Framework Automation
1. robot_test_reader
Purpose: Reads .robot test files and extracts test cases, suites, and steps.

Outputs:

List of test cases and steps

Test suite structure (parent-child relationships)

Use Case: Understand the test structure and components for analysis or refactoring.

2. robot_keyword_inspector
Purpose: Inspects available keywords (built-in and custom) from the libraries.

Outputs:

List of keywords with arguments and documentation

Possible return types and usages

Use Case: Let the agent suggest the best keywords or detect potential missing keywords.

3. robot_runner
Purpose: Executes .robot test cases and returns the results.

Outputs:

Test result (PASS/FAIL)

Logs and summaries (execution status)

Use Case: Run the tests from the MCP, trigger test executions, and display results.

4. robot_log_parser
Purpose: Parses Robot Framework test logs (output.xml, log.html) to extract relevant data.

Outputs:

Step-wise pass/fail results, timestamps, and error logs

Test run summary (total passed, failed, skipped)

Use Case: Debug failed tests by extracting errors, stack traces, or issues that occurred during execution.

5. robot_test_creator
Purpose: Creates .robot test files from structured input or natural language prompts.

Outputs:

Fully formed .robot file with test cases, keywords, and steps

Use Case: Generate test cases based on user stories or specific test scenarios (e.g., for login, search, form submission).

6. robot_variable_resolver
Purpose: Resolves and handles variables used in .robot files (both internal and external variables).

Outputs:

Dictionary of variable names to their values

Variable values dynamically resolved during test execution

Use Case: Ensure proper substitution of variables or resolve dynamically passed variables in test scripts.

7. robot_library_explorer
Purpose: Explores available libraries and their keywords, including both built-in and external libraries.

Outputs:

List of all libraries and their associated keywords

Documentation for each keyword

Use Case: Suggests libraries and keywords based on test requirements.

8. robot_test_linter
Purpose: Static analysis tool to inspect .robot test files for syntax errors, warnings, and anti-patterns.

Outputs:

List of issues like incorrect keyword usage, missing arguments, or deprecated functions

Warnings for possible improvements (e.g., duplicated steps)

Use Case: Automatically detect potential problems in tests before execution, improving quality and maintainability.

9. robot_test_mapper
Purpose: Maps test cases to application components, functionality, or features.

Outputs:

A JSON or other format mapping test cases to the functionality they test

Use Case: Helps analyze test coverage and impacts across application modules. Can be used for regression testing.

10. robot_test_coverage_analyzer
Purpose: Analyzes which parts of the codebase are covered by test cases, integrating with code coverage tools like JaCoCo or Coverage.py.

Outputs:

Coverage data showing which parts of the application are not tested

Visualization of covered/uncovered lines or modules

Use Case: Identifies gaps in test coverage, ensuring critical code is tested.

11. robot_test_refactorer
Purpose: Refactors .robot test files by consolidating redundant test steps, replacing hardcoded values, or improving readability.

Outputs:

Cleaned-up .robot files with improved structure and optimized tests

Use Case: Automatically refactor and optimize existing tests to improve maintainability.

12. robot_test_data_generator
Purpose: Generates test data for different test cases (e.g., form input, search queries, etc.).

Outputs:

Randomized, realistic test data for tests (e.g., usernames, passwords, product names)

Use Case: Generate dynamic or random data for testing purposes.

13. robot_step_debugger
Purpose: Debugs individual test steps and tracks their execution.

Outputs:

Step-level debugging logs

Variables and values at each step in the test case

Use Case: Helps debug failing test steps or complex scenarios.

14. robot_report_generator
Purpose: Generates test execution reports from the log.html, output.xml, or other data sources.

Outputs:

Beautifully formatted HTML or PDF reports with test execution details

Use Case: Provides stakeholders with detailed test execution results in a user-friendly format.

15. robot_test_scheduler
Purpose: Schedules and runs Robot Framework test cases at specified intervals or times.

Outputs:

Cron-like scheduling for automated test execution

Integration with CI/CD pipelines (e.g., Jenkins, GitHub Actions)

Use Case: Automates the running of test cases on a schedule or after specific events.

16. robot_result_aggregator
Purpose: Aggregates test results from multiple test executions or across various environments.

Outputs:

Unified summary of multiple test results (e.g., in JSON, CSV, or HTML format)

Use Case: Consolidates results from different test suites or machines.

17. robot_test_dependency_checker
Purpose: Checks for missing dependencies or conflicts between libraries, variables, or keywords in the .robot files.

Outputs:

List of missing or conflicting dependencies

Use Case: Helps resolve issues before running tests, ensuring all dependencies are properly declared and available.

18. robot_automated_feedback
Purpose: Provides feedback on test case design (e.g., efficiency, readability, maintainability).

Outputs:

Suggestions for improving test case quality and design

Use Case: Continuously improves the quality of Robot Framework scripts through automated feedback.

19. robot_visualization
Purpose: Visualizes test case execution flow, keyword usage, or coverage.

Outputs:

Graphs, flowcharts, or other visualizations of test execution paths or keyword dependencies

Use Case: Helps in understanding the flow of test cases, spotting bottlenecks, or understanding keyword interdependencies.

20. robot_external_api_interaction
Purpose: Integrates with external systems via APIs and uses data for testing or test creation.

Outputs:

Interactions with external APIs (e.g., REST APIs, databases)

Use Case: Enhances testing by interacting with external services to validate responses or data.

