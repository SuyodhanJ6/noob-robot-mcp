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
                    locators["class"] = f"class={elem_class}"
                
                # Generate XPath locator
                xpath = generate_xpath(elem)
                if xpath:
                    locators["xpath"] = xpath
                    
                # Get the recommended locator format
                recommended_locator = get_recommended_locator(locators)
                
                # Store element details
                elements[key] = {
                    "type": elem_type,
                    "locators": locators,
                    "recommended_locator": recommended_locator,
                    "value": elem_value,
                    "placeholder": elem_placeholder,
                    "required": elem.get_attribute("required") == "true"
                }
            except Exception as e:
                logger.warning(f"Error processing input element: {e}")
                
        # Get all select elements
        selects = driver.find_elements(By.TAG_NAME, "select")
        for i, elem in enumerate(selects):
            try:
                elem_id = elem.get_attribute("id")
                elem_name = elem.get_attribute("name")
                elem_class = elem.get_attribute("class") or ""
                
                # Generate a key name
                key = elem_name or elem_id or f"select_{i+1}"
                
                # Create locators in various formats
                locators = {}
                if elem_id:
                    locators["id"] = f"id={elem_id}"
                if elem_name:
                    locators["name"] = f"name={elem_name}"
                if elem_class:
                    locators["class"] = f"class={elem_class}"
                
                # Generate XPath locator
                xpath = generate_xpath(elem)
                if xpath:
                    locators["xpath"] = xpath
                    
                # Get the recommended locator format
                recommended_locator = get_recommended_locator(locators)
                
                # Get all options
                options = elem.find_elements(By.TAG_NAME, "option")
                option_values = [opt.get_attribute("value") for opt in options]
                option_texts = [opt.text for opt in options]
                
                # Store element details
                elements[key] = {
                    "type": "select",
                    "locators": locators,
                    "recommended_locator": recommended_locator,
                    "options": {
                        "values": option_values,
                        "texts": option_texts
                    },
                    "required": elem.get_attribute("required") == "true"
                }
            except Exception as e:
                logger.warning(f"Error processing select element: {e}")
                
        # Get all button elements
        buttons = driver.find_elements(By.TAG_NAME, "button")
        buttons.extend(driver.find_elements(By.XPATH, "//input[@type='submit']"))
        buttons.extend(driver.find_elements(By.XPATH, "//input[@type='button']"))
        
        for i, elem in enumerate(buttons):
            try:
                elem_id = elem.get_attribute("id")
                elem_name = elem.get_attribute("name")
                elem_type = elem.get_attribute("type") or "button"
                elem_text = elem.text.strip() if hasattr(elem, 'text') else ""
                elem_value = elem.get_attribute("value") or ""
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
                    locators["class"] = f"class={elem_class}"
                if elem_text:
                    locators["text"] = f"text={elem_text}"
                
                # Generate XPath locator
                xpath = generate_xpath(elem)
                if xpath:
                    locators["xpath"] = xpath
                    
                # Get the recommended locator format
                recommended_locator = get_recommended_locator(locators)
                
                # Determine if this is a submit button
                is_submit = (elem_type == "submit" or 
                             "submit" in elem_text.lower() or 
                             "submit" in elem_value.lower() or
                             "submit" in elem_class.lower() or
                             "submit" in key.lower())
                
                # Store element details
                elements[key] = {
                    "type": "submit" if is_submit else "button",
                    "locators": locators,
                    "recommended_locator": recommended_locator,
                    "text": elem_text,
                    "value": elem_value
                }
            except Exception as e:
                logger.warning(f"Error processing button element: {e}")
                
        # Get all textarea elements
        textareas = driver.find_elements(By.TAG_NAME, "textarea")
        for i, elem in enumerate(textareas):
            try:
                elem_id = elem.get_attribute("id")
                elem_name = elem.get_attribute("name")
                elem_value = elem.get_attribute("value") or ""
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
                    locators["class"] = f"class={elem_class}"
                
                # Generate XPath locator
                xpath = generate_xpath(elem)
                if xpath:
                    locators["xpath"] = xpath
                    
                # Get the recommended locator format
                recommended_locator = get_recommended_locator(locators)
                
                # Store element details
                elements[key] = {
                    "type": "textarea",
                    "locators": locators,
                    "recommended_locator": recommended_locator,
                    "value": elem_value,
                    "placeholder": elem_placeholder,
                    "required": elem.get_attribute("required") == "true"
                }
            except Exception as e:
                logger.warning(f"Error processing textarea element: {e}")
                
        result["elements"] = elements
        result["title"] = driver.title
        result["page_source_length"] = len(driver.page_source)
        
        # Extract form metadata
        result["forms"] = []
        forms = driver.find_elements(By.TAG_NAME, "form")
        for form in forms:
            try:
                form_id = form.get_attribute("id")
                form_name = form.get_attribute("name")
                form_action = form.get_attribute("action")
                form_method = form.get_attribute("method")
                form_class = form.get_attribute("class")
                
                form_info = {
                    "id": form_id,
                    "name": form_name,
                    "action": form_action,
                    "method": form_method,
                    "class": form_class
                }
                result["forms"].append(form_info)
            except Exception as e:
                logger.warning(f"Error processing form metadata: {e}")
                
        # Add any form-related elements not directly inside a form tag
        result["form_related_labels"] = []
        labels = driver.find_elements(By.TAG_NAME, "label")
        for label in labels:
            try:
                label_for = label.get_attribute("for")
                label_text = label.text.strip()
                
                if label_for and label_text:
                    result["form_related_labels"].append({
                        "for": label_for,
                        "text": label_text
                    })
            except Exception as e:
                logger.warning(f"Error processing label: {e}")
                
        # Detect success messages or confirmation elements
        result["potential_success_elements"] = []
        success_candidates = driver.find_elements(By.XPATH, 
            "//*[contains(@id, 'success') or contains(@class, 'success') or contains(text(), 'success') or contains(text(), 'Success')]")
        
        for elem in success_candidates:
            try:
                elem_id = elem.get_attribute("id")
                elem_class = elem.get_attribute("class")
                elem_text = elem.text.strip()
                
                if elem_id or elem_class or elem_text:
                    result["potential_success_elements"].append({
                        "id": elem_id,
                        "class": elem_class,
                        "text": elem_text,
                        "xpath": generate_xpath(elem)
                    })
            except Exception as e:
                logger.warning(f"Error processing success element candidate: {e}")
                
    except Exception as e:
        logger.error(f"Error extracting form locators: {e}")
        result["error"] = str(e)
    
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Browser closed")
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
    
    return result

def enhanced_extract_form_structure(url: str, wait_time: int = 20) -> Dict[str, Any]:
    """
    Enhanced extraction of form structure with intelligent field detection.
    
    This function uses a combination of techniques to better identify form fields:
    1. Label associations with form fields
    2. Placeholder text analysis
    3. Required field detection
    4. Field proximity analysis for labels without explicit 'for' attribute
    5. Common validation patterns detection
    
    Args:
        url: URL of the web page to analyze
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with form structure details optimized for test generation
    """
    # First get all the basic element data
    basic_data = extract_all_locators(url, wait_time)
    
    if basic_data.get("error"):
        return basic_data
        
    result = {
        "url": url,
        "form_fields": {},
        "form_metadata": {},
        "success_indicators": [],
        "error": None
    }
    
    # Extract basic form metadata
    if basic_data.get("forms"):
        result["form_metadata"] = basic_data["forms"][0]  # Use the first form as primary
    
    # Process labels to associate them with fields
    label_map = {}
    for label in basic_data.get("form_related_labels", []):
        if label.get("for") and label.get("text"):
            label_map[label["for"]] = label["text"]
    
    # Process each form element to enhance with labels and smart defaults
    for key, element_data in basic_data.get("elements", {}).items():
        field_type = element_data.get("type", "text")
        
        # Skip non-interactive elements
        if field_type in ["hidden"]:
            continue
            
        # Get element ID from the locator
        element_id = None
        if "id" in element_data.get("locators", {}):
            element_id = element_data["locators"]["id"].replace("id=", "")
            
        # Find associated label
        label = None
        if element_id and element_id in label_map:
            label = label_map[element_id]
            
        # Generate smart field name
        field_name = key.lower()
        if label:
            # Convert label to field name (remove spaces, special chars)
            clean_label = ''.join(c for c in label if c.isalnum() or c == ' ')
            field_name = clean_label.replace(' ', '_').lower()
            
        # Generate smart default value based on field type and name
        default_value = ""
        if field_type == "text":
            if any(name_part in field_name for name_part in ["name", "first", "fname"]):
                default_value = "John"
            elif any(name_part in field_name for name_part in ["last", "lname", "surname"]):
                default_value = "Doe"
        elif field_type == "email":
            default_value = "test@example.com"
        elif field_type == "tel" or "phone" in field_name:
            default_value = "1234567890"
        elif field_type == "password":
            default_value = "TestPassword123!"
        elif field_type == "checkbox":
            default_value = "true"
        elif field_type == "select":
            # Try to select a non-empty option if available
            if element_data.get("options", {}).get("values", []):
                values = element_data["options"]["values"]
                # Skip the first option if it looks like a placeholder
                if len(values) > 1 and (not values[0] or "select" in values[0].lower()):
                    default_value = values[1]
                else:
                    default_value = values[0]
        
        # Add to form fields
        result["form_fields"][field_name] = {
            "locator": element_data.get("recommended_locator", ""),
            "type": field_type,
            "value": default_value,
            "required": element_data.get("required", False),
            "label": label
        }
    
    # Add submit button
    for key, element_data in basic_data.get("elements", {}).items():
        if element_data.get("type") == "submit":
            result["form_fields"]["submit"] = {
                "locator": element_data.get("recommended_locator", ""),
                "type": "submit",
                "value": ""
            }
            break
    
    # Extract potential success indicators
    for element in basic_data.get("potential_success_elements", []):
        if element.get("id") or element.get("xpath"):
            result["success_indicators"].append({
                "locator": f"id={element['id']}" if element.get("id") else element.get("xpath", ""),
                "text": element.get("text", "")
            })
    
    return result

def generate_xpath(element) -> str:
    """
    Generate an XPath locator for an element.
    
    Args:
        element: WebElement object
        
    Returns:
        XPath locator string
    """
    try:
        # Try to get the tag name
        tag_name = element.tag_name
        
        # Try strategies in order of preference
        strategies = [
            # ID strategy
            lambda e: e.get_attribute("id") and f"xpath=//{tag_name}[@id='{e.get_attribute('id')}']",
            
            # Name strategy
            lambda e: e.get_attribute("name") and f"xpath=//{tag_name}[@name='{e.get_attribute('name')}']",
            
            # Class strategy (if unique enough)
            lambda e: e.get_attribute("class") and f"xpath=//{tag_name}[@class='{e.get_attribute('class')}']",
            
            # Text content strategy (for buttons, links, etc.)
            lambda e: e.text and f"xpath=//{tag_name}[text()='{e.text}']",
            
            # Button value strategy
            lambda e: (tag_name == "input" and e.get_attribute("type") in ["button", "submit"]) and 
                      e.get_attribute("value") and 
                      f"xpath=//{tag_name}[@value='{e.get_attribute('value')}']",
            
            # Placeholder strategy
            lambda e: e.get_attribute("placeholder") and f"xpath=//{tag_name}[@placeholder='{e.get_attribute('placeholder')}']",
        ]
        
        for strategy in strategies:
            result = strategy(element)
            if result:
                return result
                
        # Fallback to a more complex path
        return None
        
    except Exception as e:
        logger.warning(f"Error generating XPath: {e}")
        return None

def get_recommended_locator(locators: Dict[str, str]) -> str:
    """
    Get the recommended locator from a dictionary of locators.
    
    Args:
        locators: Dictionary of locator types and values
        
    Returns:
        The recommended locator string
    """
    # Order of preference
    preference = ["id", "name", "text", "xpath", "class"]
    
    for locator_type in preference:
        if locator_type in locators:
            return locators[locator_type]
    
    # Default to the first available locator
    return next(iter(locators.values())) if locators else ""

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register MCP tool."""
    
    @mcp.tool()
    async def robot_extract_locators(
        url: str,
        wait_time: int = 20
    ) -> Dict[str, Any]:
        """
        Extract all form elements and their locators from a web page.
        
        Args:
            url: URL of the web page to analyze
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with all detected elements and their locators
        """
        return extract_all_locators(url, wait_time)
        
    @mcp.tool()
    async def robot_extract_form_enhanced(
        url: str,
        wait_time: int = 20
    ) -> Dict[str, Any]:
        """
        Extract form structure with enhanced detection capabilities.
        
        This tool provides more accurate form field detection, automatic field labeling,
        smart default values, and better success indicator detection. It's optimized
        for generating more accurate Robot Framework test scripts.
        
        Args:
            url: URL of the web page to analyze
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with enhanced form structure details
        """
        return enhanced_extract_form_structure(url, wait_time) 