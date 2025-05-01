#!/usr/bin/env python
"""
MCP Tool: Robot Test Refactorer
Refactors .robot test files by consolidating redundant test steps, replacing hardcoded values,
or improving readability.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Union, Set
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import (
    find_robot_files,
    parse_robot_file,
    is_robot_file
)

logger = logging.getLogger('robot_tool.test_refactorer')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class RefactorAction(BaseModel):
    """Model for a refactor action."""
    type: str = Field(
        ...,
        description="Type of refactor action (extract_keyword, replace_hardcoded, rename, etc.)"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters specific to the action type"
    )

class RefactorRequest(BaseModel):
    """Request model for robot_test_refactorer tool."""
    file_path: str = Field(
        ...,
        description="Path to the .robot file to refactor"
    )
    actions: List[RefactorAction] = Field(
        ...,
        description="List of refactor actions to perform"
    )
    overwrite: bool = Field(
        False,
        description="Whether to overwrite the original file (otherwise creates a new file)"
    )

class RefactorResponse(BaseModel):
    """Response model for robot_test_refactorer tool."""
    original_file: str = Field(
        ...,
        description="Path to the original file"
    )
    refactored_file: str = Field(
        ...,
        description="Path to the refactored file"
    )
    changes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of changes made during refactoring"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def refactor_robot_file(
    file_path: str,
    actions: List[RefactorAction],
    overwrite: bool = False
) -> Dict[str, Any]:
    """
    Refactor a Robot Framework test file.
    
    Args:
        file_path: Path to the .robot file to refactor
        actions: List of refactor actions to perform
        overwrite: Whether to overwrite the original file
        
    Returns:
        Dictionary with refactoring results and any error
    """
    result = {
        "original_file": file_path,
        "refactored_file": None,
        "changes": [],
        "error": None
    }
    
    try:
        # Check if file exists and is a Robot Framework file
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {
                "original_file": file_path,
                "refactored_file": None,
                "changes": [],
                "error": f"File not found: {file_path}"
            }
        
        if not is_robot_file(file_path_obj):
            return {
                "original_file": file_path,
                "refactored_file": None,
                "changes": [],
                "error": f"Not a valid Robot Framework file: {file_path}"
            }
            
        # Read the original file content
        with open(file_path_obj, 'r', encoding='utf-8') as f:
            original_content = f.read()
            
        # Parse the file
        parsed_file = parse_robot_file(file_path_obj)
        
        # Apply refactoring actions
        refactored_content = original_content
        changes = []
        
        for action in actions:
            refactored_content, action_changes = apply_refactor_action(
                action, 
                refactored_content, 
                parsed_file
            )
            changes.extend(action_changes)
            
        # Create the output file
        if overwrite:
            output_file = file_path_obj
        else:
            # Create a new file with _refactored suffix
            base_name = file_path_obj.stem
            output_file = file_path_obj.with_name(f"{base_name}_refactored{file_path_obj.suffix}")
            
        # Write the refactored content
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(refactored_content)
            
        result["refactored_file"] = str(output_file)
        result["changes"] = changes
        
        logger.info(f"Refactored Robot Framework file: {file_path} -> {output_file}")
        return result
        
    except Exception as e:
        error_msg = f"Error refactoring Robot Framework file: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "original_file": file_path,
            "refactored_file": None,
            "changes": result["changes"],
            "error": error_msg
        }

def apply_refactor_action(
    action: RefactorAction,
    content: str,
    parsed_file: Dict[str, Any]
) -> tuple:
    """
    Apply a refactoring action to the file content.
    
    Args:
        action: The refactoring action to apply
        content: The current file content
        parsed_file: The parsed file structure
        
    Returns:
        Tuple of (refactored_content, changes)
    """
    action_type = action.type.lower()
    params = action.parameters
    changes = []
    
    if action_type == "extract_keyword":
        return extract_keyword(content, parsed_file, params, changes)
    elif action_type == "replace_hardcoded":
        return replace_hardcoded(content, parsed_file, params, changes)
    elif action_type == "rename":
        return rename_item(content, parsed_file, params, changes)
    elif action_type == "add_documentation":
        return add_documentation(content, parsed_file, params, changes)
    elif action_type == "add_tags":
        return add_tags(content, parsed_file, params, changes)
    else:
        raise ValueError(f"Unsupported refactor action type: {action_type}")

def extract_keyword(
    content: str,
    parsed_file: Dict[str, Any],
    params: Dict[str, Any],
    changes: List[Dict[str, Any]]
) -> tuple:
    """
    Extract repeated steps into a new keyword.
    
    Args:
        content: The current file content
        parsed_file: The parsed file structure
        params: Parameters for the action
        changes: List to append changes to
        
    Returns:
        Tuple of (refactored_content, changes)
    """
    # Required parameters
    steps = params.get("steps", [])
    keyword_name = params.get("keyword_name", "Extracted Keyword")
    instances = params.get("instances", [])  # List of test cases or line numbers
    arguments = params.get("arguments", [])
    
    if not steps or not keyword_name:
        raise ValueError("Missing required parameters for extract_keyword: steps and keyword_name")
        
    # Convert steps to a string with proper indentation
    steps_str = "\n    ".join(steps)
    
    # Create the new keyword
    keyword_def = f"{keyword_name}\n"
    if arguments:
        args_str = "    ".join([f"${{{arg}}}" for arg in arguments])
        keyword_def += f"    [Arguments]    {args_str}\n"
    keyword_def += f"    {steps_str}\n\n"
    
    # Find the Keywords section or create one
    if "*** Keywords ***" in content:
        content = re.sub(
            r"(\*\*\* Keywords \*\*\*\s*\n)",
            f"\\1{keyword_def}",
            content
        )
    else:
        content += f"\n*** Keywords ***\n{keyword_def}"
    
    changes.append({
        "type": "extract_keyword",
        "keyword_name": keyword_name,
        "steps_count": len(steps),
        "description": f"Extracted {len(steps)} steps into new keyword: {keyword_name}"
    })
    
    # Replace the steps in the specified instances
    for instance in instances:
        # Instance can be a test case name or a line range
        if isinstance(instance, str):
            # Instance is a test case name
            test_name = instance
            
            # Find the test case in the content
            test_match = re.search(
                rf"({test_name}\s*\n(?:[ \t]+.*\n)*)",
                content
            )
            
            if test_match:
                test_content = test_match.group(1)
                
                # Create pattern to match the steps
                steps_pattern = "\n    ".join([re.escape(step) for step in steps])
                steps_pattern = f"([ \t]+){steps_pattern}"
                
                # Replace the steps with the keyword call
                keyword_call = f"\\1{keyword_name}"
                if arguments:
                    keyword_call += "    " + "    ".join([f"${{{arg}}}" for arg in arguments])
                
                new_test_content = re.sub(
                    steps_pattern,
                    keyword_call,
                    test_content
                )
                
                # Replace the test case in the content
                content = content.replace(test_content, new_test_content)
                
                changes.append({
                    "type": "replace_steps",
                    "test_name": test_name,
                    "description": f"Replaced steps with call to {keyword_name} in test: {test_name}"
                })
        elif isinstance(instance, dict) and "line_range" in instance:
            # Instance is a line range
            start_line, end_line = instance["line_range"]
            lines = content.splitlines()
            
            if 0 <= start_line < len(lines) and 0 <= end_line < len(lines) and start_line <= end_line:
                # Replace the lines with the keyword call
                indent = re.match(r"^(\s*)", lines[start_line]).group(1)
                keyword_call = f"{indent}{keyword_name}"
                if arguments:
                    keyword_call += "    " + "    ".join([f"${{{arg}}}" for arg in arguments])
                
                lines[start_line:end_line+1] = [keyword_call]
                content = "\n".join(lines)
                
                changes.append({
                    "type": "replace_steps",
                    "line_range": [start_line, end_line],
                    "description": f"Replaced steps with call to {keyword_name} at lines {start_line}-{end_line}"
                })
    
    return content, changes

def replace_hardcoded(
    content: str,
    parsed_file: Dict[str, Any],
    params: Dict[str, Any],
    changes: List[Dict[str, Any]]
) -> tuple:
    """
    Replace hardcoded values with variables.
    
    Args:
        content: The current file content
        parsed_file: The parsed file structure
        params: Parameters for the action
        changes: List to append changes to
        
    Returns:
        Tuple of (refactored_content, changes)
    """
    # Required parameters
    values = params.get("values", {})
    
    if not values:
        raise ValueError("Missing required parameter for replace_hardcoded: values")
    
    # Create variables section if it doesn't exist
    if "*** Variables ***" not in content:
        if "*** Settings ***" in content:
            content = re.sub(
                r"(\*\*\* Settings \*\*\*.*?)(\n\s*\n\*\*\*|\Z)",
                f"\\1\n\n*** Variables ***\n\\2",
                content,
                flags=re.DOTALL
            )
        else:
            content = f"*** Variables ***\n\n{content}"
    
    # Add variables to the Variables section
    variables_section = ""
    for var_name, var_value in values.items():
        # Format the variable name
        if not var_name.startswith("${") and not var_name.startswith("@{") and not var_name.startswith("&{"):
            var_name = f"${{{var_name}}}"
        
        variables_section += f"{var_name}    {var_value}\n"
    
    content = re.sub(
        r"(\*\*\* Variables \*\*\*\s*\n)",
        f"\\1{variables_section}",
        content
    )
    
    # Replace the hardcoded values in the content
    for var_name, var_value in values.items():
        # Format the variable name
        if not var_name.startswith("${"):
            formatted_var_name = f"${{{var_name}}}"
        else:
            formatted_var_name = var_name
        
        # Escape special regex characters in the value
        escaped_value = re.escape(str(var_value))
        
        # Replace the value with the variable
        # Only replace if it's a standalone value (surrounded by whitespace, quotes, brackets, etc.)
        content = re.sub(
            rf"([^\w])({escaped_value})([^\w])",
            f"\\1{formatted_var_name}\\3",
            content
        )
        
        changes.append({
            "type": "replace_hardcoded",
            "variable": var_name,
            "value": var_value,
            "description": f"Replaced hardcoded value '{var_value}' with variable {var_name}"
        })
    
    return content, changes

def rename_item(
    content: str,
    parsed_file: Dict[str, Any],
    params: Dict[str, Any],
    changes: List[Dict[str, Any]]
) -> tuple:
    """
    Rename a test case, keyword, or variable.
    
    Args:
        content: The current file content
        parsed_file: The parsed file structure
        params: Parameters for the action
        changes: List to append changes to
        
    Returns:
        Tuple of (refactored_content, changes)
    """
    # Required parameters
    item_type = params.get("item_type", "").lower()  # test_case, keyword, variable
    old_name = params.get("old_name", "")
    new_name = params.get("new_name", "")
    
    if not item_type or not old_name or not new_name:
        raise ValueError("Missing required parameters for rename: item_type, old_name, and new_name")
    
    if item_type == "test_case":
        # Find the test case and rename it
        content = re.sub(
            f"^{re.escape(old_name)}\\s*$",
            new_name,
            content,
            flags=re.MULTILINE
        )
        
        changes.append({
            "type": "rename_test_case",
            "old_name": old_name,
            "new_name": new_name,
            "description": f"Renamed test case from '{old_name}' to '{new_name}'"
        })
        
    elif item_type == "keyword":
        # Find the keyword and rename it
        content = re.sub(
            f"^{re.escape(old_name)}\\s*$",
            new_name,
            content,
            flags=re.MULTILINE
        )
        
        # Also rename all references to the keyword
        content = re.sub(
            f"(\\s){re.escape(old_name)}(\\s|$)",
            f"\\1{new_name}\\2",
            content
        )
        
        changes.append({
            "type": "rename_keyword",
            "old_name": old_name,
            "new_name": new_name,
            "description": f"Renamed keyword from '{old_name}' to '{new_name}'"
        })
        
    elif item_type == "variable":
        # Format variable names
        old_var = old_name if old_name.startswith(("${", "@{", "&{")) else f"${{{old_name}}}"
        new_var = new_name if new_name.startswith(("${", "@{", "&{")) else f"${{{new_name}}}"
        
        # Update variable definition
        content = re.sub(
            f"^{re.escape(old_var)}\\s+",
            f"{new_var}    ",
            content,
            flags=re.MULTILINE
        )
        
        # Update variable references
        content = re.sub(
            re.escape(old_var),
            new_var,
            content
        )
        
        changes.append({
            "type": "rename_variable",
            "old_name": old_var,
            "new_name": new_var,
            "description": f"Renamed variable from '{old_var}' to '{new_var}'"
        })
    else:
        raise ValueError(f"Unsupported item_type for rename: {item_type}")
    
    return content, changes

def add_documentation(
    content: str,
    parsed_file: Dict[str, Any],
    params: Dict[str, Any],
    changes: List[Dict[str, Any]]
) -> tuple:
    """
    Add documentation to test cases or keywords.
    
    Args:
        content: The current file content
        parsed_file: The parsed file structure
        params: Parameters for the action
        changes: List to append changes to
        
    Returns:
        Tuple of (refactored_content, changes)
    """
    # Required parameters
    items = params.get("items", [])  # List of test cases or keywords to document
    
    if not items:
        raise ValueError("Missing required parameter for add_documentation: items")
    
    for item in items:
        item_name = item.get("name", "")
        doc_text = item.get("documentation", "")
        item_type = item.get("type", "test_case").lower()  # test_case or keyword
        
        if not item_name or not doc_text:
            continue
            
        # Find the item in the content
        item_match = re.search(
            rf"^{re.escape(item_name)}\s*\n",
            content,
            re.MULTILINE
        )
        
        if item_match:
            item_start = item_match.end()
            
            # Check if it already has a Documentation tag
            doc_match = re.search(
                r"^\s+\[Documentation\]",
                content[item_start:item_start+200],
                re.MULTILINE
            )
            
            if doc_match:
                # Update existing documentation
                doc_start = item_start + doc_match.start()
                doc_end = content.find("\n", doc_start)
                
                old_doc = content[doc_start:doc_end]
                new_doc = f"    [Documentation]    {doc_text}"
                
                content = content[:doc_start] + new_doc + content[doc_end:]
                
                changes.append({
                    "type": "update_documentation",
                    "item_name": item_name,
                    "item_type": item_type,
                    "description": f"Updated documentation for {item_type} '{item_name}'"
                })
            else:
                # Add new documentation as the first line after the item
                new_doc = f"    [Documentation]    {doc_text}\n"
                content = content[:item_start] + new_doc + content[item_start:]
                
                changes.append({
                    "type": "add_documentation",
                    "item_name": item_name,
                    "item_type": item_type,
                    "description": f"Added documentation to {item_type} '{item_name}'"
                })
    
    return content, changes

def add_tags(
    content: str,
    parsed_file: Dict[str, Any],
    params: Dict[str, Any],
    changes: List[Dict[str, Any]]
) -> tuple:
    """
    Add tags to test cases.
    
    Args:
        content: The current file content
        parsed_file: The parsed file structure
        params: Parameters for the action
        changes: List to append changes to
        
    Returns:
        Tuple of (refactored_content, changes)
    """
    # Required parameters
    tests = params.get("tests", [])  # List of test cases to tag
    
    if not tests:
        raise ValueError("Missing required parameter for add_tags: tests")
    
    for test in tests:
        test_name = test.get("name", "")
        tags = test.get("tags", [])
        
        if not test_name or not tags:
            continue
            
        # Find the test case in the content
        test_match = re.search(
            rf"^{re.escape(test_name)}\s*\n",
            content,
            re.MULTILINE
        )
        
        if test_match:
            test_start = test_match.end()
            
            # Check if it already has a Tags tag
            tags_match = re.search(
                r"^\s+\[Tags\]",
                content[test_start:test_start+200],
                re.MULTILINE
            )
            
            tags_str = "    ".join(tags)
            
            if tags_match:
                # Update existing tags
                tags_start = test_start + tags_match.start()
                tags_end = content.find("\n", tags_start)
                
                old_tags = content[tags_start:tags_end]
                new_tags = f"    [Tags]    {tags_str}"
                
                content = content[:tags_start] + new_tags + content[tags_end:]
                
                changes.append({
                    "type": "update_tags",
                    "test_name": test_name,
                    "tags": tags,
                    "description": f"Updated tags for test case '{test_name}'"
                })
            else:
                # Add new tags
                # Check if it has documentation first
                doc_match = re.search(
                    r"^\s+\[Documentation\]",
                    content[test_start:test_start+200],
                    re.MULTILINE
                )
                
                if doc_match:
                    # Add tags after documentation
                    doc_end = content.find("\n", test_start + doc_match.start())
                    new_tags = f"\n    [Tags]    {tags_str}"
                    content = content[:doc_end] + new_tags + content[doc_end:]
                else:
                    # Add tags as the first line after the test name
                    new_tags = f"    [Tags]    {tags_str}\n"
                    content = content[:test_start] + new_tags + content[test_start:]
                
                changes.append({
                    "type": "add_tags",
                    "test_name": test_name,
                    "tags": tags,
                    "description": f"Added tags to test case '{test_name}'"
                })
    
    return content, changes

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_test_refactorer(request: RefactorRequest) -> RefactorResponse:
        """
        Refactor a Robot Framework test file.
        
        Args:
            request: The request containing refactoring parameters
            
        Returns:
            Response with refactoring results and any error
        """
        logger.info(f"Received request to refactor Robot Framework file: {request.file_path}")
        
        try:
            result = refactor_robot_file(
                file_path=request.file_path,
                actions=request.actions,
                overwrite=request.overwrite
            )
            
            return RefactorResponse(
                original_file=result["original_file"],
                refactored_file=result["refactored_file"] or "",
                changes=result["changes"],
                error=result["error"]
            )
            
        except Exception as e:
            error_msg = f"Error in robot_test_refactorer: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return RefactorResponse(
                original_file=request.file_path,
                refactored_file="",
                changes=[],
                error=error_msg
            ) 