#!/usr/bin/env python
"""
MCP Tool: Robot Browser Upload
Provides file upload functionality for Robot Framework through MCP.
"""

import os
import logging
import time
import json
from typing import Dict, Any, Optional, List, Tuple
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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException,
    NoSuchElementException,
    ElementNotInteractableException
)

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_upload')

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

def parse_locator(locator: str) -> Tuple[str, str]:
    """
    Parse a locator string into its type and value.
    
    Args:
        locator: Locator string (e.g., "xpath=//button", "id=submit")
        
    Returns:
        Tuple of (locator_type, locator_value)
    """
    # Default to XPath if no prefix is given
    if "=" not in locator:
        return By.XPATH, locator
    
    prefix, value = locator.split("=", 1)
    prefix = prefix.lower().strip()
    
    if prefix == "id":
        return By.ID, value
    elif prefix == "name":
        return By.NAME, value
    elif prefix == "class":
        return By.CLASS_NAME, value
    elif prefix == "tag":
        return By.TAG_NAME, value
    elif prefix == "link":
        return By.LINK_TEXT, value
    elif prefix == "partiallink":
        return By.PARTIAL_LINK_TEXT, value
    elif prefix == "css":
        return By.CSS_SELECTOR, value
    elif prefix == "xpath":
        return By.XPATH, value
    else:
        # Default to XPath for unknown prefixes
        return By.XPATH, locator

def check_file_exists(file_path: str) -> bool:
    """
    Check if a file exists.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file exists, False otherwise
    """
    return os.path.isfile(file_path)

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def upload_file(
    url: str,
    file_upload_element: str,
    file_path: str,
    wait_time: int = 10,
    submit_element: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload a file to a website.
    
    Args:
        url: URL to navigate to
        file_upload_element: Locator for the file upload element
        file_path: Path to the file to upload
        wait_time: Time to wait for elements to be ready in seconds
        submit_element: Optional locator for a submit button to click after upload
        
    Returns:
        Dictionary with upload status
    """
    result = {
        "url": url,
        "file_upload_element": file_upload_element,
        "file_path": file_path,
        "submit_element": submit_element,
        "status": "success",
        "robot_command": None,
        "error": None
    }
    
    driver = None
    try:
        # Check if the file exists
        if not check_file_exists(file_path):
            result["status"] = "error"
            result["error"] = f"File does not exist: {file_path}"
            return result
        
        # Save file info
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        result["file_info"] = {
            "name": file_name,
            "size": file_size,
            "path": os.path.abspath(file_path)
        }
        
        # Initialize WebDriver
        driver = initialize_webdriver()
        if not driver:
            result["status"] = "error"
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Navigate to the URL
        logger.info(f"Navigating to URL: {url}")
        driver.set_page_load_timeout(wait_time * 2)
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Parse locator for file upload element
        by_type, locator_value = parse_locator(file_upload_element)
        
        # Wait for the file upload element to be present
        logger.info(f"Waiting for file upload element: {file_upload_element}")
        try:
            upload_element = WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((by_type, locator_value))
            )
        except TimeoutException:
            result["status"] = "error"
            result["error"] = f"File upload element not found or not visible: {file_upload_element}"
            return result
            
        # Check if the element is a file input
        element_type = upload_element.get_attribute("type")
        if element_type != "file":
            # Try to find a nested file input
            try:
                nested_inputs = upload_element.find_elements(By.TAG_NAME, "input")
                for inp in nested_inputs:
                    if inp.get_attribute("type") == "file":
                        upload_element = inp
                        break
            except:
                pass
            
            if upload_element.get_attribute("type") != "file":
                result["status"] = "warning"
                result["warning"] = f"Element may not be a file input. Type: {element_type}"
                # Continue anyway, as some custom file inputs might work
                
        # Send the file path to the upload element
        logger.info(f"Uploading file: {file_path}")
        try:
            # Get absolute path to avoid issues
            abs_file_path = os.path.abspath(file_path)
            upload_element.send_keys(abs_file_path)
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Error sending file path to upload element: {str(e)}"
            return result
            
        # Click submit button if provided
        if submit_element:
            logger.info(f"Clicking submit element: {submit_element}")
            try:
                # Parse locator for submit element
                submit_by_type, submit_locator_value = parse_locator(submit_element)
                
                # Wait for the submit element to be clickable
                submit_button = WebDriverWait(driver, wait_time).until(
                    EC.element_to_be_clickable((submit_by_type, submit_locator_value))
                )
                
                # Click the submit button
                submit_button.click()
                
                # Wait a moment for the form to submit
                time.sleep(2)
                
            except Exception as e:
                result["status"] = "warning"
                result["warning"] = f"Error clicking submit element: {str(e)}"
        
        # Generate Robot Framework command
        if submit_element:
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Upload File And Submit
    [Arguments]    ${{url}}    ${{file_upload_locator}}    ${{file_path}}    ${{submit_locator}}
    Open Browser    ${{url}}    Chrome
    Wait Until Page Contains Element    {file_upload_element}    timeout={wait_time}s
    Choose File    {file_upload_element}    ${{file_path}}
    Click Element    {submit_element}
    Sleep    2s
"""
        else:
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Upload File
    [Arguments]    ${{url}}    ${{file_upload_locator}}    ${{file_path}}
    Open Browser    ${{url}}    Chrome
    Wait Until Page Contains Element    {file_upload_element}    timeout={wait_time}s
    Choose File    {file_upload_element}    ${{file_path}}
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_upload_script(
    url: str,
    output_file: str,
    file_upload_element: str,
    sample_file_path: str,
    browser: str = "Chrome",
    wait_time: int = 10,
    submit_element: Optional[str] = None,
    include_verification: bool = True
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for file uploads.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        file_upload_element: Locator for the file upload element
        sample_file_path: Example file path to upload (can use a variable in the script)
        browser: Browser to use (default is Chrome)
        wait_time: Time to wait for elements to be ready in seconds
        submit_element: Optional locator for a submit button to click after upload
        include_verification: Whether to include verification steps
        
    Returns:
        Dictionary with generation status and file path
    """
    result = {
        "status": "success",
        "output_file": output_file,
        "error": None
    }
    
    try:
        # Generate Robot Framework script
        script_content = f"""*** Settings ***
Documentation     Robot Framework script for uploading files
Library           SeleniumLibrary
Library           OperatingSystem
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}             {url}
${{BROWSER}}         {browser}
${{WAIT_TIME}}       {wait_time}
${{UPLOAD_ELEMENT}}  {file_upload_element}
${{FILE_PATH}}       {sample_file_path}
"""

        if submit_element:
            script_content += f"${{SUBMIT_ELEMENT}}  {submit_element}\n"
            
        script_content += """
*** Test Cases ***
Upload File"""
        
        if submit_element:
            script_content += """ And Submit"""
            
        script_content += f"""
    [Documentation]    Navigate to a page and upload a file{" then submit the form" if submit_element else ""}
    
    # Verify the file exists
    File Should Exist    ${{FILE_PATH}}
    
    # Open browser and navigate to URL
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    
    # Wait for the upload element to be present
    Wait Until Page Contains Element    ${{UPLOAD_ELEMENT}}    timeout=${{WAIT_TIME}}s
    
    # Upload the file
    Choose File    ${{UPLOAD_ELEMENT}}    ${{FILE_PATH}}
    
"""
        
        if submit_element:
            script_content += """    # Wait for the submit button to be active (if needed)
    Wait Until Element Is Enabled    ${SUBMIT_ELEMENT}    timeout=${WAIT_TIME}s
    
    # Submit the form
    Click Element    ${SUBMIT_ELEMENT}
    
"""
        
        if include_verification:
            script_content += """    # Add verification steps here based on the expected behavior after upload
    # For example:
    # - Check if a success message appears
    # - Check if the uploaded file name appears in the UI
    # - Check if a preview of the uploaded file is shown
    Sleep    2s    # Wait for any post-upload processing
    
    # Example verification (modify as needed):
    # Wait Until Page Contains    Upload successful    timeout=${WAIT_TIME}s
    # Or check for the file name to appear somewhere in the page
    # ${file_name}=    Get File Name    ${FILE_PATH}
    # Page Should Contain    ${file_name}
    
"""
        
        script_content += """*** Keywords ***
Get File Name
    [Arguments]    ${path}
    ${file_name}=    Set Variable    ${path.split('/')[-1]}
    [Return]    ${file_name}
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
        logger.error(f"Error generating upload script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser file upload tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_upload_file(
        url: str,
        file_upload_element: str,
        file_path: str,
        wait_time: int = 10,
        submit_element: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to a website.
        
        Args:
            url: URL to navigate to
            file_upload_element: Locator for the file upload element
            file_path: Path to the file to upload
            wait_time: Time to wait for elements to be ready in seconds
            submit_element: Optional locator for a submit button to click after upload
            
        Returns:
            Dictionary with upload status
        """
        logger.info(f"Received request to upload file '{file_path}' to element '{file_upload_element}' at URL: {url}")
        result = upload_file(url, file_upload_element, file_path, wait_time, submit_element)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_upload_script(
        url: str,
        output_file: str,
        file_upload_element: str,
        sample_file_path: str,
        browser: str = "Chrome",
        wait_time: int = 10,
        submit_element: Optional[str] = None,
        include_verification: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for file uploads.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            file_upload_element: Locator for the file upload element
            sample_file_path: Example file path to upload (can use a variable in the script)
            browser: Browser to use (default is Chrome)
            wait_time: Time to wait for elements to be ready in seconds
            submit_element: Optional locator for a submit button to click after upload
            include_verification: Whether to include verification steps
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate upload script for URL: {url}")
        result = generate_upload_script(url, output_file, file_upload_element, sample_file_path, browser, wait_time, submit_element, include_verification)
        return result 