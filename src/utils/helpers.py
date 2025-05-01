#!/usr/bin/env python
"""
Helper utilities for Robot Framework MCP tools
"""

import os
import sys
import subprocess
import logging
import shutil
import glob
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
import xml.etree.ElementTree as ET
import json
import re
from datetime import datetime

logger = logging.getLogger('robot_tool')

def run_robot_command(cmd: List[str], timeout: int = 300) -> Tuple[bool, str, str]:
    """
    Run a Robot Framework command as a subprocess.
    
    Args:
        cmd: List of command arguments
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (success, stdout, stderr)
    """
    logger.debug(f"Running command: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(timeout=timeout)
        success = process.returncode == 0
        
        if not success:
            logger.error(f"Command failed with code {process.returncode}: {stderr}")
        
        return success, stdout, stderr
        
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")
        process.kill()
        return False, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return False, "", str(e)

def find_robot_files(directory: Union[str, Path], recursive: bool = True) -> List[Path]:
    """
    Find all Robot Framework files in a directory.
    
    Args:
        directory: Directory to search
        recursive: Whether to search recursively
        
    Returns:
        List of paths to Robot Framework files
    """
    if isinstance(directory, str):
        directory = Path(directory)
    
    if not directory.exists():
        logger.error(f"Directory not found: {directory}")
        return []
    
    pattern = "**/*.robot" if recursive else "*.robot"
    resource_pattern = "**/*.resource" if recursive else "*.resource"
    
    robot_files = list(directory.glob(pattern))
    resource_files = list(directory.glob(resource_pattern))
    
    return robot_files + resource_files

def is_robot_file(file_path: Union[str, Path]) -> bool:
    """
    Check if a file is a Robot Framework file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file is a Robot Framework file, False otherwise
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return False
    
    # Check extension
    if file_path.suffix.lower() not in ['.robot', '.resource']:
        return False
    
    # Try to read and find Robot Framework sections
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for Robot Framework sections
        sections = ['*** Settings ***', '*** Variables ***', '*** Test Cases ***', 
                   '*** Keywords ***', '*** Tasks ***', '*** Comments ***']
        
        for section in sections:
            if section in content:
                return True
                
        return False
        
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return False

def parse_robot_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Parse a Robot Framework file and extract its structure.
    
    Args:
        file_path: Path to the Robot Framework file
        
    Returns:
        Dictionary with the file structure
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    if not is_robot_file(file_path):
        logger.error(f"Not a valid Robot Framework file: {file_path}")
        return {"error": f"Not a valid Robot Framework file: {file_path}"}
    
    result = {
        "file_path": str(file_path),
        "file_name": file_path.name,
        "sections": {},
        "test_cases": [],
        "keywords": [],
        "settings": {},
        "variables": {},
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        current_section = None
        section_content = []
        
        # Process file line by line
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Check for section headers
            if line.startswith('***') and line.endswith('***'):
                # Save previous section
                if current_section:
                    result["sections"][current_section] = section_content
                    
                    # Process specific sections
                    if current_section == "Test Cases":
                        result["test_cases"] = parse_test_cases(section_content)
                    elif current_section == "Keywords":
                        result["keywords"] = parse_keywords(section_content)
                    elif current_section == "Settings":
                        result["settings"] = parse_settings(section_content)
                    elif current_section == "Variables":
                        result["variables"] = parse_variables(section_content)
                
                # Start new section
                current_section = line.strip('* ').strip()
                section_content = []
            else:
                # Add content to current section
                if current_section:
                    section_content.append(line)
                    
        # Save the last section
        if current_section:
            result["sections"][current_section] = section_content
            
            # Process specific sections
            if current_section == "Test Cases":
                result["test_cases"] = parse_test_cases(section_content)
            elif current_section == "Keywords":
                result["keywords"] = parse_keywords(section_content)
            elif current_section == "Settings":
                result["settings"] = parse_settings(section_content)
            elif current_section == "Variables":
                result["variables"] = parse_variables(section_content)
        
        return result
        
    except Exception as e:
        logger.error(f"Error parsing file {file_path}: {e}")
        return {"error": str(e)}

def parse_test_cases(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse test cases from section content."""
    test_cases = []
    current_test = None
    current_steps = []
    
    for line in lines:
        if not line.startswith(' ') and line:
            # Save previous test case
            if current_test:
                test_cases.append({
                    "name": current_test,
                    "steps": current_steps
                })
            
            # Start new test case
            current_test = line
            current_steps = []
        elif line.strip() and current_test:
            # Add step to current test
            current_steps.append(line.strip())
    
    # Save the last test case
    if current_test:
        test_cases.append({
            "name": current_test,
            "steps": current_steps
        })
    
    return test_cases

def parse_keywords(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse keywords from section content."""
    keywords = []
    current_keyword = None
    current_steps = []
    
    for line in lines:
        if not line.startswith(' ') and line:
            # Save previous keyword
            if current_keyword:
                keywords.append({
                    "name": current_keyword,
                    "steps": current_steps
                })
            
            # Start new keyword
            current_keyword = line
            current_steps = []
        elif line.strip() and current_keyword:
            # Add step to current keyword
            current_steps.append(line.strip())
    
    # Save the last keyword
    if current_keyword:
        keywords.append({
            "name": current_keyword,
            "steps": current_steps
        })
    
    return keywords

def parse_settings(lines: List[str]) -> Dict[str, Any]:
    """Parse settings from section content."""
    settings = {}
    
    for line in lines:
        if not line:
            continue
            
        parts = line.split('  ', 1)
        if len(parts) >= 2:
            key, value = parts[0].strip(), parts[1].strip()
            settings[key] = value
    
    return settings

def parse_variables(lines: List[str]) -> Dict[str, Any]:
    """Parse variables from section content."""
    variables = {}
    
    for line in lines:
        if not line:
            continue
            
        parts = line.split('  ', 1)
        if len(parts) >= 2:
            key, value = parts[0].strip(), parts[1].strip()
            variables[key] = value
    
    return variables

def parse_robot_output_xml(output_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Parse Robot Framework output.xml file.
    
    Args:
        output_path: Path to the output.xml file
        
    Returns:
        Dictionary with the parsed output
    """
    if isinstance(output_path, str):
        output_path = Path(output_path)
    
    if not output_path.exists():
        logger.error(f"Output file not found: {output_path}")
        return {"error": f"Output file not found: {output_path}"}
    
    try:
        tree = ET.parse(output_path)
        root = tree.getroot()
        
        result = {
            "status": root.attrib.get('status', 'UNKNOWN'),
            "generated": root.attrib.get('generated', ''),
            "generator": root.attrib.get('generator', ''),
            "statistics": {},
            "suite": {},
            "tests": [],
            "errors": []
        }
        
        # Parse statistics
        stats_elem = root.find('statistics')
        if stats_elem is not None:
            total_elem = stats_elem.find('total')
            if total_elem is not None:
                for stat in total_elem.findall('stat'):
                    name = stat.attrib.get('name', '')
                    if name:
                        result["statistics"][name] = {
                            "pass": int(stat.attrib.get('pass', 0)),
                            "fail": int(stat.attrib.get('fail', 0)),
                            "skip": int(stat.attrib.get('skip', 0)),
                            "total": int(stat.attrib.get('pass', 0)) + 
                                     int(stat.attrib.get('fail', 0)) + 
                                     int(stat.attrib.get('skip', 0))
                        }
        
        # Parse suite
        suite_elem = root.find('suite')
        if suite_elem is not None:
            result["suite"] = {
                "name": suite_elem.attrib.get('name', ''),
                "source": suite_elem.attrib.get('source', ''),
                "status": "UNKNOWN"
            }
            
            status_elem = suite_elem.find('status')
            if status_elem is not None:
                result["suite"]["status"] = status_elem.attrib.get('status', 'UNKNOWN')
                result["suite"]["start_time"] = status_elem.attrib.get('starttime', '')
                result["suite"]["end_time"] = status_elem.attrib.get('endtime', '')
            
            # Parse tests
            for test_elem in suite_elem.findall('.//test'):
                test = {
                    "name": test_elem.attrib.get('name', ''),
                    "status": "UNKNOWN",
                    "keywords": []
                }
                
                test_status = test_elem.find('status')
                if test_status is not None:
                    test["status"] = test_status.attrib.get('status', 'UNKNOWN')
                    test["start_time"] = test_status.attrib.get('starttime', '')
                    test["end_time"] = test_status.attrib.get('endtime', '')
                
                # Parse keywords
                for kw_elem in test_elem.findall('kw'):
                    keyword = {
                        "name": kw_elem.attrib.get('name', ''),
                        "type": kw_elem.attrib.get('type', ''),
                        "status": "UNKNOWN"
                    }
                    
                    kw_status = kw_elem.find('status')
                    if kw_status is not None:
                        keyword["status"] = kw_status.attrib.get('status', 'UNKNOWN')
                        keyword["start_time"] = kw_status.attrib.get('starttime', '')
                        keyword["end_time"] = kw_status.attrib.get('endtime', '')
                    
                    test["keywords"].append(keyword)
                
                result["tests"].append(test)
        
        # Parse errors
        errors_elem = root.find('errors')
        if errors_elem is not None:
            for msg_elem in errors_elem.findall('msg'):
                result["errors"].append({
                    "level": msg_elem.attrib.get('level', ''),
                    "timestamp": msg_elem.attrib.get('timestamp', ''),
                    "message": msg_elem.text or ''
                })
        
        return result
        
    except Exception as e:
        logger.error(f"Error parsing output file {output_path}: {e}")
        return {"error": str(e)}

# -----------------------------------------------------------------------------
# Library and Keyword Discovery
# -----------------------------------------------------------------------------

def get_available_robot_libraries() -> List[Dict[str, Any]]:
    """
    Attempt to discover available Robot Framework libraries by checking
    installed packages and trying to import standard libraries.

    Note: This might not find all possible libraries, especially custom ones
          not installed as packages or standard libraries not explicitly checked.

    Returns:
        List of dictionaries containing library information.
    """
    libraries = []
    standard_libs = [
        "BuiltIn", "Collections", "DateTime", "Dialogs", "OperatingSystem",
        "Process", "Screenshot", "String", "Telnet", "XML"
    ]
    
    # Add standard libraries
    for lib in standard_libs:
        libraries.append({
            "name": lib,
            "type": "standard",
            "version": None,
            "path": None
        })

    # Try finding installed packages using importlib.metadata
    try:
        from importlib.metadata import distributions
        for dist in distributions():
            dist_name = dist.metadata['Name']
            # Simple heuristic: Check common naming conventions
            if 'robotframework' in dist_name.lower() or 'library' in dist_name.lower():
                try:
                    version = dist.metadata['Version']
                except KeyError:
                    version = None
                
                # Often the importable name is the same or derived from the distribution name
                potential_lib_name = dist_name.replace('-', '.').replace('_', '.')
                libraries.append({
                    "name": potential_lib_name,
                    "type": "installed",
                    "version": version,
                    "path": None
                })

                # Try to add module names if they exist top-level
                if dist.files:
                    for file_path in dist.files:
                        # Check for top-level .py files or directories that could be libraries
                        parts = file_path.parts
                        if len(parts) == 1 and parts[0].endswith('.py'):
                            lib_name = parts[0][:-3]  # Module name
                            if lib_name not in [lib["name"] for lib in libraries]:
                                libraries.append({
                                    "name": lib_name,
                                    "type": "installed",
                                    "version": version,
                                    "path": str(file_path)
                                })
                        elif len(parts) == 2 and parts[1] == '__init__.py':
                            lib_name = parts[0]  # Package name
                            if lib_name not in [lib["name"] for lib in libraries]:
                                libraries.append({
                                    "name": lib_name,
                                    "type": "installed",
                                    "version": version,
                                    "path": str(file_path.parent)
                                })

    except ImportError:
        logger.warning("importlib.metadata not available. Relying on standard libraries list.")
    except Exception as e:
        logger.error(f"Error scanning installed packages for libraries: {e}")

    logger.info(f"Discovered potential libraries: {len(libraries)}")
    return libraries

def get_library_keywords(library_name: str) -> List[Dict[str, Any]]:
    """
    Get keywords from a Robot Framework library using libdoc spec generation.
    
    Args:
        library_name: Name of the library
        
    Returns:
        List of keywords with documentation
    """
    try:
        output_path = Path(f"temp_{library_name}_libdoc.json")
        
        cmd = [
            sys.executable, 
            "-m", 
            "robot.libdoc", 
            "--format", "JSON", 
            library_name, 
            str(output_path)
        ]
        
        success, stdout, stderr = run_robot_command(cmd)
        
        if not success:
            logger.error(f"Error getting library keywords: {stderr}")
            return []
        
        # Read the JSON output
        with open(output_path, 'r', encoding='utf-8') as f:
            libdoc = json.load(f)
        
        # Clean up temporary file
        os.remove(output_path)
        
        keywords = []
        for kw in libdoc.get('keywords', []):
            keywords.append({
                "name": kw.get('name', ''),
                "args": kw.get('args', []),
                "doc": kw.get('doc', ''),
                "shortdoc": kw.get('shortdoc', '')
            })
        
        return keywords
        
    except Exception as e:
        logger.error(f"Error getting library keywords: {e}")
        
        # Clean up temporary file if it exists
        if output_path.exists():
            os.remove(output_path)
            
        return [] 