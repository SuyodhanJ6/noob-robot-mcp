# Robot MCP Tools

## Enhanced Smart Locator

The `robot_smart_locator` tool is an enhanced, all-in-one solution for dynamic element location, authentication handling, and form automation. It replaces several individual tools to simplify the codebase and provide more robust functionality.

### Features:

- **Dynamic Locator Finding**: Automatically finds the best locators for elements that adapt to website changes
- **Authentication Handling**: Manages login workflows for accessing protected pages
- **Form Detection and Automation**: Identifies form fields and automates filling and submission
- **Resilient Locator Evaluation**: Analyzes locator quality and suggests improvements

### Important: Tools to Remove

The following tools have been consolidated into the enhanced smart locator and should be removed from your server.py imports:

```python
# REMOVE these imports from server.py
from src.mcp_tools.robot_auto_locator.tool import register_tool as register_auto_locator
from src.mcp_tools.robot_form_locator.tool import register_tool as register_form_locator
from src.mcp_tools.robot_xpath_locator.tool import register_tool as register_xpath_locator
from src.mcp_tools.robot_auth_handler.tool import register_tool as register_auth_handler
from src.mcp_tools.robot_form_automator.tool import register_tool as register_form_automator

# KEEP this import (enhanced version)
from src.mcp_tools.robot_smart_locator.tool import register_tool as register_smart_locator
```

### Available Tools:

1. `robot_find_smart_locator`: Find dynamic, resilient locators for elements using description
2. `robot_find_dynamic_locator`: Generate multiple resilient locators for an element specified by CSS selector
3. `robot_evaluate_locator_robustness`: Evaluate a locator for robustness and reliability
4. `robot_authenticate_page`: Handle authentication on websites
5. `robot_detect_form`: Detect form fields with dynamic locator generation
6. `robot_fill_form`: Fill and submit forms using dynamic locators

### Example Usage:

```python
# Find a dynamic locator for a login button
result = await robot_find_smart_locator(
    url="https://example.com", 
    element_description="Login button"
)

# Handle login and then find an element on a protected page
result = await robot_find_smart_locator(
    url="https://example.com/dashboard",
    element_description="User profile picture",
    need_login=True,
    login_url="https://example.com/login",
    username="test_user",
    password="password123",
    username_locator="id=username",
    password_locator="id=password",
    submit_locator="xpath=//button[contains(text(), 'Login')]"
)

# Detect and fill a form
form_fields = await robot_detect_form(url="https://example.com/contact")
form_data = {
    form_fields["detected_fields"]["name"]["locator"]: "John Doe",
    form_fields["detected_fields"]["email"]["locator"]: "john@example.com",
    form_fields["detected_fields"]["message"]["locator"]: "Hello world!"
}
result = await robot_fill_form(
    url="https://example.com/contact",
    form_data=form_data,
    submit_locator=form_fields["detected_submit"]
)
``` 