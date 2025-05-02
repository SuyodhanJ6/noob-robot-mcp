#!/usr/bin/env python
"""
MCP Tool: Robot Smart Locator
Advanced locator strategy that combines multiple approaches for finding elements.
Provides fallback mechanisms when standard locators fail.
"""

import os
import logging
import json
import time
import re
import shutil
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
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException, 
    NoSuchElementException,
    StaleElementReferenceException
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webelement import WebElement

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.smart_locator')

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
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Try different approaches to initialize the WebDriver
    driver = None
    
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
        logger.warning(f"WebDriver initialization failed: {e}")
            
    return driver

# -----------------------------------------------------------------------------
# Smart Locator Strategies
# -----------------------------------------------------------------------------

def get_locator_by_javascript(driver: webdriver.Chrome, description: str) -> Optional[Dict[str, Any]]:
    """
    Use JavaScript to find elements based on text content, placeholders, and other properties.
    
    Args:
        driver: WebDriver instance
        description: Text description of the element
        
    Returns:
        Dictionary with locator information if found, None otherwise
    """
    # Clean up the description
    description_lower = description.lower().strip()
    search_terms = re.split(r'\s+', description_lower)
    search_terms = [term for term in search_terms if len(term) > 2]
    
    # JavaScript to find elements by text content
    js_script = """
    function findElementsByText(searchTerms) {
        const allElements = document.querySelectorAll('*');
        const results = [];
        
        for (const element of allElements) {
            // Skip hidden elements
            if (element.offsetParent === null && !['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(element.tagName)) {
                continue;
            }
            
            // Get element text
            const text = element.textContent.toLowerCase();
            const placeholder = element.getAttribute('placeholder')?.toLowerCase() || '';
            const value = element.getAttribute('value')?.toLowerCase() || '';
            const ariaLabel = element.getAttribute('aria-label')?.toLowerCase() || '';
            const title = element.getAttribute('title')?.toLowerCase() || '';
            
            // Check if any search term is in the element's text or attributes
            const matchFound = searchTerms.some(term => 
                text.includes(term) || 
                placeholder.includes(term) || 
                value.includes(term) ||
                ariaLabel.includes(term) ||
                title.includes(term)
            );
            
            if (matchFound) {
                // Calculate XPath
                let xpath = '';
                try {
                    const element_iter = element;
                    for (const node of element_iter) {
                        const parent = node.parentNode;
                        if (!parent) continue;
                        
                        let siblings = Array.from(parent.childNodes).filter(n => n.nodeType === 1);
                        let index = siblings.indexOf(node) + 1;
                        
                        if (xpath === '') {
                            xpath = `//${node.tagName.toLowerCase()}[${index}]`;
                        } else {
                            xpath = `//${node.tagName.toLowerCase()}[${index}]${xpath}`;
                        }
                    }
                } catch (e) {
                    xpath = '';
                }
                
                // Get a CSS selector
                let cssSelector = '';
                try {
                    if (element.id) {
                        cssSelector = `#${element.id}`;
                    } else if (element.className && typeof element.className === 'string') {
                        const classes = element.className.split(' ').filter(c => c);
                        if (classes.length > 0) {
                            cssSelector = `.${classes.join('.')}`;
                        }
                    }
                } catch (e) {
                    cssSelector = '';
                }
                
                results.push({
                    element: element,
                    tag: element.tagName.toLowerCase(),
                    text: text,
                    xpath: xpath,
                    cssSelector: cssSelector,
                    attributes: {
                        id: element.id || '',
                        class: element.className || '',
                        name: element.getAttribute('name') || '',
                        type: element.getAttribute('type') || '',
                        placeholder: placeholder || '',
                        value: value || '',
                        'aria-label': ariaLabel || '',
                        title: title || ''
                    }
                });
            }
        }
        
        return results;
    }
    
    return findElementsByText(arguments[0]);
    """
    
    try:
        elements = driver.execute_script(js_script, search_terms)
        if not elements:
            return None
            
        # Get the most relevant element (first one for now, could be improved)
        element_data = elements[0]
        
        # Determine the best locator
        locator = None
        locator_type = None
        
        if element_data["attributes"]["id"]:
            locator_type = "id"
            locator = f"id={element_data['attributes']['id']}"
        elif element_data["cssSelector"]:
            locator_type = "css"
            locator = f"css={element_data['cssSelector']}"
        elif element_data["xpath"]:
            locator_type = "xpath"
            locator = f"xpath={element_data['xpath']}"
        elif element_data["attributes"]["name"]:
            locator_type = "name"
            locator = f"name={element_data['attributes']['name']}"
        
        if not locator:
            return None
            
        return {
            "locator": locator,
            "locator_type": locator_type,
            "tag_name": element_data["tag"],
            "text": element_data["text"],
            "attributes": element_data["attributes"]
        }
        
    except Exception as e:
        logger.warning(f"JavaScript locator search failed: {e}")
        return None

def get_locator_by_accessibility(driver: webdriver.Chrome, description: str) -> Optional[Dict[str, Any]]:
    """
    Find elements based on accessibility attributes like aria-label, role, etc.
    
    Args:
        driver: WebDriver instance
        description: Text description of the element
        
    Returns:
        Dictionary with locator information if found, None otherwise
    """
    # Clean up the description
    description_lower = description.lower().strip()
    search_terms = re.split(r'\s+', description_lower)
    search_terms = [term for term in search_terms if len(term) > 2]
    
    for term in search_terms:
        try:
            # Try aria-label
            xpath = f"//*[contains(@aria-label, '{term}')]"
            elements = driver.find_elements(By.XPATH, xpath)
            if elements:
                element = elements[0]
                return {
                    "locator": f"xpath={xpath}",
                    "locator_type": "xpath",
                    "tag_name": element.tag_name,
                    "text": element.text,
                    "attributes": {
                        "aria-label": element.get_attribute("aria-label"),
                        "role": element.get_attribute("role")
                    }
                }
                
            # Try role with text
            xpath = f"//*[@role and contains(text(), '{term}')]"
            elements = driver.find_elements(By.XPATH, xpath)
            if elements:
                element = elements[0]
                role = element.get_attribute("role")
                xpath = f"//*[@role='{role}' and contains(text(), '{term}')]"
                return {
                    "locator": f"xpath={xpath}",
                    "locator_type": "xpath",
                    "tag_name": element.tag_name,
                    "text": element.text,
                    "attributes": {
                        "aria-label": element.get_attribute("aria-label"),
                        "role": element.get_attribute("role")
                    }
                }
                
        except Exception as e:
            logger.warning(f"Accessibility locator search failed: {e}")
            continue
            
    return None

def get_locator_by_relative_position(driver: webdriver.Chrome, description: str) -> Optional[Dict[str, Any]]:
    """
    Find elements by their relative position to other elements like labels.
    
    Args:
        driver: WebDriver instance
        description: Text description of the element
        
    Returns:
        Dictionary with locator information if found, None otherwise
    """
    # Clean up the description
    description_lower = description.lower().strip()
    search_terms = re.split(r'\s+', description_lower)
    search_terms = [term for term in search_terms if len(term) > 2]
    
    # Identify form field elements
    if any(keyword in description_lower for keyword in ["field", "input", "textbox", "text box", "textarea"]):
        # Try to find by nearby label
        for term in search_terms:
            try:
                # Find label with matching text
                xpath = f"//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{term}')]"
                labels = driver.find_elements(By.XPATH, xpath)
                
                if labels:
                    label = labels[0]
                    
                    # Check if label has 'for' attribute
                    for_id = label.get_attribute("for")
                    if for_id:
                        xpath = f"//*[@id='{for_id}']"
                        elements = driver.find_elements(By.XPATH, xpath)
                        if elements:
                            element = elements[0]
                            return {
                                "locator": f"id={for_id}",
                                "locator_type": "id",
                                "tag_name": element.tag_name,
                                "text": element.text,
                                "attributes": {
                                    "id": for_id,
                                    "name": element.get_attribute("name"),
                                    "type": element.get_attribute("type")
                                }
                            }
                    
                    # If no 'for' attribute, try finding the next input element
                    xpath = f"//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{term}')]/following::input[1]"
                    elements = driver.find_elements(By.XPATH, xpath)
                    if elements:
                        element = elements[0]
                        element_id = element.get_attribute("id")
                        if element_id:
                            return {
                                "locator": f"id={element_id}",
                                "locator_type": "id",
                                "tag_name": element.tag_name,
                                "text": element.text,
                                "attributes": {
                                    "id": element_id,
                                    "name": element.get_attribute("name"),
                                    "type": element.get_attribute("type")
                                }
                            }
                        
                        element_name = element.get_attribute("name")
                        if element_name:
                            return {
                                "locator": f"name={element_name}",
                                "locator_type": "name",
                                "tag_name": element.tag_name,
                                "text": element.text,
                                "attributes": {
                                    "id": element_id,
                                    "name": element_name,
                                    "type": element.get_attribute("type")
                                }
                            }
                        
                        return {
                            "locator": xpath,
                            "locator_type": "xpath",
                            "tag_name": element.tag_name,
                            "text": element.text,
                            "attributes": {
                                "id": element_id,
                                "name": element_name,
                                "type": element.get_attribute("type")
                            }
                        }
                
            except Exception as e:
                logger.warning(f"Relative position locator search failed: {e}")
                continue
    
    # For buttons, try finding by icon or image
    if any(keyword in description_lower for keyword in ["button", "link", "btn"]):
        # Try to find a button with an icon that has a title or aria-label matching the description
        for term in search_terms:
            try:
                # Button with icon or image
                xpath = f"//button[.//i or .//img or .//svg][contains(@title, '{term}') or contains(@aria-label, '{term}')]"
                elements = driver.find_elements(By.XPATH, xpath)
                if elements:
                    element = elements[0]
                    element_id = element.get_attribute("id")
                    if element_id:
                        return {
                            "locator": f"id={element_id}",
                            "locator_type": "id",
                            "tag_name": element.tag_name,
                            "text": element.text,
                            "attributes": {
                                "id": element_id
                            }
                        }
                    
                    return {
                        "locator": f"xpath={xpath}",
                        "locator_type": "xpath",
                        "tag_name": element.tag_name,
                        "text": element.text,
                        "attributes": {}
                    }
                    
            except Exception as e:
                logger.warning(f"Button with icon locator search failed: {e}")
                continue
                
    return None

# -----------------------------------------------------------------------------
# Main Functions
# -----------------------------------------------------------------------------

def find_smart_locator(url: str, element_description: str, wait_time: int = 10) -> Dict[str, Any]:
    """
    Find a smart locator for an element using multiple strategies.
    
    Args:
        url: URL of the web page
        element_description: Text description of the element
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with smart locator results
    """
    result = {
        "url": url,
        "element_description": element_description,
        "locators": [],
        "recommended_locator": None,
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
        
        # Try using standard approaches from the xpath_locator tool first
        # This is a placeholder - in a real implementation you would import and use those functions
        
        # Try smart locator strategies
        locators = []
        
        # Strategy 1: JavaScript-based search
        js_locator = get_locator_by_javascript(driver, element_description)
        if js_locator:
            js_locator["strategy"] = "javascript"
            locators.append(js_locator)
        
        # Strategy 2: Accessibility-based search
        accessibility_locator = get_locator_by_accessibility(driver, element_description)
        if accessibility_locator:
            accessibility_locator["strategy"] = "accessibility"
            locators.append(accessibility_locator)
        
        # Strategy 3: Relative position search
        relative_locator = get_locator_by_relative_position(driver, element_description)
        if relative_locator:
            relative_locator["strategy"] = "relative_position"
            locators.append(relative_locator)
            
        # Add locators to result
        result["locators"] = locators
        
        # Determine recommended locator
        if locators:
            # Prioritize strategies
            strategy_priority = ["javascript", "accessibility", "relative_position"]
            
            for strategy in strategy_priority:
                for locator in locators:
                    if locator["strategy"] == strategy:
                        result["recommended_locator"] = locator["locator"]
                        break
                
                if result["recommended_locator"]:
                    break
            
            # If no priority match, use the first one
            if not result["recommended_locator"] and locators:
                result["recommended_locator"] = locators[0]["locator"]
        
        return result
    except Exception as e:
        logger.error(f"Error finding smart locator: {e}")
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()
            
def evaluate_locator_robustness(url: str, locator: str, wait_time: int = 5) -> Dict[str, Any]:
    """
    Evaluate a locator for robustness and reliability.
    
    Args:
        url: URL of the web page
        locator: Locator to evaluate
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with evaluation results
    """
    result = {
        "url": url,
        "locator": locator,
        "is_robust": False,
        "reliability_score": 0,
        "suggestions": [],
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
        
        # Determine locator type
        locator_type = None
        locator_value = locator
        
        if locator.startswith("id="):
            locator_type = By.ID
            locator_value = locator[3:]
        elif locator.startswith("name="):
            locator_type = By.NAME
            locator_value = locator[5:]
        elif locator.startswith("css="):
            locator_type = By.CSS_SELECTOR
            locator_value = locator[4:]
        elif locator.startswith("xpath="):
            locator_type = By.XPATH
            locator_value = locator[6:]
        else:
            # Default to XPath
            locator_type = By.XPATH
            locator_value = locator
        
        # Check if the locator finds an element
        try:
            element = driver.find_element(locator_type, locator_value)
            
            # Evaluate reliability
            reliability_score = 0
            suggestions = []
            
            # Check uniqueness
            elements = driver.find_elements(locator_type, locator_value)
            if len(elements) > 1:
                reliability_score -= 20
                suggestions.append("Locator matches multiple elements - make it more specific")
            else:
                reliability_score += 30
            
            # Check if the element is visible
            if element.is_displayed():
                reliability_score += 20
            else:
                reliability_score -= 10
                suggestions.append("Element is not visible - may cause issues with some interactions")
            
            # Check complexity of XPath or CSS
            if locator_type == By.XPATH:
                if locator_value.count("/") > 5:
                    reliability_score -= 10
                    suggestions.append("XPath is complex and may be brittle to DOM changes")
                if "//" in locator_value:
                    reliability_score -= 5
                    suggestions.append("XPath uses '//' which may match unexpected elements")
            
            # Check if uses robust attributes
            if "id=" in locator:
                reliability_score += 30
            elif "name=" in locator:
                reliability_score += 20
            
            # Check for dynamic IDs
            if locator_type == By.ID and re.search(r'_[0-9a-f]{8}', locator_value):
                reliability_score -= 40
                suggestions.append("ID appears to be dynamic - may change between sessions")
            
            # Set final score and robustness
            result["reliability_score"] = max(0, min(100, reliability_score))
            result["is_robust"] = result["reliability_score"] >= 70
            result["suggestions"] = suggestions
            
        except NoSuchElementException:
            result["error"] = "Element not found with the given locator"
        except Exception as e:
            result["error"] = f"Error evaluating locator: {str(e)}"
        
        return result
    except Exception as e:
        logger.error(f"Error evaluating locator robustness: {e}")
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
    async def robot_find_smart_locator(
        url: str,
        element_description: str,
        wait_time: int = 10
    ) -> Dict[str, Any]:
        """
        Find a smart locator for an element using multiple advanced strategies.
        
        This tool uses a combination of JavaScript, accessibility attributes, and
        relative positioning to find the most robust locator for an element, even
        when standard approaches fail.
        
        Args:
            url: URL of the web page to analyze
            element_description: Text description of the element (e.g., "Login button", "Username field")
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with smart locator results including multiple strategies
        """
        return find_smart_locator(url, element_description, wait_time)
    
    @mcp.tool()
    async def robot_evaluate_locator_robustness(
        url: str,
        locator: str,
        wait_time: int = 5
    ) -> Dict[str, Any]:
        """
        Evaluate a locator for robustness and reliability.
        
        This tool analyzes a locator and provides a reliability score and suggestions
        for improvement. It helps ensure that locators will be resilient to page changes.
        
        Args:
            url: URL of the web page
            locator: Locator to evaluate (with type prefix like "xpath=", "id=", etc.)
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with evaluation results including reliability score and suggestions
        """
        return evaluate_locator_robustness(url, locator, wait_time) 