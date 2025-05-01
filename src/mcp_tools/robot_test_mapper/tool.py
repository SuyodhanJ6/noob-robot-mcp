#!/usr/bin/env python
"""
MCP Tool: Robot Test Mapper
Maps test cases to application components, functionality, or features.
"""

import os
import logging
import json
import re
from typing import List, Dict, Any, Optional, Set, Union
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import (
    find_robot_files,
    parse_robot_file,
    is_robot_file
)

logger = logging.getLogger('robot_tool.test_mapper')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class RobotTestMapperRequest(BaseModel):
    """Request model for robot_test_mapper tool."""
    file_path: Optional[str] = Field(
        None,
        description="Path to a specific .robot file to map"
    )
    directory_path: Optional[str] = Field(
        None,
        description="Path to a directory containing .robot files"
    )
    recursive: bool = Field(
        True,
        description="Whether to search directories recursively"
    )
    mapping_file: Optional[str] = Field(
        None,
        description="Path to a JSON file containing existing mappings to update"
    )
    output_file: Optional[str] = Field(
        None,
        description="Path to save the generated mapping"
    )
    tag_based: bool = Field(
        True,
        description="Whether to use tags for mapping"
    )
    name_based: bool = Field(
        True,
        description="Whether to use test names for mapping"
    )
    content_based: bool = Field(
        True,
        description="Whether to analyze test content for mapping"
    )

class TestMapping(BaseModel):
    """Model for a test mapping."""
    test_name: str = Field(..., description="Name of the test case")
    file_path: str = Field(..., description="Path to the file containing the test")
    components: List[str] = Field(default_factory=list, description="Application components the test covers")
    features: List[str] = Field(default_factory=list, description="Features the test covers")
    functionality: List[str] = Field(default_factory=list, description="Functionalities the test covers")
    tags: List[str] = Field(default_factory=list, description="Tags associated with the test")
    mapping_confidence: float = Field(0.0, description="Confidence level of the mapping (0.0-1.0)")
    mapping_method: str = Field("", description="Method used for mapping (tag, name, content)")

class RobotTestMapperResponse(BaseModel):
    """Response model for robot_test_mapper tool."""
    mappings: List[TestMapping] = Field(
        default_factory=list,
        description="List of test mappings"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of mapping results"
    )
    output_file: Optional[str] = Field(
        None,
        description="Path to the saved mapping file if applicable"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def extract_components_from_tags(tags: List[str]) -> List[str]:
    """
    Extract component information from test tags.
    
    Args:
        tags: List of test tags
        
    Returns:
        List of identified components
    """
    components = []
    
    # Look for component-related tags
    for tag in tags:
        # Common patterns for component tags
        if tag.lower().startswith(("component:", "comp:", "module:", "mod:")):
            component = tag.split(":", 1)[1].strip()
            if component:
                components.append(component)
        
        # Check for component tags without prefix
        elif tag.lower().startswith(("ui", "frontend", "backend", "api", "database", "db", "auth")):
            components.append(tag)
    
    return components

def extract_features_from_tags(tags: List[str]) -> List[str]:
    """
    Extract feature information from test tags.
    
    Args:
        tags: List of test tags
        
    Returns:
        List of identified features
    """
    features = []
    
    # Look for feature-related tags
    for tag in tags:
        # Common patterns for feature tags
        if tag.lower().startswith(("feature:", "feat:", "story:")):
            feature = tag.split(":", 1)[1].strip()
            if feature:
                features.append(feature)
    
    return features

def extract_functionality_from_tags(tags: List[str]) -> List[str]:
    """
    Extract functionality information from test tags.
    
    Args:
        tags: List of test tags
        
    Returns:
        List of identified functionalities
    """
    functionalities = []
    
    # Look for functionality-related tags
    for tag in tags:
        # Common patterns for functionality tags
        if tag.lower().startswith(("func:", "functionality:", "action:")):
            functionality = tag.split(":", 1)[1].strip()
            if functionality:
                functionalities.append(functionality)
        
        # Check for common functionality tags
        elif tag.lower() in ("login", "logout", "signup", "search", "filter", "sort", "create", "read", "update", "delete", "crud"):
            functionalities.append(tag)
    
    return functionalities

def extract_components_from_name(test_name: str) -> List[str]:
    """
    Extract component information from test name.
    
    Args:
        test_name: Name of the test
        
    Returns:
        List of identified components
    """
    components = []
    
    # Common component terms
    component_terms = [
        "UI", "Frontend", "Backend", "API", "Database", "DB", "Auth",
        "Login", "User", "Admin", "Dashboard", "Report", "Form",
        "Navigation", "Menu", "Button", "Input", "Validation"
    ]
    
    # Check for component terms in the test name
    for term in component_terms:
        if term.lower() in test_name.lower():
            components.append(term)
    
    return components

def extract_functionality_from_name(test_name: str) -> List[str]:
    """
    Extract functionality information from test name.
    
    Args:
        test_name: Name of the test
        
    Returns:
        List of identified functionalities
    """
    functionalities = []
    
    # Common functionality terms
    func_terms = [
        "Login", "Logout", "Signup", "Register", "Search", "Filter", "Sort",
        "Create", "Read", "Update", "Delete", "CRUD", "Upload", "Download",
        "Submit", "Validate", "Calculate", "Process", "Generate", "Export", "Import"
    ]
    
    # Check for functionality terms in the test name
    for term in func_terms:
        if term.lower() in test_name.lower():
            functionalities.append(term)
    
    return functionalities

def extract_mapping_from_content(steps: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Extract mapping information from test steps.
    
    Args:
        steps: List of test steps
        
    Returns:
        Dictionary with components, features, and functionalities
    """
    result = {
        "components": [],
        "features": [],
        "functionality": []
    }
    
    # Component-related keywords
    component_keywords = {
        "UI": ["click", "input", "select", "button", "field", "form", "page", "element", "checkbox", "radio", "dropdown"],
        "API": ["api", "endpoint", "request", "response", "rest", "json", "http", "get", "post", "put", "delete"],
        "DB": ["database", "query", "sql", "table", "record", "insert", "update", "delete", "row", "column"],
        "Auth": ["login", "logout", "authenticate", "authorization", "credentials", "password", "user", "permission"]
    }
    
    # Functionality-related keywords
    func_keywords = {
        "Login": ["login", "sign in", "authenticate", "credentials"],
        "Search": ["search", "find", "filter", "query"],
        "Create": ["create", "add", "insert", "new"],
        "Read": ["read", "view", "display", "get"],
        "Update": ["update", "edit", "modify", "change"],
        "Delete": ["delete", "remove", "clear"]
    }
    
    # Process each step
    for step in steps:
        keyword = step.get("keyword", "").lower()
        args = [str(arg).lower() for arg in step.get("args", [])]
        
        # Check for component-related keywords
        for component, keywords in component_keywords.items():
            if any(kw in keyword for kw in keywords) or any(any(kw in arg for kw in keywords) for arg in args):
                if component not in result["components"]:
                    result["components"].append(component)
        
        # Check for functionality-related keywords
        for func, keywords in func_keywords.items():
            if any(kw in keyword for kw in keywords) or any(any(kw in arg for kw in keywords) for arg in args):
                if func not in result["functionality"]:
                    result["functionality"].append(func)
    
    return result

def load_existing_mappings(mapping_file: str) -> List[Dict[str, Any]]:
    """
    Load existing mappings from a JSON file.
    
    Args:
        mapping_file: Path to the mapping file
        
    Returns:
        List of mappings
    """
    try:
        if not os.path.exists(mapping_file):
            return []
        
        with open(mapping_file, "r") as f:
            mappings = json.load(f)
        
        # Validate the structure
        if not isinstance(mappings, list):
            return []
        
        return mappings
        
    except Exception as e:
        logger.error(f"Error loading existing mappings: {e}")
        return []

def save_mappings(mappings: List[Dict[str, Any]], output_file: str) -> bool:
    """
    Save mappings to a JSON file.
    
    Args:
        mappings: List of mappings to save
        output_file: Path to save the mappings
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump(mappings, f, indent=2)
        
        return True
        
    except Exception as e:
        logger.error(f"Error saving mappings: {e}")
        return False

def map_tests(
    file_path: Optional[str] = None,
    directory_path: Optional[str] = None,
    recursive: bool = True,
    mapping_file: Optional[str] = None,
    output_file: Optional[str] = None,
    tag_based: bool = True,
    name_based: bool = True,
    content_based: bool = True
) -> Dict[str, Any]:
    """
    Map test cases to application components, features, and functionalities.
    
    Args:
        file_path: Path to a specific .robot file to map
        directory_path: Path to a directory containing .robot files
        recursive: Whether to search directories recursively
        mapping_file: Path to a JSON file containing existing mappings to update
        output_file: Path to save the generated mapping
        tag_based: Whether to use tags for mapping
        name_based: Whether to use test names for mapping
        content_based: Whether to analyze test content for mapping
        
    Returns:
        Dictionary with mappings and summary
    """
    result = {
        "mappings": [],
        "summary": {
            "total_files": 0,
            "total_tests": 0,
            "mapped_tests": 0,
            "mapping_methods": {
                "tag": 0,
                "name": 0,
                "content": 0
            }
        },
        "output_file": output_file,
        "error": None
    }
    
    try:
        # Load existing mappings if provided
        existing_mappings = []
        if mapping_file:
            existing_mappings = load_existing_mappings(mapping_file)
        
        robot_files = []
        
        # Case 1: Specific file
        if file_path:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return {
                    "mappings": [],
                    "summary": result["summary"],
                    "output_file": output_file,
                    "error": f"File not found: {file_path}"
                }
            
            if not is_robot_file(file_path_obj):
                return {
                    "mappings": [],
                    "summary": result["summary"],
                    "output_file": output_file,
                    "error": f"Not a valid Robot Framework file: {file_path}"
                }
                
            robot_files = [file_path_obj]
            
        # Case 2: Directory
        elif directory_path:
            dir_path = Path(directory_path)
            if not dir_path.exists() or not dir_path.is_dir():
                return {
                    "mappings": [],
                    "summary": result["summary"],
                    "output_file": output_file,
                    "error": f"Directory not found: {directory_path}"
                }
                
            robot_files = find_robot_files(dir_path, recursive=recursive)
            
            if not robot_files:
                return {
                    "mappings": [],
                    "summary": result["summary"],
                    "output_file": output_file,
                    "error": f"No Robot Framework files found in {directory_path}"
                }
        else:
            return {
                "mappings": [],
                "summary": result["summary"],
                "output_file": output_file,
                "error": "Either file_path or directory_path must be provided"
            }
        
        # Update summary
        result["summary"]["total_files"] = len(robot_files)
        
        # Process each file
        for file_path_obj in robot_files:
            file_path_str = str(file_path_obj)
            parsed_file = parse_robot_file(file_path_obj)
            
            # Process each test case
            for test in parsed_file.get("test_cases", []):
                test_name = test.get("name", "")
                result["summary"]["total_tests"] += 1
                
                # Check if we already have a mapping for this test
                existing_mapping = None
                for mapping in existing_mappings:
                    if mapping.get("test_name") == test_name and mapping.get("file_path") == file_path_str:
                        existing_mapping = mapping
                        break
                
                # Initialize mapping
                mapping = {
                    "test_name": test_name,
                    "file_path": file_path_str,
                    "components": [],
                    "features": [],
                    "functionality": [],
                    "tags": test.get("tags", []),
                    "mapping_confidence": 0.0,
                    "mapping_method": ""
                }
                
                # If we have an existing mapping, use it as a starting point
                if existing_mapping:
                    mapping["components"] = existing_mapping.get("components", [])
                    mapping["features"] = existing_mapping.get("features", [])
                    mapping["functionality"] = existing_mapping.get("functionality", [])
                    mapping["mapping_confidence"] = existing_mapping.get("mapping_confidence", 0.0)
                    mapping["mapping_method"] = existing_mapping.get("mapping_method", "")
                
                # Tag-based mapping
                if tag_based and test.get("tags"):
                    tags = test.get("tags", [])
                    
                    # Extract components, features, and functionalities from tags
                    tag_components = extract_components_from_tags(tags)
                    tag_features = extract_features_from_tags(tags)
                    tag_functionalities = extract_functionality_from_tags(tags)
                    
                    # Update mapping
                    for comp in tag_components:
                        if comp not in mapping["components"]:
                            mapping["components"].append(comp)
                    
                    for feat in tag_features:
                        if feat not in mapping["features"]:
                            mapping["features"].append(feat)
                    
                    for func in tag_functionalities:
                        if func not in mapping["functionality"]:
                            mapping["functionality"].append(func)
                    
                    # Update confidence and method if we found anything
                    if tag_components or tag_features or tag_functionalities:
                        mapping["mapping_confidence"] = 0.9  # High confidence for tag-based
                        if not mapping["mapping_method"]:
                            mapping["mapping_method"] = "tag"
                        elif "tag" not in mapping["mapping_method"]:
                            mapping["mapping_method"] += ", tag"
                        
                        # Update summary
                        result["summary"]["mapping_methods"]["tag"] += 1
                
                # Name-based mapping
                if name_based:
                    # Extract components and functionalities from test name
                    name_components = extract_components_from_name(test_name)
                    name_functionalities = extract_functionality_from_name(test_name)
                    
                    # Update mapping
                    for comp in name_components:
                        if comp not in mapping["components"]:
                            mapping["components"].append(comp)
                    
                    for func in name_functionalities:
                        if func not in mapping["functionality"]:
                            mapping["functionality"].append(func)
                    
                    # Update confidence and method if we found anything
                    if name_components or name_functionalities:
                        # Only update confidence if it's lower than the name-based confidence
                        if mapping["mapping_confidence"] < 0.7:
                            mapping["mapping_confidence"] = 0.7  # Medium confidence for name-based
                        
                        if not mapping["mapping_method"]:
                            mapping["mapping_method"] = "name"
                        elif "name" not in mapping["mapping_method"]:
                            mapping["mapping_method"] += ", name"
                        
                        # Update summary
                        result["summary"]["mapping_methods"]["name"] += 1
                
                # Content-based mapping
                if content_based and test.get("steps"):
                    # Extract mapping from test steps
                    content_mapping = extract_mapping_from_content(test.get("steps", []))
                    
                    # Update mapping
                    for comp in content_mapping["components"]:
                        if comp not in mapping["components"]:
                            mapping["components"].append(comp)
                    
                    for feat in content_mapping["features"]:
                        if feat not in mapping["features"]:
                            mapping["features"].append(feat)
                    
                    for func in content_mapping["functionality"]:
                        if func not in mapping["functionality"]:
                            mapping["functionality"].append(func)
                    
                    # Update confidence and method if we found anything
                    if content_mapping["components"] or content_mapping["features"] or content_mapping["functionality"]:
                        # Only update confidence if it's lower than the content-based confidence
                        if mapping["mapping_confidence"] < 0.5:
                            mapping["mapping_confidence"] = 0.5  # Lower confidence for content-based
                        
                        if not mapping["mapping_method"]:
                            mapping["mapping_method"] = "content"
                        elif "content" not in mapping["mapping_method"]:
                            mapping["mapping_method"] += ", content"
                        
                        # Update summary
                        result["summary"]["mapping_methods"]["content"] += 1
                
                # Check if we mapped anything
                if mapping["components"] or mapping["features"] or mapping["functionality"]:
                    result["summary"]["mapped_tests"] += 1
                
                # Add mapping to result
                result["mappings"].append(mapping)
        
        # Save mappings if output file is provided
        if output_file and result["mappings"]:
            if save_mappings(result["mappings"], output_file):
                result["output_file"] = output_file
            else:
                result["error"] = f"Failed to save mappings to {output_file}"
        
        logger.info(f"Generated mappings for {result['summary']['mapped_tests']} of {result['summary']['total_tests']} tests from {len(robot_files)} files")
        return result
        
    except Exception as e:
        logger.error(f"Error mapping tests: {e}")
        return {
            "mappings": result["mappings"],
            "summary": result["summary"],
            "output_file": output_file,
            "error": f"Error mapping tests: {str(e)}"
        }

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_test_mapper(request: RobotTestMapperRequest) -> RobotTestMapperResponse:
        """
        Map test cases to application components, features, and functionalities.
        
        Args:
            request: The request containing file or directory paths and mapping options
            
        Returns:
            Response with test mappings and summary
        """
        logger.info(f"Received request for Robot Framework test mapping")
        
        try:
            result = map_tests(
                file_path=request.file_path,
                directory_path=request.directory_path,
                recursive=request.recursive,
                mapping_file=request.mapping_file,
                output_file=request.output_file,
                tag_based=request.tag_based,
                name_based=request.name_based,
                content_based=request.content_based
            )
            
            return RobotTestMapperResponse(
                mappings=result["mappings"],
                summary=result["summary"],
                output_file=result["output_file"],
                error=result["error"]
            )
            
        except Exception as e:
            error_msg = f"Error in robot_test_mapper: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return RobotTestMapperResponse(
                mappings=[],
                summary={},
                output_file=request.output_file,
                error=error_msg
            ) 