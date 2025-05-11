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
    "smart_browser_automation": {
        "name": "Smart Browser Automation",
        "description": "Create robust automation scripts with enhanced element detection and interaction",
        "steps": [
            {
                "name": "task_analysis",
                "description": "Analyze the automation task and identify elements to interact with"
            },
            {
                "name": "smart_locator_finding",
                "description": "Find reliable locators with context-aware strategies"
            },
            {
                "name": "element_interaction",
                "description": "Use smart interaction with pre-validation and recovery strategies"
            },
            {
                "name": "script_creation",
                "description": "Create resilient scripts with smart waiting and validation"
            },
            {
                "name": "test_execution",
                "description": "Execute the automation with intelligent error handling"
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
        "locator_generation": ["robot_auto_locator", "robot_browser_find_smart_locator"],
        "page_screenshot": ["robot_page_snapshot", "robot_browser_screenshot"],
        "script_creation": ["robot_form_automator"]
    },
    "form_automation": {
        "form_detection": ["robot_form_locator", "robot_auto_locator"],
        "script_creation": ["robot_form_automator"],
        "success_criteria": ["robot_form_success_detector"]
    },
    "dropdown_handling": {
        "dropdown_detection": ["robot_auto_locator", "robot_form_locator"],
        "script_creation": ["robot_dropdown_handler", "robot_browser_smart_select"]
    },
    "smart_browser_automation": {
        "smart_locator_finding": ["robot_browser_find_smart_locator", "robot_auto_locator"],
        "element_interaction": ["robot_browser_smart_click", "robot_browser_smart_input", "robot_browser_smart_select", "robot_browser_smart_wait"],
        "script_creation": ["robot_form_automator"]
    },
    "custom": {
        "tool_selection": ["robot_agent_list_workflows", "robot_agent_get_workflow"],
        "script_creation": ["robot_form_automator", "robot_dropdown_handler"]
    }
}

# Smart Browser Tool details
SMART_BROWSER_DETAILS = """
## Smart Browser Tools

Our enhanced smart browser tools provide intelligent element interaction with the following capabilities:

1. **Smart Locator Detection**:
   - Finds stable, reliable locators even for dynamic elements
   - Understands element relationships and parent-child structures
   - Generates alternative locators for automatic recovery
   - Analyzes element context for more accurate identification

2. **Element Interaction Validation**:
   - Pre-validates element state before attempting interaction
   - Checks if elements are truly clickable/typeable
   - Provides detailed diagnostic information when elements cannot be interacted with
   - Automatically handles elements that are covered or outside viewport

3. **Automatic Recovery Strategies**:
   - Tries multiple interaction techniques (standard, action chains, JavaScript)
   - Automatically retries with exponential backoff for flaky elements
   - Falls back to alternative locators if primary locator fails
   - Intelligent handling of stale elements and timing issues

4. **Smart Waiting Strategies**:
   - Adapts to different page load behaviors (standard, AJAX, SPA)
   - Detects framework-specific wait conditions (jQuery, Angular)
   - Provides detailed feedback on wait failures
   - Uses exponential backoff for more efficient waiting

5. **Comprehensive Tools**:
   - `robot_browser_smart_click`: Enhanced click with validation and recovery
   - `robot_browser_smart_input`: Intelligent text input with verification
   - `robot_browser_smart_select`: Robust dropdown selection with validation
   - `robot_browser_smart_wait`: Adaptive waiting for different page types
   - `robot_browser_find_smart_locator`: Interactive locator finder with visual selection

These tools address common automation challenges including dynamic elements, timing issues,
and element relationships, making your automation scripts more reliable and maintainable.
"""

# Remove the test runner details as it's not implemented yet
TEST_RUNNER_DETAILS = ""

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
    
    # Add smart browser details for smart browser workflow
    if workflow_id == "smart_browser_automation":
        result["smart_browser_details"] = SMART_BROWSER_DETAILS
    
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
    Generate a structured agent prompt for a specific workflow.
    
    Args:
        workflow_id: ID of the workflow
        task_description: Description of the task to perform
        target_url: Optional URL for the target website
        additional_instructions: Optional additional instructions
        
    Returns:
        Dictionary with the generated prompt and metadata
    """
    # Get workflow details
    workflow_details = get_workflow_details(workflow_id)
    
    if "error" in workflow_details:
        return workflow_details
    
    # Start building the prompt
    prompt_parts = []
    
    # Introduction
    prompt_parts.append(f"# {workflow_details['name']} Workflow")
    prompt_parts.append(f"\n## Task Description\n{task_description}")
    
    if target_url:
        prompt_parts.append(f"\n## Target URL\n{target_url}")
    
    # Workflow steps
    prompt_parts.append("\n## Workflow Steps")
    for i, step in enumerate(workflow_details["steps"], 1):
        prompt_parts.append(f"{i}. **{step['name']}**: {step['description']}")
    
    # Tool suggestions
    prompt_parts.append("\n## Tool Suggestions")
    tool_suggestions = workflow_details["tool_suggestions"]
    for step_name, tools in tool_suggestions.items():
        prompt_parts.append(f"\n### {step_name.replace('_', ' ').title()}")
        for tool in tools:
            prompt_parts.append(f"- `{tool}`")
    
    # Add smart browser details for relevant workflows
    if workflow_id == "smart_browser_automation":
        prompt_parts.append("\n" + SMART_BROWSER_DETAILS)
    elif workflow_id in ["locator_finder", "form_automation", "dropdown_handling"]:
        prompt_parts.append("\n## Smart Browser Tools Available")
        prompt_parts.append("""
For more reliable element interaction, consider using our smart browser tools:

- `robot_browser_find_smart_locator`: Find stable locators with context-awareness
- `robot_browser_smart_click`: Click with pre-validation and automatic recovery
- `robot_browser_smart_input`: Type text with verification and retry strategies
- `robot_browser_smart_select`: Select dropdown options with robust validation
- `robot_browser_smart_wait`: Wait for elements with adaptive strategies

These tools handle dynamic elements, covered elements, and timing issues automatically.""")
    
    # Add test runner details
    prompt_parts.append("\n" + TEST_RUNNER_DETAILS)
    
    # Additional instructions (if provided)
    if additional_instructions:
        prompt_parts.append(f"\n## Additional Instructions\n{additional_instructions}")
    
    # Format the complete prompt
    complete_prompt = "\n".join(prompt_parts)
    
    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow_details["name"],
        "prompt": complete_prompt,
        "target_url": target_url,
        "tool_suggestions": workflow_details["tool_suggestions"]
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