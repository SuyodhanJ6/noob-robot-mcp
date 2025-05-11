#!/usr/bin/env python
"""
MCP Tool: Robot Browser Smart
Enhanced browser automation with smart element location and interaction.
Addresses the challenges identified in the review feedback.
"""

import os
import logging
import json
import time
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

from mcp.server.fastmcp import FastMCP
from selenium.webdriver.remote.webelement import WebElement

# Import shared browser manager
from src.mcp_tools.robot_browser_manager import BrowserManager

# Import our enhanced utilities
from src.utils.smart_locators import SmartLocator, SmartWait, ElementInteractionValidator
from src.utils.smart_browser import SmartBrowserInteraction

# Import auth manager for optional login
from src.utils.auth_manager import AuthManager

logger = logging.getLogger('robot_tool.browser_smart')

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def smart_click(
    locator: str,
    wait_time: int = 10,
    retry_count: int = 3,
    take_screenshot: bool = True,
    url: Optional[str] = None,
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
    Click an element using enhanced locator detection and interaction strategies.
    
    Args:
        locator: Element locator in format "type=value" (e.g., "id=submit")
        wait_time: Time to wait for element in seconds
        retry_count: Number of retry attempts for clicking
        take_screenshot: Whether to take screenshots for debugging
        url: Optional URL to navigate to before clicking
        need_login: Whether login is required before clicking
        login_url: URL of the login page if different from target URL
        username: Username for login
        password: Password for login
        username_locator: Locator for username field
        password_locator: Locator for password field
        submit_locator: Locator for submit button
        success_indicator: Optional element to verify successful login
        
    Returns:
        Dictionary with operation status and details
    """
    result = {
        "status": "success",
        "element": locator,
        "screenshots": {},
        "error": None,
        "login_status": None,
        "click_details": None,
        "alternative_locators": []
    }
    
    try:
        # Handle login if needed and URL is provided
        if need_login and url:
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
        
        # Get browser instance from the manager
        driver = BrowserManager.get_driver()
        
        # Create smart browser interaction instance
        smart_browser = SmartBrowserInteraction(driver)
        
        # Navigate to URL if provided
        if url:
            logger.info(f"Navigating to URL: {url}")
            nav_result = smart_browser.navigate(url, wait_for_page_load=True, timeout=wait_time)
            if not nav_result["success"]:
                result["status"] = "error"
                result["error"] = f"Navigation failed: {nav_result.get('error', 'Unknown error')}"
                return result
        
        # Take screenshot before clicking if requested
        if take_screenshot:
            result["screenshots"]["before"] = driver.get_screenshot_as_base64()
        
        # Try to find alternative locators for the element
        # This helps with recovery if the original locator fails
        try:
            # First wait for the element to be present
            wait_result = smart_browser.wait_for_element(locator, timeout=wait_time)
            
            if wait_result["found"]:
                # Try to find the element with the given locator
                by_type, by_value = SmartLocator.parse_locator(locator)
                element = driver.find_element(by_type, by_value)
                
                # Generate alternative locators for this element
                alt_locators = SmartLocator.generate_smart_xpath(element, driver)
                result["alternative_locators"] = alt_locators
        except:
            pass
        
        # Perform the click with smart retry and validation
        click_result = smart_browser.click_element(
            locator, 
            timeout=wait_time,
            retry_count=retry_count,
            scroll_into_view=True,
            take_screenshot=take_screenshot
        )
        
        result["click_details"] = click_result
        
        # If original locator failed but we have alternatives, try them
        if not click_result["success"] and result["alternative_locators"]:
            logger.info(f"Original locator failed, trying {len(result['alternative_locators'])} alternatives")
            
            for alt_locator in result["alternative_locators"]:
                logger.info(f"Trying alternative locator: {alt_locator}")
                alt_result = smart_browser.click_element(
                    alt_locator,
                    timeout=wait_time // 2,  # Shorter timeout for alternatives
                    retry_count=1,
                    scroll_into_view=True
                )
                
                if alt_result["success"]:
                    logger.info(f"Alternative locator succeeded: {alt_locator}")
                    result["click_details"] = alt_result
                    result["status"] = "success"
                    result["element"] = alt_locator  # Update to the working locator
                    break
        
        # Update overall status based on click result
        if not click_result["success"] and not result["click_details"]["success"]:
            result["status"] = "error"
            result["error"] = click_result.get("error", "Click operation failed")
        
        # Take screenshot after clicking if requested
        if take_screenshot:
            result["screenshots"]["after"] = driver.get_screenshot_as_base64()
            
    except Exception as e:
        logger.error(f"Error in smart_click: {str(e)}")
        result["status"] = "error"
        result["error"] = str(e)
        
        # Take error screenshot if requested
        if take_screenshot:
            try:
                driver = BrowserManager.get_driver()
                result["screenshots"]["error"] = driver.get_screenshot_as_base64()
            except:
                pass
            
    return result

def smart_input(
    locator: str,
    text: str,
    wait_time: int = 10,
    clear_first: bool = True,
    retry_count: int = 3,
    press_enter: bool = False,
    take_screenshot: bool = True,
    url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Input text into a field using enhanced locator detection and interaction strategies.
    
    Args:
        locator: Element locator in format "type=value" (e.g., "id=email")
        text: Text to input
        wait_time: Time to wait for element in seconds
        clear_first: Whether to clear the field before inputting text
        retry_count: Number of retry attempts for input
        press_enter: Whether to press Enter after input
        take_screenshot: Whether to take screenshots for debugging
        url: Optional URL to navigate to before input
        
    Returns:
        Dictionary with operation status and details
    """
    result = {
        "status": "success",
        "element": locator,
        "text": text,
        "screenshots": {},
        "error": None,
        "input_details": None,
        "alternative_locators": []
    }
    
    try:
        # Get browser instance from the manager
        driver = BrowserManager.get_driver()
        
        # Create smart browser interaction instance
        smart_browser = SmartBrowserInteraction(driver)
        
        # Navigate to URL if provided
        if url:
            logger.info(f"Navigating to URL: {url}")
            nav_result = smart_browser.navigate(url, wait_for_page_load=True, timeout=wait_time)
            if not nav_result["success"]:
                result["status"] = "error"
                result["error"] = f"Navigation failed: {nav_result.get('error', 'Unknown error')}"
                return result
        
        # Take screenshot before input if requested
        if take_screenshot:
            result["screenshots"]["before"] = driver.get_screenshot_as_base64()
        
        # Try to find alternative locators for the element
        try:
            # First wait for the element to be present
            wait_result = smart_browser.wait_for_element(locator, timeout=wait_time)
            
            if wait_result["found"]:
                # Try to find the element with the given locator
                by_type, by_value = SmartLocator.parse_locator(locator)
                element = driver.find_element(by_type, by_value)
                
                # Generate alternative locators for this element
                alt_locators = SmartLocator.generate_smart_xpath(element, driver)
                result["alternative_locators"] = alt_locators
        except:
            pass
        
        # Perform the input with smart retry and validation
        input_result = smart_browser.input_text(
            locator,
            text,
            timeout=wait_time,
            clear_first=clear_first,
            retry_count=retry_count,
            press_enter=press_enter
        )
        
        result["input_details"] = input_result
        
        # If original locator failed but we have alternatives, try them
        if not input_result["success"] and result["alternative_locators"]:
            logger.info(f"Original locator failed, trying {len(result['alternative_locators'])} alternatives")
            
            for alt_locator in result["alternative_locators"]:
                logger.info(f"Trying alternative locator: {alt_locator}")
                alt_result = smart_browser.input_text(
                    alt_locator,
                    text,
                    timeout=wait_time // 2,  # Shorter timeout for alternatives
                    clear_first=clear_first,
                    retry_count=1,
                    press_enter=press_enter
                )
                
                if alt_result["success"]:
                    logger.info(f"Alternative locator succeeded: {alt_locator}")
                    result["input_details"] = alt_result
                    result["status"] = "success"
                    result["element"] = alt_locator  # Update to the working locator
                    break
        
        # Update overall status based on input result
        if not input_result["success"] and not result["input_details"]["success"]:
            result["status"] = "error"
            result["error"] = input_result.get("error", "Input operation failed")
        
        # Take screenshot after input if requested
        if take_screenshot:
            result["screenshots"]["after"] = driver.get_screenshot_as_base64()
            
    except Exception as e:
        logger.error(f"Error in smart_input: {str(e)}")
        result["status"] = "error"
        result["error"] = str(e)
        
        # Take error screenshot if requested
        if take_screenshot:
            try:
                driver = BrowserManager.get_driver()
                result["screenshots"]["error"] = driver.get_screenshot_as_base64()
            except:
                pass
            
    return result

def smart_select(
    locator: str,
    option_text: Optional[str] = None,
    option_value: Optional[str] = None,
    option_index: Optional[int] = None,
    wait_time: int = 10,
    retry_count: int = 3,
    take_screenshot: bool = True,
    url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Select an option from a dropdown using enhanced locator detection and interaction strategies.
    
    Args:
        locator: Element locator in format "type=value" (e.g., "id=country")
        option_text: Text of the option to select
        option_value: Value of the option to select
        option_index: Index of the option to select
        wait_time: Time to wait for element in seconds
        retry_count: Number of retry attempts for selection
        take_screenshot: Whether to take screenshots for debugging
        url: Optional URL to navigate to before selection
        
    Returns:
        Dictionary with operation status and details
    """
    result = {
        "status": "success",
        "element": locator,
        "option": option_text or option_value or f"index: {option_index}",
        "screenshots": {},
        "error": None,
        "select_details": None,
        "alternative_locators": []
    }
    
    try:
        # Get browser instance from the manager
        driver = BrowserManager.get_driver()
        
        # Create smart browser interaction instance
        smart_browser = SmartBrowserInteraction(driver)
        
        # Navigate to URL if provided
        if url:
            logger.info(f"Navigating to URL: {url}")
            nav_result = smart_browser.navigate(url, wait_for_page_load=True, timeout=wait_time)
            if not nav_result["success"]:
                result["status"] = "error"
                result["error"] = f"Navigation failed: {nav_result.get('error', 'Unknown error')}"
                return result
        
        # Take screenshot before selection if requested
        if take_screenshot:
            result["screenshots"]["before"] = driver.get_screenshot_as_base64()
        
        # Try to find alternative locators for the element
        try:
            # First wait for the element to be present
            wait_result = smart_browser.wait_for_element(locator, timeout=wait_time)
            
            if wait_result["found"]:
                # Try to find the element with the given locator
                by_type, by_value = SmartLocator.parse_locator(locator)
                element = driver.find_element(by_type, by_value)
                
                # Generate alternative locators for this element
                alt_locators = SmartLocator.generate_smart_xpath(element, driver)
                result["alternative_locators"] = alt_locators
        except:
            pass
        
        # Perform the selection with smart retry and validation
        select_result = smart_browser.select_option(
            locator,
            option_value=option_value,
            option_text=option_text,
            option_index=option_index,
            timeout=wait_time,
            retry_count=retry_count
        )
        
        result["select_details"] = select_result
        
        # If original locator failed but we have alternatives, try them
        if not select_result["success"] and result["alternative_locators"]:
            logger.info(f"Original locator failed, trying {len(result['alternative_locators'])} alternatives")
            
            for alt_locator in result["alternative_locators"]:
                logger.info(f"Trying alternative locator: {alt_locator}")
                alt_result = smart_browser.select_option(
                    alt_locator,
                    option_value=option_value,
                    option_text=option_text,
                    option_index=option_index,
                    timeout=wait_time // 2,  # Shorter timeout for alternatives
                    retry_count=1
                )
                
                if alt_result["success"]:
                    logger.info(f"Alternative locator succeeded: {alt_locator}")
                    result["select_details"] = alt_result
                    result["status"] = "success"
                    result["element"] = alt_locator  # Update to the working locator
                    break
        
        # Update overall status based on select result
        if not select_result["success"] and not result["select_details"]["success"]:
            result["status"] = "error"
            result["error"] = select_result.get("error", "Select operation failed")
        
        # Take screenshot after selection if requested
        if take_screenshot:
            result["screenshots"]["after"] = driver.get_screenshot_as_base64()
            
    except Exception as e:
        logger.error(f"Error in smart_select: {str(e)}")
        result["status"] = "error"
        result["error"] = str(e)
        
        # Take error screenshot if requested
        if take_screenshot:
            try:
                driver = BrowserManager.get_driver()
                result["screenshots"]["error"] = driver.get_screenshot_as_base64()
            except:
                pass
            
    return result

def smart_wait(
    locator: str,
    wait_time: int = 10,
    check_visibility: bool = True,
    check_clickable: bool = False,
    take_screenshot: bool = True,
    url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Wait for an element with enhanced validation and smart waiting strategies.
    
    Args:
        locator: Element locator in format "type=value" (e.g., "id=loading")
        wait_time: Maximum time to wait in seconds
        check_visibility: Whether to check if element is visible
        check_clickable: Whether to check if element is clickable
        take_screenshot: Whether to take screenshots for debugging
        url: Optional URL to navigate to before waiting
        
    Returns:
        Dictionary with operation status and details
    """
    result = {
        "status": "success",
        "element": locator,
        "screenshots": {},
        "error": None,
        "wait_details": None
    }
    
    try:
        # Get browser instance from the manager
        driver = BrowserManager.get_driver()
        
        # Create smart browser interaction instance
        smart_browser = SmartBrowserInteraction(driver)
        
        # Navigate to URL if provided
        if url:
            logger.info(f"Navigating to URL: {url}")
            nav_result = smart_browser.navigate(url, wait_for_page_load=True, timeout=wait_time)
            if not nav_result["success"]:
                result["status"] = "error"
                result["error"] = f"Navigation failed: {nav_result.get('error', 'Unknown error')}"
                return result
        
        # Take screenshot before waiting if requested
        if take_screenshot:
            result["screenshots"]["before"] = driver.get_screenshot_as_base64()
        
        # Perform the wait with enhanced validation
        wait_result = smart_browser.wait_for_element(
            locator,
            timeout=wait_time,
            check_visibility=check_visibility,
            check_clickable=check_clickable
        )
        
        result["wait_details"] = wait_result
        
        # Update overall status based on wait result
        if not wait_result["success"]:
            result["status"] = "error"
            result["error"] = wait_result.get("error", "Wait operation failed")
        
        # Take screenshot after waiting if requested
        if take_screenshot:
            result["screenshots"]["after"] = driver.get_screenshot_as_base64()
            
    except Exception as e:
        logger.error(f"Error in smart_wait: {str(e)}")
        result["status"] = "error"
        result["error"] = str(e)
        
        # Take error screenshot if requested
        if take_screenshot:
            try:
                driver = BrowserManager.get_driver()
                result["screenshots"]["error"] = driver.get_screenshot_as_base64()
            except:
                pass
            
    return result

def find_smart_locator(
    url: str,
    element_description: str,
    wait_time: int = 10,
    take_screenshot: bool = True
) -> Dict[str, Any]:
    """
    Find the best locator for an element based on its description.
    Provides visual element selection.
    
    Args:
        url: URL of the page containing the element
        element_description: Description of the element to locate
        wait_time: Time to wait for user interaction
        take_screenshot: Whether to take screenshots of the page
        
    Returns:
        Dictionary with locator information
    """
    result = {
        "status": "success",
        "description": element_description,
        "screenshots": {},
        "error": None,
        "best_locator": None,
        "alternative_locators": []
    }
    
    try:
        # Get browser instance from the manager
        driver = BrowserManager.get_driver()
        
        # Create smart browser interaction instance
        smart_browser = SmartBrowserInteraction(driver)
        
        # Navigate to URL
        logger.info(f"Navigating to URL: {url}")
        nav_result = smart_browser.navigate(url, wait_for_page_load=True, timeout=wait_time)
        if not nav_result["success"]:
            result["status"] = "error"
            result["error"] = f"Navigation failed: {nav_result.get('error', 'Unknown error')}"
            return result
        
        # Take screenshot of the page if requested
        if take_screenshot:
            result["screenshots"]["page"] = driver.get_screenshot_as_base64()
        
        # Find the best locator for the element
        locator_result = smart_browser.find_smart_locator(
            element_description,
            wait_time=wait_time
        )
        
        if not locator_result["success"]:
            result["status"] = "error"
            result["error"] = locator_result.get("error", "Failed to find locator")
            return result
        
        # Update result with locator information
        result["best_locator"] = locator_result["best_locator"]
        result["alternative_locators"] = locator_result["locators"]
        result["element_tag"] = locator_result.get("element_tag")
        result["element_text"] = locator_result.get("element_text")
        
    except Exception as e:
        logger.error(f"Error in find_smart_locator: {str(e)}")
        result["status"] = "error"
        result["error"] = str(e)
        
        # Take error screenshot if requested
        if take_screenshot:
            try:
                driver = BrowserManager.get_driver()
                result["screenshots"]["error"] = driver.get_screenshot_as_base64()
            except:
                pass
            
    return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register all smart browser tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_smart_click(
        locator: str,
        wait_time: int = 10,
        retry_count: int = 3,
        take_screenshot: bool = True,
        url: Optional[str] = None,
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
        Enhanced click operation with smart locator detection and recovery strategies.
        
        Args:
            locator: Element locator string (e.g., "xpath=//button", "id=submit")
            wait_time: Maximum wait time in seconds
            retry_count: Number of retry attempts
            take_screenshot: Whether to capture screenshots
            url: Optional URL to navigate to before clicking
            need_login: Whether login is required
            login_url: URL for login page
            username: Login username
            password: Login password
            username_locator: Username field locator
            password_locator: Password field locator
            submit_locator: Login button locator
            success_indicator: Element indicating successful login
            
        Returns:
            Operation result with status and details
        """
        return smart_click(
            locator=locator,
            wait_time=wait_time,
            retry_count=retry_count,
            take_screenshot=take_screenshot,
            url=url,
            need_login=need_login,
            login_url=login_url,
            username=username,
            password=password,
            username_locator=username_locator,
            password_locator=password_locator,
            submit_locator=submit_locator,
            success_indicator=success_indicator
        )
    
    @mcp.tool()
    async def robot_browser_smart_input(
        locator: str,
        text: str,
        wait_time: int = 10,
        clear_first: bool = True,
        retry_count: int = 3,
        press_enter: bool = False,
        take_screenshot: bool = True,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enhanced text input with smart validation and recovery strategies.
        
        Args:
            locator: Element locator string (e.g., "xpath=//input", "id=email")
            text: Text to input
            wait_time: Maximum wait time in seconds
            clear_first: Whether to clear the field first
            retry_count: Number of retry attempts
            press_enter: Whether to press Enter after input
            take_screenshot: Whether to capture screenshots
            url: Optional URL to navigate to before input
            
        Returns:
            Operation result with status and details
        """
        return smart_input(
            locator=locator,
            text=text,
            wait_time=wait_time,
            clear_first=clear_first,
            retry_count=retry_count,
            press_enter=press_enter,
            take_screenshot=take_screenshot,
            url=url
        )
    
    @mcp.tool()
    async def robot_browser_smart_select(
        locator: str,
        option_text: Optional[str] = None,
        option_value: Optional[str] = None,
        option_index: Optional[int] = None,
        wait_time: int = 10,
        retry_count: int = 3,
        take_screenshot: bool = True,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enhanced dropdown selection with smart validation and recovery strategies.
        
        Args:
            locator: Element locator string (e.g., "xpath=//select", "id=country")
            option_text: Text of the option to select
            option_value: Value of the option to select
            option_index: Index of the option to select
            wait_time: Maximum wait time in seconds
            retry_count: Number of retry attempts
            take_screenshot: Whether to capture screenshots
            url: Optional URL to navigate to before selection
            
        Returns:
            Operation result with status and details
        """
        return smart_select(
            locator=locator,
            option_text=option_text,
            option_value=option_value,
            option_index=option_index,
            wait_time=wait_time,
            retry_count=retry_count,
            take_screenshot=take_screenshot,
            url=url
        )
    
    @mcp.tool()
    async def robot_browser_smart_wait(
        locator: str,
        wait_time: int = 10,
        check_visibility: bool = True,
        check_clickable: bool = False,
        take_screenshot: bool = True,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enhanced waiting operation with smart strategies for different page types.
        
        Args:
            locator: Element locator string (e.g., "xpath=//div", "id=loading")
            wait_time: Maximum wait time in seconds
            check_visibility: Whether to check element visibility
            check_clickable: Whether to check element clickability
            take_screenshot: Whether to capture screenshots
            url: Optional URL to navigate to before waiting
            
        Returns:
            Operation result with status and details
        """
        return smart_wait(
            locator=locator,
            wait_time=wait_time,
            check_visibility=check_visibility,
            check_clickable=check_clickable,
            take_screenshot=take_screenshot,
            url=url
        )
    
    @mcp.tool()
    async def robot_browser_find_smart_locator(
        url: str,
        element_description: str,
        wait_time: int = 10,
        take_screenshot: bool = True
    ) -> Dict[str, Any]:
        """
        Interactively find the best locator for an element, with visual selection.
        
        Args:
            url: URL of the page containing the element
            element_description: Description of the element to locate
            wait_time: Time to wait for user interaction
            take_screenshot: Whether to capture screenshots
            
        Returns:
            Best locator and alternatives with selection details
        """
        return find_smart_locator(
            url=url,
            element_description=element_description,
            wait_time=wait_time,
            take_screenshot=take_screenshot
        ) 