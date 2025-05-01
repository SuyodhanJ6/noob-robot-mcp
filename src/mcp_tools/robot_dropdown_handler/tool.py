#!/usr/bin/env python
"""
MCP Tool: Robot Dropdown Handler
Specialized tool for handling dropdowns in web forms, offering enhanced functionality
for dropdown element detection, option extraction, and verification.
"""

import os
import logging
import json
import time
import tempfile
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException, 
    NoSuchElementException,
    StaleElementReferenceException,
    ElementNotInteractableException
)
from selenium.webdriver.chrome.service import Service

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger('robot_tool.dropdown_handler')

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

def initialize_webdriver(wait_time: int = 20) -> webdriver.Chrome:
    """Initialize Chrome WebDriver with appropriate settings."""
    # Set up Chrome options for headless browsing
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Try different approaches to initialize the WebDriver
    try_methods = ["direct", "manager", "path"]
    driver = None
    last_error = None
    
    for method in try_methods:
        try:
            if method == "direct":
                # Direct WebDriver initialization
                logger.info("Trying direct WebDriver initialization")
                service = Service()
                driver = webdriver.Chrome(service=service, options=chrome_options)
                break
                
            elif method == "manager" and WEBDRIVER_MANAGER_AVAILABLE:
                # Try with webdriver-manager if available
                logger.info("Trying WebDriver Manager initialization")
                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=chrome_options
                )
                break
                
            elif method == "path":
                # Search for chromedriver in PATH
                logger.info("Searching for chromedriver in PATH")
                import shutil
                chromedriver_path = shutil.which("chromedriver")
                if chromedriver_path:
                    logger.info(f"Found chromedriver at {chromedriver_path}")
                    service = Service(executable_path=chromedriver_path)
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                    break
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Method {method} failed: {e}")
            continue
            
    if driver is None:
        raise Exception(f"All WebDriver initialization methods failed. Last error: {last_error}")
    
    # Configure browser
    logger.info("WebDriver initialized successfully")
    driver.set_page_load_timeout(wait_time * 2)  # Double the wait time for page load
    return driver

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def extract_dropdown_options(url: str, dropdown_locator: str, wait_time: int = 20) -> Dict[str, Any]:
    """
    Extract all options from a dropdown element.
    
    Args:
        url: URL of the web page to analyze
        dropdown_locator: Locator for the dropdown element (id, name, xpath, css)
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with all detected options and their values
    """
    result = {
        "url": url,
        "dropdown_locator": dropdown_locator,
        "options": [],
        "option_values": [],
        "option_count": 0,
        "selected_option": None,
        "selected_value": None,
        "error": None
    }
    
    driver = None
    try:
        # Initialize the WebDriver
        driver = initialize_webdriver(wait_time)
        
        # Navigate to the URL
        logger.info(f"Visiting URL to extract dropdown options: {url}")
        driver.get(url)
        
        # Wait for the page to load
        logger.info(f"Waiting for page to load...")
        time.sleep(wait_time // 2)  # Wait some time to ensure page loads
        
        # Determine the appropriate By method based on the locator format
        by_method = By.ID  # Default to ID
        locator_value = dropdown_locator
        
        if dropdown_locator.startswith("id="):
            by_method = By.ID
            locator_value = dropdown_locator[3:]
        elif dropdown_locator.startswith("name="):
            by_method = By.NAME
            locator_value = dropdown_locator[5:]
        elif dropdown_locator.startswith("xpath="):
            by_method = By.XPATH
            locator_value = dropdown_locator[6:]
        elif dropdown_locator.startswith("css="):
            by_method = By.CSS_SELECTOR
            locator_value = dropdown_locator[4:]
        elif dropdown_locator.startswith("//"):
            by_method = By.XPATH
            locator_value = dropdown_locator
        elif dropdown_locator.startswith(".") or dropdown_locator.startswith("#"):
            by_method = By.CSS_SELECTOR
            locator_value = dropdown_locator
            
        # Wait for dropdown to be present
        logger.info(f"Looking for dropdown with locator: {locator_value} (by {by_method})")
        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((by_method, locator_value))
            )
            
            # Check if it's a SELECT element
            if element.tag_name.lower() == "select":
                select = Select(element)
                
                # Get all options
                options = []
                option_values = []
                
                for option in select.options:
                    try:
                        option_text = option.text.strip()
                        option_value = option.get_attribute("value")
                        options.append(option_text)
                        option_values.append(option_value)
                    except StaleElementReferenceException:
                        logger.warning("Option element became stale while extracting")
                        continue
                
                # Get selected option
                try:
                    selected_options = select.all_selected_options
                    if selected_options:
                        result["selected_option"] = selected_options[0].text.strip()
                        result["selected_value"] = selected_options[0].get_attribute("value")
                except Exception as e:
                    logger.warning(f"Error getting selected option: {e}")
                
                result["options"] = options
                result["option_values"] = option_values
                result["option_count"] = len(options)
                
            else:
                # Handle custom dropdown (not a SELECT element)
                # Get all child elements that might be options
                logger.info("Element is not a standard SELECT dropdown, trying to extract options from custom dropdown")
                
                # Try clicking to open the dropdown
                try:
                    element.click()
                    time.sleep(1)  # Wait for dropdown to open
                except ElementNotInteractableException:
                    logger.warning("Could not click dropdown to open it")
                
                # Try different strategies to find options
                option_elements = []
                
                # Strategy 1: Look for ul/li pattern
                option_elements = driver.find_elements(By.CSS_SELECTOR, f"#{locator_value} li, [aria-labelledby='{locator_value}'] li")
                
                # Strategy 2: Look for div/span with role='option'
                if not option_elements:
                    option_elements = driver.find_elements(By.CSS_SELECTOR, "[role='option'], [role='listitem']")
                
                # Strategy 3: Look for visible elements after clicking
                if not option_elements:
                    # Take screenshot to help diagnose
                    logger.info("Could not identify dropdown options using standard patterns")
                    
                options = []
                option_values = []
                
                for option in option_elements:
                    try:
                        option_text = option.text.strip()
                        option_value = option.get_attribute("value") or option.get_attribute("data-value")
                        if option_text:  # Only add non-empty options
                            options.append(option_text)
                            option_values.append(option_value)
                    except:
                        continue
                
                result["options"] = options
                result["option_values"] = option_values
                result["option_count"] = len(options)
                
                # Get selected option (text currently shown in the dropdown)
                result["selected_option"] = element.text.strip()
        
        except TimeoutException:
            result["error"] = f"Dropdown element not found within timeout period: {locator_value}"
            logger.error(result["error"])
        except Exception as e:
            result["error"] = f"Error extracting dropdown options: {str(e)}"
            logger.error(result["error"])
    
    except Exception as e:
        result["error"] = f"Error: {str(e)}"
        logger.error(f"Dropdown extraction failed: {e}")
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return result

def generate_robot_dropdown_keywords(url: str, dropdown_locator: str, output_file: str, 
                                    test_name: str = "Test Dropdown Options", 
                                    wait_time: int = 20) -> Dict[str, Any]:
    """
    Generate Robot Framework test to validate dropdown options.
    
    Args:
        url: URL of the web page containing the dropdown
        dropdown_locator: Locator for the dropdown element
        output_file: Path to save the generated Robot Framework test
        test_name: Name for the generated test case
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with generation result and extracted options
    """
    result = {
        "file_path": output_file,
        "options_extracted": False,
        "option_count": 0,
        "error": None
    }
    
    try:
        # Extract dropdown options first
        dropdown_data = extract_dropdown_options(url, dropdown_locator, wait_time)
        
        if dropdown_data["error"]:
            result["error"] = dropdown_data["error"]
            return result
            
        options = dropdown_data["options"]
        result["options_extracted"] = True
        result["option_count"] = len(options)
        
        # Generate Robot Framework test
        robot_content = f"""*** Settings ***
Documentation     Robot Framework test for validating dropdown options at {url}
Library           SeleniumLibrary
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}                      {url}
${{BROWSER}}                  Chrome
${{DROPDOWN_LOCATOR}}         {dropdown_locator}
@{{EXPECTED_OPTIONS}}         {' '.join([f'{option}' for option in options])}

*** Test Cases ***
{test_name}
    [Documentation]    Verify dropdown options match expected values
    [Tags]    dropdown    validation
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    Wait Until Element Is Visible    ${{DROPDOWN_LOCATOR}}    timeout=10s
    
    # Get and verify dropdown options
    @{{actual_options}}=    Get List Items    ${{DROPDOWN_LOCATOR}}
    Log Many    @{{actual_options}}
    
    # Verify option count
    ${length}    Get Length    ${{actual_options}}
    Should Be Equal As Integers    ${length}    {len(options)}
    
    # Verify each option is present
    FOR    ${{expected_option}}    IN    @{{EXPECTED_OPTIONS}}
        List Should Contain Value    ${{actual_options}}    ${{expected_option}}
    END
    
    # Verify we can select options
    FOR    ${{option}}    IN    @{{actual_options}}
        Select From List By Label    ${{DROPDOWN_LOCATOR}}    ${{option}}
        ${{selected}}=    Get Selected List Label    ${{DROPDOWN_LOCATOR}}
        Should Be Equal    ${{selected}}    ${{option}}
    END
"""
        
        # Save the file
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        except:
            # If dirname fails (e.g., for a file in current directory)
            pass
            
        with open(output_file, 'w') as f:
            f.write(robot_content)
            
        result["file_path"] = os.path.abspath(output_file)
        result["content"] = robot_content
        
    except Exception as e:
        result["error"] = f"Error generating Robot Framework test: {str(e)}"
        logger.error(result["error"])
        
    return result

def find_and_verify_dropdown(url: str, dropdown_identifier: str = None, wait_time: int = 20) -> Dict[str, Any]:
    """
    Find and verify all dropdowns on a page, or a specific one if identified.
    
    Args:
        url: URL of the web page to analyze
        dropdown_identifier: Optional text to help identify the dropdown (label text, id contains, etc.)
        wait_time: Time to wait for page to load in seconds
        
    Returns:
        Dictionary with all detected dropdowns and their options
    """
    result = {
        "url": url,
        "dropdowns": [],
        "dropdown_count": 0,
        "error": None
    }
    
    driver = None
    try:
        # Initialize the WebDriver
        driver = initialize_webdriver(wait_time)
        
        # Navigate to the URL
        logger.info(f"Visiting URL to find dropdowns: {url}")
        driver.get(url)
        
        # Wait for the page to load
        logger.info(f"Waiting for page to load...")
        time.sleep(wait_time // 2)  # Wait some time to ensure page loads
        
        # Find all SELECT elements
        select_elements = driver.find_elements(By.TAG_NAME, "select")
        
        # Process each dropdown
        dropdowns = []
        
        for i, element in enumerate(select_elements):
            try:
                select_id = element.get_attribute("id") or f"select_{i+1}"
                select_name = element.get_attribute("name") or ""
                select_class = element.get_attribute("class") or ""
                
                # Check if this dropdown matches the identifier (if provided)
                if dropdown_identifier and not (
                    (select_id and dropdown_identifier.lower() in select_id.lower()) or
                    (select_name and dropdown_identifier.lower() in select_name.lower()) or
                    (select_class and dropdown_identifier.lower() in select_class.lower())
                ):
                    # Try to find associated label
                    label_match = False
                    try:
                        # Check for label with 'for' attribute
                        if select_id:
                            labels = driver.find_elements(By.CSS_SELECTOR, f"label[for='{select_id}']")
                            for label in labels:
                                if dropdown_identifier.lower() in label.text.lower():
                                    label_match = True
                                    break
                    except:
                        pass
                        
                    if not label_match:
                        continue  # Skip this dropdown as it doesn't match identifier
                
                # Get dropdown options
                select = Select(element)
                options = []
                option_values = []
                
                for option in select.options:
                    try:
                        option_text = option.text.strip()
                        option_value = option.get_attribute("value")
                        options.append(option_text)
                        option_values.append(option_value)
                    except:
                        continue
                
                # Get dropdown locators
                locators = {
                    "id": f"id={select_id}" if select_id else None,
                    "name": f"name={select_name}" if select_name else None,
                    "css": f"css=select[class*='{select_class}']" if select_class else None,
                    "xpath": f"xpath=//select[@id='{select_id}']" if select_id else 
                             f"xpath=//select[@name='{select_name}']" if select_name else
                             f"xpath=//select[{i+1}]"
                }
                
                # Remove None locators
                locators = {k: v for k, v in locators.items() if v is not None}
                
                # Create dropdown info
                dropdown_info = {
                    "id": select_id,
                    "name": select_name,
                    "class": select_class,
                    "locators": locators,
                    "recommended_locator": locators.get("id") or locators.get("name") or locators.get("xpath"),
                    "options": options,
                    "option_values": option_values,
                    "option_count": len(options)
                }
                
                dropdowns.append(dropdown_info)
                
            except Exception as e:
                logger.warning(f"Error processing dropdown {i+1}: {e}")
                continue
                
        # Also check for custom dropdowns (non-select elements)
        custom_dropdown_candidates = driver.find_elements(
            By.CSS_SELECTOR, 
            "[role='combobox'], [role='listbox'], .dropdown, .select, [class*='dropdown'], [class*='select']"
        )
        
        for i, element in enumerate(custom_dropdown_candidates):
            try:
                # Skip if it's a regular select element or a child of another dropdown
                if element.tag_name.lower() == "select":
                    continue
                    
                elem_id = element.get_attribute("id") or f"custom_dropdown_{i+1}"
                elem_class = element.get_attribute("class") or ""
                
                # Check if this dropdown matches the identifier (if provided)
                if dropdown_identifier and not (
                    (elem_id and dropdown_identifier.lower() in elem_id.lower()) or
                    (elem_class and dropdown_identifier.lower() in elem_class.lower())
                ):
                    # Try to find text match in the dropdown
                    if dropdown_identifier.lower() not in element.text.lower():
                        continue  # Skip this dropdown as it doesn't match identifier
                
                # Get dropdown locators
                locators = {
                    "id": f"id={elem_id}" if elem_id else None,
                    "css": f"css=.{elem_class.replace(' ', '.')}" if elem_class else None,
                    "xpath": f"xpath=//*[@id='{elem_id}']" if elem_id else None
                }
                
                # Remove None locators
                locators = {k: v for k, v in locators.items() if v is not None}
                
                # Create dropdown info - for custom dropdowns we don't extract options
                # as they often require clicks to display
                dropdown_info = {
                    "id": elem_id,
                    "class": elem_class,
                    "text": element.text[:50] + ("..." if len(element.text) > 50 else ""),
                    "locators": locators,
                    "recommended_locator": locators.get("id") or locators.get("css") or locators.get("xpath"),
                    "is_custom": True
                }
                
                dropdowns.append(dropdown_info)
                
            except Exception as e:
                logger.warning(f"Error processing custom dropdown {i+1}: {e}")
                continue
        
        result["dropdowns"] = dropdowns
        result["dropdown_count"] = len(dropdowns)
        
    except Exception as e:
        result["error"] = f"Error: {str(e)}"
        logger.error(f"Dropdown search failed: {e}")
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the dropdown handler tools with MCP."""
    
    @mcp.tool()
    async def robot_extract_dropdown_options(
        url: str,
        dropdown_locator: str,
        wait_time: int = 20
    ) -> Dict[str, Any]:
        """
        Extract all options from a dropdown element.
        
        Args:
            url: URL of the web page to analyze
            dropdown_locator: Locator for the dropdown element (id=, name=, xpath=, css=)
            wait_time: Time to wait for page to load in seconds
        
        Returns:
            Dict containing the dropdown options and values
        """
        return extract_dropdown_options(url, dropdown_locator, wait_time)
    
    @mcp.tool()
    async def robot_generate_dropdown_test(
        url: str,
        dropdown_locator: str,
        output_file: str,
        test_name: str = "Test Dropdown Options",
        wait_time: int = 20
    ) -> Dict[str, Any]:
        """
        Generate Robot Framework test to validate dropdown options.
        
        Args:
            url: URL of the web page containing the dropdown
            dropdown_locator: Locator for the dropdown element
            output_file: Path to save the generated Robot Framework test
            test_name: Name for the generated test case
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dict containing generation result and file path
        """
        return generate_robot_dropdown_keywords(
            url, dropdown_locator, output_file, test_name, wait_time
        )
    
    @mcp.tool()
    async def robot_find_dropdowns(
        url: str,
        dropdown_identifier: str = None,
        wait_time: int = 20
    ) -> Dict[str, Any]:
        """
        Find and verify all dropdowns on a page, or a specific one if identified.
        
        Args:
            url: URL of the web page to analyze
            dropdown_identifier: Optional text to help identify the dropdown (label text, id contains, etc.)
            wait_time: Time to wait for page to load in seconds
            
        Returns:
            Dict containing all detected dropdowns and their options
        """
        return find_and_verify_dropdown(url, dropdown_identifier, wait_time)

if __name__ == "__main__":
    # Test the dropdown handler directly
    url = input("Enter URL to scan for dropdowns: ")
    identifier = input("Enter dropdown identifier (optional): ")
    
    result = find_and_verify_dropdown(url, identifier if identifier else None)
    
    if result["error"]:
        print(f"Error: {result['error']}")
    else:
        print(f"Found {result['dropdown_count']} dropdowns")
        for i, dropdown in enumerate(result["dropdowns"]):
            print(f"\nDropdown {i+1}:")
            print(f"  ID: {dropdown.get('id', 'N/A')}")
            print(f"  Recommended locator: {dropdown.get('recommended_locator', 'N/A')}")
            if dropdown.get('is_custom', False):
                print(f"  Custom dropdown (requires interaction to show options)")
                print(f"  Text: {dropdown.get('text', 'N/A')}")
            else:
                print(f"  Options ({dropdown.get('option_count', 0)}):")
                for j, opt in enumerate(dropdown.get('options', [])):
                    print(f"    {j+1}. {opt} = {dropdown.get('option_values', [])[j] if j < len(dropdown.get('option_values', [])) else 'N/A'}") 