#!/usr/bin/env python
"""
MCP Tool: Robot Browser Dialog
Provides browser dialog handling functionality for Robot Framework through MCP.
"""

import os
import logging
import time
import json
from typing import Dict, Any, Optional, Union
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

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoAlertPresentException,
    UnexpectedAlertPresentException
)

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_dialog')

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def initialize_webdriver() -> Optional[webdriver.Chrome]:
    """
    Initialize the Chrome WebDriver with multiple fallback methods.
    
    Returns:
        WebDriver object if successful, None otherwise
    """
    # Set up Chrome options for headless browsing
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")  # Set a large window size
    
    # Try different approaches to initialize the WebDriver
    driver = None
    last_error = None
    
    try:
        if WEBDRIVER_MANAGER_AVAILABLE:
            # Try with webdriver-manager if available
            logger.info("Trying WebDriver Manager initialization")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
        else:
            # Direct WebDriver initialization
            logger.info("Trying direct WebDriver initialization")
            service = Service()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
    except Exception as e:
        last_error = str(e)
        logger.warning(f"WebDriver initialization failed: {e}")
            
    if driver is None:
        logger.error(f"All WebDriver initialization methods failed. Last error: {last_error}")
        
    return driver

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def handle_browser_dialog(
    url: str, 
    dialog_action: str = "accept", 
    prompt_text: Optional[str] = None,
    wait_time: int = 10
) -> Dict[str, Any]:
    """
    Handle browser dialogs (alerts, confirms, prompts).
    
    Args:
        url: URL to navigate to that triggers the dialog
        dialog_action: Action to take on the dialog ('accept' or 'dismiss')
        prompt_text: Text to enter for a prompt dialog (if applicable)
        wait_time: Time to wait for the dialog to appear in seconds
        
    Returns:
        Dictionary with dialog handling status
    """
    result = {
        "url": url,
        "dialog_action": dialog_action,
        "prompt_text": prompt_text,
        "dialog_text": None,
        "dialog_type": None,
        "status": "success",
        "robot_command": None,
        "error": None
    }
    
    driver = None
    try:
        # Initialize WebDriver
        driver = initialize_webdriver()
        if not driver:
            result["status"] = "error"
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Navigate to the URL
        logger.info(f"Navigating to URL: {url}")
        try:
            driver.set_page_load_timeout(wait_time)
            driver.get(url)
        except UnexpectedAlertPresentException:
            # Dialog might appear during navigation
            pass
            
        # Wait for and handle dialog
        try:
            # Try to wait for alert to be present
            WebDriverWait(driver, wait_time).until(EC.alert_is_present())
            
            # Switch to the alert
            alert = driver.switch_to.alert
            result["dialog_text"] = alert.text
            
            # Determine dialog type (best guess based on behavior)
            try:
                # Try to send keys to determine if it's a prompt
                alert.send_keys("")
                result["dialog_type"] = "prompt"
            except:
                # If we can't send keys, it's either an alert or confirm
                # We can't reliably distinguish between alert and confirm
                result["dialog_type"] = "alert/confirm"
                
            # Handle the dialog according to action
            if dialog_action.lower() == "accept":
                if prompt_text is not None and result["dialog_type"] == "prompt":
                    alert.send_keys(prompt_text)
                alert.accept()
                logger.info(f"Accepted dialog with text: {result['dialog_text']}")
            else:
                alert.dismiss()
                logger.info(f"Dismissed dialog with text: {result['dialog_text']}")
                
        except TimeoutException:
            result["status"] = "warning"
            result["error"] = "No dialog appeared within the wait time"
            return result
        except NoAlertPresentException:
            result["status"] = "warning"
            result["error"] = "No dialog was present"
            return result
        
        # Generate Robot Framework command for dialog handling
        robot_action = "Accept Alert" if dialog_action.lower() == "accept" else "Dismiss Alert"
        prompt_command = f"    Input Text Into Alert    {prompt_text}" if prompt_text else ""
        
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Handle Browser Dialog
    [Arguments]    ${{url}}
    Open Browser    ${{url}}    Chrome
    Wait Until Alert Is Present    timeout={wait_time}
{prompt_command}
    {robot_action}
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error handling dialog: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_dialog_script(
    url: str, 
    output_file: str,
    dialog_action: str = "accept",
    prompt_text: Optional[str] = None,
    browser: str = "Chrome",
    wait_time: int = 10,
    trigger_js: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for handling browser dialogs.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        dialog_action: Action to take on the dialog ('accept' or 'dismiss')
        prompt_text: Text to enter for a prompt dialog (if applicable)
        browser: Browser to use (default is Chrome)
        wait_time: Time to wait for the dialog to appear in seconds
        trigger_js: JavaScript to execute to trigger the dialog
        
    Returns:
        Dictionary with generation status and file path
    """
    result = {
        "status": "success",
        "output_file": output_file,
        "error": None
    }
    
    try:
        # Determine the dialog handling command
        if dialog_action.lower() == "accept":
            action_cmd = "Accept Alert"
        else:
            action_cmd = "Dismiss Alert"
            
        # Handle prompt text if provided
        prompt_cmd = ""
        if prompt_text:
            prompt_cmd = f"    Input Text Into Alert    {prompt_text}\n"
            
        # Generate Robot Framework script
        script_content = f"""*** Settings ***
Documentation     Robot Framework script for handling browser dialogs
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}          {url}
${{BROWSER}}      {browser}
${{WAIT_TIME}}    {wait_time}

*** Test Cases ***
Handle Browser Dialog
    [Documentation]    Navigate to a page and handle a dialog
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
"""

        # If JavaScript trigger is provided, add it
        if trigger_js:
            script_content += f"""    
    # Trigger the dialog with JavaScript
    Execute Javascript    {trigger_js}
    
"""
        
        # Add dialog handling steps
        script_content += f"""    # Wait for and handle the dialog
    Wait Until Alert Is Present    timeout=${{WAIT_TIME}}
{prompt_cmd}    {action_cmd}
    
    # Continue with page interaction after dialog is handled
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}
"""
        
        # Ensure the directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Write the script to the output file
        with open(output_file, 'w') as f:
            f.write(script_content)
            
        return result
    except Exception as e:
        logger.error(f"Error generating dialog script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser dialog tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_handle_dialog(
        url: str,
        dialog_action: str = "accept",
        prompt_text: Optional[str] = None,
        wait_time: int = 10
    ) -> Dict[str, Any]:
        """
        Handle browser dialogs (alerts, confirms, prompts).
        
        Args:
            url: URL to navigate to that triggers the dialog
            dialog_action: Action to take on the dialog ('accept' or 'dismiss')
            prompt_text: Text to enter for a prompt dialog (if applicable)
            wait_time: Time to wait for the dialog to appear in seconds
            
        Returns:
            Dictionary with dialog handling status
        """
        logger.info(f"Received request to handle dialog at URL: {url} with action: {dialog_action}")
        result = handle_browser_dialog(url, dialog_action, prompt_text, wait_time)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_dialog_script(
        url: str,
        output_file: str,
        dialog_action: str = "accept",
        prompt_text: Optional[str] = None,
        browser: str = "Chrome",
        wait_time: int = 10,
        trigger_js: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for handling browser dialogs.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            dialog_action: Action to take on the dialog ('accept' or 'dismiss')
            prompt_text: Text to enter for a prompt dialog (if applicable)
            browser: Browser to use (default is Chrome)
            wait_time: Time to wait for the dialog to appear in seconds
            trigger_js: JavaScript to execute to trigger the dialog
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate dialog script for URL: {url}")
        result = generate_dialog_script(url, output_file, dialog_action, prompt_text, browser, wait_time, trigger_js)
        return result 