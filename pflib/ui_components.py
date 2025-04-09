"""
UI Components for the Profile Creator application
"""

import wx
import pyautogui

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