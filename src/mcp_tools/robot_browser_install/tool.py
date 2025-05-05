#!/usr/bin/env python
"""
MCP Tool: Robot Browser Install
Provides functionality to install and set up browser automation dependencies.
"""

import os
import sys
import logging
import subprocess
import platform
import asyncio
from typing import Dict, Any, Optional, List

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

# Configure logging
logger = logging.getLogger('robot_tool.browser_install')

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def check_playwright_package_installed() -> bool:
    """
    Check if the Playwright package is installed.
    
    Returns:
        True if Playwright is found, False otherwise
    """
    try:
        import playwright
        # Playwright doesn't expose version via __version__, so we'll just log that it's installed
        logger.info("Playwright package found")
        return True
    except ImportError:
        logger.warning("Playwright package not found")
        return False

def install_package(package_name: str) -> bool:
    """
    Install a Python package using pip.
    
    Args:
        package_name: Name of the package to install
        
    Returns:
        True if installation was successful, False otherwise
    """
    try:
        logger.info(f"Installing package: {package_name}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install {package_name}: {e}")
        return False

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

async def setup_browser_automation() -> Dict[str, Any]:
    """
    Set up browser automation by installing required dependencies.
    
    Returns:
        Dictionary with setup status and details
    """
    result = {
        "status": "success",
        "playwright_installed": False,
        "browsers_installed": [],
        "error": None,
        "packages_installed": [],
        "system_info": {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "path": os.environ.get("PATH", "")
        }
    }
    
    # Check if Playwright is installed
    if check_playwright_package_installed():
        result["playwright_installed"] = True
        
        # Check for existing browser installations first
        check_result = await check_playwright_browsers()
        
        if check_result["success"] and check_result["installed_browsers"]:
            # Browsers are already installed
            result["browsers_installed"] = check_result["installed_browsers"]
            result["message"] = f"Playwright and browsers already installed: {', '.join(check_result['installed_browsers'])}"
            logger.info(result["message"])
            return result
        
        # Install missing browsers
        logger.info("Installing Playwright browsers...")
        try:
            # Build the command to install browsers
            cmd = [sys.executable, "-m", "playwright", "install"]
            logger.info(f"Running command: {' '.join(cmd)}")
            
            # Run the installation process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Capture output
            stdout, stderr = await process.communicate()
            stdout_text = stdout.decode('utf-8') if stdout else ""
            stderr_text = stderr.decode('utf-8') if stderr else ""
            
            if process.returncode == 0:
                result["browsers_installed"] = ["chromium", "firefox", "webkit"]
                result["message"] = "Successfully installed Playwright browsers"
                logger.info(result["message"])
            else:
                result["status"] = "error"
                result["error"] = f"Failed to install Playwright browsers. Exit code: {process.returncode}"
                logger.error(result["error"])
                logger.error(f"STDERR: {stderr_text}")
        
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Error during Playwright browsers installation: {str(e)}"
            logger.error(result["error"])
    else:
        # Try to install Playwright if not found
        logger.info("Installing Playwright package...")
        if install_package("playwright"):
            result["packages_installed"].append("playwright")
            result["playwright_installed"] = True
            
            # Then install browsers
            try:
                cmd = [sys.executable, "-m", "playwright", "install"]
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                
                if process.returncode == 0:
                    result["browsers_installed"] = ["chromium", "firefox", "webkit"]
                    result["message"] = "Successfully installed Playwright and browsers"
                else:
                    result["status"] = "partial"
                    result["error"] = "Playwright installed but browsers installation failed"
            except Exception as e:
                result["status"] = "partial"
                result["error"] = f"Playwright installed but error during browser installation: {str(e)}"
        else:
            result["status"] = "error"
            result["error"] = "Failed to install Playwright package"
    
    return result

async def check_playwright_browsers() -> Dict[str, Any]:
    """
    Check which Playwright browsers are already installed.
    
    Returns:
        Dictionary with installed browsers status
    """
    logger.info("Checking installed Playwright browsers")
    
    result = {
        "success": False,
        "installed_browsers": [],
        "missing_browsers": [],
        "stdout": "",
        "stderr": "",
    }
    
    try:
        # Try to import the Playwright module
        try:
            from playwright.sync_api import sync_playwright
            logger.info("Successfully imported Playwright modules")
        except ImportError:
            logger.warning("Could not import Playwright modules")
            result["missing_browsers"] = ["chromium", "firefox", "webkit"]
            result["message"] = "Playwright modules not properly installed"
            result["success"] = True
            return result
        
        # First check if the base directory exists
        base_path = os.path.expanduser("~/.cache/ms-playwright")
        if not os.path.exists(base_path):
            logger.warning(f"Playwright browser directory not found: {base_path}")
            result["missing_browsers"] = ["chromium", "firefox", "webkit"]
            result["message"] = "No Playwright browsers installed"
            result["success"] = True
            return result
        
        # Try to actually launch a browser (best test to see if it's properly installed)
        cmd = [sys.executable, "-c", 
               "from playwright.sync_api import sync_playwright\n"
               "with sync_playwright() as p:\n"
               "    browser = p.chromium.launch(headless=True)\n"
               "    browser.close()\n"
               "    print('Browser launch successful')\n"]
        
        logger.info("Testing if Playwright browser can be launched")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        result["stdout"] = stdout.decode('utf-8') if stdout else ""
        result["stderr"] = stderr.decode('utf-8') if stderr else ""
        
        if process.returncode == 0 and "Browser launch successful" in result["stdout"]:
            # Browser launch successful - we have at least chromium
            result["installed_browsers"].append("chromium")
            logger.info("Chromium browser is installed and working")
        else:
            logger.warning(f"Chromium browser test failed: {result['stderr']}")
            result["missing_browsers"].append("chromium")
        
        # For other browsers, check directories
        browser_dirs = {
            "firefox": ["firefox-", "firefox/"],
            "webkit": ["webkit-", "webkit/"],
        }
        
        for browser, prefixes in browser_dirs.items():
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                if os.path.isdir(item_path):
                    for prefix in prefixes:
                        if item.startswith(prefix):
                            # Check if it has executable files
                            if any(os.access(os.path.join(item_path, f), os.X_OK) 
                                  for f in os.listdir(item_path) 
                                  if os.path.isfile(os.path.join(item_path, f))):
                                result["installed_browsers"].append(browser)
                                logger.info(f"{browser} browser is installed")
                                break
            
            if browser not in result["installed_browsers"]:
                result["missing_browsers"].append(browser)
                
        result["success"] = True
        
        if result["installed_browsers"]:
            result["message"] = f"Found installed browsers: {', '.join(result['installed_browsers'])}"
        else:
            result["message"] = "No Playwright browsers installed"
            
        logger.info(result["message"])
        
        if result["missing_browsers"]:
            logger.info(f"Missing browsers: {', '.join(result['missing_browsers'])}")
            
    except Exception as e:
        error_message = f"Error checking Playwright browsers: {str(e)}"
        logger.error(error_message)
        result["message"] = error_message
        result["error"] = str(e)
        result["missing_browsers"] = ["chromium", "firefox", "webkit"]
        
    return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser install tool with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_setup() -> Dict[str, Any]:
        """
        Set up browser automation by installing and configuring required dependencies.
        
        This tool installs and configures Playwright and browser binaries
        required for browser automation. It should be run before using any
        browser-based automation tools.
        
        Returns:
            Dictionary with setup status and details
        """
        logger.info("Setting up browser automation environment with Playwright")
        return await setup_browser_automation()

    @mcp.tool("robot_browser_install:install_playwright")
    async def install_playwright_browsers(browsers: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Install Playwright browsers for automation.
        
        Args:
            browsers: Optional list of browser names to install. 
                     If not provided, installs all browsers.
                     Options: "chromium", "firefox", "webkit"
        
        Returns:
            Dictionary with installation status
        """
        logger.info("Installing Playwright browsers")
        
        # Default to all browsers if none specified
        if not browsers:
            browsers = ["chromium", "firefox", "webkit"]
        
        result = {
            "success": False,
            "installed_browsers": [],
            "failed_browsers": [],
            "stdout": "",
            "stderr": "",
            "command": ""
        }
        
        try:
            # Build the command
            cmd = [sys.executable, "-m", "playwright", "install"]
            cmd.extend(browsers)
            
            result["command"] = " ".join(cmd)
            logger.info(f"Running command: {result['command']}")
            
            # Run the installation process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Capture output
            stdout, stderr = await process.communicate()
            result["stdout"] = stdout.decode('utf-8') if stdout else ""
            result["stderr"] = stderr.decode('utf-8') if stderr else ""
            
            if process.returncode == 0:
                result["success"] = True
                result["installed_browsers"] = browsers
                result["message"] = f"Successfully installed browsers: {', '.join(browsers)}"
                logger.info(result["message"])
            else:
                result["failed_browsers"] = browsers
                result["message"] = f"Failed to install browsers. Exit code: {process.returncode}"
                logger.error(result["message"])
                logger.error(f"STDERR: {result['stderr']}")
                
        except Exception as e:
            error_message = f"Error installing Playwright browsers: {str(e)}"
            logger.error(error_message)
            result["message"] = error_message
            result["failed_browsers"] = browsers
            result["error"] = str(e)
            
        return result
        
    @mcp.tool("robot_browser_install:check_browsers")
    async def check_browser_status() -> Dict[str, Any]:
        """
        Check which Playwright browsers are already installed.
        
        Returns:
            Dictionary with installed browsers status
        """
        return await check_playwright_browsers()
        
    logger.info("Browser installation tools registered successfully") 