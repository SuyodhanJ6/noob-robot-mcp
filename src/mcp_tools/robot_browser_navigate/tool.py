#!/usr/bin/env python
"""
MCP Tool: Robot Browser Navigate
Provides browser navigation functionality for Robot Framework through MCP.
"""

import os
import logging
import time
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from urllib.parse import urlparse, urljoin

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
from selenium.common.exceptions import TimeoutException, WebDriverException

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_navigate')

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

def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid.
    
    Args:
        url: URL to check
        
    Returns:
        True if the URL is valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def extract_page_info(driver: webdriver.Chrome) -> Dict[str, Any]:
    """
    Extract information from the current page.
    
    Args:
        driver: WebDriver instance
        
    Returns:
        Dictionary with page information
    """
    page_info = {
        "url": driver.current_url,
        "title": driver.title
    }
    
    # Try to get page metadata
    try:
        meta_tags = driver.find_elements(By.TAG_NAME, "meta")
        meta_data = {}
        
        for tag in meta_tags:
            name = tag.get_attribute("name")
            property_attr = tag.get_attribute("property")
            content = tag.get_attribute("content")
            
            if name and content:
                meta_data[name] = content
            elif property_attr and content:
                meta_data[property_attr] = content
                
        if meta_data:
            page_info["meta"] = meta_data
    except:
        pass
    
    # Try to get page links
    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        page_links = []
        
        for link in links[:10]:  # Limit to first 10 links to avoid excessive data
            href = link.get_attribute("href")
            text = link.text.strip()
            
            if href and text:
                page_links.append({"href": href, "text": text})
                
        if page_links:
            page_info["links"] = page_links
    except:
        pass
    
    return page_info

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def navigate_to_url(
    url: str,
    wait_time: int = 10,
    cookies: Optional[List[Dict[str, Any]]] = None,
    wait_for_selector: Optional[str] = None
) -> Dict[str, Any]:
    """
    Navigate to a URL in a browser.
    
    Args:
        url: URL to navigate to
        wait_time: Time to wait for page to load in seconds
        cookies: List of cookies to set before navigation
        wait_for_selector: Optional CSS selector to wait for
        
    Returns:
        Dictionary with navigation status and page information
    """
    result = {
        "url": url,
        "status": "success",
        "page_info": None,
        "robot_command": None,
        "error": None
    }
    
    # Check if URL is valid
    if not is_valid_url(url):
        result["status"] = "error"
        result["error"] = f"Invalid URL: {url}"
        return result
    
    driver = None
    try:
        # Initialize WebDriver
        driver = initialize_webdriver()
        if not driver:
            result["status"] = "error"
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Set cookies if provided
        if cookies:
            # First navigate to the domain (required to set cookies)
            parsed_url = urlparse(url)
            domain_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            driver.get(domain_url)
            
            # Set each cookie
            for cookie in cookies:
                driver.add_cookie(cookie)
        
        # Navigate to the URL
        logger.info(f"Navigating to URL: {url}")
        driver.set_page_load_timeout(wait_time * 2)
        driver.get(url)
        
        # Wait for specific selector if provided
        if wait_for_selector:
            logger.info(f"Waiting for selector: {wait_for_selector}")
            try:
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
                )
            except TimeoutException:
                result["status"] = "warning"
                result["warning"] = f"Timeout waiting for selector: {wait_for_selector}"
                # Continue anyway
        else:
            # Wait for page to load by waiting for body element
            try:
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                result["status"] = "warning"
                result["warning"] = "Timeout waiting for page to load"
                # Continue anyway
        
        # Extract page information
        page_info = extract_page_info(driver)
        result["page_info"] = page_info
        
        # Generate Robot Framework command
        if wait_for_selector:
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Navigate To URL And Wait For Element
    [Arguments]    ${{url}}    ${{selector}}
    Open Browser    ${{url}}    Chrome
    Wait Until Page Contains Element    css:{wait_for_selector}    timeout={wait_time}s
"""
        else:
            robot_command = f"""*** Settings ***
Library           SeleniumLibrary

*** Keywords ***
Navigate To URL
    [Arguments]    ${{url}}
    Open Browser    ${{url}}    Chrome
    Wait Until Page Contains Element    tag:body    timeout={wait_time}s
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error navigating to URL: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_navigation_script(
    url: str,
    output_file: str,
    browser: str = "Chrome",
    wait_time: int = 10,
    wait_for_selector: Optional[str] = None,
    verify_title: bool = True,
    include_links: bool = False
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for browser navigation.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        browser: Browser to use (default is Chrome)
        wait_time: Time to wait for page to load in seconds
        wait_for_selector: Optional CSS selector to wait for
        verify_title: Whether to verify the page title
        include_links: Whether to include link extraction
        
    Returns:
        Dictionary with generation status and file path
    """
    result = {
        "status": "success",
        "output_file": output_file,
        "error": None
    }
    
    try:
        # Extract domain for documentation
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Generate Robot Framework script
        script_content = f"""*** Settings ***
Documentation     Robot Framework script for navigating to {domain}
Library           SeleniumLibrary
Library           Collections
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}          {url}
${{BROWSER}}      {browser}
${{WAIT_TIME}}    {wait_time}
"""

        if wait_for_selector:
            script_content += f"${{SELECTOR}}     css:{wait_for_selector}\n"
            
        script_content += """
*** Test Cases ***
Navigate To Website
    [Documentation]    Navigate to a website and verify it loads correctly
    
    # Open browser and navigate to URL
    Open Browser    ${URL}    ${BROWSER}
    Maximize Browser Window
    
"""
        
        if wait_for_selector:
            script_content += """    # Wait for specific element to be present
    Wait Until Page Contains Element    ${SELECTOR}    timeout=${WAIT_TIME}s
    
"""
        else:
            script_content += """    # Wait for page to load
    Wait Until Page Contains Element    tag:body    timeout=${WAIT_TIME}s
    
"""
        
        if verify_title:
            script_content += """    # Get and verify page title
    ${title}=    Get Title
    Log    Page title: ${title}
    Should Not Be Empty    ${title}
    
"""
        
        if include_links:
            script_content += """    # Extract page links
    @{links}=    Get WebElements    tag:a
    ${link_count}=    Get Length    ${links}
    Log    Found ${link_count} links on the page
    
    # Display first few links (if any)
    FOR    ${link}    IN    @{links}[0:5]
        ${href}=    Get Element Attribute    ${link}    href
        ${text}=    Get Text    ${link}
        Log    Link: ${text} -> ${href}
    END
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
        logger.error(f"Error generating navigation script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser navigation tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_navigate(
        url: str,
        wait_time: int = 10,
        cookies: Optional[List[Dict[str, Any]]] = None,
        wait_for_selector: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Navigate to a URL in a browser.
        
        Args:
            url: URL to navigate to
            wait_time: Time to wait for page to load in seconds
            cookies: List of cookies to set before navigation
            wait_for_selector: Optional CSS selector to wait for
            
        Returns:
            Dictionary with navigation status and page information
        """
        logger.info(f"Received request to navigate to URL: {url}")
        result = navigate_to_url(url, wait_time, cookies, wait_for_selector)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_navigation_script(
        url: str,
        output_file: str,
        browser: str = "Chrome",
        wait_time: int = 10,
        wait_for_selector: Optional[str] = None,
        verify_title: bool = True,
        include_links: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for browser navigation.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            browser: Browser to use (default is Chrome)
            wait_time: Time to wait for page to load in seconds
            wait_for_selector: Optional CSS selector to wait for
            verify_title: Whether to verify the page title
            include_links: Whether to include link extraction
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate navigation script for URL: {url}")
        result = generate_navigation_script(url, output_file, browser, wait_time, wait_for_selector, verify_title, include_links)
        return result 