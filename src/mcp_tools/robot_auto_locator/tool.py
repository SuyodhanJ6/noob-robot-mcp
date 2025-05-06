#!/usr/bin/env python
"""
MCP Tool: Robot Auto Locator
Automatically finds all possible locators for elements on a web page.
Combines multiple locator strategies for comprehensive element identification.
Supports optional authentication through central AuthManager.
"""

import os
import logging
import json
import time
import re
import base64
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

# Import shared browser manager
from src.mcp_tools.robot_browser_manager import BrowserManager

# Import auth manager for optional login
from src.utils.auth_manager import AuthManager

logger = logging.getLogger('robot_tool.auto_locator')

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

def get_element_screenshot(driver: webdriver.Chrome, element: WebElement) -> Optional[str]:
    """
    Capture a screenshot of a specific element and return as base64.
    
    Args:
        driver: WebDriver instance
        element: Element to capture
        
    Returns:
        Base64 encoded screenshot or None if failed
    """
    try:
        # Take a screenshot of the entire page
        screenshot = driver.get_screenshot_as_base64()
        
        # Get element's location and size
        location = element.location
        size = element.size
        
        return screenshot
    except Exception as e:
        logger.warning(f"Element screenshot failed: {e}")
        return None

# -----------------------------------------------------------------------------
# Locator Generation Functions
# -----------------------------------------------------------------------------

def generate_id_locator(element: WebElement) -> Optional[str]:
    """Generate an ID-based locator if the element has an ID."""
    element_id = element.get_attribute("id")
    if element_id and element_id.strip():
        return f"id={element_id}"
    return None

def generate_name_locator(element: WebElement) -> Optional[str]:
    """Generate a name-based locator if the element has a name."""
    element_name = element.get_attribute("name")
    if element_name and element_name.strip():
        return f"name={element_name}"
    return None

def generate_class_locator(element: WebElement) -> Optional[str]:
    """Generate a class-based CSS locator if the element has classes."""
    element_class = element.get_attribute("class")
    if element_class and element_class.strip():
        classes = element_class.split()
        if classes:
            # Use the most specific class (usually the longest)
            longest_class = max(classes, key=len)
            return f"css=.{longest_class}"
    return None

def generate_css_locator(element: WebElement) -> List[str]:
    """Generate multiple CSS-based locators."""
    locators = []
    tag_name = element.tag_name
    
    # Add tag-based locator if useful
    if tag_name not in ('div', 'span'):
        locators.append(f"css={tag_name}")
    
    # Try with attributes
    for attr in ["type", "role", "aria-label", "placeholder", "title", "data-testid", "data-cy"]:
        value = element.get_attribute(attr)
        if value and value.strip():
            locators.append(f"css={tag_name}[{attr}='{value}']")
    
    return locators

def generate_text_locator(element: WebElement) -> Optional[str]:
    """Generate a text-based XPath locator if the element has text."""
    text = element.text
    if text and text.strip():
        # If text is too long, use only the first few words
        if len(text) > 50:
            words = text.split()
            text = " ".join(words[:5]) + "..."
            return f"xpath=//*[contains(text(), '{text}')]"
        else:
            return f"xpath=//*[text()='{text}']"
    return None

def generate_attribute_xpath_locators(element: WebElement) -> List[str]:
    """Generate XPath locators based on various attributes."""
    locators = []
    tag_name = element.tag_name
    
    # Try with common attributes
    for attr in ["id", "name", "class", "type", "role", "aria-label", "title", "placeholder"]:
        value = element.get_attribute(attr)
        if value and value.strip():
            if attr == "class":
                # For class attribute, we need to handle multiple classes
                classes = value.split()
                if classes:
                    specific_class = max(classes, key=len)
                    locators.append(f"xpath=//{tag_name}[contains(@class, '{specific_class}')]")
            else:
                locators.append(f"xpath=//{tag_name}[@{attr}='{value}']")
    
    return locators

def generate_relative_locators(element: WebElement, driver: webdriver.Chrome) -> List[str]:
    """Generate locators based on element's position relative to other elements."""
    locators = []
    
    try:
        # Try to find nearby labels
        script = """
        function findNearbyLabels(element, maxDistance = 100) {
            const labels = document.querySelectorAll('label');
            const rect = element.getBoundingClientRect();
            const result = [];
            
            for (const label of labels) {
                const labelRect = label.getBoundingClientRect();
                
                // Calculate distance between centers
                const dx = (rect.left + rect.width/2) - (labelRect.left + labelRect.width/2);
                const dy = (rect.top + rect.height/2) - (labelRect.top + labelRect.height/2);
                const distance = Math.sqrt(dx*dx + dy*dy);
                
                if (distance < maxDistance) {
                    result.push({
                        text: label.textContent.trim(),
                        distance: distance,
                        forId: label.getAttribute('for')
                    });
                }
            }
            
            return result.sort((a, b) => a.distance - b.distance);
        }
        
        return findNearbyLabels(arguments[0]);
        """
        
        nearby_labels = driver.execute_script(script, element)
        
        if nearby_labels:
            for label_info in nearby_labels[:3]:  # Get top 3 closest labels
                label_text = label_info.get("text", "")
                for_id = label_info.get("forId", "")
                
                if label_text:
                    if for_id:
                        locators.append(f"xpath=//label[contains(text(), '{label_text}')]/@for")
                    locators.append(f"xpath=//label[contains(text(), '{label_text}')]/following::*[1]")
                    locators.append(f"xpath=//*[text()='{label_text}']/following::*[1]")
    except Exception as e:
        logger.warning(f"Error generating relative locators: {e}")
    
    return locators

def get_direct_parent_locator(element: WebElement, driver: webdriver.Chrome) -> Optional[str]:
    """Get a locator that includes the parent element if useful."""
    try:
        parent = driver.execute_script("return arguments[0].parentNode;", element)
        if parent:
            parent_id = parent.get_attribute("id")
            tag_name = element.tag_name
            
            if parent_id:
                return f"xpath=//*[@id='{parent_id}']//{tag_name}"
    except Exception as e:
        logger.warning(f"Error getting parent locator: {e}")
        
    return None

def evaluate_locator_quality(driver: webdriver.Chrome, locator: str) -> Dict[str, Any]:
    """
    Evaluate the quality of a locator.
    
    Args:
        driver: WebDriver instance
        locator: The locator to evaluate
        
    Returns:
        Dictionary with quality metrics
    """
    result = {
        "specificity": 0,
        "robustness": 0,
        "readability": 0,
        "unique": False,
        "found": False,
        "matches_count": 0
    }
    
    try:
        # Determine locator type
        locator_type = None
        locator_value = locator
        
        if locator.startswith("id="):
            locator_type = By.ID
            locator_value = locator[3:]
            result["readability"] = 10  # ID locators are highly readable
            result["robustness"] = 8    # Usually robust but can change
        elif locator.startswith("name="):
            locator_type = By.NAME
            locator_value = locator[5:]
            result["readability"] = 9
            result["robustness"] = 7
        elif locator.startswith("css="):
            locator_type = By.CSS_SELECTOR
            locator_value = locator[4:]
            result["readability"] = 7
            # Robustness depends on complexity
            result["robustness"] = 10 - min(8, locator_value.count(" ") + locator_value.count(">") * 2)
        elif locator.startswith("xpath="):
            locator_type = By.XPATH
            locator_value = locator[6:]
            # XPath readability is lower
            result["readability"] = 5
            # Complex XPaths are less robust
            result["robustness"] = 10 - min(8, locator_value.count("/") + locator_value.count("contains") * 2)
        else:
            # Default to XPath
            locator_type = By.XPATH
            locator_value = locator
            result["readability"] = 5
            result["robustness"] = 6

        # Check if locator finds elements
        elements = driver.find_elements(locator_type, locator_value)
        result["matches_count"] = len(elements)
        result["found"] = len(elements) > 0
        result["unique"] = len(elements) == 1
        
        # Adjust specificity based on match count
        if len(elements) == 1:
            result["specificity"] = 10
        elif len(elements) > 1 and len(elements) <= 3:
            result["specificity"] = 7
        elif len(elements) > 3 and len(elements) <= 10:
            result["specificity"] = 4
        else:
            result["specificity"] = 1
            
    except Exception as e:
        logger.warning(f"Error evaluating locator quality: {e}")
        
    return result

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def find_all_locators(
    url: str, 
    element_description: str = None, 
    wait_time: int = 10,
    need_login: bool = False,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    username_locator: Optional[str] = None,
    password_locator: Optional[str] = None,
    submit_locator: Optional[str] = None,
    success_indicator: Optional[str] = None
) -> Dict[str, Any]:
    """
    Find all possible locators for elements on a web page.
    
    Args:
        url: URL of the web page to analyze
        element_description: Optional description of element to find specific locators for
        wait_time: Time to wait for page to load in seconds
        need_login: Whether login is required before locating elements
        login_url: URL of the login page if different from main URL
        username: Username for login
        password: Password for login
        username_locator: Locator for username field
        password_locator: Locator for password field
        submit_locator: Locator for submit button
        success_indicator: Optional element to verify successful login
        
    Returns:
        Dictionary with all detected elements and their locators
    """
    result = {
        "url": url,
        "status": "success",
        "elements": [],
        "locators": {},
        "element_screenshot": None,
        "page_screenshot": None,
        "error": None,
        "login_status": None
    }
    
    try:
        # Handle login if needed
        if need_login:
            # Check if already authenticated
            if not AuthManager.is_authenticated(url):
                if not all([username, password, username_locator, password_locator, submit_locator]):
                    result["status"] = "error"
                    result["error"] = "Login requested but missing required login parameters"
                    return result
                    
                # Perform login
                login_result = AuthManager.login(
                    login_url or url,
                    username,
                    password,
                    username_locator,
                    password_locator,
                    submit_locator,
                    success_indicator,
                    wait_time
                )
                
                result["login_status"] = login_result
                
                if not login_result["success"]:
                    result["status"] = "error"
                    result["error"] = f"Login failed: {login_result.get('message', 'Unknown error')}"
                    return result
            else:
                result["login_status"] = {"success": True, "message": "Already authenticated"}
        
        # Get the WebDriver instance from the manager
        driver = BrowserManager.get_driver()
        
        # Navigate to URL
        current_url = driver.current_url
        if current_url != url:
            logger.info(f"Navigating to URL: {url}")
            driver.set_page_load_timeout(wait_time * 2)
            driver.get(url)
            
            # Wait for body element to ensure page is loaded
            try:
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                logger.warning(f"Timeout waiting for page body at {url}")
        
        # Take a screenshot of the page
        try:
            result["page_screenshot"] = driver.get_screenshot_as_base64()
        except Exception as e:
            logger.warning(f"Failed to take page screenshot: {e}")
            
        # Find specific element(s) if description is provided
        target_elements = []
        
        if element_description:
            # Use JS to find elements matching the description
            js_script = """
            function findElementsByDescription(description) {
                description = description.toLowerCase();
                const allElements = document.querySelectorAll('button, a, input, select, textarea, [role="button"], [role="link"], [role="checkbox"], [role="radio"]');
                const matches = [];
                
                for (const element of allElements) {
                    // Skip hidden elements
                    if (element.offsetParent === null && !['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(element.tagName)) {
                        continue;
                    }
                    
                    // Get element text and attributes
                    const text = element.textContent.toLowerCase();
                    const placeholder = element.getAttribute('placeholder')?.toLowerCase() || '';
                    const value = element.getAttribute('value')?.toLowerCase() || '';
                    const ariaLabel = element.getAttribute('aria-label')?.toLowerCase() || '';
                    const title = element.getAttribute('title')?.toLowerCase() || '';
                    const alt = element.getAttribute('alt')?.toLowerCase() || '';
                    
                    // Check if description matches any of these
                    if (text.includes(description) || 
                        placeholder.includes(description) || 
                        value.includes(description) ||
                        ariaLabel.includes(description) ||
                        title.includes(description) ||
                        alt.includes(description)) {
                        matches.push(element);
                    }
                }
                
                return matches;
            }
            
            return findElementsByDescription(arguments[0]);
            """
            
            matched_elements = driver.execute_script(js_script, element_description.lower())
            target_elements = matched_elements
            
            # If no elements found, try finding all interactive elements
            if not target_elements:
                logger.info(f"No elements found with description: {element_description}. Getting all interactive elements.")
                target_elements = []
        
        # If no specific description or no matches found, get all interactive elements
        if not target_elements:
            # Get all interactive elements
            interactive_elements = driver.find_elements(By.CSS_SELECTOR, 
                "a, button, input, select, textarea, [role='button'], [role='link'], [role='checkbox'], [role='radio'], [tabindex]")
            
            # Filter out hidden elements
            target_elements = []
            for element in interactive_elements:
                try:
                    if element.is_displayed():
                        target_elements.append(element)
                except:
                    pass
        
        # Process each element to find all possible locators
        element_results = []
        
        for i, element in enumerate(target_elements[:30]):  # Limit to 30 elements to avoid overwhelming response
            try:
                locators = {}
                
                # Get element info
                tag_name = element.tag_name
                text = element.text.strip()
                attributes = {}
                
                for attr in ["id", "name", "class", "type", "role", "aria-label", "placeholder", "title"]:
                    value = element.get_attribute(attr)
                    if value:
                        attributes[attr] = value
                
                # Generate different types of locators
                id_locator = generate_id_locator(element)
                if id_locator:
                    locators["id"] = id_locator
                
                name_locator = generate_name_locator(element)
                if name_locator:
                    locators["name"] = name_locator
                
                class_locator = generate_class_locator(element)
                if class_locator:
                    locators["class"] = class_locator
                
                css_locators = generate_css_locator(element)
                if css_locators:
                    locators["css"] = css_locators
                
                text_locator = generate_text_locator(element)
                if text_locator:
                    locators["text"] = text_locator
                
                xpath_locators = generate_attribute_xpath_locators(element)
                if xpath_locators:
                    locators["xpath"] = xpath_locators
                
                relative_locators = generate_relative_locators(element, driver)
                if relative_locators:
                    locators["relative"] = relative_locators
                
                parent_locator = get_direct_parent_locator(element, driver)
                if parent_locator:
                    locators["parent"] = parent_locator
                
                # Evaluate each locator
                ranked_locators = []
                for locator_type, locs in locators.items():
                    if isinstance(locs, list):
                        for loc in locs:
                            quality = evaluate_locator_quality(driver, loc)
                            ranked_locators.append({
                                "locator": loc,
                                "type": locator_type,
                                "quality": quality
                            })
                    else:
                        quality = evaluate_locator_quality(driver, locs)
                        ranked_locators.append({
                            "locator": locs,
                            "type": locator_type,
                            "quality": quality
                        })
                
                # Sort locators by quality score (unique, specific, robust, readable)
                def locator_score(loc):
                    q = loc["quality"]
                    unique_bonus = 10 if q["unique"] else 0
                    return unique_bonus + q["specificity"] + q["robustness"] + q["readability"]
                
                ranked_locators.sort(key=locator_score, reverse=True)
                
                # Get screenshot of the element if possible
                screenshot = get_element_screenshot(driver, element)
                
                # Add element to results
                element_results.append({
                    "element_index": i,
                    "tag_name": tag_name,
                    "text": text,
                    "attributes": attributes,
                    "locators": ranked_locators,
                    "recommended_locator": ranked_locators[0]["locator"] if ranked_locators else None,
                    "screenshot": screenshot
                })
                
            except Exception as e:
                logger.warning(f"Error processing element {i}: {e}")
                continue
        
        result["elements"] = element_results
        result["status"] = "success"
        result["element_count"] = len(element_results)
        
        return result
    except Exception as e:
        logger.error(f"Error finding locators: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the auto locator tool with the MCP server."""
    
    @mcp.tool()
    async def robot_find_all_locators(
        url: str,
        element_description: str = None,
        wait_time: int = 10,
        need_login: bool = False,
        login_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        username_locator: Optional[str] = None,
        password_locator: Optional[str] = None,
        submit_locator: Optional[str] = None,
        success_indicator: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find all possible locators for elements on a web page.
        
        This tool automatically detects elements on a web page and generates
        multiple locator strategies for each element. It can be used to identify
        the best ways to locate elements for automation scripts.
        
        If login is required, the tool can handle authentication through the
        shared AuthManager to maintain session state across tools.
        
        Args:
            url: URL of the web page to analyze
            element_description: Optional description to find specific elements
            wait_time: Time to wait for page to load in seconds
            need_login: Whether login is required before locating elements
            login_url: URL of the login page if different from main URL
            username: Username for login
            password: Password for login
            username_locator: Locator for username field
            password_locator: Locator for password field
            submit_locator: Locator for submit button
            success_indicator: Optional element to verify successful login
            
        Returns:
            Dictionary with all detected elements and their locators
        """
        logger.info(f"Finding all locators for URL: {url}")
        logger.info(f"Need login: {need_login}")
        
        return find_all_locators(
            url, 
            element_description, 
            wait_time,
            need_login,
            login_url,
            username,
            password,
            username_locator,
            password_locator,
            submit_locator,
            success_indicator
        ) 