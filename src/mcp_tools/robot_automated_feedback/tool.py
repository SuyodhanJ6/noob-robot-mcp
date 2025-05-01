#!/usr/bin/env python
"""
MCP Tool: Robot Automated Feedback
Provides feedback on test case design (e.g., efficiency, readability, maintainability).
"""

import os
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
import re

from src.utils.helpers import (
    find_robot_files,
    parse_robot_file,
    is_robot_file
)
from src.config.config import LINTER_RULES, SYSTEM_PROMPTS

logger = logging.getLogger('robot_tool.automated_feedback')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class RobotAutomatedFeedbackRequest(BaseModel):
    """Request model for robot_automated_feedback tool."""
    file_path: Optional[str] = Field(
        None,
        description="Path to a specific .robot file to analyze"
    )
    directory_path: Optional[str] = Field(
        None,
        description="Path to a directory containing .robot files"
    )
    recursive: bool = Field(
        True,
        description="Whether to search directories recursively"
    )
    detailed: bool = Field(
        False,
        description="Whether to provide detailed feedback"
    )

class FeedbackItem(BaseModel):
    """Model for a feedback item."""
    file_path: str = Field(..., description="Path to the file")
    line_number: Optional[int] = Field(None, description="Line number if applicable")
    severity: str = Field(..., description="Severity level: 'info', 'warning', 'critical'")
    category: str = Field(..., description="Category of feedback: 'naming', 'structure', 'redundancy', 'maintainability'")
    message: str = Field(..., description="Feedback message")
    suggestion: str = Field(..., description="Suggestion for improvement")

class RobotAutomatedFeedbackResponse(BaseModel):
    """Response model for robot_automated_feedback tool."""
    feedback: List[FeedbackItem] = Field(
        default_factory=list,
        description="List of feedback items"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of feedback"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def analyze_test_case_naming(test_cases: List[Dict[str, Any]], file_path: str) -> List[FeedbackItem]:
    """
    Analyze test case naming conventions.
    
    Args:
        test_cases: List of test cases to analyze
        file_path: Path to the file
        
    Returns:
        List of feedback items
    """
    feedback_items = []
    naming_pattern = re.compile(LINTER_RULES["test_naming"])
    
    for test in test_cases:
        test_name = test.get("name", "")
        line_number = test.get("line", None)
        
        # Check if test name is too short
        if len(test_name) < 10:
            feedback_items.append(
                FeedbackItem(
                    file_path=file_path,
                    line_number=line_number,
                    severity="warning",
                    category="naming",
                    message=f"Test name '{test_name}' is too short and may not be descriptive enough",
                    suggestion="Use more descriptive test names that clearly indicate what is being tested"
                )
            )
        
        # Check if test name doesn't follow naming convention
        if not naming_pattern.match(test_name):
            feedback_items.append(
                FeedbackItem(
                    file_path=file_path,
                    line_number=line_number,
                    severity="warning",
                    category="naming",
                    message=f"Test name '{test_name}' doesn't follow the recommended naming convention",
                    suggestion=f"Follow the pattern '{LINTER_RULES['test_naming']}' for test names"
                )
            )
    
    return feedback_items

def analyze_keyword_naming(keywords: List[Dict[str, Any]], file_path: str) -> List[FeedbackItem]:
    """
    Analyze keyword naming conventions.
    
    Args:
        keywords: List of keywords to analyze
        file_path: Path to the file
        
    Returns:
        List of feedback items
    """
    feedback_items = []
    naming_pattern = re.compile(LINTER_RULES["keyword_naming"])
    
    for keyword in keywords:
        keyword_name = keyword.get("name", "")
        line_number = keyword.get("line", None)
        
        # Check if keyword name is too short
        if len(keyword_name) < 5:
            feedback_items.append(
                FeedbackItem(
                    file_path=file_path,
                    line_number=line_number,
                    severity="info",
                    category="naming",
                    message=f"Keyword name '{keyword_name}' is too short and may not be descriptive enough",
                    suggestion="Use more descriptive keyword names that clearly indicate the action performed"
                )
            )
        
        # Check if keyword name doesn't follow naming convention
        if not naming_pattern.match(keyword_name):
            feedback_items.append(
                FeedbackItem(
                    file_path=file_path,
                    line_number=line_number,
                    severity="info",
                    category="naming",
                    message=f"Keyword name '{keyword_name}' doesn't follow the recommended naming convention",
                    suggestion=f"Follow the pattern '{LINTER_RULES['keyword_naming']}' for keyword names"
                )
            )
    
    return feedback_items

def analyze_test_structure(test_cases: List[Dict[str, Any]], file_path: str) -> List[FeedbackItem]:
    """
    Analyze test case structure.
    
    Args:
        test_cases: List of test cases to analyze
        file_path: Path to the file
        
    Returns:
        List of feedback items
    """
    feedback_items = []
    
    for test in test_cases:
        test_name = test.get("name", "")
        line_number = test.get("line", None)
        steps = test.get("steps", [])
        
        # Check for empty test cases
        if not steps:
            feedback_items.append(
                FeedbackItem(
                    file_path=file_path,
                    line_number=line_number,
                    severity="warning",
                    category="structure",
                    message=f"Test case '{test_name}' has no steps",
                    suggestion="Add steps to the test case or remove it if not needed"
                )
            )
        
        # Check for too many steps in a test case
        if len(steps) > 15:
            feedback_items.append(
                FeedbackItem(
                    file_path=file_path,
                    line_number=line_number,
                    severity="warning",
                    category="structure",
                    message=f"Test case '{test_name}' has {len(steps)} steps, which is too many",
                    suggestion="Consider breaking the test into smaller, more focused tests or create custom keywords for groups of steps"
                )
            )
        
        # Check for missing documentation
        if not test.get("documentation", ""):
            feedback_items.append(
                FeedbackItem(
                    file_path=file_path,
                    line_number=line_number,
                    severity="info",
                    category="maintainability",
                    message=f"Test case '{test_name}' lacks documentation",
                    suggestion="Add documentation to describe the purpose and expected behavior of the test"
                )
            )
    
    return feedback_items

def analyze_redundancy(test_cases: List[Dict[str, Any]], file_path: str) -> List[FeedbackItem]:
    """
    Analyze test cases for redundancy.
    
    Args:
        test_cases: List of test cases to analyze
        file_path: Path to the file
        
    Returns:
        List of feedback items
    """
    feedback_items = []
    
    # Extract patterns of steps
    step_patterns = {}
    for test in test_cases:
        test_name = test.get("name", "")
        line_number = test.get("line", None)
        steps = test.get("steps", [])
        
        if len(steps) < 3:
            continue
        
        # Create a pattern from 3 consecutive steps
        for i in range(len(steps) - 2):
            pattern = tuple(step.get("keyword", "") for step in steps[i:i+3])
            if pattern in step_patterns:
                step_patterns[pattern]["count"] += 1
                step_patterns[pattern]["tests"].append(test_name)
            else:
                step_patterns[pattern] = {
                    "count": 1,
                    "tests": [test_name],
                    "line": line_number
                }
    
    # Check for repeated patterns
    for pattern, info in step_patterns.items():
        if info["count"] > 1 and len(info["tests"]) > 1:
            feedback_items.append(
                FeedbackItem(
                    file_path=file_path,
                    line_number=info["line"],
                    severity="warning",
                    category="redundancy",
                    message=f"Redundant step pattern '{' -> '.join(pattern)}' found in multiple tests: {', '.join(info['tests'][:3])}{'...' if len(info['tests']) > 3 else ''}",
                    suggestion="Consider creating a custom keyword for these steps to reduce redundancy"
                )
            )
    
    return feedback_items

def analyze_variable_usage(robot_file: Dict[str, Any], file_path: str) -> List[FeedbackItem]:
    """
    Analyze variable usage in Robot Framework files.
    
    Args:
        robot_file: Parsed Robot Framework file
        file_path: Path to the file
        
    Returns:
        List of feedback items
    """
    feedback_items = []
    variables = robot_file.get("variables", {})
    test_cases = robot_file.get("test_cases", [])
    keywords = robot_file.get("keywords", [])
    
    # Check for unused variables
    used_variables = set()
    
    # Check in test cases
    for test in test_cases:
        for step in test.get("steps", []):
            step_str = str(step)
            for var in variables:
                if f"${{{var}}}" in step_str:
                    used_variables.add(var)
    
    # Check in keywords
    for keyword in keywords:
        for step in keyword.get("steps", []):
            step_str = str(step)
            for var in variables:
                if f"${{{var}}}" in step_str:
                    used_variables.add(var)
    
    # Report unused variables
    for var in variables:
        if var not in used_variables:
            feedback_items.append(
                FeedbackItem(
                    file_path=file_path,
                    line_number=None,
                    severity="info",
                    category="maintainability",
                    message=f"Variable '${{{var}}}' is defined but not used",
                    suggestion="Remove unused variables to improve maintainability"
                )
            )
    
    return feedback_items

def provide_robot_feedback(
    file_path: Optional[str] = None,
    directory_path: Optional[str] = None,
    recursive: bool = True,
    detailed: bool = False
) -> Dict[str, Any]:
    """
    Provide automated feedback on Robot Framework test files.
    
    Args:
        file_path: Path to a specific .robot file
        directory_path: Path to a directory containing .robot files
        recursive: Whether to search directories recursively
        detailed: Whether to provide detailed feedback
        
    Returns:
        Dictionary with feedback items and summary
    """
    result = {
        "feedback": [],
        "summary": {
            "total_files": 0,
            "total_feedback_items": 0,
            "by_severity": {
                "info": 0,
                "warning": 0,
                "critical": 0
            },
            "by_category": {
                "naming": 0,
                "structure": 0,
                "redundancy": 0,
                "maintainability": 0
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
                    "feedback": [],
                    "summary": result["summary"],
                    "error": f"File not found: {file_path}"
                }
            
            if not is_robot_file(file_path_obj):
                return {
                    "feedback": [],
                    "summary": result["summary"],
                    "error": f"Not a valid Robot Framework file: {file_path}"
                }
                
            robot_files = [file_path_obj]
            
        # Case 2: Directory
        elif directory_path:
            dir_path = Path(directory_path)
            if not dir_path.exists() or not dir_path.is_dir():
                return {
                    "feedback": [],
                    "summary": result["summary"],
                    "error": f"Directory not found: {directory_path}"
                }
                
            robot_files = find_robot_files(dir_path, recursive=recursive)
            
            if not robot_files:
                return {
                    "feedback": [],
                    "summary": result["summary"],
                    "error": f"No Robot Framework files found in {directory_path}"
                }
        else:
            return {
                "feedback": [],
                "summary": result["summary"],
                "error": "Either file_path or directory_path must be provided"
            }
        
        # Update summary
        result["summary"]["total_files"] = len(robot_files)
        
        # Analyze each file
        for file in robot_files:
            file_path_str = str(file)
            
            # Parse the file
            robot_file = parse_robot_file(file)
            
            if "error" in robot_file:
                continue
            
            # Collect feedback
            feedback_items = []
            
            # Analyze test case naming
            feedback_items.extend(analyze_test_case_naming(robot_file.get("test_cases", []), file_path_str))
            
            # Analyze keyword naming
            feedback_items.extend(analyze_keyword_naming(robot_file.get("keywords", []), file_path_str))
            
            # Analyze test structure
            feedback_items.extend(analyze_test_structure(robot_file.get("test_cases", []), file_path_str))
            
            # Analyze redundancy
            feedback_items.extend(analyze_redundancy(robot_file.get("test_cases", []), file_path_str))
            
            # Analyze variable usage
            feedback_items.extend(analyze_variable_usage(robot_file, file_path_str))
            
            # Add feedback to result
            result["feedback"].extend(feedback_items)
            
            # Update summary
            for item in feedback_items:
                result["summary"]["total_feedback_items"] += 1
                result["summary"]["by_severity"][item.severity] += 1
                result["summary"]["by_category"][item.category] += 1
        
        # Sort feedback items by severity and category
        result["feedback"].sort(key=lambda x: (
            {"critical": 0, "warning": 1, "info": 2}[x.severity],
            x.category
        ))
        
        # Limit feedback if not detailed
        if not detailed and len(result["feedback"]) > 20:
            # Keep all critical, but limit warnings and info
            critical = [item for item in result["feedback"] if item.severity == "critical"]
            warnings = [item for item in result["feedback"] if item.severity == "warning"]
            info = [item for item in result["feedback"] if item.severity == "info"]
            
            # Prioritize showing a mix of categories
            def select_diverse(items, limit):
                by_category = {}
                for item in items:
                    if item.category not in by_category:
                        by_category[item.category] = []
                    by_category[item.category].append(item)
                
                selected = []
                while len(selected) < limit and by_category:
                    for category in list(by_category.keys()):
                        if by_category[category]:
                            selected.append(by_category[category].pop(0))
                            if not by_category[category]:
                                del by_category[category]
                        if len(selected) >= limit:
                            break
                
                return selected
            
            # Select items to show
            warning_limit = min(10, len(warnings))
            info_limit = min(5, len(info))
            
            selected_warnings = select_diverse(warnings, warning_limit)
            selected_info = select_diverse(info, info_limit)
            
            # Update result
            result["feedback"] = critical + selected_warnings + selected_info
            result["summary"]["limited_output"] = True
            result["summary"]["total_shown"] = len(result["feedback"])
            
        logger.info(f"Generated feedback for {len(robot_files)} Robot Framework files with {result['summary']['total_feedback_items']} items")
        return result
        
    except Exception as e:
        logger.error(f"Error providing Robot Framework feedback: {e}")
        return {
            "feedback": result["feedback"],
            "summary": result["summary"],
            "error": f"Error providing Robot Framework feedback: {str(e)}"
        }

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_automated_feedback(request: RobotAutomatedFeedbackRequest) -> RobotAutomatedFeedbackResponse:
        """
        Provide automated feedback on Robot Framework test case design.
        
        Args:
            request: The request containing file or directory paths
            
        Returns:
            Response with feedback items and summary
        """
        logger.info(f"Received request for Robot Framework automated feedback")
        
        try:
            result = provide_robot_feedback(
                file_path=request.file_path,
                directory_path=request.directory_path,
                recursive=request.recursive,
                detailed=request.detailed
            )
            
            return RobotAutomatedFeedbackResponse(
                feedback=result["feedback"],
                summary=result["summary"],
                error=result["error"]
            )
            
        except Exception as e:
            error_msg = f"Error in robot_automated_feedback: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return RobotAutomatedFeedbackResponse(
                feedback=[],
                summary={},
                error=error_msg
            ) 