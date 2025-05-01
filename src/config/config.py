#!/usr/bin/env python
"""
Configuration settings for Robot Framework MCP tools
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent

# Create necessary directories
LOGS_DIR = BASE_DIR / 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)

ROBOT_OUTPUT_DIR_PATH = BASE_DIR / "output"
os.makedirs(ROBOT_OUTPUT_DIR_PATH, exist_ok=True)

ROBOT_REPORT_DIR_PATH = BASE_DIR / "reports"
os.makedirs(ROBOT_REPORT_DIR_PATH, exist_ok=True)

# MCP Server settings
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "3007"))
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/sse"

# CORS Settings
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# Robot Framework settings
ROBOT_OUTPUT_DIR = os.getenv("ROBOT_OUTPUT_DIR", str(ROBOT_OUTPUT_DIR_PATH))
ROBOT_REPORT_DIR = os.getenv("ROBOT_REPORT_DIR", str(ROBOT_REPORT_DIR_PATH))

# Default settings
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", "30"))
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "100"))

# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': 'DEBUG',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.FileHandler',
            'formatter': 'standard',
            'level': 'DEBUG',
            'filename': str(LOGS_DIR / 'robot_mcp_server.log'),
            'mode': 'a'
        }
    },
    'loggers': {
        'robot_mcp_server': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True
        },
        'robot_tool': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True
        }
    }
}

# Tool specific settings
TEST_FILE_EXTENSIONS = ['.robot', '.resource']
REPORT_FORMATS = ['html', 'xml', 'json']
LINTER_RULES = {
    'line_length': 100,
    'keyword_naming': r'^[A-Z][a-zA-Z0-9 ]+$',
    'test_naming': r'^[A-Z][a-zA-Z0-9 ]+$',
    'variable_naming': r'^[A-Z_][A-Z0-9_]*$',
}

# API and service settings
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_URL = os.getenv("JIRA_URL", "")
JENKINS_URL = os.getenv("JENKINS_URL", "")
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN", "")

# System prompts for AI-assisted tools
SYSTEM_PROMPTS = {
    'test_creator': """
    You are a Robot Framework test creation assistant. Your job is to create high-quality, 
    maintainable test cases based on the user's requirements. Focus on these key aspects:
    
    1. Clear test case structure and naming
    2. Proper keyword usage and arguments
    3. Effective separation of concerns
    4. Good variable management
    
    Create tests that follow best practices and are easy to maintain.
    """,
    
    'automated_feedback': """
    You are a Robot Framework code quality analyzer. Your job is to provide constructive 
    feedback on test scripts to improve their quality, readability, and maintainability.
    Focus on:
    
    1. Code structure and organization
    2. Test case and keyword naming
    3. Potential duplications or redundancies
    4. Variable usage and management
    
    Provide specific, actionable feedback that helps improve the test code.
    """
}

# Error messages
ERROR_MESSAGES = {
    'file_not_found': "Error: File '{file}' not found",
    'invalid_file_format': "Error: File '{file}' is not a valid Robot Framework file",
    'execution_error': "Error executing Robot Framework command: {error}",
    'timeout_error': "Error: Operation timed out after {timeout} seconds",
    'permission_error': "Error: Permission denied for file '{file}'",
    'api_not_enabled': "{api_name} API access is not configured. Set {env_var} in environment variables."
}
