#!/usr/bin/env python
"""
Robot Framework MCP Server - Provides Robot Framework automation tools via MCP protocol.
"""

import logging
import uvicorn
import importlib
import os
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Import configuration
from src.config.config import (
    LOGGING_CONFIG, 
    MCP_HOST, 
    MCP_PORT, 
    ALLOWED_ORIGINS
)

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger('robot_mcp_server')

# Create MCP server
mcp = FastMCP("RobotFrameworkTools")

# Define tool modules to import
# Only including essential tools for advanced Robot script generation with agent workflow
TOOLS = [
    # Agent orchestration tool
    "robot_agent_prompt",         # Main orchestration tool for agent workflows
    
    # Core automation tools
    "robot_form_automator",        # Form automation tool
    "robot_form_locator",          # Form locator tool
    "robot_xpath_locator",         # XPath locator tool
    "robot_smart_locator",         # Advanced smart locator with fallback strategies
    "robot_page_snapshot",         # Screenshot tool for element identification
    "robot_dropdown_handler",      # Dropdown handler tool
    "robot_form_success_detector", # Form success detector tool
    "robot_runner",                # Tool for running Robot Framework tests
    
    # Agent workflow tools
    "robot_test_reader",           # For reading existing test files
    "robot_library_explorer",      # For exploring available Robot Framework libraries
    "robot_visualization",         # For visualizing test execution
    
    # Optional tools that might be useful
    "robot_log_parser",            # For parsing execution logs
    "robot_test_data_generator",   # For generating test data
    
    # Commented out tools that aren't essential for the agent workflow
    # "robot_keyword_inspector",
    # "robot_variable_resolver",
    # "robot_test_linter",
    # "robot_test_mapper",
    # "robot_test_coverage_analyzer",
    # "robot_test_refactorer",
    # "robot_step_debugger",
    # "robot_report_generator",
    # "robot_test_scheduler",
    # "robot_result_aggregator",
    # "robot_test_dependency_checker",
    # "robot_automated_feedback",
    # "robot_external_api_interaction",
    # "robot_test_creator",
]

# Import existing tools
tool_registry = {}
for tool_name in TOOLS:
    tool_module_path = f"src.mcp_tools.{tool_name}.tool"
    try:
        # Try to import the module
        tool_module = importlib.import_module(tool_module_path)
        tool_registry[tool_name] = tool_module.register_tool
        logger.info(f"Successfully imported tool: {tool_name}")
    except (ImportError, ModuleNotFoundError):
        # If the tool hasn't been implemented yet, log it
        logger.warning(f"Tool not yet implemented: {tool_name}")
        tool_registry[tool_name] = None

def register_all_tools():
    """Register all MCP tools with the server."""
    logger.info("Registering all MCP tools...")
    
    # Register each tool that exists
    for tool_name, register_func in tool_registry.items():
        if register_func:
            logger.info(f"Registering tool: {tool_name}")
            register_func(mcp)
        else:
            logger.info(f"Skipping registration of unimplemented tool: {tool_name}")
    
    logger.info("Tool registration complete")

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create and configure the Starlette application.
    
    Args:
        mcp_server: The MCP server instance
        debug: Whether to enable debug mode
        
    Returns:
        Configured Starlette application
    """
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]
    
    # Create SSE transport with messages endpoint
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        """Handle SSE connection requests."""
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
    
    # Define routes for the application
    routes = [
        Route("/sse", endpoint=handle_sse),
    ]
    
    # Create a Starlette app
    app = Starlette(
        debug=debug,
        routes=routes,
        middleware=middleware,
    )
    
    # Mount the messages endpoint to handle POST requests
    app.routes.append(
        Mount("/messages", app=sse.handle_post_message)
    )
    
    return app

def start_server():
    """Start the MCP server."""
    register_all_tools()
    
    # Get the actual MCP server instance from FastMCP
    mcp_server = mcp._mcp_server
    
    app = create_starlette_app(mcp_server, debug=True)
    
    logger.info(f"Starting Robot Framework MCP server at {MCP_HOST}:{MCP_PORT}")
    uvicorn.run(
        app,
        host=MCP_HOST,
        port=MCP_PORT,
        log_level="info",
    )

if __name__ == "__main__":
    start_server() 