# NoobRobot - Robot Framework MCP Server

[![Version](https://img.shields.io/badge/Version-v0.1.0-brightgreen)](https://github.com/SuyodhanJ6/noob-robot-mcp/releases/tag/v0.1.0)
![MCP Server](https://img.shields.io/badge/MCP-Server-blue)
![Python](https://img.shields.io/badge/Python-3.11-yellow)
![Robot Framework](https://img.shields.io/badge/Robot%20Framework-6.1-red)
![License](https://img.shields.io/badge/License-MIT-green)

<p align="center">
  <img src="assets/robot-mcp-demo.gif" alt="NoobRobot MCP Server" width="600">
</p>

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
git clone https://github.com/SuyodhanJ6/noob-robot-mcp.git
cd noob-robot-mcp

# Create a virtual environment with uv and Python 3.11
uv venv --python 3.11

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies using uv
uv sync
```

## Usage

### Starting the Server

```bash
# Start the MCP server
uv run main.py
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

## Docker

### Building and Running with Docker

```bash
# Rebuild and start the containers
docker-compose down && docker-compose build --no-cache && docker-compose up
```

## Development

### Project Structure

```
noob-robot-mcp/
│
├── main.py                      # Main entry point
├── pyproject.toml               # Project configuration
├── uv.lock                      # uv dependency lock file
├── .python-version              # Python version (3.11)
│
├── src/                         # Source code
│   ├── mcp_server_sse/          # MCP Server implementation
│   │   └── server.py
│   │
│   └── mcp_tools/               # MCP Tools implementations
│       ├── robot_test_reader/
│       ├── robot_keyword_inspector/
│       ├── robot_runner/
│       └── ...
│
├── tests/                       # Test directory
├── robot_registration_test/     # Robot framework test registrations
├── logs/                        # Log files
├── output/                      # Output files
└── reports/                     # Report files
```

### Adding a New Tool

To add a new tool:

1. Create a new directory in `src/mcp_tools/`
2. Implement the tool in a `tool.py` file
3. Register the tool in `src/mcp_server_sse/server.py`

## License

MIT License
