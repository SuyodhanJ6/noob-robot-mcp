#!/usr/bin/env python
"""
MCP Tool: Robot Browser PDF
Provides browser PDF generation functionality for Robot Framework through MCP.
"""

import os
import logging
import base64
import json
from typing import Dict, Any, Optional
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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger('robot_tool.browser_pdf')

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def initialize_webdriver() -> Optional[webdriver.Chrome]:
    """
    Initialize the Chrome WebDriver with multiple fallback methods.
    
    Returns:
        WebDriver object if successful, None otherwise
    """
    # Set up Chrome options for headless browsing (required for PDF printing)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")  # Set a large window size
    chrome_options.add_argument("--disable-gpu")  # Required for PDF printing in some setups
    
    # Try different approaches to initialize the WebDriver
    driver = None
    last_error = None
    
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
        last_error = str(e)
        logger.warning(f"WebDriver initialization failed: {e}")
            
    if driver is None:
        logger.error(f"All WebDriver initialization methods failed. Last error: {last_error}")
        
    return driver

def save_base64_to_file(base64_data: str, output_path: str) -> bool:
    """
    Save base64 encoded data to a file.
    
    Args:
        base64_data: Base64 encoded data
        output_path: Path to save the data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create the directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Decode and save the data
        with open(output_path, 'wb') as f:
            f.write(base64.b64decode(base64_data))
            
        return True
    except Exception as e:
        logger.error(f"Error saving base64 to file: {e}")
        return False

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def generate_pdf(
    url: str,
    save_path: Optional[str] = None,
    wait_time: int = 10,
    page_size: str = 'A4',
    landscape: bool = False,
    print_background: bool = True,
    scale: float = 1.0
) -> Dict[str, Any]:
    """
    Generate a PDF from a web page.
    
    Args:
        url: URL to navigate to
        save_path: Path to save the PDF (optional)
        wait_time: Time to wait for page to load in seconds
        page_size: Page size for the PDF ('A4', 'Letter', etc.)
        landscape: Whether to use landscape orientation
        print_background: Whether to print background colors/images
        scale: Scale factor for the PDF (1.0 = 100%)
        
    Returns:
        Dictionary with PDF data and metadata
    """
    result = {
        "url": url,
        "save_path": save_path,
        "page_size": page_size,
        "landscape": landscape,
        "print_background": print_background,
        "scale": scale,
        "status": "success",
        "robot_command": None,
        "error": None
    }
    
    driver = None
    try:
        # Initialize WebDriver
        driver = initialize_webdriver()
        if not driver:
            result["status"] = "error"
            result["error"] = "Failed to initialize WebDriver"
            return result
            
        # Navigate to the URL
        logger.info(f"Navigating to URL: {url}")
        driver.set_page_load_timeout(wait_time * 2)
        driver.get(url)
        
        # Wait for page to be loaded
        try:
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            result["status"] = "warning"
            result["error"] = f"Timeout waiting for page to load after {wait_time} seconds"
            # Continue anyway - maybe the page is still usable
        
        # Define PDF print options
        print_options = {
            'paperWidth': 8.5,  # Default Letter width in inches
            'paperHeight': 11,  # Default Letter height in inches
            'marginTop': 0,
            'marginBottom': 0,
            'marginLeft': 0,
            'marginRight': 0,
            'printBackground': print_background,
            'scale': scale,
            'landscape': landscape
        }
        
        # Set page size
        if page_size.upper() == 'A4':
            print_options['paperWidth'] = 8.27  # A4 width in inches
            print_options['paperHeight'] = 11.69  # A4 height in inches
        # Add more paper sizes as needed
        
        # Execute print to PDF command
        logger.info(f"Generating PDF for URL: {url}")
        pdf_data = driver.execute_cdp_cmd('Page.printToPDF', print_options)
        
        # Extract PDF base64 data
        pdf_base64 = pdf_data.get('data', '')
        
        # Store PDF data in result
        result["pdf_base64"] = pdf_base64
        
        # Save to file if requested
        if save_path:
            logger.info(f"Saving PDF to: {save_path}")
            save_success = save_base64_to_file(pdf_base64, save_path)
            if save_success:
                result["saved_to_file"] = True
                result["file_path"] = os.path.abspath(save_path)
            else:
                result["saved_to_file"] = False
                result["save_error"] = "Failed to save PDF to file"
        
        # Generate Robot Framework command
        robot_command = f"""*** Settings ***
Library           SeleniumLibrary
Library           OperatingSystem

*** Keywords ***
Generate PDF From Website
    [Arguments]    ${{url}}    ${{save_path}}
    Open Browser    ${{url}}    headlesschrome
    Wait Until Page Contains Element    tag:body    timeout={wait_time}
    # Note: This is a custom implementation as Robot Framework doesn't have direct PDF generation
    # You would need to create a custom keyword or use the Browser library with Playwright
    Execute Javascript    console.log('PDF generation requested - requires custom implementation')
    Close Browser
"""
        result["robot_command"] = robot_command
        
        return result
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if driver:
            driver.quit()

def generate_pdf_script(
    url: str,
    output_file: str,
    pdf_path: str,
    browser: str = "Chrome",
    wait_time: int = 10,
    page_size: str = 'A4',
    landscape: bool = False,
    print_background: bool = True
) -> Dict[str, Any]:
    """
    Generate a Robot Framework script for creating a PDF from a web page.
    
    Args:
        url: URL to navigate to
        output_file: File to save the generated script
        pdf_path: Path to save the PDF in the script
        browser: Browser to use (default is Chrome)
        wait_time: Time to wait for page to load in seconds
        page_size: Page size for the PDF ('A4', 'Letter', etc.)
        landscape: Whether to use landscape orientation
        print_background: Whether to print background colors/images
        
    Returns:
        Dictionary with generation status and file path
    """
    result = {
        "status": "success",
        "output_file": output_file,
        "error": None
    }
    
    try:
        # Generate orientation and background settings
        orientation = "landscape" if landscape else "portrait"
        background = "with" if print_background else "without"
        
        # Generate Robot Framework script
        script_content = f"""*** Settings ***
Documentation     Robot Framework script for generating a PDF from a web page
Library           SeleniumLibrary
Library           OperatingSystem
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}              {url}
${{BROWSER}}          {browser}
${{WAIT_TIME}}        {wait_time}
${{PDF_PATH}}         {pdf_path}
${{PAGE_SIZE}}        {page_size}
${{ORIENTATION}}      {orientation}
${{PRINT_BACKGROUND}} {print_background}

*** Test Cases ***
Generate PDF From Website
    [Documentation]    Navigate to a page and generate a PDF ({page_size}, {orientation}, {background} background)
    
    # IMPORTANT NOTE: Robot Framework's SeleniumLibrary doesn't provide direct PDF generation
    # This script creates a demo file with instructions on how this would need to be implemented
    # with a custom keyword or using the Browser library with Playwright
    
    Open Browser    ${{URL}}    ${{BROWSER}}    options=add_argument("--headless")
    Maximize Browser Window
    Wait Until Page Contains Element    tag:body    timeout=${{WAIT_TIME}}s
    
    # Create a placeholder file with instructions
    ${{\$instructions}}=    Catenate    SEPARATOR=\\n
    ...    # PDF Generation Instructions
    ...    # To implement real PDF generation, you would need:
    ...    # 1. A custom Robot Framework library that uses Selenium's CDP commands
    ...    # 2. Or use the newer Browser library that uses Playwright which has pdf support
    ...    #
    ...    # Example using Browser library (Playwright):
    ...    # *** Settings ***
    ...    # Library    Browser
    ...    # *** Test Cases ***
    ...    # Generate PDF
    ...    #     New Browser    headless=True
    ...    #     New Page    {url}
    ...    #     ${{\$pdf}}=    Pdf    path=${{PDF_PATH}}    landscape={str(landscape).lower()}    format={page_size}
    Create File    ${{PDF_PATH}}    ${{\$instructions}}
    
    Log    PDF generation placeholder created at ${{PDF_PATH}}
    # Note: In a real implementation, this would be replaced with actual PDF generation
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
        logger.error(f"Error generating PDF script: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        result["output_file"] = None
        return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the browser PDF tools with the MCP server."""
    
    @mcp.tool()
    async def robot_browser_generate_pdf(
        url: str,
        save_path: Optional[str] = None,
        wait_time: int = 10,
        page_size: str = 'A4',
        landscape: bool = False,
        print_background: bool = True,
        scale: float = 1.0
    ) -> Dict[str, Any]:
        """
        Generate a PDF from a web page.
        
        Args:
            url: URL to navigate to
            save_path: Path to save the PDF (optional)
            wait_time: Time to wait for page to load in seconds
            page_size: Page size for the PDF ('A4', 'Letter', etc.)
            landscape: Whether to use landscape orientation
            print_background: Whether to print background colors/images
            scale: Scale factor for the PDF (1.0 = 100%)
            
        Returns:
            Dictionary with PDF data and metadata
        """
        logger.info(f"Received request to generate PDF from URL: {url}")
        result = generate_pdf(url, save_path, wait_time, page_size, landscape, print_background, scale)
        return result
    
    @mcp.tool()
    async def robot_browser_generate_pdf_script(
        url: str,
        output_file: str,
        pdf_path: str,
        browser: str = "Chrome",
        wait_time: int = 10,
        page_size: str = 'A4',
        landscape: bool = False,
        print_background: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework script for creating a PDF from a web page.
        
        Args:
            url: URL to navigate to
            output_file: File to save the generated script
            pdf_path: Path to save the PDF in the script
            browser: Browser to use (default is Chrome)
            wait_time: Time to wait for page to load in seconds
            page_size: Page size for the PDF ('A4', 'Letter', etc.)
            landscape: Whether to use landscape orientation
            print_background: Whether to print background colors/images
            
        Returns:
            Dictionary with generation status and file path
        """
        logger.info(f"Received request to generate PDF script for URL: {url}")
        result = generate_pdf_script(url, output_file, pdf_path, browser, wait_time, page_size, landscape, print_background)
        return result 