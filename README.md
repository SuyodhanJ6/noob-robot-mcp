# NoobRobot - Robot Framework MCP Server

A Machine Control Protocol (MCP) server implementation for Robot Framework automation, providing 20 tools to enhance testing with Robot Framework.

## Overview

NoobRobot exposes Robot Framework functionality through the MCP protocol, allowing AI agents and other clients to interact with Robot Framework through a standardized API. The server uses Server-Sent Events (SSE) for real-time communication.

## Features

This MCP server implements 20 tools for working with Robot Framework:

1. **robot_test_reader** - Reads .robot test files and extracts test cases, suites, and steps
2. **robot_keyword_inspector** - Inspects available keywords from libraries
3. **robot_runner** - Executes .robot test cases and returns the results
4. **robot_log_parser** - Parses Robot Framework test logs
5. **robot_test_creator** - Creates .robot test files from structured input
6. **robot_variable_resolver** - Resolves variables used in .robot files
7. **robot_library_explorer** - Explores available libraries and their keywords
8. **robot_test_linter** - Static analysis tool for .robot files
9. **robot_test_mapper** - Maps test cases to application components
10. **robot_test_coverage_analyzer** - Analyzes which parts of the codebase are covered by tests
11. **robot_test_refactorer** - Refactors .robot test files
12. **robot_test_data_generator** - Generates test data for different test cases
13. **robot_step_debugger** - Debugs individual test steps
14. **robot_report_generator** - Generates test execution reports
15. **robot_test_scheduler** - Schedules and runs test cases
16. **robot_result_aggregator** - Aggregates test results
17. **robot_test_dependency_checker** - Checks for missing dependencies
18. **robot_automated_feedback** - Provides feedback on test case design
19. **robot_visualization** - Visualizes test case execution flow
20. **robot_external_api_interaction** - Integrates with external systems via APIs

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/noobrobot.git
cd noobrobot

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

## Configuration

NoobRobot can be configured through environment variables or a `.env` file:

```
# Server settings
MCP_HOST=localhost
MCP_PORT=3007

# Robot Framework settings
ROBOT_OUTPUT_DIR=./output
ROBOT_REPORT_DIR=./reports

# Default settings
DEFAULT_TIMEOUT=30
MAX_RESULTS=100
```

## Usage

### Starting the Server

```bash
# Start the MCP server
python -m main
```

This will start the MCP server at `http://localhost:3007/sse` (by default).

### Connecting to the Server

You can connect to the MCP server using any MCP client. For example, using the MCP JavaScript client:

```javascript
import { MCP } from 'mcp-client';

const mcp = new MCP('http://localhost:3007/sse');

// Use the robot_test_reader tool
const result = await mcp.call('robot_test_reader', {
  directory_path: './tests',
  recursive: true
});

console.log(result.files);
```

## Development

### Project Structure

```
noobRobot/
│
├── main.py                      # Main entry point
├── pyproject.toml               # Project configuration
│
└── src/
    ├── mcp_server_sse/          # MCP Server implementation
    │   └── server.py
    │
    ├── utils/                   # Utility functions
    │   └── helpers.py
    │
    ├── config/                  # Configuration
    │   └── config.py
    │
    └── mcp_tools/               # MCP Tools implementations
        ├── robot_test_reader/
        ├── robot_keyword_inspector/
        ├── robot_runner/
        └── ...
```

### Adding a New Tool

To add a new tool:

1. Create a new directory in `src/mcp_tools/`
2. Implement the tool in a `tool.py` file
3. Register the tool in `src/mcp_server_sse/server.py`

## License

MIT License
