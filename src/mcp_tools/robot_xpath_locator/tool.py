#!/usr/bin/env python
"""
MCP Tool: Robot XPath Locator
Advanced tool for generating robust XPath locators for web elements.
Helps create reliable locators for dynamic elements in Robot Framework tests.
"""

import os
import logging
import json
import time
import sys
import re
import shutil
import subprocess
from typing import List, Dict, Any, Optional, Union, Tuple
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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webelement import WebElement

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.xpath_locator')

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
                # Implementation details omitted for brevity
                pass
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Method {method} failed: {e}")
            continue
            
    if driver is None:
        logger.error(f"All WebDriver initialization methods failed. Last error: {last_error}")
        
    return driver

# -----------------------------------------------------------------------------
# Core XPath Generation Functions
# -----------------------------------------------------------------------------

def generate_attribute_xpath(element: WebElement) -> Optional[str]:
    """
    Generate XPath using element attributes.
    
    Args:
        element: WebElement object
        
    Returns:
        XPath locator string or None
    """
    try:
        tag_name = element.tag_name
        
        # List of attributes to try for XPath generation
        important_attrs = ["id", "name", "class", "data-testid", "data-cy", "data-automation-id", 
                           "aria-label", "role", "type", "title", "placeholder"]
        
        for attr in important_attrs:
            value = element.get_attribute(attr)
            if value:
                # For class attribute, we need special handling as it can contain multiple classes
                if attr == "class":
                    classes = value.split()
                    if len(classes) > 0:
                        # Try with the most specific class (usually the longest or last one)
                        specific_class = max(classes, key=len)
                        xpath = f"xpath=//{tag_name}[contains(@class, '{specific_class}')]"
                        return xpath
                else:
                    # For other attributes, use exact matching
                    xpath = f"xpath=//{tag_name}[@{attr}='{value}']"
                    return xpath
                    
        return None
    except Exception as e:
        logger.warning(f"Error generating attribute XPath: {e}")
        return None

def generate_text_xpath(element: WebElement) -> Optional[str]:
    """
    Generate XPath using element text content.
    
    Args:
        element: WebElement object
        
    Returns:
        XPath locator string or None
    """
    try:
        tag_name = element.tag_name
        text = element.text.strip()
        
        if text:
            # For shorter text, use exact matching
            if len(text) < 50:
                xpath = f"xpath=//{tag_name}[text()='{text}']"
                return xpath
            else:
                # For longer text, use contains
                first_few_words = ' '.join(text.split()[:5])
                xpath = f"xpath=//{tag_name}[contains(text(), '{first_few_words}')]"
                return xpath
                
        return None
    except Exception as e:
        logger.warning(f"Error generating text XPath: {e}")
        return None

def generate_position_xpath(element: WebElement, driver: webdriver.Chrome) -> Optional[str]:
    """
    Generate XPath using element position and parent-child relationships.
    
    Args:
        element: WebElement object
        driver: WebDriver instance
        
    Returns:
        XPath locator string or None
    """
    try:
        # Get parent element
        parent_element = driver.execute_script("return arguments[0].parentNode;", element)
        if not parent_element:
            return None
            
        # Try to get parent attributes
        parent_tag = parent_element.tag_name
        parent_id = parent_element.get_attribute("id")
        parent_class = parent_element.get_attribute("class")
        
        tag_name = element.tag_name
        
        # If parent has ID, use it for more specific XPath
        if parent_id:
            # Find the position of this element among siblings of the same type
            siblings = driver.execute_script(
                f"return arguments[0].querySelectorAll('{tag_name}')", parent_element)
            
            if siblings:
                for i, sibling in enumerate(siblings, 1):
                    if sibling == element:
                        return f"xpath=//{parent_tag}[@id='{parent_id}']//{tag_name}[{i}]"
        
        # If parent has class, use it as fallback
        if parent_class:
            specific_class = max(parent_class.split(), key=len) if parent_class else ""
            if specific_class:
                # Count siblings of the same tag
                siblings = driver.execute_script(
                    f"return arguments[0].querySelectorAll('{tag_name}')", parent_element)
                
                if siblings:
                    for i, sibling in enumerate(siblings, 1):
                        if sibling == element:
                            return f"xpath=//{parent_tag}[contains(@class, '{specific_class}')]//{tag_name}[{i}]"
        
        return None
    except Exception as e:
        logger.warning(f"Error generating position XPath: {e}")
        return None

def generate_nearby_text_xpath(element: WebElement, driver: webdriver.Chrome) -> Optional[str]:
    """
    Generate XPath using nearby text elements (like labels).
    
    Args:
        element: WebElement object
        driver: WebDriver instance
        
    Returns:
        XPath locator string or None
    """
    try:
        tag_name = element.tag_name
        
        # Try to find associated label (for input fields)
        if tag_name in ["input", "select", "textarea"]:
            element_id = element.get_attribute("id")
            if element_id:
                # Try to find label with for attribute
                label_script = f"return document.querySelector('label[for=\"{element_id}\"]')"
                label = driver.execute_script(label_script)
                
                if label and label.text:
                    label_text = label.text.strip()
                    if label_text:
                        xpath = f"xpath=//{tag_name}[@id='{element_id}' and //label[@for='{element_id}' and contains(text(), '{label_text}')]]"
                        return xpath
        
        # Try to find nearby text nodes for buttons and links
        if tag_name in ["a", "button", "span", "div"]:
            # Look at element text
            if element.text:
                text = element.text.strip()
                if text:
                    xpath = f"xpath=//{tag_name}[contains(text(), '{text}')]"
                    return xpath
                    
        return None
    except Exception as e:
        logger.warning(f"Error generating nearby text XPath: {e}")
        return None

def generate_css_xpath(element: WebElement) -> Optional[str]:
    """
    Generate XPath using CSS selector attributes.
    
    Args:
        element: WebElement object
        
    Returns:
        XPath locator string or None
    """
    try:
        tag_name = element.tag_name
        
        # Try with common CSS selector attributes
        css_attrs = ["id", "class", "name", "type", "value"]
        
        for attr in css_attrs:
            value = element.get_attribute(attr)
            if value:
                if attr == "class":
                    classes = value.split()
                    if len(classes) > 0:
                        class_selector = '.'.join(classes)
                        return f"css={tag_name}.{class_selector}"
                elif attr == "id":
                    return f"css=#{value}"
                else:
                    return f"css={tag_name}[{attr}='{value}']"
                    
        return None
    except Exception as e:
        logger.warning(f"Error generating CSS XPath: {e}")
        return None
        
# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def find_element_by_description(url: str, element_description: str, wait_time: int = 20) -> Dict[str, Any]:
    """
    Find an element by its description and generate multiple locator strategies.
    
    Args:
        url: URL of the web page
        element_description: Text description of the element (e.g., "Login button", "Username field")
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with locator strategies and element details
    """
    result = {
        "url": url,
        "element_description": element_description,
        "locators": {},
        "recommended_locator": None,
        "element_details": {},
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
        
        # Try to find the element based on the description
        element = find_by_description(driver, element_description)
        
        if not element:
            result["error"] = f"Could not find element matching description: {element_description}"
            return result
            
        # Generate different types of locators
        locators = {}
        
        # Attribute-based XPath
        attr_xpath = generate_attribute_xpath(element)
        if attr_xpath:
            locators["attribute"] = attr_xpath
            
        # Text-based XPath
        text_xpath = generate_text_xpath(element)
        if text_xpath:
            locators["text"] = text_xpath
            
        # Position-based XPath
        position_xpath = generate_position_xpath(element, driver)
        if position_xpath:
            locators["position"] = position_xpath
            
        # Nearby text XPath
        nearby_text_xpath = generate_nearby_text_xpath(element, driver)
        if nearby_text_xpath:
            locators["nearby_text"] = nearby_text_xpath
            
        # CSS selector
        css_selector = generate_css_xpath(element)
        if css_selector:
            locators["css"] = css_selector
            
        # Store locators in result
        result["locators"] = locators
        
        # Determine recommended locator
        result["recommended_locator"] = get_recommended_locator(locators)
        
        # Get element details
        result["element_details"] = {
            "tag_name": element.tag_name,
            "text": element.text,
            "is_displayed": element.is_displayed(),
            "is_enabled": element.is_enabled(),
            "attributes": {
                attr: element.get_attribute(attr) for attr in [
                    "id", "name", "class", "type", "value", "placeholder", "href",
                    "data-testid", "aria-label", "role"
                ] if element.get_attribute(attr)
            }
        }
        
        return result
    except Exception as e:
        logger.error(f"Error finding element: {e}")
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def find_by_description(driver: webdriver.Chrome, description: str) -> Optional[WebElement]:
    """
    Find an element based on a text description.
    
    Args:
        driver: WebDriver instance
        description: Text description of the element
        
    Returns:
        WebElement if found, None otherwise
    """
    # Parse the description to determine element type and characteristics
    element_type = "unknown"
    
    if "button" in description.lower():
        element_type = "button"
    elif "link" in description.lower():
        element_type = "link"
    elif "field" in description.lower() or "input" in description.lower():
        element_type = "input"
    elif "dropdown" in description.lower() or "select" in description.lower():
        element_type = "select"
    elif "checkbox" in description.lower():
        element_type = "checkbox"
    elif "radio" in description.lower():
        element_type = "radio"
    elif "image" in description.lower() or "img" in description.lower():
        element_type = "image"
    
    # Extract key terms from the description
    key_terms = [term.strip().lower() for term in re.split(r'\s+', description) 
                 if len(term.strip()) > 2 and term.lower() not in [
                     "the", "and", "for", "with", "button", "link", "field", 
                     "input", "dropdown", "select", "checkbox", "radio", "image"
                 ]]
    
    # Strategy 1: Search by text content
    for term in key_terms:
        try:
            # Try exact match
            elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{term}')]")
            if elements:
                return elements[0]
                
            # Try partial match with case insensitivity
            elements = driver.find_elements(By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{term.lower()}')]")
            if elements:
                return elements[0]
        except Exception:
            pass
    
    # Strategy 2: Search by element type and attributes
    if element_type == "button":
        # Look for buttons with matching text
        for term in key_terms:
            try:
                # Try button elements
                elements = driver.find_elements(By.XPATH, f"//button[contains(text(), '{term}')]")
                if elements:
                    return elements[0]
                    
                # Try input buttons
                elements = driver.find_elements(By.XPATH, f"//input[@type='button' and contains(@value, '{term}')]")
                if elements:
                    return elements[0]
                    
                # Try submit buttons
                elements = driver.find_elements(By.XPATH, f"//input[@type='submit' and contains(@value, '{term}')]")
                if elements:
                    return elements[0]
            except Exception:
                pass
    
    elif element_type == "link":
        # Look for links with matching text
        for term in key_terms:
            try:
                elements = driver.find_elements(By.XPATH, f"//a[contains(text(), '{term}')]")
                if elements:
                    return elements[0]
            except Exception:
                pass
    
    elif element_type in ["input", "field"]:
        # Look for input fields with matching placeholder, label, or name
        for term in key_terms:
            try:
                # Try by placeholder
                elements = driver.find_elements(By.XPATH, f"//input[contains(@placeholder, '{term}')]")
                if elements:
                    return elements[0]
                    
                # Try by label
                elements = driver.find_elements(By.XPATH, f"//label[contains(text(), '{term}')]/following::input[1]")
                if elements:
                    return elements[0]
                    
                # Try by name or id
                elements = driver.find_elements(By.XPATH, f"//input[contains(@name, '{term}') or contains(@id, '{term}')]")
                if elements:
                    return elements[0]
            except Exception:
                pass
    
    # Strategy 3: Generic search
    try:
        # Try finding elements with matching id, name, class, or title
        for term in key_terms:
            # Check for attributes that might contain the term
            elements = driver.find_elements(
                By.XPATH, 
                f"//*[contains(@id, '{term}') or contains(@name, '{term}') or contains(@class, '{term}') or contains(@title, '{term}')]"
            )
            if elements:
                return elements[0]
    except Exception:
        pass
    
    return None

def get_recommended_locator(locators: Dict[str, str]) -> Optional[str]:
    """
    Get the recommended locator from a dictionary of locators.
    
    Args:
        locators: Dictionary of locator types and values
        
    Returns:
        The recommended locator string or None
    """
    # Order of preference
    preference = ["attribute", "text", "css", "nearby_text", "position"]
    
    for locator_type in preference:
        if locator_type in locators:
            return locators[locator_type]
    
    # Default to the first available locator
    return next(iter(locators.values())) if locators else None

def test_xpath_locator(url: str, xpath: str, wait_time: int = 20) -> Dict[str, Any]:
    """
    Test if an XPath locator successfully finds an element on the page.
    
    Args:
        url: URL of the web page
        xpath: XPath locator to test
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with test results
    """
    result = {
        "url": url,
        "xpath": xpath,
        "is_valid": False,
        "element_found": False,
        "element_details": {},
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
        
        # Check if the XPath is valid and find the element
        try:
            # Process the XPath to extract the actual expression without prefix
            actual_xpath = xpath
            if xpath.startswith("xpath="):
                actual_xpath = xpath[6:]
            elif xpath.startswith("css="):
                actual_xpath = xpath[4:]
                result["is_valid"] = True
                
                # Find element using CSS selector
                element = driver.find_element(By.CSS_SELECTOR, actual_xpath)
                result["element_found"] = True
                
                # Get element details
                result["element_details"] = {
                    "tag_name": element.tag_name,
                    "text": element.text,
                    "is_displayed": element.is_displayed(),
                    "is_enabled": element.is_enabled(),
                    "attributes": {
                        attr: element.get_attribute(attr) for attr in [
                            "id", "name", "class", "type", "value", "placeholder"
                        ] if element.get_attribute(attr)
                    }
                }
                return result
            
            # Validate XPath syntax
            result["is_valid"] = True
            
            # Find element using XPath
            element = driver.find_element(By.XPATH, actual_xpath)
            result["element_found"] = True
            
            # Get element details
            result["element_details"] = {
                "tag_name": element.tag_name,
                "text": element.text,
                "is_displayed": element.is_displayed(),
                "is_enabled": element.is_enabled(),
                "attributes": {
                    attr: element.get_attribute(attr) for attr in [
                        "id", "name", "class", "type", "value", "placeholder"
                    ] if element.get_attribute(attr)
                }
            }
            
        except NoSuchElementException:
            result["is_valid"] = True
            result["element_found"] = False
            result["error"] = "Element not found with the given XPath"
        except Exception as e:
            result["is_valid"] = False
            result["error"] = f"Invalid XPath syntax: {str(e)}"
            
        return result
    except Exception as e:
        logger.error(f"Error testing XPath: {e}")
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
    async def robot_find_xpath_by_description(
        url: str,
        element_description: str,
        wait_time: int = 20
    ) -> Dict[str, Any]:
        """
        Find an element by its description and generate multiple XPath locator strategies.
        
        This tool helps find elements on web pages based on natural language descriptions,
        and generates robust XPath locators that can be used in Robot Framework tests.
        
        Args:
            url: URL of the web page to analyze
            element_description: Text description of the element (e.g., "Login button", "Username field")
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with locator strategies and element details
        """
        return find_element_by_description(url, element_description, wait_time)
        
    @mcp.tool()
    async def robot_test_xpath_locator(
        url: str,
        xpath: str,
        wait_time: int = 20
    ) -> Dict[str, Any]:
        """
        Test if an XPath locator successfully finds an element on a web page.
        
        This tool validates XPath syntax and tests if the XPath can find an element
        on the specified page. It provides details about the found element if successful.
        
        Args:
            url: URL of the web page to test
            xpath: XPath locator to test (with or without "xpath=" prefix)
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with test results and element details if found
        """
        return test_xpath_locator(url, xpath, wait_time) 