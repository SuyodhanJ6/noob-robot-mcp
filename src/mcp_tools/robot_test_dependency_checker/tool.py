#!/usr/bin/env python
"""
MCP Tool: Robot Test Dependency Checker
Checks for missing dependencies or conflicts between libraries, variables, or keywords in Robot Framework files.
"""

import os
import logging
import re
from typing import List, Dict, Any, Optional, Set, Tuple, Union
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import (
    find_robot_files,
    parse_robot_file,
    is_robot_file,
    get_available_robot_libraries,
    get_library_keywords
)

logger = logging.getLogger('robot_tool.dependency_checker')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class RobotTestDependencyCheckerRequest(BaseModel):
    """Request model for robot_test_dependency_checker tool."""
    file_path: Optional[str] = Field(
        None,
        description="Path to a specific .robot file to check"
    )
    directory_path: Optional[str] = Field(
        None,
        description="Path to a directory containing .robot files"
    )
    recursive: bool = Field(
        True,
        description="Whether to search directories recursively"
    )
    check_libraries: bool = Field(
        True,
        description="Whether to check for missing library dependencies"
    )
    check_resources: bool = Field(
        True,
        description="Whether to check for missing resource dependencies"
    )
    check_variables: bool = Field(
        True,
        description="Whether to check for undefined variables"
    )
    check_keywords: bool = Field(
        True,
        description="Whether to check for undefined keywords"
    )

class DependencyIssue(BaseModel):
    """Model for a dependency issue."""
    file_path: str = Field(..., description="Path to the file with the issue")
    line_number: Optional[int] = Field(None, description="Line number if available")
    issue_type: str = Field(..., description="Type of issue: 'missing_library', 'missing_resource', 'undefined_variable', 'undefined_keyword', 'conflicting_keyword'")
    name: str = Field(..., description="Name of the dependency (library, resource, variable, keyword)")
    message: str = Field(..., description="Description of the issue")
    suggestion: Optional[str] = Field(None, description="Suggestion for resolving the issue")

class RobotTestDependencyCheckerResponse(BaseModel):
    """Response model for robot_test_dependency_checker tool."""
    issues: List[DependencyIssue] = Field(
        default_factory=list,
        description="List of dependency issues found"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of dependency checking results"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def extract_library_imports(robot_file: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract library imports from a Robot Framework file.
    
    Args:
        robot_file: Parsed Robot Framework file
        
    Returns:
        List of library imports with name and arguments
    """
    libraries = []
    
    settings = robot_file.get("settings", {})
    for setting, value in settings.items():
        if setting.lower() == "library":
            if isinstance(value, list):
                for lib in value:
                    if isinstance(lib, str):
                        libraries.append({
                            "name": lib.split()[0],
                            "args": lib.split()[1:] if len(lib.split()) > 1 else []
                        })
                    elif isinstance(lib, dict) and "name" in lib:
                        libraries.append({
                            "name": lib["name"],
                            "args": lib.get("args", [])
                        })
            elif isinstance(value, str):
                libraries.append({
                    "name": value.split()[0],
                    "args": value.split()[1:] if len(value.split()) > 1 else []
                })
    
    return libraries

def extract_resource_imports(robot_file: Dict[str, Any]) -> List[str]:
    """
    Extract resource imports from a Robot Framework file.
    
    Args:
        robot_file: Parsed Robot Framework file
        
    Returns:
        List of resource file paths
    """
    resources = []
    
    settings = robot_file.get("settings", {})
    for setting, value in settings.items():
        if setting.lower() == "resource":
            if isinstance(value, list):
                for res in value:
                    if isinstance(res, str):
                        resources.append(res.strip())
            elif isinstance(value, str):
                resources.append(value.strip())
    
    return resources

def extract_variables_imports(robot_file: Dict[str, Any]) -> List[str]:
    """
    Extract variables imports from a Robot Framework file.
    
    Args:
        robot_file: Parsed Robot Framework file
        
    Returns:
        List of variables file paths
    """
    variables_files = []
    
    settings = robot_file.get("settings", {})
    for setting, value in settings.items():
        if setting.lower() == "variables":
            if isinstance(value, list):
                for var_file in value:
                    if isinstance(var_file, str):
                        variables_files.append(var_file.strip())
            elif isinstance(value, str):
                variables_files.append(value.strip())
    
    return variables_files

def extract_used_variables(robot_file: Dict[str, Any]) -> Set[str]:
    """
    Extract variables used in a Robot Framework file.
    
    Args:
        robot_file: Parsed Robot Framework file
        
    Returns:
        Set of variable names used in the file
    """
    used_variables = set()
    
    # Regular expression to find variables like ${variable_name}
    var_pattern = re.compile(r'\$\{([^}]+)\}')
    
    # Check in test cases
    for test in robot_file.get("test_cases", []):
        # Check in test name
        for match in var_pattern.finditer(test.get("name", "")):
            used_variables.add(match.group(1))
        
        # Check in test steps
        for step in test.get("steps", []):
            # Check in keyword name
            for match in var_pattern.finditer(step.get("keyword", "")):
                used_variables.add(match.group(1))
            
            # Check in arguments
            for arg in step.get("args", []):
                if isinstance(arg, str):
                    for match in var_pattern.finditer(arg):
                        used_variables.add(match.group(1))
    
    # Check in keywords
    for keyword in robot_file.get("keywords", []):
        # Check in keyword name
        for match in var_pattern.finditer(keyword.get("name", "")):
            used_variables.add(match.group(1))
        
        # Check in keyword steps
        for step in keyword.get("steps", []):
            # Check in step keyword
            for match in var_pattern.finditer(step.get("keyword", "")):
                used_variables.add(match.group(1))
            
            # Check in arguments
            for arg in step.get("args", []):
                if isinstance(arg, str):
                    for match in var_pattern.finditer(arg):
                        used_variables.add(match.group(1))
    
    return used_variables

def extract_defined_variables(robot_file: Dict[str, Any]) -> Set[str]:
    """
    Extract variables defined in a Robot Framework file.
    
    Args:
        robot_file: Parsed Robot Framework file
        
    Returns:
        Set of variable names defined in the file
    """
    defined_variables = set()
    
    # Add variables from the Variables section
    for var_name in robot_file.get("variables", {}):
        defined_variables.add(var_name)
    
    # Add variables from test case and keyword arguments
    for test in robot_file.get("test_cases", []):
        for step in test.get("steps", []):
            if step.get("keyword", "").lower().startswith(("set variable", "create list", "create dictionary")):
                if len(step.get("args", [])) >= 1:
                    var_name = step["args"][0]
                    if var_name.startswith("${") and var_name.endswith("}"):
                        defined_variables.add(var_name[2:-1])
    
    for keyword in robot_file.get("keywords", []):
        # Add arguments as defined variables
        for arg in keyword.get("args", []):
            if arg.startswith("${") and arg.endswith("}"):
                defined_variables.add(arg[2:-1])
        
        # Add variables set within the keyword
        for step in keyword.get("steps", []):
            if step.get("keyword", "").lower().startswith(("set variable", "create list", "create dictionary")):
                if len(step.get("args", [])) >= 1:
                    var_name = step["args"][0]
                    if var_name.startswith("${") and var_name.endswith("}"):
                        defined_variables.add(var_name[2:-1])
    
    return defined_variables

def extract_used_keywords(robot_file: Dict[str, Any]) -> Set[str]:
    """
    Extract keywords used in a Robot Framework file.
    
    Args:
        robot_file: Parsed Robot Framework file
        
    Returns:
        Set of keyword names used in the file
    """
    used_keywords = set()
    
    # Check in test cases
    for test in robot_file.get("test_cases", []):
        for step in test.get("steps", []):
            keyword = step.get("keyword", "")
            if keyword:
                used_keywords.add(keyword.strip())
    
    # Check in keywords
    for keyword in robot_file.get("keywords", []):
        for step in keyword.get("steps", []):
            step_keyword = step.get("keyword", "")
            if step_keyword:
                used_keywords.add(step_keyword.strip())
    
    return used_keywords

def extract_defined_keywords(robot_file: Dict[str, Any]) -> Set[str]:
    """
    Extract keywords defined in a Robot Framework file.
    
    Args:
        robot_file: Parsed Robot Framework file
        
    Returns:
        Set of keyword names defined in the file
    """
    defined_keywords = set()
    
    for keyword in robot_file.get("keywords", []):
        defined_keywords.add(keyword.get("name", "").strip())
    
    return defined_keywords

def check_dependencies(
    file_path: Optional[str] = None,
    directory_path: Optional[str] = None,
    recursive: bool = True,
    check_libraries: bool = True,
    check_resources: bool = True,
    check_variables: bool = True,
    check_keywords: bool = True
) -> Dict[str, Any]:
    """
    Check for missing dependencies in Robot Framework files.
    
    Args:
        file_path: Path to a specific .robot file to check
        directory_path: Path to a directory containing .robot files
        recursive: Whether to search directories recursively
        check_libraries: Whether to check for missing library dependencies
        check_resources: Whether to check for missing resource dependencies
        check_variables: Whether to check for undefined variables
        check_keywords: Whether to check for undefined keywords
        
    Returns:
        Dictionary with dependency issues and summary
    """
    result = {
        "issues": [],
        "summary": {
            "total_files": 0,
            "total_issues": 0,
            "by_type": {
                "missing_library": 0,
                "missing_resource": 0,
                "undefined_variable": 0,
                "undefined_keyword": 0,
                "conflicting_keyword": 0
            }
        },
        "error": None
    }
    
    try:
        robot_files = []
        
        # Case 1: Specific file
        if file_path:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return {
                    "issues": [],
                    "summary": result["summary"],
                    "error": f"File not found: {file_path}"
                }
            
            if not is_robot_file(file_path_obj):
                return {
                    "issues": [],
                    "summary": result["summary"],
                    "error": f"Not a valid Robot Framework file: {file_path}"
                }
                
            robot_files = [file_path_obj]
            
        # Case 2: Directory
        elif directory_path:
            dir_path = Path(directory_path)
            if not dir_path.exists() or not dir_path.is_dir():
                return {
                    "issues": [],
                    "summary": result["summary"],
                    "error": f"Directory not found: {directory_path}"
                }
                
            robot_files = find_robot_files(dir_path, recursive=recursive)
            
            if not robot_files:
                return {
                    "issues": [],
                    "summary": result["summary"],
                    "error": f"No Robot Framework files found in {directory_path}"
                }
        else:
            return {
                "issues": [],
                "summary": result["summary"],
                "error": "Either file_path or directory_path must be provided"
            }
        
        # Update summary
        result["summary"]["total_files"] = len(robot_files)
        
        # Get available libraries
        available_libraries = get_available_robot_libraries() if check_libraries else []
        
        # Process each file
        parsed_files = {}
        for file_path_obj in robot_files:
            file_path_str = str(file_path_obj)
            parsed_file = parse_robot_file(file_path_obj)
            parsed_files[file_path_str] = parsed_file
        
        # Create resource and variable file mappings
        resource_files = {}
        variable_files = {}
        
        # First pass: collect all defined resources and variables
        for file_path_str, parsed_file in parsed_files.items():
            resource_files[file_path_str] = extract_resource_imports(parsed_file)
            variable_files[file_path_str] = extract_variables_imports(parsed_file)
        
        # Second pass: check dependencies
        for file_path_str, parsed_file in parsed_files.items():
            base_dir = os.path.dirname(file_path_str)
            
            # Check library dependencies
            if check_libraries:
                libraries = extract_library_imports(parsed_file)
                for lib in libraries:
                    lib_name = lib["name"]
                    if lib_name not in available_libraries:
                        result["issues"].append(
                            DependencyIssue(
                                file_path=file_path_str,
                                line_number=None,
                                issue_type="missing_library",
                                name=lib_name,
                                message=f"Library '{lib_name}' is imported but not installed or available",
                                suggestion=f"Install the library with 'pip install {lib_name.lower()}' or check the import path"
                            )
                        )
                        result["summary"]["by_type"]["missing_library"] += 1
                        result["summary"]["total_issues"] += 1
            
            # Check resource dependencies
            if check_resources:
                resources = resource_files[file_path_str]
                for res in resources:
                    # Try different possible paths
                    resource_path = res
                    if not os.path.isabs(resource_path):
                        resource_path = os.path.join(base_dir, resource_path)
                    
                    if not os.path.exists(resource_path):
                        result["issues"].append(
                            DependencyIssue(
                                file_path=file_path_str,
                                line_number=None,
                                issue_type="missing_resource",
                                name=res,
                                message=f"Resource file '{res}' is imported but not found",
                                suggestion=f"Check the resource file path relative to the importing file"
                            )
                        )
                        result["summary"]["by_type"]["missing_resource"] += 1
                        result["summary"]["total_issues"] += 1
            
            # Check variable dependencies
            if check_variables:
                used_vars = extract_used_variables(parsed_file)
                defined_vars = extract_defined_variables(parsed_file)
                
                # Check for undefined variables
                for var in used_vars:
                    if var not in defined_vars:
                        # Check if variable might be defined in imported files
                        found_in_imports = False
                        for imp_vars in variable_files[file_path_str]:
                            # This is a simplified check, ideally we would parse the variables file
                            # But for now, we'll assume the variable might be defined there
                            found_in_imports = True
                            break
                        
                        if not found_in_imports:
                            result["issues"].append(
                                DependencyIssue(
                                    file_path=file_path_str,
                                    line_number=None,
                                    issue_type="undefined_variable",
                                    name=f"${{{var}}}",
                                    message=f"Variable '${{{var}}}' is used but not defined in the file or its imports",
                                    suggestion=f"Define the variable in the Variables section or import it from a variables file"
                                )
                            )
                            result["summary"]["by_type"]["undefined_variable"] += 1
                            result["summary"]["total_issues"] += 1
            
            # Check keyword dependencies
            if check_keywords:
                used_keywords = extract_used_keywords(parsed_file)
                defined_keywords = extract_defined_keywords(parsed_file)
                
                # Built-in keywords (simplified list)
                builtin_keywords = {
                    "log", "log to console", "comment", "sleep", "fail",
                    "fatal error", "exit for loop", "exit for loop if",
                    "continue for loop", "continue for loop if",
                    "return from keyword", "return from keyword if",
                    "set variable", "set test variable", "set suite variable",
                    "set global variable", "variable should exist",
                    "variable should not exist", "get variable value",
                    "run keyword", "run keyword and continue on failure",
                    "run keyword and ignore error", "run keyword and return",
                    "run keyword and return status", "run keyword if",
                    "run keyword if all critical tests passed",
                    "run keyword if all tests passed",
                    "run keyword if any critical tests failed",
                    "run keyword if any tests failed",
                    "run keyword if test failed", "run keyword if test passed",
                    "run keyword unless", "run keywords", "repeat keyword"
                }
                
                # Add library keywords
                library_keywords = set()
                libraries = extract_library_imports(parsed_file)
                for lib in libraries:
                    lib_name = lib["name"]
                    if lib_name in available_libraries:
                        lib_keywords = get_library_keywords(lib_name)
                        for kw in lib_keywords:
                            library_keywords.add(kw.get("name", "").lower())
                
                # Check for undefined keywords
                for keyword in used_keywords:
                    keyword_lower = keyword.lower()
                    if (
                        keyword_lower not in builtin_keywords and
                        keyword_lower not in library_keywords and
                        keyword not in defined_keywords
                    ):
                        # Check if keyword might be defined in imported resources
                        found_in_imports = False
                        for res in resources:
                            # This is a simplified check, ideally we would parse the resource file
                            # But for now, we'll assume the keyword might be defined there
                            found_in_imports = True
                            break
                        
                        if not found_in_imports:
                            result["issues"].append(
                                DependencyIssue(
                                    file_path=file_path_str,
                                    line_number=None,
                                    issue_type="undefined_keyword",
                                    name=keyword,
                                    message=f"Keyword '{keyword}' is used but not defined in the file or its imports",
                                    suggestion=f"Define the keyword in the Keywords section or import it from a resource file"
                                )
                            )
                            result["summary"]["by_type"]["undefined_keyword"] += 1
                            result["summary"]["total_issues"] += 1
                
                # Check for conflicting keywords
                if len(defined_keywords) != len(set(k.lower() for k in defined_keywords)):
                    # Find duplicates
                    keyword_counts = {}
                    for kw in defined_keywords:
                        kw_lower = kw.lower()
                        if kw_lower in keyword_counts:
                            keyword_counts[kw_lower].append(kw)
                        else:
                            keyword_counts[kw_lower] = [kw]
                    
                    # Report conflicts
                    for kw_lower, variants in keyword_counts.items():
                        if len(variants) > 1:
                            result["issues"].append(
                                DependencyIssue(
                                    file_path=file_path_str,
                                    line_number=None,
                                    issue_type="conflicting_keyword",
                                    name=", ".join(variants),
                                    message=f"Multiple keywords with the same name (case-insensitive): {', '.join(variants)}",
                                    suggestion=f"Rename one of the keywords to avoid conflicts"
                                )
                            )
                            result["summary"]["by_type"]["conflicting_keyword"] += 1
                            result["summary"]["total_issues"] += 1
        
        # Sort issues by file path and type
        result["issues"].sort(key=lambda x: (x.file_path, x.issue_type))
        
        logger.info(f"Found {result['summary']['total_issues']} dependency issues in {len(robot_files)} Robot Framework files")
        return result
        
    except Exception as e:
        logger.error(f"Error checking dependencies: {e}")
        return {
            "issues": result["issues"],
            "summary": result["summary"],
            "error": f"Error checking dependencies: {str(e)}"
        }

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_test_dependency_checker(request: RobotTestDependencyCheckerRequest) -> RobotTestDependencyCheckerResponse:
        """
        Check for missing dependencies or conflicts in Robot Framework files.
        
        Args:
            request: The request containing file or directory paths and check options
            
        Returns:
            Response with dependency issues and summary
        """
        logger.info(f"Received request for Robot Framework dependency checking")
        
        try:
            result = check_dependencies(
                file_path=request.file_path,
                directory_path=request.directory_path,
                recursive=request.recursive,
                check_libraries=request.check_libraries,
                check_resources=request.check_resources,
                check_variables=request.check_variables,
                check_keywords=request.check_keywords
            )
            
            return RobotTestDependencyCheckerResponse(
                issues=result["issues"],
                summary=result["summary"],
                error=result["error"]
            )
            
        except Exception as e:
            error_msg = f"Error in robot_test_dependency_checker: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return RobotTestDependencyCheckerResponse(
                issues=[],
                summary={},
                error=error_msg
            ) 