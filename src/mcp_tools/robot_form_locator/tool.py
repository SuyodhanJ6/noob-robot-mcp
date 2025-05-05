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

# Import shared browser manager
from ..robot_browser_manager import BrowserManager

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
    
    try:
        logger.info(f"Getting shared WebDriver to extract locators for: {url}")
        driver = BrowserManager.get_driver()
        
        # Remove local WebDriver initialization logic
        # Set up Chrome options for headless browsing
        # chrome_options = Options()
        # ... rest of initialization code ...
        # if driver is None:
        #     raise Exception(f"All WebDriver initialization methods failed. Last error: {last_error}")

        # Navigate to URL if necessary
        current_url_before_nav = driver.current_url
        if url != current_url_before_nav:
             logger.info(f"Navigating to URL: {url}")
             driver.set_page_load_timeout(wait_time * 2)  # Double the wait time for page load
             driver.get(url)
        else:
             logger.info(f"Already at URL: {url}")
            
        # Wait for the page to load (consider a more robust wait strategy if needed)
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
    result = {"url": url, "form_fields": {}, "form_metadata": {}, "success_indicators": [], "error": None}
    driver = None
    try:
        logger.info(f"Enhanced form structure extraction for URL: {url}")
        driver = BrowserManager.get_driver() # Use shared manager

        # Navigate if necessary
        current_url_before_nav = driver.current_url
        if url != current_url_before_nav:
             logger.info(f"Navigating to URL: {url}")
             driver.set_page_load_timeout(wait_time * 2)
             driver.get(url)
        else:
             logger.info(f"Already at URL: {url}")
             
        logger.info(f"Waiting {wait_time} seconds for enhanced extraction")
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
        logger.error(f"Error extracting form structure: {e}")
        result["error"] = str(e)
    
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
        logger.info(f"Received request to extract locators for URL: {url}")
        # Call the modified function
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
        logger.info(f"Received request for enhanced form extraction for URL: {url}")
        # Call the modified function
        return enhanced_extract_form_structure(url, wait_time) 