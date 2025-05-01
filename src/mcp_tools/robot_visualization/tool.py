#!/usr/bin/env python
"""
MCP Tool: Robot Visualization
Visualizes test case execution flow, keyword usage, or coverage.
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from io import BytesIO
import base64

from src.utils.helpers import (
    find_robot_files,
    parse_robot_file,
    is_robot_file,
    parse_robot_output_xml
)
from src.config.config import ROBOT_OUTPUT_DIR, ROBOT_REPORT_DIR

logger = logging.getLogger('robot_tool.visualization')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class RobotVisualizationRequest(BaseModel):
    """Request model for robot_visualization tool."""
    visualization_type: str = Field(
        ...,
        description="Type of visualization: 'execution_flow', 'keyword_usage', 'coverage', or 'test_duration'"
    )
    file_path: Optional[str] = Field(
        None,
        description="Path to a specific .robot file to visualize"
    )
    output_xml_path: Optional[str] = Field(
        None,
        description="Path to output.xml file for execution analysis"
    )
    directory_path: Optional[str] = Field(
        None,
        description="Path to a directory containing .robot files"
    )
    output_format: str = Field(
        "png",
        description="Format of the visualization output (png, svg, json)"
    )
    limit: Optional[int] = Field(
        None,
        description="Limit number of items in visualization"
    )

class RobotVisualizationResponse(BaseModel):
    """Response model for robot_visualization tool."""
    visualization_data: str = Field(
        "",
        description="Base64 encoded visualization data or JSON data"
    )
    visualization_type: str = Field(
        "",
        description="Type of visualization generated"
    )
    format: str = Field(
        "",
        description="Format of the visualization (png, svg, json)"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def generate_execution_flow_visualization(
    output_xml_path: Path,
    output_format: str = "png",
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generate a visualization of test execution flow from output.xml.
    
    Args:
        output_xml_path: Path to output.xml file
        output_format: Format of the visualization output
        limit: Limit number of nodes in the graph
        
    Returns:
        Dictionary with visualization data and metadata
    """
    try:
        if not output_xml_path.exists():
            return {
                "error": f"Output XML file not found: {output_xml_path}"
            }
        
        # Parse the output XML
        execution_data = parse_robot_output_xml(output_xml_path)
        
        # Create directed graph
        G = nx.DiGraph()
        
        # Process test execution data
        nodes = []
        edges = []
        
        for test in execution_data.get("tests", []):
            test_name = test.get("name", "Unknown Test")
            nodes.append(test_name)
            
            # Add keyword steps
            for keyword in test.get("keywords", []):
                keyword_name = keyword.get("name", "Unknown Keyword")
                nodes.append(keyword_name)
                edges.append((test_name, keyword_name))
                
                # Add nested keywords
                for nested in keyword.get("keywords", []):
                    nested_name = nested.get("name", "Unknown Nested Keyword")
                    nodes.append(nested_name)
                    edges.append((keyword_name, nested_name))
        
        # Limit the number of nodes if requested
        if limit and len(nodes) > limit:
            nodes = nodes[:limit]
            edges = [e for e in edges if e[0] in nodes and e[1] in nodes]
        
        # Add nodes and edges to graph
        for node in nodes:
            G.add_node(node)
        for edge in edges:
            G.add_edge(edge[0], edge[1])
        
        # Create visualization
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color='lightblue', 
                node_size=1500, edge_color='gray', arrows=True, 
                font_size=8, font_weight='bold')
        plt.title("Test Execution Flow")
        
        # Save to buffer
        buffer = BytesIO()
        plt.savefig(buffer, format=output_format)
        plt.close()
        
        # Encode as base64
        buffer.seek(0)
        img_encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return {
            "visualization_data": img_encoded,
            "visualization_type": "execution_flow",
            "format": output_format
        }
        
    except Exception as e:
        logger.error(f"Error generating execution flow visualization: {e}")
        return {
            "error": f"Error generating execution flow visualization: {str(e)}"
        }

def generate_keyword_usage_visualization(
    robot_files: List[Path],
    output_format: str = "png",
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generate a visualization of keyword usage across test files.
    
    Args:
        robot_files: List of Robot Framework files
        output_format: Format of the visualization output
        limit: Limit number of keywords in visualization
        
    Returns:
        Dictionary with visualization data and metadata
    """
    try:
        # Extract keywords from files
        keywords = {}
        for file_path in robot_files:
            parsed_file = parse_robot_file(file_path)
            
            # Process test cases for keywords
            for test in parsed_file.get("test_cases", []):
                for step in test.get("steps", []):
                    keyword = step.get("keyword", "")
                    if keyword:
                        keywords[keyword] = keywords.get(keyword, 0) + 1
        
        # Sort keywords by usage count
        sorted_keywords = dict(sorted(keywords.items(), key=lambda x: x[1], reverse=True))
        
        # Limit the number of keywords if requested
        if limit:
            sorted_keywords = dict(list(sorted_keywords.items())[:limit])
        
        # Create visualization
        plt.figure(figsize=(12, 8))
        plt.bar(sorted_keywords.keys(), sorted_keywords.values(), color='skyblue')
        plt.xlabel('Keywords')
        plt.ylabel('Usage Count')
        plt.title('Keyword Usage in Robot Framework Tests')
        plt.xticks(rotation=90)
        plt.tight_layout()
        
        # Save to buffer
        buffer = BytesIO()
        plt.savefig(buffer, format=output_format)
        plt.close()
        
        # Encode as base64
        buffer.seek(0)
        img_encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return {
            "visualization_data": img_encoded,
            "visualization_type": "keyword_usage",
            "format": output_format
        }
        
    except Exception as e:
        logger.error(f"Error generating keyword usage visualization: {e}")
        return {
            "error": f"Error generating keyword usage visualization: {str(e)}"
        }

def generate_test_duration_visualization(
    output_xml_path: Path,
    output_format: str = "png",
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generate a visualization of test case durations.
    
    Args:
        output_xml_path: Path to output.xml file
        output_format: Format of the visualization output
        limit: Limit number of test cases in visualization
        
    Returns:
        Dictionary with visualization data and metadata
    """
    try:
        if not output_xml_path.exists():
            return {
                "error": f"Output XML file not found: {output_xml_path}"
            }
        
        # Parse the output XML
        execution_data = parse_robot_output_xml(output_xml_path)
        
        # Extract test durations
        test_durations = {}
        for test in execution_data.get("tests", []):
            test_name = test.get("name", "Unknown Test")
            duration = test.get("elapsed_time", 0)
            test_durations[test_name] = duration
        
        # Sort by duration
        sorted_durations = dict(sorted(test_durations.items(), key=lambda x: x[1], reverse=True))
        
        # Limit the number of tests if requested
        if limit:
            sorted_durations = dict(list(sorted_durations.items())[:limit])
        
        # Create visualization
        plt.figure(figsize=(12, 8))
        plt.barh(list(sorted_durations.keys()), list(sorted_durations.values()), color='salmon')
        plt.xlabel('Duration (seconds)')
        plt.ylabel('Test Cases')
        plt.title('Test Case Durations')
        plt.tight_layout()
        
        # Save to buffer
        buffer = BytesIO()
        plt.savefig(buffer, format=output_format)
        plt.close()
        
        # Encode as base64
        buffer.seek(0)
        img_encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return {
            "visualization_data": img_encoded,
            "visualization_type": "test_duration",
            "format": output_format
        }
        
    except Exception as e:
        logger.error(f"Error generating test duration visualization: {e}")
        return {
            "error": f"Error generating test duration visualization: {str(e)}"
        }

def generate_coverage_visualization(
    robot_files: List[Path],
    output_format: str = "png"
) -> Dict[str, Any]:
    """
    Generate a visualization of test coverage.
    
    Args:
        robot_files: List of Robot Framework files
        output_format: Format of the visualization output
        
    Returns:
        Dictionary with visualization data and metadata
    """
    try:
        # Extract coverage data
        coverage_data = {
            "total_files": len(robot_files),
            "total_test_cases": 0,
            "total_keywords": 0,
            "files_by_type": {},
            "test_cases_by_tag": {}
        }
        
        for file_path in robot_files:
            file_type = file_path.suffix
            coverage_data["files_by_type"][file_type] = coverage_data["files_by_type"].get(file_type, 0) + 1
            
            parsed_file = parse_robot_file(file_path)
            
            # Count test cases
            test_cases = parsed_file.get("test_cases", [])
            coverage_data["total_test_cases"] += len(test_cases)
            
            # Count keywords
            keywords = parsed_file.get("keywords", [])
            coverage_data["total_keywords"] += len(keywords)
            
            # Group test cases by tags
            for test in test_cases:
                for tag in test.get("tags", []):
                    if tag not in coverage_data["test_cases_by_tag"]:
                        coverage_data["test_cases_by_tag"][tag] = 0
                    coverage_data["test_cases_by_tag"][tag] += 1
        
        # Create visualization
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        
        # Files by type
        ax1.pie(coverage_data["files_by_type"].values(), labels=coverage_data["files_by_type"].keys(), autopct='%1.1f%%')
        ax1.set_title('Files by Type')
        
        # Test cases vs keywords
        ax2.bar(['Test Cases', 'Keywords'], [coverage_data["total_test_cases"], coverage_data["total_keywords"]], color=['blue', 'green'])
        ax2.set_title('Test Cases vs Keywords')
        
        # Test cases by tag
        tags = list(coverage_data["test_cases_by_tag"].keys())
        counts = list(coverage_data["test_cases_by_tag"].values())
        if tags:
            ax3.barh(tags, counts, color='orange')
            ax3.set_title('Test Cases by Tag')
        else:
            ax3.text(0.5, 0.5, 'No tags found', horizontalalignment='center', verticalalignment='center')
            ax3.set_title('Test Cases by Tag')
        
        # Coverage summary
        ax4.axis('off')
        summary = (
            f"Total Files: {coverage_data['total_files']}\n"
            f"Total Test Cases: {coverage_data['total_test_cases']}\n"
            f"Total Keywords: {coverage_data['total_keywords']}\n"
            f"Average Test Cases per File: {coverage_data['total_test_cases'] / max(1, coverage_data['total_files']):.2f}"
        )
        ax4.text(0.1, 0.5, summary, verticalalignment='center')
        ax4.set_title('Coverage Summary')
        
        plt.tight_layout()
        
        # Save to buffer
        buffer = BytesIO()
        plt.savefig(buffer, format=output_format)
        plt.close()
        
        # Encode as base64
        buffer.seek(0)
        img_encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return {
            "visualization_data": img_encoded,
            "visualization_type": "coverage",
            "format": output_format
        }
        
    except Exception as e:
        logger.error(f"Error generating coverage visualization: {e}")
        return {
            "error": f"Error generating coverage visualization: {str(e)}"
        }

def create_robot_visualization(
    visualization_type: str,
    file_path: Optional[str] = None,
    output_xml_path: Optional[str] = None,
    directory_path: Optional[str] = None,
    output_format: str = "png",
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a visualization of Robot Framework test data.
    
    Args:
        visualization_type: Type of visualization to generate
        file_path: Path to a specific .robot file
        output_xml_path: Path to output.xml file
        directory_path: Path to a directory containing .robot files
        output_format: Format of the visualization output
        limit: Limit number of items in visualization
        
    Returns:
        Dictionary with visualization data and metadata
    """
    try:
        # Validate output format
        if output_format not in ["png", "svg", "json"]:
            return {
                "error": f"Unsupported output format: {output_format}. Use 'png', 'svg', or 'json'."
            }
        
        # Get robot files
        robot_files = []
        
        if file_path:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return {"error": f"File not found: {file_path}"}
            
            if not is_robot_file(file_path_obj):
                return {"error": f"Not a valid Robot Framework file: {file_path}"}
                
            robot_files = [file_path_obj]
            
        elif directory_path:
            dir_path = Path(directory_path)
            if not dir_path.exists() or not dir_path.is_dir():
                return {"error": f"Directory not found: {directory_path}"}
                
            robot_files = find_robot_files(dir_path, recursive=True)
            
            if not robot_files:
                return {"error": f"No Robot Framework files found in {directory_path}"}
                
        # Validate output_xml_path if needed
        if visualization_type in ["execution_flow", "test_duration"]:
            if not output_xml_path:
                # Try to find the latest output.xml in the default output directory
                output_dir = Path(ROBOT_OUTPUT_DIR)
                output_xml_files = list(output_dir.glob("output*.xml"))
                if not output_xml_files:
                    return {"error": "No output.xml file found. Please specify output_xml_path."}
                
                # Sort by modification time and get the most recent
                output_xml_path = str(sorted(output_xml_files, key=os.path.getmtime, reverse=True)[0])
            
            output_xml_path_obj = Path(output_xml_path)
            if not output_xml_path_obj.exists():
                return {"error": f"Output XML file not found: {output_xml_path}"}
        
        # Generate visualization based on type
        if visualization_type == "execution_flow":
            return generate_execution_flow_visualization(
                Path(output_xml_path),
                output_format,
                limit
            )
            
        elif visualization_type == "keyword_usage":
            if not robot_files:
                return {"error": "No Robot Framework files specified. Please provide file_path or directory_path."}
                
            return generate_keyword_usage_visualization(
                robot_files,
                output_format,
                limit
            )
            
        elif visualization_type == "test_duration":
            return generate_test_duration_visualization(
                Path(output_xml_path),
                output_format,
                limit
            )
            
        elif visualization_type == "coverage":
            if not robot_files:
                return {"error": "No Robot Framework files specified. Please provide file_path or directory_path."}
                
            return generate_coverage_visualization(
                robot_files,
                output_format
            )
            
        else:
            return {"error": f"Unsupported visualization type: {visualization_type}"}
            
    except Exception as e:
        logger.error(f"Error creating visualization: {e}")
        return {"error": f"Error creating visualization: {str(e)}"}

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_visualization(request: RobotVisualizationRequest) -> RobotVisualizationResponse:
        """
        Visualize Robot Framework test case execution flow, keyword usage, or coverage.
        
        Args:
            request: The request containing visualization parameters
            
        Returns:
            Response with visualization data and metadata
        """
        logger.info(f"Received request for Robot Framework visualization: {request.visualization_type}")
        
        try:
            result = create_robot_visualization(
                visualization_type=request.visualization_type,
                file_path=request.file_path,
                output_xml_path=request.output_xml_path,
                directory_path=request.directory_path,
                output_format=request.output_format,
                limit=request.limit
            )
            
            return RobotVisualizationResponse(
                visualization_data=result.get("visualization_data", ""),
                visualization_type=result.get("visualization_type", request.visualization_type),
                format=result.get("format", request.output_format),
                error=result.get("error")
            )
            
        except Exception as e:
            error_msg = f"Error in robot_visualization: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return RobotVisualizationResponse(
                visualization_data="",
                visualization_type=request.visualization_type,
                format=request.output_format,
                error=error_msg
            ) 