"""
Browser Installation Module - For installing and setting up browser drivers.
"""

from . import tool  # Import the tool module
from .tool import register_tool

__all__ = ["register_tool"] 