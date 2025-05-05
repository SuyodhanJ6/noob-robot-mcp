import logging
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

# Try to import webdriver_manager
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)

class BrowserManager:
    _instance: Optional[webdriver.Chrome] = None
    _session_active: bool = False

    @classmethod
    def get_driver(cls) -> webdriver.Chrome:
        """Gets the current WebDriver instance or initializes a new one."""
        if cls._instance is None or not cls._is_driver_active():
            logger.info("No active WebDriver instance found. Initializing a new one.")
            cls._instance = cls._initialize_webdriver()
            if cls._instance:
                cls._session_active = True
            else:
                cls._session_active = False
                raise WebDriverException("Failed to initialize WebDriver.")
        
        # Check again if initialization succeeded
        if not cls._instance:
             raise WebDriverException("WebDriver instance is None after attempting initialization.")

        return cls._instance

    @classmethod
    def _initialize_webdriver(cls) -> Optional[webdriver.Chrome]:
        """Initializes the Chrome WebDriver."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        driver = None
        last_error = None

        try:
            if WEBDRIVER_MANAGER_AVAILABLE:
                logger.info("Trying WebDriver Manager initialization")
                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=chrome_options
                )
            else:
                logger.info("Trying direct WebDriver initialization (requires chromedriver in PATH)")
                service = Service()
                driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            last_error = str(e)
            logger.warning(f"WebDriver initialization failed: {e}")

        if driver is None:
            logger.error(f"WebDriver initialization failed. Last error: {last_error}")
        
        return driver

    @classmethod
    def _is_driver_active(cls) -> bool:
        """Checks if the current WebDriver instance is still active."""
        if cls._instance is None or not cls._session_active:
            return False
        try:
            # Accessing current_url is a lightweight way to check session status
            _ = cls._instance.current_url 
            return True
        except WebDriverException as e:
            logger.warning(f"WebDriver session seems inactive: {e}")
            cls._session_active = False
            cls._instance = None # Clear the instance if it's dead
            return False
        except Exception as e: # Catch other potential errors during check
            logger.error(f"Unexpected error checking WebDriver status: {e}")
            cls._session_active = False
            cls._instance = None
            return False


    @classmethod
    def close_driver(cls):
        """Closes the WebDriver instance if it exists and is active."""
        if cls._instance and cls._session_active:
            logger.info("Closing WebDriver instance.")
            try:
                cls._instance.quit()
            except WebDriverException as e:
                logger.warning(f"Error quitting WebDriver: {e}")
            finally:
                 cls._instance = None
                 cls._session_active = False
        else:
            logger.info("No active WebDriver instance to close.")

# Optional: Create an instance for easy import
# browser_manager = BrowserManager() 
# Using class methods is generally simpler for this singleton pattern

# Example usage (within another tool):
# from .robot_browser_manager import BrowserManager
# driver = BrowserManager.get_driver()
# driver.get("http://example.com")
# # ... do stuff ...
# BrowserManager.close_driver() # Call this from the close tool 