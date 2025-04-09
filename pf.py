"""
Enhanced UI Profile Creator - With Real-Time Cursor Tracker

This tool allows users to:
1. Create and manage menu/screen definitions with detection conditions
2. Define UI elements within each menu/screen
3. Save and load profile data as JSON files
4. Use a floating cursor tracker to see real-time color and coordinates

Uses wxPython for a simple, reliable interface.
"""

import wx
import json
import os
import pyautogui
import numpy as np
from PIL import Image
import wx.lib.scrolledpanel as scrolled
from pynput import keyboard
import threading
import time

# Constants for application
APP_TITLE = "Enhanced UI Profile Creator"
APP_VERSION = "1.2"

# Make ColorDisplay class available globally
class ColorDisplay(wx.Panel):
    """Panel that displays a color with label"""
    
    def __init__(self, parent, id=wx.ID_ANY, initial_color=(255, 255, 255)):
        super().__init__(parent, id, size=(-1, 30))
        self.color = initial_color
        self.SetBackgroundColour(wx.Colour(*initial_color))
        
        # Add a border
        self.SetWindowStyle(wx.BORDER_SIMPLE)
        
        # Bind paint event to show RGB values
        self.Bind(wx.EVT_PAINT, self.on_paint)
    
    def on_paint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetSize()
        
        # Set text color to be visible on the background
        r, g, b = self.color
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_color = wx.BLACK if brightness > 128 else wx.WHITE
        
        dc.SetTextForeground(text_color)
        color_text = f"RGB: {self.color[0]}, {self.color[1]}, {self.color[2]}"
        
        # Center the text
        text_width, text_height = dc.GetTextExtent(color_text)
        x = (w - text_width) // 2
        y = (h - text_height) // 2
        
        dc.DrawText(color_text, x, y)
    
    def GetColor(self):
        return self.color
    
    def SetColor(self, color):
        self.color = color
        self.SetBackgroundColour(wx.Colour(*color))
        self.Refresh()  # Force a repaint to update the text


class CursorTracker(wx.Frame):
    """
    Floating window that tracks the cursor and shows info about the pixel under it
    """
    def __init__(self, parent=None):
        super().__init__(
            parent, 
            style=wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP | wx.BORDER_SIMPLE,
            size=(300, 180)
        )
        
        # Setup window appearance
        self.SetBackgroundColour(wx.Colour(50, 50, 50))
        
        # Create panel with border
        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(50, 50, 50))
        
        # Create main sizer with padding
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add title/header
        title = wx.StaticText(panel, label="Cursor Info")
        title.SetForegroundColour(wx.WHITE)
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        main_sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER, 8)
        
        # Add separator line
        line = wx.StaticLine(panel, style=wx.LI_HORIZONTAL)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        
        # Create content area
        content_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Position text with proper spacing
        self.pos_text = wx.StaticText(panel, label="Position: (0, 0)")
        self.pos_text.SetForegroundColour(wx.WHITE)
        self.pos_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        content_sizer.Add(self.pos_text, 0, wx.ALL, 8)
        
        # Color section
        color_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Color label
        color_label = wx.StaticText(panel, label="Color:")
        color_label.SetForegroundColour(wx.WHITE)
        color_label.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        color_sizer.Add(color_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        
        # Color display with border
        self.color_display = wx.Panel(panel, size=(-1, 50))
        self.color_display.SetBackgroundColour(wx.WHITE)
        color_sizer.Add(self.color_display, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        
        # RGB value text
        self.rgb_text = wx.StaticText(panel, label="RGB: (0, 0, 0)")
        self.rgb_text.SetForegroundColour(wx.WHITE)
        self.rgb_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        color_sizer.Add(self.rgb_text, 0, wx.ALL, 8)
        
        # Add color section to content area
        content_sizer.Add(color_sizer, 0, wx.EXPAND)
        
        # Add content to main sizer
        main_sizer.Add(content_sizer, 1, wx.EXPAND)
        
        # Set panel sizer
        panel.SetSizer(main_sizer)
        
        # Fit sizer to ensure proper layout
        main_sizer.Fit(self)
        
        # Setup timer for tracking cursor
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        
        # Track active state
        self.is_active = False
        
        # Start hidden
        self.Hide()
    
    def start_tracking(self):
        """Start tracking the cursor"""
        self.timer.Start(50)  # Update 20 times per second
        self.is_active = True
        
        # Make sure the window is fully rendered before showing
        self.Freeze()
        self.Layout()
        self.Fit()
        self.Thaw()
        
        # Reset the window position offscreen to avoid flash
        screen_width, screen_height = wx.DisplaySize()
        self.SetPosition((-1000, -1000))
        
        # Then show it
        self.Show()
        
        # Force an immediate update
        self.timer.Notify()
    
    def stop_tracking(self):
        """Stop tracking the cursor"""
        self.timer.Stop()
        self.is_active = False
        self.Hide()
    
    def on_timer(self, event):
        """Update the tracker with current cursor info"""
        # Get current mouse position
        x, y = pyautogui.position()
        
        # Update position text
        self.pos_text.SetLabel(f"Position: ({x}, {y})")
        
        # Get pixel color
        try:
            screenshot = pyautogui.screenshot(region=(x, y, 1, 1))
            pixel_color = screenshot.getpixel((0, 0))
            
            # Update color display with bold border
            self.color_display.SetBackgroundColour(wx.Colour(*pixel_color))
            
            # Update RGB text - make it easier to read
            r, g, b = pixel_color
            self.rgb_text.SetLabel(f"RGB: ({r}, {g}, {b})")
            
            # Position window near cursor but not directly under it
            screen_width, screen_height = wx.DisplaySize()
            window_width, window_height = self.GetSize()
            
            # Get current cursor position
            cursor_pos = wx.GetMousePosition()
            
            # Calculate position to keep window on screen
            pos_x = min(cursor_pos.x + 20, screen_width - window_width)
            pos_y = min(cursor_pos.y + 20, screen_height - window_height)
            
            # Check if we need to flip position (if too close to screen edge)
            if pos_x + window_width > screen_width:
                pos_x = cursor_pos.x - window_width - 10
            
            if pos_y + window_height > screen_height:
                pos_y = cursor_pos.y - window_height - 10
                
            # Set new position
            self.SetPosition((pos_x, pos_y))
            
            # Force redraw
            self.Refresh()
            self.Update()
            
        except Exception as e:
            # Log error but continue
            print(f"Cursor tracker error: {e}")
            pass


# Global cursor tracker instance
global_cursor_tracker = None

def get_cursor_tracker():
    """Get or create the global cursor tracker instance"""
    global global_cursor_tracker
    if global_cursor_tracker is None or not wx.GetApp():
        global_cursor_tracker = CursorTracker()
    return global_cursor_tracker


class PixelPickerThread(threading.Thread):
    """Background thread for pixel picking without blocking UI"""
    
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.daemon = True  # Thread will exit when main program exits
        self.stop_event = threading.Event()
        self.result = None
    
    def run(self):
        """Run the picker in background"""
        # Create keyboard listener
        def on_key_press(key):
            if key == keyboard.Key.enter:
                # Capture current position and color
                x, y = pyautogui.position()
                screenshot = pyautogui.screenshot()
                pixel_color = screenshot.getpixel((x, y))
                self.result = (x, y, pixel_color)
                self.stop_event.set()
                return False  # Stop listener
            elif key == keyboard.Key.esc:
                self.stop_event.set()
                return False  # Stop listener
            return True
        
        # Start keyboard listener
        listener = keyboard.Listener(on_press=on_key_press)
        listener.start()
        
        # Wait for done flag or timeout after 30 seconds
        self.stop_event.wait(30)  # 30 second timeout
        
        # Ensure listener is stopped
        listener.stop()
        
        # Notify parent with wx.CallAfter to ensure it happens in the main thread
        if self.result:
            wx.CallAfter(self.parent.on_picker_complete, self.result)


class PixelColorConditionDialog(wx.Dialog):
    """Dialog for creating/editing a pixel color condition"""
    
    def __init__(self, parent, title="Add Pixel Color Condition", condition=None):
        super().__init__(parent, title=title, size=(400, 350))
        
        self.condition = condition or {
            "type": "pixel_color",
            "x": 0,
            "y": 0,
            "color": [255, 255, 255],
            "tolerance": 10
        }
        
        # Get cursor tracker
        self.cursor_tracker = get_cursor_tracker()
        
        # Picker thread
        self.picker_thread = None
        
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Coordinates group
        coord_box = wx.StaticBox(panel, label="Coordinates")
        coord_sizer = wx.StaticBoxSizer(coord_box, wx.HORIZONTAL)
        
        # X coordinate
        x_box = wx.BoxSizer(wx.HORIZONTAL)
        x_label = wx.StaticText(panel, label="X:")
        self.x_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition["x"]))
        x_box.Add(x_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        x_box.Add(self.x_ctrl, proportion=1)
        
        # Y coordinate
        y_box = wx.BoxSizer(wx.HORIZONTAL)
        y_label = wx.StaticText(panel, label="Y:")
        self.y_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition["y"]))
        y_box.Add(y_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        y_box.Add(self.y_ctrl, proportion=1)
        
        coord_sizer.Add(x_box, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10)
        coord_sizer.Add(y_box, proportion=1, flag=wx.EXPAND)
        
        vbox.Add(coord_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Color display
        color_label = wx.StaticText(panel, label="Color:")
        self.color_display = ColorDisplay(panel, initial_color=tuple(self.condition["color"]))
        
        vbox.Add(color_label, flag=wx.LEFT, border=10)
        vbox.Add(self.color_display, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)
        
        # Tolerance
        tolerance_box = wx.BoxSizer(wx.HORIZONTAL)
        tolerance_label = wx.StaticText(panel, label="Tolerance:")
        self.tolerance_ctrl = wx.SpinCtrl(panel, min=0, max=255, value=str(self.condition["tolerance"]))
        tolerance_help = wx.StaticText(panel, label="(0-255)")
        
        tolerance_box.Add(tolerance_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        tolerance_box.Add(self.tolerance_ctrl, proportion=1, flag=wx.RIGHT, border=8) 
        tolerance_box.Add(tolerance_help, flag=wx.ALIGN_CENTER_VERTICAL)
        
        vbox.Add(tolerance_box, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Instructions
        instructions = wx.StaticText(panel, label="Move cursor to desired position, then press Enter to select")
        vbox.Add(instructions, flag=wx.ALL, border=10)
        
        # Pick from screen button
        self.screen_pick_btn = wx.Button(panel, label="Pick Pixel from Screen")
        self.screen_pick_btn.Bind(wx.EVT_BUTTON, self.on_pick_from_screen)
        vbox.Add(self.screen_pick_btn, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        
        # Buttons
        button_box = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(panel, wx.ID_OK, "OK")
        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_box.Add(ok_button)
        button_box.Add(cancel_button, flag=wx.LEFT, border=5)
        vbox.Add(button_box, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        panel.SetSizer(vbox)
        
        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
    def on_close(self, event):
        """Ensure tracker is stopped when dialog closes"""
        if self.cursor_tracker.is_active:
            self.cursor_tracker.stop_tracking()
        event.Skip()
    
    def on_pick_from_screen(self, event):
        """Begin the pixel picking process"""
        # Iconize window to get it out of the way
        self.Iconize(True)
        
        # Start cursor tracker
        self.cursor_tracker.start_tracking()
        
        # Status text in parent's status bar if available
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Press Enter to select current position, Esc to cancel")
        except:
            pass
        
        # Display small instructions label at the top of the screen
        screen_width, screen_height = wx.DisplaySize()
        instruction_label = wx.Frame(None, style=wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP | wx.BORDER_NONE)
        instruction_label.SetTransparent(200)
        instruction_label.SetBackgroundColour(wx.Colour(0, 0, 0))
        instruction_text = wx.StaticText(instruction_label, label="Press Enter to select, Esc to cancel")
        instruction_text.SetForegroundColour(wx.WHITE)
        instruction_label.SetSize((300, 30))
        instruction_label.Centre(wx.HORIZONTAL)
        instruction_label.SetPosition((screen_width // 2 - 150, 10))
        instruction_label.Show()
        
        # Start picker thread
        self.picker_thread = PixelPickerThread(self)
        self.picker_thread.start()
        
        # Set a timeout to check if the thread is done
        wx.CallLater(500, self.check_picker_thread, instruction_label)
    
    def check_picker_thread(self, instruction_label):
        """Check if the picker thread is done"""
        if self.picker_thread and not self.picker_thread.is_alive():
            # Thread is done, process result
            if self.picker_thread.result:
                self.on_picker_complete(self.picker_thread.result)
            
            # Clean up
            instruction_label.Destroy()
            self.picker_thread = None
            return
        
        # Thread still running, check again later
        wx.CallLater(500, self.check_picker_thread, instruction_label)
    
    def on_picker_complete(self, result):
        """Handle the completion of the picker thread"""
        if result:
            x, y, pixel_color = result
            # Update controls
            self.x_ctrl.SetValue(x)
            self.y_ctrl.SetValue(y)
            self.color_display.SetColor(pixel_color)
        
        # Stop the cursor tracker
        self.cursor_tracker.stop_tracking()
        
        # Restore window
        self.Iconize(False)
        self.Raise()
        
        # Reset status text
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except:
            pass
    
    def get_condition(self):
        """Get the condition data from the dialog"""
        self.condition.update({
            "x": self.x_ctrl.GetValue(),
            "y": self.y_ctrl.GetValue(),
            "color": list(self.color_display.GetColor()),
            "tolerance": self.tolerance_ctrl.GetValue()
        })
        return self.condition


class RegionColorConditionDialog(wx.Dialog):
    """Dialog for creating/editing a region color condition"""
    
    def __init__(self, parent, title="Add Region Color Condition", condition=None):
        super().__init__(parent, title=title, size=(500, 550))
        
        self.condition = condition or {
            "type": "pixel_region_color",
            "x1": 0,
            "y1": 0,
            "x2": 100,
            "y2": 100,
            "color": [255, 255, 255],
            "tolerance": 10,
            "threshold": 0.5
        }
        
        # Initialize selection variables
        self.selection_mode = False
        self.start_pos = None
        self.current_pos = None
        self.screenshot = None
        
        # Get cursor tracker
        self.cursor_tracker = get_cursor_tracker()
        
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Region coordinates group
        coord_box = wx.StaticBox(panel, label="Region Coordinates")
        coord_sizer = wx.StaticBoxSizer(coord_box, wx.VERTICAL)
        
        # First row: Top-left corner
        tl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tl_label = wx.StaticText(panel, label="Top-left:")
        
        x1_label = wx.StaticText(panel, label="X1:")
        self.x1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition["x1"]))
        
        y1_label = wx.StaticText(panel, label="Y1:")
        self.y1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition["y1"]))
        
        tl_sizer.Add(tl_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        tl_sizer.Add(x1_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        tl_sizer.Add(self.x1_ctrl, proportion=1, flag=wx.RIGHT, border=10)
        tl_sizer.Add(y1_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        tl_sizer.Add(self.y1_ctrl, proportion=1)
        
        # Second row: Bottom-right corner
        br_sizer = wx.BoxSizer(wx.HORIZONTAL)
        br_label = wx.StaticText(panel, label="Bottom-right:")
        
        x2_label = wx.StaticText(panel, label="X2:")
        self.x2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition["x2"]))
        
        y2_label = wx.StaticText(panel, label="Y2:")
        self.y2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition["y2"]))
        
        br_sizer.Add(br_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        br_sizer.Add(x2_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        br_sizer.Add(self.x2_ctrl, proportion=1, flag=wx.RIGHT, border=10)
        br_sizer.Add(y2_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        br_sizer.Add(self.y2_ctrl, proportion=1)
        
        # Select region button
        self.region_btn = wx.Button(panel, label="Select Region on Screen")
        self.region_btn.Bind(wx.EVT_BUTTON, self.on_select_region)
        
        # Add to coordinate sizer
        coord_sizer.Add(tl_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        coord_sizer.Add(br_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        coord_sizer.Add(self.region_btn, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Add to main sizer
        vbox.Add(coord_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Preview image (shows selected region)
        preview_box = wx.StaticBox(panel, label="Region Preview")
        preview_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)
        
        self.preview_text = wx.StaticText(panel, label="Select a region to see preview")
        preview_sizer.Add(self.preview_text, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Add to main sizer
        vbox.Add(preview_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Color section - SEPARATED FROM REGION
        color_box = wx.StaticBox(panel, label="Region Color")
        color_sizer = wx.StaticBoxSizer(color_box, wx.VERTICAL)
        
        # Color display
        color_label = wx.StaticText(panel, label="Color:")
        self.color_display = ColorDisplay(panel, initial_color=tuple(self.condition["color"]))
        
        # Color picker button
        self.color_btn = wx.Button(panel, label="Pick Color from Screen")
        self.color_btn.Bind(wx.EVT_BUTTON, self.on_pick_color)
        
        # Add to color section
        color_sizer.Add(color_label, flag=wx.LEFT | wx.TOP, border=5)
        color_sizer.Add(self.color_display, flag=wx.EXPAND | wx.ALL, border=5)
        color_sizer.Add(self.color_btn, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Add color section to main sizer
        vbox.Add(color_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Parameters group
        param_box = wx.StaticBox(panel, label="Detection Parameters")
        param_sizer = wx.StaticBoxSizer(param_box, wx.VERTICAL)
        
        # Tolerance
        tolerance_box = wx.BoxSizer(wx.HORIZONTAL)
        tolerance_label = wx.StaticText(panel, label="Tolerance:")
        self.tolerance_ctrl = wx.SpinCtrl(panel, min=0, max=255, value=str(self.condition["tolerance"]))
        tolerance_help = wx.StaticText(panel, label="(color variation allowed)")
        
        tolerance_box.Add(tolerance_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        tolerance_box.Add(self.tolerance_ctrl, proportion=1, flag=wx.RIGHT, border=8)
        tolerance_box.Add(tolerance_help, flag=wx.ALIGN_CENTER_VERTICAL)
        
        # Threshold
        threshold_box = wx.BoxSizer(wx.HORIZONTAL)
        threshold_label = wx.StaticText(panel, label="Threshold:")
        self.threshold_ctrl = wx.SpinCtrlDouble(panel, min=0, max=1, inc=0.1, value=str(self.condition["threshold"]))
        threshold_help = wx.StaticText(panel, label="(% of pixels that must match)")
        
        threshold_box.Add(threshold_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        threshold_box.Add(self.threshold_ctrl, proportion=1, flag=wx.RIGHT, border=8)
        threshold_box.Add(threshold_help, flag=wx.ALIGN_CENTER_VERTICAL)
        
        # Add to parameters sizer
        param_sizer.Add(tolerance_box, flag=wx.EXPAND | wx.ALL, border=5)
        param_sizer.Add(threshold_box, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Add to main sizer
        vbox.Add(param_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Buttons
        button_box = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(panel, wx.ID_OK, "OK")
        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_box.Add(ok_button)
        button_box.Add(cancel_button, flag=wx.LEFT, border=5)
        vbox.Add(button_box, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        panel.SetSizer(vbox)
        
        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
    def on_close(self, event):
        """Ensure tracker is stopped when dialog closes"""
        if self.cursor_tracker.is_active:
            self.cursor_tracker.stop_tracking()
        event.Skip()
    
    def on_select_region(self, event):
        """Start the interactive region selection process"""
        self.Iconize(True)
        
        # Start cursor tracker
        self.cursor_tracker.start_tracking()
        
        # Status text in parent's status bar if available
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Click and drag to select a region. Press ESC to cancel")
        except:
            pass
        
        # IMPORTANT: Call region selection directly instead of in a thread
        # Use wx.CallAfter to ensure we're still in the main thread
        wx.CallAfter(self._do_select_region)
    
    def on_pick_color(self, event):
        """Start the color picking process"""
        self.Iconize(True)
        
        # Start cursor tracker
        self.cursor_tracker.start_tracking()
        
        # Status text in parent's status bar if available
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Press Enter to select a color, Esc to cancel")
        except:
            pass
        
        # Display instructions at the top of the screen
        screen_width, screen_height = wx.DisplaySize()
        instruction_label = wx.Frame(None, style=wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP | wx.BORDER_NONE)
        instruction_label.SetTransparent(200)
        instruction_label.SetBackgroundColour(wx.Colour(0, 0, 0))
        instruction_text = wx.StaticText(instruction_label, label="Press Enter to select color, Esc to cancel")
        instruction_text.SetForegroundColour(wx.WHITE)
        instruction_label.SetSize((300, 30))
        instruction_label.Centre(wx.HORIZONTAL)
        instruction_label.SetPosition((screen_width // 2 - 150, 10))
        instruction_label.Show()
        
        # Manual keyboard monitoring
        self.pick_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_color_pick_timer, self.pick_timer)
        self.pick_timer.Start(100)  # Check every 100ms
        
        # Set a timeout
        self.selection_timeout = 300  # 30 seconds
        self.selection_done = False
        
        # Store instruction label
        self.instruction_label = instruction_label
    
    def on_color_pick_timer(self, event):
        """Timer event to check for keyboard input during color picking"""
        # Decrement timeout counter
        self.selection_timeout -= 1
        if self.selection_timeout <= 0 or self.selection_done:
            self.pick_timer.Stop()
            if not self.selection_done:
                self.end_color_picking(None)
            return
            
        # Check for keyboard input
        if wx.GetKeyState(wx.WXK_RETURN) or wx.GetKeyState(wx.WXK_NUMPAD_ENTER):
            x, y = pyautogui.position()
            screenshot = pyautogui.screenshot()
            pixel_color = screenshot.getpixel((x, y))
            self.selection_done = True
            self.pick_timer.Stop()
            self.end_color_picking((x, y, pixel_color))
        elif wx.GetKeyState(wx.WXK_ESCAPE):
            self.selection_done = True
            self.pick_timer.Stop()
            self.end_color_picking(None)
    
    def end_color_picking(self, result):
        """End the color picking process"""
        # Clean up
        if hasattr(self, 'instruction_label') and self.instruction_label:
            self.instruction_label.Destroy()
            self.instruction_label = None
        
        # Stop cursor tracker
        self.cursor_tracker.stop_tracking()
        
        # Process result if we have one
        if result:
            x, y, pixel_color = result
            # Update color display
            self.color_display.SetColor(pixel_color)
        
        # Restore window
        self.Iconize(False)
        self.Raise()
        
        # Reset status text
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except:
            pass
    
    def _do_select_region(self):
        """Perform the interactive region selection"""
        # Create a selection overlay dialog
        overlay = wx.Dialog(None, title="Region Selector", 
                          style=wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR | wx.NO_BORDER)
        
        # Make it full screen and transparent
        overlay.SetTransparent(150)  # Semi-transparent
        overlay.ShowFullScreen(True)
        
        # Take a full screenshot for reference
        self.screenshot = pyautogui.screenshot()
        screen_width, screen_height = self.screenshot.size
        
        # Create a panel to capture mouse events
        panel = wx.Panel(overlay)
        panel.SetSize(screen_width, screen_height)
        
        # State variables for the selection
        selection_start = None
        is_selecting = False
        
        # Create a buffered DC for drawing
        buffer = wx.Bitmap(screen_width, screen_height)
        
        def draw_selection():
            """Draw the current selection on the overlay"""
            nonlocal buffer
            
            dc = wx.BufferedDC(wx.ClientDC(panel), buffer)
            dc.Clear()
            
            if selection_start and is_selecting:
                x1, y1 = selection_start
                x2, y2 = panel.ScreenToClient(wx.GetMousePosition())
                
                # Draw rectangle
                dc.SetPen(wx.Pen(wx.BLUE, 2))
                dc.SetBrush(wx.Brush(wx.Colour(0, 0, 255, 64)))  # Semi-transparent blue
                
                # Calculate rectangle coordinates
                left = min(x1, x2)
                top = min(y1, y2)
                width = abs(x2 - x1)
                height = abs(y2 - y1)
                
                dc.DrawRectangle(left, top, width, height)
                
                # Draw dimensions text
                text = f"{width}x{height} px"
                dc.SetTextForeground(wx.WHITE)
                dc.DrawText(text, left + 5, top + 5)
        
        def on_paint(evt):
            """Handle paint events"""
            wx.BufferedPaintDC(panel, buffer)
        
        def on_mouse_down(evt):
            """Handle mouse down events"""
            nonlocal selection_start, is_selecting
            selection_start = evt.GetPosition()
            is_selecting = True
            draw_selection()
        
        def on_mouse_move(evt):
            """Handle mouse move events"""
            if is_selecting:
                draw_selection()
        
        def on_mouse_up(evt):
            """Handle mouse up events"""
            nonlocal is_selecting
            
            if not is_selecting:
                return
                
            is_selecting = False
            
            # Get the selection
            x1, y1 = selection_start
            x2, y2 = evt.GetPosition()
            
            # Ensure x1,y1 is top-left and x2,y2 is bottom-right
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            
            # Close the overlay
            overlay.Close()
            
            # Process the selection (in the main thread already)
            self.process_selection(x1, y1, x2, y2)
        
        def on_key_down(evt):
            """Handle key down events"""
            if evt.GetKeyCode() == wx.WXK_ESCAPE:
                overlay.Close()
                self.on_selection_canceled()
        
        # Bind events
        panel.Bind(wx.EVT_PAINT, on_paint)
        panel.Bind(wx.EVT_LEFT_DOWN, on_mouse_down)
        panel.Bind(wx.EVT_MOTION, on_mouse_move)
        panel.Bind(wx.EVT_LEFT_UP, on_mouse_up)
        panel.Bind(wx.EVT_KEY_DOWN, on_key_down)
        
        # Initialize the buffer
        dc = wx.BufferedDC(None, buffer)
        dc.Clear()
        
        # Show instructions
        info_text = "Click and drag to select a region. Press ESC to cancel."
        font = wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        dc.SetTextForeground(wx.WHITE)
        text_width, text_height = dc.GetTextExtent(info_text)
        dc.DrawText(info_text, (screen_width - text_width) // 2, 30)
        
        # Show the overlay (this blocks until the overlay is closed)
        overlay.ShowModal()
    
    def on_selection_canceled(self):
        """Handle cancellation of region selection"""
        # Stop the cursor tracker
        self.cursor_tracker.stop_tracking()
        
        # Restore main window
        self.Iconize(False)
        self.Raise()
        
        # Reset status text
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except:
            pass
    
    def process_selection(self, x1, y1, x2, y2):
        """Process the selected region"""
        # Update controls
        self.x1_ctrl.SetValue(x1)
        self.y1_ctrl.SetValue(y1)
        self.x2_ctrl.SetValue(x2)
        self.y2_ctrl.SetValue(y2)
        
        # Extract region info but DON'T update color automatically
        try:
            # Crop the region from our screenshot
            region = self.screenshot.crop((x1, y1, x2, y2))
            
            # Update preview text
            region_size = region.size
            self.preview_text.SetLabel(f"Region: {region_size[0]}x{region_size[1]} pixels")
            
        except Exception as e:
            self.preview_text.SetLabel(f"Error analyzing region: {str(e)}")
        
        # Stop the cursor tracker
        self.cursor_tracker.stop_tracking()
        
        # Restore main window
        self.Iconize(False)
        self.Raise()
        
        # Reset status text
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except:
            pass
    
    def get_condition(self):
        """Get the condition data from the dialog"""
        self.condition.update({
            "x1": self.x1_ctrl.GetValue(),
            "y1": self.y1_ctrl.GetValue(),
            "x2": self.x2_ctrl.GetValue(),
            "y2": self.y2_ctrl.GetValue(),
            "color": list(self.color_display.GetColor()),
            "tolerance": self.tolerance_ctrl.GetValue(),
            "threshold": self.threshold_ctrl.GetValue()
        })
        return self.condition


class UIElementDialog(wx.Dialog):
    """Dialog for creating/editing a UI element"""
    
    def __init__(self, parent, title="Add UI Element", element=None):
        super().__init__(parent, title=title, size=(450, 450))
        
        # Default values if no element is provided
        self.element = element or [
            (0, 0),            # coordinates
            "New Element",     # name
            "button",          # element_type
            False,             # speaks_on_select
            None               # submenu_id
        ]
        
        # Store screenshot for element info
        self.screenshot = None
        
        # Get cursor tracker
        self.cursor_tracker = get_cursor_tracker()
        
        # Picker thread
        self.picker_thread = None
        
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Position section
        pos_box = wx.StaticBox(panel, label="Element Position")
        pos_sizer = wx.StaticBoxSizer(pos_box, wx.VERTICAL)
        
        # Coordinates
        coord_box = wx.BoxSizer(wx.HORIZONTAL)
        x_label = wx.StaticText(panel, label="X:")
        self.x_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.element[0][0]))
        y_label = wx.StaticText(panel, label="Y:")
        self.y_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.element[0][1]))
        
        coord_box.Add(x_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        coord_box.Add(self.x_ctrl, proportion=1, flag=wx.RIGHT, border=10)
        coord_box.Add(y_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        coord_box.Add(self.y_ctrl, proportion=1)
        
        # Color at position
        color_box = wx.BoxSizer(wx.HORIZONTAL)
        color_label = wx.StaticText(panel, label="Color at Position:")
        self.color_display = ColorDisplay(panel, initial_color=(200, 200, 200))
        color_box.Add(color_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        color_box.Add(self.color_display, proportion=1, flag=wx.EXPAND)
        
        # Instructions
        instructions = wx.StaticText(panel, label="Move cursor to desired element, then press Enter to select")
        
        # Pick location button
        self.pick_btn = wx.Button(panel, label="Pick Element Location on Screen")
        self.pick_btn.Bind(wx.EVT_BUTTON, self.on_pick_location)
        
        # Add to position section
        pos_sizer.Add(coord_box, flag=wx.EXPAND | wx.ALL, border=5)
        pos_sizer.Add(color_box, flag=wx.EXPAND | wx.ALL, border=5)
        pos_sizer.Add(instructions, flag=wx.ALL, border=5)
        pos_sizer.Add(self.pick_btn, flag=wx.EXPAND | wx.ALL, border=5)
        
        vbox.Add(pos_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Element properties section
        props_box = wx.StaticBox(panel, label="Element Properties")
        props_sizer = wx.StaticBoxSizer(props_box, wx.VERTICAL)
        
        # Name
        name_box = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(panel, label="Name:")
        self.name_ctrl = wx.TextCtrl(panel, value=str(self.element[1]))
        name_box.Add(name_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        name_box.Add(self.name_ctrl, proportion=1)
        
        # Element Type
        type_box = wx.BoxSizer(wx.HORIZONTAL)
        type_label = wx.StaticText(panel, label="Type:")
        element_types = ["button", "dropdown", "menu", "tab", "toggle", "link"]
        self.type_ctrl = wx.Choice(panel, choices=element_types)
        
        # Set selected type
        if self.element[2] in element_types:
            self.type_ctrl.SetSelection(element_types.index(self.element[2]))
        else:
            self.type_ctrl.SetSelection(0)  # Default to button
            
        type_box.Add(type_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        type_box.Add(self.type_ctrl, proportion=1)
        
        # Speaks on select
        self.speaks_ctrl = wx.CheckBox(panel, label="Speaks on Select")
        self.speaks_ctrl.SetValue(self.element[3])
        
        # Submenu ID
        submenu_box = wx.BoxSizer(wx.HORIZONTAL)
        submenu_label = wx.StaticText(panel, label="Submenu ID:")
        self.submenu_ctrl = wx.TextCtrl(panel, value=str(self.element[4] or ""))
        submenu_box.Add(submenu_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        submenu_box.Add(self.submenu_ctrl, proportion=1)
        
        # Add to properties section
        props_sizer.Add(name_box, flag=wx.EXPAND | wx.ALL, border=5)
        props_sizer.Add(type_box, flag=wx.EXPAND | wx.ALL, border=5)
        props_sizer.Add(self.speaks_ctrl, flag=wx.EXPAND | wx.ALL, border=5)
        props_sizer.Add(submenu_box, flag=wx.EXPAND | wx.ALL, border=5)
        
        vbox.Add(props_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Buttons
        button_box = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(panel, wx.ID_OK, "OK")
        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_box.Add(ok_button)
        button_box.Add(cancel_button, flag=wx.LEFT, border=5)
        vbox.Add(button_box, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        # Update color display if we have coordinates
        wx.CallAfter(self.update_position_color)
        
        panel.SetSizer(vbox)
        
        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
    def on_close(self, event):
        """Ensure tracker is stopped when dialog closes"""
        if self.cursor_tracker.is_active:
            self.cursor_tracker.stop_tracking()
        event.Skip()
    
    def update_position_color(self):
        """Update the color display based on current coordinates"""
        try:
            x, y = self.x_ctrl.GetValue(), self.y_ctrl.GetValue()
            
            # Take a screenshot if we don't have one
            if self.screenshot is None:
                self.screenshot = pyautogui.screenshot()
            
            # Get pixel color at coordinates
            if 0 <= x < self.screenshot.width and 0 <= y < self.screenshot.height:
                pixel_color = self.screenshot.getpixel((x, y))
                self.color_display.SetColor(pixel_color)
        except Exception as e:
            print(f"Error updating position color: {e}")
    
    def on_pick_location(self, event):
        """Interactive location picker with live preview"""
        self.Iconize(True)
        
        # Start cursor tracker
        self.cursor_tracker.start_tracking()
        
        # Status text in parent's status bar if available
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Press Enter to select current position, Esc to cancel")
        except:
            pass
        
        # Display small instructions label at the top of the screen
        screen_width, screen_height = wx.DisplaySize()
        instruction_label = wx.Frame(None, style=wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP | wx.BORDER_NONE)
        instruction_label.SetTransparent(200)
        instruction_label.SetBackgroundColour(wx.Colour(0, 0, 0))
        instruction_text = wx.StaticText(instruction_label, label="Press Enter to select, Esc to cancel")
        instruction_text.SetForegroundColour(wx.WHITE)
        instruction_label.SetSize((300, 30))
        instruction_label.Centre(wx.HORIZONTAL)
        instruction_label.SetPosition((screen_width // 2 - 150, 10))
        instruction_label.Show()
        
        # Take a screenshot for later use
        self.screenshot = pyautogui.screenshot()
        
        # Manual keyboard monitoring to avoid threading issues
        self.pick_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_pick_timer, self.pick_timer)
        self.pick_timer.Start(100)  # Check every 100ms
        
        # Set a timeout to check if the selection is done
        self.selection_timeout = 300  # 30 seconds in 100ms increments
        self.selection_done = False
        
        # Store instruction label for cleanup
        self.instruction_label = instruction_label
    
    def on_pick_timer(self, event):
        """Timer event to check for keyboard input during picking"""
        # Decrement timeout counter
        self.selection_timeout -= 1
        if self.selection_timeout <= 0 or self.selection_done:
            self.pick_timer.Stop()
            if not self.selection_done:
                self.end_picking(None)
            return
            
        # Check for keyboard input
        if wx.GetKeyState(wx.WXK_RETURN) or wx.GetKeyState(wx.WXK_NUMPAD_ENTER):
            x, y = pyautogui.position()
            screenshot = pyautogui.screenshot()
            pixel_color = screenshot.getpixel((x, y))
            self.selection_done = True
            self.pick_timer.Stop()
            self.end_picking((x, y, pixel_color))
        elif wx.GetKeyState(wx.WXK_ESCAPE):
            self.selection_done = True
            self.pick_timer.Stop()
            self.end_picking(None)
    
    def end_picking(self, result):
        """End the picking process and process results"""
        # Clean up
        if hasattr(self, 'instruction_label') and self.instruction_label:
            self.instruction_label.Destroy()
            self.instruction_label = None
        
        # Stop cursor tracker
        self.cursor_tracker.stop_tracking()
        
        # Process result if we have one
        if result:
            x, y, pixel_color = result
            # Update controls
            self.x_ctrl.SetValue(x)
            self.y_ctrl.SetValue(y)
            self.color_display.SetColor(pixel_color)
            
            # Suggest name if appropriate
            suggested_name = f"Element at {x},{y}"
            if not self.name_ctrl.GetValue() or self.name_ctrl.GetValue() == "New Element":
                self.name_ctrl.SetValue(suggested_name)
        
        # Restore window
        self.Iconize(False)
        self.Raise()
        
        # Reset status text
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except:
            pass
    
    def get_element(self):
        """Get the element data from the dialog"""
        submenu_id = self.submenu_ctrl.GetValue()
        if not submenu_id:
            submenu_id = None
            
        return [
            (self.x_ctrl.GetValue(), self.y_ctrl.GetValue()),
            self.name_ctrl.GetValue(),
            self.type_ctrl.GetString(self.type_ctrl.GetSelection()),
            self.speaks_ctrl.GetValue(),
            submenu_id
        ]


class MenuPanel(scrolled.ScrolledPanel):
    """Panel for displaying and editing menu data"""
    
    def __init__(self, parent, menu_id, menu_data, profile_editor):
        super().__init__(parent)
        
        self.menu_id = menu_id
        self.menu_data = menu_data
        self.profile_editor = profile_editor
        
        self.init_ui()
        self.SetupScrolling()
        
    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Menu Header
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title = wx.StaticText(self, label=f"Menu: {self.menu_id}")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        header_sizer.Add(title, flag=wx.ALL, border=5)
        
        # Delete menu button
        delete_btn = wx.Button(self, label="Delete Menu")
        delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_menu)
        header_sizer.Add(delete_btn, flag=wx.ALL, border=5)
        
        main_sizer.Add(header_sizer, flag=wx.EXPAND)
        
        # Conditions section
        conditions_box = wx.StaticBox(self, label="Menu Detection Conditions")
        conditions_sizer = wx.StaticBoxSizer(conditions_box, wx.VERTICAL)
        
        # Add condition buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_pixel_btn = wx.Button(self, label="Add Pixel Color")
        add_pixel_btn.Bind(wx.EVT_BUTTON, self.on_add_pixel_condition)
        add_region_btn = wx.Button(self, label="Add Region Color")
        add_region_btn.Bind(wx.EVT_BUTTON, self.on_add_region_condition)
        
        btn_sizer.Add(add_pixel_btn, flag=wx.RIGHT, border=5)
        btn_sizer.Add(add_region_btn)
        conditions_sizer.Add(btn_sizer, flag=wx.ALL, border=5)
        
        # Conditions list
        self.conditions_list = wx.ListCtrl(self, style=wx.LC_REPORT, size=(-1, 150))
        self.conditions_list.InsertColumn(0, "Type", width=100)
        self.conditions_list.InsertColumn(1, "Details", width=300)
        
        # Populate conditions
        self.update_conditions_list()
        
        # Context menu for conditions
        self.conditions_list.Bind(wx.EVT_CONTEXT_MENU, self.on_condition_context_menu)
        
        conditions_sizer.Add(self.conditions_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        main_sizer.Add(conditions_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # UI Elements section
        elements_box = wx.StaticBox(self, label="Menu UI Elements")
        elements_sizer = wx.StaticBoxSizer(elements_box, wx.VERTICAL)
        
        # Add element button
        add_element_btn = wx.Button(self, label="Add UI Element")
        add_element_btn.Bind(wx.EVT_BUTTON, self.on_add_element)
        elements_sizer.Add(add_element_btn, flag=wx.ALL, border=5)
        
        # Elements list
        self.elements_list = wx.ListCtrl(self, style=wx.LC_REPORT, size=(-1, 200))
        self.elements_list.InsertColumn(0, "Name", width=150)
        self.elements_list.InsertColumn(1, "Type", width=100)
        self.elements_list.InsertColumn(2, "Position", width=100)
        self.elements_list.InsertColumn(3, "Submenu", width=100)
        
        # Populate elements
        self.update_elements_list()
        
        # Context menu for elements
        self.elements_list.Bind(wx.EVT_CONTEXT_MENU, self.on_element_context_menu)
        
        elements_sizer.Add(self.elements_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        main_sizer.Add(elements_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        self.SetSizer(main_sizer)
    
    def update_conditions_list(self):
        """Update the conditions list with current data"""
        self.conditions_list.DeleteAllItems()
        
        if "conditions" not in self.menu_data:
            return
            
        for i, condition in enumerate(self.menu_data["conditions"]):
            condition_type = condition.get("type", "unknown")
            
            if condition_type == "pixel_color":
                details = f"({condition['x']}, {condition['y']}) = RGB{condition['color']} ±{condition['tolerance']}"
            elif condition_type == "pixel_region_color":
                details = f"Region ({condition['x1']}, {condition['y1']}) to ({condition['x2']}, {condition['y2']}), " \
                          f"RGB{condition['color']} ±{condition['tolerance']}, thresh={condition['threshold']}"
            else:
                details = str(condition)
            
            idx = self.conditions_list.InsertItem(i, condition_type)
            self.conditions_list.SetItem(idx, 1, details)
    
    def update_elements_list(self):
        """Update the elements list with current data"""
        self.elements_list.DeleteAllItems()
        
        if "items" not in self.menu_data:
            return
            
        for i, element in enumerate(self.menu_data["items"]):
            idx = self.elements_list.InsertItem(i, element[1])  # Name
            self.elements_list.SetItem(idx, 1, element[2])      # Type
            self.elements_list.SetItem(idx, 2, f"({element[0][0]}, {element[0][1]})")  # Position
            self.elements_list.SetItem(idx, 3, str(element[4] or ""))  # Submenu
    
    def on_add_pixel_condition(self, event):
        """Add a new pixel color condition"""
        dialog = PixelColorConditionDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            condition = dialog.get_condition()
            
            if "conditions" not in self.menu_data:
                self.menu_data["conditions"] = []
                
            self.menu_data["conditions"].append(condition)
            self.update_conditions_list()
            self.profile_editor.mark_profile_changed()
            
        dialog.Destroy()
    
    def on_add_region_condition(self, event):
        """Add a new region color condition"""
        dialog = RegionColorConditionDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            condition = dialog.get_condition()
            
            if "conditions" not in self.menu_data:
                self.menu_data["conditions"] = []
                
            self.menu_data["conditions"].append(condition)
            self.update_conditions_list()
            self.profile_editor.mark_profile_changed()
            
        dialog.Destroy()
    
    def on_condition_context_menu(self, event):
        """Show context menu for conditions list"""
        if not self.conditions_list.GetSelectedItemCount():
            return
            
        menu = wx.Menu()
        edit_item = menu.Append(wx.ID_ANY, "Edit Condition")
        delete_item = menu.Append(wx.ID_ANY, "Delete Condition")
        
        self.Bind(wx.EVT_MENU, self.on_edit_condition, edit_item)
        self.Bind(wx.EVT_MENU, self.on_delete_condition, delete_item)
        
        self.PopupMenu(menu)
        menu.Destroy()
    
    def on_edit_condition(self, event):
        """Edit the selected condition"""
        selected_idx = self.conditions_list.GetFirstSelected()
        if selected_idx == -1:
            return
            
        condition = self.menu_data["conditions"][selected_idx]
        
        if condition["type"] == "pixel_color":
            dialog = PixelColorConditionDialog(self, title="Edit Pixel Color Condition", 
                                             condition=condition)
        elif condition["type"] == "pixel_region_color":
            dialog = RegionColorConditionDialog(self, title="Edit Region Color Condition", 
                                              condition=condition)
        else:
            wx.MessageBox(f"Cannot edit condition of type: {condition['type']}", 
                         "Error", wx.ICON_ERROR)
            return
        
        if dialog.ShowModal() == wx.ID_OK:
            edited_condition = dialog.get_condition()
            self.menu_data["conditions"][selected_idx] = edited_condition
            self.update_conditions_list()
            self.profile_editor.mark_profile_changed()
            
        dialog.Destroy()
    
    def on_delete_condition(self, event):
        """Delete the selected condition"""
        selected_idx = self.conditions_list.GetFirstSelected()
        if selected_idx == -1:
            return
            
        if wx.MessageBox("Are you sure you want to delete this condition?", 
                       "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            del self.menu_data["conditions"][selected_idx]
            self.update_conditions_list()
            self.profile_editor.mark_profile_changed()
    
    def on_add_element(self, event):
        """Add a new UI element"""
        dialog = UIElementDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            element = dialog.get_element()
            
            if "items" not in self.menu_data:
                self.menu_data["items"] = []
                
            self.menu_data["items"].append(element)
            self.update_elements_list()
            self.profile_editor.mark_profile_changed()
            
        dialog.Destroy()
    
    def on_element_context_menu(self, event):
        """Show context menu for elements list"""
        if not self.elements_list.GetSelectedItemCount():
            return
            
        menu = wx.Menu()
        edit_item = menu.Append(wx.ID_ANY, "Edit Element")
        delete_item = menu.Append(wx.ID_ANY, "Delete Element")
        
        self.Bind(wx.EVT_MENU, self.on_edit_element, edit_item)
        self.Bind(wx.EVT_MENU, self.on_delete_element, delete_item)
        
        self.PopupMenu(menu)
        menu.Destroy()
    
    def on_edit_element(self, event):
        """Edit the selected element"""
        selected_idx = self.elements_list.GetFirstSelected()
        if selected_idx == -1:
            return
            
        element = self.menu_data["items"][selected_idx]
        
        dialog = UIElementDialog(self, title="Edit UI Element", element=element)
        if dialog.ShowModal() == wx.ID_OK:
            edited_element = dialog.get_element()
            self.menu_data["items"][selected_idx] = edited_element
            self.update_elements_list()
            self.profile_editor.mark_profile_changed()
            
        dialog.Destroy()
    
    def on_delete_element(self, event):
        """Delete the selected element"""
        selected_idx = self.elements_list.GetFirstSelected()
        if selected_idx == -1:
            return
            
        if wx.MessageBox("Are you sure you want to delete this element?", 
                       "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            del self.menu_data["items"][selected_idx]
            self.update_elements_list()
            self.profile_editor.mark_profile_changed()
    
    def on_delete_menu(self, event):
        """Delete this entire menu"""
        if wx.MessageBox(f"Are you sure you want to delete the menu '{self.menu_id}'?", 
                       "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.profile_editor.delete_menu(self.menu_id)


class ProfileEditorFrame(wx.Frame):
    """Main frame for the profile editor application"""
    
    def __init__(self, parent, title):
        super().__init__(parent, title=f"{title} v{APP_VERSION}", size=(800, 700))
        
        self.profile_data = {}
        self.current_file = None
        self.is_changed = False
        
        self.init_ui()
        self.Center()
        
        # Initialize with default main_menu
        self.add_menu("main_menu")
        
    def init_ui(self):
        panel = wx.Panel(self)
        
        # Menu Bar
        menubar = wx.MenuBar()
        
        # File Menu
        file_menu = wx.Menu()
        new_item = file_menu.Append(wx.ID_NEW, "New Profile", "Create a new profile")
        open_item = file_menu.Append(wx.ID_OPEN, "Open Profile", "Open an existing profile")
        save_item = file_menu.Append(wx.ID_SAVE, "Save Profile", "Save current profile")
        save_as_item = file_menu.Append(wx.ID_SAVEAS, "Save Profile As", "Save current profile with a new name")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "Exit", "Exit the application")
        
        # Tools Menu
        tools_menu = wx.Menu()
        test_item = tools_menu.Append(wx.ID_ANY, "Test Current Menu", "Test the detection of the current menu")
        export_py_item = tools_menu.Append(wx.ID_ANY, "Export as Python", "Export profile as Python code")
        
        # Help Menu
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "About", "About this application")
        
        # Bind file menu events
        self.Bind(wx.EVT_MENU, self.on_new, new_item)
        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        self.Bind(wx.EVT_MENU, self.on_save, save_item)
        self.Bind(wx.EVT_MENU, self.on_save_as, save_as_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        
        # Bind tools menu events
        self.Bind(wx.EVT_MENU, self.on_test_menu, test_item)
        self.Bind(wx.EVT_MENU, self.on_export_python, export_py_item)
        
        # Bind help menu events
        self.Bind(wx.EVT_MENU, self.on_about, about_item)
        
        menubar.Append(file_menu, "&File")
        menubar.Append(tools_menu, "&Tools")
        menubar.Append(help_menu, "&Help")
        self.SetMenuBar(menubar)
        
        # Main layout
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Top controls for adding menus
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        menu_label = wx.StaticText(panel, label="Menu ID:")
        self.menu_id_ctrl = wx.TextCtrl(panel)
        add_menu_btn = wx.Button(panel, label="Add Menu")
        add_menu_btn.Bind(wx.EVT_BUTTON, self.on_add_menu)
        
        top_sizer.Add(menu_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_sizer.Add(self.menu_id_ctrl, proportion=1, flag=wx.RIGHT, border=5)
        top_sizer.Add(add_menu_btn)
        
        main_sizer.Add(top_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Notebook for menus
        self.notebook = wx.Notebook(panel)
        main_sizer.Add(self.notebook, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        
        panel.SetSizer(main_sizer)
        
        # Status Bar
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText("New Profile")
        
        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)
    
    def on_add_menu(self, event):
        """Add a new menu to the profile"""
        menu_id = self.menu_id_ctrl.GetValue().strip()
        
        if not menu_id:
            wx.MessageBox("Please enter a menu ID", "Error", wx.ICON_ERROR)
            return
            
        if menu_id in self.profile_data:
            wx.MessageBox(f"Menu '{menu_id}' already exists", "Error", wx.ICON_ERROR)
            return
            
        self.add_menu(menu_id)
        self.menu_id_ctrl.Clear()
    
    def add_menu(self, menu_id):
        """Add a menu to the profile and create a tab for it"""
        self.profile_data[menu_id] = {
            "conditions": [],
            "items": []
        }
        
        menu_panel = MenuPanel(self.notebook, menu_id, self.profile_data[menu_id], self)
        self.notebook.AddPage(menu_panel, menu_id)
        self.notebook.SetSelection(self.notebook.GetPageCount() - 1)
        
        self.mark_profile_changed()
    
    def delete_menu(self, menu_id):
        """Delete a menu from the profile and remove its tab"""
        if menu_id not in self.profile_data:
            return
            
        # Find the tab index
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if hasattr(page, 'menu_id') and page.menu_id == menu_id:
                self.notebook.DeletePage(i)
                break
        
        # Remove from profile data
        del self.profile_data[menu_id]
        self.mark_profile_changed()
    
    def mark_profile_changed(self):
        """Mark the profile as changed and update UI accordingly"""
        self.is_changed = True
        
        # Update title bar
        title = self.GetTitle()
        if not title.startswith('*'):
            self.SetTitle('*' + title)
            
        # Update status bar
        filename = self.current_file or "New Profile"
        self.statusbar.SetStatusText(f"Modified: {filename}")
    
    def on_new(self, event):
        """Create a new profile"""
        if self.is_changed:
            if wx.MessageBox("Current profile has unsaved changes. Continue?", 
                           "Please confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES:
                return
        
        self.profile_data = {}
        self.current_file = None
        self.is_changed = False
        
        # Clear notebook
        while self.notebook.GetPageCount() > 0:
            self.notebook.DeletePage(0)
        
        # Add default main menu
        self.add_menu("main_menu")
        
        # Update UI
        self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - New Profile")
        self.statusbar.SetStatusText("New Profile")
    
    def on_open(self, event):
        """Open an existing profile"""
        if self.is_changed:
            if wx.MessageBox("Current profile has unsaved changes. Continue?", 
                           "Please confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES:
                return
        
        with wx.FileDialog(self, "Open Profile", wildcard="JSON files (*.json)|*.json",
                         style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            
            # Get the path
            path = fileDialog.GetPath()
            
            try:
                with open(path, 'r') as file:
                    self.profile_data = json.load(file)
                
                self.current_file = path
                self.is_changed = False
                
                # Clear notebook
                while self.notebook.GetPageCount() > 0:
                    self.notebook.DeletePage(0)
                
                # Add pages for each menu
                for menu_id, menu_data in self.profile_data.items():
                    menu_panel = MenuPanel(self.notebook, menu_id, menu_data, self)
                    self.notebook.AddPage(menu_panel, menu_id)
                
                # Update UI
                self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - {os.path.basename(path)}")
                self.statusbar.SetStatusText(f"Loaded: {path}")
                
            except Exception as e:
                wx.MessageBox(f"Error loading profile: {str(e)}", "Error", wx.ICON_ERROR)
    
    def on_save(self, event):
        """Save the current profile"""
        if not self.current_file:
            self.on_save_as(event)
            return
            
        try:
            with open(self.current_file, 'w') as file:
                json.dump(self.profile_data, file, indent=2)
            
            self.is_changed = False
            
            # Update UI
            self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - {os.path.basename(self.current_file)}")
            self.statusbar.SetStatusText(f"Saved: {self.current_file}")
            
        except Exception as e:
            wx.MessageBox(f"Error saving profile: {str(e)}", "Error", wx.ICON_ERROR)
    
    def on_save_as(self, event):
        """Save the current profile with a new name"""
        with wx.FileDialog(self, "Save Profile", wildcard="JSON files (*.json)|*.json",
                         style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            
            # Get the path
            path = fileDialog.GetPath()
            
            # Add .json extension if missing
            if not path.endswith('.json'):
                path += '.json'
            
            try:
                with open(path, 'w') as file:
                    json.dump(self.profile_data, file, indent=2)
                
                self.current_file = path
                self.is_changed = False
                
                # Update UI
                self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - {os.path.basename(path)}")
                self.statusbar.SetStatusText(f"Saved: {path}")
                
            except Exception as e:
                wx.MessageBox(f"Error saving profile: {str(e)}", "Error", wx.ICON_ERROR)
    
    def on_test_menu(self, event):
        """Test the detection of the current menu"""
        # Get the currently selected menu
        current_tab = self.notebook.GetSelection()
        if current_tab == -1:
            wx.MessageBox("No menu selected", "Error", wx.ICON_ERROR)
            return
            
        menu_panel = self.notebook.GetPage(current_tab)
        menu_id = menu_panel.menu_id
        menu_data = self.profile_data[menu_id]
        
        if "conditions" not in menu_data or not menu_data["conditions"]:
            wx.MessageBox(f"Menu '{menu_id}' has no conditions to test", "Error", wx.ICON_ERROR)
            return
        
        # Create a dialog to show test results
        dialog = wx.Dialog(self, title=f"Testing Menu: {menu_id}", size=(500, 400))
        panel = wx.Panel(dialog)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Status text
        status_text = wx.StaticText(panel, label="Testing menu conditions...")
        sizer.Add(status_text, flag=wx.ALL, border=10)
        
        # Results list
        results_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        results_list.InsertColumn(0, "Condition", width=150)
        results_list.InsertColumn(1, "Result", width=100)
        results_list.InsertColumn(2, "Details", width=200)
        
        sizer.Add(results_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Overall result
        overall_result = wx.StaticText(panel, label="")
        overall_result.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(overall_result, flag=wx.ALL, border=10)
        
        # Close button
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda evt: dialog.Close())
        sizer.Add(close_btn, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        panel.SetSizer(sizer)
        
        # Start the test in a separate thread to avoid freezing UI
        condition_checker = MenuCondition()
        
        def run_test():
            # Take screenshot
            screenshot = np.array(pyautogui.screenshot())
            
            # Test each condition
            all_passed = True
            
            for i, condition in enumerate(menu_data["conditions"]):
                condition_type = condition["type"]
                
                try:
                    # Check the condition
                    result = condition_checker.check_condition(condition, screenshot)
                    
                    # Add to results list
                    if condition_type == "pixel_color":
                        description = f"Pixel at ({condition['x']}, {condition['y']})"
                    elif condition_type == "pixel_region_color":
                        description = f"Region ({condition['x1']}, {condition['y1']}) to ({condition['x2']}, {condition['y2']})"
                    else:
                        description = str(condition)
                    
                    result_text = "PASSED" if result else "FAILED"
                    details = f"RGB{condition['color']} ±{condition['tolerance']}"
                    
                    # Update UI from main thread
                    wx.CallAfter(lambda: results_list.InsertItem(i, description))
                    wx.CallAfter(lambda: results_list.SetItem(i, 1, result_text))
                    wx.CallAfter(lambda: results_list.SetItem(i, 2, details))
                    
                    # Update status
                    all_passed = all_passed and result
                    
                except Exception as e:
                    wx.CallAfter(lambda: results_list.InsertItem(i, str(condition)))
                    wx.CallAfter(lambda: results_list.SetItem(i, 1, "ERROR"))
                    wx.CallAfter(lambda: results_list.SetItem(i, 2, str(e)))
                    all_passed = False
            
            # Update final result
            if all_passed:
                wx.CallAfter(lambda: overall_result.SetLabel("RESULT: ALL CONDITIONS PASSED - Menu is active"))
                wx.CallAfter(lambda: overall_result.SetForegroundColour(wx.Colour(0, 128, 0)))  # Green
            else:
                wx.CallAfter(lambda: overall_result.SetLabel("RESULT: SOME CONDITIONS FAILED - Menu is not active"))
                wx.CallAfter(lambda: overall_result.SetForegroundColour(wx.Colour(192, 0, 0)))  # Red
            
            wx.CallAfter(lambda: status_text.SetLabel("Test completed."))
        
        # Start the test thread
        test_thread = threading.Thread(target=run_test)
        test_thread.daemon = True
        test_thread.start()
        
        # Show the dialog
        dialog.ShowModal()
        dialog.Destroy()
    
    def on_export_python(self, event):
        """Export the profile as Python code"""
        if not self.profile_data:
            wx.MessageBox("No profile data to export", "Error", wx.ICON_ERROR)
            return
            
        with wx.FileDialog(self, "Export as Python", wildcard="Python files (*.py)|*.py",
                         style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            
            # Get the path
            path = fileDialog.GetPath()
            
            # Add .py extension if missing
            if not path.endswith('.py'):
                path += '.py'
            
            try:
                # Generate Python code
                py_code = self._generate_python_code()
                
                with open(path, 'w') as file:
                    file.write(py_code)
                
                self.statusbar.SetStatusText(f"Exported to: {path}")
                
                # Show success message with option to open file
                if wx.MessageBox(f"Profile exported to {path}\n\nOpen the file?", 
                               "Export Successful", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                    # Open the file with default system editor
                    import subprocess
                    import platform
                    
                    if platform.system() == 'Windows':
                        os.startfile(path)
                    elif platform.system() == 'Darwin':  # macOS
                        subprocess.call(('open', path))
                    else:  # Linux
                        subprocess.call(('xdg-open', path))
                
            except Exception as e:
                wx.MessageBox(f"Error exporting profile: {str(e)}", "Error", wx.ICON_ERROR)
    
    def _generate_python_code(self):
        """Generate Python code from the profile data"""
        code = [
            '"""',
            f'UI Menu Profile - Generated by {APP_TITLE} v{APP_VERSION}',
            f'Generated on: {time.strftime("%Y-%m-%d %H:%M:%S")}',
            'This file defines menu structures and detection conditions for navigation.',
            '"""',
            '',
            '# Menu structure definition',
            'menus = {'
        ]
        
        # Sort menu IDs to make output deterministic
        menu_ids = sorted(self.profile_data.keys())
        
        for menu_id in menu_ids:
            menu_data = self.profile_data[menu_id]
            
            code.append(f'    "{menu_id}": {{')
            
            # Add conditions
            if "conditions" in menu_data and menu_data["conditions"]:
                code.append('        "conditions": [')
                for condition in menu_data["conditions"]:
                    condition_str = json.dumps(condition, indent=12)
                    # Fix indentation in the JSON string
                    condition_str = condition_str.replace('\n', '\n            ')
                    code.append(f'            {condition_str},')
                code.append('        ],')
            else:
                code.append('        "conditions": [],')
            
            # Add items
            if "items" in menu_data and menu_data["items"]:
                code.append('        "items": [')
                for item in menu_data["items"]:
                    # Convert the item to a proper Python representation
                    coords = item[0]
                    name = item[1]
                    elem_type = item[2]
                    speaks = item[3]
                    submenu = item[4]
                    
                    code.append(f'            (({coords[0]}, {coords[1]}), "{name}", "{elem_type}", {speaks}, {repr(submenu)}),')
                code.append('        ],')
            else:
                code.append('        "items": [],')
            
            code.append('    },')
        
        code.append('}')
        code.append('')
        code.append('# Example usage:')
        code.append('if __name__ == "__main__":')
        code.append('    import json')
        code.append('    print(f"Loaded {len(menus)} menus:")')
        code.append('    for menu_id, menu_data in menus.items():')
        code.append('        conditions = len(menu_data.get("conditions", []))')
        code.append('        items = len(menu_data.get("items", []))')
        code.append('        print(f"  - {menu_id}: {conditions} conditions, {items} items")')
        
        return '\n'.join(code)
    
    def on_about(self, event):
        """Show the about dialog"""
        info = wx.adv.AboutDialogInfo()
        info.SetName(APP_TITLE)
        info.SetVersion(APP_VERSION)
        info.SetDescription("A tool for creating UI navigation profiles with screen detection conditions")
        info.SetCopyright("(C) 2025")
        
        try:
            wx.adv.AboutBox(info)
        except:
            # Fallback if wx.adv is not available
            wx.MessageBox(f"{APP_TITLE} v{APP_VERSION}\nA tool for creating UI navigation profiles", "About", wx.OK | wx.ICON_INFORMATION)
    
    def on_exit(self, event):
        """Exit the application"""
        self.Close()
    
    def on_close(self, event):
        """Handle window close event"""
        if self.is_changed:
            dlg = wx.MessageDialog(self, 
                                  "Save changes before closing?",
                                  "Please confirm",
                                  wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            
            if result == wx.ID_YES:
                self.on_save(event)
                event.Skip()  # Continue with close
            elif result == wx.ID_NO:
                event.Skip()  # Continue with close without saving
            else:  # wx.ID_CANCEL
                event.Veto()  # Stop the close
        else:
            event.Skip()  # No changes, continue with close


class MenuCondition:
    """Class for defining and checking menu detection conditions"""
    
    def __init__(self):
        """Initialize the condition checker"""
        pass
    
    def check_condition(self, condition: dict, screenshot: np.ndarray) -> bool:
        """
        Check a single condition.
        
        Args:
            condition: Condition dictionary with type and parameters
            screenshot: Screenshot as numpy array
            
        Returns:
            bool: True if condition is met, False otherwise
        """
        condition_type = condition.get("type", "")
        
        if condition_type == "pixel_color":
            return self._check_pixel_color(
                screenshot,
                condition.get("x", 0),
                condition.get("y", 0),
                condition.get("color", [0, 0, 0]),
                condition.get("tolerance", 0)
            )
            
        elif condition_type == "pixel_region_color":
            return self._check_pixel_region_color(
                screenshot,
                condition.get("x1", 0),
                condition.get("y1", 0),
                condition.get("x2", 0),
                condition.get("y2", 0),
                condition.get("color", [0, 0, 0]),
                condition.get("tolerance", 0),
                condition.get("threshold", 0.5)
            )
            
        return False
    
    def check_menu_conditions(self, menu_conditions: list, screenshot: np.ndarray) -> bool:
        """
        Check if a menu is currently active based on its conditions.
        
        Args:
            menu_conditions: List of condition dictionaries
            screenshot: Screenshot as numpy array
            
        Returns:
            bool: True if all conditions are met, False otherwise
        """
        # If menu has no conditions, it's not active
        if not menu_conditions:
            return False
            
        # Check each condition - all must be met for the menu to be active
        for condition in menu_conditions:
            if not self.check_condition(condition, screenshot):
                return False
                
        return True
    
    def _check_pixel_color(
        self, 
        screenshot: np.ndarray, 
        x: int, 
        y: int, 
        color: list, 
        tolerance: int
    ) -> bool:
        """
        Check if a pixel at coordinates (x, y) has a specific color.
        
        Args:
            screenshot: Screenshot as numpy array
            x: X coordinate
            y: Y coordinate
            color: RGB color to check [R, G, B]
            tolerance: Color difference tolerance
            
        Returns:
            bool: True if pixel color matches, False otherwise
        """
        try:
            # Get the pixel color (BGR format)
            pixel_color = screenshot[y, x]
            
            # Convert to RGB for comparison (screenshot is BGR)
            pixel_color = pixel_color[::-1]
            
            # Calculate color difference
            diff = np.sqrt(np.sum((np.array(pixel_color) - np.array(color)) ** 2))
            
            return diff <= tolerance
        except Exception as e:
            print(f"Error checking pixel color: {str(e)}")
            return False
            
    def _check_pixel_region_color(
        self, 
        screenshot: np.ndarray, 
        x1: int, 
        y1: int, 
        x2: int, 
        y2: int, 
        color: list, 
        tolerance: int,
        threshold: float
    ) -> bool:
        """
        Check if a region of pixels has a specific color.
        
        Args:
            screenshot: Screenshot as numpy array
            x1, y1: Top-left coordinates
            x2, y2: Bottom-right coordinates
            color: RGB color to check [R, G, B]
            tolerance: Color difference tolerance
            threshold: Percentage of pixels that must match
            
        Returns:
            bool: True if enough pixels match the color, False otherwise
        """
        try:
            # Extract region
            region = screenshot[y1:y2, x1:x2]
            
            # Convert BGR to RGB
            region_rgb = region[:, :, ::-1]
            
            # Calculate color differences for each pixel
            color_diffs = np.sqrt(np.sum((region_rgb - np.array(color)) ** 2, axis=2))
            
            # Count matching pixels
            matching_pixels = np.count_nonzero(color_diffs <= tolerance)
            total_pixels = (x2 - x1) * (y2 - y1)
            
            # Check if enough pixels match
            return matching_pixels / total_pixels >= threshold
        except Exception as e:
            print(f"Error checking pixel region color: {str(e)}")
            return False


if __name__ == "__main__":
    app = wx.App()
    
    # Need to import wx.adv after wx.App is created
    try:
        import wx.adv
    except ImportError:
        pass
    
    # Initialize global cursor tracker
    global_cursor_tracker = get_cursor_tracker()
    
    frame = ProfileEditorFrame(None, APP_TITLE)
    frame.Show()
    app.MainLoop()