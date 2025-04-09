"""
Utilities for the Profile Creator application
"""

import wx

# Constants for application
APP_TITLE = "UI Profile Creator"
APP_VERSION = "1"

# Global cursor tracker instance
global_cursor_tracker = None

def get_cursor_tracker():
    """
    Get or create the global cursor tracker instance
    
    Returns:
        CursorTracker: The global cursor tracker instance
    """
    global global_cursor_tracker
    
    # Avoid circular import by importing here
    from pflib.ui_components import CursorTracker
    
    if global_cursor_tracker is None or not wx.GetApp():
        global_cursor_tracker = CursorTracker()
    return global_cursor_tracker