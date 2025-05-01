#!/usr/bin/env python
"""
MCP Tool: Robot Test Reader
Reads .robot test files and extracts test cases, suites, and steps.
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import (
    find_robot_files,
    parse_robot_file,
    is_robot_file
)
from src.config.config import TEST_FILE_EXTENSIONS

logger = logging.getLogger('robot_tool.test_reader')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class RobotTestReaderRequest(BaseModel):
    """Request model for robot_test_reader tool."""
    file_path: Optional[str] = Field(
        None, 
        description="Path to a specific .robot file to read"
    )
    directory_path: Optional[str] = Field(
        None, 
        description="Path to a directory containing .robot files"
    )
    recursive: bool = Field(
        True, 
        description="Whether to search directories recursively"
    )

class RobotTestReaderResponse(BaseModel):
    """Response model for robot_test_reader tool."""
    files: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of parsed Robot Framework files"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def read_robot_tests(
    file_path: Optional[str] = None,
    directory_path: Optional[str] = None,
    recursive: bool = True
) -> Dict[str, Any]:
    """
    Read Robot Framework test files and extract their structure.
    
    Args:
        file_path: Path to a specific .robot file
        directory_path: Path to a directory containing .robot files
        recursive: Whether to search directories recursively
        
    Returns:
        Dictionary with parsed files and any error
    """
    result = {
        "files": [],
        "error": None
    }
    
    try:
        robot_files = []
        
        # Case 1: Specific file
        if file_path:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return {
                    "files": [],
                    "error": f"File not found: {file_path}"
                }
            
            if not is_robot_file(file_path_obj):
                return {
                    "files": [],
                    "error": f"Not a valid Robot Framework file: {file_path}"
                }
                
            robot_files = [file_path_obj]
            
        # Case 2: Directory
        elif directory_path:
            dir_path = Path(directory_path)
            if not dir_path.exists() or not dir_path.is_dir():
                return {
                    "files": [],
                    "error": f"Directory not found: {directory_path}"
                }
                
            robot_files = find_robot_files(dir_path, recursive=recursive)
            
            if not robot_files:
                return {
                    "files": [],
                    "error": f"No Robot Framework files found in {directory_path}"
                }
        else:
            return {
                "files": [],
                "error": "Either file_path or directory_path must be provided"
            }
            
        # Parse each file
        for file in robot_files:
            parsed_file = parse_robot_file(file)
            result["files"].append(parsed_file)
            
        logger.info(f"Successfully read {len(robot_files)} Robot Framework files")
        return result
        
    except Exception as e:
        logger.error(f"Error reading Robot Framework files: {e}")
        return {
            "files": result["files"],
            "error": f"Error reading Robot Framework files: {str(e)}"
        }

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_test_reader(
        file_path: Optional[str] = None, 
        directory_path: Optional[str] = None, 
        recursive: bool = True
    ) -> Dict[str, Any]:
        """
        Read Robot Framework test files and extract test cases, suites, and steps.
        
        Args:
            file_path: Path to a specific .robot file to read (optional)
            directory_path: Path to a directory containing .robot files (optional)
            recursive: Whether to search directories recursively (default: True)
            
        Returns:
            Response with parsed files and any error
        """
        logger.info(f"Received request to read Robot Framework tests. File: {file_path}, Directory: {directory_path}")
        
        try:
            result = read_robot_tests(
                file_path=file_path,
                directory_path=directory_path,
                recursive=recursive
            )
            
            # Return a dictionary instead of a Pydantic model for better compatibility
            return {
                "files": result["files"],
                "error": result["error"]
            }
            
        except Exception as e:
            error_msg = f"Error in robot_test_reader: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"files": [], "error": error_msg} 