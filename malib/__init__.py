"""
MenuAccess Library Package

This package contains modules for the Accessible Menu Navigation application.
"""

# Version information
__version__ = "1.0"

# Import key components to simplify importing from the package
from malib.utils import setup_logging
from malib.screen_capture import ScreenCapture
from malib.condition_checker import MenuConditionChecker
from malib.navigator import AccessibleMenuNavigator
