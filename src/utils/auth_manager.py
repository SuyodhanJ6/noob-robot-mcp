#!/usr/bin/env python
"""
Auth Manager Utility - Centralized authentication management for all tools
"""

import logging
import time
from typing import Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Import browser manager
from src.mcp_tools.robot_browser_manager import BrowserManager

logger = logging.getLogger("auth_manager")

class AuthManager:
    """Singleton class for managing authentication across all tools"""
    
    _instance = None
    _is_authenticated = False
    _auth_info = {
        "username": None,
        "site": None,
        "last_login_time": None
    }
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def is_authenticated(cls, site_url: Optional[str] = None) -> bool:
        """Check if user is authenticated for a specific site"""
        if not cls._is_authenticated:
            return False
            
        # If site URL is provided, check if it's the same site
        if site_url and cls._auth_info["site"]:
            # Basic URL matching (could be improved with domain matching)
            return site_url.startswith(cls._auth_info["site"])
            
        return cls._is_authenticated
        
    @classmethod
    def login(cls, 
              url: str, 
              username: str, 
              password: str, 
              username_locator: str, 
              password_locator: str, 
              submit_locator: str,
              success_indicator: Optional[str] = None,
              wait_time: int = 10) -> Dict[str, Any]:
        """
        Perform login and store authentication state
        
        Args:
            url: Login page URL
            username: Username to use
            password: Password to use
            username_locator: Locator for username field
            password_locator: Locator for password field
            submit_locator: Locator for submit button
            success_indicator: Optional element to verify successful login
            wait_time: Maximum wait time in seconds
            
        Returns:
            Dict with login status and info
        """
        result = {
            "success": False,
            "message": "",
            "error": None
        }
        
        try:
            # Get browser instance
            driver = BrowserManager.get_driver()
            
            # Navigate to login page if not already there
            current_url = driver.current_url
            if current_url != url:
                logger.info(f"Navigating to login page: {url}")
                driver.get(url)
                
                # Wait for page to load
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            
            # Wait for username field
            logger.info(f"Looking for username field: {username_locator}")
            parse_locator = lambda loc: (By.XPATH, loc[6:]) if loc.startswith("xpath=") else \
                           (By.ID, loc[3:]) if loc.startswith("id=") else \
                           (By.NAME, loc[5:]) if loc.startswith("name=") else \
                           (By.CSS_SELECTOR, loc[4:]) if loc.startswith("css=") else \
                           (By.XPATH, loc)
                           
            username_by, username_selector = parse_locator(username_locator)
            password_by, password_selector = parse_locator(password_locator)
            submit_by, submit_selector = parse_locator(submit_locator)
            
            # Wait for username field
            username_element = WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((username_by, username_selector))
            )
            
            # Clear and fill username field
            username_element.clear()
            username_element.send_keys(username)
            
            # Find and fill password field
            password_element = driver.find_element(password_by, password_selector)
            password_element.clear()
            password_element.send_keys(password)
            
            # Find and click submit button
            submit_element = driver.find_element(submit_by, submit_selector)
            submit_element.click()
            
            # Wait for success indicator if provided
            if success_indicator:
                success_by, success_selector = parse_locator(success_indicator)
                try:
                    WebDriverWait(driver, wait_time).until(
                        EC.presence_of_element_located((success_by, success_selector))
                    )
                    logger.info("Login successful - success indicator found")
                    cls._is_authenticated = True
                except TimeoutException:
                    logger.warning("Success indicator not found, login may have failed")
                    result["message"] = "Login might have failed - success indicator not found"
                    result["success"] = False
                    return result
            else:
                # Wait for navigation to complete
                time.sleep(2)
                
                # Simple check - if URL changed and doesn't contain 'login'
                new_url = driver.current_url
                if new_url != url and "login" not in new_url.lower():
                    logger.info(f"Login seems successful - redirected to {new_url}")
                    cls._is_authenticated = True
                else:
                    logger.warning("Login may have failed - URL didn't change as expected")
                    result["message"] = "Login might have failed - URL didn't change as expected" 
                    result["success"] = False
                    return result
            
            # Update auth info
            cls._auth_info = {
                "username": username,
                "site": url.split("/")[0] + "//" + url.split("/")[2],  # Extract domain
                "last_login_time": time.time()
            }
            
            result["success"] = True
            result["message"] = "Login successful"
            return result
            
        except Exception as e:
            logger.error(f"Login failed with error: {str(e)}")
            result["success"] = False
            result["error"] = str(e)
            result["message"] = "Login failed due to error"
            return result
    
    @classmethod
    def logout(cls) -> Dict[str, Any]:
        """Reset authentication state"""
        cls._is_authenticated = False
        cls._auth_info = {
            "username": None,
            "site": None,
            "last_login_time": None
        }
        return {
            "success": True,
            "message": "Logged out successfully"
        } 