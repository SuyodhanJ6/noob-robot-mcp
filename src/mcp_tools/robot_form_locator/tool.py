#!/usr/bin/env python
"""
MCP Tool: Robot Form Locator
Extracts all form elements and their locators from a web page.
"""

import os
import logging
import json
import time
import sys
import shutil
import subprocess
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.chrome.service import Service

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.form_locator')

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def extract_all_locators(url: str, wait_time: int = 20) -> Dict[str, Any]:
    """
    Extract all form elements and their locators from a web page.
    
    Args:
        url: URL of the web page to analyze
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with all detected elements and their locators
    """
    result = {
        "url": url,
        "elements": {},
        "error": None
    }
    
    driver = None
    try:
        logger.info(f"Visiting URL to extract locators: {url}")
        
        # Set up Chrome options for headless browsing
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Try to detect the Chrome binary location
        chrome_binary = None
        possible_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",    # Windows
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                chrome_binary = path
                break
                
        if chrome_binary:
            logger.info(f"Using Chrome binary at: {chrome_binary}")
            chrome_options.binary_location = chrome_binary
            
        # Try different approaches to initialize the WebDriver
        service = None
        try_methods = ["direct", "manager", "path_search", "subprocess"]
        driver = None
        last_error = None
        
        for method in try_methods:
            try:
                if method == "direct":
                    # Direct WebDriver initialization
                    logger.info("Trying direct WebDriver initialization")
                    service = Service()
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                    break
                    
                elif method == "manager" and WEBDRIVER_MANAGER_AVAILABLE:
                    # Try with webdriver-manager if available
                    logger.info("Trying WebDriver Manager initialization")
                    driver = webdriver.Chrome(
                        service=Service(ChromeDriverManager().install()),
                        options=chrome_options
                    )
                    break
                    
                elif method == "path_search":
                    # Search for chromedriver in PATH
                    logger.info("Searching for chromedriver in PATH")
                    chromedriver_path = shutil.which("chromedriver")
                    if chromedriver_path:
                        logger.info(f"Found chromedriver at {chromedriver_path}")
                        service = Service(executable_path=chromedriver_path)
                        driver = webdriver.Chrome(service=service, options=chrome_options)
                        break
                
                elif method == "subprocess":
                    # Try to use subprocess to find Chrome location
                    logger.info("Trying to locate Chrome using subprocess")
                    if sys.platform.startswith('win'):
                        cmd = r'reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve'
                        try:
                            result = subprocess.run(cmd, capture_output=True, shell=True, text=True)
                            if result.returncode == 0:
                                chrome_path = result.stdout.split("REG_SZ")[-1].strip()
                                logger.info(f"Found Chrome at {chrome_path}")
                                chrome_options.binary_location = chrome_path
                        except Exception as e:
                            logger.warning(f"Failed to get Chrome path via registry: {e}")
                    elif sys.platform == 'darwin':  # macOS
                        try:
                            result = subprocess.run(['mdfind', 'kMDItemCFBundleIdentifier = "com.google.Chrome"'], 
                                                    capture_output=True, text=True)
                            if result.stdout.strip():
                                chrome_path = os.path.join(result.stdout.strip().split('\n')[0], 
                                                          'Contents/MacOS/Google Chrome')
                                if os.path.exists(chrome_path):
                                    logger.info(f"Found Chrome at {chrome_path}")
                                    chrome_options.binary_location = chrome_path
                        except Exception as e:
                            logger.warning(f"Failed to get Chrome path via mdfind: {e}")
                    else:  # Linux
                        try:
                            result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
                            if result.returncode == 0:
                                chrome_path = result.stdout.strip()
                                logger.info(f"Found Chrome at {chrome_path}")
                                chrome_options.binary_location = chrome_path
                        except Exception as e:
                            logger.warning(f"Failed to get Chrome path via 'which': {e}")
                            
                    # Now try initializing with updated binary location    
                    service = Service()
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                    break
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Method {method} failed: {e}")
                continue
                
        if driver is None:
            raise Exception(f"All WebDriver initialization methods failed. Last error: {last_error}")
            
        # Configure browser
        logger.info("WebDriver initialized successfully")
        driver.set_page_load_timeout(wait_time * 2)  # Double the wait time for page load
        driver.get(url)
        
        # Wait for the page to load
        logger.info(f"Waiting {wait_time} seconds for page to load")
        time.sleep(wait_time)
        
        # Get all interactive elements
        elements = {}
        
        # Get all input elements
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for i, elem in enumerate(inputs):
            try:
                elem_id = elem.get_attribute("id")
                elem_name = elem.get_attribute("name")
                elem_type = elem.get_attribute("type") or "text"
                elem_value = elem.get_attribute("value") or ""
                elem_placeholder = elem.get_attribute("placeholder") or ""
                elem_class = elem.get_attribute("class") or ""
                
                # Skip hidden inputs
                if elem_type == "hidden":
                    continue
                
                # Generate a key name
                key = elem_name or elem_id or f"input_{i+1}"
                
                # Create locators in various formats
                locators = {}
                if elem_id:
                    locators["id"] = f"id={elem_id}"
                if elem_name:
                    locators["name"] = f"name={elem_name}"
                if elem_class:
                    locators["class"] = f"css=.{elem_class.replace(' ', '.')}"
                
                # Generate XPath
                locators["xpath"] = generate_xpath(elem)
                
                # Add to elements
                elements[key] = {
                    "tag_name": "input",
                    "type": elem_type,
                    "value": elem_value,
                    "placeholder": elem_placeholder,
                    "locators": locators,
                    "recommended_locator": get_recommended_locator(locators)
                }
            except Exception as e:
                logger.warning(f"Error processing input element: {e}")
        
        # Get all button elements
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for i, elem in enumerate(buttons):
            try:
                elem_id = elem.get_attribute("id")
                elem_name = elem.get_attribute("name")
                elem_type = elem.get_attribute("type") or ""
                elem_text = elem.text
                elem_class = elem.get_attribute("class") or ""
                
                # Generate a key name
                key = elem_name or elem_id or f"button_{i+1}"
                
                # Create locators in various formats
                locators = {}
                if elem_id:
                    locators["id"] = f"id={elem_id}"
                if elem_name:
                    locators["name"] = f"name={elem_name}"
                if elem_class:
                    locators["class"] = f"css=.{elem_class.replace(' ', '.')}"
                if elem_text:
                    locators["text"] = f"//button[text()='{elem_text}']"
                
                # Generate XPath
                locators["xpath"] = generate_xpath(elem)
                
                # Add to elements
                elements[key] = {
                    "tag_name": "button",
                    "type": elem_type,
                    "text": elem_text,
                    "locators": locators,
                    "recommended_locator": get_recommended_locator(locators)
                }
            except Exception as e:
                logger.warning(f"Error processing button element: {e}")
        
        # Get all select elements
        selects = driver.find_elements(By.TAG_NAME, "select")
        for i, elem in enumerate(selects):
            try:
                elem_id = elem.get_attribute("id")
                elem_name = elem.get_attribute("name")
                elem_class = elem.get_attribute("class") or ""
                
                # Get options
                options = []
                option_elements = elem.find_elements(By.TAG_NAME, "option")
                for opt in option_elements:
                    opt_value = opt.get_attribute("value")
                    opt_text = opt.text
                    options.append({"value": opt_value, "text": opt_text})
                
                # Generate a key name
                key = elem_name or elem_id or f"select_{i+1}"
                
                # Create locators in various formats
                locators = {}
                if elem_id:
                    locators["id"] = f"id={elem_id}"
                if elem_name:
                    locators["name"] = f"name={elem_name}"
                if elem_class:
                    locators["class"] = f"css=.{elem_class.replace(' ', '.')}"
                
                # Generate XPath
                locators["xpath"] = generate_xpath(elem)
                
                # Add to elements
                elements[key] = {
                    "tag_name": "select",
                    "options": options,
                    "locators": locators,
                    "recommended_locator": get_recommended_locator(locators)
                }
            except Exception as e:
                logger.warning(f"Error processing select element: {e}")
        
        # Get all textarea elements
        textareas = driver.find_elements(By.TAG_NAME, "textarea")
        for i, elem in enumerate(textareas):
            try:
                elem_id = elem.get_attribute("id")
                elem_name = elem.get_attribute("name")
                elem_placeholder = elem.get_attribute("placeholder") or ""
                elem_class = elem.get_attribute("class") or ""
                
                # Generate a key name
                key = elem_name or elem_id or f"textarea_{i+1}"
                
                # Create locators in various formats
                locators = {}
                if elem_id:
                    locators["id"] = f"id={elem_id}"
                if elem_name:
                    locators["name"] = f"name={elem_name}"
                if elem_class:
                    locators["class"] = f"css=.{elem_class.replace(' ', '.')}"
                
                # Generate XPath
                locators["xpath"] = generate_xpath(elem)
                
                # Add to elements
                elements[key] = {
                    "tag_name": "textarea",
                    "placeholder": elem_placeholder,
                    "locators": locators,
                    "recommended_locator": get_recommended_locator(locators)
                }
            except Exception as e:
                logger.warning(f"Error processing textarea element: {e}")
        
        # Get all anchor elements
        anchors = driver.find_elements(By.TAG_NAME, "a")
        for i, elem in enumerate(anchors):
            try:
                elem_id = elem.get_attribute("id")
                elem_href = elem.get_attribute("href")
                elem_text = elem.text
                elem_class = elem.get_attribute("class") or ""
                
                # Skip if no text or href (probably not useful)
                if not elem_text and not elem_href:
                    continue
                    
                # Generate a key name
                key = elem_id or f"link_{i+1}"
                
                # Create locators in various formats
                locators = {}
                if elem_id:
                    locators["id"] = f"id={elem_id}"
                if elem_text:
                    locators["link"] = f"link={elem_text}"
                if elem_href:
                    locators["href"] = f"xpath=//a[@href='{elem_href}']"
                if elem_class:
                    locators["class"] = f"css=.{elem_class.replace(' ', '.')}"
                
                # Generate XPath
                locators["xpath"] = generate_xpath(elem)
                
                # Add to elements
                elements[key] = {
                    "tag_name": "a",
                    "text": elem_text,
                    "href": elem_href,
                    "locators": locators,
                    "recommended_locator": get_recommended_locator(locators)
                }
            except Exception as e:
                logger.warning(f"Error processing anchor element: {e}")
        
        # Get other common elements by class
        labels = driver.find_elements(By.TAG_NAME, "label")
        for i, elem in enumerate(labels):
            try:
                elem_id = elem.get_attribute("id")
                elem_for = elem.get_attribute("for")
                elem_text = elem.text
                elem_class = elem.get_attribute("class") or ""
                
                # Skip if no text (probably not useful)
                if not elem_text:
                    continue
                    
                # Generate a key name
                key = f"label_for_{elem_for}" if elem_for else (elem_id or f"label_{i+1}")
                
                # Create locators in various formats
                locators = {}
                if elem_id:
                    locators["id"] = f"id={elem_id}"
                if elem_for:
                    locators["for"] = f"xpath=//label[@for='{elem_for}']"
                if elem_text:
                    locators["text"] = f"xpath=//label[text()='{elem_text}']"
                if elem_class:
                    locators["class"] = f"css=.{elem_class.replace(' ', '.')}"
                
                # Generate XPath
                locators["xpath"] = generate_xpath(elem)
                
                # Add to elements
                elements[key] = {
                    "tag_name": "label",
                    "for": elem_for,
                    "text": elem_text,
                    "locators": locators,
                    "recommended_locator": get_recommended_locator(locators)
                }
            except Exception as e:
                logger.warning(f"Error processing label element: {e}")
        
        result["elements"] = elements
        return result
        
    except Exception as e:
        error_msg = f"Error extracting locators: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "url": url,
            "elements": {},
            "error": error_msg
        }
    finally:
        if driver:
            driver.quit()

def generate_xpath(element) -> str:
    """
    Generate XPath for an element based on its attributes or position.
    
    Args:
        element: Selenium WebElement
        
    Returns:
        XPath locator string
    """
    try:
        tag_name = element.tag_name
        
        # Try to create an xpath with an ID
        element_id = element.get_attribute("id")
        if element_id:
            return f"xpath=//{tag_name}[@id='{element_id}']"
        
        # Try with name attribute
        element_name = element.get_attribute("name")
        if element_name:
            return f"xpath=//{tag_name}[@name='{element_name}']"
        
        # Try with class attribute
        element_class = element.get_attribute("class")
        if element_class:
            return f"xpath=//{tag_name}[@class='{element_class}']"
        
        # Try with text for elements that typically have text
        if tag_name in ["a", "button", "label", "h1", "h2", "h3", "h4", "h5", "h6", "p"]:
            element_text = element.text
            if element_text:
                return f"xpath=//{tag_name}[text()='{element_text}']"
        
        # Last resort - use position in the DOM
        return f"xpath=(//{tag_name})[1]"
    except Exception as e:
        logger.error(f"Error generating XPath: {e}")
        return "xpath=//body"

def get_recommended_locator(locators: Dict[str, str]) -> str:
    """
    Get the recommended locator from a set of locators.
    
    Args:
        locators: Dictionary of locator types and values
        
    Returns:
        Recommended locator string
    """
    # Priority order: id > name > link > text > class > xpath
    if "id" in locators:
        return locators["id"]
    elif "name" in locators:
        return locators["name"]
    elif "link" in locators:
        return locators["link"]
    elif "text" in locators:
        return locators["text"]
    elif "for" in locators:
        return locators["for"]
    elif "class" in locators:
        return locators["class"]
    elif "xpath" in locators:
        return locators["xpath"]
    else:
        return ""

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the robot_form_locator tool with the MCP server."""
    
    @mcp.tool()
    async def robot_extract_locators(
        url: str,
        wait_time: int = 20
    ) -> Dict[str, Any]:
        """
        Extract all web elements and their locators from a given URL.
        
        Args:
            url: URL of the web page to analyze
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with all detected elements and their locators
        """
        logger.info(f"Extracting locators from URL: {url}")
        
        result = extract_all_locators(url, wait_time)
        return result 