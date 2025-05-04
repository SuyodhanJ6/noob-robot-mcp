#!/usr/bin/env python
"""
MCP Tool: Robot Browser Network
Provides browser network request capture functionality for Robot Framework through MCP.
"""

import os
import logging
import time
import json
from typing import Dict, Any, Optional, List
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
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import WebDriverException

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_network')

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def initialize_webdriver_with_network() -> Optional[webdriver.Chrome]:
    """
    Initialize the Chrome WebDriver with network logging enabled.
    
    Returns:
        WebDriver object if successful, None otherwise
    """
    # Enable performance logging
    capabilities = DesiredCapabilities.CHROME
    capabilities['goog:loggingPrefs'] = {'performance': 'ALL', 'browser': 'ALL'}
    
    # Set up Chrome options for headless browsing
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Try different approaches to initialize the WebDriver
    driver = None
    last_error = None
    
    try:
        if WEBDRIVER_MANAGER_AVAILABLE:
            # Try with webdriver-manager if available
            logger.info("Trying WebDriver Manager initialization")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options,
                desired_capabilities=capabilities
            )
        else:
            # Direct WebDriver initialization
            logger.info("Trying direct WebDriver initialization")
            service = Service()
            driver = webdriver.Chrome(
                service=service, 
                options=chrome_options,
                desired_capabilities=capabilities
            )
            
    except Exception as e:
        last_error = str(e)
        logger.warning(f"WebDriver initialization failed: {e}")
            
    if driver is None:
        logger.error(f"All WebDriver initialization methods failed. Last error: {last_error}")
        
    return driver

def extract_network_requests(performance_logs: List[Dict]) -> List[Dict]:
    """
    Extract network request information from performance logs.
    
    Args:
        performance_logs: Performance logs from Chrome WebDriver
        
    Returns:
        List of network request data
    """
    network_requests = []
    
    for entry in performance_logs:
        try:
            log = json.loads(entry.get('message', '{}')).get('message', {})
            
            # Filter for Network events
            if 'Network.response' in log.get('method', '') or 'Network.request' in log.get('method', ''):
                params = log.get('params', {})
                request_id = params.get('requestId')
                
                if request_id:
                    # Create or update request info
                    request_info = next((r for r in network_requests if r.get('requestId') == request_id), None)
                    
                    if not request_info:
                        request_info = {'requestId': request_id}
                        network_requests.append(request_info)
                    
                    # Add/update information based on event type
                    if log.get('method') == 'Network.requestWillBeSent':
                        req = params.get('request', {})
                        request_info.update({
                            'url': req.get('url'),
                            'method': req.get('method'),
                            'headers': req.get('headers'),
                            'timestamp': params.get('timestamp')
                        })
                    
                    elif log.get('method') == 'Network.responseReceived':
                        resp = params.get('response', {})
                        request_info.update({
                            'status': resp.get('status'),
                            'statusText': resp.get('statusText'),
                            'mimeType': resp.get('mimeType'),
                            'responseHeaders': resp.get('headers')
                        })
                        
        except Exception as e:
            logger.warning(f"Error parsing network log entry: {e}")
    
    return network_requests

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def capture_network_requests(
    url: str, 
    wait_time: int = 5,
    filter_type: Optional[str] = None,
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Capture network requests made by a web page.
    
    Args:
        url: URL to navigate to
        wait_time: Time to wait for page to load in seconds
        filter_type: Filter requests by type (e.g., 'xhr', 'document', 'script')
        save_path: Path to save the network requests as JSON
        
    Returns:
        Dictionary with network request data
    """
    result = {
        "url": url,
        "network_requests": [],
        "status": "success",
        "robot_command": None,
        "error": None
    }
    
    driver = None
    try:
        # Initialize WebDriver with network logging
        driver = initialize_webdriver_with_network()
        if not driver:
            result["status"] = "error"
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Navigate to the URL
        logger.info(f"Navigating to URL: {url}")
        driver.set_page_load_timeout(wait_time * 2)
        driver.get(url)
        
        # Wait for page to load and execute any JavaScript/AJAX requests
        time.sleep(wait_time)
        
        # Get performance logs
        performance_logs = driver.get_log('performance')
        
        # Extract network requests
        network_requests = extract_network_requests(performance_logs)
        
        # Apply filter if specified
        if filter_type:
            filter_type = filter_type.lower()
            filtered_requests = []
            for req in network_requests:
                mime_type = req.get('mimeType', '').lower()
                req_url = req.get('url', '').lower()
                
                if (filter_type == 'xhr' and ('json' in mime_type or 'xml' in mime_type or '/ajax/' in req_url)) or \
                   (filter_type == 'document' and ('html' in mime_type or 'document' in mime_type)) or \
                   (filter_type == 'script' and ('javascript' in mime_type or 'js' in req_url)) or \
                   (filter_type == 'image' and ('image' in mime_type or any(ext in req_url for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg']))) or \
                   (filter_type == 'css' and ('css' in mime_type or '.css' in req_url)):
                    filtered_requests.append(req)
            
            network_requests = filtered_requests
        
        # Store network requests in result
        result["network_requests"] = network_requests
        
        # Save to JSON file if requested
        if save_path:
            try:
                # Ensure the directory exists
                save_dir = os.path.dirname(save_path)
                if save_dir and not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                
                # Save to file
                with open(save_path, 'w') as f:
                    json.dump(network_requests, f, indent=2)
                
                result["saved_to_file"] = True
                result["file_path"] = os.path.abspath(save_path)
            except Exception as e:
                logger.error(f"Error saving network requests to file: {e}")
                result["saved_to_file"] = False
                result["save_error"] = str(e)
        
        # Generate Robot Framework command for network capture
        robot_command = """*** Settings ***
Library           SeleniumLibrary
Library           OperatingSystem

*** Keywords ***
Capture Network Requests
    [Arguments]    ${url}
    # Note: Robot Framework doesn't have direct network request logging
    # This would require a custom Python library
    Open Browser    ${url}    Chrome    options=add_argument("--enable-logging")
    # Custom keyword would be needed to extract the logs
    # In real implementation, you would need to create a custom library
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error capturing network requests: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_network_script(
    url: str, 
    output_file: str,
    browser: str = "Chrome",
    wait_time: int = 5,
    filter_type: Optional[str] = None,
    save_json_path: Optional[str] = "network_requests.json"
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for capturing network requests.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        browser: Browser to use (default is Chrome)
        wait_time: Time to wait for page to load in seconds
        filter_type: Filter requests by type (e.g., 'xhr', 'document', 'script')
        save_json_path: Path to save network requests JSON in the script
        
    Returns:
        Dictionary with generation status and file path
    """
    result = {
        "status": "success",
        "output_file": output_file,
        "error": None
    }
    
    try:
        # Generate filter comment
        filter_comment = f"# Filter requests by type: {filter_type}" if filter_type else ""
        
        # Generate Robot Framework script
        script_content = f"""*** Settings ***
Documentation     Robot Framework script for capturing network requests
Library           SeleniumLibrary
Library           OperatingSystem
Library           Collections
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}          {url}
${{BROWSER}}      {browser}
${{WAIT_TIME}}    {wait_time}
${{SAVE_PATH}}    {save_json_path}

*** Test Cases ***
Capture Network Requests
    [Documentation]    Navigate to a page and capture network requests
    {filter_comment}
    
    # Open browser with logging enabled (this will need a custom keyword in real use)
    ${{\$options}}=    Create Dictionary    goog:loggingPrefs=${{dict(performance=ALL)}}
    Open Browser    ${{URL}}    ${{BROWSER}}    desired_capabilities=${{options}}
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
    
    # Additional actions to trigger network requests can be added here
    # For example: Click Button    id=load-data
    
    Sleep    ${{WAIT_TIME}}s    # Wait for network requests to complete
    
    # IMPORTANT: This is a placeholder - Robot Framework doesn't have built-in
    # network request capturing. In a real implementation, you would need a custom
    # library or keyword that accesses the WebDriver logs.
    
    # Placeholder for custom keyword that would capture the requests
    Log    Capturing network requests (would use custom keyword in real implementation)
    
    # Create a demo output file with placeholder content
    Create File    ${{SAVE_PATH}}    ${{{"dummy_network_capture": true, "url": "${{URL}}"}}}
    
    Log    Network requests saved to ${{SAVE_PATH}}
"""
        
        # Ensure the directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Write the script to the output file
        with open(output_file, 'w') as f:
            f.write(script_content)
            
        return result
    except Exception as e:
        logger.error(f"Error generating network script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser network tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_capture_network(
        url: str,
        wait_time: int = 5,
        filter_type: Optional[str] = None,
        save_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Capture network requests made by a web page.
        
        Args:
            url: URL to navigate to
            wait_time: Time to wait for page to load in seconds
            filter_type: Filter requests by type (e.g., 'xhr', 'document', 'script')
            save_path: Path to save the network requests as JSON
            
        Returns:
            Dictionary with network request data
        """
        logger.info(f"Received request to capture network requests from URL: {url}")
        result = capture_network_requests(url, wait_time, filter_type, save_path)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_network_script(
        url: str,
        output_file: str,
        browser: str = "Chrome",
        wait_time: int = 5,
        filter_type: Optional[str] = None,
        save_json_path: Optional[str] = "network_requests.json"
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for capturing network requests.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            browser: Browser to use (default is Chrome)
            wait_time: Time to wait for page to load in seconds
            filter_type: Filter requests by type (e.g., 'xhr', 'document', 'script')
            save_json_path: Path to save network requests JSON in the script
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate network script for URL: {url}")
        result = generate_network_script(url, output_file, browser, wait_time, filter_type, save_json_path)
        return result 