#!/bin/bash
# Script to set up all browser tool directories for Robot Framework

# List of browser tools to create
TOOLS=(
    "robot_browser_navigate"
    "robot_browser_snapshot"
    "robot_browser_click"
    "robot_browser_drag"
    "robot_browser_hover"
    "robot_browser_type"
    "robot_browser_select_option"
    "robot_browser_screenshot"
    "robot_browser_back"
    "robot_browser_forward"
    "robot_browser_tab_list"
    "robot_browser_tab_new"
    "robot_browser_tab_select"
    "robot_browser_tab_close"
    "robot_browser_console"
    "robot_browser_upload"
    "robot_browser_pdf"
    "robot_browser_close"
    "robot_browser_wait"
    "robot_browser_resize"
    "robot_browser_press_key"
    "robot_browser_network"
    "robot_browser_dialog"
)

# Create directories and add __init__.py files
for tool in "${TOOLS[@]}"; do
    echo "Creating directory for $tool..."
    mkdir -p "src/mcp_tools/$tool"
    
    # Create __init__.py
    cat > "src/mcp_tools/$tool/__init__.py" << EOF
from .tool import register_tool

__all__ = ["register_tool"]
EOF
    
    echo "Created $tool directory and __init__.py"
done

echo "Browser tool directories have been set up successfully."
echo "Remember to implement the actual tool.py files in each directory." 