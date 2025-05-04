#!/bin/bash
set -e

echo "Setting up Chrome and ChromeDriver permissions..."

# Start Xvfb
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1280x1024x24 -ac &

# Wait for Xvfb to start
sleep 1

# Create ChromeDriver cache directory if it doesn't exist
mkdir -p /app/.wdm/drivers
mkdir -p /app/.cache/selenium/chromedriver
chmod -R 777 /app/.wdm
chmod -R 777 /app/.cache

# Print Chrome version for debugging
echo "Chrome version:"
google-chrome --version

echo "Starting application..."
# Run the application
exec python main.py 