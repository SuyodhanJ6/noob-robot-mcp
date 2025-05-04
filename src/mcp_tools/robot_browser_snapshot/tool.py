#!/usr/bin/env python
"""
MCP Tool: Robot Browser Snapshot
Captures accessibility snapshot of the current page for Robot Framework through MCP.
"""

import os
import logging
import json
import base64
from typing import Dict, Any, Optional, List
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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_snapshot')

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

def get_element_accessibility_info(driver: webdriver.Chrome) -> List[Dict[str, Any]]:
    """
    Extract accessibility information for elements on the page.
    
    Args:
        driver: WebDriver instance
        
    Returns:
        List of dictionaries with accessibility information
    """
    # Script to extract accessibility information from elements
    script = """
    function getAccessibilityInfo() {
        const elements = document.querySelectorAll('button, a, input, select, textarea, [role]');
        const result = [];
        
        elements.forEach((el, index) => {
            const rect = el.getBoundingClientRect();
            
            // Skip hidden elements
            if (rect.width === 0 || rect.height === 0) return;
            
            const computedStyle = window.getComputedStyle(el);
            if (computedStyle.display === 'none' || computedStyle.visibility === 'hidden') return;
            
            // Get text content
            let textContent = el.textContent || '';
            textContent = textContent.trim();
            
            // Get accessible name
            let accessibleName = el.getAttribute('aria-label') || 
                               el.getAttribute('alt') || 
                               el.getAttribute('title') || 
                               el.getAttribute('placeholder') || 
                               textContent;
            
            // Get element info
            const info = {
                id: el.id || null,
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type') || null,
                role: el.getAttribute('role') || null,
                text: textContent,
                name: accessibleName,
                isEnabled: !el.disabled,
                isRequired: el.required || false,
                hasError: el.getAttribute('aria-invalid') === 'true',
                attributes: {},
                location: {
                    x: Math.round(rect.left),
                    y: Math.round(rect.top),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                },
                xpath: generateXPath(el),
                cssSelector: generateCssSelector(el),
                ref: "element_" + index  // Reference ID for the element
            };
            
            // Add common attributes
            ['name', 'value', 'href', 'src', 'for', 'placeholder', 'aria-label', 'aria-labelledby', 'aria-describedby'].forEach(attr => {
                if (el.hasAttribute(attr)) {
                    info.attributes[attr] = el.getAttribute(attr);
                }
            });
            
            result.push(info);
        });
        
        return result;
        
        // Helper function to generate XPath
        function generateXPath(element) {
            if (element.id) return `//*[@id="${element.id}"]`;
            
            let path = '';
            while (element !== document.body && element.parentElement) {
                let siblingCount = 0;
                let siblingIndex = 0;
                let siblings = element.parentElement.children;
                
                for (let i = 0; i < siblings.length; i++) {
                    if (siblings[i].tagName === element.tagName) {
                        siblingCount++;
                        if (siblings[i] === element) {
                            siblingIndex = siblingCount;
                        }
                    }
                }
                
                const tag = element.tagName.toLowerCase();
                path = siblingCount > 1 ? 
                    `/${tag}[${siblingIndex}]${path}` : 
                    `/${tag}${path}`;
                    
                element = element.parentElement;
            }
            
            return `/html/body${path}`;
        }
        
        // Helper function to generate CSS selector
        function generateCssSelector(element) {
            if (element.id) return `#${element.id}`;
            
            let selector = element.tagName.toLowerCase();
            if (element.className) {
                const classes = element.className.split(/\s+/)
                    .filter(cls => cls.trim().length > 0)
                    .map(cls => `.${cls}`)
                    .join('');
                selector += classes;
            }
            
            return selector;
        }
    }
    
    return getAccessibilityInfo();
    """
    
    try:
        accessibility_data = driver.execute_script(script)
        return accessibility_data
    except Exception as e:
        logger.error(f"Error extracting accessibility information: {e}")
        return []

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def take_page_snapshot(url: Optional[str] = None, wait_time: int = 5) -> Dict[str, Any]:
    """
    Capture an accessibility snapshot of the current page.
    
    Args:
        url: URL to navigate to (optional, if not provided, will use current page)
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with page snapshot data
    """
    result = {
        "url": url,
        "title": None,
        "snapshot": None,
        "elements": [],
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
        result["title"] = driver.title
        result["url"] = driver.current_url
        
        # Wait for the page to be fully loaded
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Take a screenshot and encode as base64
        screenshot = driver.get_screenshot_as_base64()
        result["snapshot"] = screenshot
        
        # Get accessibility information about elements on the page
        elements = get_element_accessibility_info(driver)
        result["elements"] = elements
        
        # Generate Robot Framework command for snapshot
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Take Page Snapshot
    Open Browser    {url}    Chrome
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout=10s
    # Capture page state with accessibility information
    # This would require a custom library in actual Robot Framework
"""

        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error taking page snapshot: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_snapshot_script(
    url: str, 
    output_file: str,
    browser: str = "Chrome"
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for taking a page snapshot.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        browser: Browser to use (default is Chrome)
        
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
Documentation     Robot Framework script for taking a page snapshot of {url}
Library           SeleniumLibrary

*** Variables ***
${{URL}}          {url}
${{BROWSER}}      {browser}
${{SCREENSHOT_PATH}}    screenshots/page_snapshot.png

*** Test Cases ***
Take Page Snapshot
    [Documentation]    Navigate to the specified URL and take a snapshot
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout=10s
    Capture Page Screenshot    ${{SCREENSHOT_PATH}}
    
    # Log page information
    ${{'title'}}=    Get Title
    Log    Page Title: ${{title}}
    
    # Element information logging would require custom keywords in production
    Close Browser
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
        logger.error(f"Error generating snapshot script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register MCP tool."""
    
    @mcp.tool()
    async def robot_browser_snapshot(
        url: Optional[str] = None,
        wait_time: int = 5
    ) -> Dict[str, Any]:
        """
        Capture an accessibility snapshot of the current page.
        
        This tool captures a snapshot of a web page's accessibility information,
        including interactive elements and their properties.
        
        Args:
            url: URL to navigate to (optional, if not provided, will use current page)
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with page snapshot data including accessibility information
        """
        return take_page_snapshot(url, wait_time)
    
    @mcp.tool()
    async def robot_browser_generate_snapshot_script(
        url: str,
        output_file: str,
        browser: str = "Chrome"
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for taking a page snapshot.
        
        This tool generates a Robot Framework script that navigates to a URL
        and takes a snapshot of the page.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            browser: Browser to use (default is Chrome)
            
        Returns:
            Dictionary with generation status and file path
        """
        return generate_snapshot_script(url, output_file, browser) 