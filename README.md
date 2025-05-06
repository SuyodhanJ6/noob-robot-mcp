# NoobRobot - Robot Framework MCP Server

[![Version](https://img.shields.io/badge/Version-v0.2.1-brightgreen)](https://github.com/SuyodhanJ6/noob-robot-mcp/releases/tag/v0.2.1)
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

This MCP server implements a comprehensive set of browser automation and form handling tools:

### Core Form Automation
1. **robot_form_automator** - Creates and runs Robot Framework tests for web form automation
2. **robot_form_locator** - Extracts form elements and their locators from web pages
3. **robot_form_success_detector** - Detects successful form submissions and generates tests

### Browser Automation
4. **robot_browser_navigate** - Navigates to URLs with optional authentication support
5. **robot_browser_click** - Performs click operations on web elements
6. **robot_browser_type** - Types text into form fields and input elements
7. **robot_browser_select_option** - Selects options from dropdown menus
8. **robot_browser_screenshot** - Takes screenshots of web pages
9. **robot_browser_wait** - Waits for elements or fixed time periods
10. **robot_browser_tab_new** - Opens new browser tabs
11. **robot_browser_tab_select** - Selects and switches between browser tabs
12. **robot_browser_close** - Closes browser sessions

### Advanced Element Location
13. **robot_auto_locator** - Comprehensive locator finder for all elements
14. **robot_page_snapshot** - Takes page snapshots for element identification
15. **robot_dropdown_handler** - Specialized tool for dropdown element handling

### Authentication Support
16. **Auth Manager** - Central authentication management for maintaining login sessions across tools

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
