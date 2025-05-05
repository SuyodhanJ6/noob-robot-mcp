#!/usr/bin/env python
"""
Robot Authentication Handler Tool - Handles login and session management for web portals.
"""

import logging
import os
import base64
import json
from typing import Dict, Any, Optional, List, Union

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

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    ElementNotInteractableException
)

# Import the browser manager for selenium operations
from src.mcp_tools.robot_browser_manager import BrowserManager

from playwright.async_api import async_playwright, TimeoutError

# Configure logging
logger = logging.getLogger("robot_auth_handler")

# Define tool schemas
AUTH_LOGIN_SCHEMA = {
    "title": "robot_auth_loginArguments",
    "type": "object",
    "properties": {
        "url": {"title": "Url", "type": "string"},
        "username_locator": {"title": "Username Locator", "type": "string"},
        "password_locator": {"title": "Password Locator", "type": "string"}, 
        "submit_locator": {"title": "Submit Locator", "type": "string"},
        "username": {"title": "Username", "type": "string"},
        "password": {"title": "Password", "type": "string"},
        "wait_time": {"title": "Wait Time", "type": "integer", "default": 10},
        "success_indicator": {
            "title": "Success Indicator",
            "type": "string",
            "description": "Locator to verify successful login", 
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None
        },
        "failure_indicator": {
            "title": "Failure Indicator", 
            "type": "string",
            "description": "Locator to identify failed login",
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None
        },
        "save_session": {"title": "Save Session", "type": "boolean", "default": True}
    },
    "required": ["url", "username_locator", "password_locator", "submit_locator", "username", "password"]
}

AUTH_VERIFY_SCHEMA = {
    "title": "robot_auth_verifyArguments",
    "type": "object",
    "properties": {
        "url": {"title": "Url", "type": "string"},
        "success_indicator": {"title": "Success Indicator", "type": "string"},
        "failure_indicator": {
            "title": "Failure Indicator",
            "type": "string",
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None
        },
        "wait_time": {"title": "Wait Time", "type": "integer", "default": 10}
    },
    "required": ["url", "success_indicator"]
}

AUTH_USE_SESSION_SCHEMA = {
    "title": "robot_auth_use_sessionArguments", 
    "type": "object",
    "properties": {
        "url": {"title": "Url", "type": "string"},
        "success_indicator": {
            "title": "Success Indicator",
            "type": "string",
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None
        },
        "wait_time": {"title": "Wait Time", "type": "integer", "default": 10}
    },
    "required": ["url"]
}

# Helper functions
def get_by_method(locator: str) -> By:
    """Convert locator prefix to Selenium By method."""
    if locator.startswith("id="):
        return By.ID
    elif locator.startswith("name="):
        return By.NAME
    elif locator.startswith("xpath="):
        return By.XPATH
    elif locator.startswith("css=") or locator.startswith("css selector="):
        return By.CSS_SELECTOR
    elif locator.startswith("class="):
        return By.CLASS_NAME
    elif locator.startswith("link="):
        return By.LINK_TEXT
    elif locator.startswith("partial link="):
        return By.PARTIAL_LINK_TEXT
    elif locator.startswith("tag="):
        return By.TAG_NAME
    else:
        # Default to XPath if no prefix
        return By.XPATH

def get_locator_value(locator: str) -> str:
    """Extract the actual locator value without the prefix."""
    if "=" in locator:
        return locator.split("=", 1)[1]
    return locator

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

class AuthHandler:
    """Handler for authentication operations in Robot Framework automation."""
    
    def __init__(self):
        self.is_logged_in = False
        self.browser = None
        self.context = None
        self.page = None
    
    async def login(self, url, username_locator, password_locator, submit_locator, 
                   username, password, wait_time=10):
        """
        Perform login on a website.
        
        Args:
            url: Login page URL
            username_locator: Locator for username field
            password_locator: Locator for password field
            submit_locator: Locator for submit button
            username: Username to enter
            password: Password to enter
            wait_time: Time to wait for elements in seconds
            
        Returns:
            dict: Login result with success status and details
        """
        try:
            if not self.browser:
                playwright = await async_playwright().start()
                self.browser = await playwright.chromium.launch(headless=True)
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
            
            # Navigate to login page
            await self.page.goto(url, wait_until="networkidle", timeout=wait_time * 1000)
            
            # Wait for the page to be fully loaded
            current_url = self.page.url
            page_title = await self.page.title()
            
            logger.info(f"Navigated to {current_url} with title: {page_title}")
            
            # Fill username
            await self.page.wait_for_selector(username_locator, timeout=wait_time * 1000)
            await self.page.fill(username_locator, username)
            
            # Fill password
            await self.page.wait_for_selector(password_locator, timeout=wait_time * 1000)
            await self.page.fill(password_locator, password)
            
            # Take screenshot before submission
            pre_login_screenshot = await self.page.screenshot(type="jpeg", quality=50)
            
            # Click submit button
            await self.page.wait_for_selector(submit_locator, timeout=wait_time * 1000)
            await self.page.click(submit_locator)
            
            # Wait for navigation to complete after login
            await self.page.wait_for_load_state("networkidle", timeout=wait_time * 1000)
            
            # Get post-login state
            post_login_url = self.page.url
            post_login_title = await self.page.title()
            
            # Take screenshot after login
            post_login_screenshot = await self.page.screenshot(type="jpeg", quality=50)
            
            # Check if login was successful based on URL change
            self.is_logged_in = post_login_url != current_url and "login" not in post_login_url.lower()
            
            logger.info(f"Login {'successful' if self.is_logged_in else 'failed'}. Now at {post_login_url}")
            
            return {
                "success": self.is_logged_in,
                "pre_login_url": current_url,
                "post_login_url": post_login_url,
                "pre_login_title": page_title,
                "post_login_title": post_login_title,
                "pre_login_screenshot": pre_login_screenshot,
                "post_login_screenshot": post_login_screenshot
            }
        
        except TimeoutError as e:
            logger.error(f"Timeout during login: {str(e)}")
            screenshot = await self.page.screenshot(type="jpeg", quality=50) if self.page else None
            current_url = self.page.url if self.page else "Unknown"
            page_title = await self.page.title() if self.page else "Unknown"
            
            return {
                "success": False,
                "current_url": current_url,
                "page_title": page_title,
                "error_message": f"Timeout: {str(e)}",
                "screenshot": screenshot
            }
        
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            screenshot = await self.page.screenshot(type="jpeg", quality=50) if self.page else None
            current_url = self.page.url if self.page else "Unknown"
            page_title = await self.page.title() if self.page else "Unknown"
            
            return {
                "success": False,
                "current_url": current_url,
                "page_title": page_title, 
                "error_message": str(e),
                "screenshot": screenshot
            }
    
    async def verify_login_status(self):
        """
        Verify if the user is currently logged in.
        
        Returns:
            dict: Status verification result
        """
        if not self.page:
            return {"success": False, "logged_in": False, "message": "No active browser session"}
        
        try:
            current_url = self.page.url
            page_title = await self.page.title()
            screenshot = await self.page.screenshot(type="jpeg", quality=50)
            
            return {
                "success": True,
                "logged_in": self.is_logged_in,
                "current_url": current_url,
                "page_title": page_title,
                "screenshot": screenshot
            }
        except Exception as e:
            logger.error(f"Error verifying login status: {str(e)}")
            return {"success": False, "logged_in": False, "error_message": str(e)}
    
    async def navigate_to_protected_page(self, url, wait_time=10):
        """
        Navigate to a protected page using existing authenticated session.
        
        Args:
            url: URL of the protected page
            wait_time: Time to wait for page load in seconds
            
        Returns:
            dict: Navigation result
        """
        if not self.page:
            return {
                "success": False, 
                "message": "No active browser session. Please login first."
            }
        
        if not self.is_logged_in:
            return {
                "success": False,
                "message": "Not logged in. Please login first."
            }
        
        try:
            # Navigate to the protected page
            await self.page.goto(url, wait_until="networkidle", timeout=wait_time * 1000)
            
            # Wait for page to be fully loaded
            await self.page.wait_for_load_state("networkidle", timeout=wait_time * 1000)
            
            current_url = self.page.url
            page_title = await self.page.title()
            screenshot = await self.page.screenshot(type="jpeg", quality=50)
            
            # Check if we were redirected to login page
            if "login" in current_url.lower():
                self.is_logged_in = False
                return {
                    "success": False,
                    "redirected_to_login": True,
                    "current_url": current_url,
                    "page_title": page_title,
                    "screenshot": screenshot,
                    "message": "Session expired and redirected to login page"
                }
            
            return {
                "success": True,
                "current_url": current_url,
                "page_title": page_title,
                "screenshot": screenshot
            }
            
        except TimeoutError as e:
            logger.error(f"Timeout navigating to protected page: {str(e)}")
            screenshot = await self.page.screenshot(type="jpeg", quality=50)
            current_url = self.page.url
            
            return {
                "success": False,
                "current_url": current_url,
                "error_message": f"Timeout: {str(e)}",
                "screenshot": screenshot
            }
            
        except Exception as e:
            logger.error(f"Error navigating to protected page: {str(e)}")
            screenshot = await self.page.screenshot(type="jpeg", quality=50) if self.page else None
            current_url = self.page.url if self.page else "Unknown"
            
            return {
                "success": False,
                "current_url": current_url,
                "error_message": str(e),
                "screenshot": screenshot
            }
    
    async def close(self):
        """Close the browser session."""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.context = None
            self.page = None
            self.is_logged_in = False

# Instantiate the auth handler
auth_handler = AuthHandler()

def register_tool(mcp: FastMCP):
    """Register auth handler tool with MCP."""
    
    @mcp.tool("robot_auth_handler:login")
    async def auth_login(url: str, username_locator: str, password_locator: str, 
                   submit_locator: str, username: str, password: str, wait_time: int = 10):
        """
        Login to a website with provided credentials.
        
        Args:
            url: Login page URL
            username_locator: Locator for username field
            password_locator: Locator for password field
            submit_locator: Locator for submit button
            username: Username to enter
            password: Password to enter
            wait_time: Time to wait for elements in seconds (default: 10)
            
        Returns:
            Login result with success status and details
        """
        return await auth_handler.login(
            url, username_locator, password_locator, submit_locator, 
            username, password, wait_time
        )
    
    @mcp.tool("robot_auth_handler:verify")
    async def auth_verify():
        """
        Verify if user is currently logged in.
        
        Returns:
            Status verification result
        """
        return await auth_handler.verify_login_status()
    
    @mcp.tool("robot_auth_handler:navigate")
    async def auth_navigate(url: str, wait_time: int = 10):
        """
        Navigate to a protected page using existing authenticated session.
        
        Args:
            url: URL of the protected page
            wait_time: Time to wait for page load in seconds (default: 10)
            
        Returns:
            Navigation result
        """
        return await auth_handler.navigate_to_protected_page(url, wait_time)
    
    @mcp.tool("robot_auth_handler:close")
    async def auth_close():
        """
        Close the browser session.
        
        Returns:
            Closure result
        """
        await auth_handler.close()
        return {"success": True, "message": "Browser session closed"}

    logger.info("Authentication tools registered successfully") 