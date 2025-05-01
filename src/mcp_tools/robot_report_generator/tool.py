#!/usr/bin/env python
"""
MCP Tool: Robot Report Generator
Generates test execution reports from Robot Framework logs and output files.
"""

import os
import json
import logging
import subprocess
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import (
    run_robot_command,
    parse_robot_output_xml
)
from src.config.config import (
    ROBOT_OUTPUT_DIR,
    ROBOT_REPORT_DIR,
    REPORT_FORMATS
)

logger = logging.getLogger('robot_tool.report_generator')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class ReportGeneratorRequest(BaseModel):
    """Request model for robot_report_generator tool."""
    output_xml_path: str = Field(
        ..., 
        description="Path to the output.xml file from a Robot Framework test execution"
    )
    report_name: Optional[str] = Field(
        None, 
        description="Base name for the generated reports (default: based on output.xml name)"
    )
    formats: List[str] = Field(
        default_factory=lambda: ["html"], 
        description="List of report formats to generate (html, xml, json)"
    )
    include_keywords: bool = Field(
        True, 
        description="Whether to include keyword details in the report"
    )
    custom_template: Optional[str] = Field(
        None, 
        description="Path to a custom report template"
    )

class ReportGeneratorResponse(BaseModel):
    """Response model for robot_report_generator tool."""
    reports: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of generated reports with paths and formats"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of test execution results"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def generate_reports(
    output_xml_path: str,
    report_name: Optional[str] = None,
    formats: List[str] = None,
    include_keywords: bool = True,
    custom_template: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate test execution reports from Robot Framework output.xml.
    
    Args:
        output_xml_path: Path to the output.xml file
        report_name: Base name for the generated reports
        formats: List of report formats to generate
        include_keywords: Whether to include keyword details
        custom_template: Path to a custom report template
        
    Returns:
        Dictionary with generated reports, summary, and any error
    """
    result = {
        "reports": [],
        "summary": {},
        "error": None
    }
    
    try:
        # Input validation
        output_path = Path(output_xml_path)
        if not output_path.exists():
            return {
                "reports": [],
                "summary": {},
                "error": f"Output XML file not found: {output_xml_path}"
            }
            
        # Set default formats
        if formats is None:
            formats = ["html"]
        
        # Validate formats
        valid_formats = [fmt for fmt in formats if fmt.lower() in REPORT_FORMATS]
        if not valid_formats:
            return {
                "reports": [],
                "summary": {},
                "error": f"No valid report formats specified. Supported formats: {', '.join(REPORT_FORMATS)}"
            }
            
        # Set report base name
        if not report_name:
            report_name = output_path.stem
            
        # Create output directory if it doesn't exist
        report_dir = Path(ROBOT_REPORT_DIR)
        report_dir.mkdir(exist_ok=True, parents=True)
            
        # Generate reports in each format
        for fmt in valid_formats:
            if fmt.lower() == "html":
                output_file = generate_html_report(output_path, report_name, report_dir, include_keywords, custom_template)
            elif fmt.lower() == "xml":
                output_file = generate_xml_report(output_path, report_name, report_dir)
            elif fmt.lower() == "json":
                output_file = generate_json_report(output_path, report_name, report_dir)
                
            if output_file:
                result["reports"].append({
                    "format": fmt,
                    "path": str(output_file)
                })
        
        # Parse output.xml to get summary information
        result["summary"] = parse_robot_output_xml(output_path)
        
        logger.info(f"Generated {len(result['reports'])} reports from {output_xml_path}")
        return result
        
    except Exception as e:
        error_msg = f"Error generating reports: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "reports": result["reports"],
            "summary": result["summary"],
            "error": error_msg
        }

def generate_html_report(
    output_path: Path, 
    report_name: str, 
    report_dir: Path,
    include_keywords: bool,
    custom_template: Optional[str]
) -> Optional[Path]:
    """Generate HTML report using rebot."""
    try:
        report_file = report_dir / f"{report_name}.html"
        log_file = report_dir / f"{report_name}_log.html"
        
        cmd = [
            "python", "-m", "robot.rebot",
            "--outputdir", str(report_dir),
            "--report", str(report_file.name),
            "--log", str(log_file.name)
        ]
        
        if not include_keywords:
            cmd.append("--removekeywords")
            cmd.append("ALL")
            
        if custom_template:
            template_path = Path(custom_template)
            if template_path.exists():
                cmd.append("--reportbackground")
                cmd.append(f":::{str(template_path)}")
                
        cmd.append(str(output_path))
        
        success, stdout, stderr = run_robot_command(cmd)
        
        if success and report_file.exists():
            logger.info(f"Generated HTML report: {report_file}")
            return report_file
        else:
            logger.error(f"Failed to generate HTML report: {stderr}")
            return None
            
    except Exception as e:
        logger.error(f"Error generating HTML report: {e}")
        return None

def generate_xml_report(
    output_path: Path, 
    report_name: str, 
    report_dir: Path
) -> Optional[Path]:
    """Generate XML report by copying and renaming output.xml."""
    try:
        report_file = report_dir / f"{report_name}.xml"
        
        # For XML, we can just copy the output.xml
        import shutil
        shutil.copy2(output_path, report_file)
        
        if report_file.exists():
            logger.info(f"Generated XML report: {report_file}")
            return report_file
        return None
        
    except Exception as e:
        logger.error(f"Error generating XML report: {e}")
        return None

def generate_json_report(
    output_path: Path, 
    report_name: str, 
    report_dir: Path
) -> Optional[Path]:
    """Generate JSON report by converting the XML to JSON."""
    try:
        report_file = report_dir / f"{report_name}.json"
        
        # Use robot framework XML to JSON converter or custom implementation
        # For now, we'll use a simple approach with ElementTree and json
        import xml.etree.ElementTree as ET
        import json
        
        tree = ET.parse(output_path)
        root = tree.getroot()
        
        # Convert XML to dictionary
        def xml_to_dict(element):
            result = {}
            
            # Add attributes
            for key, value in element.attrib.items():
                result[f"@{key}"] = value
                
            # Add children
            for child in element:
                child_dict = xml_to_dict(child)
                
                if child.tag in result:
                    if not isinstance(result[child.tag], list):
                        result[child.tag] = [result[child.tag]]
                    result[child.tag].append(child_dict)
                else:
                    result[child.tag] = child_dict
                    
            # Add text if it exists and no children
            if element.text and element.text.strip() and not result:
                result = element.text.strip()
                
            return result
        
        # Convert to dictionary and write to file
        xml_dict = {root.tag: xml_to_dict(root)}
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(xml_dict, f, indent=2)
            
        if report_file.exists():
            logger.info(f"Generated JSON report: {report_file}")
            return report_file
        return None
        
    except Exception as e:
        logger.error(f"Error generating JSON report: {e}")
        return None

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_report_generator(
        output_xml_path: str,
        report_name: Optional[str] = None,
        formats: Optional[List[str]] = None,
        include_keywords: bool = True,
        custom_template: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate test execution reports from Robot Framework logs and output files.
        
        Args:
            output_xml_path: Path to the output.xml file from a Robot Framework test execution
            report_name: Base name for the generated reports (optional, default: based on output.xml name)
            formats: List of report formats to generate (optional, default: ["html"])
            include_keywords: Whether to include keyword details in the report (default: True)
            custom_template: Path to a custom report template (optional)
            
        Returns:
            Response with generated reports, summary, and any error
        """
        logger.info(f"Received request to generate reports from {output_xml_path}")
        
        try:
            # Log parameters for debugging
            logger.debug(f"Parameters: output_xml_path={output_xml_path}, "
                        f"report_name={report_name}, "
                        f"formats={formats}, "
                        f"include_keywords={include_keywords}, "
                        f"custom_template={custom_template}")
            
            # Use default formats if not provided
            if formats is None:
                formats = ["html"]
            
            result = generate_reports(
                output_xml_path=output_xml_path,
                report_name=report_name,
                formats=formats,
                include_keywords=include_keywords,
                custom_template=custom_template
            )
            
            # Return as dictionary for maximum compatibility
            return {
                "reports": result["reports"],
                "summary": result["summary"],
                "error": result["error"]
            }
            
        except Exception as e:
            error_msg = f"Error in robot_report_generator: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "reports": [],
                "summary": {},
                "error": error_msg
            } 