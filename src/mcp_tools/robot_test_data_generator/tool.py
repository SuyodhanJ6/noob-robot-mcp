#!/usr/bin/env python
"""
MCP Tool: Robot Test Data Generator
Generates test data for Robot Framework test cases (e.g., form input, search queries, etc.).
"""

import logging
import random
import string
import re
import json
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger('robot_tool.test_data_generator')

# -----------------------------------------------------------------------------
# Request and Response Models
# -----------------------------------------------------------------------------

class DataGeneratorRequest(BaseModel):
    """Request model for robot_test_data_generator tool."""
    data_type: str = Field(
        ...,
        description="Type of data to generate (e.g., 'username', 'email', 'password', 'name', 'address', 'phone', 'date', 'number', 'text', 'custom')"
    )
    count: int = Field(
        1,
        description="Number of data items to generate"
    )
    format_pattern: Optional[str] = Field(
        None,
        description="Custom format pattern for the data (for 'custom' data_type)"
    )
    min_value: Optional[Union[int, float, str]] = Field(
        None,
        description="Minimum value for numeric data or minimum length for text data"
    )
    max_value: Optional[Union[int, float, str]] = Field(
        None,
        description="Maximum value for numeric data or maximum length for text data"
    )
    prefix: Optional[str] = Field(
        None,
        description="Prefix to add to generated data"
    )
    suffix: Optional[str] = Field(
        None,
        description="Suffix to add to generated data"
    )
    template: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON template for complex test data with placeholders"
    )

class DataGeneratorResponse(BaseModel):
    """Response model for robot_test_data_generator tool."""
    data: List[Any] = Field(
        default_factory=list,
        description="Generated test data"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if an error occurred"
    )

# -----------------------------------------------------------------------------
# Tool Implementation
# -----------------------------------------------------------------------------

def generate_test_data(
    data_type: str,
    count: int = 1,
    format_pattern: Optional[str] = None,
    min_value: Optional[Union[int, float, str]] = None,
    max_value: Optional[Union[int, float, str]] = None,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    template: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate test data for Robot Framework test cases.
    
    Args:
        data_type: Type of data to generate
        count: Number of data items to generate
        format_pattern: Custom format pattern for the data
        min_value: Minimum value/length
        max_value: Maximum value/length
        prefix: Prefix to add to generated data
        suffix: Suffix to add to generated data
        template: JSON template for complex test data with placeholders
        
    Returns:
        Dictionary with generated data and any error
    """
    result = {
        "data": [],
        "error": None
    }
    
    try:
        # Input validation
        if count < 1:
            return {"data": [], "error": "Count must be at least 1"}
        
        for _ in range(count):
            generated_value = None
            
            # Handle different data types
            if data_type == "username":
                generated_value = generate_username(min_value, max_value)
            elif data_type == "email":
                generated_value = generate_email()
            elif data_type == "password":
                generated_value = generate_password(min_value, max_value)
            elif data_type == "name":
                generated_value = generate_name()
            elif data_type == "address":
                generated_value = generate_address()
            elif data_type == "phone":
                generated_value = generate_phone()
            elif data_type == "date":
                generated_value = generate_date(min_value, max_value)
            elif data_type == "number":
                generated_value = generate_number(min_value, max_value)
            elif data_type == "text":
                generated_value = generate_text(min_value, max_value)
            elif data_type == "custom" and format_pattern:
                generated_value = generate_custom_format(format_pattern)
            elif template:
                generated_value = process_template(template)
            else:
                return {"data": [], "error": f"Unsupported data type: {data_type}"}
            
            # Apply prefix/suffix if provided
            if prefix:
                generated_value = f"{prefix}{generated_value}"
            if suffix:
                generated_value = f"{generated_value}{suffix}"
                
            result["data"].append(generated_value)
            
        logger.info(f"Generated {count} items of {data_type} test data")
        return result
        
    except Exception as e:
        error_msg = f"Error generating test data: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "data": result["data"],
            "error": error_msg
        }

def generate_username(min_length=None, max_length=None):
    """Generate a random username."""
    min_len = 6 if min_length is None else int(min_length)
    max_len = 12 if max_length is None else int(max_length)
    length = random.randint(min_len, max_len)
    
    prefixes = ["user", "test", "qa", "dev", "admin"]
    prefix = random.choice(prefixes)
    
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length-len(prefix)))
    return f"{prefix}{suffix}"

def generate_email():
    """Generate a random email address."""
    domains = ["example.com", "test.org", "qa.dev", "robot.io", "autotest.net"]
    username = generate_username()
    domain = random.choice(domains)
    return f"{username}@{domain}"

def generate_password(min_length=None, max_length=None):
    """Generate a random password."""
    min_len = 8 if min_length is None else int(min_length)
    max_len = 16 if max_length is None else int(max_length)
    length = random.randint(min_len, max_len)
    
    chars = string.ascii_letters + string.digits + "!@#$%^&*()_-+=<>?"
    return ''.join(random.choices(chars, k=length))

def generate_name():
    """Generate a random full name."""
    first_names = ["John", "Jane", "Bob", "Alice", "Mike", "Sarah", "David", "Emma", "Chris", "Lisa"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Anderson", "Taylor"]
    
    first = random.choice(first_names)
    last = random.choice(last_names)
    return f"{first} {last}"

def generate_address():
    """Generate a random address."""
    street_numbers = [str(random.randint(1, 9999)) for _ in range(10)]
    street_names = ["Main St", "Oak Ave", "Maple Rd", "Washington Blvd", "Park Lane"]
    cities = ["Springfield", "Rivertown", "Lakeside", "Mountainview", "Brookfield"]
    states = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]
    zip_codes = [f"{random.randint(10000, 99999)}" for _ in range(10)]
    
    street_num = random.choice(street_numbers)
    street = random.choice(street_names)
    city = random.choice(cities)
    state = random.choice(states)
    zip_code = random.choice(zip_codes)
    
    return f"{street_num} {street}, {city}, {state} {zip_code}"

def generate_phone():
    """Generate a random phone number."""
    area_code = random.randint(100, 999)
    prefix = random.randint(100, 999)
    line = random.randint(1000, 9999)
    return f"({area_code}) {prefix}-{line}"

def generate_date(min_date=None, max_date=None):
    """Generate a random date."""
    today = datetime.now().date()
    
    # Default range: 30 days in past to 30 days in future
    days_min = -30 if min_date is None else int(min_date)
    days_max = 30 if max_date is None else int(max_date)
    
    days_diff = random.randint(days_min, days_max)
    result_date = today + timedelta(days=days_diff)
    return result_date.strftime("%Y-%m-%d")

def generate_number(min_val=None, max_val=None):
    """Generate a random number."""
    min_value = 0 if min_val is None else float(min_val)
    max_value = 100 if max_val is None else float(max_val)
    
    # Handle integers vs floats
    if min_value.is_integer() and max_value.is_integer():
        return random.randint(int(min_value), int(max_value))
    else:
        return round(random.uniform(min_value, max_value), 2)

def generate_text(min_length=None, max_length=None):
    """Generate random text."""
    min_len = 10 if min_length is None else int(min_length)
    max_len = 50 if max_length is None else int(max_length)
    length = random.randint(min_len, max_len)
    
    words = ["lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", 
             "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore", 
             "et", "dolore", "magna", "aliqua"]
    
    result = []
    while len(' '.join(result)) < length:
        result.append(random.choice(words))
    
    return ' '.join(result)[:length]

def generate_custom_format(pattern):
    """Generate data using a custom format pattern."""
    result = pattern
    
    # Replace placeholders
    placeholder_patterns = {
        "{{name}}": generate_name,
        "{{email}}": generate_email,
        "{{username}}": generate_username,
        "{{password}}": generate_password,
        "{{date}}": generate_date,
        "{{phone}}": generate_phone,
        "{{number}}": generate_number,
        "{{address}}": generate_address,
        "{{text}}": generate_text
    }
    
    # Additional pattern for random digits or letters of specific length
    digit_pattern = re.compile(r"{{digits\((\d+)\)}}")
    letter_pattern = re.compile(r"{{letters\((\d+)\)}}")
    
    # Replace named placeholders
    for placeholder, generator in placeholder_patterns.items():
        if placeholder in result:
            result = result.replace(placeholder, str(generator()))
    
    # Replace digit patterns
    for match in digit_pattern.finditer(result):
        length = int(match.group(1))
        digits = ''.join(random.choices(string.digits, k=length))
        result = result.replace(match.group(0), digits)
    
    # Replace letter patterns
    for match in letter_pattern.finditer(result):
        length = int(match.group(1))
        letters = ''.join(random.choices(string.ascii_letters, k=length))
        result = result.replace(match.group(0), letters)
    
    return result

def process_template(template):
    """Process a template with placeholders for complex data structures."""
    if isinstance(template, dict):
        result = {}
        for key, value in template.items():
            result[key] = process_template(value)
        return result
    elif isinstance(template, list):
        return [process_template(item) for item in template]
    elif isinstance(template, str):
        # Check if the string is a placeholder
        if template.startswith("{{") and template.endswith("}}"):
            placeholder = template[2:-2]  # Remove {{ and }}
            
            # Check for placeholder with parameters
            if "(" in placeholder and ")" in placeholder:
                func_name, params_str = placeholder.split("(", 1)
                params_str = params_str.rstrip(")")
                params = [p.strip() for p in params_str.split(",")]
                
                # Call appropriate generator based on function name
                if func_name == "username":
                    return generate_username(*params)
                elif func_name == "email":
                    return generate_email()
                elif func_name == "password":
                    return generate_password(*params)
                elif func_name == "name":
                    return generate_name()
                elif func_name == "date":
                    return generate_date(*params)
                elif func_name == "number":
                    return generate_number(*params)
                elif func_name == "text":
                    return generate_text(*params)
                else:
                    return template  # Unknown function
            else:
                # Simple placeholder without parameters
                if placeholder == "username":
                    return generate_username()
                elif placeholder == "email":
                    return generate_email()
                elif placeholder == "password":
                    return generate_password()
                elif placeholder == "name":
                    return generate_name()
                elif placeholder == "date":
                    return generate_date()
                elif placeholder == "number":
                    return generate_number()
                elif placeholder == "text":
                    return generate_text()
                else:
                    return template  # Unknown placeholder
        else:
            return template  # Not a placeholder
    else:
        return template  # Not a string, list, or dict

# -----------------------------------------------------------------------------
# MCP Tool Registration
# -----------------------------------------------------------------------------

def register_tool(mcp: FastMCP):
    """Register the tool with the MCP server."""
    
    @mcp.tool()
    async def robot_test_data_generator(request: DataGeneratorRequest) -> DataGeneratorResponse:
        """
        Generate test data for Robot Framework test cases.
        
        Args:
            request: The request containing data generation parameters
            
        Returns:
            Response with generated data and any error
        """
        logger.info(f"Received request to generate {request.count} items of {request.data_type} test data")
        
        try:
            result = generate_test_data(
                data_type=request.data_type,
                count=request.count,
                format_pattern=request.format_pattern,
                min_value=request.min_value,
                max_value=request.max_value,
                prefix=request.prefix,
                suffix=request.suffix,
                template=request.template
            )
            
            return DataGeneratorResponse(
                data=result["data"],
                error=result["error"]
            )
            
        except Exception as e:
            error_msg = f"Error in robot_test_data_generator: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return DataGeneratorResponse(data=[], error=error_msg) 