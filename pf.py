"""
Enhanced UI Profile Creator - With Real-Time Cursor Tracker

This tool allows users to:
1. Create and manage menu/screen definitions with detection conditions
2. Define UI elements within each menu/screen
3. Save and load profile data as JSON files
4. Use a floating cursor tracker to see real-time color and coordinates

Uses wxPython for a simple, reliable interface.
"""

import sys

# Try importing wx first at the module level
try:
    import wx
    print("wxPython imported at module level")
except ImportError as e:
    print("ERROR: Failed to import wxPython:", e)
    print("Please install wxPython with: pip install wxPython")
    sys.exit(1)

# Now import the rest of our modules
from pflib.profile_editor import ProfileEditorFrame
from pflib.utils import APP_TITLE, APP_VERSION, get_cursor_tracker

def main():
    """Main entry point for the application"""
    # Explicitly declare wx as global to ensure it's accessible
    global wx
    
    print("Inside main function, wx is:", wx)
    
    # Create the wx application
    app = wx.App()
    
    # Import wx.adv after app is created
    try:
        import wx.adv
        print("wx.adv imported successfully")
    except ImportError:
        print("Warning: wx.adv module not available, will use fallback")
    
    # Initialize global cursor tracker
    global_cursor_tracker = get_cursor_tracker()
    
    # Create and show the main application frame
    frame = ProfileEditorFrame(None, APP_TITLE)
    frame.Show()
    
    # Start the main event loop
    print("Starting wxPython main loop")
    app.MainLoop()

if __name__ == "__main__":
    print("Starting application")
    main()