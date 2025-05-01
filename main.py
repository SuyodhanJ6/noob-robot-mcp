#!/usr/bin/env python
"""
Main entry point for the Robot Framework MCP Server
"""

from src.mcp_server_sse.server import start_server

def main():
    """Start the Robot Framework MCP Server"""
    start_server()

if __name__ == "__main__":
    main()
