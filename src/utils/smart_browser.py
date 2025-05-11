#!/usr/bin/env python
"""
Smart Browser Utilities - Enhanced browser interaction with improved element handling
Provides robust interaction with web elements and recovery strategies
"""

import logging
import time
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException, 
    NoSuchElementException,
    StaleElementReferenceException,
    ElementNotInteractableException,
    ElementClickInterceptedException
)
from selenium.webdriver.remote.webelement import WebElement

# Import the smart locator utilities
from src.utils.smart_locators import Sma

















rtLocator, SmartWait, ElementInteractionValidator

# Setup logging
logger = logging.getLogger('smart_browser')

class SmartBrowserInteraction:
    """
    Enhanced browser interaction with smart element handling and recovery strategies
    """
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize with a WebDriver instance
        
        Args:
            driver: WebDriver instance
        """
        self.driver = driver
        
    def navigate(self, url: str, wait_for_page_load: bool = True, timeout: int = 30) -> Dict[str, Any]:
        """
        Navigate to a URL with enhanced page load waiting
        
        Args:
            url: URL to navigate to
            wait_for_page_load: Whether to wait for full page load
            timeout: Timeout in seconds
            
        Returns:
            Dict with navigation result
        """
        result = {
            "success": False,
            "url": url,
            "error": None,
            "page_loaded": False
        }
        
        try:
            logger.info(f"Navigating to URL: {url}")
            self.driver.get(url)
            
            if wait_for_page_load:
                result["page_loaded"] = SmartWait.wait_for_page_load(self.driver, timeout)
            else:
                # Simple wait for basic page load
                WebDriverWait(self.driver, timeout).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                result["page_loaded"] = True
                
            result["success"] = True
            result["final_url"] = self.driver.current_url
            
        except Exception as e:
            logger.error(f"Navigation error: {str(e)}")
            result["error"] = str(e)
            
        return result
    
    def click_element(self, locator: str, timeout: int = 10, 
                      retry_count: int = 3, scroll_into_view: bool = True,
                      take_screenshot: bool = False) -> Dict[str, Any]:
        """
        Click an element with enhanced validation and recovery strategies
        
        Args:
            locator: Element locator
            timeout: Timeout in seconds
            retry_count: Number of retries if click fails
            scroll_into_view: Whether to scroll element into view before clicking
            take_screenshot: Whether to take a screenshot on failure
            
        Returns:
            Dict with click operation result
        """
        result = {
            "success": False,
            "error": None,
            "element_found": False,
            "retry_count": 0,
            "clickable": False,
            "screenshot": None
        }
        
        by_type, by_value = SmartLocator.parse_locator(locator)
        
        for attempt in range(retry_count):
            result["retry_count"] = attempt
            
            try:
                # Wait for element using exponential backoff
                element = SmartWait.wait_for_element_with_backoff(
                    self.driver, locator, max_timeout=timeout
                )
                
                if not element:
                    if attempt == retry_count - 1:  # Last attempt
                        result["error"] = f"Element not found: {locator}"
                        
                        if take_screenshot:
                            result["screenshot"] = self._take_screenshot()
                            
                        return result
                    continue  # Try again
                
                result["element_found"] = True
                
                # Validate if element is truly clickable
                clickable_state = ElementInteractionValidator.is_clickable(element)
                result["clickable"] = clickable_state["clickable"]
                
                if not clickable_state["clickable"]:
                    logger.warning(f"Element not clickable: {clickable_state['reason']}")
                    
                    # Try to recover based on the issue
                    if not clickable_state["in_viewport"] and scroll_into_view:
                        # Scroll element into view
                        self._scroll_to_element(element)
                        time.sleep(0.5)  # Allow time for scrolling animations
                    
                    if clickable_state["covered"]:
                        # Try to use JavaScript click as fallback
                        logger.info("Element is covered, trying JavaScript click")
                        self._js_click(element)
                        result["success"] = True
                        return result
                        
                    if attempt < retry_count - 1:
                        continue  # Try again
                    
                    result["error"] = f"Element not clickable: {clickable_state['reason']}"
                    
                    if take_screenshot:
                        result["screenshot"] = self._take_screenshot()
                        
                    return result
                
                # Try different click strategies
                click_success = False
                
                # 1. Standard Selenium click
                try:
                    element.click()
                    click_success = True
                except (ElementClickInterceptedException, ElementNotInteractableException):
                    # 2. Try ActionChains click
                    try:
                        ActionChains(self.driver).move_to_element(element).click().perform()
                        click_success = True
                    except:
                        # 3. Try JavaScript click
                        self._js_click(element)
                        click_success = True
                
                # If any click strategy succeeded
                if click_success:
                    result["success"] = True
                    return result
                
            except StaleElementReferenceException:
                # Element became stale, retry
                logger.warning("StaleElementReferenceException, retrying...")
                time.sleep(0.5)
                continue
                
            except Exception as e:
                logger.error(f"Error clicking element: {str(e)}")
                result["error"] = str(e)
                
                if take_screenshot:
                    result["screenshot"] = self._take_screenshot()
                    
                if attempt < retry_count - 1:
                    time.sleep(1)  # Wait before retrying
                    continue
                    
                return result
        
        return result
    
    def input_text(self, locator: str, text: str, timeout: int = 10,
                   clear_first: bool = True, retry_count: int = 3,
                   press_enter: bool = False) -> Dict[str, Any]:
        """
        Input text into an element with validation and retry
        
        Args:
            locator: Element locator
            text: Text to input
            timeout: Timeout in seconds
            clear_first: Whether to clear the field first
            retry_count: Number of retries if input fails
            press_enter: Whether to press Enter after input
            
        Returns:
            Dict with input operation result
        """
        result = {
            "success": False,
            "error": None,
            "element_found": False,
            "retry_count": 0,
            "can_input": False
        }
        
        by_type, by_value = SmartLocator.parse_locator(locator)
        
        for attempt in range(retry_count):
            result["retry_count"] = attempt
            
            try:
                # Wait for element
                element = SmartLocator.find_element(
                    self.driver, locator, timeout, ensure_interactable=True
                )
                
                if not element:
                    if attempt == retry_count - 1:  # Last attempt
                        result["error"] = f"Element not found: {locator}"
                        return result
                    continue  # Try again
                
                result["element_found"] = True
                
                # Validate if element can receive text input
                input_state = ElementInteractionValidator.can_input_text(element)
                result["can_input"] = input_state["can_input"]
                
                if not input_state["can_input"]:
                    if attempt < retry_count - 1:
                        continue  # Try again
                    
                    result["error"] = f"Element cannot receive text input: {input_state['reason']}"
                    return result
                
                # Scroll element into view
                self._scroll_to_element(element)
                
                # Clear field if requested
                if clear_first:
                    element.clear()
                    # Double-check if cleared
                    if element.get_attribute("value"):
                        # Try JavaScript clear if normal clear didn't work
                        self.driver.execute_script("arguments[0].value = '';", element)
                
                # Input text
                element.send_keys(text)
                
                # Press Enter if requested
                if press_enter:
                    element.send_keys(Keys.RETURN)
                
                # Verify text was entered
                actual_value = element.get_attribute("value")
                if actual_value != text and text not in actual_value:
                    logger.warning(f"Text verification failed. Expected: '{text}', Got: '{actual_value}'")
                    
                    if attempt < retry_count - 1:
                        # Try JavaScript input as fallback
                        self.driver.execute_script(f"arguments[0].value = '{text}';", element)
                        continue
                        
                    result["error"] = "Failed to input text correctly"
                    return result
                
                result["success"] = True
                return result
                
            except StaleElementReferenceException:
                # Element became stale, retry
                logger.warning("StaleElementReferenceException, retrying...")
                time.sleep(0.5)
                continue
                
            except Exception as e:
                logger.error(f"Error inputting text: {str(e)}")
                result["error"] = str(e)
                
                if attempt < retry_count - 1:
                    time.sleep(1)  # Wait before retrying
                    continue
                    
                return result
        
        return result
    
    def select_option(self, locator: str, option_value: Optional[str] = None, 
                      option_text: Optional[str] = None, option_index: Optional[int] = None,
                      timeout: int = 10, retry_count: int = 3) -> Dict[str, Any]:
        """
        Select an option from a dropdown with validation
        
        Args:
            locator: Select element locator
            option_value: Option value to select
            option_text: Option text to select
            option_index: Option index to select
            timeout: Timeout in seconds
            retry_count: Number of retries
            
        Returns:
            Dict with selection result
        """
        result = {
            "success": False,
            "error": None,
            "element_found": False,
            "retry_count": 0,
            "is_select": False,
            "options_found": False
        }
        
        if not any([option_value, option_text, option_index is not None]):
            result["error"] = "Must provide one of: option_value, option_text, or option_index"
            return result
        
        by_type, by_value = SmartLocator.parse_locator(locator)
        
        for attempt in range(retry_count):
            result["retry_count"] = attempt
            
            try:
                # Wait for element
                element = SmartLocator.find_element(
                    self.driver, locator, timeout
                )
                
                if not element:
                    if attempt == retry_count - 1:  # Last attempt
                        result["error"] = f"Select element not found: {locator}"
                        return result
                    continue  # Try again
                
                result["element_found"] = True
                
                # Check if it's a select element
                if element.tag_name.lower() != "select":
                    result["error"] = f"Element is not a select: {element.tag_name}"
                    return result
                
                result["is_select"] = True
                
                # Create Select object
                select = Select(element)
                
                # Get options
                options = select.options
                if not options:
                    result["error"] = "Select element has no options"
                    return result
                
                result["options_found"] = True
                result["option_count"] = len(options)
                
                # Select option based on provided criteria
                if option_value is not None:
                    select.select_by_value(option_value)
                elif option_text is not None:
                    select.select_by_visible_text(option_text)
                elif option_index is not None:
                    select.select_by_index(option_index)
                
                # Verify selection
                selected_option = select.first_selected_option
                selected_text = selected_option.text
                selected_value = selected_option.get_attribute("value")
                
                result["selected_text"] = selected_text
                result["selected_value"] = selected_value
                
                # Verify correct option was selected
                if (option_value is not None and selected_value != option_value) or \
                   (option_text is not None and selected_text != option_text):
                    if attempt < retry_count - 1:
                        continue  # Try again
                        
                    result["error"] = "Failed to select correct option"
                    return result
                
                result["success"] = True
                return result
                
            except StaleElementReferenceException:
                # Element became stale, retry
                logger.warning("StaleElementReferenceException, retrying...")
                time.sleep(0.5)
                continue
                
            except Exception as e:
                logger.error(f"Error selecting option: {str(e)}")
                result["error"] = str(e)
                
                if attempt < retry_count - 1:
                    time.sleep(1)  # Wait before retrying
                    continue
                    
                return result
        
        return result
    
    def wait_for_element(self, locator: str, timeout: int = 10, 
                         check_visibility: bool = True, 
                         check_clickable: bool = False) -> Dict[str, Any]:
        """
        Wait for an element with enhanced conditions
        
        Args:
            locator: Element locator
            timeout: Timeout in seconds
            check_visibility: Whether to check if element is visible
            check_clickable: Whether to check if element is clickable
            
        Returns:
            Dict with wait result
        """
        result = {
            "success": False,
            "error": None,
            "found": False,
            "visible": False,
            "clickable": False
        }
        
        by_type, by_value = SmartLocator.parse_locator(locator)
        
        try:
            start_time = time.time()
            
            # First check if element exists
            try:
                if check_clickable:
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.element_to_be_clickable((by_type, by_value))
                    )
                    result["found"] = True
                    result["visible"] = True
                    result["clickable"] = True
                elif check_visibility:
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.visibility_of_element_located((by_type, by_value))
                    )
                    result["found"] = True
                    result["visible"] = True
                    
                    # Check if also clickable
                    clickable_state = ElementInteractionValidator.is_clickable(element)
                    result["clickable"] = clickable_state["clickable"]
                else:
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((by_type, by_value))
                    )
                    result["found"] = True
                    
                    # Check visibility separately
                    result["visible"] = element.is_displayed()
                    
                    if result["visible"]:
                        # Check if also clickable
                        clickable_state = ElementInteractionValidator.is_clickable(element)
                        result["clickable"] = clickable_state["clickable"]
                
                result["success"] = True
                result["element_tag"] = element.tag_name
                result["wait_time"] = time.time() - start_time
                
            except TimeoutException:
                result["error"] = f"Timeout waiting for element: {locator}"
            
        except Exception as e:
            logger.error(f"Error waiting for element: {str(e)}")
            result["error"] = str(e)
            
        return result
    
    def find_smart_locator(self, description: str, wait_time: int = 10) -> Dict[str, Any]:
        """
        Find the best locator for an element based on a description
        
        Args:
            description: Description of the element to find
            wait_time: Time to wait for page interaction
            
        Returns:
            Dict with locator information
        """
        result = {
            "success": False,
            "locators": [],
            "best_locator": None,
            "error": None
        }
        
        try:
            # Ask user to manually identify the element
            logger.info(f"Please identify the element: {description}")
            logger.info("You have 10 seconds to move mouse to the element")
            
            # Use JavaScript to create a highlighting effect when mouse hovers over elements
            self.driver.execute_script("""
                document.querySelectorAll('*').forEach(el => {
                    el.addEventListener('mouseover', function() {
                        this._originalOutline = this.style.outline;
                        this.style.outline = '2px solid red';
                    });
                    el.addEventListener('mouseout', function() {
                        this.style.outline = this._originalOutline;
                    });
                });
                
                // Store the currently highlighted element
                window._currentElement = null;
                document.addEventListener('mouseover', function(e) {
                    window._currentElement = e.target;
                });
            """)
            
            # Wait for user to identify element
            time.sleep(wait_time)
            
            # Get the element that was hovered
            element = self.driver.execute_script("return window._currentElement;")
            
            if not element:
                result["error"] = "No element was identified"
                return result
            
            # Use our smart locator to get the best locator
            best_locator = SmartLocator.find_best_locator(self.driver, element)
            
            # Get all possible locators
            locators = []
            
            # Get element ID
            element_id = element.get_attribute("id")
            if element_id and element_id.strip():
                locators.append(f"id={element_id}")
            
            # Get element name
            element_name = element.get_attribute("name")
            if element_name and element_name.strip():
                locators.append(f"name={element_name}")
            
            # Get smart XPath locators
            xpath_locators = SmartLocator.generate_smart_xpath(element, self.driver)
            locators.extend(xpath_locators)
            
            # Get element text for identification
            element_text = element.text.strip() if element.text else None
            element_tag = element.tag_name
            
            result["success"] = True
            result["best_locator"] = best_locator
            result["locators"] = locators
            result["element_tag"] = element_tag
            result["element_text"] = element_text
            
        except Exception as e:
            logger.error(f"Error finding smart locator: {str(e)}")
            result["error"] = str(e)
            
        return result
    
    def _take_screenshot(self) -> Optional[str]:
        """
        Take a screenshot and return as base64
        
        Returns:
            Base64 encoded screenshot or None if failed
        """
        try:
            return self.driver.get_screenshot_as_base64()
        except Exception as e:
            logger.error(f"Failed to take screenshot: {str(e)}")
            return None
    
    def _scroll_to_element(self, element: WebElement) -> bool:
        """
        Scroll element into view
        
        Args:
            element: WebElement to scroll to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            return True
        except Exception as e:
            logger.error(f"Error scrolling to element: {str(e)}")
            return False
    
    def _js_click(self, element: WebElement) -> bool:
        """
        Click element using JavaScript
        
        Args:
            element: WebElement to click
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            logger.error(f"JavaScript click failed: {str(e)}")
            return False 