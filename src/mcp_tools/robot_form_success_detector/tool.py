#!/usr/bin/env python
"""
MCP Tool: Robot Form Success Detector
Advanced tool for detecting form submission success through multiple methods.
Works with any type of form, not just static registration forms.
"""

import os
import logging
import json
import time
import tempfile
import hashlib
import base64
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path

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

# Try to import webdriver_manager for automatic chromedriver installation
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger('robot_tool.form_success_detector')

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

def initialize_webdriver(wait_time: int = 20, headless: bool = True) -> webdriver.Chrome:
    """Initialize Chrome WebDriver with appropriate settings."""
    # Set up Chrome options for browsing
    chrome_options = Options()
    if headless:
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

def get_page_state(driver: webdriver.Chrome) -> Dict[str, Any]:
    """
    Capture current state of the page including URL, title, visible text,
    forms, errors, and other relevant information.
    """
    state = {
        "url": driver.current_url,
        "title": driver.title,
        "visible_forms": [],
        "error_messages": [],
        "success_indicators": [],
        "page_hash": "",
        "active_elements": [],
        "form_fields": {},
    }
    
    # Get visible forms
    forms = driver.find_elements(By.TAG_NAME, "form")
    for form in forms:
        if form.is_displayed():
            form_info = {
                "id": form.get_attribute("id") or "",
                "action": form.get_attribute("action") or "",
                "method": form.get_attribute("method") or "",
                "fields": len(form.find_elements(By.TAG_NAME, "input")),
                "buttons": len(form.find_elements(By.TAG_NAME, "button")) + 
                          len(form.find_elements(By.XPATH, ".//input[@type='submit']")),
            }
            state["visible_forms"].append(form_info)
    
    # Look for typical success messages
    success_keywords = [
        "success", "thank you", "successfully", "submitted", "completed", "received",
        "registration complete", "welcome", "congratulations", "confirmed"
    ]
    for keyword in success_keywords:
        elements = driver.find_elements(
            By.XPATH, 
            f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}')]"
        )
        for element in elements:
            if element.is_displayed():
                try:
                    state["success_indicators"].append({
                        "text": element.text,
                        "element": element.tag_name,
                        "class": element.get_attribute("class") or "",
                    })
                except:
                    pass
    
    # Look for error messages
    error_keywords = ["error", "invalid", "failed", "incorrect", "required"]
    for keyword in error_keywords:
        elements = driver.find_elements(
            By.XPATH,
            f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}')]"
        )
        for element in elements:
            if element.is_displayed():
                try:
                    state["error_messages"].append({
                        "text": element.text,
                        "element": element.tag_name,
                        "class": element.get_attribute("class") or ""
                    })
                except:
                    pass
    
    # Also check for elements with error classes
    error_class_elements = driver.find_elements(
        By.CSS_SELECTOR, 
        ".error, .invalid, .validation-error, .has-error, [aria-invalid='true'], .text-danger"
    )
    for element in error_class_elements:
        if element.is_displayed():
            try:
                state["error_messages"].append({
                    "text": element.text,
                    "element": element.tag_name,
                    "class": element.get_attribute("class") or ""
                })
            except:
                pass
    
    # Create a hash of main content
    try:
        content = driver.find_element(By.TAG_NAME, "body").text
        state["page_hash"] = hashlib.md5(content.encode()).hexdigest()
    except:
        state["page_hash"] = ""
        
    # Collect form fields that are still visible
    try:
        input_fields = driver.find_elements(By.TAG_NAME, "input")
        for field in input_fields:
            if field.is_displayed():
                field_name = field.get_attribute("name") or field.get_attribute("id") or ""
                if field_name:
                    state["form_fields"][field_name] = {
                        "type": field.get_attribute("type") or "text",
                        "value": field.get_attribute("value") or "",
                        "disabled": field.get_attribute("disabled") is not None,
                        "readonly": field.get_attribute("readonly") is not None,
                    }
    except:
        pass
        
    return state

def get_state_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare before and after states to determine what changed.
    """
    diff = {
        "url_changed": before["url"] != after["url"],
        "title_changed": before["title"] != after["title"],
        "page_hash_changed": before["page_hash"] != after["page_hash"],
        "forms_disappeared": [],
        "forms_appeared": [],
        "new_success_indicators": [],
        "new_error_messages": [],
        "form_fields_changed": {},
    }
    
    # Check if forms disappeared
    before_form_ids = [form["id"] for form in before["visible_forms"] if form["id"]]
    after_form_ids = [form["id"] for form in after["visible_forms"] if form["id"]]
    
    diff["forms_disappeared"] = [form_id for form_id in before_form_ids if form_id not in after_form_ids]
    diff["forms_appeared"] = [form_id for form_id in after_form_ids if form_id not in before_form_ids]
    
    # Check for new success indicators
    before_success = [indicator["text"] for indicator in before["success_indicators"]]
    for indicator in after["success_indicators"]:
        if indicator["text"] not in before_success:
            diff["new_success_indicators"].append(indicator)
    
    # Check for new error messages
    before_errors = [error["text"] for error in before["error_messages"]]
    for error in after["error_messages"]:
        if error["text"] not in before_errors:
            diff["new_error_messages"].append(error)
    
    # Check for changes in form fields
    for field_name, before_field in before["form_fields"].items():
        if field_name in after["form_fields"]:
            after_field = after["form_fields"][field_name]
            if before_field != after_field:
                diff["form_fields_changed"][field_name] = {
                    "before": before_field,
                    "after": after_field
                }
    
    return diff

def take_screenshot(driver: webdriver.Chrome, file_path: Optional[str] = None) -> Optional[str]:
    """
    Take a screenshot of the current page.
    
    Args:
        driver: WebDriver instance
        file_path: Optional path to save the screenshot
        
    Returns:
        Path to saved screenshot if successful, None otherwise
    """
    try:
        if file_path:
            # Make sure the directory exists
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            return driver.save_screenshot(file_path)
        else:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                driver.save_screenshot(tmp.name)
                return tmp.name
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        return None

def analyze_success(diff: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze the diff to determine if form submission was successful.
    Returns a detailed analysis with confidence level.
    """
    results = {
        "success": False,
        "confidence": 0.0,  # 0.0 to 1.0
        "reasoning": [],
        "errors": [],
    }
    
    confidence_score = 0.0
    confidence_factors = 0
    
    # Check URL change
    if diff["url_changed"]:
        confidence_score += 0.7
        confidence_factors += 1
        results["reasoning"].append("URL changed after submission, likely indicating successful navigation")
    
    # Check page hash change
    if diff["page_hash_changed"]:
        confidence_score += 0.3
        confidence_factors += 1
        results["reasoning"].append("Page content changed after submission")
    
    # Check for disappeared forms
    if diff["forms_disappeared"]:
        confidence_score += 0.8
        confidence_factors += 1
        results["reasoning"].append("Form disappeared after submission, likely indicating successful processing")
    
    # Check for success indicators
    if diff["new_success_indicators"]:
        confidence_score += 1.0
        confidence_factors += 1
        indicator_texts = [ind["text"] for ind in diff["new_success_indicators"]]
        results["reasoning"].append(f"Success messages detected: {', '.join(indicator_texts[:3])}")
    
    # Check for error messages
    if diff["new_error_messages"]:
        confidence_score -= 0.8
        confidence_factors += 1
        error_texts = [err["text"] for err in diff["new_error_messages"]]
        results["errors"].append(f"Error messages detected: {', '.join(error_texts[:3])}")
    
    # Calculate final confidence
    if confidence_factors > 0:
        final_confidence = confidence_score / confidence_factors
        results["confidence"] = max(0.0, min(1.0, final_confidence))  # Clamp between 0 and 1
    
    # Determine success based on confidence threshold
    results["success"] = results["confidence"] >= 0.5
    
    return results

# -----------------------------------------------------------------------------
# Main Tool Functions
# -----------------------------------------------------------------------------

def detect_form_submission_success(
    url: str, 
    submission_steps: List[Dict[str, Any]], 
    wait_time: int = 20,
    screenshot_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detect if a form submission was successful by analyzing page state before and after.
    
    Args:
        url: URL of the form page
        submission_steps: List of steps to submit the form, each with:
            - action: "click", "type", "select", "check", "wait"
            - locator: Element locator (id=x, xpath=y, etc.)
            - value: Value to type/select (for type/select actions)
            - wait: Time to wait after action (optional)
        wait_time: Time to wait for page to load/process after form submission
        screenshot_dir: Directory to save screenshots (optional)
        
    Returns:
        Dictionary with success detection results
    """
    result = {
        "url": url,
        "success": False,
        "confidence": 0.0,
        "reasoning": [],
        "errors": [],
        "screenshots": {
            "before": None,
            "after": None
        },
        "state_diff": {},
        "error": None
    }
    
    driver = None
    try:
        # Initialize the WebDriver
        driver = initialize_webdriver(wait_time)
        
        # Navigate to the URL
        logger.info(f"Visiting form URL: {url}")
        driver.get(url)
        
        # Wait for page to load
        logger.info(f"Waiting for page to load...")
        time.sleep(min(5, wait_time // 4))  # Wait some time to ensure initial page loads
        
        # Take screenshot before
        if screenshot_dir:
            before_screenshot = os.path.join(screenshot_dir, "form_before.png")
            take_screenshot(driver, before_screenshot)
            result["screenshots"]["before"] = before_screenshot
        
        # Capture initial state
        logger.info("Capturing initial page state")
        before_state = get_page_state(driver)
        
        # Execute submission steps
        for i, step in enumerate(submission_steps):
            action = step.get("action", "").lower()
            locator = step.get("locator", "")
            value = step.get("value", "")
            step_wait = step.get("wait", 1)  # Default wait 1 second after each step
            
            logger.info(f"Executing step {i+1}: {action} on {locator}")
            
            # Process different action types
            try:
                # Parse locator
                by_method, locator_value = By.ID, locator  # Default
                
                if locator.startswith("id="):
                    by_method, locator_value = By.ID, locator[3:]
                elif locator.startswith("name="):
                    by_method, locator_value = By.NAME, locator[5:]
                elif locator.startswith("xpath="):
                    by_method, locator_value = By.XPATH, locator[6:]
                elif locator.startswith("css="):
                    by_method, locator_value = By.CSS_SELECTOR, locator[4:]
                elif locator.startswith("//"):
                    by_method, locator_value = By.XPATH, locator
                
                # Wait for element to be present
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((by_method, locator_value))
                )
                
                # Perform action
                if action == "click":
                    WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((by_method, locator_value))
                    ).click()
                    
                elif action == "type":
                    element.clear()
                    element.send_keys(value)
                    
                elif action == "select":
                    from selenium.webdriver.support.ui import Select
                    select = Select(element)
                    
                    # Try different selection methods
                    try:
                        select.select_by_visible_text(value)
                    except:
                        try:
                            select.select_by_value(value)
                        except:
                            try:
                                select.select_by_index(int(value) if value.isdigit() else 0)
                            except:
                                raise Exception(f"Could not select '{value}' from dropdown")
                                
                elif action == "check":
                    if element.is_selected() != (value.lower() in ('true', 'yes', '1')):
                        element.click()
                        
                elif action == "wait":
                    time.sleep(float(value) if value else 1)
                    
                else:
                    raise Exception(f"Unknown action: {action}")
                
                # Wait after action
                time.sleep(step_wait)
                
            except Exception as e:
                logger.error(f"Error executing step {i+1}: {e}")
                result["errors"].append(f"Step {i+1} ({action} on {locator}) failed: {str(e)}")
                # Continue with next step
        
        # Wait for page to process form submission
        logger.info(f"Waiting {wait_time} seconds for form processing")
        time.sleep(wait_time)
        
        # Take screenshot after
        if screenshot_dir:
            after_screenshot = os.path.join(screenshot_dir, "form_after.png")
            take_screenshot(driver, after_screenshot)
            result["screenshots"]["after"] = after_screenshot
        
        # Capture final state
        logger.info("Capturing final page state")
        after_state = get_page_state(driver)
        
        # Analyze state changes
        state_diff = get_state_diff(before_state, after_state)
        result["state_diff"] = state_diff
        
        # Determine success
        success_analysis = analyze_success(state_diff)
        result["success"] = success_analysis["success"]
        result["confidence"] = success_analysis["confidence"]
        result["reasoning"] = success_analysis["reasoning"]
        
        if success_analysis["errors"]:
            result["errors"].extend(success_analysis["errors"])
        
    except Exception as e:
        result["error"] = f"Error: {str(e)}"
        logger.error(f"Form submission detection failed: {e}")
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return result

def generate_robot_form_test(
    url: str,
    form_id: str,
    field_mappings: Dict[str, Dict[str, Any]],
    output_file: str,
    test_name: str = "Test Form Submission",
    wait_time: int = 10
) -> Dict[str, Any]:
    """
    Generate a Robot Framework test for form submission with advanced success detection.
    
    Args:
        url: URL of the form page
        form_id: ID or locator of the form
        field_mappings: Dictionary mapping field locators to test values and actions
        output_file: Path to save the generated Robot Framework test
        test_name: Name for the test case
        wait_time: Time to wait after submission
        
    Returns:
        Dictionary with generation result
    """
    result = {
        "file_path": output_file,
        "error": None
    }
    
    try:
        # Generate Robot Framework test
        robot_content = f"""*** Settings ***
Documentation     Robot Framework test for form submission with advanced success detection
Library           SeleniumLibrary
Library           Collections
Library           String
Library           DateTime
Test Teardown     Close All Browsers

*** Variables ***
${{URL}}                     {url}
${{BROWSER}}                 Chrome
${{FORM_LOCATOR}}            {form_id}
${{WAIT_TIME}}               {wait_time}

*** Test Cases ***
{test_name}
    [Documentation]    Test form submission and verify success
    [Tags]    form    submission    validation
    Open Browser And Navigate
    Fill Form Fields
    Submit Form
    Verify Submission Success

*** Keywords ***
Open Browser And Navigate
    Open Browser    ${{URL}}    ${{BROWSER}}
    Maximize Browser Window
    Wait Until Element Is Visible    ${{FORM_LOCATOR}}    timeout=10s
    # Take screenshot of initial state
    Capture Page Screenshot    before_submission.png

Fill Form Fields
"""
        
        # Add keywords for each field
        for field_name, field_info in field_mappings.items():
            locator = field_info.get("locator", "")
            value = field_info.get("value", "")
            field_type = field_info.get("type", "text").lower()
            
            if field_type == "text" or field_type == "email" or field_type == "password" or field_type == "tel":
                robot_content += f"    Input Text    {locator}    {value}\n"
            elif field_type == "select":
                robot_content += f"    Select From List By Label    {locator}    {value}\n"
            elif field_type == "checkbox":
                if value.lower() in ("true", "yes", "1"):
                    robot_content += f"    Select Checkbox    {locator}\n"
                else:
                    robot_content += f"    Unselect Checkbox    {locator}\n"
            elif field_type == "radio":
                robot_content += f"    Select Radio Button    {field_name}    {value}\n"
        
        # Add form submission and verification
        robot_content += """
Submit Form
    # Store page information before submission
    ${initial_url}=    Get Location
    ${initial_title}=    Get Title
    
    # Get form element count for comparison
    ${form_exists}=    Run Keyword And Return Status    Element Should Be Visible    ${FORM_LOCATOR}
    ${form_fields_before}=    Run Keyword If    ${form_exists}    Get Element Count    ${FORM_LOCATOR} input
    ...    ELSE    Set Variable    0
    
    # Find and click the submit button
    ${submit_btn}=    Run Keyword And Return Status    Element Should Be Visible    ${FORM_LOCATOR} input[type='submit']
    Run Keyword If    ${submit_btn}    Click Element    ${FORM_LOCATOR} input[type='submit']
    ...    ELSE    Click Button    css=${FORM_LOCATOR} button[type='submit']
    
    # Wait for form processing
    Sleep    ${WAIT_TIME}
    Capture Page Screenshot    after_submission.png

Verify Submission Success
    # Check different success indicators
    # 1. Check if URL changed (likely redirect after success)
    ${current_url}=    Get Location
    ${url_changed}=    Run Keyword And Return Status    Should Not Be Equal    ${initial_url}    ${current_url}
    Run Keyword If    ${url_changed}    Log    URL changed after submission, likely successful
    
    # 2. Check for success messages
    @{success_texts}=    Create List    success    thank you    successfully    submitted    completed    received    registration    welcome    confirmed
    ${page_text}=    Get Text    css=body
    ${page_text_lower}=    Convert To Lowercase    ${page_text}
    
    ${success_message_found}=    Set Variable    ${False}
    :FOR    ${success_text}    IN    @{success_texts}
        ${contains_text}=    Run Keyword And Return Status    Should Contain    ${page_text_lower}    ${success_text}
        ${success_message_found}=    Set Variable If    ${contains_text}    ${True}    ${success_message_found}
        Run Keyword If    ${contains_text}    Log    Success message containing '${success_text}' found
    
    # 3. Check if form disappeared (also indicates success)
    ${form_exists_after}=    Run Keyword And Return Status    Element Should Be Visible    ${FORM_LOCATOR}
    ${form_disappeared}=    Run Keyword If    not ${form_exists_after}    Set Variable    ${True}
    ...    ELSE    Set Variable    ${False}
    Run Keyword If    ${form_disappeared}    Log    Form disappeared after submission, likely successful
    
    # Determine overall success based on collected evidence
    ${submission_successful}=    Set Variable    ${False}
    ${submission_successful}=    Set Variable If    ${url_changed} or ${success_message_found} or ${form_disappeared}    ${True}    ${submission_successful}
    
    # Check for error messages that would indicate failure
    @{error_texts}=    Create List    error    invalid    failed    incorrect    required
    ${error_message_found}=    Set Variable    ${False}
    :FOR    ${error_text}    IN    @{error_texts}
        ${contains_error}=    Run Keyword And Return Status    Should Contain    ${page_text_lower}    ${error_text}
        ${error_message_found}=    Set Variable If    ${contains_error}    ${True}    ${error_message_found}
        Run Keyword If    ${contains_error}    Log    Error message containing '${error_text}' found
    
    # Error messages override positive indicators
    ${submission_successful}=    Set Variable If    ${error_message_found}    ${False}    ${submission_successful}
    
    # Final verification
    Should Be True    ${submission_successful}    Form submission was not successful
"""
        
        # Save the file
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(robot_content)
        
        result["file_path"] = os.path.abspath(output_file)
        result["content"] = robot_content
    
    except Exception as e:
        result["error"] = f"Error generating Robot Framework test: {str(e)}"
        logger.error(result["error"])
    
    return result

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register form success detector tools with MCP."""
    
    @mcp.tool()
    async def robot_detect_form_success(
        url: str,
        submission_steps: List[Dict[str, Any]],
        wait_time: int = 20,
        screenshot_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Detect if a form submission was successful through multiple methods.
        
        Args:
            url: URL of the form page
            submission_steps: List of steps to submit the form
            wait_time: Time to wait after submission
            screenshot_dir: Directory to save screenshots (optional)
            
        Returns:
            Dict with success detection results
        """
        return detect_form_submission_success(url, submission_steps, wait_time, screenshot_dir)
    
    @mcp.tool()
    async def robot_generate_smart_form_test(
        url: str,
        form_id: str,
        field_mappings: Dict[str, Dict[str, Any]],
        output_file: str,
        test_name: str = "Test Form Submission",
        wait_time: int = 10
    ) -> Dict[str, Any]:
        """
        Generate a Robot Framework test for form submission with advanced success detection.
        
        Args:
            url: URL of the form page
            form_id: ID or locator of the form
            field_mappings: Dictionary mapping field locators to test values
            output_file: Path to save the generated test
            test_name: Name for the test case
            wait_time: Time to wait after submission
            
        Returns:
            Dict with generation result
        """
        return generate_robot_form_test(
            url, form_id, field_mappings, output_file, test_name, wait_time
        )

if __name__ == "__main__":
    # For direct testing of the tool
    import argparse
    
    parser = argparse.ArgumentParser(description="Test the form success detector tool")
    parser.add_argument("--url", required=True, help="URL of the form to test")
    parser.add_argument("--output", help="Path to save the test file")
    
    args = parser.parse_args()
    
    # Define simple test steps
    test_steps = [
        {"action": "type", "locator": "id=email", "value": "test@example.com"},
        {"action": "type", "locator": "id=password", "value": "Password123"},
        {"action": "click", "locator": "//button[@type='submit']"}
    ]
    
    result = detect_form_submission_success(
        args.url, 
        test_steps, 
        wait_time=10,
        screenshot_dir="."
    )
    
    print(f"Success: {result['success']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print("Reasoning:")
    for reason in result['reasoning']:
        print(f"- {reason}")
    if result['errors']:
        print("Errors:")
        for error in result['errors']:
            print(f"- {error}")
            
    if args.output:
        # Example field mappings
        field_mappings = {
            "email": {"locator": "id=email", "value": "test@example.com", "type": "email"},
            "password": {"locator": "id=password", "value": "Password123", "type": "password"}
        }
        generate_robot_form_test(
            args.url, 
            "//form", 
            field_mappings, 
            args.output
        )
        print(f"Generated test saved to {args.output}") 