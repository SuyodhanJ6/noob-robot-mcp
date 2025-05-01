#!/usr/bin/env python
"""
MCP Tool: Robot Test Coverage Analyzer
Analyzes which parts of the codebase are covered by test cases, integrating with code coverage tools.
"""

import os
import logging
import json
import re
import subprocess
import glob
from typing import List, Dict, Any, Optional, Set, Union, Tuple
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import (
    find_robot_files,
    parse_robot_file,
    is_robot_file,
    run_robot_command
)
from src.config.config import ROBOT_OUTPUT_DIR

logger = logging.getLogger('robot_tool.coverage_analyzer')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class RobotTestCoverageAnalyzerRequest(BaseModel):
    """Request model for robot_test_coverage_analyzer tool."""
    test_path: str = Field(
        ...,
        description="Path to a specific .robot file or directory containing .robot files to analyze"
    )
    source_path: str = Field(
        ...,
        description="Path to the source code directory to measure coverage for"
    )
    output_directory: Optional[str] = Field(
        None,
        description="Directory to store the coverage results"
    )
    coverage_tool: str = Field(
        "coverage.py",
        description="Coverage tool to use: 'coverage.py' or 'jacoco'"
    )
    include_pattern: Optional[str] = Field(
        None,
        description="Glob pattern for files to include in coverage analysis"
    )
    exclude_pattern: Optional[str] = Field(
        None,
        description="Glob pattern for files to exclude from coverage analysis"
    )
    branch_coverage: bool = Field(
        False,
        description="Whether to measure branch coverage instead of just line coverage"
    )
    report_format: str = Field(
        "json",
        description="Format for the coverage report: 'json', 'xml', 'html'"
    )

class CoverageFile(BaseModel):
    """Model for coverage information about a single file."""
    file_path: str = Field(..., description="Path to the file")
    total_lines: int = Field(..., description="Total number of lines in the file")
    covered_lines: int = Field(..., description="Number of lines covered by tests")
    missing_lines: List[int] = Field(default_factory=list, description="List of line numbers not covered by tests")
    coverage_percentage: float = Field(..., description="Percentage of lines covered (0-100)")

class CoverageModule(BaseModel):
    """Model for coverage information about a module."""
    module_name: str = Field(..., description="Name of the module")
    files: List[CoverageFile] = Field(default_factory=list, description="List of files in the module")
    total_lines: int = Field(..., description="Total number of lines in the module")
    covered_lines: int = Field(..., description="Number of lines covered by tests")
    coverage_percentage: float = Field(..., description="Percentage of lines covered (0-100)")

class RobotTestCoverageAnalyzerResponse(BaseModel):
    """Response model for robot_test_coverage_analyzer tool."""
    modules: List[CoverageModule] = Field(
        default_factory=list,
        description="List of modules with coverage information"
    )
    total_lines: int = Field(
        0,
        description="Total number of lines in the codebase"
    )
    covered_lines: int = Field(
        0,
        description="Number of lines covered by tests"
    )
    coverage_percentage: float = Field(
        0.0,
        description="Percentage of lines covered (0-100)"
    )
    uncovered_files: List[str] = Field(
        default_factory=list,
        description="List of files with no coverage"
    )
    report_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Paths to the generated report files"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def setup_coverage_py(
    source_path: str,
    output_directory: str,
    include_pattern: Optional[str] = None,
    exclude_pattern: Optional[str] = None,
    branch_coverage: bool = False
) -> Tuple[bool, str]:
    """
    Set up coverage.py configuration.
    
    Args:
        source_path: Path to the source code directory
        output_directory: Directory to store the coverage results
        include_pattern: Glob pattern for files to include
        exclude_pattern: Glob pattern for files to exclude
        branch_coverage: Whether to measure branch coverage
        
    Returns:
        Tuple of (success, rc_path or error message)
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)
        
        # Create .coveragerc file
        rc_path = os.path.join(output_directory, ".coveragerc")
        
        with open(rc_path, "w") as f:
            f.write("[run]\n")
            f.write(f"source = {source_path}\n")
            
            if include_pattern:
                f.write(f"include = {include_pattern}\n")
            
            if exclude_pattern:
                f.write(f"omit = {exclude_pattern}\n")
            
            if branch_coverage:
                f.write("branch = True\n")
                
            f.write("\n[report]\n")
            f.write("exclude_lines =\n")
            f.write("    pragma: no cover\n")
            f.write("    def __repr__\n")
            f.write("    raise NotImplementedError\n")
            f.write("    if __name__ == .__main__.:\n")
            f.write("    pass\n")
            f.write("    raise ImportError\n")
        
        return True, rc_path
        
    except Exception as e:
        logger.error(f"Error setting up coverage.py: {e}")
        return False, f"Error setting up coverage.py: {str(e)}"

def run_robot_with_coverage(
    test_path: str,
    rc_path: str,
    output_directory: str
) -> Tuple[bool, str, str]:
    """
    Run Robot Framework tests with coverage.py.
    
    Args:
        test_path: Path to the test file or directory
        rc_path: Path to the .coveragerc file
        output_directory: Directory to store the coverage results
        
    Returns:
        Tuple of (success, coverage_data_path, error message)
    """
    try:
        # Set up environment variables
        env = os.environ.copy()
        env["COVERAGE_FILE"] = os.path.join(output_directory, ".coverage")
        
        # Build the command
        cmd = [
            "coverage", "run",
            "--rcfile", rc_path,
            "-m", "robot",
            "--outputdir", output_directory,
            test_path
        ]
        
        # Run the command
        logger.info(f"Running Robot with coverage: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(timeout=300)
        
        if process.returncode != 0:
            return False, "", f"Error running Robot with coverage: {stderr}"
        
        coverage_data_path = os.path.join(output_directory, ".coverage")
        return True, coverage_data_path, ""
        
    except Exception as e:
        logger.error(f"Error running Robot with coverage: {e}")
        return False, "", f"Error running Robot with coverage: {str(e)}"

def generate_coverage_reports(
    coverage_data_path: str,
    output_directory: str,
    report_format: str
) -> Tuple[bool, Dict[str, str]]:
    """
    Generate coverage reports in the specified format.
    
    Args:
        coverage_data_path: Path to the coverage data file
        output_directory: Directory to store the reports
        report_format: Format for the reports
        
    Returns:
        Tuple of (success, dict of report paths)
    """
    try:
        report_files = {}
        
        # Generate JSON report
        if report_format == "json" or report_format == "all":
            json_path = os.path.join(output_directory, "coverage.json")
            cmd = ["coverage", "json", "-o", json_path]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(timeout=60)
            
            if process.returncode == 0:
                report_files["json"] = json_path
            else:
                logger.error(f"Error generating JSON report: {stderr}")
        
        # Generate XML report
        if report_format == "xml" or report_format == "all":
            xml_path = os.path.join(output_directory, "coverage.xml")
            cmd = ["coverage", "xml", "-o", xml_path]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(timeout=60)
            
            if process.returncode == 0:
                report_files["xml"] = xml_path
            else:
                logger.error(f"Error generating XML report: {stderr}")
        
        # Generate HTML report
        if report_format == "html" or report_format == "all":
            html_dir = os.path.join(output_directory, "html")
            os.makedirs(html_dir, exist_ok=True)
            
            cmd = ["coverage", "html", "-d", html_dir]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(timeout=60)
            
            if process.returncode == 0:
                report_files["html"] = os.path.join(html_dir, "index.html")
            else:
                logger.error(f"Error generating HTML report: {stderr}")
        
        return True, report_files
        
    except Exception as e:
        logger.error(f"Error generating coverage reports: {e}")
        return False, {}

def parse_coverage_json(json_path: str) -> Dict[str, Any]:
    """
    Parse coverage data from a JSON report.
    
    Args:
        json_path: Path to the JSON coverage report
        
    Returns:
        Dictionary with parsed coverage data
    """
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        
        return data
        
    except Exception as e:
        logger.error(f"Error parsing coverage JSON: {e}")
        return {}

def extract_modules_from_files(files_data: Dict[str, Any], source_path: str) -> List[Dict[str, Any]]:
    """
    Extract module information from coverage data.
    
    Args:
        files_data: Dictionary of file coverage data
        source_path: Path to the source code directory
        
    Returns:
        List of modules with coverage information
    """
    modules = {}
    
    for file_path, file_data in files_data.items():
        # Skip files outside the source path
        if not file_path.startswith(source_path):
            continue
        
        # Determine module name from the file path
        rel_path = os.path.relpath(file_path, source_path)
        parts = rel_path.split(os.sep)
        
        # Use the first directory as the module name
        module_name = parts[0] if len(parts) > 1 else "root"
        
        # Initialize module if not seen before
        if module_name not in modules:
            modules[module_name] = {
                "module_name": module_name,
                "files": [],
                "total_lines": 0,
                "covered_lines": 0,
                "coverage_percentage": 0.0
            }
        
        # Extract line coverage data
        total_lines = file_data.get("summary", {}).get("num_statements", 0)
        missing_lines = file_data.get("missing_lines", [])
        covered_lines = total_lines - len(missing_lines)
        
        # Calculate coverage percentage
        coverage_percentage = 0.0
        if total_lines > 0:
            coverage_percentage = (covered_lines / total_lines) * 100
        
        # Add file to module
        modules[module_name]["files"].append({
            "file_path": file_path,
            "total_lines": total_lines,
            "covered_lines": covered_lines,
            "missing_lines": missing_lines,
            "coverage_percentage": coverage_percentage
        })
        
        # Update module totals
        modules[module_name]["total_lines"] += total_lines
        modules[module_name]["covered_lines"] += covered_lines
    
    # Calculate module coverage percentages
    for module_name, module in modules.items():
        if module["total_lines"] > 0:
            module["coverage_percentage"] = (module["covered_lines"] / module["total_lines"]) * 100
    
    return list(modules.values())

def analyze_coverage_with_coverage_py(
    test_path: str,
    source_path: str,
    output_directory: Optional[str] = None,
    include_pattern: Optional[str] = None,
    exclude_pattern: Optional[str] = None,
    branch_coverage: bool = False,
    report_format: str = "json"
) -> Dict[str, Any]:
    """
    Analyze test coverage using coverage.py.
    
    Args:
        test_path: Path to the test file or directory
        source_path: Path to the source code directory
        output_directory: Directory to store the coverage results
        include_pattern: Glob pattern for files to include
        exclude_pattern: Glob pattern for files to exclude
        branch_coverage: Whether to measure branch coverage
        report_format: Format for the coverage report
        
    Returns:
        Dictionary with coverage analysis results
    """
    result = {
        "modules": [],
        "total_lines": 0,
        "covered_lines": 0,
        "coverage_percentage": 0.0,
        "uncovered_files": [],
        "report_files": {},
        "error": None
    }
    
    try:
        # Set default output directory if not provided
        if not output_directory:
            output_directory = os.path.join(ROBOT_OUTPUT_DIR, "coverage")
        
        # Setup coverage.py configuration
        success, rc_path_or_error = setup_coverage_py(
            source_path,
            output_directory,
            include_pattern,
            exclude_pattern,
            branch_coverage
        )
        
        if not success:
            return {**result, "error": rc_path_or_error}
        
        # Run Robot Framework tests with coverage
        success, coverage_data_path, error = run_robot_with_coverage(
            test_path,
            rc_path_or_error,
            output_directory
        )
        
        if not success:
            return {**result, "error": error}
        
        # Generate coverage reports
        success, report_files = generate_coverage_reports(
            coverage_data_path,
            output_directory,
            report_format
        )
        
        if not success or "json" not in report_files:
            return {**result, "error": "Failed to generate coverage reports", "report_files": report_files}
        
        # Parse coverage data from JSON report
        coverage_data = parse_coverage_json(report_files["json"])
        
        if not coverage_data:
            return {**result, "error": "Failed to parse coverage data", "report_files": report_files}
        
        # Extract modules from coverage data
        modules = extract_modules_from_files(coverage_data.get("files", {}), source_path)
        
        # Calculate overall coverage
        total_lines = sum(module["total_lines"] for module in modules)
        covered_lines = sum(module["covered_lines"] for module in modules)
        
        coverage_percentage = 0.0
        if total_lines > 0:
            coverage_percentage = (covered_lines / total_lines) * 100
        
        # Find uncovered files
        uncovered_files = []
        for module in modules:
            for file_data in module["files"]:
                if file_data["coverage_percentage"] == 0.0:
                    uncovered_files.append(file_data["file_path"])
        
        # Build the result
        result = {
            "modules": modules,
            "total_lines": total_lines,
            "covered_lines": covered_lines,
            "coverage_percentage": coverage_percentage,
            "uncovered_files": uncovered_files,
            "report_files": report_files,
            "error": None
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing coverage with coverage.py: {e}")
        return {**result, "error": f"Error analyzing coverage: {str(e)}"}

def setup_jacoco():
    """
    Set up JaCoCo for Java code coverage.
    This is a placeholder and would need to be implemented based on the project's requirements.
    """
    raise NotImplementedError("JaCoCo support is not implemented yet")

def analyze_test_coverage(
    test_path: str,
    source_path: str,
    output_directory: Optional[str] = None,
    coverage_tool: str = "coverage.py",
    include_pattern: Optional[str] = None,
    exclude_pattern: Optional[str] = None,
    branch_coverage: bool = False,
    report_format: str = "json"
) -> Dict[str, Any]:
    """
    Analyze which parts of the codebase are covered by test cases.
    
    Args:
        test_path: Path to the test file or directory
        source_path: Path to the source code directory
        output_directory: Directory to store the coverage results
        coverage_tool: Coverage tool to use
        include_pattern: Glob pattern for files to include
        exclude_pattern: Glob pattern for files to exclude
        branch_coverage: Whether to measure branch coverage
        report_format: Format for the coverage report
        
    Returns:
        Dictionary with coverage analysis results
    """
    if coverage_tool == "coverage.py":
        return analyze_coverage_with_coverage_py(
            test_path,
            source_path,
            output_directory,
            include_pattern,
            exclude_pattern,
            branch_coverage,
            report_format
        )
    elif coverage_tool == "jacoco":
        # This would need to be implemented
        raise NotImplementedError("JaCoCo support is not implemented yet")
    else:
        return {
            "modules": [],
            "total_lines": 0,
            "covered_lines": 0,
            "coverage_percentage": 0.0,
            "uncovered_files": [],
            "report_files": {},
            "error": f"Unsupported coverage tool: {coverage_tool}"
        }

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_test_coverage_analyzer(request: RobotTestCoverageAnalyzerRequest) -> RobotTestCoverageAnalyzerResponse:
        """
        Analyze which parts of the codebase are covered by test cases.
        
        Args:
            request: The request containing test and source paths
            
        Returns:
            Response with coverage analysis results
        """
        logger.info(f"Received request for Robot Framework test coverage analysis")
        
        try:
            result = analyze_test_coverage(
                test_path=request.test_path,
                source_path=request.source_path,
                output_directory=request.output_directory,
                coverage_tool=request.coverage_tool,
                include_pattern=request.include_pattern,
                exclude_pattern=request.exclude_pattern,
                branch_coverage=request.branch_coverage,
                report_format=request.report_format
            )
            
            return RobotTestCoverageAnalyzerResponse(
                modules=result["modules"],
                total_lines=result["total_lines"],
                covered_lines=result["covered_lines"],
                coverage_percentage=result["coverage_percentage"],
                uncovered_files=result["uncovered_files"],
                report_files=result["report_files"],
                error=result["error"]
            )
            
        except Exception as e:
            error_msg = f"Error in robot_test_coverage_analyzer: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return RobotTestCoverageAnalyzerResponse(
                modules=[],
                total_lines=0,
                covered_lines=0,
                coverage_percentage=0.0,
                uncovered_files=[],
                report_files={},
                error=error_msg
            ) 