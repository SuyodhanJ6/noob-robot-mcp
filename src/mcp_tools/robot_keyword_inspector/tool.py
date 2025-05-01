#!/usr/bin/env python
"""
MCP Tool: Robot Keyword Inspector
Inspects available keywords from Robot Framework libraries and returns their documentation.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import (
    get_available_robot_libraries,
    get_library_keywords
)

logger = logging.getLogger('robot_tool.keyword_inspector')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class KeywordInspectorRequest(BaseModel):
    """Request model for robot_keyword_inspector tool."""
    library_name: Optional[str] = Field(
        None,
        description="Name of the library to inspect. If not provided, lists all available libraries."
    )

class KeywordInspectorResponse(BaseModel):
    """Response model for robot_keyword_inspector tool."""
    libraries: List[str] = Field(
        default_factory=list,
        description="List of available libraries (if no library_name provided)"
    )
    keywords: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of keywords with documentation (if library_name provided)"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def inspect_keywords(
    library_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Inspect available keywords from Robot Framework libraries.
    
    Args:
        library_name: Name of the library to inspect. If not provided, 
                      lists all available libraries.
                      
    Returns:
        Dictionary with libraries/keywords and any error
    """
    result = {
        "libraries": [],
        "keywords": [],
        "error": None
    }
    
    try:
        # Case 1: List all libraries
        if not library_name:
            libraries = get_available_robot_libraries()
            result["libraries"] = libraries
            
            if not libraries:
                result["error"] = "No Robot Framework libraries found"
                
            logger.info(f"Found {len(libraries)} Robot Framework libraries")
            return result
            
        # Case 2: Get keywords from a specific library
        keywords = get_library_keywords(library_name)
        result["keywords"] = keywords
        
        if not keywords:
            result["error"] = f"No keywords found in library: {library_name}"
            
        logger.info(f"Found {len(keywords)} keywords in library: {library_name}")
        return result
        
    except Exception as e:
        error_msg = f"Error inspecting keywords: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "libraries": result["libraries"],
            "keywords": result["keywords"],
            "error": error_msg
        }

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_keyword_inspector(library_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Inspect available keywords from Robot Framework libraries.
        
        Args:
            library_name: Name of the library to inspect. If not provided, 
                          lists all available libraries.
            
        Returns:
            Response with libraries/keywords and any error
        """
        logger.info(f"Received request to inspect keywords for library: {library_name}")
        
        try:
            result = inspect_keywords(library_name=library_name)
            
            # Return a dictionary instead of a Pydantic model for better compatibility
            return {
                "libraries": result["libraries"],
                "keywords": result["keywords"],
                "error": result["error"]
            }
            
        except Exception as e:
            error_msg = f"Error in robot_keyword_inspector: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "libraries": [],
                "keywords": [],
                "error": error_msg
            } 