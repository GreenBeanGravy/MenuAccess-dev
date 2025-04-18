"""
Dialog windows for the Profile Creator application
"""

import wx
import threading
import pyautogui
from pynput import keyboard
from PIL import Image

from pflib.ui_components import ColorDisplay
from pflib.utils import get_cursor_tracker

class PixelPickerOverlay(wx.Dialog):
    """Interactive overlay for pixel picking with click-to-select functionality"""
    
    def __init__(self, parent):
        super().__init__(None, title="Pixel Picker", style=wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR | wx.NO_BORDER)
        self.parent = parent
        self.result = None
        
        # Take a full screenshot for reference
        self.screenshot = pyautogui.screenshot()
        screen_width, screen_height = self.screenshot.size
        
        # Make it full screen and semi-transparent
        self.SetTransparent(120)  # More transparent than region selector
        self.ShowFullScreen(True)
        
        # Create a panel to capture mouse events
        self.panel = wx.Panel(self)
        self.panel.SetSize(screen_width, screen_height)
        
        # Bind events
        self.panel.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        self.panel.Bind(wx.EVT_MOTION, self.on_motion)
        self.panel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        
        # Set focus for keyboard events
        self.panel.SetFocus()
        
        # Create a status display that follows the mouse
        self.status_overlay = wx.Frame(None, style=wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP | wx.NO_BORDER)
        self.status_overlay.SetTransparent(200)
        self.status_overlay.SetBackgroundColour(wx.Colour(0, 0, 0))
        self.status_label = wx.StaticText(self.status_overlay, label="Click to select pixel")
        self.status_label.SetForegroundColour(wx.WHITE)
        self.status_overlay.SetSize((200, 30))
        self.status_overlay.Show()
        
        # Instructions at the top of the screen
        instructions = wx.StaticText(self.panel, label="Click to select pixel, press Esc to cancel")
        instructions.SetForegroundColour(wx.WHITE)
        instructions.SetBackgroundColour(wx.Colour(0, 0, 0))
        font = wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        instructions.SetFont(font)
        # Center the instructions at the top
        text_width = instructions.GetSize().width
        instructions.SetPosition(((screen_width - text_width) // 2, 20))
        
        # Start the timer for updating status overlay
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer)
        self.timer.Start(50)  # Update 20 times per second
    
    def on_timer(self, event):
        # Update status overlay position to follow mouse
        mouse_pos = wx.GetMousePosition()
        self.status_overlay.SetPosition((mouse_pos.x + 15, mouse_pos.y + 15))
        
        # Update the label with current position and color
        x, y = pyautogui.position()
        try:
            pixel_color = self.screenshot.getpixel((x, y))
            self.status_label.SetLabel(f"({x}, {y}) RGB: {pixel_color}")
            # Adjust the width based on text
            text_width = self.status_label.GetSize().width
            self.status_overlay.SetSize((text_width + 20, 30))
        except:
            pass
    
    def on_click(self, event):
        """Handle mouse click to select a pixel"""
        # Get current pixel info
        x, y = pyautogui.position()
        try:
            pixel_color = self.screenshot.getpixel((x, y))
            self.result = (x, y, pixel_color)
            self.EndModal(wx.ID_OK)
        except Exception as e:
            print(f"Error capturing pixel: {e}")
    
    def on_motion(self, event):
        """Handle mouse movement"""
        # Update cursor position in status overlay
        pass
    
    def on_key_down(self, event):
        """Handle key press"""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        event.Skip()
    
    def get_result(self):
        """Get the selected pixel data"""
        return self.result
    
    def cleanup(self):
        """Clean up resources"""
        if self.timer.IsRunning():
            self.timer.Stop()
        if self.status_overlay:
            self.status_overlay.Destroy()


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
        """Begin the pixel picking process with click-to-select functionality"""
        # Iconize window to get it out of the way
        self.Iconize(True)
        
        # Stop tracker if running
        if self.cursor_tracker.is_active:
            self.cursor_tracker.stop_tracking()
        
        # Status text in parent's status bar if available
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Click to select a pixel, Esc to cancel")
        except:
            pass
        
        # Create and show the pixel picker overlay
        picker_overlay = PixelPickerOverlay(self)
        result = picker_overlay.ShowModal()
        
        # Process result
        if result == wx.ID_OK and picker_overlay.get_result():
            self.on_picker_complete(picker_overlay.get_result())
        else:
            # User canceled
            self.on_picker_complete(None)
        
        # Clean up
        picker_overlay.cleanup()
        picker_overlay.Destroy()
    
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

class RegionImageConditionDialog(wx.Dialog):
    """Dialog for creating/editing a region image condition that matches a captured screenshot"""
    
    def __init__(self, parent, title="Add Region Image Condition", condition=None):
        super().__init__(parent, title=title, size=(550, 650))
        
        self.condition = condition or {
            "type": "pixel_region_image",
            "x1": 0,
            "y1": 0,
            "x2": 100,
            "y2": 100,
            "confidence": 0.8,
            "image_data": None  # Will store base64 encoded image data
        }
        
        # Initialize selection variables
        self.selection_mode = False
        self.start_pos = None
        self.current_pos = None
        self.screenshot = None
        self.captured_region = None
        
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
        
        # Preview image section (shows selected region)
        preview_box = wx.StaticBox(panel, label="Region Preview")
        preview_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)
        
        # Add a static bitmap for image preview
        self.preview_text = wx.StaticText(panel, label="Select a region to see preview")
        preview_sizer.Add(self.preview_text, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Static bitmap to display the captured region
        self.preview_bitmap = wx.StaticBitmap(panel, size=(320, 240))
        preview_sizer.Add(self.preview_bitmap, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Add to main sizer
        vbox.Add(preview_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Confidence threshold section
        confidence_box = wx.StaticBox(panel, label="Match Confidence")
        confidence_sizer = wx.StaticBoxSizer(confidence_box, wx.VERTICAL)
        
        # Confidence slider
        confidence_label = wx.StaticText(panel, label=f"Confidence Threshold: {self.condition['confidence']:.2f}")
        self.confidence_slider = wx.Slider(panel, value=int(self.condition["confidence"] * 100),
                                         minValue=50, maxValue=100,
                                         style=wx.SL_HORIZONTAL | wx.SL_LABELS)
        
        self.confidence_slider.Bind(wx.EVT_SLIDER, self.on_confidence_changed)
        
        # Add to confidence section
        confidence_sizer.Add(confidence_label, flag=wx.EXPAND | wx.ALL, border=5)
        confidence_sizer.Add(self.confidence_slider, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Add confidence section to main sizer
        vbox.Add(confidence_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Help text
        help_text = wx.StaticText(panel, label="This condition checks if the captured region image appears on screen with the specified confidence level.")
        help_text.Wrap(500)  # Wrap text to fit dialog width
        vbox.Add(help_text, flag=wx.EXPAND | wx.ALL, border=10)
        
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
        
        # Load existing image if present
        if self.condition.get("image_data"):
            self.load_preview_from_base64()
    
    def on_confidence_changed(self, event):
        """Update the confidence label when slider is moved"""
        confidence = self.confidence_slider.GetValue() / 100.0
        for child in self.GetChildren():
            if isinstance(child, wx.Panel):
                for grandchild in child.GetChildren():
                    if isinstance(grandchild, wx.StaticBox):
                        for greatgrandchild in grandchild.GetChildren():
                            if isinstance(greatgrandchild, wx.StaticText) and "Confidence Threshold:" in greatgrandchild.GetLabel():
                                greatgrandchild.SetLabel(f"Confidence Threshold: {confidence:.2f}")
                                break
    
    def load_preview_from_base64(self):
        """Load the image preview from base64-encoded data"""
        import base64
        import io
        from PIL import Image
        
        try:
            # Decode the base64 image data
            image_data = base64.b64decode(self.condition["image_data"])
            
            # Create a PIL Image from the decoded data
            image = Image.open(io.BytesIO(image_data))
            
            # Convert PIL Image to wx.Bitmap
            width, height = image.size
            wximage = wx.Image(width, height)
            wximage.SetData(image.convert("RGB").tobytes())
            bitmap = wx.Bitmap(wximage)
            
            # Update the preview bitmap and text
            self.preview_bitmap.SetBitmap(bitmap)
            self.preview_text.SetLabel(f"Image: {width}x{height} pixels")
            self.captured_region = image
            
            # Update layout
            self.Layout()
        except Exception as e:
            self.preview_text.SetLabel(f"Error loading image: {str(e)}")
    
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
        """Process the selected region and capture the image"""
        # Update controls
        self.x1_ctrl.SetValue(x1)
        self.y1_ctrl.SetValue(y1)
        self.x2_ctrl.SetValue(x2)
        self.y2_ctrl.SetValue(y2)
        
        try:
            # Crop the region from our screenshot
            region = self.screenshot.crop((x1, y1, x2, y2))
            self.captured_region = region
            
            # Convert PIL Image to wx.Bitmap for preview
            width, height = region.size
            wximage = wx.Image(width, height)
            wximage.SetData(region.convert("RGB").tobytes())
            bitmap = wx.Bitmap(wximage)
            
            # Update preview
            self.preview_bitmap.SetBitmap(bitmap)
            self.preview_text.SetLabel(f"Image: {width}x{height} pixels")
            
            # Update layout
            self.Layout()
            
        except Exception as e:
            self.preview_text.SetLabel(f"Error capturing region: {str(e)}")
        
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
        import base64
        import io
        
        # Update coordinate values
        self.condition.update({
            "x1": self.x1_ctrl.GetValue(),
            "y1": self.y1_ctrl.GetValue(),
            "x2": self.x2_ctrl.GetValue(),
            "y2": self.y2_ctrl.GetValue(),
            "confidence": self.confidence_slider.GetValue() / 100.0,
        })
        
        # If we have a captured image, save it as base64
        if self.captured_region:
            # Save image to bytes buffer
            buffer = io.BytesIO()
            self.captured_region.save(buffer, format="PNG")
            
            # Convert to base64
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Store in condition
            self.condition["image_data"] = image_base64
        
        return self.condition


class OCRRegionDialog(wx.Dialog):
    """Dialog for creating/editing an OCR region with conditions support"""
    
    def __init__(self, parent, title="Add OCR Region", ocr_region=None):
        super().__init__(parent, title=title, size=(500, 550))  # Increased height for conditions
        
        self.ocr_region = ocr_region or {
            "x1": 0,
            "y1": 0,
            "x2": 100,
            "y2": 100,
            "tag": "ocr1",
            "conditions": []  # Initialize conditions list
        }
        
        # Initialize selection variables
        self.screenshot = None
        
        # Get cursor tracker
        self.cursor_tracker = get_cursor_tracker()
        
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Region coordinates group
        coord_box = wx.StaticBox(panel, label="OCR Region Coordinates")
        coord_sizer = wx.StaticBoxSizer(coord_box, wx.VERTICAL)
        
        # First row: Top-left corner
        tl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tl_label = wx.StaticText(panel, label="Top-left:")
        
        x1_label = wx.StaticText(panel, label="X1:")
        self.x1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.ocr_region["x1"]))
        
        y1_label = wx.StaticText(panel, label="Y1:")
        self.y1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.ocr_region["y1"]))
        
        tl_sizer.Add(tl_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        tl_sizer.Add(x1_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        tl_sizer.Add(self.x1_ctrl, proportion=1, flag=wx.RIGHT, border=10)
        tl_sizer.Add(y1_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        tl_sizer.Add(self.y1_ctrl, proportion=1)
        
        # Second row: Bottom-right corner
        br_sizer = wx.BoxSizer(wx.HORIZONTAL)
        br_label = wx.StaticText(panel, label="Bottom-right:")
        
        x2_label = wx.StaticText(panel, label="X2:")
        self.x2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.ocr_region["x2"]))
        
        y2_label = wx.StaticText(panel, label="Y2:")
        self.y2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.ocr_region["y2"]))
        
        br_sizer.Add(br_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        br_sizer.Add(x2_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        br_sizer.Add(self.x2_ctrl, proportion=1, flag=wx.RIGHT, border=10)
        br_sizer.Add(y2_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        br_sizer.Add(self.y2_ctrl, proportion=1)
        
        # Tag field
        tag_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tag_label = wx.StaticText(panel, label="OCR Tag:")
        self.tag_ctrl = wx.TextCtrl(panel, value=str(self.ocr_region["tag"]))
        tag_help = wx.StaticText(panel, label="(used as {tag} in announcement)")
        
        tag_sizer.Add(tag_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        tag_sizer.Add(self.tag_ctrl, proportion=1, flag=wx.RIGHT, border=8)
        tag_sizer.Add(tag_help, flag=wx.ALIGN_CENTER_VERTICAL)
        
        # Select region button
        self.region_btn = wx.Button(panel, label="Select Region on Screen")
        self.region_btn.Bind(wx.EVT_BUTTON, self.on_select_region)
        
        # Add to coordinate sizer
        coord_sizer.Add(tl_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        coord_sizer.Add(br_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        coord_sizer.Add(tag_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        coord_sizer.Add(self.region_btn, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Add to main sizer
        vbox.Add(coord_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Preview section (shows selected region)
        preview_box = wx.StaticBox(panel, label="Preview")
        preview_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)
        
        self.preview_text = wx.StaticText(panel, label="Select a region to see dimensions")
        preview_sizer.Add(self.preview_text, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Add to main sizer
        vbox.Add(preview_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # NEW: Conditions section
        conditions_box = wx.StaticBox(panel, label="OCR Activation Conditions")
        conditions_sizer = wx.StaticBoxSizer(conditions_box, wx.VERTICAL)
        
        # Conditions list
        self.conditions_list = wx.ListCtrl(panel, style=wx.LC_REPORT, size=(-1, 100))
        self.conditions_list.InsertColumn(0, "Type", width=120)
        self.conditions_list.InsertColumn(1, "Details", width=250)
        
        # Populate conditions list
        self.update_conditions_list()
        
        # Condition buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        add_pixel_btn = wx.Button(panel, label="Add Pixel Color")
        add_pixel_btn.Bind(wx.EVT_BUTTON, self.on_add_pixel_condition)
        btn_sizer.Add(add_pixel_btn, flag=wx.RIGHT, border=5)
        
        add_region_btn = wx.Button(panel, label="Add Region Color")
        add_region_btn.Bind(wx.EVT_BUTTON, self.on_add_region_condition)
        btn_sizer.Add(add_region_btn, flag=wx.RIGHT, border=5)
        
        delete_condition_btn = wx.Button(panel, label="Delete")
        delete_condition_btn.Bind(wx.EVT_BUTTON, self.on_delete_condition)
        btn_sizer.Add(delete_condition_btn)
        
        # Help text
        help_text = wx.StaticText(panel, label="OCR will only be performed when all conditions are met.")
        
        # Add to conditions section
        conditions_sizer.Add(self.conditions_list, flag=wx.EXPAND | wx.ALL, border=5)
        conditions_sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        conditions_sizer.Add(help_text, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Add to main sizer
        vbox.Add(conditions_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
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
        
    def update_conditions_list(self):
        """Update the conditions list with current data"""
        self.conditions_list.DeleteAllItems()
        
        if "conditions" not in self.ocr_region or not self.ocr_region["conditions"]:
            return
            
        for i, condition in enumerate(self.ocr_region["conditions"]):
            condition_type = condition.get("type", "unknown")
            
            if condition_type == "pixel_color":
                details = f"({condition['x']}, {condition['y']}) = RGB{condition['color']} +/-{condition['tolerance']}"
            elif condition_type == "pixel_region_color":
                details = f"Region ({condition['x1']}, {condition['y1']}) to ({condition['x2']}, {condition['y2']}), " \
                          f"RGB{condition['color']} +/-{condition['tolerance']}, thresh={condition['threshold']}"
            else:
                details = str(condition)
            
            idx = self.conditions_list.InsertItem(i, condition_type)
            self.conditions_list.SetItem(idx, 1, details)
    
    def on_add_pixel_condition(self, event):
        """Add a new pixel color condition"""
        from pflib.dialogs import PixelColorConditionDialog
        
        dialog = PixelColorConditionDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            condition = dialog.get_condition()
            
            if "conditions" not in self.ocr_region:
                self.ocr_region["conditions"] = []
                
            self.ocr_region["conditions"].append(condition)
            self.update_conditions_list()
            
        dialog.Destroy()
    
    def on_add_region_condition(self, event):
        """Add a new region color condition"""
        from pflib.dialogs import RegionColorConditionDialog
        
        dialog = RegionColorConditionDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            condition = dialog.get_condition()
            
            if "conditions" not in self.ocr_region:
                self.ocr_region["conditions"] = []
                
            self.ocr_region["conditions"].append(condition)
            self.update_conditions_list()
            
        dialog.Destroy()
    
    def on_delete_condition(self, event):
        """Delete the selected condition"""
        selected = self.conditions_list.GetFirstSelected()
        if selected == -1:
            return
        
        if "conditions" not in self.ocr_region:
            return
            
        # Confirm deletion
        if wx.MessageBox("Are you sure you want to delete this condition?", 
                         "Confirm", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
            
        # Delete the condition
        del self.ocr_region["conditions"][selected]
        self.update_conditions_list()
    
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
        
        # Use wx.CallAfter to ensure we're in the main thread
        wx.CallAfter(self._do_select_region)
    
    def _do_select_region(self):
        """Perform the interactive region selection"""
        # Create a selection overlay dialog
        overlay = wx.Dialog(None, title="OCR Region Selector", 
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
                dc.SetPen(wx.Pen(wx.GREEN, 2))
                dc.SetBrush(wx.Brush(wx.Colour(0, 255, 0, 64)))  # Semi-transparent green
                
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
            
            # Process the selection
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
        info_text = "Click and drag to select an OCR region. Press ESC to cancel."
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
        
        # Extract region info
        try:
            # Crop the region from our screenshot
            region = self.screenshot.crop((x1, y1, x2, y2))
            
            # Update preview text
            region_size = region.size
            self.preview_text.SetLabel(f"OCR Region: {region_size[0]}x{region_size[1]} pixels")
            
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
    
    def get_ocr_region(self):
        """Get the OCR region data from the dialog"""
        self.ocr_region.update({
            "x1": self.x1_ctrl.GetValue(),
            "y1": self.y1_ctrl.GetValue(),
            "x2": self.x2_ctrl.GetValue(),
            "y2": self.y2_ctrl.GetValue(),
            "tag": self.tag_ctrl.GetValue() or "ocr1"
            # conditions are updated directly when added/removed
        })
        return self.ocr_region


class UIElementDialog(wx.Dialog):
    """Dialog for creating/editing a UI element"""
    
    def __init__(self, parent, title="Add UI Element", element=None):
        # Increased height to ensure all sections are visible
        super().__init__(parent, title=title, size=(550, 850))  # Increased height for conditions
        
        # Default values if no element is provided
        self.element = element or [
            (0, 0),            # coordinates
            "New Element",     # name
            "button",          # element_type
            False,             # speaks_on_select
            None,              # submenu_id
            "default",         # group
            [],                # ocr_regions
            None,              # custom_announcement
            0,                 # index (new)
            []                 # conditions (new)
        ]
        
        # Ensure the element has all fields
        while len(self.element) < 10:
            if len(self.element) == 6:  # Add OCR regions
                self.element.append([])
            elif len(self.element) == 7:  # Add custom announcement
                self.element.append(None)
            elif len(self.element) == 8:  # Add index
                self.element.append(0)
            elif len(self.element) == 9:  # Add conditions
                self.element.append([])
            else:  # Add any missing fields (for backward compatibility)
                self.element.append(None)
        
        # Store screenshot for element info
        self.screenshot = None
        
        # Get cursor tracker
        self.cursor_tracker = get_cursor_tracker()
        
        # Picker thread
        self.picker_thread = None
        
        # Create a scrolled panel to ensure all sections are visible
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        # Use a scrolled panel instead of a regular panel to enable scrolling
        panel = wx.lib.scrolledpanel.ScrolledPanel(self)
        panel.SetupScrolling(scroll_x=False, scroll_y=True)
        
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
        
        # Group
        group_box = wx.BoxSizer(wx.HORIZONTAL)
        group_label = wx.StaticText(panel, label="Group:")
        # Default group options
        standard_groups = ["default", "tab-bar", "main-content", "side-panel", "footer"]
        # Use a combobox to allow both selection from predefined options and custom input
        self.group_ctrl = wx.ComboBox(panel, choices=standard_groups, 
                                    value=str(self.element[5] if len(self.element) > 5 else "default"))
        group_box.Add(group_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        group_box.Add(self.group_ctrl, proportion=1)
        
        # Add to properties section
        props_sizer.Add(name_box, flag=wx.EXPAND | wx.ALL, border=5)
        props_sizer.Add(type_box, flag=wx.EXPAND | wx.ALL, border=5)
        props_sizer.Add(self.speaks_ctrl, flag=wx.EXPAND | wx.ALL, border=5)
        props_sizer.Add(submenu_box, flag=wx.EXPAND | wx.ALL, border=5)
        props_sizer.Add(group_box, flag=wx.EXPAND | wx.ALL, border=5)
        
        vbox.Add(props_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # OCR Regions section
        ocr_box = wx.StaticBox(panel, label="OCR Regions")
        ocr_sizer = wx.StaticBoxSizer(ocr_box, wx.VERTICAL)
        
        # OCR Regions list
        self.ocr_list = wx.ListCtrl(panel, style=wx.LC_REPORT, size=(-1, 100))
        self.ocr_list.InsertColumn(0, "Tag", width=60)
        self.ocr_list.InsertColumn(1, "Region", width=200)
        
        # Populate OCR regions list
        self.update_ocr_list()
        
        # OCR button sizer
        ocr_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Add OCR region button
        add_ocr_btn = wx.Button(panel, label="Add OCR Region")
        add_ocr_btn.Bind(wx.EVT_BUTTON, self.on_add_ocr_region)
        ocr_btn_sizer.Add(add_ocr_btn, flag=wx.RIGHT, border=5)
        
        # Edit OCR region button
        edit_ocr_btn = wx.Button(panel, label="Edit OCR Region")
        edit_ocr_btn.Bind(wx.EVT_BUTTON, self.on_edit_ocr_region)
        ocr_btn_sizer.Add(edit_ocr_btn, flag=wx.RIGHT, border=5)
        
        # Delete OCR region button
        del_ocr_btn = wx.Button(panel, label="Delete OCR Region")
        del_ocr_btn.Bind(wx.EVT_BUTTON, self.on_delete_ocr_region)
        ocr_btn_sizer.Add(del_ocr_btn)
        
        # Add to OCR section
        ocr_sizer.Add(self.ocr_list, flag=wx.EXPAND | wx.ALL, border=5)
        ocr_sizer.Add(ocr_btn_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        
        vbox.Add(ocr_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # Element Index
        index_box = wx.BoxSizer(wx.HORIZONTAL)
        index_label = wx.StaticText(panel, label="Display Index:")
        self.index_ctrl = wx.SpinCtrl(panel, min=0, max=999, value=str(self.element[8]))
        index_help = wx.StaticText(panel, label="(Determines order in group)")
        
        index_box.Add(index_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        index_box.Add(self.index_ctrl, proportion=1, flag=wx.RIGHT, border=8)
        index_box.Add(index_help, flag=wx.ALIGN_CENTER_VERTICAL)
        
        vbox.Add(index_box, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Element Conditions section
        condition_box = wx.StaticBox(panel, label="Element Conditions")
        condition_sizer = wx.StaticBoxSizer(condition_box, wx.VERTICAL)
        
        # Enable conditions checkbox
        self.has_conditions_cb = wx.CheckBox(panel, label="This element has its own activation conditions")
        self.has_conditions_cb.SetValue(len(self.element) > 9 and len(self.element[9]) > 0)
        self.has_conditions_cb.Bind(wx.EVT_CHECKBOX, self.on_has_conditions_toggled)
        condition_sizer.Add(self.has_conditions_cb, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Conditions list
        self.conditions_list = wx.ListCtrl(panel, style=wx.LC_REPORT, size=(-1, 150))
        self.conditions_list.InsertColumn(0, "Type", width=150)
        self.conditions_list.InsertColumn(1, "Details", width=350)
        self.conditions_list.Enable(self.has_conditions_cb.GetValue())
        condition_sizer.Add(self.conditions_list, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Populate conditions list
        self.update_conditions_list()
        
        # Condition Buttons
        condition_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.add_pixel_condition_btn = wx.Button(panel, label="Add Pixel Color")
        self.add_pixel_condition_btn.Bind(wx.EVT_BUTTON, self.on_add_pixel_condition)
        self.add_pixel_condition_btn.Enable(self.has_conditions_cb.GetValue())
        
        self.add_region_condition_btn = wx.Button(panel, label="Add Region Color")
        self.add_region_condition_btn.Bind(wx.EVT_BUTTON, self.on_add_region_condition)
        self.add_region_condition_btn.Enable(self.has_conditions_cb.GetValue())
        
        self.add_image_condition_btn = wx.Button(panel, label="Add Region Image")
        self.add_image_condition_btn.Bind(wx.EVT_BUTTON, self.on_add_region_image_condition)
        self.add_image_condition_btn.Enable(self.has_conditions_cb.GetValue())
        
        self.delete_condition_btn = wx.Button(panel, label="Delete")
        self.delete_condition_btn.Bind(wx.EVT_BUTTON, self.on_delete_condition)
        self.delete_condition_btn.Enable(self.has_conditions_cb.GetValue())
        
        condition_btn_sizer.Add(self.add_pixel_condition_btn, flag=wx.RIGHT, border=5)
        condition_btn_sizer.Add(self.add_region_condition_btn, flag=wx.RIGHT, border=5)
        condition_btn_sizer.Add(self.add_image_condition_btn, flag=wx.RIGHT, border=5)
        condition_btn_sizer.Add(self.delete_condition_btn)
        
        condition_sizer.Add(condition_btn_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Help text for conditions
        help_text = wx.StaticText(panel, label="Element conditions are checked only when the parent menu is active.")
        help_text.Wrap(500)
        condition_sizer.Add(help_text, flag=wx.EXPAND | wx.ALL, border=5)
        
        vbox.Add(condition_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Custom Announcement section - making it more visible
        announce_box = wx.StaticBox(panel, label="Custom Announcement")
        announce_sizer = wx.StaticBoxSizer(announce_box, wx.VERTICAL)
        
        # Enable custom announcement checkbox
        self.custom_announce_cb = wx.CheckBox(panel, label="Use custom announcement format")
        self.custom_announce_cb.SetValue(self.element[7] is not None)
        self.custom_announce_cb.Bind(wx.EVT_CHECKBOX, self.on_custom_announce_toggled)
        
        # Custom announcement template field - making it larger
        template_label = wx.StaticText(panel, label="Format Template:")
        self.template_ctrl = wx.TextCtrl(panel, 
                                      value=str(self.element[7] or "{name}, {type}, {index}"),
                                      size=(-1, 80), style=wx.TE_MULTILINE)  # Taller textbox
        self.template_ctrl.Enable(self.element[7] is not None)
        
        # Help text - more detailed
        help_text = wx.StaticText(panel, label="Available tags: {name}, {type}, {index}, {menu}, {submenu}, {group}")
        help_ocr = wx.StaticText(panel, label="OCR tags: Reference OCR regions with their tag names, e.g. {ocr1}")
        
        # Add to announcement section
        announce_sizer.Add(self.custom_announce_cb, flag=wx.EXPAND | wx.ALL, border=5)
        announce_sizer.Add(template_label, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=5)
        announce_sizer.Add(self.template_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=5)
        announce_sizer.Add(help_text, flag=wx.EXPAND | wx.ALL, border=5)
        announce_sizer.Add(help_ocr, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)
        
        vbox.Add(announce_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
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
        panel.Layout()
        
        # Ensure the panel is sized properly to include all elements
        panel.SetMinSize(panel.GetBestSize())
        
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
    
    def on_custom_announce_toggled(self, event):
        """Handle toggling the custom announcement checkbox"""
        is_enabled = event.IsChecked()
        self.template_ctrl.Enable(is_enabled)
        
        # Set default template if enabling
        if is_enabled and not self.template_ctrl.GetValue():
            self.template_ctrl.SetValue("{name}, {type}, {index}")
    
    def update_ocr_list(self):
        """Update the OCR regions list"""
        self.ocr_list.DeleteAllItems()
        
        ocr_regions = self.element[6] if len(self.element) > 6 else []
        
        for i, region in enumerate(ocr_regions):
            tag = region.get("tag", f"ocr{i+1}")
            region_text = f"({region.get('x1', 0)}, {region.get('y1', 0)}) to ({region.get('x2', 0)}, {region.get('y2', 0)})"
            
            # Add condition count if present
            condition_count = len(region.get("conditions", []))
            if condition_count > 0:
                region_text += f" [{condition_count} conditions]"
            
            idx = self.ocr_list.InsertItem(i, tag)
            self.ocr_list.SetItem(idx, 1, region_text)
    
    def on_add_ocr_region(self, event):
        """Add a new OCR region"""
        # Create OCR tag based on existing regions
        ocr_regions = self.element[6] if len(self.element) > 6 else []
        existing_tags = set(region.get("tag", f"ocr{i+1}") for i, region in enumerate(ocr_regions))
        
        # Find a unique tag
        new_tag = "ocr1"
        counter = 1
        while new_tag in existing_tags:
            counter += 1
            new_tag = f"ocr{counter}"
        
        # Create dialog for OCR region
        dialog = OCRRegionDialog(self, title="Add OCR Region", 
                               ocr_region={"x1": 0, "y1": 0, "x2": 100, "y2": 100, "tag": new_tag})
        
        if dialog.ShowModal() == wx.ID_OK:
            # Get region data
            ocr_region = dialog.get_ocr_region()
            
            # Add to element
            if len(self.element) <= 6:
                self.element.append([])
            
            self.element[6].append(ocr_region)
            
            # Update list
            self.update_ocr_list()
        
        dialog.Destroy()
    
    def on_edit_ocr_region(self, event):
        """Edit the selected OCR region"""
        selected = self.ocr_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Please select an OCR region to edit", "No Selection", wx.ICON_INFORMATION)
            return
        
        ocr_regions = self.element[6] if len(self.element) > 6 else []
        if selected >= len(ocr_regions):
            return
        
        # Create dialog for OCR region
        dialog = OCRRegionDialog(self, title="Edit OCR Region", ocr_region=ocr_regions[selected])
        
        if dialog.ShowModal() == wx.ID_OK:
            # Get updated region data
            updated_region = dialog.get_ocr_region()
            
            # Update element
            ocr_regions[selected] = updated_region
            
            # Update list
            self.update_ocr_list()
        
        dialog.Destroy()
    
    def on_delete_ocr_region(self, event):
        """Delete the selected OCR region"""
        selected = self.ocr_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Please select an OCR region to delete", "No Selection", wx.ICON_INFORMATION)
            return
        
        ocr_regions = self.element[6] if len(self.element) > 6 else []
        if selected >= len(ocr_regions):
            return
        
        # Confirm deletion
        if wx.MessageBox("Are you sure you want to delete this OCR region?", 
                       "Confirm Deletion", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        
        # Delete the region
        del ocr_regions[selected]
        
        # Update list
        self.update_ocr_list()
    
    def on_pick_location(self, event):
        """Interactive location picker with click-to-select functionality"""
        self.Iconize(True)
        
        # Stop tracker if running
        if self.cursor_tracker.is_active:
            self.cursor_tracker.stop_tracking()
        
        # Status text in parent's status bar if available
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Click to select element position, Esc to cancel")
        except:
            pass
        
        # Take a screenshot for later use
        self.screenshot = pyautogui.screenshot()
        
        # Create and show the pixel picker overlay
        picker_overlay = PixelPickerOverlay(self)
        result = picker_overlay.ShowModal()
        
        # Process result
        if result == wx.ID_OK and picker_overlay.get_result():
            self.end_picking(picker_overlay.get_result())
        else:
            # User canceled
            self.end_picking(None)
        
        # Clean up
        picker_overlay.cleanup()
        picker_overlay.Destroy()
    
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
            
        # Get the group value, defaulting to "default" if empty
        group = self.group_ctrl.GetValue()
        if not group:
            group = "default"
            
        # Get OCR regions
        ocr_regions = self.element[6] if len(self.element) > 6 else []
        
        # Get custom announcement template
        announcement = None
        if self.custom_announce_cb.GetValue():
            announcement = self.template_ctrl.GetValue()
            
        # Get index
        index = self.index_ctrl.GetValue()
        
        # Get conditions (only if enabled)
        conditions = []
        if self.has_conditions_cb.GetValue() and len(self.element) > 9:
            conditions = self.element[9]
            
        return [
            (self.x_ctrl.GetValue(), self.y_ctrl.GetValue()),
            self.name_ctrl.GetValue(),
            self.type_ctrl.GetString(self.type_ctrl.GetSelection()),
            self.speaks_ctrl.GetValue(),
            submenu_id,
            group,
            ocr_regions,
            announcement,
            index,
            conditions
        ]

    def on_has_conditions_toggled(self, event):
        """Handle toggling the conditions checkbox"""
        enabled = event.IsChecked()
        self.conditions_list.Enable(enabled)
        self.add_pixel_condition_btn.Enable(enabled)
        self.add_region_condition_btn.Enable(enabled)
        self.add_image_condition_btn.Enable(enabled)
        self.delete_condition_btn.Enable(enabled)
        
        # If disabling, clear all conditions
        if not enabled and len(self.element) > 9:
            self.element[9] = []
            self.update_conditions_list()
    
    def update_conditions_list(self):
        """Update the conditions list with current data"""
        self.conditions_list.DeleteAllItems()
        
        if len(self.element) <= 9 or not self.element[9]:
            return
            
        for i, condition in enumerate(self.element[9]):
            condition_type = condition.get("type", "unknown")
            
            if condition_type == "pixel_color":
                details = f"({condition['x']}, {condition['y']}) = RGB{condition['color']} +/-{condition['tolerance']}"
            elif condition_type == "pixel_region_color":
                details = f"Region ({condition['x1']}, {condition['y1']}) to ({condition['x2']}, {condition['y2']}), " \
                          f"RGB{condition['color']} +/-{condition['tolerance']}, thresh={condition['threshold']}"
            elif condition_type == "pixel_region_image":
                details = f"Region ({condition['x1']}, {condition['y1']}) to ({condition['x2']}, {condition['y2']}), " \
                          f"confidence={condition['confidence']:.2f}, has_image={'Yes' if condition.get('image_data') else 'No'}"
            else:
                details = str(condition)
            
            idx = self.conditions_list.InsertItem(i, condition_type)
            self.conditions_list.SetItem(idx, 1, details)
    
    def on_add_pixel_condition(self, event):
        """Add a new pixel color condition"""
        dialog = PixelColorConditionDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            condition = dialog.get_condition()
            
            # Ensure element has conditions list
            if len(self.element) <= 9:
                self.element.append([])
                
            # Add the condition
            self.element[9].append(condition)
            self.update_conditions_list()
            
        dialog.Destroy()
    
    def on_add_region_condition(self, event):
        """Add a new region color condition"""
        dialog = RegionColorConditionDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            condition = dialog.get_condition()
            
            # Ensure element has conditions list
            if len(self.element) <= 9:
                self.element.append([])
                
            # Add the condition
            self.element[9].append(condition)
            self.update_conditions_list()
            
        dialog.Destroy()
    
    def on_add_region_image_condition(self, event):
        """Add a new region image condition"""
        dialog = RegionImageConditionDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            condition = dialog.get_condition()
            
            # Ensure element has conditions list
            if len(self.element) <= 9:
                self.element.append([])
                
            # Add the condition
            self.element[9].append(condition)
            self.update_conditions_list()
            
        dialog.Destroy()
    
    def on_delete_condition(self, event):
        """Delete the selected condition"""
        selected_idx = self.conditions_list.GetFirstSelected()
        if selected_idx == -1:
            return
            
        # Confirm deletion
        if wx.MessageBox("Are you sure you want to delete this condition?", 
                        "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
            
        # Delete the condition
        del self.element[9][selected_idx]
        self.update_conditions_list()