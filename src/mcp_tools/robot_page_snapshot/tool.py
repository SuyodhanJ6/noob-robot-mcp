#!/usr/bin/env python
"""
MCP Tool: Robot Page Snapshot
Takes screenshots of web pages to assist with identifying elements for automation.
"""

import os
import logging
import json
import time
import base64
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile

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
from selenium.common.exceptions import TimeoutException, WebDriverException

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.page_snapshot')

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

def take_page_screenshot(url: str, wait_time: int = 5, full_page: bool = True) -> Dict[str, Any]:
    """
    Take a screenshot of a web page.
    
    Args:
        url: URL of the web page
        wait_time: Time to wait for page to load in seconds
        full_page: Whether to capture the full page or just the viewport
        
    Returns:
        Dictionary with screenshot data and metadata
    """
    result = {
        "url": url,
        "screenshot": None,
        "viewport_size": None,
        "page_title": None,
        "error": None
    }
    
    driver = None
    try:
        # Initialize WebDriver
        driver = initialize_webdriver()
        if not driver:
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Navigate to the URL
        logger.info(f"Navigating to URL: {url}")
        driver.set_page_load_timeout(wait_time * 2)
        driver.get(url)
        
        # Wait for page to load
        logger.info(f"Waiting {wait_time} seconds for page to load")
        time.sleep(wait_time)
        
        # Get page metadata
        result["page_title"] = driver.title
        result["viewport_size"] = {
            "width": driver.execute_script("return window.innerWidth"),
            "height": driver.execute_script("return window.innerHeight")
        }
        
        # Take screenshot
        if full_page:
            # Get the full page height
            total_height = driver.execute_script("return document.body.scrollHeight")
            # Set window size to capture everything
            driver.set_window_size(1920, total_height)
            # Give browser time to adjust
            time.sleep(1)
            
        # Take the screenshot
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            screenshot_path = tmp_file.name
            driver.save_screenshot(screenshot_path)
            
            # Convert to base64
            with open(screenshot_path, "rb") as img_file:
                img_data = img_file.read()
                result["screenshot"] = base64.b64encode(img_data).decode("utf-8")
                
            # Remove the temp file
            os.unlink(screenshot_path)
        
        return result
    except Exception as e:
        logger.error(f"Error taking screenshot: {e}")
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def take_element_screenshot(
    url: str, 
    element_xpath: str, 
    wait_time: int = 5
) -> Dict[str, Any]:
    """
    Take a screenshot of a specific element on a web page.
    
    Args:
        url: URL of the web page
        element_xpath: XPath of the element to capture
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with screenshot data and metadata
    """
    result = {
        "url": url,
        "element_xpath": element_xpath,
        "screenshot": None,
        "element_size": None,
        "error": None
    }
    
    driver = None
    try:
        # Initialize WebDriver
        driver = initialize_webdriver()
        if not driver:
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Navigate to the URL
        logger.info(f"Navigating to URL: {url}")
        driver.set_page_load_timeout(wait_time * 2)
        driver.get(url)
        
        # Wait for page to load
        logger.info(f"Waiting {wait_time} seconds for page to load")
        time.sleep(wait_time)
        
        # Find the element
        if element_xpath.startswith("xpath="):
            element_xpath = element_xpath[6:]
            
        element = driver.find_element("xpath", element_xpath)
        
        # Get element size
        result["element_size"] = {
            "width": element.size["width"],
            "height": element.size["height"]
        }
        
        # Scroll element into view
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)  # Wait for scrolling
        
        # Take screenshot of the element
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            element_screenshot_path = tmp_file.name
            element.screenshot(element_screenshot_path)
            
            # Convert to base64
            with open(element_screenshot_path, "rb") as img_file:
                img_data = img_file.read()
                result["screenshot"] = base64.b64encode(img_data).decode("utf-8")
                
            # Remove the temp file
            os.unlink(element_screenshot_path)
        
        return result
    except Exception as e:
        logger.error(f"Error taking element screenshot: {e}")
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register MCP tool."""
    
    @mcp.tool()
    async def robot_take_page_screenshot(
        url: str,
        wait_time: int = 5,
        full_page: bool = True
    ) -> Dict[str, Any]:
        """
        Take a screenshot of a web page to assist with element identification.
        
        This tool captures a screenshot of the entire web page or just the viewport,
        which can be used by an agent to visually identify elements for automation.
        
        Args:
            url: URL of the web page to capture
            wait_time: Time to wait for page to load in seconds
            full_page: Whether to capture the full page or just the viewport
            
        Returns:
            Dictionary with screenshot data (base64 encoded) and page metadata
        """
        return take_page_screenshot(url, wait_time, full_page)
    
    @mcp.tool()
    async def robot_take_element_screenshot(
        url: str,
        element_xpath: str,
        wait_time: int = 5
    ) -> Dict[str, Any]:
        """
        Take a screenshot of a specific element on a web page.
        
        This tool captures a screenshot of a specific element identified by its XPath,
        which can be useful for verifying that the right element has been located.
        
        Args:
            url: URL of the web page
            element_xpath: XPath of the element to capture (with or without "xpath=" prefix)
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with screenshot data (base64 encoded) and element metadata
        """
        return take_element_screenshot(url, element_xpath, wait_time) 