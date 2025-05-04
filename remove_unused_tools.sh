#!/bin/bash
# Script to remove unused tool directories

# List of tools to keep (essential tools and new browser tools)
KEEP_TOOLS=(
    "robot_agent_prompt"
    "robot_form_automator"
    "robot_form_locator"
    "robot_xpath_locator"
    "robot_smart_locator"
    "robot_page_snapshot"
    "robot_dropdown_handler"
    "robot_form_success_detector"
    "robot_runner"
    "robot_test_reader"
    "robot_library_explorer"
    "robot_visualization"
    "robot_log_parser"
    "robot_test_data_generator"
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

# Create a function to check if a tool should be kept
should_keep() {
    local tool=$1
    for keep_tool in "${KEEP_TOOLS[@]}"; do
        if [ "$tool" = "$keep_tool" ]; then
            return 0 # True
        fi
    done
    return 1 # False
}

# Process each directory in the src/mcp_tools directory
echo "Checking for tools to remove..."
for tool_dir in src/mcp_tools/*/; do
    # Extract the directory name
    tool_name=$(basename "$tool_dir")
    
    # Skip the __pycache__ directory
    if [ "$tool_name" = "__pycache__" ]; then
        continue
    fi
    
    # Check if the tool should be kept
    if should_keep "$tool_name"; then
        echo "Keeping $tool_name"
    else
        echo "Removing $tool_name..."
        rm -rf "$tool_dir"
        echo "Removed $tool_name"
    fi
done

echo "Unused tool directories have been removed." 