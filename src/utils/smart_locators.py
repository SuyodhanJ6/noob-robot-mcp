#!/usr/bin/env python
"""
Smart Locator Utilities - Enhanced element location strategies
Addresses the challenges with dynamic elements, element relationships, and selector stability
"""

import logging
import time
import re
from typing import List, Dict, Any, Optional, Tuple, Set, Union
from selenium import webdriver
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
from selenium.webdriver.remote.webelement import WebElement

# Setup logging
logger = logging.getLogger('smart_locators')

class SmartLocator:
    """
    Smart locator class for finding stable, reliable element locators
    Provides enhanced locator strategies and validation
    """
    
    # Map of locator types to Selenium By types
    LOCATOR_TYPES = {
        "id": By.ID,
        "name": By.NAME,
        "xpath": By.XPATH,
        "css": By.CSS_SELECTOR,
        "class": By.CLASS_NAME,
        "tag": By.TAG_NAME,
        "link": By.LINK_TEXT,
        "partial": By.PARTIAL_LINK_TEXT
    }
    
    @staticmethod
    def parse_locator(locator: str) -> Tuple[str, str]:
        """
        Parse a locator string into its type and value.
        
        Args:
            locator: Locator string (e.g., "xpath=//button", "id=submit")
            
        Returns:
            Tuple of (locator_type, locator_value)
        """
        # Default to XPath if no prefix is given
        if "=" not in locator:
            return By.XPATH, locator
        
        prefix, value = locator.split("=", 1)
        prefix = prefix.lower().strip()
        
        if prefix == "id":
            return By.ID, value
        elif prefix == "name":
            return By.NAME, value
        elif prefix == "class":
            return By.CLASS_NAME, value
        elif prefix == "tag":
            return By.TAG_NAME, value
        elif prefix == "link":
            return By.LINK_TEXT, value
        elif prefix == "partiallink":
            return By.PARTIAL_LINK_TEXT, value
        elif prefix == "css":
            return By.CSS_SELECTOR, value
        elif prefix == "xpath":
            return By.XPATH, value
        else:
            # Default to XPath for unknown prefixes
            return By.XPATH, locator
    
    @classmethod
    def find_element(cls, driver: webdriver.Chrome, locator: str, 
                     timeout: int = 10, ensure_interactable: bool = False) -> Optional[WebElement]:
        """
        Find an element with enhanced waiting strategies and validation
        
        Args:
            driver: WebDriver instance
            locator: Element locator
            timeout: Timeout in seconds
            ensure_interactable: Whether to ensure element is interactable
            
        Returns:
            WebElement if found and valid, None otherwise
        """
        by_type, by_value = cls.parse_locator(locator)
        
        try:
            if ensure_interactable:
                element = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((by_type, by_value))
                )
            else:
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by_type, by_value))
                )
                
            # Additional validation
            if not element.is_displayed():
                logger.warning(f"Element found but not displayed: {locator}")
                return None
                
            return element
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning(f"Element not found: {locator}, error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error finding element {locator}: {str(e)}")
            return None
    
    @classmethod
    def validate_element_state(cls, element: WebElement) -> Dict[str, bool]:
        """
        Validate the state of an element to determine if it can be interacted with
        
        Args:
            element: WebElement to validate
            
        Returns:
            Dictionary with element state information
        """
        state = {
            "exists": True,
            "displayed": False,
            "enabled": False,
            "clickable": False
        }
        
        try:
            state["displayed"] = element.is_displayed()
            state["enabled"] = element.is_enabled()
            
            # Check if element has dimensions indicating it's rendered
            size = element.size
            state["clickable"] = state["displayed"] and state["enabled"] and size["width"] > 0 and size["height"] > 0
            
        except StaleElementReferenceException:
            state["exists"] = False
        except Exception as e:
            logger.error(f"Error validating element state: {str(e)}")
            
        return state

    @classmethod
    def generate_smart_xpath(cls, element: WebElement, driver: webdriver.Chrome) -> List[str]:
        """
        Generate smart XPath locators that are more resilient to changes
        
        Args:
            element: WebElement to generate XPath for
            driver: WebDriver instance for context
            
        Returns:
            List of XPath locators in order of reliability
        """
        locators = []
        
        try:
            # Get element attributes
            element_id = element.get_attribute("id")
            element_class = element.get_attribute("class")
            element_name = element.get_attribute("name")
            element_type = element.get_attribute("type")
            element_text = element.text.strip() if element.text else ""
            element_tag = element.tag_name
            
            # 1. ID-based XPath (most reliable if ID exists)
            if element_id and element_id.strip():
                locators.append(f"xpath=//{element_tag}[@id='{element_id}']")
            
            # 2. Data attribute locators (often used for testing)
            for attr in ["data-testid", "data-cy", "data-test", "data-automation"]:
                attr_value = element.get_attribute(attr)
                if attr_value and attr_value.strip():
                    locators.append(f"xpath=//*[@{attr}='{attr_value}']")
            
            # 3. Name attribute (common for form fields)
            if element_name and element_name.strip():
                locators.append(f"xpath=//{element_tag}[@name='{element_name}']")
            
            # 4. Text-based locators for elements with text
            if element_text:
                # Exact text match
                locators.append(f"xpath=//{element_tag}[text()='{element_text}']")
                # Partial text match (more resilient to small changes)
                if len(element_text) > 10:
                    # Use the first few words for partial matching
                    partial_text = " ".join(element_text.split()[:3])
                    locators.append(f"xpath=//{element_tag}[contains(text(),'{partial_text}')]")
            
            # 5. Label-based locators for form fields
            if element_tag in ["input", "select", "textarea"] and element_id:
                # Find label associated by for attribute
                try:
                    label = driver.find_element(By.XPATH, f"//label[@for='{element_id}']")
                    label_text = label.text.strip()
                    if label_text:
                        locators.append(f"xpath=//label[text()='{label_text}']/following::*[1]")
                        locators.append(f"xpath=//label[contains(text(),'{label_text}')]/following::*[1]")
                except NoSuchElementException:
                    pass
            
            # 6. Contextual locators based on parent elements
            parent = cls.get_parent_with_identifier(element, driver)
            if parent:
                parent_id = parent.get_attribute("id")
                parent_class = parent.get_attribute("class")
                
                if parent_id:
                    locators.append(f"xpath=//*[@id='{parent_id}']//{element_tag}")
                    
                    # Add attributes to make more specific
                    if element_class:
                        class_names = element_class.split()
                        if class_names:
                            locators.append(f"xpath=//*[@id='{parent_id}']//{element_tag}[@class='{element_class}']")
                    
                    if element_type:
                        locators.append(f"xpath=//*[@id='{parent_id}']//{element_tag}[@type='{element_type}']")
            
            # 7. Position-based locators (last resort)
            if parent and parent_id:
                # Find position of element among siblings
                siblings = driver.find_elements(By.XPATH, f"//*[@id='{parent_id}']//{element_tag}")
                if siblings:
                    for i, sibling in enumerate(siblings):
                        try:
                            if sibling.id == element.id:
                                locators.append(f"xpath=//*[@id='{parent_id}']//{element_tag}[{i+1}]")
                                break
                        except:
                            pass
            
        except Exception as e:
            logger.error(f"Error generating smart XPath: {str(e)}")
        
        return locators
    
    @classmethod
    def get_parent_with_identifier(cls, element: WebElement, driver: webdriver.Chrome) -> Optional[WebElement]:
        """
        Find a parent element that has an identifier (id, unique class)
        
        Args:
            element: WebElement to find parent for
            driver: WebDriver instance
            
        Returns:
            Parent element with identifier or None
        """
        try:
            # Try to get element's javascript path
            js_path = driver.execute_script("""
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
            """, element)
            
            if js_path:
                # Get parent path by removing the last segment
                parent_path = "/".join(js_path.split("/")[:-1])
                if parent_path:
                    return driver.find_element(By.XPATH, parent_path)
        except:
            pass
            
        # Fallback: try to find parent with id or meaningful class
        try:
            parent = driver.execute_script("return arguments[0].parentNode;", element)
            if parent:
                parent_id = parent.get_attribute("id")
                if parent_id and parent_id.strip():
                    return parent
                    
                parent_class = parent.get_attribute("class")
                if parent_class and parent_class.strip() and " " not in parent_class:
                    return parent
                    
            # Try grandparent if parent doesn't have identifier
            grandparent = driver.execute_script("return arguments[0].parentNode.parentNode;", element)
            if grandparent:
                gp_id = grandparent.get_attribute("id")
                if gp_id and gp_id.strip():
                    return grandparent
        except:
            pass
            
        return None
        
    @classmethod
    def find_best_locator(cls, driver: webdriver.Chrome, element: WebElement) -> str:
        """
        Find the best, most stable locator for an element
        
        Args:
            driver: WebDriver instance
            element: WebElement to find locator for
            
        Returns:
            Best locator string
        """
        # Generate candidate locators
        locators = []
        
        # Check for ID (most reliable)
        element_id = element.get_attribute("id")
        if element_id and element_id.strip():
            locators.append(f"id={element_id}")
        
        # Check for data test attributes
        for attr in ["data-testid", "data-cy", "data-test", "data-automation"]:
            attr_value = element.get_attribute(attr)
            if attr_value and attr_value.strip():
                locators.append(f"css=[{attr}='{attr_value}']")
        
        # Check for name
        element_name = element.get_attribute("name")
        if element_name and element_name.strip():
            locators.append(f"name={element_name}")
        
        # Get smart XPath locators
        xpath_locators = cls.generate_smart_xpath(element, driver)
        for xpath in xpath_locators:
            locators.append(xpath)
        
        # Test each locator for uniqueness and return the first good one
        for locator in locators:
            uniqueness = cls.test_locator_uniqueness(driver, locator)
            if uniqueness["count"] == 1:
                return locator
        
        # If no unique locator found, return the first one with a warning
        if locators:
            logger.warning(f"No unique locator found for element, using: {locators[0]}")
            return locators[0]
        
        # Last resort - use full XPath
        return f"xpath={cls.get_full_xpath(driver, element)}"
    
    @classmethod
    def test_locator_uniqueness(cls, driver: webdriver.Chrome, locator: str) -> Dict[str, Any]:
        """
        Test if a locator uniquely identifies an element
        
        Args:
            driver: WebDriver instance
            locator: Locator to test
            
        Returns:
            Dict with test results
        """
        by_type, by_value = cls.parse_locator(locator)
        
        result = {
            "locator": locator,
            "count": 0,
            "unique": False
        }
        
        try:
            elements = driver.find_elements(by_type, by_value)
            result["count"] = len(elements)
            result["unique"] = len(elements) == 1
        except Exception as e:
            logger.error(f"Error testing locator uniqueness: {str(e)}")
        
        return result
    
    @classmethod
    def get_full_xpath(cls, driver: webdriver.Chrome, element: WebElement) -> str:
        """
        Get the full XPath for an element
        
        Args:
            driver: WebDriver instance
            element: WebElement
            
        Returns:
            Full XPath string
        """
        try:
            return driver.execute_script("""
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
            """, element)
        except:
            # Fallback
            return "//body"

class SmartWait:
    """
    Smart waiting strategies that adapt to page conditions
    """
    
    @staticmethod
    def wait_for_element_with_backoff(driver: webdriver.Chrome, locator: str, 
                                      max_timeout: int = 30, 
                                      initial_interval: float = 0.5,
                                      max_interval: float = 5.0) -> Optional[WebElement]:
        """
        Wait for an element with exponential backoff
        
        Args:
            driver: WebDriver instance
            locator: Element locator
            max_timeout: Maximum timeout in seconds
            initial_interval: Initial polling interval
            max_interval: Maximum polling interval
            
        Returns:
            WebElement if found, None otherwise
        """
        by_type, by_value = SmartLocator.parse_locator(locator)
        
        start_time = time.time()
        interval = initial_interval
        
        while time.time() - start_time < max_timeout:
            try:
                element = driver.find_element(by_type, by_value)
                if element.is_displayed():
                    return element
            except (NoSuchElementException, StaleElementReferenceException):
                pass
            
            # Sleep with increasing intervals (exponential backoff)
            time.sleep(interval)
            interval = min(interval * 1.5, max_interval)
        
        return None
    
    @staticmethod
    def wait_for_page_load(driver: webdriver.Chrome, timeout: int = 30) -> bool:
        """
        Wait for page to fully load with multiple signals
        
        Args:
            driver: WebDriver instance
            timeout: Timeout in seconds
            
        Returns:
            True if page loaded successfully, False otherwise
        """
        try:
            # Wait for document ready state
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Wait for jQuery (if present)
            jquery_ready = driver.execute_script("""
                return typeof jQuery !== 'undefined' ? jQuery.active === 0 : true;
            """)
            
            if not jquery_ready:
                WebDriverWait(driver, timeout).until(
                    lambda d: d.execute_script("return jQuery.active === 0")
                )
            
            # Wait for Angular (if present)
            angular_ready = driver.execute_script("""
                return typeof angular === 'undefined' || 
                       (typeof angular !== 'undefined' && 
                        angular.element(document).injector() === null) ||
                       (typeof angular !== 'undefined' && 
                        !angular.element(document).injector().has('$http'));
            """)
            
            if not angular_ready:
                WebDriverWait(driver, timeout).until(
                    lambda d: d.execute_script("""
                        return (typeof angular === 'undefined' || 
                               angular.element(document).injector().get('$http').pendingRequests.length === 0);
                    """)
                )
                
            return True
        except:
            return False

class ElementInteractionValidator:
    """
    Validates element interactions before they happen to prevent errors
    """
    
    @staticmethod
    def is_clickable(element: WebElement) -> Dict[str, Any]:
        """
        Check if an element is truly clickable
        
        Args:
            element: WebElement to check
            
        Returns:
            Dict with clickability status and details
        """
        result = {
            "clickable": False,
            "visible": False,
            "enabled": False,
            "in_viewport": False,
            "covered": False,
            "reason": None
        }
        
        try:
            result["visible"] = element.is_displayed()
            result["enabled"] = element.is_enabled()
            
            if not result["visible"]:
                result["reason"] = "Element is not visible"
                return result
                
            if not result["enabled"]:
                result["reason"] = "Element is disabled"
                return result
            
            # Check if element has size
            size = element.size
            if size["width"] == 0 or size["height"] == 0:
                result["reason"] = "Element has zero size"
                return result
            
            # Check if element is in viewport
            in_viewport = element.parent.execute_script("""
                var elem = arguments[0];
                var rect = elem.getBoundingClientRect();
                return (
                    rect.top >= 0 &&
                    rect.left >= 0 &&
                    rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                    rect.right <= (window.innerWidth || document.documentElement.clientWidth)
                );
            """, element)
            
            result["in_viewport"] = in_viewport
            
            if not in_viewport:
                result["reason"] = "Element is outside viewport"
                return result
            
            # Check if element is covered by another element
            covered = element.parent.execute_script("""
                var elem = arguments[0];
                var rect = elem.getBoundingClientRect();
                var cx = rect.left + rect.width / 2;
                var cy = rect.top + rect.height / 2;
                var element = document.elementFromPoint(cx, cy);
                return element !== elem && !elem.contains(element);
            """, element)
            
            result["covered"] = covered
            
            if covered:
                result["reason"] = "Element is covered by another element"
                return result
            
            # If we got here, element is clickable
            result["clickable"] = True
            
        except Exception as e:
            result["reason"] = f"Error checking clickability: {str(e)}"
            
        return result
    
    @staticmethod
    def can_input_text(element: WebElement) -> Dict[str, Any]:
        """
        Check if an element can receive text input
        
        Args:
            element: WebElement to check
            
        Returns:
            Dict with input status and details
        """
        result = {
            "can_input": False,
            "visible": False,
            "enabled": False,
            "editable": False,
            "reason": None
        }
        
        try:
            result["visible"] = element.is_displayed()
            result["enabled"] = element.is_enabled()
            
            if not result["visible"]:
                result["reason"] = "Element is not visible"
                return result
                
            if not result["enabled"]:
                result["reason"] = "Element is disabled"
                return result
            
            # Check if element is of input type
            tag_name = element.tag_name.lower()
            if tag_name not in ["input", "textarea"]:
                result["reason"] = f"Element is not an input field (tag: {tag_name})"
                return result
            
            # For input elements, check type
            if tag_name == "input":
                input_type = element.get_attribute("type")
                if input_type in ["submit", "button", "image", "reset", "hidden", "checkbox", "radio"]:
                    result["reason"] = f"Input is of type {input_type}, which doesn't accept text"
                    return result
            
            # Check if element is readonly
            readonly = element.get_attribute("readonly")
            if readonly and readonly.lower() in ["true", "readonly"]:
                result["reason"] = "Element is read-only"
                return result
            
            # If we got here, element is editable
            result["editable"] = True
            result["can_input"] = True
            
        except Exception as e:
            result["reason"] = f"Error checking input ability: {str(e)}"
            
        return result 