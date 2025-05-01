#!/usr/bin/env python
"""
MCP Tool: Robot Step Debugger
Debugs individual test steps in Robot Framework tests and tracks their execution.
"""

import os
import logging
import tempfile
import json
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from src.utils.helpers import (
    run_robot_command,
    parse_robot_file,
    is_robot_file
)
from src.config.config import (
    ROBOT_OUTPUT_DIR,
    DEFAULT_TIMEOUT
)

logger = logging.getLogger('robot_tool.step_debugger')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class DebugStepRequest(BaseModel):
    """Request model for robot_step_debugger tool."""
    file_path: str = Field(
        ...,
        description="Path to a .robot file containing the test case to debug"
    )
    test_name: str = Field(
        ...,
        description="Name of the test case to debug"
    )
    breakpoints: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="""
        List of breakpoints to set. Each breakpoint can be:
        1. A step index ({"step_index": 2})
        2. A keyword name ({"keyword": "Login With Valid Credentials"})
        3. A line number ({"line": 42})
        """
    )
    variables: Optional[Dict[str, str]] = Field(
        None,
        description="Variables to pass to the test run"
    )
    run_mode: str = Field(
        "step_by_step",
        description="Debug mode: 'step_by_step', 'run_to_breakpoint', or 'run_to_failure'"
    )
    continue_from: Optional[Dict[str, Any]] = Field(
        None,
        description="Continuation point from a previous debug session"
    )
    timeout: int = Field(
        DEFAULT_TIMEOUT,
        description="Timeout for the debug session in seconds"
    )

class DebugStepResponse(BaseModel):
    """Response model for robot_step_debugger tool."""
    status: str = Field(
        ...,
        description="Status of the debug session: 'running', 'paused', 'completed', 'failed'"
    )
    current_step: Optional[Dict[str, Any]] = Field(
        None,
        description="Current step being executed (with keyword, arguments, line number)"
    )
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Current values of variables at this point in execution"
    )
    logs: List[str] = Field(
        default_factory=list,
        description="Log messages from the test execution"
    )
    continue_from: Optional[Dict[str, Any]] = Field(
        None,
        description="Continuation point for the next debug session"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def debug_test_step(
    file_path: str,
    test_name: str,
    breakpoints: List[Dict[str, Any]] = None,
    variables: Dict[str, str] = None,
    run_mode: str = "step_by_step",
    continue_from: Dict[str, Any] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """
    Debug individual steps in a Robot Framework test.
    
    Args:
        file_path: Path to a .robot file containing the test case to debug
        test_name: Name of the test case to debug
        breakpoints: List of breakpoints to set
        variables: Variables to pass to the test run
        run_mode: Debug mode (step_by_step, run_to_breakpoint, run_to_failure)
        continue_from: Continuation point from a previous debug session
        timeout: Timeout for the debug session in seconds
        
    Returns:
        Dictionary with debug results and any error
    """
    result = {
        "status": "failed",
        "current_step": None,
        "variables": {},
        "logs": [],
        "continue_from": None,
        "error": None
    }
    
    try:
        # Input validation
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {
                "status": "failed",
                "error": f"File not found: {file_path}"
            }
        
        if not is_robot_file(file_path_obj):
            return {
                "status": "failed",
                "error": f"Not a valid Robot Framework file: {file_path}"
            }
        
        # Create a temporary listener for debugging
        listener_file = create_debug_listener(
            breakpoints=breakpoints or [],
            run_mode=run_mode,
            continue_from=continue_from
        )
        
        # Create a temporary output directory for this debug session
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            output_file = output_dir / "debug_output.json"
            
            # Build command
            cmd = ["robot"]
            
            # Add the test name
            cmd.extend(["--test", test_name])
            
            # Add listener
            cmd.extend(["--listener", str(listener_file) + ":" + str(output_file)])
            
            # Add variables
            if variables:
                for name, value in variables.items():
                    cmd.extend(["--variable", f"{name}:{value}"])
            
            # Add output files
            cmd.extend([
                "--outputdir", str(output_dir),
                "--output", "output.xml",
                "--log", "NONE",
                "--report", "NONE"
            ])
            
            # Add file to run
            cmd.append(str(file_path_obj))
            
            # Run the command
            logger.info(f"Running Robot Framework debug session: {' '.join(cmd)}")
            success, stdout, stderr = run_robot_command(cmd, timeout=timeout)
            
            # Parse debug output
            if output_file.exists():
                with open(output_file, 'r', encoding='utf-8') as f:
                    debug_data = json.load(f)
                    
                # Update result based on debug output
                result.update(debug_data)
                
                # Set status based on run mode and debug data
                if debug_data.get("status") == "completed":
                    result["status"] = "completed"
                elif debug_data.get("status") == "failed":
                    result["status"] = "failed"
                elif run_mode == "step_by_step" or debug_data.get("status") == "breakpoint_hit":
                    result["status"] = "paused"
                else:
                    result["status"] = "running"
            else:
                result["status"] = "failed"
                result["error"] = f"Debug session failed to generate output"
                result["logs"] = [stdout, stderr]
        
        # Clean up temporary listener file
        try:
            os.remove(listener_file)
        except Exception as e:
            logger.warning(f"Failed to remove temporary listener file: {e}")
        
        return result
        
    except Exception as e:
        error_msg = f"Error debugging Robot Framework test: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": "failed",
            "current_step": None,
            "variables": {},
            "logs": [],
            "continue_from": None,
            "error": error_msg
        }

def create_debug_listener(
    breakpoints: List[Dict[str, Any]],
    run_mode: str,
    continue_from: Dict[str, Any] = None
) -> Path:
    """
    Create a temporary Robot Framework listener for debugging.
    
    Args:
        breakpoints: List of breakpoints to set
        run_mode: Debug mode
        continue_from: Continuation point from a previous debug session
        
    Returns:
        Path to the created listener file
    """
    # Create a temporary python file
    with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as f:
        f.write("""
import os
import json
from robot.api import logger
from robot.running.context import EXECUTION_CONTEXTS

class RobotStepDebugger:
    ROBOT_LISTENER_API_VERSION = 2
    
    def __init__(self, output_file):
        self.output_file = output_file
        self.breakpoints = {breakpoints}
        self.run_mode = "{run_mode}"
        self.continue_from = {continue_from}
        self.current_test = None
        self.current_step_index = 0
        self.variables = {{}}
        self.logs = []
        self.status = "running"
        self.hit_breakpoint = False
    
    def start_test(self, name, attrs):
        self.current_test = name
        self.current_step_index = 0
        self.variables = {{}}
        self.logs = []
        
        # Restore position if continuing from a previous session
        if self.continue_from:
            self.current_step_index = self.continue_from.get("step_index", 0)
    
    def end_test(self, name, attrs):
        if attrs['status'] == 'PASS':
            self.status = "completed"
        else:
            self.status = "failed"
            self.logs.append(f"Test failed: {{attrs['message']}}")
        
        self.write_debug_output()
    
    def start_keyword(self, name, attrs):
        if self.current_test:
            # Get variables from current context
            variables = self._get_variables()
            
            # Check for breakpoints
            if self._should_break(name, attrs):
                self.status = "breakpoint_hit"
                self.hit_breakpoint = True
                self.logs.append(f"Breakpoint hit at keyword: {{name}}")
                
                # Write output and stop execution if a breakpoint was hit
                self.write_debug_output()
                if self.run_mode in ["step_by_step", "run_to_breakpoint"]:
                    return False  # Not supported in all RF versions
            
            # If in step-by-step mode and not at a step we're continuing from
            if self.run_mode == "step_by_step" and not self.continue_from:
                self.status = "paused"
                
                # Write output and stop execution
                self.write_debug_output()
                return False  # Not supported in all RF versions
            
            # If continuing from a previous point, decrement step counter
            if self.continue_from and self.current_step_index > 0:
                self.current_step_index -= 1
                return
            
            # Store current step info
            self.current_step = {{
                "step_index": self.current_step_index,
                "keyword": name,
                "arguments": attrs.get('args', []),
                "line": attrs.get('lineno', 0),
                "source": attrs.get('source', None)
            }}
            
            # Store variables at this step
            self.variables = variables
            
            # Increment step counter for the next step
            self.current_step_index += 1
    
    def log_message(self, message):
        self.logs.append(message['message'])
        
        # If in run_to_failure mode and there's an error or fail message,
        # write output and stop execution
        if (self.run_mode == "run_to_failure" and 
            message['level'] in ['ERROR', 'FAIL']):
            self.status = "failed"
            self.write_debug_output()
            return False  # Not supported in all RF versions
    
    def _should_break(self, name, attrs):
        # Check all breakpoints to see if any match
        for bp in self.breakpoints:
            # Break on step index
            if 'step_index' in bp and bp['step_index'] == self.current_step_index:
                return True
                
            # Break on keyword name
            if 'keyword' in bp and bp['keyword'] in name:
                return True
                
            # Break on line number
            if 'line' in bp and attrs.get('lineno') == bp['line']:
                return True
                
        return False
    
    def _get_variables(self):
        # Get current execution context
        ctx = EXECUTION_CONTEXTS.current
        if not ctx:
            return {{}}
            
        # Get variable scopes
        variables = {{}}
        
        # Add global variables
        if hasattr(ctx, 'variables'):
            variables.update(self._extract_variables(ctx.variables))
            
        # Add test case variables
        if hasattr(ctx, 'namespace') and hasattr(ctx.namespace, 'variables'):
            variables.update(self._extract_variables(ctx.namespace.variables))
        
        return variables
    
    def _extract_variables(self, var_store):
        result = {{}}
        
        # Different RF versions have different variable access methods
        if hasattr(var_store, 'as_dict'):
            # RF 4.0+
            variables = var_store.as_dict()
            for name, value in variables.items():
                # Skip internal variables
                if not name.startswith('${{') or name.startswith('@{{'):
                    continue
                # Clean up variable name
                clean_name = name[2:-1]  # Remove ${{ }}
                result[clean_name] = str(value)
        elif hasattr(var_store, '_variables'):
            # Older RF versions
            variables = var_store._variables
            for name, value in variables.items():
                if name.startswith('${{') or name.startswith('@{{'):
                    clean_name = name[2:-1]  # Remove ${{ }}
                    result[clean_name] = str(value)
        
        return result
    
    def write_debug_output(self):
        # Prepare continue_from for next session
        continue_from = {{
            "step_index": self.current_step_index,
            "test_name": self.current_test
        }}
        
        output_data = {{
            "status": self.status,
            "current_step": self.current_step,
            "variables": self.variables,
            "logs": self.logs,
            "continue_from": continue_from
        }}
        
        with open(self.output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
            
""".format(
            breakpoints=json.dumps(breakpoints),
            run_mode=run_mode,
            continue_from=json.dumps(continue_from or {})
        ))
        return Path(f.name)

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_step_debugger(request: DebugStepRequest) -> DebugStepResponse:
        """
        Debug individual steps in a Robot Framework test.
        
        Args:
            request: The request containing debug parameters
            
        Returns:
            Response with debug results and any error
        """
        logger.info(f"Received request to debug Robot Framework test: {request.test_name} in {request.file_path}")
        
        try:
            result = debug_test_step(
                file_path=request.file_path,
                test_name=request.test_name,
                breakpoints=request.breakpoints,
                variables=request.variables,
                run_mode=request.run_mode,
                continue_from=request.continue_from,
                timeout=request.timeout
            )
            
            return DebugStepResponse(
                status=result["status"],
                current_step=result["current_step"],
                variables=result["variables"],
                logs=result["logs"],
                continue_from=result["continue_from"],
                error=result["error"]
            )
            
        except Exception as e:
            error_msg = f"Error in robot_step_debugger: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return DebugStepResponse(
                status="failed",
                current_step=None,
                variables={},
                logs=[],
                continue_from=None,
                error=error_msg
            ) 