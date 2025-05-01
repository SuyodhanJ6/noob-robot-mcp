#!/usr/bin/env python
"""
MCP Tool: Robot Variable Resolver
Resolves and handles variables used in Robot Framework test files.
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import (
    find_robot_files,
    parse_robot_file,
    is_robot_file
)

logger = logging.getLogger('robot_tool.variable_resolver')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class VariableResolveRequest(BaseModel):
    """Request model for robot_variable_resolver tool."""
    file_path: Optional[str] = Field(
        None,
        description="Path to a specific .robot file to analyze"
    )
    directory_path: Optional[str] = Field(
        None,
        description="Path to a directory containing .robot files to analyze"
    )
    recursive: bool = Field(
        True,
        description="Whether to search directories recursively"
    )
    variable_name: Optional[str] = Field(
        None,
        description="Name of a specific variable to resolve (without $ or {})"
    )
    custom_variables: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom variables to use for resolution"
    )
    resolve_external: bool = Field(
        True,
        description="Whether to resolve variables from external files (resource files, variable files)"
    )

class VariableResolveResponse(BaseModel):
    """Response model for robot_variable_resolver tool."""
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of variable names to their values"
    )
    usages: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Dictionary of variable names to their usages"
    )
    unresolved: List[str] = Field(
        default_factory=list,
        description="List of variables that could not be resolved"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def resolve_variables(
    file_path: Optional[str] = None,
    directory_path: Optional[str] = None,
    recursive: bool = True,
    variable_name: Optional[str] = None,
    custom_variables: Optional[Dict[str, Any]] = None,
    resolve_external: bool = True
) -> Dict[str, Any]:
    """
    Resolve variables used in Robot Framework test files.
    
    Args:
        file_path: Path to a specific .robot file to analyze
        directory_path: Path to a directory containing .robot files to analyze
        recursive: Whether to search directories recursively
        variable_name: Name of a specific variable to resolve
        custom_variables: Custom variables to use for resolution
        resolve_external: Whether to resolve variables from external files
        
    Returns:
        Dictionary with resolved variables, usages, unresolved variables, and any error
    """
    result = {
        "variables": {},
        "usages": {},
        "unresolved": [],
        "error": None
    }
    
    try:
        # Set default values
        custom_variables = custom_variables or {}
        
        # Find robot files to analyze
        robot_files = []
        
        # Case 1: Specific file
        if file_path:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return {
                    "variables": {},
                    "usages": {},
                    "unresolved": [],
                    "error": f"File not found: {file_path}"
                }
            
            if not is_robot_file(file_path_obj):
                return {
                    "variables": {},
                    "usages": {},
                    "unresolved": [],
                    "error": f"Not a valid Robot Framework file: {file_path}"
                }
                
            robot_files = [file_path_obj]
            
        # Case 2: Directory
        elif directory_path:
            dir_path = Path(directory_path)
            if not dir_path.exists() or not dir_path.is_dir():
                return {
                    "variables": {},
                    "usages": {},
                    "unresolved": [],
                    "error": f"Directory not found: {directory_path}"
                }
                
            robot_files = find_robot_files(dir_path, recursive=recursive)
            
            if not robot_files:
                return {
                    "variables": {},
                    "usages": {},
                    "unresolved": [],
                    "error": f"No Robot Framework files found in {directory_path}"
                }
        else:
            return {
                "variables": {},
                "usages": {},
                "unresolved": [],
                "error": "Either file_path or directory_path must be provided"
            }
            
        # Parse each file to collect variables and their usages
        all_variables = {}  # Name -> Value
        all_usages = {}     # Name -> List of usages
        all_unresolved = set()
        resource_files = set()
        variable_files = set()
        
        # First pass: collect all variables and their definitions
        for file_path_obj in robot_files:
            file_data = parse_robot_file(file_path_obj)
            
            # Get variables from Variables section
            for var_name, var_value in file_data.get("variables", {}).items():
                normalized_name = normalize_variable_name(var_name)
                
                if normalized_name not in all_variables:
                    all_variables[normalized_name] = var_value
                    all_usages[normalized_name] = []
                
                all_usages[normalized_name].append({
                    "file": str(file_path_obj),
                    "type": "definition",
                    "value": var_value
                })
            
            # Collect resource files for later processing
            if resolve_external:
                # Get resource files from Settings section
                for setting_name, setting_value in file_data.get("settings", {}).items():
                    if setting_name == "Resource":
                        if isinstance(setting_value, list):
                            resource_files.update(setting_value)
                        else:
                            resource_files.add(setting_value)
                    
                    if setting_name == "Variables":
                        if isinstance(setting_value, list):
                            variable_files.update(setting_value)
                        else:
                            variable_files.add(setting_value)
        
        # Add custom variables
        for var_name, var_value in custom_variables.items():
            normalized_name = normalize_variable_name(var_name)
            all_variables[normalized_name] = var_value
            
            if normalized_name not in all_usages:
                all_usages[normalized_name] = []
                
            all_usages[normalized_name].append({
                "file": "custom",
                "type": "custom",
                "value": var_value
            })
        
        # Second pass: collect variable usages and resolve them
        for file_path_obj in robot_files:
            collect_variable_usages(file_path_obj, all_variables, all_usages, all_unresolved)
        
        # Filter results if a specific variable was requested
        if variable_name:
            normalized_var_name = normalize_variable_name(variable_name)
            if normalized_var_name in all_variables:
                all_variables = {normalized_var_name: all_variables[normalized_var_name]}
                all_usages = {normalized_var_name: all_usages[normalized_var_name]}
                all_unresolved = set()
            else:
                all_variables = {}
                all_usages = {}
                all_unresolved = {normalized_var_name}
        
        result["variables"] = all_variables
        result["usages"] = all_usages
        result["unresolved"] = list(all_unresolved)
        
        logger.info(f"Resolved {len(all_variables)} variables, found {len(all_unresolved)} unresolved variables")
        return result
        
    except Exception as e:
        error_msg = f"Error resolving variables: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "variables": result["variables"],
            "usages": result["usages"],
            "unresolved": result["unresolved"],
            "error": error_msg
        }

def normalize_variable_name(name: str) -> str:
    """
    Normalize a variable name by removing ${}, @{}, &{}, etc.
    
    Args:
        name: The variable name to normalize
        
    Returns:
        Normalized variable name
    """
    # Remove any $, @, &, % and braces
    if name.startswith(('${', '@{', '&{', '%{')):
        return name[2:-1]
    
    # Handle the case where the name doesn't have braces
    return name.lstrip('$@&%')

def collect_variable_usages(
    file_path: Path, 
    all_variables: Dict[str, Any],
    all_usages: Dict[str, List[Dict[str, Any]]],
    all_unresolved: set
) -> None:
    """
    Collect variable usages from a Robot Framework file.
    
    Args:
        file_path: Path to the Robot Framework file
        all_variables: Dictionary of all known variables
        all_usages: Dictionary to update with usages
        all_unresolved: Set to update with unresolved variables
    """
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Find all variable references in the file
        # Match patterns like ${var}, @{list}, &{dict}, %{env}
        var_pattern = re.compile(r'[\$@&%]\{([^{}]+)\}')
        
        for match in var_pattern.finditer(content):
            var_name = match.group(1)
            normalized_name = normalize_variable_name(var_name)
            
            # Skip if it's a nested variable like ${${inner}}
            if var_pattern.search(var_name):
                continue
                
            # Record usage if the variable is known
            if normalized_name in all_variables:
                if normalized_name not in all_usages:
                    all_usages[normalized_name] = []
                    
                # Get line number and context
                line_num = content[:match.start()].count('\n') + 1
                line_content = content.splitlines()[line_num - 1]
                
                all_usages[normalized_name].append({
                    "file": str(file_path),
                    "line": line_num,
                    "context": line_content.strip(),
                    "type": "usage"
                })
            else:
                # Record as unresolved
                all_unresolved.add(normalized_name)
                
    except Exception as e:
        logger.error(f"Error collecting variable usages from {file_path}: {e}")

def resolve_variable_value(
    var_name: str,
    all_variables: Dict[str, Any]
) -> Any:
    """
    Resolve a variable value, including nested variables.
    
    Args:
        var_name: Name of the variable to resolve
        all_variables: Dictionary of all known variables
        
    Returns:
        Resolved variable value
    """
    normalized_name = normalize_variable_name(var_name)
    
    if normalized_name not in all_variables:
        return None
        
    value = all_variables[normalized_name]
    
    # Handle string values with nested variables
    if isinstance(value, str):
        # Match patterns like ${var}, @{list}, &{dict}, %{env}
        var_pattern = re.compile(r'[\$@&%]\{([^{}]+)\}')
        
        def replace_var(match):
            inner_var_name = match.group(1)
            inner_value = resolve_variable_value(inner_var_name, all_variables)
            return str(inner_value) if inner_value is not None else match.group(0)
            
        # Replace all variables in the value
        return var_pattern.sub(replace_var, value)
    
    return value

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_variable_resolver(
        file_path: Optional[str] = None,
        directory_path: Optional[str] = None,
        recursive: bool = True,
        variable_name: Optional[str] = None,
        custom_variables: Optional[Dict[str, Any]] = None,
        resolve_external: bool = True
    ) -> Dict[str, Any]:
        """
        Resolve variables used in Robot Framework test files.
        
        Args:
            file_path: Path to a specific .robot file to analyze (optional)
            directory_path: Path to a directory containing .robot files to analyze (optional)
            recursive: Whether to search directories recursively (default: True)
            variable_name: Name of a specific variable to resolve (without $ or {}) (optional)
            custom_variables: Custom variables to use for resolution (optional)
            resolve_external: Whether to resolve variables from external files (default: True)
            
        Returns:
            Response with resolved variables, usages, unresolved variables, and any error
        """
        logger.info(f"Received request to resolve Robot Framework variables. File: {file_path}, Directory: {directory_path}")
        
        try:
            # Log parameters for debugging
            logger.debug(f"Parameters: file_path={file_path}, "
                        f"directory_path={directory_path}, "
                        f"recursive={recursive}, "
                        f"variable_name={variable_name}, "
                        f"custom_variables={custom_variables}, "
                        f"resolve_external={resolve_external}")
            
            result = resolve_variables(
                file_path=file_path,
                directory_path=directory_path,
                recursive=recursive,
                variable_name=variable_name,
                custom_variables=custom_variables,
                resolve_external=resolve_external
            )
            
            # Return as dictionary for maximum compatibility
            return {
                "variables": result["variables"],
                "usages": result["usages"],
                "unresolved": result["unresolved"],
                "error": result["error"]
            }
            
        except Exception as e:
            error_msg = f"Error in robot_variable_resolver: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "variables": {},
                "usages": {},
                "unresolved": [],
                "error": error_msg
            } 