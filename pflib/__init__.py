"""
Profile Creator Library Package

This package contains modules for the Enhanced UI Profile Creator application.
"""

# Version information
__version__ = "1"

# Import key components to simplify importing from the package
from pflib.utils import APP_TITLE, APP_VERSION
from pflib.ui_components import ColorDisplay, CursorTracker
from pflib.profile_editor import ProfileEditorFrame
from pflib.menu_condition import MenuCondition
from pflib.menu_panel import MenuPanel