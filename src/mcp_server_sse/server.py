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

# Import the AuthManager
from src.utils.auth_manager import AuthManager

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger('robot_mcp_server')

# Create MCP server
mcp = FastMCP("RobotFrameworkTools")

# Define tool modules to import
# Only including essential tools for advanced Robot script generation with agent workflow
TOOLS = [
    # Core automation tools
    "robot_form_automator",       # Form automation tool
    "robot_form_locator",         # Form locator tool
    
    # Advanced locator tool - keeping only the most powerful one
    "robot_auto_locator",         # Comprehensive locator finder for all elements
    
    "robot_page_snapshot",        # Screenshot tool for element identification
    "robot_dropdown_handler",     # Dropdown handler tool
    "robot_form_success_detector", # Form success detector tool
    # "robot_auth_handler",         # Authentication handler for login portals
    # "robot_browser_install",      # Browser and driver installation tool
    
    # Essential browser automation tools
    "robot_browser_navigate",      # Navigate to a URL
    "robot_browser_click",         # Perform click on a web page
    "robot_browser_type",          # Type text into editable element
    "robot_browser_select_option", # Select an option in a dropdown
    "robot_browser_screenshot",    # Take a screenshot of the current page
    "robot_browser_wait",          # Wait for a specified time in seconds
    
    # Optional - include if needed
    "robot_browser_tab_new",       # Open a new tab
    "robot_browser_tab_select",    # Select a tab by index
    "robot_browser_close",         # Close the page
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
    # Initialize the AuthManager
    logger.info("Initializing the AuthManager...")
    auth_manager = AuthManager.get_instance()
    logger.info("AuthManager initialized")
    
    # Register all tools
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