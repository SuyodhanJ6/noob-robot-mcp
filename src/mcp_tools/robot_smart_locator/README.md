# Enhanced Robot Smart Locator

This advanced tool consolidates and enhances multiple separate tools, providing a unified solution for element location, authentication, and form automation in web testing.

## What This Tool Replaces

The Enhanced Smart Locator replaces the following tools:

1. `robot_auto_locator` - Basic locator finder
2. `robot_form_locator` - Form-specific element locator
3. `robot_xpath_locator` - XPath-specific locator
4. `robot_auth_handler` - Authentication handling
5. `robot_form_automator` - Form automation capabilities

## Key Features

- **Dynamic Locator Strategy**: Automatically finds the most robust locator for any element
- **Resilient to Website Changes**: Generates multiple backup locators that can adapt when websites change
- **Authentication Handling**: Built-in support for handling login processes
- **Form Detection**: Automatically detects form fields and generates appropriate locators
- **Multiple Strategy Approach**: Uses JavaScript, accessibility attributes, and relative positioning to find elements

## Usage Examples

### Finding a Smart Locator

```python
result = await robot_find_smart_locator(
    url="https://example.com/login",
    element_description="Sign In button",
    wait_time=10
)

print(f"Recommended locator: {result['recommended_locator']}")
```

### With Authentication

```python
result = await robot_find_smart_locator(
    url="https://example.com/dashboard",
    element_description="Add User button",
    need_login=True,
    login_url="https://example.com/login",
    username="admin",
    password="password123",
    username_locator="id=username",
    password_locator="id=password",
    submit_locator="xpath=//button[contains(text(), 'Login')]",
    success_indicator="xpath=//div[@class='dashboard-header']"
)
```

### Form Detection

```python
form_fields = await robot_detect_form(
    url="https://example.com/signup",
    wait_time=10
)

print("Detected form fields:")
for field_name, field_info in form_fields["detected_fields"].items():
    print(f"- {field_name}: {field_info['locator']}")
```

### Form Automation

```python
result = await robot_fill_form(
    url="https://example.com/contact",
    form_data={
        "id=name": "John Doe",
        "id=email": "john@example.com",
        "id=message": "Hello, this is a test message"
    },
    submit_locator="id=submit-btn",
    wait_success_element="xpath=//div[contains(@class, 'success-message')]",
    wait_success_time=5
)
```

### Generate Dynamic Locators

```python
result = await robot_find_dynamic_locator(
    url="https://example.com/products",
    css_selector=".product-card:first-child .add-to-cart", 
    wait_time=10
)

print("Alternative locators:")
for locator in result["dynamic_locators"]:
    print(f"- {locator['locator']} (reliability: {locator['reliability']}%)")
```

### Evaluate Locator Robustness

```python
result = await robot_evaluate_locator_robustness(
    url="https://example.com/products",
    locator="xpath=//button[contains(text(), 'Add to Cart')]",
    wait_time=5
)

print(f"Is robust: {result['is_robust']}")
print(f"Reliability score: {result['reliability_score']}")
print("Suggestions:")
for suggestion in result["suggestions"]:
    print(f"- {suggestion}")
```

## Benefits

1. **Simplified Codebase**: Eliminates the need for multiple redundant tools
2. **Better Robustness**: Finds the most stable elements across changing websites
3. **Comprehensive Solution**: Handles everything from finding elements to authentication
4. **Improved Maintainability**: Consolidates code in a single place
5. **Enhanced Adaption**: Generates multiple alternatives when websites change

## Technical Implementation Details

- Uses multiple strategies (JavaScript, accessibility, relative positioning) to locate elements
- Implements smart XPath normalization to avoid common syntax errors
- Provides comprehensive element attribute collection
- Adapts dynamically to different website structures
- Handles authentication seamlessly when needed 