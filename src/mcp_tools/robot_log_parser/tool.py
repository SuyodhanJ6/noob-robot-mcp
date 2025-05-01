#!/usr/bin/env python
"""
MCP Tool: Robot Log Parser
Parses Robot Framework test logs (output.xml, log.html) to extract relevant data.
"""

import os
import xml.etree.ElementTree as ET
import json
import re
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import parse_robot_output_xml

logger = logging.getLogger('robot_tool.log_parser')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class LogParserRequest(BaseModel):
    """Request model for robot_log_parser tool."""
    log_file_path: str = Field(
        ..., 
        description="Path to the output.xml or log.html file to parse"
    )
    include_keywords: bool = Field(
        True, 
        description="Whether to include keyword details in the parse results"
    )
    include_messages: bool = Field(
        True, 
        description="Whether to include log messages in the parse results"
    )
    filter_test_status: Optional[str] = Field(
        None, 
        description="Filter tests by status (PASS, FAIL, SKIP, etc.)"
    )
    filter_test_names: Optional[List[str]] = Field(
        None, 
        description="Filter tests by name (list of test names to include)"
    )
    filter_tags: Optional[List[str]] = Field(
        None, 
        description="Filter tests by tags (list of tags to include)"
    )

class TestResult(BaseModel):
    """Model for a test result."""
    name: str = Field(..., description="Name of the test")
    status: str = Field(..., description="Status of the test (PASS, FAIL, SKIP, etc.)")
    start_time: str = Field(..., description="Start time of the test")
    end_time: str = Field(..., description="End time of the test")
    elapsed_time: float = Field(..., description="Elapsed time in seconds")
    tags: List[str] = Field(default_factory=list, description="Tags for the test")
    message: Optional[str] = Field(None, description="Message for the test (if failed)")
    keywords: Optional[List[Dict[str, Any]]] = Field(None, description="Keywords executed in the test")
    messages: Optional[List[Dict[str, Any]]] = Field(None, description="Log messages from the test")

class SuiteResult(BaseModel):
    """Model for a suite result."""
    name: str = Field(..., description="Name of the suite")
    status: str = Field(..., description="Status of the suite (PASS, FAIL, SKIP, etc.)")
    start_time: str = Field(..., description="Start time of the suite")
    end_time: str = Field(..., description="End time of the suite")
    elapsed_time: float = Field(..., description="Elapsed time in seconds")
    message: Optional[str] = Field(None, description="Message for the suite (if failed)")
    tests: List[TestResult] = Field(default_factory=list, description="Tests in the suite")
    suites: List[Any] = Field(default_factory=list, description="Sub-suites in the suite")

class LogParserResponse(BaseModel):
    """Response model for robot_log_parser tool."""
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of test results (passed, failed, skipped, etc.)"
    )
    suite: Optional[SuiteResult] = Field(
        None,
        description="Results of the root suite and its children"
    )
    stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Statistics from the test execution"
    )
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Errors from the test execution"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def parse_log_file(
    log_file_path: str,
    include_keywords: bool = True,
    include_messages: bool = True,
    filter_test_status: Optional[str] = None,
    filter_test_names: Optional[List[str]] = None,
    filter_tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Parse Robot Framework test logs (output.xml, log.html).
    
    Args:
        log_file_path: Path to the log file to parse
        include_keywords: Whether to include keyword details
        include_messages: Whether to include log messages
        filter_test_status: Filter tests by status
        filter_test_names: Filter tests by name
        filter_tags: Filter tests by tags
        
    Returns:
        Dictionary with parsed data and any error
    """
    result = {
        "summary": {},
        "suite": None,
        "stats": {},
        "errors": [],
        "error": None
    }
    
    try:
        # Check if file exists
        file_path = Path(log_file_path)
        if not file_path.exists():
            return {
                "summary": {},
                "suite": None,
                "stats": {},
                "errors": [],
                "error": f"File not found: {log_file_path}"
            }
            
        # Check file extension
        if file_path.suffix.lower() == '.xml':
            # Parse output.xml
            parsed_data = parse_output_xml(
                file_path,
                include_keywords,
                include_messages,
                filter_test_status,
                filter_test_names,
                filter_tags
            )
        elif file_path.suffix.lower() == '.html':
            # Parse log.html
            parsed_data = parse_log_html(
                file_path,
                include_keywords,
                include_messages,
                filter_test_status,
                filter_test_names,
                filter_tags
            )
        else:
            return {
                "summary": {},
                "suite": None,
                "stats": {},
                "errors": [],
                "error": f"Unsupported file type: {file_path.suffix}. Only .xml and .html are supported."
            }
            
        result.update(parsed_data)
        logger.info(f"Successfully parsed Robot Framework log file: {log_file_path}")
        return result
        
    except Exception as e:
        error_msg = f"Error parsing Robot Framework log file: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "summary": {},
            "suite": None,
            "stats": {},
            "errors": [],
            "error": error_msg
        }

def parse_output_xml(
    file_path: Path,
    include_keywords: bool,
    include_messages: bool,
    filter_test_status: Optional[str],
    filter_test_names: Optional[List[str]],
    filter_tags: Optional[List[str]]
) -> Dict[str, Any]:
    """
    Parse Robot Framework output.xml file.
    
    Args:
        file_path: Path to the output.xml file
        include_keywords: Whether to include keyword details
        include_messages: Whether to include log messages
        filter_test_status: Filter tests by status
        filter_test_names: Filter tests by name
        filter_tags: Filter tests by tags
        
    Returns:
        Dictionary with parsed data
    """
    try:
        # Use the existing helper function to parse the XML
        parsed_data = parse_robot_output_xml(file_path)
        
        # Extract the root suite
        root_suite = extract_suite_data(parsed_data["suite"], include_keywords, include_messages)
        
        # Apply filters
        filtered_suite = filter_suite(
            root_suite,
            filter_test_status,
            filter_test_names,
            filter_tags
        )
        
        # Update parsed data with filtered suite
        parsed_data["suite"] = filtered_suite
        
        # Update summary based on filtered suite
        summary = calculate_summary(filtered_suite)
        parsed_data["summary"] = summary
        
        return parsed_data
        
    except Exception as e:
        logger.error(f"Error parsing output.xml: {e}")
        raise

def parse_log_html(
    file_path: Path,
    include_keywords: bool,
    include_messages: bool,
    filter_test_status: Optional[str],
    filter_test_names: Optional[List[str]],
    filter_tags: Optional[List[str]]
) -> Dict[str, Any]:
    """
    Parse Robot Framework log.html file.
    
    Args:
        file_path: Path to the log.html file
        include_keywords: Whether to include keyword details
        include_messages: Whether to include log messages
        filter_test_status: Filter tests by status
        filter_test_names: Filter tests by name
        filter_tags: Filter tests by tags
        
    Returns:
        Dictionary with parsed data
    """
    try:
        # Read the log.html file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Extract the data model from the HTML
        match = re.search(r'window\.output\s*=\s*({.*?});', content, re.DOTALL)
        if not match:
            raise ValueError("Could not find output data in log.html")
            
        json_str = match.group(1)
        
        # Clean up the JS object to make it valid JSON
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)  # Add quotes to keys
        json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
        
        # Parse the JSON
        data = json.loads(json_str)
        
        # Extract relevant data from the JavaScript model
        # This is a simplified version, as the actual structure is complex
        suite_data = {
            "name": data.get("suite", {}).get("name", ""),
            "status": "PASS" if data.get("stats", {}).get("fail", 0) == 0 else "FAIL",
            "start_time": "",
            "end_time": "",
            "elapsed_time": 0,
            "tests": []
        }
        
        # Extract tests
        for test_id, test_data in data.get("tests", {}).items():
            test = {
                "name": test_data.get("name", ""),
                "status": test_data.get("status", ""),
                "start_time": "",
                "end_time": "",
                "elapsed_time": 0,
                "tags": test_data.get("tags", []),
                "message": test_data.get("message", "")
            }
            
            # Add keywords if included
            if include_keywords and "keywords" in test_data:
                test["keywords"] = extract_keywords(test_data["keywords"], include_messages)
                
            suite_data["tests"].append(test)
            
        # Apply filters
        filtered_suite = filter_suite(
            suite_data,
            filter_test_status,
            filter_test_names,
            filter_tags
        )
        
        # Calculate summary
        summary = calculate_summary(filtered_suite)
        
        return {
            "summary": summary,
            "suite": filtered_suite,
            "stats": data.get("stats", {}),
            "errors": data.get("errors", [])
        }
        
    except Exception as e:
        logger.error(f"Error parsing log.html: {e}")
        raise

def extract_suite_data(
    suite: Dict[str, Any],
    include_keywords: bool,
    include_messages: bool
) -> Dict[str, Any]:
    """
    Extract suite data from the parsed output.
    
    Args:
        suite: The suite data from parsed output
        include_keywords: Whether to include keyword details
        include_messages: Whether to include log messages
        
    Returns:
        Dictionary with suite data
    """
    # Extract basic suite info
    result = {
        "name": suite.get("name", ""),
        "status": suite.get("status", ""),
        "start_time": suite.get("start_time", ""),
        "end_time": suite.get("end_time", ""),
        "elapsed_time": suite.get("elapsed_time", 0),
        "message": suite.get("message", ""),
        "tests": [],
        "suites": []
    }
    
    # Extract tests
    for test in suite.get("tests", []):
        test_data = {
            "name": test.get("name", ""),
            "status": test.get("status", ""),
            "start_time": test.get("start_time", ""),
            "end_time": test.get("end_time", ""),
            "elapsed_time": test.get("elapsed_time", 0),
            "tags": test.get("tags", []),
            "message": test.get("message", "")
        }
        
        # Add keywords if included
        if include_keywords and "keywords" in test:
            test_data["keywords"] = extract_keywords(test.get("keywords", []), include_messages)
            
        # Add messages if included
        if include_messages and "messages" in test:
            test_data["messages"] = test.get("messages", [])
            
        result["tests"].append(test_data)
        
    # Recursively extract sub-suites
    for sub_suite in suite.get("suites", []):
        result["suites"].append(extract_suite_data(sub_suite, include_keywords, include_messages))
        
    return result

def extract_keywords(
    keywords: List[Dict[str, Any]],
    include_messages: bool
) -> List[Dict[str, Any]]:
    """
    Extract keyword data from the parsed output.
    
    Args:
        keywords: The keyword data from parsed output
        include_messages: Whether to include log messages
        
    Returns:
        List of dictionaries with keyword data
    """
    result = []
    
    for keyword in keywords:
        keyword_data = {
            "name": keyword.get("name", ""),
            "type": keyword.get("type", ""),
            "status": keyword.get("status", ""),
            "start_time": keyword.get("start_time", ""),
            "end_time": keyword.get("end_time", ""),
            "elapsed_time": keyword.get("elapsed_time", 0),
            "arguments": keyword.get("arguments", [])
        }
        
        # Add messages if included
        if include_messages and "messages" in keyword:
            keyword_data["messages"] = keyword.get("messages", [])
            
        # Recursively extract sub-keywords
        if "keywords" in keyword:
            keyword_data["keywords"] = extract_keywords(keyword.get("keywords", []), include_messages)
            
        result.append(keyword_data)
        
    return result

def filter_suite(
    suite: Dict[str, Any],
    filter_test_status: Optional[str],
    filter_test_names: Optional[List[str]],
    filter_tags: Optional[List[str]]
) -> Dict[str, Any]:
    """
    Filter suite data based on provided filters.
    
    Args:
        suite: The suite data to filter
        filter_test_status: Filter tests by status
        filter_test_names: Filter tests by name
        filter_tags: Filter tests by tags
        
    Returns:
        Filtered suite data
    """
    # Create a copy of the suite to avoid modifying the original
    filtered_suite = suite.copy()
    filtered_tests = []
    
    # Filter tests
    for test in suite.get("tests", []):
        # Check status filter
        if filter_test_status and test.get("status", "") != filter_test_status:
            continue
            
        # Check name filter
        if filter_test_names and test.get("name", "") not in filter_test_names:
            continue
            
        # Check tag filter
        if filter_tags:
            test_tags = test.get("tags", [])
            if not any(tag in test_tags for tag in filter_tags):
                continue
                
        # Include the test if it passes all filters
        filtered_tests.append(test)
        
    # Update tests in the suite
    filtered_suite["tests"] = filtered_tests
    
    # Recursively filter sub-suites
    filtered_suites = []
    for sub_suite in suite.get("suites", []):
        filtered_sub_suite = filter_suite(
            sub_suite,
            filter_test_status,
            filter_test_names,
            filter_tags
        )
        
        # Only include the sub-suite if it has tests after filtering
        if filtered_sub_suite.get("tests") or filtered_sub_suite.get("suites"):
            filtered_suites.append(filtered_sub_suite)
            
    # Update suites in the suite
    filtered_suite["suites"] = filtered_suites
    
    return filtered_suite

def calculate_summary(suite: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate summary statistics for a suite.
    
    Args:
        suite: The suite data to calculate summary for
        
    Returns:
        Dictionary with summary statistics
    """
    summary = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "elapsed_time": suite.get("elapsed_time", 0)
    }
    
    # Count tests in this suite
    for test in suite.get("tests", []):
        summary["total"] += 1
        
        status = test.get("status", "").upper()
        if status == "PASS":
            summary["passed"] += 1
        elif status == "FAIL":
            summary["failed"] += 1
        elif status == "SKIP":
            summary["skipped"] += 1
            
    # Recursively count tests in sub-suites
    for sub_suite in suite.get("suites", []):
        sub_summary = calculate_summary(sub_suite)
        summary["total"] += sub_summary["total"]
        summary["passed"] += sub_summary["passed"]
        summary["failed"] += sub_summary["failed"]
        summary["skipped"] += sub_summary["skipped"]
        
    return summary

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_log_parser(
        log_file_path: str,
        include_keywords: bool = True,
        include_messages: bool = True,
        filter_test_status: Optional[str] = None,
        filter_test_names: Optional[List[str]] = None,
        filter_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Parse Robot Framework test logs (output.xml, log.html).
        
        Args:
            log_file_path: Path to the output.xml or log.html file to parse
            include_keywords: Whether to include keyword details in the parse results (default: True)
            include_messages: Whether to include log messages in the parse results (default: True)
            filter_test_status: Filter tests by status (PASS, FAIL, SKIP, etc.) (optional)
            filter_test_names: Filter tests by name (list of test names to include) (optional)
            filter_tags: Filter tests by tags (list of tags to include) (optional)
            
        Returns:
            Response with parsed data and any error
        """
        logger.info(f"Received request to parse Robot Framework log file: {log_file_path}")
        
        try:
            # Log parameters for debugging
            logger.debug(f"Parameters: log_file_path={log_file_path}, "
                        f"include_keywords={include_keywords}, "
                        f"include_messages={include_messages}, "
                        f"filter_test_status={filter_test_status}, "
                        f"filter_test_names={filter_test_names}, "
                        f"filter_tags={filter_tags}")
            
            result = parse_log_file(
                log_file_path=log_file_path,
                include_keywords=include_keywords,
                include_messages=include_messages,
                filter_test_status=filter_test_status,
                filter_test_names=filter_test_names,
                filter_tags=filter_tags
            )
            
            # Return as dictionary for maximum compatibility
            return {
                "summary": result["summary"],
                "suite": result["suite"],
                "stats": result["stats"],
                "errors": result["errors"],
                "error": result["error"]
            }
            
        except Exception as e:
            error_msg = f"Error in robot_log_parser: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "summary": {},
                "suite": None,
                "stats": {},
                "errors": [],
                "error": error_msg
            } 