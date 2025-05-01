#!/usr/bin/env python
"""
MCP Tool: Robot Test Creator
Creates .robot test files from structured input or natural language prompts.
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
    is_robot_file
)
from src.config.config import (
    TEST_FILE_EXTENSIONS,
    SYSTEM_PROMPTS
)

logger = logging.getLogger('robot_tool.test_creator')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class TestCase(BaseModel):
    """Model for a test case."""
    name: str = Field(
        ...,
        description="Name of the test case"
    )
    documentation: Optional[str] = Field(
        None,
        description="Documentation for the test case"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for the test case"
    )
    setup: Optional[str] = Field(
        None,
        description="Setup keyword for the test case"
    )
    teardown: Optional[str] = Field(
        None,
        description="Teardown keyword for the test case"
    )
    steps: List[str] = Field(
        ...,
        description="Steps for the test case"
    )

class Keyword(BaseModel):
    """Model for a keyword."""
    name: str = Field(
        ...,
        description="Name of the keyword"
    )
    documentation: Optional[str] = Field(
        None,
        description="Documentation for the keyword"
    )
    arguments: List[str] = Field(
        default_factory=list,
        description="Arguments for the keyword"
    )
    steps: List[str] = Field(
        ...,
        description="Steps for the keyword"
    )

class Variable(BaseModel):
    """Model for a variable."""
    name: str = Field(
        ...,
        description="Name of the variable"
    )
    value: Any = Field(
        ...,
        description="Value of the variable"
    )

class TestCreatorRequest(BaseModel):
    """Request model for robot_test_creator tool."""
    output_file: str = Field(
        ...,
        description="Path to the output .robot file"
    )
    description: Optional[str] = Field(
        None,
        description="Description of the test suite to generate (natural language)"
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Settings for the test suite (e.g., Documentation, Default Tags, etc.)"
    )
    variables: List[Variable] = Field(
        default_factory=list,
        description="Variables to include in the test suite"
    )
    test_cases: List[TestCase] = Field(
        default_factory=list,
        description="Test cases to include in the test suite"
    )
    keywords: List[Keyword] = Field(
        default_factory=list,
        description="Keywords to include in the test suite"
    )
    libraries: List[str] = Field(
        default_factory=list,
        description="Libraries to import"
    )
    resource_files: List[str] = Field(
        default_factory=list,
        description="Resource files to import"
    )
    overwrite: bool = Field(
        False,
        description="Whether to overwrite an existing file"
    )

class TestCreatorResponse(BaseModel):
    """Response model for robot_test_creator tool."""
    file_path: Optional[str] = Field(
        None,
        description="Path to the created .robot file"
    )
    content: Optional[str] = Field(
        None,
        description="Content of the created .robot file"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def create_test_file(
    output_file: str,
    description: Optional[str] = None,
    settings: Dict[str, Any] = None,
    variables: List[Dict[str, Any]] = None,
    test_cases: List[Dict[str, Any]] = None,
    keywords: List[Dict[str, Any]] = None,
    libraries: List[str] = None,
    resource_files: List[str] = None,
    overwrite: bool = False
) -> Dict[str, Any]:
    """
    Create a .robot test file from structured input.
    
    Args:
        output_file: Path to the output .robot file
        description: Description of the test suite to generate
        settings: Settings for the test suite
        variables: Variables to include in the test suite
        test_cases: Test cases to include in the test suite
        keywords: Keywords to include in the test suite
        libraries: Libraries to import
        resource_files: Resource files to import
        overwrite: Whether to overwrite an existing file
        
    Returns:
        Dictionary with file path, content, and any error
    """
    result = {
        "file_path": None,
        "content": None,
        "error": None
    }
    
    try:
        # Set up parameters
        settings = settings or {}
        variables = variables or []
        test_cases = test_cases or []
        keywords = keywords or []
        libraries = libraries or []
        resource_files = resource_files or []
        
        # Convert dictionaries to model instances if needed
        variable_models = []
        for var in variables:
            if isinstance(var, dict):
                variable_models.append(Variable(**var))
            else:
                variable_models.append(var)
                
        test_case_models = []
        for tc in test_cases:
            if isinstance(tc, dict):
                test_case_models.append(TestCase(**tc))
            else:
                test_case_models.append(tc)
                
        keyword_models = []
        for kw in keywords:
            if isinstance(kw, dict):
                keyword_models.append(Keyword(**kw))
            else:
                keyword_models.append(kw)
        
        # Input validation
        output_path = Path(output_file)
        
        # Check if file exists
        if output_path.exists() and not overwrite:
            return {
                "file_path": None,
                "content": None,
                "error": f"File already exists: {output_file}. Set overwrite=True to overwrite."
            }
            
        # Check if output directory exists, create if needed
        output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
            
        # Handle natural language description if provided
        if description and not (test_cases or keywords):
            # Generate test cases from description
            generated_content = generate_from_description(description, libraries, resource_files)
            # Extract test cases, keywords, settings from generated content
            test_case_models = generated_content.get("test_cases", [])
            keyword_models = generated_content.get("keywords", [])
            settings.update(generated_content.get("settings", {}))
            libraries.extend(generated_content.get("libraries", []))
            resource_files.extend(generated_content.get("resource_files", []))
            variable_models.extend(generated_content.get("variables", []))
            
        # Generate .robot file content
        content = generate_robot_file_content(
            settings=settings,
            variables=variable_models,
            test_cases=test_case_models,
            keywords=keyword_models,
            libraries=libraries,
            resource_files=resource_files
        )
            
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info(f"Created Robot Framework test file: {output_path}")
        
        result["file_path"] = str(output_path)
        result["content"] = content
        return result
        
    except Exception as e:
        error_msg = f"Error creating Robot Framework test file: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "file_path": None,
            "content": None,
            "error": error_msg
        }

def generate_robot_file_content(
    settings: Dict[str, Any],
    variables: List[Variable],
    test_cases: List[TestCase],
    keywords: List[Keyword],
    libraries: List[str],
    resource_files: List[str]
) -> str:
    """
    Generate .robot file content from structured input.
    
    Args:
        settings: Settings for the test suite
        variables: Variables to include in the test suite
        test_cases: Test cases to include in the test suite
        keywords: Keywords to include in the test suite
        libraries: Libraries to import
        resource_files: Resource files to import
        
    Returns:
        String with .robot file content
    """
    content = []
    
    # *** Settings *** section
    if settings or libraries or resource_files:
        content.append("*** Settings ***")
        
        # Add documentation if provided
        if "Documentation" in settings:
            content.append(f"Documentation    {settings['Documentation']}")
            
        # Add libraries
        for library in libraries:
            content.append(f"Library    {library}")
            
        # Add resource files
        for resource in resource_files:
            content.append(f"Resource    {resource}")
            
        # Add other settings
        for key, value in settings.items():
            if key != "Documentation":  # Already handled
                content.append(f"{key}    {value}")
                
        content.append("")
    
    # *** Variables *** section
    if variables:
        content.append("*** Variables ***")
        for variable in variables:
            # Format value based on type
            if isinstance(variable.value, list):
                # List variable
                formatted_value = "    ".join([str(item) for item in variable.value])
                content.append(f"@{{{variable.name}}}    {formatted_value}")
            elif isinstance(variable.value, dict):
                # Dictionary variable
                content.append(f"&{{{variable.name}}}")
                for k, v in variable.value.items():
                    content.append(f"...    {k}    {v}")
            else:
                # Scalar variable
                content.append(f"${{{variable.name}}}    {variable.value}")
        content.append("")
    
    # *** Test Cases *** section
    if test_cases:
        content.append("*** Test Cases ***")
        for test_case in test_cases:
            content.append(test_case.name)
            
            # Add documentation if provided
            if test_case.documentation:
                content.append(f"    [Documentation]    {test_case.documentation}")
                
            # Add tags if provided
            if test_case.tags:
                content.append(f"    [Tags]    {' '.join(test_case.tags)}")
                
            # Add setup if provided
            if test_case.setup:
                content.append(f"    [Setup]    {test_case.setup}")
                
            # Add steps
            for step in test_case.steps:
                content.append(f"    {step}")
                
            # Add teardown if provided
            if test_case.teardown:
                content.append(f"    [Teardown]    {test_case.teardown}")
                
            content.append("")
    
    # *** Keywords *** section
    if keywords:
        content.append("*** Keywords ***")
        for keyword in keywords:
            content.append(keyword.name)
            
            # Add documentation if provided
            if keyword.documentation:
                content.append(f"    [Documentation]    {keyword.documentation}")
                
            # Add arguments if provided
            if keyword.arguments:
                content.append(f"    [Arguments]    {' '.join(['${' + arg + '}' for arg in keyword.arguments])}")
                
            # Add steps
            for step in keyword.steps:
                content.append(f"    {step}")
                
            content.append("")
    
    return "\n".join(content)

def generate_from_description(
    description: str,
    libraries: List[str],
    resource_files: List[str]
) -> Dict[str, Any]:
    """
    Generate test cases, keywords, and settings from a natural language description.
    
    This is a placeholder implementation. In a real system, this would use a language
    model or predefined templates to generate the test content.
    
    Args:
        description: Natural language description of the test suite
        libraries: Libraries to import
        resource_files: Resource files to import
        
    Returns:
        Dictionary with generated test cases, keywords, settings, etc.
    """
    # This is a placeholder implementation
    # In a real system, this would use a language model or predefined templates
    
    # For now, we'll just create a simple login test case
    result = {
        "test_cases": [
            TestCase(
                name="Simple Login Test",
                documentation="A simple test case to demonstrate login functionality",
                tags=["login", "demo"],
                steps=[
                    "Open Browser    ${URL}    ${BROWSER}",
                    "Input Text    id=username    ${USERNAME}",
                    "Input Password    id=password    ${PASSWORD}",
                    "Click Button    id=login-button",
                    "Page Should Contain    Welcome",
                    "Close Browser"
                ]
            )
        ],
        "keywords": [
            Keyword(
                name="Login With Valid Credentials",
                documentation="Performs login with valid credentials",
                arguments=["username", "password"],
                steps=[
                    "Input Text    id=username    ${username}",
                    "Input Password    id=password    ${password}",
                    "Click Button    id=login-button",
                    "Page Should Contain    Welcome"
                ]
            )
        ],
        "settings": {
            "Documentation": "Test suite generated from description: " + description,
            "Test Timeout": "1 minute"
        },
        "libraries": ["SeleniumLibrary"],
        "resource_files": [],
        "variables": [
            Variable(name="URL", value="https://example.com/login"),
            Variable(name="BROWSER", value="Chrome"),
            Variable(name="USERNAME", value="demo_user"),
            Variable(name="PASSWORD", value="demo_pass")
        ]
    }
    
    # Add user-provided libraries and resource files
    result["libraries"].extend([lib for lib in libraries if lib not in result["libraries"]])
    result["resource_files"].extend([res for res in resource_files if res not in result["resource_files"]])
    
    return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the robot_test_creator tool with the MCP server."""
    
    @mcp.tool()
    async def robot_test_creator(
        output_file: str,
        description: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
        variables: Optional[List[Dict[str, Any]]] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None,
        keywords: Optional[List[Dict[str, Any]]] = None,
        libraries: Optional[List[str]] = None,
        resource_files: Optional[List[str]] = None,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Create a .robot test file from structured input or natural language prompt.
        
        Args:
            output_file: Path to the output .robot file
            description: Description of the test suite to generate (natural language)
            settings: Settings for the test suite
            variables: Variables to include in the test suite
            test_cases: Test cases to include in the test suite
            keywords: Keywords to include in the test suite
            libraries: Libraries to import
            resource_files: Resource files to import
            overwrite: Whether to overwrite an existing file
            
        Returns:
            Dictionary with file path, content, and any error
        """
        logger.info(f"Creating Robot test file: {output_file}")
        
        result = create_test_file(
            output_file=output_file,
            description=description,
            settings=settings or {},
            variables=variables or [],
            test_cases=test_cases or [],
            keywords=keywords or [],
            libraries=libraries or [],
            resource_files=resource_files or [],
            overwrite=overwrite
        )
        
        return result 