#!/usr/bin/env python
"""
MCP Tool: Enhanced Robot Smart Locator
Advanced strategy that dynamically finds the best locators for web elements.
Handles dynamic content and changing element attributes automatically.
Includes authentication handling and form automation capabilities.
Replaces static locator tools like xpath_locator, form_locator, and auto_locator.
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
    StaleElementReferenceException,
    ElementNotInteractableException
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webelement import WebElement

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

# Import shared browser manager
from src.mcp_tools.robot_browser_manager import BrowserManager

logger = logging.getLogger('robot_tool.smart_locator')

"""
IMPORTANT: This tool replaces and consolidates functionality from:
- robot_auto_locator
- robot_form_locator
- robot_xpath_locator
- robot_auth_handler
- robot_form_automator

After implementing this enhanced tool, those tools can be removed from the server.py imports.
"""

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def initialize_webdriver() -> Optional[webdriver.Chrome]:
    """
    Initialize the Chrome WebDriver with multiple fallback methods.
    
    Returns:
        WebDriver object if successful, None otherwise
    """
    # Use the browser manager to get a shared browser instance
    try:
        return BrowserManager.get_driver()
    except Exception as e:
        logger.warning(f"Failed to get browser from BrowserManager: {e}")
        
    # Set up Chrome options for headless browsing as fallback
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Use newer headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-web-security")
    
    # Add user agent to make sites treat us like a regular browser
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    
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
        
        # Try to find chromedriver in PATH
        try:
            logger.info("Trying to find chromedriver in PATH")
            chromedriver_path = shutil.which("chromedriver")
            if chromedriver_path:
                logger.info(f"Found chromedriver at {chromedriver_path}")
                service = Service(executable_path=chromedriver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e2:
            logger.warning(f"PATH-based WebDriver initialization failed: {e2}")
            
    return driver

def get_by_method(locator: str) -> Tuple[By, str]:
    """Convert locator prefix to Selenium By method."""
    if locator.startswith("id="):
        return By.ID, locator[3:]
    elif locator.startswith("name="):
        return By.NAME, locator[5:]
    elif locator.startswith("xpath="):
        return By.XPATH, locator[6:]
    elif locator.startswith("css=") or locator.startswith("css selector="):
        return By.CSS_SELECTOR, locator.split("=", 1)[1]
    elif locator.startswith("class="):
        return By.CLASS_NAME, locator[6:]
    elif locator.startswith("link="):
        return By.LINK_TEXT, locator[5:]
    elif locator.startswith("partial link="):
        return By.PARTIAL_LINK_TEXT, locator[13:]
    elif locator.startswith("tag="):
        return By.TAG_NAME, locator[4:]
    else:
        # Default to XPath if no prefix
        return By.XPATH, locator

# Helper function to normalize XPath expressions
def normalize_xpath(xpath: str) -> str:
    """
    Normalize an XPath expression to avoid common syntax errors.
    
    Args:
        xpath: XPath expression to normalize
        
    Returns:
        Normalized XPath expression
    """
    if not xpath:
        return xpath
        
    # Replace triple slashes with double slashes (do this repeatedly until all are gone)
    while '///' in xpath:
        xpath = xpath.replace('///', '//')
        
    # Fix other improper syntax like '//' followed by '/'
    while '///' in xpath:
        xpath = xpath.replace('///', '//')
    
    # Fix '//./' pattern (sometimes created by JavaScript XPath generators)
    xpath = xpath.replace('//.//', '//')
    
    # Fix quoted attributes with extra spaces
    # For example: //div[@class = 'foo'] to //div[@class='foo']
    xpath = re.sub(r'@([a-zA-Z0-9_-]+)\s*=\s*([\'"])', r'@\1=\2', xpath)
    
    # Make sure the expression starts correctly
    if xpath.startswith('//'):
        # Already a valid relative path, no change needed
        pass
    elif xpath.startswith('/'):
        # Already a valid absolute path, no change needed
        pass
    elif not xpath.startswith('//') and not xpath.startswith('/'):
        # Add // for a relative path if not already there
        xpath = '//' + xpath
        
    return xpath

# Add this helper to simplify code
def safe_find_element(driver: webdriver.Chrome, by: By, value: str) -> Optional[WebElement]:
    """
    Safely find an element, handling any XPath normalization.
    
    Args:
        driver: WebDriver instance
        by: By method (By.XPATH, By.ID, etc.)
        value: Selector value
        
    Returns:
        WebElement if found, None otherwise
    """
    try:
        # Normalize XPath expressions before using them
        if by == By.XPATH:
            value = normalize_xpath(value)
            
        return driver.find_element(by, value)
    except NoSuchElementException:
        return None
    except Exception as e:
        logger.warning(f"Error finding element: {e}")
        return None

def safe_find_elements(driver: webdriver.Chrome, by: By, value: str) -> List[WebElement]:
    """
    Safely find elements, handling any XPath normalization.
    
    Args:
        driver: WebDriver instance
        by: By method (By.XPATH, By.ID, etc.)
        value: Selector value
        
    Returns:
        List of WebElements found, empty list if none
    """
    try:
        # Normalize XPath expressions before using them
        if by == By.XPATH:
            value = normalize_xpath(value)
            
        return driver.find_elements(by, value)
    except Exception as e:
        logger.warning(f"Error finding elements: {e}")
        return []

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
        
        // First pass: look specifically for input elements with matching attributes
        // as these are more likely to be what we want for form fields
        const inputElements = [];
        const containerElements = [];
        
        for (const element of allElements) {
            // Skip hidden elements
            if (element.offsetParent === null && !['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(element.tagName)) {
                continue;
            }
            
            const tagName = element.tagName.toLowerCase();
            const isFormElement = ['input', 'select', 'textarea'].includes(tagName);
            
            // Get element text and attributes
            const text = element.textContent.toLowerCase();
            const placeholder = element.getAttribute('placeholder')?.toLowerCase() || '';
            const value = element.getAttribute('value')?.toLowerCase() || '';
            const ariaLabel = element.getAttribute('aria-label')?.toLowerCase() || '';
            const title = element.getAttribute('title')?.toLowerCase() || '';
            const name = element.getAttribute('name')?.toLowerCase() || '';
            const id = element.id?.toLowerCase() || '';
            
            // Check if any search term is in the element's text or attributes
            const matchFound = searchTerms.some(term => 
                text.includes(term) || 
                placeholder.includes(term) || 
                value.includes(term) ||
                ariaLabel.includes(term) ||
                title.includes(term) ||
                name.includes(term) ||
                id.includes(term)
            );
            
            if (matchFound) {
                // Store the element info with a priority based on whether it's a form element
                const elementInfo = {
                    element: element,
                    tag: tagName,
                    text: text,
                    isFormElement: isFormElement,
                    isLabel: tagName === 'label',
                    // Calculate match score
                    matchScore: (placeholder.includes(searchTerms[0]) ? 10 : 0) +
                                (name.includes(searchTerms[0]) ? 8 : 0) +
                                (id.includes(searchTerms[0]) ? 7 : 0) +
                                (ariaLabel.includes(searchTerms[0]) ? 6 : 0) +
                                (isFormElement ? 5 : 0) +
                                (title.includes(searchTerms[0]) ? 4 : 0) +
                                (value.includes(searchTerms[0]) ? 3 : 0) +
                                (text.includes(searchTerms[0]) ? 2 : 0)
                };
                
                if (isFormElement) {
                    inputElements.push(elementInfo);
                } else {
                    containerElements.push(elementInfo);
                }
            }
        }
        
        // Sort both arrays by match score (highest first)
        inputElements.sort((a, b) => b.matchScore - a.matchScore);
        containerElements.sort((a, b) => b.matchScore - a.matchScore);
        
        // Combine the arrays with input elements first
        const sortedElements = [...inputElements, ...containerElements];
        
        // Process the top matches
        const maxResults = 5; // Limit to top 5 results
        for (let i = 0; i < Math.min(sortedElements.length, maxResults); i++) {
            const elementInfo = sortedElements[i];
            const element = elementInfo.element;
            
                // Calculate XPath
                let xpath = '';
                try {
                    let node = element;
                    let path = [];
                    while (node && node.nodeType === 1) {
                        let name = node.nodeName.toLowerCase();
                        let sibIndex = 1;
                        let sibs = node.previousSibling;
                        while (sibs) {
                            if (sibs.nodeName.toLowerCase() === name) {
                                sibIndex++;
                            }
                            sibs = sibs.previousSibling;
                        }
                        
                        if (node.hasAttribute('id')) {
                            path.unshift(`//${name}[@id='${node.id}']`);
                            break;
                        } else {
                            path.unshift(`${name}[${sibIndex}]`);
                        }
                        
                        node = node.parentNode;
                    }
                    
                // Join the path parts with a single slash to avoid triple slashes
                    xpath = '/' + path.join('/');
                
                // Normalize the XPath by replacing any triple slashes
                while (xpath.includes('///')) {
                    xpath = xpath.replace('///', '//');
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
            
            // Get all important attributes
            const placeholder = element.getAttribute('placeholder') || '';
            const value = element.getAttribute('value') || '';
            const ariaLabel = element.getAttribute('aria-label') || '';
            const title = element.getAttribute('title') || '';
            const name = element.getAttribute('name') || '';
            const type = element.getAttribute('type') || '';
                
                results.push({
                    element: element,
                    tag: element.tagName.toLowerCase(),
                text: elementInfo.text,
                    xpath: xpath,
                    cssSelector: cssSelector,
                isFormElement: elementInfo.isFormElement,
                isLabel: elementInfo.isLabel,
                matchScore: elementInfo.matchScore,
                    attributes: {
                        id: element.id || '',
                        class: element.className || '',
                    name: name,
                    type: type,
                    placeholder: placeholder,
                    value: value,
                    'aria-label': ariaLabel,
                    title: title
                }
            });
        }
        
        // If we found a label but no input, try to find an associated input
        const labelResults = results.filter(r => r.isLabel);
        if (labelResults.length > 0 && !results.some(r => r.isFormElement)) {
            for (const labelResult of labelResults) {
                const label = labelResult.element;
                let inputElement = null;
                
                // Check for 'for' attribute
                const forId = label.getAttribute('for');
                if (forId) {
                    inputElement = document.getElementById(forId);
                }
                
                // If no input found by 'for', look for child or sibling input
                if (!inputElement) {
                    // Check for child input
                    inputElement = label.querySelector('input, select, textarea');
                    
                    // Check for following sibling input
                    if (!inputElement) {
                        let sibling = label.nextElementSibling;
                        while (sibling && !inputElement) {
                            if (['INPUT', 'SELECT', 'TEXTAREA'].includes(sibling.tagName)) {
                                inputElement = sibling;
                            }
                            sibling = sibling.nextElementSibling;
                        }
                    }
                }
                
                // If we found an associated input element, add it to results
                if (inputElement) {
                    // Calculate XPath for the input
                    let xpath = '';
                    try {
                        let node = inputElement;
                        let path = [];
                        while (node && node.nodeType === 1) {
                            let name = node.nodeName.toLowerCase();
                            let sibIndex = 1;
                            let sibs = node.previousSibling;
                            while (sibs) {
                                if (sibs.nodeName.toLowerCase() === name) {
                                    sibIndex++;
                                }
                                sibs = sibs.previousSibling;
                            }
                            
                            if (node.hasAttribute('id')) {
                                path.unshift(`//${name}[@id='${node.id}']`);
                                break;
                            } else {
                                path.unshift(`${name}[${sibIndex}]`);
                            }
                            
                            node = node.parentNode;
                        }
                        
                        xpath = '/' + path.join('/');
                        while (xpath.includes('///')) {
                            xpath = xpath.replace('///', '//');
                        }
                    } catch (e) {
                        xpath = '';
                    }
                    
                    // Add to results with high priority
                    results.unshift({
                        element: inputElement,
                        tag: inputElement.tagName.toLowerCase(),
                        text: labelResult.text, // Use the label text
                        xpath: xpath,
                        cssSelector: inputElement.id ? `#${inputElement.id}` : '',
                        isFormElement: true,
                        isLabel: false,
                        matchScore: labelResult.matchScore + 10, // Higher score since this is an input associated with a matching label
                        attributes: {
                            id: inputElement.id || '',
                            class: inputElement.className || '',
                            name: inputElement.getAttribute('name') || '',
                            type: inputElement.getAttribute('type') || '',
                            placeholder: inputElement.getAttribute('placeholder') || '',
                            value: inputElement.getAttribute('value') || '',
                            'aria-label': inputElement.getAttribute('aria-label') || '',
                            title: inputElement.getAttribute('title') || ''
                        }
                    });
                }
            }
        }
        
        return results;
    }
    
    return findElementsByText(arguments[0]);
    """
    
    try:
        elements = driver.execute_script(js_script, search_terms)
        if not elements or len(elements) == 0:
            return None
            
        # Sort elements by how many search terms they match
        element_scores = []
        for element in elements:
            score = 0
            text = element.get("text", "").lower()
            
            # Score based on how many terms match
            for term in search_terms:
                if term in text:
                    score += 10
                    
                # Check attributes
                attrs = element.get("attributes", {})
                for attr_name, attr_value in attrs.items():
                    if attr_value and term in str(attr_value).lower():
                        score += 5
            
            element_scores.append((element, score))
            
        # Sort by score (highest first)
        element_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Get best element
        best_element = element_scores[0][0]
        
        # Create a locator
        locator = None
        attributes = best_element.get("attributes", {})
        
        # Try ID first
        if attributes.get("id"):
            locator = f"id={attributes['id']}"
        # Then name
        elif attributes.get("name"):
            locator = f"name={attributes['name']}"
        # Then XPath
        elif best_element.get("xpath"):
            locator = f"xpath={best_element['xpath']}"
        # Then CSS
        elif best_element.get("cssSelector"):
            locator = f"css={best_element['cssSelector']}"
        
        if not locator:
            return None
            
        return {
            "locator": locator,
            "locator_type": locator.split("=", 1)[0],
            "tag_name": best_element.get("tag"),
            "text": best_element.get("text"),
            "attributes": attributes
        }
    except Exception as e:
        logger.warning(f"JavaScript-based locator search failed: {e}")
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
    description_lower = description.lower().strip()
    terms = re.split(r'\s+', description_lower)
    
    # Try various accessibility-based locators
    for term in terms:
        if len(term) < 3:
            continue
            
        try:
            # Aria-label
            xpath = f"//*[contains(@aria-label, '{term}')]"
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
                            "aria-label": element.get_attribute("aria-label")
                        }
                    }
                
                return {
                    "locator": f"xpath={xpath}",
                    "locator_type": "xpath",
                    "tag_name": element.tag_name,
                    "text": element.text,
                    "attributes": {
                        "aria-label": element.get_attribute("aria-label")
                    }
                }
        except Exception as e:
            logger.warning(f"Aria-label search failed: {e}")
                
        try:
            # Role with text
            xpath = f"//*[@role and contains(text(), '{term}')]"
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
                            "role": element.get_attribute("role")
                        }
                    }
                
                return {
                    "locator": f"xpath={xpath}",
                    "locator_type": "xpath",
                    "tag_name": element.tag_name,
                    "text": element.text,
                    "attributes": {
                        "role": element.get_attribute("role")
                    }
                }
        except Exception as e:
            logger.warning(f"Role+text search failed: {e}")
            
    return None

def get_locator_by_relative_position(driver: webdriver.Chrome, description: str) -> Optional[Dict[str, Any]]:
    """
    Find elements based on their position relative to other elements with known text.
    
    Args:
        driver: WebDriver instance
        description: Text description of the element
        
    Returns:
        Dictionary with locator information if found, None otherwise
    """
    description_lower = description.lower().strip()
    
    # Check for positional cues in the description
    relative_patterns = [
        (r'next to (.*)', 'following-sibling::*[1]|preceding-sibling::*[1]'),
        (r'after (.*)', 'following-sibling::*'),
        (r'before (.*)', 'preceding-sibling::*'),
        (r'above (.*)', 'preceding::*'),
        (r'below (.*)', 'following::*'),
        (r'inside (.*)', 'ancestor::*'),
        (r'containing (.*)', 'descendant::*')
    ]
    
    for pattern, xpath_rel in relative_patterns:
        match = re.search(pattern, description_lower)
        if match:
            reference_text = match.group(1).strip()
            
            try:
                # Find reference element by text
                reference_xpath = f"//*[contains(text(), '{reference_text}')]"
                reference_elements = driver.find_elements(By.XPATH, reference_xpath)
                
                if reference_elements:
                    reference_element = reference_elements[0]
                    
                    # Use JavaScript to find element by relative position
                    js_script = f"""
                    function findRelativeElement(referenceElement, relation) {{
                        let element = null;
                        
                        switch(relation) {{
                            case 'following-sibling::*[1]|preceding-sibling::*[1]':
                                // Next to
                                element = referenceElement.nextElementSibling || referenceElement.previousElementSibling;
                                break;
                            case 'following-sibling::*':
                                // After
                                element = referenceElement.nextElementSibling;
                                break;
                            case 'preceding-sibling::*':
                                // Before
                                element = referenceElement.previousElementSibling;
                                break;
                            case 'preceding::*':
                                // Above (simplified)
                                element = referenceElement.parentElement?.previousElementSibling?.lastElementChild;
                                break;
                            case 'following::*':
                                // Below (simplified)
                                element = referenceElement.parentElement?.nextElementSibling?.firstElementChild;
                                break;
                            case 'ancestor::*':
                                // Inside/containing
                                element = referenceElement.parentElement;
                                break;
                            case 'descendant::*':
                                // Child
                                element = referenceElement.firstElementChild;
                                break;
                        }}
                        
                        return element;
                    }}
                    
                    return findRelativeElement(arguments[0], arguments[1]);
                    """
                    
                    element = driver.execute_script(js_script, reference_element, xpath_rel)
                    
                    if element:
                        element_id = element.get_attribute("id")
                        element_tag = element.tag_name
                        
                        if element_id:
                            return {
                                "locator": f"id={element_id}",
                                "locator_type": "id",
                                "tag_name": element_tag,
                                "text": element.text,
                                "attributes": {
                                    "id": element_id
                                }
                            }
                        
                        # Generate a more robust XPath for the element
                        # Carefully join the paths to avoid triple slashes
                        rel_part = xpath_rel.split('|')[0]
                        
                        # Make sure we don't end up with /// by checking if reference_xpath ends with / and rel_part starts with /
                        if rel_part.startswith('/') and reference_xpath.endswith('/'):
                            rel_part = rel_part[1:]  # Remove the leading / from rel_part
                        
                        # Now join the paths, ensuring no /// is created
                        joined_xpath = f"{reference_xpath}/{rel_part}"
                        # As an extra safeguard, replace any triple slashes
                        joined_xpath = joined_xpath.replace('///', '//')
                        
                        return {
                            "locator": f"xpath={joined_xpath}",
                            "locator_type": "xpath",
                            "tag_name": element_tag,
                            "text": element.text,
                            "attributes": {}
                        }
            except Exception as e:
                logger.warning(f"Relative position search failed for pattern '{pattern}': {e}")
    
    return None

def get_dynamic_resilient_locator(driver: webdriver.Chrome, element: WebElement) -> Dict[str, Any]:
    """
    Generate a resilient locator that can adapt to dynamic changes in the website.
    This function uses multiple strategies to create locators that will work even if IDs change.
    
    Args:
        driver: WebDriver instance
        element: The target WebElement
        
    Returns:
        Dictionary with locator information
    """
    result = {
        "locator": None,
        "locator_type": None,
        "alternatives": [],
        "dynamic_strategy": "smart_attributes",
        "tag_name": element.tag_name,
        "text": element.text.strip() if element.text else "",
        "attributes": {}
    }
    
    # Strategy 1: Try stable attributes
    stable_attrs = ["id", "name", "data-testid", "data-cy", "data-automation", "aria-label", "title", "role"]
    for attr in stable_attrs:
        value = element.get_attribute(attr)
        if value and len(value) > 0:
            result["attributes"][attr] = value
            
            # Check if this attribute is unique
            unique = False
            try:
                selector = f"[{attr}='{value}']"
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                unique = len(elements) == 1
            except:
                unique = False
                
            if unique:
                # Add the locator to alternatives
                if attr == "id":
                    locator = f"id={value}"
                    result["alternatives"].append({"locator": locator, "type": "id", "reliability": 95})
                elif attr == "name":
                    locator = f"name={value}"
                    result["alternatives"].append({"locator": locator, "type": "name", "reliability": 85})
                else:
                    tag_name = element.tag_name
                    locator = f"css={tag_name}[{attr}='{value}']"
                    result["alternatives"].append({"locator": locator, "type": "css", "reliability": 80})
    
    # Strategy 2: Try compound unique attributes
    if len(result["alternatives"]) == 0:
        tag_name = element.tag_name
        attrs = {}
        for attr in ["class", "type", "placeholder", "value"]:
            value = element.get_attribute(attr)
            if value and len(value) > 0:
                attrs[attr] = value
                result["attributes"][attr] = value
        
        if len(attrs) > 0:
            # Build a compound CSS selector
            css_parts = []
            for attr, value in attrs.items():
                if attr == "class":
                    # Handle class specially
                    classes = value.split()
                    if len(classes) > 0:
                        # Use the first class only for now
                        css_parts.append(f".{classes[0]}")
                else:
                    css_parts.append(f"[{attr}='{value}']")
            
            if css_parts:
                locator = f"css={tag_name}{' '.join(css_parts)}"
                # Check if this is unique
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, locator.replace("css=", ""))
                    if len(elements) == 1:
                        result["alternatives"].append({"locator": locator, "type": "css", "reliability": 70})
                except:
                    pass
    
    # Strategy 3: Text-based locator
    if element.text and len(element.text.strip()) > 0 and len(element.text.strip()) < 50:
        text = element.text.strip()
        tag_name = element.tag_name
        locator = f"xpath=//{tag_name}[text()='{text}']"
        
        try:
            elements = driver.find_elements(By.XPATH, locator.replace("xpath=", ""))
            if len(elements) == 1:
                result["alternatives"].append({"locator": locator, "type": "xpath", "reliability": 60})
            else:
                # Try with contains for partial text match
                locator = f"xpath=//{tag_name}[contains(text(), '{text}')]"
                elements = driver.find_elements(By.XPATH, locator.replace("xpath=", ""))
                if len(elements) == 1:
                    result["alternatives"].append({"locator": locator, "type": "xpath", "reliability": 50})
        except:
            pass
    
    # Strategy 4: Position and structure-based locator (last resort)
    try:
        # Get nearby text elements as landmarks
        js_script = """
        function getNearbyTextElements(element, maxDistance = 3) {
            const result = [];
            
            // Helper to check if an element has visible text
            function hasVisibleText(elem) {
                return elem.offsetParent !== null && 
                       elem.textContent && 
                       elem.textContent.trim().length > 0 &&
                       elem.textContent.trim().length < 50;
            }
            
            // Check siblings
            let sibling = element.previousElementSibling;
            let distance = 1;
            while(sibling && distance <= maxDistance) {
                if (hasVisibleText(sibling)) {
                    result.push({
                        text: sibling.textContent.trim(),
                        relation: 'previous-sibling',
                        distance: distance
                    });
                }
                sibling = sibling.previousElementSibling;
                distance++;
            }
            
            sibling = element.nextElementSibling;
            distance = 1;
            while(sibling && distance <= maxDistance) {
                if (hasVisibleText(sibling)) {
                    result.push({
                        text: sibling.textContent.trim(),
                        relation: 'next-sibling',
                        distance: distance
                    });
                }
                sibling = sibling.nextElementSibling;
                distance++;
            }
            
            // Check parent's text
            let parent = element.parentElement;
            if (parent && hasVisibleText(parent)) {
                result.push({
                    text: parent.textContent.trim(),
                    relation: 'parent',
                    distance: 1
                });
            }
            
            return result;
        }
        
        return getNearbyTextElements(arguments[0]);
        """
        
        nearby_text = driver.execute_script(js_script, element)
        
        if nearby_text and len(nearby_text) > 0:
            # Sort by distance (closest first)
            nearby_text.sort(key=lambda x: x.get('distance', 999))
            
            # Use the closest text element as landmark
            landmark = nearby_text[0]
            text = landmark['text']
            relation = landmark['relation']
            
            # Build a relative XPath
            if relation == 'previous-sibling':
                locator = f"xpath=//*[contains(text(), '{text}')]/following-sibling::*[{landmark['distance']}]"
            elif relation == 'next-sibling':
                locator = f"xpath=//*[contains(text(), '{text}')]/preceding-sibling::*[{landmark['distance']}]"
            elif relation == 'parent':
                tag_name = element.tag_name
                locator = f"xpath=//*[contains(text(), '{text}')]/{tag_name}"
            
            # Normalize the XPath to avoid triple slashes
            if locator.startswith("xpath="):
                locator = "xpath=" + normalize_xpath(locator[6:])
            
            # Check if this locator is unique
            try:
                elements = driver.find_elements(By.XPATH, locator.replace("xpath=", ""))
                if len(elements) == 1:
                    result["alternatives"].append({"locator": locator, "type": "xpath", "reliability": 40})
            except Exception as e:
                logger.warning(f"Error checking locator uniqueness: {e}")
    except Exception as e:
        logger.warning(f"Dynamic landmark-based locator generation failed: {e}")
    
    # Finally, select the best locator from alternatives
    if result["alternatives"]:
        # Sort by reliability
        result["alternatives"].sort(key=lambda x: x.get('reliability', 0), reverse=True)
        best = result["alternatives"][0]
        result["locator"] = best["locator"]
        result["locator_type"] = best["type"]
    
    return result

# -----------------------------------------------------------------------------
# Authentication Handling Functions
# -----------------------------------------------------------------------------

def handle_authentication(
    driver: webdriver.Chrome, 
    url: str,
    username_locator: str,
    password_locator: str, 
    submit_locator: str,
    username: str,
    password: str,
    wait_time: int = 10,
    success_indicator: Optional[str] = None,
    failure_indicator: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle authentication on a web page.
    
    Args:
        driver: WebDriver instance
        url: URL of the login page
        username_locator: Locator for username field
        password_locator: Locator for password field
        submit_locator: Locator for submit button
        username: Username to enter
        password: Password to enter
        wait_time: Time to wait for elements in seconds
        success_indicator: Locator to verify successful login
        failure_indicator: Locator to identify failed login
        
    Returns:
        Dictionary with login result details
    """
    result = {
        "success": False,
        "error": None,
        "url_before": None,
        "url_after": None,
        "screenshot": None
    }
    
    try:
        # Navigate to login page
        logger.info(f"Navigating to login page: {url}")
        driver.get(url)
        
        # Wait for page to load
        time.sleep(2)
        
        # Store initial URL
        result["url_before"] = driver.current_url
        
        # Find elements using the provided locators
        username_by, username_value = get_by_method(username_locator)
        password_by, password_value = get_by_method(password_locator)
        submit_by, submit_value = get_by_method(submit_locator)
        
        # Wait for username field and enter username
        try:
            username_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable((username_by, username_value))
            )
            username_element.clear()
            username_element.send_keys(username)
        except Exception as e:
            result["error"] = f"Failed to enter username: {str(e)}"
            logger.error(result["error"])
            return result
        
        # Enter password
        try:
            password_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable((password_by, password_value))
            )
            password_element.clear()
            password_element.send_keys(password)
        except Exception as e:
            result["error"] = f"Failed to enter password: {str(e)}"
            logger.error(result["error"])
            return result
        
        # Click submit button
        try:
            submit_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable((submit_by, submit_value))
            )
            submit_element.click()
        except Exception as e:
            result["error"] = f"Failed to click submit button: {str(e)}"
            logger.error(result["error"])
            return result
        
        # Wait for login process
        time.sleep(5)
        
        # Store final URL
        result["url_after"] = driver.current_url
        
        # Take screenshot for verification
        try:
            result["screenshot"] = driver.get_screenshot_as_base64()
        except Exception as e:
            logger.warning(f"Failed to take screenshot: {str(e)}")
        
        # Check for success indicator if provided
        if success_indicator:
            success_by, success_value = get_by_method(success_indicator)
            try:
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((success_by, success_value))
                )
                result["success"] = True
            except TimeoutException:
                result["success"] = False
                result["error"] = "Success indicator not found after login"
        # Check for failure indicator if provided
        elif failure_indicator:
            failure_by, failure_value = get_by_method(failure_indicator)
            try:
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((failure_by, failure_value))
                )
                result["success"] = False
                result["error"] = "Failure indicator found after login"
            except TimeoutException:
                # If failure indicator is not found, assume success
                result["success"] = True
        else:
            # If neither indicator is provided, check if URL changed
            if result["url_before"] != result["url_after"]:
                result["success"] = True
            else:
                result["success"] = False
                result["error"] = "URL did not change after login"
        
        return result
    except Exception as e:
        result["error"] = f"Authentication error: {str(e)}"
        logger.error(result["error"])
        return result

# -----------------------------------------------------------------------------
# Form Handling Functions
# -----------------------------------------------------------------------------

def detect_form_fields(
    driver: webdriver.Chrome,
    form_locator: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detect form fields on the current page.
    
    Args:
        driver: WebDriver instance
        form_locator: Optional locator for the form element
        
    Returns:
        Dictionary with detected form fields
    """
    result = {
        "form_fields": {},
        "submit_button": None,
        "error": None
    }
    
    try:
        # If form locator is provided, find the form element
        form_element = None
        if form_locator:
            form_by, form_value = get_by_method(form_locator)
            try:
                form_element = driver.find_element(form_by, form_value)
            except NoSuchElementException:
                result["error"] = f"Form element not found with locator: {form_locator}"
                return result
                
        # Get all input elements (either within the form or on the entire page)
        if form_element:
            input_elements = form_element.find_elements(By.XPATH, ".//input | .//textarea | .//select")
        else:
            # Try to find all forms first
            forms = driver.find_elements(By.TAG_NAME, "form")
            if forms:
                # Use the first visible form
                for form in forms:
                    if form.is_displayed():
                        form_element = form
                        break
                
                if form_element:
                    input_elements = form_element.find_elements(By.XPATH, ".//input | .//textarea | .//select")
                else:
                    # If no visible form found, search the entire page
                    input_elements = driver.find_elements(By.XPATH, "//input | //textarea | //select")
            else:
                # If no forms found, search the entire page
                input_elements = driver.find_elements(By.XPATH, "//input | //textarea | //select")
        
        # Process each input element
        for element in input_elements:
            # Skip hidden elements
            if not element.is_displayed():
                continue
                
            # Get element attributes
            element_type = element.get_attribute("type")
            element_name = element.get_attribute("name") or element.get_attribute("id")
            element_id = element.get_attribute("id")
            element_placeholder = element.get_attribute("placeholder")
            element_label = None
            
            # Skip submit and button inputs (handle them separately)
            if element_type in ["submit", "button", "reset", "image", "hidden"]:
                continue
                
            # Try to find label for this element
            if element_id:
                try:
                    label_element = driver.find_element(By.XPATH, f"//label[@for='{element_id}']")
                    element_label = label_element.text.strip()
                except NoSuchElementException:
                    pass
            
            # If no label found, try to find label based on proximity
            if not element_label:
                try:
                    # Look for label within the same parent
                    parent = element.find_element(By.XPATH, "./..")
                    labels = parent.find_elements(By.TAG_NAME, "label")
                    if labels:
                        element_label = labels[0].text.strip()
                except Exception:
                    pass
            
            # Use placeholder as label if no other label found
            if not element_label and element_placeholder:
                element_label = element_placeholder
                
            # If still no label, use name or id
            if not element_label:
                element_label = element_name
            
            # Create a label if still none found
            if not element_label:
                element_label = f"Field_{len(result['form_fields']) + 1}"
            
            # Determine best locator for this element
            locator = None
            if element_id:
                locator = f"id={element_id}"
            elif element_name:
                locator = f"name={element_name}"
            else:
                # Build XPath if no ID or name
                xpath = generate_xpath_for_element(driver, element)
                if xpath:
                    locator = f"xpath={xpath}"
            
            # Skip element if no locator could be determined
            if not locator:
                continue
                
            # Add field to result
            field_key = element_label.lower().replace(" ", "_")
            result["form_fields"][field_key] = {
                "locator": locator,
                "type": element_type or "text",
                "label": element_label,
                "required": element.get_attribute("required") == "true"
            }
        
        # Find submit button
        submit_buttons = []
        
        # Look for buttons with type="submit"
        if form_element:
            submit_elements = form_element.find_elements(By.XPATH, ".//button[@type='submit'] | .//input[@type='submit']")
        else:
            submit_elements = driver.find_elements(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
            
        for element in submit_elements:
            if element.is_displayed():
                submit_buttons.append(element)
        
        # If no submit buttons with type="submit", look for buttons inside form
        if not submit_buttons and form_element:
            button_elements = form_element.find_elements(By.TAG_NAME, "button")
            for element in button_elements:
                if element.is_displayed():
                    submit_buttons.append(element)
        
        # If still no buttons, look for elements that look like submit buttons
        if not submit_buttons:
            # Common submit button texts
            submit_texts = ["submit", "send", "login", "sign in", "register", "create", "continue", "next"]
            
            for text in submit_texts:
                xpath = f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')] | " \
                       f"//input[contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')] | " \
                       f"//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]"
                elements = driver.find_elements(By.XPATH, xpath)
                for element in elements:
                    if element.is_displayed():
                        submit_buttons.append(element)
                
                if submit_buttons:
                    break
        
        # Add submit button to result
        if submit_buttons:
            submit_button = submit_buttons[0]
            submit_id = submit_button.get_attribute("id")
            submit_name = submit_button.get_attribute("name")
            
            if submit_id:
                result["submit_button"] = f"id={submit_id}"
            elif submit_name:
                result["submit_button"] = f"name={submit_name}"
            else:
                # Build XPath
                submit_xpath = generate_xpath_for_element(driver, submit_button)
                if submit_xpath:
                    result["submit_button"] = f"xpath={submit_xpath}"
        
        return result
    except Exception as e:
        result["error"] = f"Error detecting form fields: {str(e)}"
        logger.error(result["error"])
        return result

def generate_xpath_for_element(driver: webdriver.Chrome, element: WebElement) -> Optional[str]:
    """Generate a unique XPath for an element."""
    try:
        # Try to get a unique XPath using attributes
        attributes = ["id", "name", "class", "type", "role", "aria-label", "data-testid"]
        
        for attr in attributes:
            value = element.get_attribute(attr)
            if value:
                # For id, a simple xpath is enough
                if attr == "id":
                    return f"//*[@id='{value}']"
                    
                # For other attributes, we need to be more specific with tag name
                tag_name = element.tag_name
                xpath = f"//{tag_name}[@{attr}='{value}']"
                
                # Check if this XPath is unique
                elements = driver.find_elements(By.XPATH, xpath)
                if len(elements) == 1:
                    return xpath
        
        # If we couldn't generate a unique XPath with attributes, use text content
        text = element.text.strip()
        if text:
            xpath = f"//{element.tag_name}[text()='{text}']"
            elements = driver.find_elements(By.XPATH, xpath)
            if len(elements) == 1:
                return xpath
            
            # Try with contains for partial text match
            xpath = f"//{element.tag_name}[contains(text(), '{text}')]"
            elements = driver.find_elements(By.XPATH, xpath)
            if len(elements) == 1:
                return xpath
        
        # If still not unique, use the full DOM path
        js_script = """
        function getPathTo(element) {
            if (element.id !== '')
                return "//*[@id='" + element.id + "']";
                
            if (element === document.body)
                return "/html/body";

            var ix = 0;
            var siblings = element.parentNode.childNodes;
            
            for (var i = 0; i < siblings.length; i++) {
                var sibling = siblings[i];
                
                if (sibling === element)
                    return getPathTo(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                    
                if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                    ix++;
            }
        }
        
        return getPathTo(arguments[0]);
        """
        
        xpath = driver.execute_script(js_script, element)
        
        # Fix any potential triple slash (///) issues by normalizing the path
        if xpath:
            xpath = normalize_xpath(xpath)
            
        return xpath
    except Exception as e:
        logger.warning(f"Failed to generate XPath: {e}")
        return None

# -----------------------------------------------------------------------------
# Main Functions
# -----------------------------------------------------------------------------

def analyze_ui_elements(driver: webdriver.Chrome) -> Dict[str, List[Dict[str, Any]]]:
    """
    Analyze the page and identify common UI elements like buttons, links, inputs, etc.
    This helps with finding elements even when descriptions don't exactly match.
    
    Args:
        driver: WebDriver instance
        
    Returns:
        Dictionary with categorized UI elements
    """
    try:
        # Use JavaScript to analyze the page structure and extract elements by type
        js_script = """
        function analyzeUIElements() {
            const result = {
                buttons: [],
                links: [],
                inputs: [],
                dropdowns: [],
                checkboxes: [],
                radioButtons: [],
                menuItems: [],
                tabs: [],
                images: [],
                headings: [],
                cards: []
            };
            
            // Helper function to get a clean description of an element
            function getElementDescription(el) {
                let text = el.textContent?.trim() || '';
                let ariaLabel = el.getAttribute('aria-label') || '';
                let title = el.getAttribute('title') || '';
                let alt = el.getAttribute('alt') || '';
                let name = el.getAttribute('name') || '';
                let placeholder = el.getAttribute('placeholder') || '';
                let value = el.getAttribute('value') || '';
                
                // Combine all potential descriptive attributes
                let desc = text;
                if (!desc && ariaLabel) desc = ariaLabel;
                if (!desc && title) desc = title;
                if (!desc && alt) desc = alt;
                if (!desc && name) desc = name;
                if (!desc && placeholder) desc = placeholder;
                if (!desc && value) desc = value;
                
                return desc;
            }
            
            // Helper function to generate an XPath for an element
            function generateXPath(element) {
                let xpath = '';
                try {
                    let node = element;
                    let path = [];
                    while (node && node.nodeType === 1) {
                        let name = node.nodeName.toLowerCase();
                        let sibIndex = 1;
                        let sibs = node.previousSibling;
                        while (sibs) {
                            if (sibs.nodeName.toLowerCase() === name) {
                                sibIndex++;
                            }
                            sibs = sibs.previousSibling;
                        }
                        
                        if (node.hasAttribute('id')) {
                            path.unshift(`//${name}[@id='${node.id}']`);
                            break;
                        } else {
                            path.unshift(`${name}[${sibIndex}]`);
                        }
                        
                        node = node.parentNode;
                    }
                    
                    xpath = '/' + path.join('/');
                    while (xpath.includes('///')) {
                        xpath = xpath.replace('///', '//');
                    }
                    return xpath;
                } catch (e) {
                    return '';
                }
            }
            
            // Helper to get element's role - both explicit and implicit
            function getElementRole(el) {
                // Check explicit role attribute
                const role = el.getAttribute('role');
                if (role) return role;
                
                // Infer role from element type
                const tag = el.tagName.toLowerCase();
                if (tag === 'button') return 'button';
                if (tag === 'a') return 'link';
                if (tag === 'input') {
                    const type = el.type?.toLowerCase();
                    if (type === 'checkbox') return 'checkbox';
                    if (type === 'radio') return 'radio';
                    if (type === 'submit' || type === 'button') return 'button';
                    return 'textbox';
                }
                if (tag === 'select') return 'combobox';
                if (tag === 'textarea') return 'textbox';
                if (tag === 'img') return 'img';
                if (tag === 'h1' || tag === 'h2' || tag === 'h3' || tag === 'h4' || tag === 'h5' || tag === 'h6') return 'heading';
                
                // Check for common nav/menu patterns
                if (el.closest('nav') || el.closest('[role="navigation"]')) return 'menuitem';
                if (el.closest('menu') || el.closest('[role="menu"]')) return 'menuitem';
                if (el.closest('ul') && el.tagName.toLowerCase() === 'li') return 'listitem';
                
                // Check for styling cues
                const style = window.getComputedStyle(el);
                if (style.cursor === 'pointer') return 'clickable';
                
                return '';
            }
            
            // Enhanced function to detect regions (header, footer, sidebar, etc.)
            function detectRegions(el) {
                const regions = {
                    inHeader: false,
                    inFooter: false, 
                    inSidebar: false,
                    inMenu: false,
                    inForm: false,
                    inMain: false
                };
                
                // Check self first
                const tag = el.tagName.toLowerCase();
                const className = (el.className || '').toLowerCase();
                const id = (el.id || '').toLowerCase();
                const role = el.getAttribute('role') || '';
                
                // Header detection
                if (tag === 'header' || 
                    id.includes('header') || 
                    className.includes('header') || 
                    role === 'banner' ||
                    id.includes('top') ||
                    className.includes('top-bar') ||
                    className.includes('navbar') ||
                    className.includes('appbar')) {
                    regions.inHeader = true;
                }
                
                // Footer detection
                if (tag === 'footer' || 
                    id.includes('footer') || 
                    className.includes('footer') || 
                    role === 'contentinfo' ||
                    id.includes('bottom') ||
                    className.includes('bottom')) {
                    regions.inFooter = true;
                }
                
                // Sidebar detection
                if (id.includes('sidebar') || 
                    className.includes('sidebar') || 
                    id.includes('side') ||
                    className.includes('side') ||
                    role === 'complementary' ||
                    id.includes('drawer') ||
                    className.includes('drawer') ||
                    className.includes('panel')) {
                    regions.inSidebar = true;
                }
                
                // Menu detection
                if (tag === 'nav' || 
                    id.includes('nav') || 
                    className.includes('nav') || 
                    role === 'navigation' ||
                    id.includes('menu') ||
                    className.includes('menu') ||
                    className.includes('dropdown')) {
                    regions.inMenu = true;
                }
                
                // Form detection
                if (tag === 'form' || 
                    id.includes('form') || 
                    className.includes('form') || 
                    role === 'form' ||
                    el.closest('form') !== null) {
                    regions.inForm = true;
                }
                
                // Main content detection
                if (tag === 'main' || 
                    id.includes('main') || 
                    className.includes('main') || 
                    role === 'main' ||
                    id === 'content' ||
                    className.includes('content')) {
                    regions.inMain = true;
                }
                
                // Check ancestors if not determined yet
                if (!Object.values(regions).some(v => v === true)) {
                    let parent = el.parentElement;
                    while (parent && parent !== document.body) {
                        const pTag = parent.tagName.toLowerCase();
                        const pClassName = (parent.className || '').toLowerCase();
                        const pId = (parent.id || '').toLowerCase();
                        const pRole = parent.getAttribute('role') || '';
                        
                        // Header detection in ancestors
                        if (pTag === 'header' || 
                            pId.includes('header') || 
                            pClassName.includes('header') || 
                            pRole === 'banner' ||
                            pId.includes('top') ||
                            pClassName.includes('top-bar') ||
                            pClassName.includes('navbar') ||
                            pClassName.includes('appbar')) {
                            regions.inHeader = true;
                        }
                        
                        // Footer detection in ancestors
                        if (pTag === 'footer' || 
                            pId.includes('footer') || 
                            pClassName.includes('footer') || 
                            pRole === 'contentinfo' ||
                            pId.includes('bottom') ||
                            pClassName.includes('bottom')) {
                            regions.inFooter = true;
                        }
                        
                        // Sidebar detection in ancestors
                        if (pId.includes('sidebar') || 
                            pClassName.includes('sidebar') || 
                            pId.includes('side') ||
                            pClassName.includes('side') ||
                            pRole === 'complementary' ||
                            pId.includes('drawer') ||
                            pClassName.includes('drawer') ||
                            pClassName.includes('panel')) {
                            regions.inSidebar = true;
                        }
                        
                        // Menu detection in ancestors
                        if (pTag === 'nav' || 
                            pId.includes('nav') || 
                            pClassName.includes('nav') || 
                            pRole === 'navigation' ||
                            pId.includes('menu') ||
                            pClassName.includes('menu') ||
                            pClassName.includes('dropdown')) {
                            regions.inMenu = true;
                        }
                        
                        // Form detection in ancestors
                        if (pTag === 'form' || 
                            pId.includes('form') || 
                            pClassName.includes('form') || 
                            pRole === 'form') {
                            regions.inForm = true;
                        }
                        
                        // Main content detection in ancestors
                        if (pTag === 'main' || 
                            pId.includes('main') || 
                            pClassName.includes('main') || 
                            pRole === 'main' ||
                            pId === 'content' ||
                            pClassName.includes('content')) {
                            regions.inMain = true;
                        }
                        
                        parent = parent.parentElement;
                    }
                }
                
                // Position-based heuristics if still not determined
                if (!Object.values(regions).some(v => v === true)) {
                    const rect = el.getBoundingClientRect();
                    const viewportHeight = window.innerHeight;
                    const viewportWidth = window.innerWidth;
                    
                    // Top 15% of screen likely header
                    if (rect.top < viewportHeight * 0.15) {
                        regions.inHeader = true;
                    }
                    
                    // Bottom 15% of screen likely footer
                    if (rect.bottom > viewportHeight * 0.85) {
                        regions.inFooter = true;
                    }
                    
                    // Left 20% could be sidebar
                    if (rect.left < viewportWidth * 0.2 && rect.height > viewportHeight * 0.3) {
                        regions.inSidebar = true;
                    }
                    
                    // Right 20% could also be sidebar
                    if (rect.right > viewportWidth * 0.8 && rect.height > viewportHeight * 0.3) {
                        regions.inSidebar = true;
                    }
                }
                
                return regions;
            }
            
            // Function to check if element is in navigation/menu
            function isInMenu(el) {
                return !!el.closest('nav, [role="navigation"], menu, [role="menu"], .nav, .menu, .sidebar, .navigation');
            }
            
            // Function to check if element is a button (by appearance or behavior)
            function looksLikeButton(el) {
                if (el.tagName.toLowerCase() === 'button') return true;
                if (el.getAttribute('role') === 'button') return true;
                if (el.tagName.toLowerCase() === 'input' && (el.type === 'submit' || el.type === 'button')) return true;
                
                // Check for button-like styling
                const style = window.getComputedStyle(el);
                if (style.cursor === 'pointer' && 
                    ((style.border !== 'none' && style.border !== '') || 
                     (style.borderRadius !== '0px' && style.borderRadius !== '') ||
                     (style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent'))) {
                    return true;
                }
                
                // Check for common button classes
                const className = el.className.toLowerCase();
                return className.includes('btn') || className.includes('button');
            }
            
            // Collect all visible elements
            const allElements = document.querySelectorAll('*');
            for (const el of allElements) {
                // Skip non-visible elements
                if (el.offsetParent === null && !['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) {
                    continue;
                }
                
                const tag = el.tagName.toLowerCase();
                const role = getElementRole(el);
                const desc = getElementDescription(el);
                const regionInfo = detectRegions(el);
                const inMenu = regionInfo.inMenu || isInMenu(el);
                const xpath = generateXPath(el);
                const isClickable = window.getComputedStyle(el).cursor === 'pointer';
                
                // Skip elements without any description or role
                if (!desc && !role) continue;
                
                const elementInfo = {
                    tag: tag,
                    text: desc,
                    role: role,
                    xpath: xpath,
                    isClickable: isClickable,
                    inMenu: inMenu,
                    inHeader: regionInfo.inHeader,
                    inFooter: regionInfo.inFooter,
                    inSidebar: regionInfo.inSidebar,
                    inForm: regionInfo.inForm,
                    inMain: regionInfo.inMain,
                    attributes: {
                        id: el.id || '',
                        class: el.className || '',
                        name: el.getAttribute('name') || '',
                        type: el.getAttribute('type') || '',
                        href: el.getAttribute('href') || '',
                        src: el.getAttribute('src') || '',
                        placeholder: el.getAttribute('placeholder') || '',
                        value: el.getAttribute('value') || '',
                        'aria-label': el.getAttribute('aria-label') || '',
                        title: el.getAttribute('title') || ''
                    }
                };
                
                // Categorize elements
                if (tag === 'button' || role === 'button' || looksLikeButton(el)) {
                    result.buttons.push(elementInfo);
                }
                
                if (tag === 'a' || role === 'link') {
                    result.links.push(elementInfo);
                }
                
                if (tag === 'input' || tag === 'textarea' || role === 'textbox') {
                    if (el.type !== 'checkbox' && el.type !== 'radio' && el.type !== 'submit' && el.type !== 'button') {
                        result.inputs.push(elementInfo);
                    }
                }
                
                if (tag === 'select' || role === 'combobox' || role === 'listbox') {
                    result.dropdowns.push(elementInfo);
                }
                
                if (tag === 'input' && el.type === 'checkbox' || role === 'checkbox') {
                    result.checkboxes.push(elementInfo);
                }
                
                if (tag === 'input' && el.type === 'radio' || role === 'radio') {
                    result.radioButtons.push(elementInfo);
                }
                
                if (inMenu || role === 'menuitem') {
                    result.menuItems.push(elementInfo);
                }
                
                if (role === 'tab') {
                    result.tabs.push(elementInfo);
                }
                
                if (tag === 'img' || role === 'img') {
                    result.images.push(elementInfo);
                }
                
                if (tag.match(/^h[1-6]$/) || role === 'heading') {
                    result.headings.push(elementInfo);
                }
                
                // Detect card patterns (common in dashboard UIs)
                if (el.className.toLowerCase().includes('card') || 
                    (el.offsetWidth > 100 && el.offsetHeight > 100 && el.querySelectorAll('*').length > 3)) {
                    result.cards.push(elementInfo);
                }
            }
            
            return result;
        }
        
        return analyzeUIElements();
        """
        
        ui_elements = driver.execute_script(js_script)
        return ui_elements
    except Exception as e:
        logger.warning(f"Error analyzing UI elements: {e}")
        return {}

def find_element_by_intelligent_match(
    driver: webdriver.Chrome, 
    element_description: str, 
    ui_elements: Dict[str, List[Dict[str, Any]]]
) -> Optional[Dict[str, Any]]:
    """
    Find an element using more intelligent matching that understands context and UI patterns.
    
    Args:
        driver: WebDriver instance
        element_description: Text description of the element
        ui_elements: Dictionary of categorized UI elements
        
    Returns:
        Dictionary with element information if found, None otherwise
    """
    try:
        description_lower = element_description.lower()
        words = description_lower.split()
        
        # Extract element type from description
        element_type = None
        if "button" in description_lower:
            element_type = "buttons"
        elif "link" in description_lower:
            element_type = "links"
        elif any(x in description_lower for x in ["input", "field", "textbox", "text box"]):
            element_type = "inputs"
        elif any(x in description_lower for x in ["dropdown", "select", "combo box", "list box"]):
            element_type = "dropdowns"
        elif "checkbox" in description_lower:
            element_type = "checkboxes"
        elif "radio" in description_lower:
            element_type = "radioButtons"
        elif any(x in description_lower for x in ["menu item", "menu", "navigation", "nav"]):
            element_type = "menuItems"
        elif "tab" in description_lower:
            element_type = "tabs"
        elif "image" in description_lower or "img" in description_lower:
            element_type = "images"
        elif "heading" in description_lower or "header" in description_lower:
            element_type = "headings"
        elif "card" in description_lower:
            element_type = "cards"
        
        # Extract location context from description
        in_menu = "menu" in description_lower or "navigation" in description_lower or "nav" in description_lower
        in_header = "header" in description_lower or "top" in description_lower
        in_footer = "footer" in description_lower or "bottom" in description_lower
        in_sidebar = "sidebar" in description_lower or "side" in description_lower
        in_form = "form" in description_lower
        
        # Extract action context
        is_submit = "submit" in description_lower or "send" in description_lower
        is_cancel = "cancel" in description_lower
        is_search = "search" in description_lower
        is_login = "login" in description_lower or "log in" in description_lower or "sign in" in description_lower
        is_signup = "signup" in description_lower or "sign up" in description_lower or "register" in description_lower
        
        # If we can't determine element type, try all element types with priorities
        element_types_to_check = []
        if element_type:
            element_types_to_check.append(element_type)
        else:
            # Default priority for unknown element types
            # Adjust priority based on action context
            if is_submit or is_cancel or is_login or is_signup:
                element_types_to_check = [
                    "buttons", "links", "inputs", "menuItems", "tabs", 
                    "dropdowns", "checkboxes", "radioButtons", "images", "headings", "cards"
                ]
            elif is_search:
                element_types_to_check = [
                    "inputs", "buttons", "links", "menuItems", "tabs", 
                    "dropdowns", "checkboxes", "radioButtons", "images", "headings", "cards"
                ]
            else:
                element_types_to_check = [
                    "buttons", "links", "menuItems", "inputs", "dropdowns", 
                    "checkboxes", "radioButtons", "tabs", "images", "headings", "cards"
                ]
        
        # Check each element type
        for elem_type in element_types_to_check:
            elements = ui_elements.get(elem_type, [])
            best_match = None
            best_score = 0
            
            for element in elements:
                # Skip elements that don't match the location context if specified
                if (in_menu and not element.get("inMenu", False) and elem_type != "menuItems") or \
                   (in_header and not element.get("inHeader", False)) or \
                   (in_footer and not element.get("inFooter", False)) or \
                   (in_sidebar and not element.get("inSidebar", False)) or \
                   (in_form and not element.get("inForm", False)):
                    continue
                
                element_text = element.get("text", "").lower()
                element_attrs = element.get("attributes", {})
                
                # Calculate match score based on text and attribute matches
                score = 0
                
                # If the description matches the element text exactly, high score
                if element_text and (description_lower.endswith(element_text) or element_text.endswith(description_lower)):
                    score += 100
                elif element_text and (description_lower in element_text or element_text in description_lower):
                    score += 80
                
                # Check for partial text match
                for word in words:
                    if word in element_text and len(word) > 2:  # Only consider meaningful words
                        score += 10 * len(word)  # Longer word matches score higher
                
                # Check attributes for matches
                for attr_name, attr_value in element_attrs.items():
                    if not attr_value:
                        continue
                    
                    attr_value_lower = str(attr_value).lower()
                    
                    # Higher score for important attributes
                    multiplier = 1
                    if attr_name in ["id", "name", "title", "aria-label", "alt", "placeholder"]:
                        multiplier = 3
                    
                    for word in words:
                        if word in attr_value_lower and len(word) > 2:
                            score += 5 * len(word) * multiplier
                
                # Boost score for action-specific elements
                if is_submit and (
                    "submit" in element_text or 
                    "submit" in str(element_attrs.get("type", "")).lower() or
                    "send" in element_text
                ):
                    score += 50
                
                if is_cancel and "cancel" in element_text:
                    score += 50
                    
                if is_search and (
                    "search" in element_text or 
                    "search" in str(element_attrs.get("placeholder", "")).lower() or
                    "search" in str(element_attrs.get("name", "")).lower() or
                    "search" in str(element_attrs.get("id", "")).lower()
                ):
                    score += 50
                    
                if is_login and (
                    "login" in element_text or "log in" in element_text or "sign in" in element_text or
                    "login" in str(element_attrs.get("id", "")).lower() or
                    "signin" in str(element_attrs.get("id", "")).lower()
                ):
                    score += 50
                    
                if is_signup and (
                    "signup" in element_text or "sign up" in element_text or "register" in element_text or
                    "signup" in str(element_attrs.get("id", "")).lower() or
                    "register" in str(element_attrs.get("id", "")).lower()
                ):
                    score += 50
                
                # If this is a better match, update
                if score > best_score:
                    best_score = score
                    best_match = element
            
            # If we found a good match, return it
            if best_match and best_score > 10:  # Minimum threshold for a good match
                return best_match
        
        # No good match found
        return None
    except Exception as e:
        logger.warning(f"Error in intelligent element matching: {e}")
        return None

def find_smart_locator(
    url: str, 
    element_description: str, 
    wait_time: int = 10,
    need_login: bool = False,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    username_locator: Optional[str] = None,
    password_locator: Optional[str] = None,
    submit_locator: Optional[str] = None,
    success_indicator: Optional[str] = None,
    take_screenshot: bool = True
) -> Dict[str, Any]:
    """
    Find the best locator for an element based on its description.
    Uses multiple strategies for reliable element location.
    
    Args:
        url: URL of the web page containing the element
        element_description: Text description of the element
        wait_time: Time to wait for page to load in seconds
        need_login: Whether login is required before locating the element
        login_url: URL for login if different from main URL
        username: Username for login
        password: Password for login
        username_locator: Locator for username field
        password_locator: Locator for password field
        submit_locator: Locator for login submit button
        success_indicator: Optional element to verify successful login
        take_screenshot: Whether to take a screenshot of the found element
        
    Returns:
        Dictionary with locator information
    """
    result = {
        "url": url,
        "description": element_description,
        "locators": [],
        "recommended_locator": None,
        "element_found": False,
        "error": None
    }
    
    try:
        # Initialize WebDriver
        driver = initialize_webdriver()
        if not driver:
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Handle authentication if needed
        if need_login and username and password and username_locator and password_locator and submit_locator:
            auth_result = handle_authentication(
                driver=driver,
                url=login_url or url,
                username_locator=username_locator,
                password_locator=password_locator,
                submit_locator=submit_locator,
                username=username,
                password=password,
                wait_time=wait_time,
                success_indicator=success_indicator
            )
            
            result["authenticated"] = auth_result.get("success", False)
            result["auth_info"] = auth_result
            
            if not auth_result.get("success", False):
                result["error"] = f"Authentication failed: {auth_result.get('error', 'Unknown error')}"
                return result
                
            # Wait after successful login
            time.sleep(3)
            
        # Navigate to the URL if not already there (after login)
        if not need_login or driver.current_url != url:
            logger.info(f"Navigating to URL: {url}")
            driver.set_page_load_timeout(wait_time * 2)
            driver.get(url)
            
            # Wait for page to load
            logger.info(f"Waiting {wait_time} seconds for page to load")
            time.sleep(min(wait_time, 5))  # Cap the wait time for efficiency
        
        # Try smart locator strategies
        locators = []
        
        # Check if we're looking for an input field
        is_input_field_search = any(x in element_description.lower() for x in [
            "input", "field", "textbox", "text box", "form field", "enter", "type", "fill"
        ])
        
        # NEW APPROACH: First analyze all UI elements on the page
        ui_elements = analyze_ui_elements(driver)
        
        # Try to find the element using intelligent matching
        intelligent_match = find_element_by_intelligent_match(driver, element_description, ui_elements)
        
        if intelligent_match:
            # Create a locator for the intelligent match
            element_xpath = intelligent_match.get("xpath", "")
            if element_xpath:
                intelligent_locator = {
                    "locator": f"xpath={element_xpath}",
                    "locator_type": "xpath",
                    "tag_name": intelligent_match.get("tag", ""),
                    "text": intelligent_match.get("text", ""),
                    "attributes": intelligent_match.get("attributes", {}),
                    "strategy": "intelligent"
                }
                locators.append(intelligent_locator)
                
                # Try to find the element with this locator
                try:
                    element = safe_find_element(driver, By.XPATH, element_xpath)
                    if element:
                        # Check if we found a container instead of an input when looking for form fields
                        if is_input_field_search and element.tag_name.lower() not in ['input', 'textarea', 'select']:
                            input_element = find_input_in_container(driver, element)
                            if input_element:
                                # Add an input-specific locator
                                input_xpath = generate_xpath_for_element(driver, input_element)
                                if input_xpath:
                                    input_locator = {
                                        "locator": f"xpath={input_xpath}",
                                        "locator_type": "xpath",
                                        "tag_name": input_element.tag_name,
                                        "text": input_element.text if input_element.text else "",
                                        "attributes": {
                                            "id": input_element.get_attribute("id") or "",
                                            "name": input_element.get_attribute("name") or "",
                                            "type": input_element.get_attribute("type") or "",
                                            "placeholder": input_element.get_attribute("placeholder") or ""
                                        },
                                        "strategy": "input_element"
                                    }
                                    locators.append(input_locator)
                        
                        # Generate dynamic resilient locators for this element
                        dynamic_locator = get_dynamic_resilient_locator(driver, element)
                        
                        # Add all alternative locators 
                        if dynamic_locator.get("alternatives"):
                            result["dynamic_locator_options"] = dynamic_locator.get("alternatives", [])
                            
                            # Add the main dynamic locator
                            if dynamic_locator.get("locator"):
                                dynamic_result = {
                                    "locator": dynamic_locator["locator"],
                                    "locator_type": dynamic_locator["locator_type"],
                                    "tag_name": dynamic_locator["tag_name"],
                                    "text": dynamic_locator["text"],
                                    "attributes": dynamic_locator["attributes"],
                                    "strategy": "dynamic"
                                }
                                locators.append(dynamic_result)
                except Exception as e:
                    logger.warning(f"Error finding element with intelligent match: {e}")
        
        # If intelligent approach didn't find anything, try traditional approaches
        if not locators:
            # Strategy 1: JavaScript-based search to find matching element by description
            js_locator = get_locator_by_javascript(driver, element_description)
            if js_locator:
                # Make sure the XPath is normalized to avoid triple slashes
                if js_locator.get("locator", "").startswith("xpath="):
                    js_locator["locator"] = "xpath=" + normalize_xpath(js_locator["locator"][6:])
                    
                js_locator["strategy"] = "javascript"
                locators.append(js_locator)
                
                # If we found an element with JavaScript, use dynamic locator strategy on it
                try:
                    locator_type, locator_value = get_by_method(js_locator["locator"])
                    element = safe_find_element(driver, locator_type, locator_value)
                    
                    if element:
                        # Check if we found a container instead of an input when looking for form fields
                        if is_input_field_search and element.tag_name.lower() not in ['input', 'textarea', 'select']:
                            input_element = find_input_in_container(driver, element)
                            if input_element:
                                # Add an input-specific locator
                                input_xpath = generate_xpath_for_element(driver, input_element)
                                if input_xpath:
                                    input_locator = {
                                        "locator": f"xpath={input_xpath}",
                                        "locator_type": "xpath",
                                        "tag_name": input_element.tag_name,
                                        "text": input_element.text if input_element.text else "",
                                        "attributes": {
                                            "id": input_element.get_attribute("id") or "",
                                            "name": input_element.get_attribute("name") or "",
                                            "type": input_element.get_attribute("type") or "",
                                            "placeholder": input_element.get_attribute("placeholder") or ""
                                        },
                                        "strategy": "input_element"
                                    }
                                    locators.append(input_locator)
                        
                        # Use dynamic locator strategy 
                        dynamic_locator = get_dynamic_resilient_locator(driver, element)
                        
                        # Add all alternative locators 
                        if dynamic_locator.get("alternatives"):
                            result["dynamic_locator_options"] = dynamic_locator.get("alternatives", [])
                            
                            # Add the main dynamic locator
                            if dynamic_locator.get("locator"):
                                dynamic_result = {
                                    "locator": dynamic_locator["locator"],
                                    "locator_type": dynamic_locator["locator_type"],
                                    "tag_name": dynamic_locator["tag_name"],
                                    "text": dynamic_locator["text"],
                                    "attributes": dynamic_locator["attributes"],
                                    "strategy": "dynamic"
                                }
                                locators.append(dynamic_result)
                except Exception as e:
                    logger.warning(f"Error getting dynamic locators for JavaScript match: {e}")
            
            # Strategy 2: Accessibility-based search
            accessibility_locator = get_locator_by_accessibility(driver, element_description)
            if accessibility_locator:
                accessibility_locator["strategy"] = "accessibility"
                locators.append(accessibility_locator)
            
            # Strategy 3: Position-based search (last resort)
            position_locator = get_locator_by_relative_position(driver, element_description)
            if position_locator:
                position_locator["strategy"] = "relative_position"
                locators.append(position_locator)
        
        # Add all locators to the result
        result["locators"] = locators
        
        # Determine recommended locator
        if locators:
            # Prioritize strategies
            strategy_priority = ["input_element", "intelligent", "dynamic", "javascript", "accessibility", "relative_position"]
            
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
                
            # Verify the recommended locator works
            if result["recommended_locator"]:
                try:
                    locator_type, locator_value = get_by_method(result["recommended_locator"])
                    
                    # Make sure to normalize XPath if that's the locator type
                    if locator_type == By.XPATH:
                        locator_value = normalize_xpath(locator_value)
                    
                    # Use safe find with XPath normalization
                    element = safe_find_element(driver, locator_type, locator_value)
                    result["element_found"] = (element is not None)
                    
                    # Take a screenshot if requested and element found
                    if take_screenshot and element:
                        try:
                            result["screenshot"] = driver.get_screenshot_as_base64()
                        except Exception as e:
                            logger.warning(f"Failed to take screenshot: {e}")
                except Exception as e:
                    logger.warning(f"Error verifying recommended locator: {e}")
                    result["element_found"] = False
        
        # Final check if it's an input field search but we didn't find any input fields
        if is_input_field_search and result["recommended_locator"] and result["element_found"]:
            try:
                locator_type, locator_value = get_by_method(result["recommended_locator"])
                element = safe_find_element(driver, locator_type, locator_value)
                
                if element and element.tag_name.lower() not in ['input', 'textarea', 'select']:
                    logger.info("Found a container instead of an input field, trying to find the input inside")
                    input_element = find_input_in_container(driver, element)
                    
                    if input_element:
                        # Generate a new XPath for the input element
                        input_xpath = generate_xpath_for_element(driver, input_element)
                        if input_xpath:
                            result["recommended_locator"] = f"xpath={input_xpath}"
                            
                            # Add this locator to the list if not already there
                            already_exists = False
                            for locator in locators:
                                if locator["locator"] == result["recommended_locator"]:
                                    already_exists = True
                                    break
                                    
                            if not already_exists:
                                input_locator = {
                                    "locator": result["recommended_locator"],
                                    "locator_type": "xpath",
                                    "tag_name": input_element.tag_name,
                                    "text": input_element.text if input_element.text else "",
                                    "attributes": {
                                        "id": input_element.get_attribute("id") or "",
                                        "name": input_element.get_attribute("name") or "",
                                        "type": input_element.get_attribute("type") or "",
                                        "placeholder": input_element.get_attribute("placeholder") or ""
                                    },
                                    "strategy": "input_element"
                                }
                                locators.insert(0, input_locator)
                                result["locators"] = locators
            except Exception as e:
                logger.warning(f"Error in final input field check: {e}")
        
        return result
    except Exception as e:
        result["error"] = f"Error finding smart locator: {str(e)}"
        return result
    finally:
        # Don't close the driver since we're using a shared driver from BrowserManager
        pass

def find_input_in_container(driver: webdriver.Chrome, container: WebElement) -> Optional[WebElement]:
    """
    Find an input element within a container element.
    Used when the smart locator has identified a container instead of the actual input field.
    
    Args:
        driver: WebDriver instance
        container: Container WebElement
        
    Returns:
        Input WebElement if found, None otherwise
    """
    try:
        # Check if the container itself is an input
        if container.tag_name.lower() in ['input', 'textarea', 'select']:
            return container
            
        # Check for input elements inside the container
        # Priority order: input > textarea > select
        input_elements = []
        
        # Find by tag name
        for tag in ['input', 'textarea', 'select']:
            try:
                elements = container.find_elements(By.TAG_NAME, tag)
                if elements:
                    input_elements.extend(elements)
            except Exception:
                pass
                
        # Find by role
        for role in ['textbox', 'combobox', 'listbox', 'searchbox']:
            try:
                elements = container.find_elements(By.CSS_SELECTOR, f'[role="{role}"]')
                if elements:
                    input_elements.extend(elements)
            except Exception:
                pass
        
        # Check for visible inputs only, prioritizing those with non-empty attributes
        if input_elements:
            visible_inputs = []
            for input_el in input_elements:
                try:
                    if input_el.is_displayed():
                        # Skip button and submit inputs
                        input_type = input_el.get_attribute('type')
                        if input_type in ['button', 'submit', 'reset', 'image', 'file', 'hidden']:
                            continue
                        
                        # Prioritize inputs with useful attributes
                        score = 0
                        if input_el.get_attribute('id'):
                            score += 5
                        if input_el.get_attribute('name'):
                            score += 5
                        if input_el.get_attribute('placeholder'):
                            score += 3
                        if input_el.get_attribute('aria-label'):
                            score += 3
                        if input_el.get_attribute('label'):
                            score += 2
                            
                        visible_inputs.append((input_el, score))
                except Exception:
                    pass
            
            # Sort by score (higher is better)
            visible_inputs.sort(key=lambda x: x[1], reverse=True)
            
            if visible_inputs:
                return visible_inputs[0][0]
        
        return None
    except Exception as e:
        logger.warning(f"Error finding input in container: {e}")
        return None

def automate_form(
    url: str,
    form_data: Dict[str, str],
    submit_locator: Optional[str] = None,
    wait_time: int = 10,
    need_login: bool = False,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    username_locator: Optional[str] = None,
    password_locator: Optional[str] = None,
    login_submit_locator: Optional[str] = None,
    success_indicator: Optional[str] = None,
    wait_success_element: Optional[str] = None,
    wait_success_time: int = 5,
    include_screenshot: bool = False
) -> Dict[str, Any]:
    """
    Fill and submit a form on a web page using dynamic locators.
    
    Args:
        url: URL of the form to automate
        form_data: Dictionary of field locators and values to fill
        submit_locator: Locator for form submit button
        wait_time: Time to wait for page to load in seconds
        need_login: Whether login is required
        login_url: URL of the login page if different from form URL
        username: Username for login
        password: Password for login
        username_locator: Locator for username field
        password_locator: Locator for password field
        login_submit_locator: Locator for login submit button
        success_indicator: Optional element to verify successful login
        wait_success_element: Element to wait for after form submission
        wait_success_time: Time to wait for success element
        include_screenshot: Whether to include a screenshot in the result (default: False)
        
    Returns:
        Dictionary with form automation results
    """
    result = {
        "url": url,
        "success": False,
        "authenticated": None,
        "auth_info": None,
        "form_detected": False,
        "fields_filled": [],
        "submitted": False,
        "error": None,
        "screenshot": None
    }
    
    driver = None
    try:
        # Initialize WebDriver
        driver = initialize_webdriver()
        if not driver:
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Handle authentication if needed
        if need_login and username and password and username_locator and password_locator and login_submit_locator:
            auth_result = handle_authentication(
                driver=driver,
                url=login_url or url,
                username_locator=username_locator,
                password_locator=password_locator,
                submit_locator=login_submit_locator,
                username=username,
                password=password,
                wait_time=wait_time,
                success_indicator=success_indicator
            )
            
            result["authenticated"] = auth_result.get("success", False)
            result["auth_info"] = auth_result
            
            if not auth_result.get("success", False):
                result["error"] = f"Authentication failed: {auth_result.get('error', 'Unknown error')}"
                return result
                
            # Wait after successful login
            time.sleep(3)
            
        # Navigate to the URL if not already there (after login)
        if not need_login or driver.current_url != url:
            logger.info(f"Navigating to URL: {url}")
            driver.set_page_load_timeout(wait_time * 2)
            driver.get(url)
            
            # Wait for page to load
            logger.info(f"Waiting {min(wait_time, 5)} seconds for page to load")
            time.sleep(min(wait_time, 5))  # Cap the wait time for efficiency
            
        # If no form data is provided, try to detect the form
        if not form_data:
            form_result = detect_form_fields(driver)
            result["form_detected"] = not form_result.get("error")
            result["detected_fields"] = form_result.get("form_fields", {})
            result["detected_submit"] = form_result.get("submit_button")
            
            if form_result.get("error"):
                result["error"] = f"Form detection failed: {form_result.get('error')}"
                return result
                
            # No further action if just detecting
            return result
            
        # Fill form fields
        filled_fields = []
        for field_name, field_value in form_data.items():
            try:
                field_by, field_selector = get_by_method(field_name)
                field_element = WebDriverWait(driver, wait_time).until(
                    EC.element_to_be_clickable((field_by, field_selector))
                )
                
                # Clear existing value first
                field_element.clear()
                
                # Fill the field
                field_element.send_keys(field_value)
                filled_fields.append(field_name)
            except Exception as e:
                logger.warning(f"Failed to fill field {field_name}: {e}")
                
        result["fields_filled"] = filled_fields
        
        # Submit the form
        if submit_locator:
            try:
                submit_by, submit_selector = get_by_method(submit_locator)
                submit_element = WebDriverWait(driver, wait_time).until(
                    EC.element_to_be_clickable((submit_by, submit_selector))
                )
                
                # Click the submit button
                submit_element.click()
                result["submitted"] = True
                
                # Wait for success indicator if provided
                if wait_success_element:
                    try:
                        success_by, success_selector = get_by_method(wait_success_element)
                        WebDriverWait(driver, wait_success_time).until(
                            EC.presence_of_element_located((success_by, success_selector))
                        )
                        result["success"] = True
                    except TimeoutException:
                        result["success"] = False
                        result["error"] = f"Success element not found after submission: {wait_success_element}"
                else:
                    # If no success indicator, assume success if submitted
                    time.sleep(wait_success_time)  # Wait for potential page changes
                    result["success"] = True
            except Exception as e:
                result["error"] = f"Form submission failed: {e}"
                result["submitted"] = False
                
        # Take a screenshot
        try:
            result["screenshot"] = driver.get_screenshot_as_base64()
        except:
            pass
            
        # Remove screenshot from result if not requested
        if not include_screenshot and "screenshot" in result:
            del result["screenshot"]
            
        return result
    except Exception as e:
        logger.error(f"Error automating form: {e}")
        result["error"] = str(e)
        return result
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
            
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
        locator_type, locator_value = get_by_method(locator)
        
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
            
            # Check if element is visible
            if element.is_displayed():
                reliability_score += 20
            else:
                reliability_score -= 10
                suggestions.append("Element is not visible - consider checking visibility before operations")
                
            # Check if element is enabled (for inputs, buttons)
            if element.tag_name in ['input', 'button', 'select', 'textarea', 'a']:
                if element.is_enabled():
                    reliability_score += 20
                else:
                    reliability_score -= 10
                    suggestions.append("Element is disabled - check if it becomes enabled")
                    
            # Check for better locator options
            element_id = element.get_attribute("id")
            if element_id and locator_type != By.ID:
                suggestions.append(f"Consider using id={element_id} for better reliability")
                
            element_name = element.get_attribute("name")
            if element_name and locator_type != By.NAME:
                suggestions.append(f"Consider using name={element_name} for better reliability")
                
            # Check locator type resilience
            if locator_type == By.XPATH:
                # Check if XPath is too complex
                if len(locator_value) > 100:
                    reliability_score -= 10
                    suggestions.append("XPath is very complex - consider simplifying")
                    
                # Check if using fragile approaches
                if "//*//" in locator_value:
                    reliability_score -= 10
                    suggestions.append("XPath contains // sequences which are fragile to DOM changes")
                    
                if "[" in locator_value and "]" in locator_value and not "contains" in locator_value:
                    reliability_score -= 5
                    suggestions.append("XPath uses indexed elements which are fragile to DOM changes")
            
            # Set final score and robustness
            result["reliability_score"] = max(0, min(100, reliability_score + 30))  # Normalize to 0-100
            result["is_robust"] = result["reliability_score"] >= 70
            result["suggestions"] = suggestions
            
            return result
        except NoSuchElementException:
            result["error"] = "Element not found with the provided locator"
            return result
        except Exception as e:
            result["error"] = f"Error evaluating locator: {e}"
        return result
    except Exception as e:
        logger.error(f"Error evaluating locator robustness: {e}")
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def find_dynamic_locator(url: str, css_selector: str, wait_time: int = 10) -> Dict[str, Any]:
    """
    Find dynamic, resilient locators for an element specified by CSS selector.
    This is useful when you have an initial selector but need more robust alternatives
    that will work even if the page structure changes.
    
    Args:
        url: URL of the web page
        css_selector: CSS selector to find the element initially
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with dynamic locator results
    """
    result = {
        "url": url,
        "original_selector": css_selector,
        "dynamic_locators": [],
        "recommended_locator": None,
        "element_found": False,
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
        time.sleep(min(wait_time, 5))
        
        # Try to find the element with the provided CSS selector
        try:
            element = driver.find_element(By.CSS_SELECTOR, css_selector)
            result["element_found"] = True
            
            # Use dynamic strategy to generate resilient locators
            dynamic_result = get_dynamic_resilient_locator(driver, element)
            
            # Add all alternative locators
            if dynamic_result.get("alternatives"):
                result["dynamic_locators"] = dynamic_result.get("alternatives", [])
                
                # Sort by reliability
                result["dynamic_locators"].sort(key=lambda x: x.get('reliability', 0), reverse=True)
                
                # Set recommended locator
                if result["dynamic_locators"]:
                    result["recommended_locator"] = result["dynamic_locators"][0]["locator"]
            
            # Take a screenshot
            try:
                result["screenshot"] = driver.get_screenshot_as_base64()
            except:
                pass
                
        except NoSuchElementException:
            result["error"] = f"Element not found with selector: {css_selector}"
        except Exception as e:
            result["error"] = f"Error finding element: {str(e)}"
            
        return result
    except Exception as e:
        logger.error(f"Error in find_dynamic_locator: {e}")
        result["error"] = str(e)
        return result
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """
    Register all tools with MCP.
    
    This tool replaces and consolidates functionality from:
    - robot_auto_locator
    - robot_form_locator
    - robot_xpath_locator
    - robot_auth_handler
    - robot_form_automator
    
    These tools can be removed from the server.py imports.
    """
    
    @mcp.tool()
    async def robot_find_smart_locator(
        url: str,
        element_description: str,
        wait_time: int = 10,
        need_login: bool = False,
        login_url: str = "",
        username: str = "",
        password: str = "",
        username_locator: str = "",
        password_locator: str = "",
        submit_locator: str = "",
        success_indicator: str = "",
        include_screenshot: bool = False,
        take_screenshot: bool = True
    ) -> Dict[str, Any]:
        """
        Find the best locator for a web element based on its description.
        
        This enhanced version uses intelligent matching to understand context and UI patterns,
        making it more effective at finding elements based on descriptions like:
        - "Submit button"
        - "My Info link in main menu"
        - "Username field in login form"
        - "Search box in header"
        
        The tool now:
        1. Better understands page regions (header, footer, sidebar, menu)
        2. Intelligently identifies actual input fields instead of containers
        3. Prioritizes elements based on context and semantic understanding
        4. Finds elements even when descriptions don't match exactly
        
        Args:
            url: URL of the page containing the element
            element_description: Description of the element to locate
            wait_time: Time to wait for page to load in seconds
            need_login: Whether login is required before locating the element
            login_url: URL for login if different from main URL
            username: Username for login
            password: Password for login
            username_locator: Locator for username field
            password_locator: Locator for password field
            submit_locator: Locator for login submit button
            success_indicator: Optional element to verify successful login
            include_screenshot: Whether to include a screenshot in the result
            take_screenshot: Whether to take screenshots during the process
            
        Returns:
            Dictionary with locator information and recommendations
        """
        result = find_smart_locator(
            url=url,
            element_description=element_description,
            wait_time=wait_time,
            need_login=need_login,
            login_url=login_url or None,
            username=username or None,
            password=password or None,
            username_locator=username_locator or None,
            password_locator=password_locator or None,
            submit_locator=submit_locator or None,
            success_indicator=success_indicator or None,
            take_screenshot=take_screenshot
        )
        
        # Remove screenshot from result if not requested
        if not include_screenshot and "screenshot" in result:
            del result["screenshot"]
            
        return result
    
    @mcp.tool()
    async def robot_find_dynamic_locator(
        url: str,
        css_selector: str,
        wait_time: int = 10,
        include_screenshot: bool = False
    ) -> Dict[str, Any]:
        """
        Create multiple dynamic, resilient locators for an element specified by CSS selector.
        Useful when you need locators that will work even when website structure changes.
        
        Args:
            url: URL of the web page
            css_selector: CSS selector to find the element initially
            wait_time: Time to wait for page to load in seconds
            include_screenshot: Whether to include a screenshot in the result (default: False)
            
        Returns:
            Dictionary with multiple dynamic locator options and recommendations
        """
        result = find_dynamic_locator(
            url=url,
            css_selector=css_selector,
            wait_time=wait_time
        )
        
        # Remove screenshot from result if not requested
        if not include_screenshot and "screenshot" in result:
            del result["screenshot"]
        
        return result
    
    @mcp.tool()
    async def robot_evaluate_locator_robustness(
        url: str,
        locator: str,
        wait_time: int = 5
    ) -> Dict[str, Any]:
        """
        Evaluate a locator for robustness and reliability.
        
        Args:
            url: URL of the web page
            locator: Locator to evaluate
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dictionary with evaluation results
        """
        return evaluate_locator_robustness(
            url=url,
            locator=locator,
            wait_time=wait_time
        )
    
    @mcp.tool()
    async def robot_authenticate_page(
        url: str,
        username_locator: str,
        password_locator: str,
        submit_locator: str,
        username: str,
        password: str,
        wait_time: int = 10,
        success_indicator: str = "",
        failure_indicator: str = "",
        include_screenshot: bool = False
    ) -> Dict[str, Any]:
        """
        Authenticate to a web page using the provided credentials.
        
        Args:
            url: URL of the login page
            username_locator: Locator for the username field
            password_locator: Locator for the password field
            submit_locator: Locator for the submit button
            username: Username to use for login
            password: Password to use for login
            wait_time: Time to wait for page to load in seconds
            success_indicator: Optional element to verify successful login
            failure_indicator: Optional element to detect failed login
            include_screenshot: Whether to include a screenshot in the result
            
        Returns:
            Dictionary with authentication result
        """
        # Convert empty strings to None for optional parameters
        success_indicator = success_indicator or None
        failure_indicator = failure_indicator or None
        
        driver = None
        result = {
            "url": url,
            "success": False,
            "current_url": "",
            "page_title": "",
            "error": None
        }
        try:
            driver = initialize_webdriver()
            if not driver:
                result["error"] = "Failed to initialize WebDriver"
                return result
                
            result = handle_authentication(
                driver=driver,
                url=url,
                username_locator=username_locator,
                password_locator=password_locator,
                submit_locator=submit_locator,
                username=username,
                password=password,
                wait_time=wait_time,
                success_indicator=success_indicator,
                failure_indicator=failure_indicator
            )
            
            # Remove screenshot from result if not requested
            if not include_screenshot and "screenshot" in result:
                del result["screenshot"]
            
            return result
        except Exception as e:
            logger.error(f"Error in authenticate_page: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    @mcp.tool()
    async def robot_detect_form(
        url: str,
        wait_time: int = 10,
        need_login: bool = False,
        login_url: str = "",
        username: str = "",
        password: str = "",
        username_locator: str = "",
        password_locator: str = "",
        submit_locator: str = "",
        success_indicator: str = "",
        include_screenshot: bool = False
    ) -> Dict[str, Any]:
        """
        Detect form fields on a web page for automated form filling.
        
        Args:
            url: URL of the web page containing the form
            wait_time: Time to wait for page to load in seconds
            need_login: Whether login is required before detecting form
            login_url: URL for login if different from main URL
            username: Username for login
            password: Password for login
            username_locator: Locator for username field
            password_locator: Locator for password field
            submit_locator: Locator for login submit button
            success_indicator: Optional element to verify successful login
            include_screenshot: Whether to include a screenshot in the result
            
        Returns:
            Dictionary with detected form fields
        """
        # Convert empty strings to None for optional parameters
        login_url = login_url or None
        username = username or None
        password = password or None
        username_locator = username_locator or None
        password_locator = password_locator or None
        submit_locator = submit_locator or None
        success_indicator = success_indicator or None
        
        driver = None
        result = {
            "url": url,
            "fields": [],
            "form_found": False,
            "error": None
        }
        try:
            driver = initialize_webdriver()
            if not driver:
                result["error"] = "Failed to initialize WebDriver"
                return result
                
            result = handle_authentication(
                driver=driver,
            url=url,
            username_locator=username_locator,
            password_locator=password_locator,
                submit_locator=submit_locator,
                username=username,
                password=password,
                wait_time=wait_time,
            success_indicator=success_indicator
        )
            
            # Remove screenshot from result if not requested
            if not include_screenshot and "screenshot" in result:
                del result["screenshot"]
            
            return result
        except Exception as e:
            logger.error(f"Error in detect_form: {e}")
            result["error"] = str(e)
            return result
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    @mcp.tool()
    async def robot_fill_form(
        url: str,
        form_data: Dict[str, str],
        submit_locator: str = "",
        wait_time: int = 10,
        need_login: bool = False,
        login_url: str = "",
        username: str = "",
        password: str = "",
        username_locator: str = "",
        password_locator: str = "",
        login_submit_locator: str = "",
        success_indicator: str = "",
        wait_success_element: str = "",
        wait_success_time: int = 5,
        include_screenshot: bool = False
    ) -> Dict[str, Any]:
        """
        Automate form filling and submission with intelligent field detection.
        
        Args:
            url: URL of the web page containing the form
            form_data: Dictionary mapping field descriptions to values
            submit_locator: Locator for the form submit button
            wait_time: Time to wait for page to load in seconds
            need_login: Whether login is required before filling form
            login_url: URL for login if different from main URL
            username: Username for login
            password: Password for login
            username_locator: Locator for username field
            password_locator: Locator for password field
            login_submit_locator: Locator for login submit button
            success_indicator: Optional element to verify successful login
            wait_success_element: Element to wait for after form submission
            wait_success_time: Time to wait for success element in seconds
            include_screenshot: Whether to include a screenshot in the result
            
        Returns:
            Dictionary with form submission result
        """
        # Convert empty strings to None for optional parameters
        submit_locator = submit_locator or None
        login_url = login_url or None
        username = username or None
        password = password or None
        username_locator = username_locator or None
        password_locator = password_locator or None
        login_submit_locator = login_submit_locator or None
        success_indicator = success_indicator or None
        wait_success_element = wait_success_element or None
        
        return automate_form(
            url=url,
            form_data=form_data,
            submit_locator=submit_locator,
            wait_time=wait_time,
            need_login=need_login,
            login_url=login_url,
            username=username,
            password=password,
            username_locator=username_locator,
            password_locator=password_locator,
            login_submit_locator=login_submit_locator,
            success_indicator=success_indicator,
            wait_success_element=wait_success_element,
            wait_success_time=wait_success_time,
            include_screenshot=include_screenshot
        )
    
    @mcp.tool()
    async def robot_map_page_ui(
        url: str,
        wait_time: int = 10,
        need_login: bool = False,
        login_url: str = "",
        username: str = "",
        password: str = "",
        username_locator: str = "",
        password_locator: str = "",
        login_submit_locator: str = "",
        success_indicator: str = "",
        include_screenshot: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze a web page and create a comprehensive map of all UI elements.
        This is useful for:
        1. Getting all possible interactive elements even when smart locator can't find them
        2. Creating a catalog of UI elements for reference and testing
        3. Finding navigation menus, buttons, and other important UI elements
        
        Args:
            url: URL of the web page to analyze
            wait_time: Time to wait for page to load in seconds
            need_login: Whether login is required before analyzing
            login_url: URL for login if different from main URL
            username: Username for login
            password: Password for login  
            username_locator: Locator for username field
            password_locator: Locator for password field
            login_submit_locator: Locator for login submit button
            success_indicator: Optional element to verify successful login
            include_screenshot: Whether to include a screenshot in the result
            
        Returns:
            Dictionary with categorized UI elements and their locators
        """
        # Convert empty strings to None for optional parameters
        login_url = login_url or None
        username = username or None
        password = password or None
        username_locator = username_locator or None
        password_locator = password_locator or None
        login_submit_locator = login_submit_locator or None
        success_indicator = success_indicator or None
        
        result = {
            "url": url,
            "page_title": "",
            "authenticated": None,
            "ui_map": {
                "navigation": [],
                "main_menu": [],
                "buttons": [],
                "links": [],
                "form_fields": [],
                "important_elements": []
            },
            "error": None
        }
        
        driver = None
        try:
            # Initialize WebDriver
            driver = initialize_webdriver()
            if not driver:
                result["error"] = "Failed to initialize WebDriver"
                return result
                
            # Handle authentication if needed
            if need_login and username and password and username_locator and password_locator and login_submit_locator:
                auth_result = handle_authentication(
                    driver=driver,
                    url=login_url or url,
                    username_locator=username_locator,
                    password_locator=password_locator,
                    submit_locator=login_submit_locator,
                    username=username,
                    password=password,
                    wait_time=wait_time,
                    success_indicator=success_indicator
                )
                
                result["authenticated"] = auth_result.get("success", False)
                
                if not auth_result.get("success", False):
                    result["error"] = f"Authentication failed: {auth_result.get('error', 'Unknown error')}"
                    return result
                    
                # Wait after successful login
                time.sleep(3)
                
            # Navigate to the URL if not already there (after login)
            if not need_login or driver.current_url != url:
                logger.info(f"Navigating to URL: {url}")
                driver.set_page_load_timeout(wait_time * 2)
                driver.get(url)
                
                # Wait for page to load
                logger.info(f"Waiting {wait_time} seconds for page to load")
                time.sleep(min(wait_time, 5))  # Cap the wait time for efficiency
            
            # Get page title
            result["page_title"] = driver.title
            
            # Use JavaScript to analyze the page and find all important elements
            js_script = """
            function mapPageUI() {
                const result = {
                    navigation: [],
                    main_menu: [],
                    buttons: [],
                    links: [],
                    form_fields: [],
                    important_elements: []
                };
                
                // Helper to get element description
                function getElementDescription(el) {
                    let text = el.textContent?.trim() || '';
                    let ariaLabel = el.getAttribute('aria-label') || '';
                    let title = el.getAttribute('title') || '';
                    let alt = el.getAttribute('alt') || '';
                    let name = el.getAttribute('name') || '';
                    let placeholder = el.getAttribute('placeholder') || '';
                    let value = el.getAttribute('value') || '';
                    
                    // Combine all potential descriptive attributes
                    let desc = text;
                    if (!desc && ariaLabel) desc = ariaLabel;
                    if (!desc && title) desc = title;
                    if (!desc && alt) desc = alt;
                    if (!desc && name) desc = name;
                    if (!desc && placeholder) desc = placeholder;
                    if (!desc && value) desc = value;
                    
                    return desc;
                }
                
                // Helper to generate XPath
                function generateXPath(element) {
                    let xpath = '';
                    try {
                        if (element.id) {
                            return `//*[@id="${element.id}"]`;
                        }
                        
                        let node = element;
                        let path = [];
                        while (node && node.nodeType === 1) {
                            let name = node.nodeName.toLowerCase();
                            let sibIndex = 1;
                            let sibs = node.previousSibling;
                            while (sibs) {
                                if (sibs.nodeName.toLowerCase() === name) {
                                    sibIndex++;
                                }
                                sibs = sibs.previousSibling;
                            }
                            
                            path.unshift(`${name}[${sibIndex}]`);
                            node = node.parentNode;
                        }
                        
                        xpath = '/' + path.join('/');
                        return xpath;
                    } catch (e) {
                        return '';
                    }
                }
                
                // Helper to check if element is in navigation
                function isInNavigation(el) {
                    return !!el.closest('nav, [role="navigation"], aside, .sidebar, .nav, .navigation, .menu, [role="menu"]');
                }
                
                // Helper to check if element is clickable
                function isClickable(el) {
                    if (el.tagName === 'A' || el.tagName === 'BUTTON') return true;
                    if (el.onclick) return true;
                    if (el.getAttribute('role') === 'button' || el.getAttribute('role') === 'link') return true;
                    
                    const style = window.getComputedStyle(el);
                    return style.cursor === 'pointer';
                }
                
                // Find all navigation elements
                const navElements = document.querySelectorAll('nav, [role="navigation"], .nav, .sidebar, .navigation, aside');
                navElements.forEach(nav => {
                    const navItems = nav.querySelectorAll('a, button, [role="link"], [role="button"], [role="menuitem"], li');
                    navItems.forEach(item => {
                        if (!item.offsetParent) return; // Skip hidden items
                        
                        const desc = getElementDescription(item);
                        if (!desc) return; // Skip items without description
                        
                        result.navigation.push({
                            text: desc,
                            tag: item.tagName.toLowerCase(),
                            xpath: generateXPath(item),
                            css_selector: item.id ? `#${item.id}` : null,
                            attributes: {
                                id: item.id || '',
                                class: item.className || '',
                                href: item.getAttribute('href') || ''
                            }
                        });
                        
                        // Also add to main menu if it looks like a main menu item
                        if (nav.id?.includes('menu') || 
                            nav.className?.includes('menu') || 
                            nav.getAttribute('role') === 'menubar' ||
                            nav.getAttribute('aria-label')?.includes('Main')) {
                            result.main_menu.push({
                                text: desc,
                                tag: item.tagName.toLowerCase(),
                                xpath: generateXPath(item),
                                css_selector: item.id ? `#${item.id}` : null,
                                attributes: {
                                    id: item.id || '',
                                    class: item.className || '',
                                    href: item.getAttribute('href') || ''
                                }
                            });
                        }
                    });
                });
                
                // Find all buttons
                const buttonElements = document.querySelectorAll('button, [role="button"], input[type="button"], input[type="submit"], .btn, .button');
                buttonElements.forEach(button => {
                    if (!button.offsetParent) return; // Skip hidden buttons
                    
                    const desc = getElementDescription(button);
                    if (!desc) return; // Skip buttons without description
                    
                    result.buttons.push({
                        text: desc,
                        tag: button.tagName.toLowerCase(),
                        xpath: generateXPath(button),
                        css_selector: button.id ? `#${button.id}` : null,
                        attributes: {
                            id: button.id || '',
                            class: button.className || '',
                            type: button.getAttribute('type') || ''
                        }
                    });
                });
                
                return result;
            }
            
            return mapPageUI();
            """
            
            ui_map = driver.execute_script(js_script)
            
            # Process the results to create locators
            for category, elements in ui_map.items():
                result["ui_map"][category] = []
                
                for element in elements:
                    # Create a locator string
                    locator = None
                    if element.get("css_selector"):
                        locator = f"css={element['css_selector']}"
                    elif element.get("xpath"):
                        # Normalize the XPath to avoid triple slashes
                        xpath = normalize_xpath(element["xpath"])
                        locator = f"xpath={xpath}"
                        
                    if locator:
                        result["ui_map"][category].append({
                            "text": element.get("text", ""),
                            "tag": element.get("tag", ""),
                            "locator": locator,
                            "attributes": element.get("attributes", {})
                        })
            
            return result
        except Exception as e:
            logger.error(f"Error mapping page UI: {e}")
            result["error"] = str(e)
            return result
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass