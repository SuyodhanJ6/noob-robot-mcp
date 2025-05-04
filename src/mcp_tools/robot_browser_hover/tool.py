#!/usr/bin/env python
"""
MCP Tool: Robot Browser Hover
Hovers over an element on a web page for Robot Framework through MCP.
"""

import os
import logging
import json
from typing import Dict, Any, Optional, Tuple
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
from selenium.webdriver.common.action_chains import ActionChains
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

logger = logging.getLogger('robot_tool.browser_hover')

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

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def hover_over_element(
    element_locator: str,
    url: Optional[str] = None,
    wait_time: int = 5,
    hover_duration: float = 0.5
) -> Dict[str, Any]:
    """
    Hover over an element on a web page.
    
    Args:
        element_locator: Locator string for the element to hover over
        url: URL to navigate to (optional, if not provided, will use current page)
        wait_time: Time to wait for element to be available in seconds
        hover_duration: Duration to hover over the element in seconds
        
    Returns:
        Dictionary with the hover operation result
    """
    result = {
        "element_locator": element_locator,
        "url": url,
        "status": "success",
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
        
        # Navigate to URL if provided
        if url:
            logger.info(f"Navigating to URL: {url}")
            driver.set_page_load_timeout(wait_time * 2)
            try:
                driver.get(url)
            except TimeoutException:
                result["status"] = "error"
                result["error"] = f"Timeout after {wait_time*2} seconds while loading {url}"
                return result
            
            # Get page metadata
            result["url"] = driver.current_url
            result["title"] = driver.title
        
        # Parse locator
        by_type, by_value = parse_locator(element_locator)
        
        # Wait for element to be present
        logger.info(f"Waiting for element: {element_locator}")
        try:
            element = WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((by_type, by_value))
            )
        except TimeoutException:
            result["status"] = "error"
            result["error"] = f"Element not found with locator: {element_locator}"
            return result
        
        # Perform hover operation
        logger.info(f"Hovering over element: {element_locator}")
        try:
            actions = ActionChains(driver)
            actions.move_to_element(element).pause(hover_duration).perform()
            
            # Add hover operation details
            element_text = element.text.strip() if element.text else "[No text]"
            result["element_text"] = element_text
            result["element_tag"] = element.tag_name
            
            # Attempt to capture any tooltip or hover effect
            try:
                # Wait briefly to allow any hover effects to appear
                import time
                time.sleep(0.5)
                
                # Attempt to find tooltips or hover elements
                potential_tooltips = driver.find_elements(By.XPATH, "//div[contains(@class, 'tooltip') or contains(@class, 'hover')]")
                if potential_tooltips:
                    result["potential_tooltips"] = [
                        {"text": tip.text, "visible": tip.is_displayed()} 
                        for tip in potential_tooltips
                    ]
            except Exception as e:
                logger.warning(f"Non-critical error detecting tooltips: {e}")
                
        except ElementNotInteractableException:
            result["status"] = "error"
            result["error"] = "Element not interactable for hover"
            return result
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Error hovering over element: {str(e)}"
            return result
        
        # Generate Robot Framework command for hover
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Hover Over Element
    Open Browser    {url}    Chrome
    Maximize Browser Window
    Wait Until Element Is Visible    {element_locator}    timeout={wait_time}s
    Mouse Over    {element_locator}
    # Add a brief pause to allow hover effects to appear
    Sleep    0.5s
    Close Browser
"""

        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error during hover operation: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_hover_script(
    url: str,
    output_file: str,
    element_locator: str,
    browser: str = "Chrome",
    include_verification: bool = True
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for hovering over an element.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        element_locator: Locator string for the element to hover over
        browser: Browser to use (default is Chrome)
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
Documentation     Robot Framework script for hovering over an element
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}                 {url}
${{BROWSER}}             {browser}
${{ELEMENT_LOCATOR}}     {element_locator}

*** Test Cases ***
Hover Over Element
    [Documentation]    Hovers over an element to trigger hover effects
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    
    # Wait for element to be ready
    Wait Until Element Is Visible    ${{ELEMENT_LOCATOR}}    timeout=10s
    
    # Perform hover operation
    Mouse Over    ${{ELEMENT_LOCATOR}}
    
    # Add a brief pause to allow hover effects to appear
    Sleep    0.5s
"""

        if include_verification:
            script_content += """    
    # Add verification steps here based on your application's behavior
    # For example:
    # Element Should Be Visible    css=.tooltip
    # Element Should Contain    css=.hover-info    Expected Info Text
"""
        
        # Ensure the directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Write to file
        with open(output_file, "w") as file:
            file.write(script_content)
        
        result["script_content"] = script_content
        
        return result
    except Exception as e:
        logger.error(f"Error generating hover script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register MCP tool."""
    
    @mcp.tool()
    async def robot_browser_hover(
        element_locator: str,
        url: Optional[str] = None,
        wait_time: int = 5,
        hover_duration: float = 0.5
    ) -> Dict[str, Any]:
        """
        Hover over an element on a web page.
        
        This tool hovers over an element on a web page using a provided locator,
        useful for triggering hover-specific elements like tooltips or dropdown menus.
        
        Args:
            element_locator: Locator string for the element to hover over (e.g., "xpath=//button[@title='Info']")
            url: URL to navigate to (optional, if not provided, will use current page)
            wait_time: Time to wait for element to be available in seconds
            hover_duration: Duration to hover over the element in seconds
            
        Returns:
            Dictionary with the hover operation result
        """
        return hover_over_element(element_locator, url, wait_time, hover_duration)
    
    @mcp.tool()
    async def robot_browser_generate_hover_script(
        url: str,
        output_file: str,
        element_locator: str,
        browser: str = "Chrome",
        include_verification: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for hovering over an element.
        
        This tool generates a Robot Framework script that navigates to a URL
        and hovers over a specified element.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            element_locator: Locator string for the element to hover over
            browser: Browser to use (default is Chrome)
            include_verification: Whether to include verification steps
            
        Returns:
            Dictionary with generation status and file path
        """
        return generate_hover_script(
            url, 
            output_file, 
            element_locator, 
            browser, 
            include_verification
        ) 