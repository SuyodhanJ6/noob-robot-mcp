#!/usr/bin/env python
"""
MCP Tool: Robot Library Explorer
Explores available libraries and their keywords in Robot Framework.
"""

import logging
import importlib
import pkgutil
import inspect
import json
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import (
    get_available_robot_libraries,
    get_library_keywords
)

logger = logging.getLogger('robot_tool.library_explorer')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class LibraryExplorerRequest(BaseModel):
    """Request model for robot_library_explorer tool."""
    library_name: Optional[str] = Field(
        None,
        description="Name of a specific library to explore"
    )
    keyword_pattern: Optional[str] = Field(
        None,
        description="Pattern to filter keywords by name"
    )
    include_standard_libraries: bool = Field(
        True,
        description="Whether to include Robot Framework's standard libraries"
    )
    include_installed_libraries: bool = Field(
        True,
        description="Whether to include installed third-party libraries"
    )

class LibraryInfo(BaseModel):
    """Model for library information."""
    name: str = Field(..., description="Name of the library")
    version: Optional[str] = Field(None, description="Version of the library")
    path: Optional[str] = Field(None, description="Path to the library")
    doc: Optional[str] = Field(None, description="Documentation for the library")
    keywords_count: int = Field(0, description="Number of keywords in the library")
    type: str = Field("unknown", description="Type of library (standard, installed, or custom)")

class KeywordInfo(BaseModel):
    """Model for keyword information."""
    name: str = Field(..., description="Name of the keyword")
    library: str = Field(..., description="Library the keyword belongs to")
    arguments: List[str] = Field(default_factory=list, description="Arguments for the keyword")
    doc: Optional[str] = Field(None, description="Documentation for the keyword")
    tags: List[str] = Field(default_factory=list, description="Tags for the keyword")
    return_type: Optional[str] = Field(None, description="Return type of the keyword")

class LibraryExplorerResponse(BaseModel):
    """Response model for robot_library_explorer tool."""
    libraries: List[dict] = Field(
        default_factory=list,
        description="List of available libraries"
    )
    keywords: List[dict] = Field(
        default_factory=list,
        description="List of keywords in the specified library"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def explore_libraries(
    library_name: Optional[str] = None,
    keyword_pattern: Optional[str] = None,
    include_standard_libraries: bool = True,
    include_installed_libraries: bool = True
) -> Dict[str, Any]:
    """
    Explore Robot Framework libraries and their keywords.
    
    Args:
        library_name: Name of a specific library to explore
        keyword_pattern: Pattern to filter keywords by name
        include_standard_libraries: Whether to include standard libraries
        include_installed_libraries: Whether to include installed libraries
        
    Returns:
        Dictionary with libraries, keywords, and any error
    """
    result = {
        "libraries": [],
        "keywords": [],
        "error": None
    }
    
    try:
        # Get available libraries
        available_libraries = get_available_robot_libraries()
        
        # Filter libraries by type
        filtered_libraries = []
        for lib in available_libraries:
            lib_type = lib.get("type", "").lower()
            
            if lib_type == "standard" and not include_standard_libraries:
                continue
                
            if lib_type == "installed" and not include_installed_libraries:
                continue
                
            filtered_libraries.append(lib)
        
        # Process specific library if requested
        if library_name:
            # Check if library exists
            if not any(lib.get("name", "").lower() == library_name.lower() for lib in filtered_libraries):
                return {
                    "libraries": filtered_libraries,
                    "keywords": [],
                    "error": f"Library not found: {library_name}"
                }
                
            # Get keywords for the specified library
            keywords = get_library_keywords(library_name)
            
            # Filter keywords by pattern if specified
            if keyword_pattern:
                keywords = [kw for kw in keywords if keyword_pattern.lower() in kw.get("name", "").lower()]
                
            result["keywords"] = keywords
        
        result["libraries"] = filtered_libraries
        logger.info(f"Found {len(filtered_libraries)} libraries and {len(result['keywords'])} keywords")
        return result
        
    except Exception as e:
        error_msg = f"Error exploring Robot Framework libraries: {str(e)}"
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
    """Register the robot_library_explorer tool with the MCP server."""
    
    @mcp.tool()
    async def robot_library_explorer(
        library_name: Optional[str] = None,
        keyword_pattern: Optional[str] = None,
        include_standard_libraries: bool = True,
        include_installed_libraries: bool = True
    ) -> Dict[str, Any]:
        """
        Explore Robot Framework libraries and their keywords.
        
        Args:
            library_name: Name of a specific library to explore
            keyword_pattern: Pattern to filter keywords by name
            include_standard_libraries: Whether to include standard libraries
            include_installed_libraries: Whether to include installed libraries
            
        Returns:
            Dictionary with libraries, keywords, and any error
        """
        logger.info(f"Exploring Robot Framework libraries: library_name={library_name}")
        
        result = explore_libraries(
            library_name=library_name,
            keyword_pattern=keyword_pattern,
            include_standard_libraries=include_standard_libraries,
            include_installed_libraries=include_installed_libraries
        )
        
        return result 