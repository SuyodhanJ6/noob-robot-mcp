#!/usr/bin/env python
"""
MCP Tool: Robot Test Linter
Performs static analysis on Robot Framework test files to detect syntax errors,
violations of best practices, and potential issues.
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
from src.config.config import (
    TEST_FILE_EXTENSIONS,
    LINTER_RULES
)

logger = logging.getLogger('robot_tool.test_linter')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class LinterIssue(BaseModel):
    """Model for a linter issue."""
    line: int = Field(
        ...,
        description="Line number where the issue was found"
    )
    column: Optional[int] = Field(
        None,
        description="Column number where the issue was found"
    )
    rule: str = Field(
        ...,
        description="Linter rule that was violated"
    )
    severity: str = Field(
        ...,
        description="Severity of the issue (error, warning, info)"
    )
    message: str = Field(
        ...,
        description="Description of the issue"
    )

class LinterFileResult(BaseModel):
    """Model for linter results for a single file."""
    file_path: str = Field(
        ...,
        description="Path to the file that was analyzed"
    )
    issues: List[LinterIssue] = Field(
        default_factory=list,
        description="List of issues found in the file"
    )

class LinterRequest(BaseModel):
    """Request model for robot_test_linter tool."""
    file_path: Optional[str] = Field(
        None,
        description="Path to a specific .robot file to lint"
    )
    directory_path: Optional[str] = Field(
        None,
        description="Path to a directory containing .robot files to lint"
    )
    recursive: bool = Field(
        True,
        description="Whether to search directories recursively"
    )
    rules: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom linter rules to override the defaults"
    )
    ignore_rules: List[str] = Field(
        default_factory=list,
        description="List of rule IDs to ignore"
    )

class LinterResponse(BaseModel):
    """Response model for robot_test_linter tool."""
    results: List[LinterFileResult] = Field(
        default_factory=list,
        description="List of linter results for each file"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of linter results"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def lint_robot_files(
    file_path: Optional[str] = None,
    directory_path: Optional[str] = None,
    recursive: bool = True,
    rules: Optional[Dict[str, Any]] = None,
    ignore_rules: List[str] = None
) -> Dict[str, Any]:
    """
    Lint Robot Framework test files to detect potential issues.
    
    Args:
        file_path: Path to a specific .robot file to lint
        directory_path: Path to a directory containing .robot files to lint
        recursive: Whether to search directories recursively
        rules: Custom linter rules to override the defaults
        ignore_rules: List of rule IDs to ignore
        
    Returns:
        Dictionary with linter results and any error
    """
    result = {
        "results": [],
        "summary": {
            "total_files": 0,
            "files_with_issues": 0,
            "total_issues": 0,
            "errors": 0,
            "warnings": 0,
            "info": 0,
            "warning": 0  # Added for backwards compatibility
        },
        "error": None
    }
    
    try:
        # Set up linter rules
        active_rules = dict(LINTER_RULES)
        if rules:
            active_rules.update(rules)
            
        # Set up ignore rules
        ignored_rules = ignore_rules or []
        
        # Find robot files
        robot_files = []
        
        # Case 1: Specific file
        if file_path:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return {
                    "results": [],
                    "summary": result["summary"],
                    "error": f"File not found: {file_path}"
                }
            
            if not is_robot_file(file_path_obj):
                return {
                    "results": [],
                    "summary": result["summary"],
                    "error": f"Not a valid Robot Framework file: {file_path}"
                }
                
            robot_files = [file_path_obj]
            
        # Case 2: Directory
        elif directory_path:
            dir_path = Path(directory_path)
            if not dir_path.exists() or not dir_path.is_dir():
                return {
                    "results": [],
                    "summary": result["summary"],
                    "error": f"Directory not found: {directory_path}"
                }
                
            robot_files = find_robot_files(dir_path, recursive=recursive)
            
            if not robot_files:
                return {
                    "results": [],
                    "summary": result["summary"],
                    "error": f"No Robot Framework files found in {directory_path}"
                }
        else:
            return {
                "results": [],
                "summary": result["summary"],
                "error": "Either file_path or directory_path must be provided"
            }
            
        # Lint each file
        result["summary"]["total_files"] = len(robot_files)
        
        for file in robot_files:
            file_result = lint_file(file, active_rules, ignored_rules)
            # Convert LinterFileResult to dictionary for consistency
            result["results"].append({
                "file_path": file_result.file_path,
                "issues": [issue.dict() for issue in file_result.issues]
            })
            
            # Update summary
            if file_result.issues:
                result["summary"]["files_with_issues"] += 1
                result["summary"]["total_issues"] += len(file_result.issues)
                
                # Count by severity
                for issue in file_result.issues:
                    severity = issue.severity.lower()
                    # Make sure both "warning" and "warnings" are updated
                    if severity == "warning":
                        result["summary"]["warning"] += 1
                        result["summary"]["warnings"] += 1
                    else:
                        result["summary"][severity] += 1
                    
        logger.info(f"Linted {len(robot_files)} Robot Framework files, found {result['summary']['total_issues']} issues")
        return result
        
    except Exception as e:
        logger.error(f"Error linting Robot Framework files: {str(e)}", exc_info=True)
        return {
            "results": result["results"],
            "summary": result["summary"],
            "error": f"Error linting Robot Framework files: {str(e)}"
        }

def lint_file(
    file_path: Path,
    rules: Dict[str, Any],
    ignored_rules: List[str]
) -> LinterFileResult:
    """
    Lint a single Robot Framework file.
    
    Args:
        file_path: Path to the Robot Framework file
        rules: Linter rules to apply
        ignored_rules: List of rule IDs to ignore
        
    Returns:
        LinterFileResult with issues found in the file
    """
    issues = []
    
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        lines = content.split('\n')
        
        # Parse the robot file
        parsed_file = parse_robot_file(file_path)
        
        # Apply linter rules
        
        # Rule 1: Check line length
        if 'line_length' in rules and 'line_length' not in ignored_rules:
            max_length = rules['line_length']
            for i, line in enumerate(lines):
                if len(line.strip()) > max_length:
                    issues.append(LinterIssue(
                        line=i + 1,  # 1-indexed line number
                        rule='line_length',
                        severity='warning',
                        message=f"Line exceeds maximum length of {max_length} characters"
                    ))
        
        # Rule 2: Check keyword naming
        if 'keyword_naming' in rules and 'keyword_naming' not in ignored_rules:
            pattern = rules['keyword_naming']
            for keyword in parsed_file.get("keywords", []):
                keyword_name = keyword.get("name", "")
                if not re.match(pattern, keyword_name):
                    # Find line number of the keyword
                    line_num = find_line_number(lines, keyword_name) or 1
                    issues.append(LinterIssue(
                        line=line_num,
                        rule='keyword_naming',
                        severity='warning',
                        message=f"Keyword name '{keyword_name}' does not match pattern '{pattern}'"
                    ))
        
        # Rule 3: Check test case naming
        if 'test_naming' in rules and 'test_naming' not in ignored_rules:
            pattern = rules['test_naming']
            for test_case in parsed_file.get("test_cases", []):
                test_name = test_case.get("name", "")
                if not re.match(pattern, test_name):
                    # Find line number of the test case
                    line_num = find_line_number(lines, test_name) or 1
                    issues.append(LinterIssue(
                        line=line_num,
                        rule='test_naming',
                        severity='warning',
                        message=f"Test case name '{test_name}' does not match pattern '{pattern}'"
                    ))
        
        # Rule 4: Check variable naming
        if 'variable_naming' in rules and 'variable_naming' not in ignored_rules:
            pattern = rules['variable_naming']
            for var_name in parsed_file.get("variables", {}).keys():
                if not re.match(pattern, var_name):
                    # Find line number of the variable
                    line_num = find_line_number(lines, var_name) or 1
                    issues.append(LinterIssue(
                        line=line_num,
                        rule='variable_naming',
                        severity='warning',
                        message=f"Variable name '{var_name}' does not match pattern '{pattern}'"
                    ))
        
        # Rule 5: Check for duplicate test cases
        if 'duplicate_test_cases' not in ignored_rules:
            test_names = {}
            for test_case in parsed_file.get("test_cases", []):
                test_name = test_case.get("name", "")
                if test_name in test_names:
                    line_num = find_line_number(lines, test_name, test_names[test_name] + 1) or 1
                    issues.append(LinterIssue(
                        line=line_num,
                        rule='duplicate_test_cases',
                        severity='error',
                        message=f"Duplicate test case name '{test_name}'"
                    ))
                else:
                    test_names[test_name] = find_line_number(lines, test_name) or 1
        
        # Rule 6: Check for duplicate keywords
        if 'duplicate_keywords' not in ignored_rules:
            keyword_names = {}
            for keyword in parsed_file.get("keywords", []):
                keyword_name = keyword.get("name", "")
                if keyword_name in keyword_names:
                    line_num = find_line_number(lines, keyword_name, keyword_names[keyword_name] + 1) or 1
                    issues.append(LinterIssue(
                        line=line_num,
                        rule='duplicate_keywords',
                        severity='error',
                        message=f"Duplicate keyword name '{keyword_name}'"
                    ))
                else:
                    keyword_names[keyword_name] = find_line_number(lines, keyword_name) or 1
        
        # Rule 7: Check for empty sections
        if 'empty_sections' not in ignored_rules:
            for section_name, section_content in parsed_file.get("sections", {}).items():
                if not section_content:
                    # Find line number of the section
                    section_header = f"*** {section_name} ***"
                    line_num = find_line_number(lines, section_header) or 1
                    issues.append(LinterIssue(
                        line=line_num,
                        rule='empty_sections',
                        severity='info',
                        message=f"Empty section '{section_name}'"
                    ))
        
        # Rule 8: Check for missing documentation
        if 'missing_documentation' not in ignored_rules:
            # Check test cases
            for test_case in parsed_file.get("test_cases", []):
                test_name = test_case.get("name", "")
                if not any(step.strip().startswith("[Documentation]") for step in test_case.get("steps", [])):
                    line_num = find_line_number(lines, test_name) or 1
                    issues.append(LinterIssue(
                        line=line_num,
                        rule='missing_documentation',
                        severity='info',
                        message=f"Test case '{test_name}' is missing documentation"
                    ))
            
            # Check keywords
            for keyword in parsed_file.get("keywords", []):
                keyword_name = keyword.get("name", "")
                if not any(step.strip().startswith("[Documentation]") for step in keyword.get("steps", [])):
                    line_num = find_line_number(lines, keyword_name) or 1
                    issues.append(LinterIssue(
                        line=line_num,
                        rule='missing_documentation',
                        severity='info',
                        message=f"Keyword '{keyword_name}' is missing documentation"
                    ))
        
        # Rule 9: Check for hardcoded values
        if 'hardcoded_values' not in ignored_rules:
            # Simple check for values that could be variables
            hardcoded_patterns = [
                r'(\s)(https?://\S+)(\s)',  # URLs
                r'(\s)(\d{4}-\d{2}-\d{2})(\s)',  # Dates
                r'(\s)(\d+\.\d+\.\d+\.\d+)(\s)'  # IP addresses
            ]
            
            for i, line in enumerate(lines):
                for pattern in hardcoded_patterns:
                    matches = re.finditer(pattern, " " + line + " ")
                    for match in matches:
                        issues.append(LinterIssue(
                            line=i + 1,
                            column=match.start(2),
                            rule='hardcoded_values',
                            severity='info',
                            message=f"Consider using a variable instead of hardcoded value '{match.group(2)}'"
                        ))
        
        return LinterFileResult(
            file_path=str(file_path),
            issues=issues
        )
        
    except Exception as e:
        logger.error(f"Error linting file {file_path}: {str(e)}", exc_info=True)
        return LinterFileResult(
            file_path=str(file_path),
            issues=[LinterIssue(
                line=1,
                rule='linter_error',
                severity='error',
                message=f"Error linting file: {str(e)}"
            )]
        )

def find_line_number(lines: List[str], text: str, start_line: int = 0) -> Optional[int]:
    """
    Find the line number containing the specified text.
    
    Args:
        lines: List of file lines
        text: Text to search for
        start_line: Line number to start the search from
        
    Returns:
        Line number (1-indexed) or None if not found
    """
    for i in range(start_line, len(lines)):
        if text in lines[i]:
            return i + 1  # Convert to 1-indexed
    return None

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the robot_test_linter tool with the MCP server."""
    
    @mcp.tool()
    async def robot_test_linter(
        file_path: Optional[str] = None,
        directory_path: Optional[str] = None,
        recursive: bool = True,
        rules: Optional[Dict[str, Any]] = None,
        ignore_rules: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Lint Robot Framework test files to detect potential issues.
        
        Args:
            file_path: Path to a specific .robot file to lint
            directory_path: Path to a directory containing .robot files to lint
            recursive: Whether to search directories recursively
            rules: Custom linter rules to override the defaults
            ignore_rules: List of rule IDs to ignore
            
        Returns:
            Dictionary with linter results and any error
        """
        logger.info(f"Linting Robot test files (file: {file_path}, directory: {directory_path})")
        
        result = lint_robot_files(
            file_path=file_path,
            directory_path=directory_path,
            recursive=recursive,
            rules=rules,
            ignore_rules=ignore_rules or []
        )
        
        return result 