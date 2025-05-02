#!/usr/bin/env python
"""
MCP Tool: Robot Agent Prompt
Provides a structured workflow for robot framework test automation using an agent approach.
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

# Import local modules instead of direct mcp import
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    # Define a stub class for type hinting
    class FastMCP:
        def tool(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

logger = logging.getLogger('robot_tool.agent_prompt')

# -----------------------------------------------------------------------------
# Workflow Definitions
# -----------------------------------------------------------------------------

# Define the available workflows and their steps
WORKFLOWS = {
    "locator_finder": {
        "name": "Dynamic Locator Finder",
        "description": "Find robust XPath/CSS locators for web elements",
        "steps": [
            {
                "name": "task_analysis",
                "description": "Analyze the task and determine what elements need locators"
            },
            {
                "name": "page_screenshot",
                "description": "Take a screenshot of the page to visually identify elements"
            },
            {
                "name": "element_description",
                "description": "Describe the target elements in natural language"
            },
            {
                "name": "locator_generation",
                "description": "Generate and test robust locators for the elements"
            },
            {
                "name": "script_creation",
                "description": "Create Robot Framework test script with the locators"
            },
            {
                "name": "test_execution",
                "description": "Execute the generated test script and verify results"
            }
        ]
    },
    "form_automation": {
        "name": "Form Automation",
        "description": "Create test scripts for automating web forms",
        "steps": [
            {
                "name": "task_analysis",
                "description": "Analyze the form structure and requirements"
            },
            {
                "name": "form_detection",
                "description": "Detect form fields and their attributes"
            },
            {
                "name": "data_preparation",
                "description": "Prepare test data for form fields"
            },
            {
                "name": "success_criteria",
                "description": "Define success criteria for form submission"
            },
            {
                "name": "script_creation",
                "description": "Create and validate the form automation script"
            },
            {
                "name": "test_execution",
                "description": "Execute the form automation test and verify results"
            }
        ]
    },
    "dropdown_handling": {
        "name": "Dropdown Handling",
        "description": "Create test scripts for handling complex dropdowns",
        "steps": [
            {
                "name": "task_analysis",
                "description": "Analyze the dropdown type and behavior"
            },
            {
                "name": "dropdown_detection",
                "description": "Detect dropdown elements and their options"
            },
            {
                "name": "interaction_strategy",
                "description": "Determine the best strategy for interacting with the dropdown"
            },
            {
                "name": "script_creation",
                "description": "Create and test the dropdown handling script"
            },
            {
                "name": "test_execution",
                "description": "Execute the dropdown test and verify results"
            }
        ]
    },
    "custom": {
        "name": "Custom Workflow",
        "description": "Create a custom workflow for your specific needs",
        "steps": [
            {
                "name": "task_analysis",
                "description": "Analyze the automation task requirements"
            },
            {
                "name": "tool_selection",
                "description": "Select the appropriate MCP tools for the task"
            },
            {
                "name": "execution_plan",
                "description": "Create a detailed execution plan"
            },
            {
                "name": "script_creation",
                "description": "Create and test the automation script"
            },
            {
                "name": "test_execution",
                "description": "Execute the automation script and analyze results"
            }
        ]
    }
}

# Tool suggestions for each workflow step
TOOL_SUGGESTIONS = {
    "locator_finder": {
        "locator_generation": ["robot_xpath_locator", "robot_smart_locator", "robot_form_locator"],
        "page_screenshot": ["robot_page_snapshot"],
        "script_creation": ["robot_form_automator"],
        "test_execution": ["robot_runner"]
    },
    "form_automation": {
        "form_detection": ["robot_form_locator", "robot_smart_locator"],
        "script_creation": ["robot_form_automator"],
        "success_criteria": ["robot_form_success_detector"],
        "test_execution": ["robot_runner"]
    },
    "dropdown_handling": {
        "dropdown_detection": ["robot_form_locator", "robot_xpath_locator", "robot_smart_locator"],
        "script_creation": ["robot_dropdown_handler"],
        "test_execution": ["robot_runner"]
    },
    "custom": {
        "tool_selection": ["robot_library_explorer"],
        "script_creation": ["robot_test_reader", "robot_test_data_generator"],
        "test_execution": ["robot_runner", "robot_visualization"]
    }
}

# Robot test runner configuration details
TEST_RUNNER_DETAILS = """
## Test Runner Usage

The `robot_runner` tool is essential for executing Robot Framework test scripts. It can be used to:

1. **Execute a specific test file**:
   - Run a single test file with specific variables and tags
   - Monitor test execution in real-time
   - Collect execution results for analysis

2. **Run with custom variables**:
   - Pass dynamic variables to your tests at runtime
   - Override default values for greater flexibility
   - Examples: `browser=chrome`, `url=https://example.com`

3. **Filter tests by tags**:
   - Run only tests with specific tags
   - Skip tests with certain tags
   - Example: Include `smoke` tests, exclude `slow` tests

4. **Advanced options**:
   - Set output directories for reports and logs
   - Configure test timeouts
   - Select specific test suites within a test file

When your locators and test script are ready, use the `robot_runner` tool to validate them against the actual website.
"""

# -----------------------------------------------------------------------------
# Agent Prompt Functions
# -----------------------------------------------------------------------------

def get_workflow_details(workflow_id: str) -> Dict[str, Any]:
    """
    Get details for a specific workflow.
    
    Args:
        workflow_id: ID of the workflow
        
    Returns:
        Dictionary with workflow details
    """
    if workflow_id not in WORKFLOWS:
        return {
            "error": f"Workflow '{workflow_id}' not found",
            "available_workflows": list(WORKFLOWS.keys())
        }
    
    workflow = WORKFLOWS[workflow_id]
    result = {
        "id": workflow_id,
        "name": workflow["name"],
        "description": workflow["description"],
        "steps": workflow["steps"],
        "tool_suggestions": TOOL_SUGGESTIONS.get(workflow_id, {}),
        "test_runner_details": TEST_RUNNER_DETAILS
    }
    
    return result

def list_workflows() -> Dict[str, Any]:
    """
    List all available workflows.
    
    Returns:
        Dictionary with all workflows
    """
    result = {
        "workflows": []
    }
    
    for workflow_id, workflow in WORKFLOWS.items():
        result["workflows"].append({
            "id": workflow_id,
            "name": workflow["name"],
            "description": workflow["description"]
        })
    
    return result

def generate_agent_prompt(
    workflow_id: str,
    task_description: str,
    target_url: Optional[str] = None,
    additional_instructions: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a structured prompt for the agent to follow.
    
    Args:
        workflow_id: ID of the workflow to use
        task_description: Description of the automation task
        target_url: URL of the page to automate (optional)
        additional_instructions: Additional instructions for the agent (optional)
        
    Returns:
        Dictionary with structured prompt and workflow details
    """
    if workflow_id not in WORKFLOWS:
        return {
            "error": f"Workflow '{workflow_id}' not found",
            "available_workflows": list(WORKFLOWS.keys())
        }
    
    workflow = WORKFLOWS[workflow_id]
    tool_suggestions = TOOL_SUGGESTIONS.get(workflow_id, {})
    
    # Build the agent prompt
    prompt_parts = []
    
    # Add header
    prompt_parts.append(f"# {workflow['name']} Agent Workflow")
    prompt_parts.append(f"\n## Task Description")
    prompt_parts.append(f"{task_description}")
    
    if target_url:
        prompt_parts.append(f"\n## Target URL")
        prompt_parts.append(f"{target_url}")
    
    prompt_parts.append(f"\n## Workflow Steps")
    for i, step in enumerate(workflow["steps"], 1):
        prompt_parts.append(f"{i}. **{step['name']}**: {step['description']}")
        # Add tool suggestions if available for this step
        if step["name"] in tool_suggestions:
            tools = tool_suggestions[step["name"]]
            prompt_parts.append(f"   - Suggested tools: {', '.join(tools)}")
    
    # Add test runner information
    prompt_parts.append(TEST_RUNNER_DETAILS)
    
    if additional_instructions:
        prompt_parts.append(f"\n## Additional Instructions")
        prompt_parts.append(f"{additional_instructions}")
    
    # Add footer with guidance
    prompt_parts.append(f"\n## Agent Guidelines")
    prompt_parts.append("1. Follow the workflow steps in order")
    prompt_parts.append("2. Use the suggested tools for each step when available")
    prompt_parts.append("3. Document your reasoning and actions for each step")
    prompt_parts.append("4. After script creation, validate with the robot_runner tool")
    prompt_parts.append("5. Provide a summary after completing the workflow")
    
    # Combine all parts
    prompt = "\n".join(prompt_parts)
    
    return {
        "prompt": prompt,
        "workflow": {
            "id": workflow_id,
            "name": workflow["name"],
            "steps": [step["name"] for step in workflow["steps"]]
        },
        "test_runner": {
            "tool": "robot_runner",
            "description": "Tool for executing Robot Framework tests"
        }
    }

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register MCP tool."""
    
    @mcp.tool()
    async def robot_agent_list_workflows() -> Dict[str, Any]:
        """
        List all available agent workflows.
        
        Returns:
            Dictionary with all workflows and their details
        """
        return list_workflows()
    
    @mcp.tool()
    async def robot_agent_get_workflow(
        workflow_id: str
    ) -> Dict[str, Any]:
        """
        Get details for a specific agent workflow.
        
        Args:
            workflow_id: ID of the workflow
            
        Returns:
            Dictionary with workflow details including steps and tool suggestions
        """
        return get_workflow_details(workflow_id)
    
    @mcp.tool()
    async def robot_agent_generate_prompt(
        workflow_id: str,
        task_description: str,
        target_url: Optional[str] = None,
        additional_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a structured prompt for the agent to follow for Robot Framework automation.
        
        This tool helps orchestrate a multi-step workflow by creating a structured prompt
        that guides an AI agent through the process of automating tasks with Robot Framework.
        
        Args:
            workflow_id: ID of the workflow to use (e.g., "locator_finder", "form_automation")
            task_description: Description of the automation task
            target_url: URL of the page to automate (optional)
            additional_instructions: Additional instructions for the agent (optional)
            
        Returns:
            Dictionary with structured prompt and workflow details
        """
        return generate_agent_prompt(
            workflow_id=workflow_id,
            task_description=task_description,
            target_url=target_url,
            additional_instructions=additional_instructions
        ) 