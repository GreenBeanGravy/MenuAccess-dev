"""
Dialog windows for the Profile Creator application - COMPLETE FIXED VERSION
"""

import wx
import wx.lib.scrolledpanel
import threading
from pynput import keyboard
from PIL import Image
import base64
import io

from pflib.ui_components import ColorDisplay
from pflib.utils import get_cursor_tracker
from malib.screen_capture import ScreenCapture

# --- Condition Dialogs ---

class BaseConditionDialog(wx.Dialog):
    """Base class for condition dialogs to include common elements like 'negate'."""
    def __init__(self, parent, title, condition_type_default="unknown"):
        super().__init__(parent, title=title)
        self.condition_data = {"type": condition_type_default, "negate": False}
        self.screen_capture = ScreenCapture()

    def _add_negate_checkbox(self, panel, sizer):
        self.negate_cb = wx.CheckBox(panel, label="Negate this condition (NOT)")
        self.negate_cb.SetValue(self.condition_data.get("negate", False))
        sizer.Add(self.negate_cb, flag=wx.ALL, border=10)

    def _get_common_condition_data(self):
        self.condition_data["negate"] = self.negate_cb.GetValue()
        return self.condition_data

class PixelPickerOverlay(wx.Dialog):
    """Interactive overlay for pixel picking with click-to-select functionality"""
    
    def __init__(self, parent):
        super().__init__(None, title="Pixel Picker", style=wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR | wx.NO_BORDER)
        self.parent = parent
        self.result = None
        
        # Use unified screen capture
        self.screen_capture = ScreenCapture()
        
        # Take a full screenshot for reference
        self.screenshot = self.screen_capture.capture()
        screen_width, screen_height = self.screenshot.size
        
        # Don't show full screen here - do it in ShowModal
        self.SetSize(screen_width, screen_height)
        
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
        
        # Instructions at the top of the screen
        instructions_text = "Click to select pixel, press Esc to cancel"
        instructions = wx.StaticText(self.panel, label=instructions_text)
        instructions.SetForegroundColour(wx.WHITE)
        instructions.SetBackgroundColour(wx.Colour(0, 0, 0))
        font = wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        instructions.SetFont(font)
        
        # Get text dimensions properly - FIXED
        dc = wx.ScreenDC()
        dc.SetFont(font)
        text_width, text_height = dc.GetTextExtent(instructions_text)
        
        # Center the instructions at the top
        instructions.SetPosition(((screen_width - text_width) // 2, 20))
        
        # Initialize timer but don't start it yet
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer)
    
    def ShowModal(self):
        """Override ShowModal to set up full screen display properly"""
        # Make it full screen and semi-transparent
        self.SetTransparent(120)
        self.ShowFullScreen(True)
        self.status_overlay.Show()
        
        # Start the timer for updating status overlay
        self.timer.Start(50)  # Update 20 times per second
        
        # Call the parent ShowModal
        return super().ShowModal()
    
    def on_timer(self, event):
        # Update status overlay position to follow mouse
        mouse_pos = wx.GetMousePosition()
        self.status_overlay.SetPosition((mouse_pos.x + 15, mouse_pos.y + 15))
        
        # Update the label with current position and color
        x, y = mouse_pos.x, mouse_pos.y
        try:
            # Ensure x,y are within screenshot bounds
            if 0 <= x < self.screenshot.width and 0 <= y < self.screenshot.height:
                pixel_color = self.screenshot.getpixel((x, y))
                if len(pixel_color) > 3: 
                    pixel_color = pixel_color[:3]
                self.status_label.SetLabel(f"({x}, {y}) RGB: {pixel_color}")
                # Adjust the width based on text
                dc = wx.ScreenDC()
                text_width, text_height = dc.GetTextExtent(self.status_label.GetLabel())
                self.status_overlay.SetSize((text_width + 20, 30))
            else:
                self.status_label.SetLabel(f"({x}, {y}) Out of bounds")
        except Exception:
            self.status_label.SetLabel(f"({x}, {y}) Error reading pixel")
    
    def on_click(self, event):
        """Handle mouse click to select a pixel"""
        # Get current pixel info
        mouse_pos = wx.GetMousePosition()
        x, y = mouse_pos.x, mouse_pos.y
        try:
            if 0 <= x < self.screenshot.width and 0 <= y < self.screenshot.height:
                pixel_color = self.screenshot.getpixel((x, y))
                if len(pixel_color) > 3: 
                    pixel_color = pixel_color[:3]
                self.result = (x, y, pixel_color)
                self.EndModal(wx.ID_OK)
            else:
                wx.MessageBox("Clicked outside of screen bounds.", "Error", wx.ICON_ERROR)
        except Exception as e:
            print(f"Error capturing pixel: {e}")
            wx.MessageBox(f"Error capturing pixel: {e}", "Error", wx.ICON_ERROR)
    
    def on_motion(self, event):
        """Handle mouse movement"""
        # Update cursor position in status overlay (done by timer)
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
        if hasattr(self, 'timer') and self.timer.IsRunning():
            self.timer.Stop()
        if hasattr(self, 'status_overlay') and self.status_overlay:
            self.status_overlay.Destroy()
            self.status_overlay = None
        if hasattr(self, 'screen_capture'):
            self.screen_capture.close()
    
    def Destroy(self):
        """Override Destroy to ensure cleanup"""
        self.cleanup()
        return super().Destroy()


class PixelColorConditionDialog(BaseConditionDialog):
    """Dialog for creating/editing a pixel color condition"""
    
    def __init__(self, parent, title="Add Pixel Color Condition", condition=None):
        super().__init__(parent, title, condition_type_default="pixel_color")
        
        self.condition_data.update(condition or {
            "x": 0, "y": 0, "color": [255, 255, 255], "tolerance": 10, "negate": False
        })
        
        self.cursor_tracker = get_cursor_tracker()
        self.picker_thread = None
        
        self.init_ui()
        self.SetSize((400, 400))
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        coord_box = wx.StaticBox(panel, label="Coordinates")
        coord_sizer = wx.StaticBoxSizer(coord_box, wx.HORIZONTAL)
        
        x_box = wx.BoxSizer(wx.HORIZONTAL)
        x_label = wx.StaticText(panel, label="X:")
        self.x_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["x"]))
        x_box.Add(x_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        x_box.Add(self.x_ctrl, proportion=1)
        
        y_box = wx.BoxSizer(wx.HORIZONTAL)
        y_label = wx.StaticText(panel, label="Y:")
        self.y_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["y"]))
        y_box.Add(y_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        y_box.Add(self.y_ctrl, proportion=1)
        
        coord_sizer.Add(x_box, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10)
        coord_sizer.Add(y_box, proportion=1, flag=wx.EXPAND)
        vbox.Add(coord_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        color_label = wx.StaticText(panel, label="Color:")
        self.color_display = ColorDisplay(panel, initial_color=tuple(self.condition_data["color"]))
        vbox.Add(color_label, flag=wx.LEFT, border=10)
        vbox.Add(self.color_display, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)
        
        tolerance_box = wx.BoxSizer(wx.HORIZONTAL)
        tolerance_label = wx.StaticText(panel, label="Tolerance:")
        self.tolerance_ctrl = wx.SpinCtrl(panel, min=0, max=255, value=str(self.condition_data["tolerance"]))
        tolerance_help = wx.StaticText(panel, label="(0-255)")
        tolerance_box.Add(tolerance_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        tolerance_box.Add(self.tolerance_ctrl, proportion=1, flag=wx.RIGHT, border=8) 
        tolerance_box.Add(tolerance_help, flag=wx.ALIGN_CENTER_VERTICAL)
        vbox.Add(tolerance_box, flag=wx.EXPAND | wx.ALL, border=10)

        self._add_negate_checkbox(panel, vbox)
        
        instructions = wx.StaticText(panel, label="Move cursor to desired position, then press Enter to select")
        vbox.Add(instructions, flag=wx.ALL, border=10)
        
        self.screen_pick_btn = wx.Button(panel, label="Pick Pixel from Screen")
        self.screen_pick_btn.Bind(wx.EVT_BUTTON, self.on_pick_from_screen)
        vbox.Add(self.screen_pick_btn, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        
        button_box = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_box.AddButton(ok_button)
        button_box.AddButton(cancel_button)
        button_box.Realize()
        vbox.Add(button_box, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        panel.SetSizer(vbox)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
    def on_close(self, event):
        if self.cursor_tracker.is_active:
            self.cursor_tracker.stop_tracking()
        if hasattr(self, 'screen_capture'):
            self.screen_capture.close()
        event.Skip()
    
    def on_pick_from_screen(self, event):
        self.Iconize(True)
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Click to select a pixel, Esc to cancel")
        except: 
            pass
        
        picker_overlay = PixelPickerOverlay(self)
        result = picker_overlay.ShowModal()
        
        if result == wx.ID_OK and picker_overlay.get_result():
            self.on_picker_complete(picker_overlay.get_result())
        else:
            self.on_picker_complete(None)
        
        picker_overlay.cleanup()
        picker_overlay.Destroy()
    
    def on_picker_complete(self, result):
        if result:
            x, y, pixel_color = result
            self.x_ctrl.SetValue(x)
            self.y_ctrl.SetValue(y)
            self.color_display.SetColor(pixel_color)
        
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass
    
    def get_condition(self):
        self._get_common_condition_data()
        self.condition_data.update({
            "x": self.x_ctrl.GetValue(),
            "y": self.y_ctrl.GetValue(),
            "color": list(self.color_display.GetColor()),
            "tolerance": self.tolerance_ctrl.GetValue()
        })
        return self.condition_data


class RegionColorConditionDialog(BaseConditionDialog):
    """Dialog for creating/editing a region color condition"""
    
    def __init__(self, parent, title="Add Region Color Condition", condition=None):
        super().__init__(parent, title, condition_type_default="pixel_region_color")
        
        self.condition_data.update(condition or {
            "x1": 0, "y1": 0, "x2": 100, "y2": 100,
            "color": [255, 255, 255], "tolerance": 10, "threshold": 0.5, "negate": False
        })
        
        self.selection_mode = False
        self.start_pos = None
        self.current_pos = None
        self.screenshot = None
        self.cursor_tracker = get_cursor_tracker()
        
        self.init_ui()
        self.SetSize((500, 600))
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        coord_box = wx.StaticBox(panel, label="Region Coordinates")
        coord_sizer = wx.StaticBoxSizer(coord_box, wx.VERTICAL)
        
        tl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tl_label = wx.StaticText(panel, label="Top-left:")
        x1_label = wx.StaticText(panel, label="X1:")
        self.x1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["x1"]))
        y1_label = wx.StaticText(panel, label="Y1:")
        self.y1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["y1"]))
        tl_sizer.Add(tl_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        tl_sizer.Add(x1_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        tl_sizer.Add(self.x1_ctrl, proportion=1, flag=wx.RIGHT, border=10)
        tl_sizer.Add(y1_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        tl_sizer.Add(self.y1_ctrl, proportion=1)
        
        br_sizer = wx.BoxSizer(wx.HORIZONTAL)
        br_label = wx.StaticText(panel, label="Bottom-right:")
        x2_label = wx.StaticText(panel, label="X2:")
        self.x2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["x2"]))
        y2_label = wx.StaticText(panel, label="Y2:")
        self.y2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["y2"]))
        br_sizer.Add(br_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        br_sizer.Add(x2_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        br_sizer.Add(self.x2_ctrl, proportion=1, flag=wx.RIGHT, border=10)
        br_sizer.Add(y2_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        br_sizer.Add(self.y2_ctrl, proportion=1)
        
        self.region_btn = wx.Button(panel, label="Select Region on Screen")
        self.region_btn.Bind(wx.EVT_BUTTON, self.on_select_region)
        coord_sizer.Add(tl_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        coord_sizer.Add(br_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        coord_sizer.Add(self.region_btn, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(coord_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        preview_box = wx.StaticBox(panel, label="Region Preview")
        preview_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)
        self.preview_text = wx.StaticText(panel, label="Select a region to see preview")
        preview_sizer.Add(self.preview_text, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(preview_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        color_box = wx.StaticBox(panel, label="Region Color")
        color_sizer = wx.StaticBoxSizer(color_box, wx.VERTICAL)
        color_label = wx.StaticText(panel, label="Color:")
        self.color_display = ColorDisplay(panel, initial_color=tuple(self.condition_data["color"]))
        self.color_btn = wx.Button(panel, label="Pick Color from Screen")
        self.color_btn.Bind(wx.EVT_BUTTON, self.on_pick_color)
        color_sizer.Add(color_label, flag=wx.LEFT | wx.TOP, border=5)
        color_sizer.Add(self.color_display, flag=wx.EXPAND | wx.ALL, border=5)
        color_sizer.Add(self.color_btn, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(color_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        param_box = wx.StaticBox(panel, label="Detection Parameters")
        param_sizer = wx.StaticBoxSizer(param_box, wx.VERTICAL)
        tolerance_box = wx.BoxSizer(wx.HORIZONTAL)
        tolerance_label = wx.StaticText(panel, label="Tolerance:")
        self.tolerance_ctrl = wx.SpinCtrl(panel, min=0, max=255, value=str(self.condition_data["tolerance"]))
        tolerance_help = wx.StaticText(panel, label="(color variation allowed)")
        tolerance_box.Add(tolerance_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        tolerance_box.Add(self.tolerance_ctrl, proportion=1, flag=wx.RIGHT, border=8)
        tolerance_box.Add(tolerance_help, flag=wx.ALIGN_CENTER_VERTICAL)
        
        threshold_box = wx.BoxSizer(wx.HORIZONTAL)
        threshold_label = wx.StaticText(panel, label="Threshold:")
        self.threshold_ctrl = wx.SpinCtrlDouble(panel, min=0, max=1, inc=0.01, value=str(self.condition_data["threshold"]))
        threshold_help = wx.StaticText(panel, label="(% of pixels that must match)")
        threshold_box.Add(threshold_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        threshold_box.Add(self.threshold_ctrl, proportion=1, flag=wx.RIGHT, border=8)
        threshold_box.Add(threshold_help, flag=wx.ALIGN_CENTER_VERTICAL)
        param_sizer.Add(tolerance_box, flag=wx.EXPAND | wx.ALL, border=5)
        param_sizer.Add(threshold_box, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(param_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self._add_negate_checkbox(panel, vbox)

        button_box = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_box.AddButton(ok_button)
        button_box.AddButton(cancel_button)
        button_box.Realize()
        vbox.Add(button_box, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        panel.SetSizer(vbox)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, event):
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        if hasattr(self, 'screen_capture'):
            self.screen_capture.close()
        event.Skip()
    
    def on_select_region(self, event):
        self.Iconize(True)
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Click and drag to select a region. Press ESC to cancel")
        except: 
            pass
        wx.CallAfter(self._do_select_region)
    
    def on_pick_color(self, event):
        self.Iconize(True)
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Click to select a color, Esc to cancel")
        except: 
            pass
        
        picker_overlay = PixelPickerOverlay(self)
        result = picker_overlay.ShowModal()
        
        if result == wx.ID_OK and picker_overlay.get_result():
            self.end_color_picking(picker_overlay.get_result())
        else:
            self.end_color_picking(None)
        
        picker_overlay.cleanup()
        picker_overlay.Destroy()

    def end_color_picking(self, result):
        if hasattr(self, 'instruction_label') and self.instruction_label:
            self.instruction_label.Destroy()
            self.instruction_label = None
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        if result:
            _, _, pixel_color = result
            self.color_display.SetColor(pixel_color)
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass
    
    def _do_select_region(self):
        overlay = wx.Dialog(None, title="Region Selector", style=wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR | wx.NO_BORDER)
        self.screenshot = self.screen_capture.capture()
        screen_width, screen_height = self.screenshot.size
        overlay.SetSize(screen_width, screen_height)
        panel = wx.Panel(overlay)
        panel.SetSize(screen_width, screen_height)
        selection_start = None
        is_selecting = False
        buffer = wx.Bitmap(screen_width, screen_height)

        def draw_selection_rect(dc, rect_coords):
            dc.SetPen(wx.Pen(wx.BLUE, 2))
            dc.SetBrush(wx.Brush(wx.Colour(0, 0, 255, 64)))
            left, top, width, height = rect_coords
            dc.DrawRectangle(left, top, width, height)
            text = f"{width}x{height} px"
            dc.SetTextForeground(wx.WHITE)
            dc.DrawText(text, left + 5, top + 5)

        def on_paint(evt): 
            wx.BufferedPaintDC(panel, buffer)
        def on_mouse_down(evt):
            nonlocal selection_start, is_selecting
            selection_start = evt.GetPosition()
            is_selecting = True
        def on_mouse_move(evt):
            if is_selecting:
                dc = wx.BufferedDC(wx.ClientDC(panel), buffer)
                dc.Clear()
                x1, y1 = selection_start
                x2, y2 = panel.ScreenToClient(wx.GetMousePosition())
                draw_selection_rect(dc, (min(x1,x2), min(y1,y2), abs(x2-x1), abs(y2-y1)))
        def on_mouse_up(evt):
            nonlocal is_selecting
            if not is_selecting: 
                return
            is_selecting = False
            x1, y1 = selection_start
            x2, y2 = evt.GetPosition()
            overlay.Close()
            self.process_selection(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))
        def on_key_down(evt):
            if evt.GetKeyCode() == wx.WXK_ESCAPE:
                overlay.Close()
                self.on_selection_canceled()
        
        panel.Bind(wx.EVT_PAINT, on_paint)
        panel.Bind(wx.EVT_LEFT_DOWN, on_mouse_down)
        panel.Bind(wx.EVT_MOTION, on_mouse_move)
        panel.Bind(wx.EVT_LEFT_UP, on_mouse_up)
        panel.Bind(wx.EVT_KEY_DOWN, on_key_down)
        panel.SetFocus()

        dc = wx.BufferedDC(None, buffer)
        dc.Clear()
        info_text = "Click and drag to select a region. Press ESC to cancel."
        font = wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        dc.SetTextForeground(wx.WHITE)
        text_width, text_height = dc.GetTextExtent(info_text)
        dc.DrawText(info_text, (screen_width - text_width) // 2, 30)
        
        overlay.SetTransparent(150)
        overlay.ShowFullScreen(True)
        overlay.ShowModal()
        overlay.Destroy()
    
    def on_selection_canceled(self):
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass
    
    def process_selection(self, x1, y1, x2, y2):
        self.x1_ctrl.SetValue(x1)
        self.y1_ctrl.SetValue(y1)
        self.x2_ctrl.SetValue(x2)
        self.y2_ctrl.SetValue(y2)
        try:
            region = self.screenshot.crop((x1, y1, x2, y2))
            region_size = region.size
            self.preview_text.SetLabel(f"Region: {region_size[0]}x{region_size[1]} pixels")
        except Exception as e:
            self.preview_text.SetLabel(f"Error analyzing region: {str(e)}")
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass
    
    def get_condition(self):
        self._get_common_condition_data()
        self.condition_data.update({
            "x1": self.x1_ctrl.GetValue(), "y1": self.y1_ctrl.GetValue(),
            "x2": self.x2_ctrl.GetValue(), "y2": self.y2_ctrl.GetValue(),
            "color": list(self.color_display.GetColor()),
            "tolerance": self.tolerance_ctrl.GetValue(),
            "threshold": self.threshold_ctrl.GetValue()
        })
        return self.condition_data


class RegionImageConditionDialog(BaseConditionDialog):
    """Dialog for creating/editing a region image condition that matches a captured screenshot"""
    
    def __init__(self, parent, title="Add Region Image Condition", condition=None):
        super().__init__(parent, title, condition_type_default="pixel_region_image")
        
        self.condition_data.update(condition or {
            "x1": 0, "y1": 0, "x2": 100, "y2": 100,
            "confidence": 0.8, "image_data": None, "negate": False
        })
        
        self.selection_mode = False
        self.start_pos = None
        self.current_pos = None
        self.screenshot = None
        self.captured_region = None
        self.cursor_tracker = get_cursor_tracker()
        
        self.init_ui()
        self.SetSize((550, 700))
        self.Center()
        
    def init_ui(self):
        panel = wx.lib.scrolledpanel.ScrolledPanel(self)
        panel.SetupScrolling(scroll_x=False, scroll_y=True)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        coord_box = wx.StaticBox(panel, label="Region Coordinates")
        coord_sizer = wx.StaticBoxSizer(coord_box, wx.VERTICAL)
        tl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tl_label = wx.StaticText(panel, label="Top-left:")
        x1_label = wx.StaticText(panel, label="X1:")
        self.x1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["x1"]))
        y1_label = wx.StaticText(panel, label="Y1:")
        self.y1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["y1"]))
        tl_sizer.Add(tl_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        tl_sizer.Add(x1_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        tl_sizer.Add(self.x1_ctrl, proportion=1, flag=wx.RIGHT, border=10)
        tl_sizer.Add(y1_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        tl_sizer.Add(self.y1_ctrl, proportion=1)
        
        br_sizer = wx.BoxSizer(wx.HORIZONTAL)
        br_label = wx.StaticText(panel, label="Bottom-right:")
        x2_label = wx.StaticText(panel, label="X2:")
        self.x2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["x2"]))
        y2_label = wx.StaticText(panel, label="Y2:")
        self.y2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["y2"]))
        br_sizer.Add(br_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        br_sizer.Add(x2_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        br_sizer.Add(self.x2_ctrl, proportion=1, flag=wx.RIGHT, border=10)
        br_sizer.Add(y2_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        br_sizer.Add(self.y2_ctrl, proportion=1)
        
        self.region_btn = wx.Button(panel, label="Select Region on Screen")
        self.region_btn.Bind(wx.EVT_BUTTON, self.on_select_region)
        coord_sizer.Add(tl_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        coord_sizer.Add(br_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        coord_sizer.Add(self.region_btn, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(coord_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        preview_box = wx.StaticBox(panel, label="Region Preview")
        preview_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)
        self.preview_text = wx.StaticText(panel, label="Select a region to see preview")
        preview_sizer.Add(self.preview_text, flag=wx.EXPAND | wx.ALL, border=5)
        self.preview_bitmap = wx.StaticBitmap(panel, size=(320, 240))
        self.preview_bitmap.SetBackgroundColour(wx.Colour(200,200,200))
        preview_sizer.Add(self.preview_bitmap, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(preview_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        confidence_box = wx.StaticBox(panel, label="Match Confidence")
        confidence_sizer = wx.StaticBoxSizer(confidence_box, wx.VERTICAL)
        self.confidence_label_text = wx.StaticText(panel, label=f"Confidence Threshold: {self.condition_data['confidence']:.2f}")
        self.confidence_slider = wx.Slider(panel, value=int(self.condition_data["confidence"] * 100),
                                         minValue=0, maxValue=100,
                                         style=wx.SL_HORIZONTAL | wx.SL_LABELS)
        self.confidence_slider.Bind(wx.EVT_SLIDER, self.on_confidence_changed)
        confidence_sizer.Add(self.confidence_label_text, flag=wx.EXPAND | wx.ALL, border=5)
        confidence_sizer.Add(self.confidence_slider, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(confidence_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self._add_negate_checkbox(panel, vbox)

        help_text = wx.StaticText(panel, label="This condition checks if the captured region image appears on screen with the specified confidence level.")
        help_text.Wrap(500)
        vbox.Add(help_text, flag=wx.EXPAND | wx.ALL, border=10)
        
        button_box = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_box.AddButton(ok_button)
        button_box.AddButton(cancel_button)
        button_box.Realize()
        vbox.Add(button_box, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        panel.SetSizer(vbox)
        panel.Layout()
        panel.SetupScrolling()
        self.Bind(wx.EVT_CLOSE, self.on_close)
        if self.condition_data.get("image_data"): 
            self.load_preview_from_base64()
            
    def on_select_region(self, event):
        self.Iconize(True)
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Click and drag to select a region. Press ESC to cancel")
        except: 
            pass
        wx.CallAfter(self._do_select_region)
        
    def _do_select_region(self):
        overlay = wx.Dialog(None, title="Region Selector", style=wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR | wx.NO_BORDER)
        self.screenshot = self.screen_capture.capture()
        screen_width, screen_height = self.screenshot.size
        overlay.SetSize(screen_width, screen_height)
        panel = wx.Panel(overlay)
        panel.SetSize(screen_width, screen_height)
        selection_start = None
        is_selecting = False
        buffer = wx.Bitmap(screen_width, screen_height)

        def draw_selection_rect(dc, rect_coords):
            dc.SetPen(wx.Pen(wx.BLUE, 2))
            dc.SetBrush(wx.Brush(wx.Colour(0, 0, 255, 64)))
            left, top, width, height = rect_coords
            dc.DrawRectangle(left, top, width, height)
            text = f"{width}x{height} px"
            dc.SetTextForeground(wx.WHITE)
            dc.DrawText(text, left + 5, top + 5)

        def on_paint(evt): 
            wx.BufferedPaintDC(panel, buffer)
        def on_mouse_down(evt):
            nonlocal selection_start, is_selecting
            selection_start = evt.GetPosition()
            is_selecting = True
        def on_mouse_move(evt):
            if is_selecting:
                dc = wx.BufferedDC(wx.ClientDC(panel), buffer)
                dc.Clear()
                x1, y1 = selection_start
                x2, y2 = panel.ScreenToClient(wx.GetMousePosition())
                draw_selection_rect(dc, (min(x1,x2), min(y1,y2), abs(x2-x1), abs(y2-y1)))
        def on_mouse_up(evt):
            nonlocal is_selecting
            if not is_selecting: 
                return
            is_selecting = False
            x1, y1 = selection_start
            x2, y2 = evt.GetPosition()
            overlay.Close()
            self.process_selection(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))
        def on_key_down(evt):
            if evt.GetKeyCode() == wx.WXK_ESCAPE:
                overlay.Close()
                self.on_selection_canceled()
        
        panel.Bind(wx.EVT_PAINT, on_paint)
        panel.Bind(wx.EVT_LEFT_DOWN, on_mouse_down)
        panel.Bind(wx.EVT_MOTION, on_mouse_move)
        panel.Bind(wx.EVT_LEFT_UP, on_mouse_up)
        panel.Bind(wx.EVT_KEY_DOWN, on_key_down)
        panel.SetFocus()

        dc = wx.BufferedDC(None, buffer)
        dc.Clear()
        info_text = "Click and drag to select a region. Press ESC to cancel."
        font = wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        dc.SetTextForeground(wx.WHITE)
        text_width, text_height = dc.GetTextExtent(info_text)
        dc.DrawText(info_text, (screen_width - text_width) // 2, 30)
        
        overlay.SetTransparent(150)
        overlay.ShowFullScreen(True)
        overlay.ShowModal()
        overlay.Destroy()
        
    def on_selection_canceled(self):
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass
    
    def process_selection(self, x1, y1, x2, y2):
        self.x1_ctrl.SetValue(x1)
        self.y1_ctrl.SetValue(y1)
        self.x2_ctrl.SetValue(x2)
        self.y2_ctrl.SetValue(y2)
        try:
            region = self.screenshot.crop((x1, y1, x2, y2))
            self.captured_region = region
            
            max_preview_w, max_preview_h = 320, 240
            img_w, img_h = region.size
            
            if img_w > max_preview_w or img_h > max_preview_h:
                scale = min(max_preview_w / img_w, max_preview_h / img_h)
                preview_w, preview_h = int(img_w * scale), int(img_h * scale)
                preview_img = region.resize((preview_w, preview_h), Image.Resampling.LANCZOS)
            else:
                preview_img = region

            wximage = wx.Image(preview_img.width, preview_img.height)
            wximage.SetData(preview_img.convert("RGB").tobytes())
            bitmap = wx.Bitmap(wximage)
            
            self.preview_bitmap.SetBitmap(bitmap)
            self.preview_text.SetLabel(f"Image: {img_w}x{img_h} pixels (Preview: {preview_img.width}x{preview_img.height})")
            self.GetSizer().Layout()
            
        except Exception as e:
            self.preview_text.SetLabel(f"Error capturing region: {str(e)}")
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass
            
    def on_confidence_changed(self, event):
        confidence = self.confidence_slider.GetValue() / 100.0
        self.confidence_label_text.SetLabel(f"Confidence Threshold: {confidence:.2f}")
    
    def load_preview_from_base64(self):
        try:
            image_data = base64.b64decode(self.condition_data["image_data"])
            image = Image.open(io.BytesIO(image_data))
            self.captured_region = image

            max_preview_w, max_preview_h = 320, 240
            img_w, img_h = image.size
            if img_w > max_preview_w or img_h > max_preview_h:
                scale = min(max_preview_w / img_w, max_preview_h / img_h)
                preview_w, preview_h = int(img_w * scale), int(img_h * scale)
                preview_img = image.resize((preview_w, preview_h), Image.Resampling.LANCZOS)
            else:
                preview_img = image
            
            wximage = wx.Image(preview_img.width, preview_img.height)
            wximage.SetData(preview_img.convert("RGB").tobytes())
            bitmap = wx.Bitmap(wximage)
            
            self.preview_bitmap.SetBitmap(bitmap)
            self.preview_text.SetLabel(f"Image: {img_w}x{img_h} pixels (Preview: {preview_img.width}x{preview_img.height})")
            self.GetSizer().Layout()
        except Exception as e:
            self.preview_text.SetLabel(f"Error loading image: {str(e)}")
    
    def on_close(self, event):
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        if hasattr(self, 'screen_capture'):
            self.screen_capture.close()
        event.Skip()
        
    def get_condition(self):
        self._get_common_condition_data()
        self.condition_data.update({
            "x1": self.x1_ctrl.GetValue(), "y1": self.y1_ctrl.GetValue(),
            "x2": self.x2_ctrl.GetValue(), "y2": self.y2_ctrl.GetValue(),
            "confidence": self.confidence_slider.GetValue() / 100.0,
        })
        if self.captured_region:
            buffer = io.BytesIO()
            self.captured_region.save(buffer, format="PNG")
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            self.condition_data["image_data"] = image_base64
        return self.condition_data


class OCRTextMatchConditionDialog(BaseConditionDialog):
    """Dialog for creating/editing an OCR text match condition."""
    def __init__(self, parent, title="Add OCR Text Match Condition", condition=None):
        super().__init__(parent, title, condition_type_default="ocr_text_match")
        self.condition_data.update(condition or {
            "x1": 0, "y1": 0, "x2": 100, "y2": 50,
            "expected_text": "", "match_mode": "contains",
            "case_sensitive": False, "negate": False
        })
        self.screenshot = None
        self.cursor_tracker = get_cursor_tracker()
        self.init_ui()
        self.SetSize((500, 500))
        self.Center()

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Region Coordinates
        coord_box = wx.StaticBox(panel, label="OCR Region Coordinates")
        coord_sizer = wx.StaticBoxSizer(coord_box, wx.VERTICAL)
        
        tl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        x1_label = wx.StaticText(panel, label="X1:")
        self.x1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["x1"]))
        y1_label = wx.StaticText(panel, label="Y1:")
        self.y1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["y1"]))
        tl_sizer.Add(x1_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        tl_sizer.Add(self.x1_ctrl, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        tl_sizer.Add(y1_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        tl_sizer.Add(self.y1_ctrl, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        coord_sizer.Add(tl_sizer, 0, wx.EXPAND | wx.ALL, 5)

        br_sizer = wx.BoxSizer(wx.HORIZONTAL)
        x2_label = wx.StaticText(panel, label="X2:")
        self.x2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["x2"]))
        y2_label = wx.StaticText(panel, label="Y2:")
        self.y2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.condition_data["y2"]))
        br_sizer.Add(x2_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        br_sizer.Add(self.x2_ctrl, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        br_sizer.Add(y2_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        br_sizer.Add(self.y2_ctrl, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        coord_sizer.Add(br_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.region_btn = wx.Button(panel, label="Select Region on Screen")
        self.region_btn.Bind(wx.EVT_BUTTON, self.on_select_region)
        coord_sizer.Add(self.region_btn, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(coord_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # OCR Parameters
        ocr_params_box = wx.StaticBox(panel, label="OCR Parameters")
        ocr_params_sizer = wx.StaticBoxSizer(ocr_params_box, wx.VERTICAL)

        text_sizer = wx.BoxSizer(wx.HORIZONTAL)
        text_label = wx.StaticText(panel, label="Expected Text:")
        self.expected_text_ctrl = wx.TextCtrl(panel, value=self.condition_data["expected_text"])
        text_sizer.Add(text_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        text_sizer.Add(self.expected_text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        ocr_params_sizer.Add(text_sizer, 0, wx.EXPAND | wx.ALL, 5)

        mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mode_label = wx.StaticText(panel, label="Match Mode:")
        self.match_mode_choice = wx.Choice(panel, choices=["contains", "exact", "regex"])
        self.match_mode_choice.SetStringSelection(self.condition_data["match_mode"])
        mode_sizer.Add(mode_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        mode_sizer.Add(self.match_mode_choice, 1, wx.EXPAND | wx.ALL, 5)
        ocr_params_sizer.Add(mode_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.case_sensitive_cb = wx.CheckBox(panel, label="Case Sensitive")
        self.case_sensitive_cb.SetValue(self.condition_data["case_sensitive"])
        ocr_params_sizer.Add(self.case_sensitive_cb, 0, wx.ALL, 5)
        vbox.Add(ocr_params_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self._add_negate_checkbox(panel, vbox)

        # Buttons
        button_box = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_box.AddButton(ok_button)
        button_box.AddButton(cancel_button)
        button_box.Realize()
        vbox.Add(button_box, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(vbox)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_select_region(self, event):
        self.Iconize(True)
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Click and drag to select a region. Press ESC to cancel")
        except: 
            pass
        wx.CallAfter(self._do_select_region)

    def _do_select_region(self):
        overlay = wx.Dialog(None, title="OCR Region Selector", style=wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR | wx.NO_BORDER)
        self.screenshot = self.screen_capture.capture()
        screen_width, screen_height = self.screenshot.size
        overlay.SetSize(screen_width, screen_height)
        panel = wx.Panel(overlay)
        panel.SetSize(screen_width, screen_height)
        selection_start = None
        is_selecting = False
        buffer = wx.Bitmap(screen_width, screen_height)

        def draw_selection_rect(dc, rect_coords):
            dc.SetPen(wx.Pen(wx.GREEN, 2))
            dc.SetBrush(wx.Brush(wx.Colour(0, 255, 0, 64)))
            left, top, width, height = rect_coords
            dc.DrawRectangle(left, top, width, height)
            text = f"{width}x{height} px"
            dc.SetTextForeground(wx.WHITE)
            dc.DrawText(text, left + 5, top + 5)

        def on_paint(evt): 
            wx.BufferedPaintDC(panel, buffer)
        def on_mouse_down(evt):
            nonlocal selection_start, is_selecting
            selection_start = evt.GetPosition()
            is_selecting = True
        def on_mouse_move(evt):
            if is_selecting:
                dc = wx.BufferedDC(wx.ClientDC(panel), buffer)
                dc.Clear()
                x1, y1 = selection_start
                x2, y2 = panel.ScreenToClient(wx.GetMousePosition())
                draw_selection_rect(dc, (min(x1,x2), min(y1,y2), abs(x2-x1), abs(y2-y1)))
        def on_mouse_up(evt):
            nonlocal is_selecting
            if not is_selecting: 
                return
            is_selecting = False
            x1, y1 = selection_start
            x2, y2 = evt.GetPosition()
            overlay.Close()
            self.process_selection(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))
        def on_key_down(evt):
            if evt.GetKeyCode() == wx.WXK_ESCAPE:
                overlay.Close()
                self.on_selection_canceled()
        
        panel.Bind(wx.EVT_PAINT, on_paint)
        panel.Bind(wx.EVT_LEFT_DOWN, on_mouse_down)
        panel.Bind(wx.EVT_MOTION, on_mouse_move)
        panel.Bind(wx.EVT_LEFT_UP, on_mouse_up)
        panel.Bind(wx.EVT_KEY_DOWN, on_key_down)
        panel.SetFocus()

        dc = wx.BufferedDC(None, buffer)
        dc.Clear()
        info_text = "Click and drag to select OCR region. Press ESC to cancel."
        font = wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        dc.SetTextForeground(wx.WHITE)
        text_width, text_height = dc.GetTextExtent(info_text)
        dc.DrawText(info_text, (screen_width - text_width) // 2, 30)
        
        overlay.SetTransparent(150)
        overlay.ShowFullScreen(True)
        overlay.ShowModal()
        overlay.Destroy()

    def on_selection_canceled(self):
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass

    def process_selection(self, x1, y1, x2, y2):
        self.x1_ctrl.SetValue(x1)
        self.y1_ctrl.SetValue(y1)
        self.x2_ctrl.SetValue(x2)
        self.y2_ctrl.SetValue(y2)
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass

    def on_close(self, event):
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        if hasattr(self, 'screen_capture'):
            self.screen_capture.close()
        event.Skip()

    def get_condition(self):
        self._get_common_condition_data()
        self.condition_data.update({
            "x1": self.x1_ctrl.GetValue(), "y1": self.y1_ctrl.GetValue(),
            "x2": self.x2_ctrl.GetValue(), "y2": self.y2_ctrl.GetValue(),
            "expected_text": self.expected_text_ctrl.GetValue(),
            "match_mode": self.match_mode_choice.GetStringSelection(),
            "case_sensitive": self.case_sensitive_cb.GetValue()
        })
        return self.condition_data


class ORConditionDialog(BaseConditionDialog):
    """Dialog for creating/editing an OR condition."""
    def __init__(self, parent, title="Add OR Condition", condition=None):
        super().__init__(parent, title, condition_type_default="or")
        self.condition_data.update(condition or {
            "conditions": [None, None], "negate": False
        })
        self.profile_editor_frame = wx.GetApp().GetTopWindow()
        self.init_ui()
        self.SetSize((500, 350))
        self.Center()

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        explanation = wx.StaticText(panel, label="An OR condition is true if Condition 1 OR Condition 2 is true.")
        explanation.Wrap(480)
        vbox.Add(explanation, 0, wx.ALL | wx.EXPAND, 10)

        # Condition 1
        cond1_box = wx.StaticBox(panel, label="Condition 1")
        cond1_sizer = wx.StaticBoxSizer(cond1_box, wx.VERTICAL)
        self.cond1_text = wx.StaticText(panel, label=self._get_condition_summary(0))
        self.cond1_btn = wx.Button(panel, label="Define Condition 1")
        self.cond1_btn.Bind(wx.EVT_BUTTON, lambda evt, idx=0: self.on_define_sub_condition(evt, idx))
        cond1_sizer.Add(self.cond1_text, 0, wx.ALL | wx.EXPAND, 5)
        cond1_sizer.Add(self.cond1_btn, 0, wx.ALL | wx.EXPAND, 5)
        vbox.Add(cond1_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Condition 2
        cond2_box = wx.StaticBox(panel, label="Condition 2")
        cond2_sizer = wx.StaticBoxSizer(cond2_box, wx.VERTICAL)
        self.cond2_text = wx.StaticText(panel, label=self._get_condition_summary(1))
        self.cond2_btn = wx.Button(panel, label="Define Condition 2")
        self.cond2_btn.Bind(wx.EVT_BUTTON, lambda evt, idx=1: self.on_define_sub_condition(evt, idx))
        cond2_sizer.Add(self.cond2_text, 0, wx.ALL | wx.EXPAND, 5)
        cond2_sizer.Add(self.cond2_btn, 0, wx.ALL | wx.EXPAND, 5)
        vbox.Add(cond2_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self._add_negate_checkbox(panel, vbox)

        # Buttons
        button_box = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_box.AddButton(ok_button)
        button_box.AddButton(cancel_button)
        button_box.Realize()
        vbox.Add(button_box, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(vbox)

    def _get_condition_summary(self, index):
        cond = self.condition_data["conditions"][index]
        if not cond:
            return "Not defined"
        summary = f"Type: {cond.get('type', 'N/A')}"
        if cond.get('negate'):
            summary += " (NOT)"
        if cond.get('type') == 'pixel_color':
            summary += f" @ ({cond.get('x')},{cond.get('y')})"
        return summary

    def on_define_sub_condition(self, event, index):
        menu = wx.Menu()
        item_pixel = menu.Append(wx.ID_ANY, "Pixel Color Condition")
        item_region_color = menu.Append(wx.ID_ANY, "Region Color Condition")
        item_region_image = menu.Append(wx.ID_ANY, "Region Image Condition")
        item_ocr_text = menu.Append(wx.ID_ANY, "OCR Text Match Condition")
        
        self.Bind(wx.EVT_MENU, lambda evt, i=index: self.open_sub_condition_dialog(evt, i, "pixel_color"), item_pixel)
        self.Bind(wx.EVT_MENU, lambda evt, i=index: self.open_sub_condition_dialog(evt, i, "pixel_region_color"), item_region_color)
        self.Bind(wx.EVT_MENU, lambda evt, i=index: self.open_sub_condition_dialog(evt, i, "pixel_region_image"), item_region_image)
        self.Bind(wx.EVT_MENU, lambda evt, i=index: self.open_sub_condition_dialog(evt, i, "ocr_text_match"), item_ocr_text)
        
        self.PopupMenu(menu)
        menu.Destroy()

    def open_sub_condition_dialog(self, event, index, condition_type):
        existing_cond = self.condition_data["conditions"][index] if self.condition_data["conditions"][index] and self.condition_data["conditions"][index].get("type") == condition_type else None
        
        dialog = None
        if condition_type == "pixel_color":
            dialog = PixelColorConditionDialog(self.profile_editor_frame, "Define Sub-Condition", condition=existing_cond)
        elif condition_type == "pixel_region_color":
            dialog = RegionColorConditionDialog(self.profile_editor_frame, "Define Sub-Condition", condition=existing_cond)
        elif condition_type == "pixel_region_image":
            dialog = RegionImageConditionDialog(self.profile_editor_frame, "Define Sub-Condition", condition=existing_cond)
        elif condition_type == "ocr_text_match":
            dialog = OCRTextMatchConditionDialog(self.profile_editor_frame, "Define Sub-Condition", condition=existing_cond)

        if dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.condition_data["conditions"][index] = dialog.get_condition()
                if index == 0:
                    self.cond1_text.SetLabel(self._get_condition_summary(0))
                else:
                    self.cond2_text.SetLabel(self._get_condition_summary(1))
                self.Layout()
            dialog.Destroy()

    def on_ok(self, event):
        if not self.condition_data["conditions"][0] or not self.condition_data["conditions"][1]:
            wx.MessageBox("Both sub-conditions must be defined for an OR condition.", "Error", wx.ICON_ERROR)
            return
        self.EndModal(wx.ID_OK)

    def get_condition(self):
        self._get_common_condition_data()
        return self.condition_data


# --- OCR Region Dialog ---
class OCRRegionDialog(wx.Dialog):
    """Dialog for creating/editing an OCR region with conditions support"""
    
    def __init__(self, parent, title="Add OCR Region", ocr_region=None):
        super().__init__(parent, title=title, size=(500, 600))
        
        self.ocr_region = ocr_region or {
            "x1": 0, "y1": 0, "x2": 100, "y2": 100,
            "tag": "ocr1", "conditions": []
        }
        
        self.screenshot = None
        self.cursor_tracker = get_cursor_tracker()
        self.profile_editor_frame = wx.GetApp().GetTopWindow()
        self.screen_capture = ScreenCapture()
        
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        coord_box = wx.StaticBox(panel, label="OCR Region Coordinates")
        coord_sizer = wx.StaticBoxSizer(coord_box, wx.VERTICAL)
        tl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        x1_label = wx.StaticText(panel, label="X1:")
        self.x1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.ocr_region["x1"]))
        y1_label = wx.StaticText(panel, label="Y1:")
        self.y1_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.ocr_region["y1"]))
        tl_sizer.Add(x1_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        tl_sizer.Add(self.x1_ctrl, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        tl_sizer.Add(y1_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        tl_sizer.Add(self.y1_ctrl, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        coord_sizer.Add(tl_sizer, 0, wx.EXPAND|wx.ALL, 5)

        br_sizer = wx.BoxSizer(wx.HORIZONTAL)
        x2_label = wx.StaticText(panel, label="X2:")
        self.x2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.ocr_region["x2"]))
        y2_label = wx.StaticText(panel, label="Y2:")
        self.y2_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.ocr_region["y2"]))
        br_sizer.Add(x2_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        br_sizer.Add(self.x2_ctrl, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        br_sizer.Add(y2_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        br_sizer.Add(self.y2_ctrl, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        coord_sizer.Add(br_sizer, 0, wx.EXPAND|wx.ALL, 5)
        
        tag_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tag_label = wx.StaticText(panel, label="OCR Tag:")
        self.tag_ctrl = wx.TextCtrl(panel, value=str(self.ocr_region["tag"]))
        tag_help = wx.StaticText(panel, label="(used as {tag} in announcement)")
        tag_sizer.Add(tag_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        tag_sizer.Add(self.tag_ctrl, proportion=1, flag=wx.RIGHT, border=8)
        tag_sizer.Add(tag_help, flag=wx.ALIGN_CENTER_VERTICAL)
        coord_sizer.Add(tag_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        
        self.region_btn = wx.Button(panel, label="Select Region on Screen")
        self.region_btn.Bind(wx.EVT_BUTTON, self.on_select_region)
        coord_sizer.Add(self.region_btn, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(coord_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        preview_box = wx.StaticBox(panel, label="Preview")
        preview_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)
        self.preview_text = wx.StaticText(panel, label="Select a region to see dimensions")
        preview_sizer.Add(self.preview_text, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(preview_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        conditions_box = wx.StaticBox(panel, label="OCR Activation Conditions")
        conditions_sizer = wx.StaticBoxSizer(conditions_box, wx.VERTICAL)
        self.conditions_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 120))
        self.conditions_list.InsertColumn(0, "Type", width=120)
        self.conditions_list.InsertColumn(1, "Details", width=250)
        self.update_conditions_list()
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_pixel_btn = wx.Button(panel, label="Pixel Color")
        add_pixel_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_condition("pixel_color"))
        add_region_color_btn = wx.Button(panel, label="Region Color")
        add_region_color_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_condition("pixel_region_color"))
        add_region_image_btn = wx.Button(panel, label="Region Image")
        add_region_image_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_condition("pixel_region_image"))
        add_or_btn = wx.Button(panel, label="OR")
        add_or_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_condition("or"))
        add_ocr_match_btn = wx.Button(panel, label="OCR Match")
        add_ocr_match_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_condition("ocr_text_match"))

        btn_sizer.Add(add_pixel_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(add_region_color_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(add_region_image_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(add_or_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(add_ocr_match_btn, 0, wx.RIGHT, 5)

        edit_condition_btn = wx.Button(panel, label="Edit")
        edit_condition_btn.Bind(wx.EVT_BUTTON, self.on_edit_condition)
        delete_condition_btn = wx.Button(panel, label="Delete")
        delete_condition_btn.Bind(wx.EVT_BUTTON, self.on_delete_condition)
        btn_sizer.Add(edit_condition_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(delete_condition_btn, 0, wx.RIGHT, 5)
        
        conditions_sizer.Add(self.conditions_list, 1, wx.EXPAND | wx.ALL, 5)
        conditions_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        help_text = wx.StaticText(panel, label="OCR will only be performed when all conditions are met.")
        conditions_sizer.Add(help_text, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(conditions_sizer, 1, wx.EXPAND | wx.ALL, 10)
        
        button_box = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_box.AddButton(ok_button)
        button_box.AddButton(cancel_button)
        button_box.Realize()
        vbox.Add(button_box, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        panel.SetSizer(vbox)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
    def update_conditions_list(self):
        self.conditions_list.DeleteAllItems()
        if "conditions" not in self.ocr_region or not self.ocr_region["conditions"]:
            return
        for i, condition in enumerate(self.ocr_region["conditions"]):
            condition_type = condition.get("type", "unknown")
            details = f"Negated: {condition.get('negate', False)}"
            if condition_type == "pixel_color":
                details = f"({condition['x']},{condition['y']}) RGB{condition['color']} Tol:{condition['tolerance']}"
            elif condition_type == "pixel_region_color":
                details = f"Region({condition['x1']},{condition['y1']}-{condition['x2']},{condition['y2']}) RGB{condition['color']} Tol:{condition['tolerance']} Thresh:{condition['threshold']}"
            elif condition_type == "pixel_region_image":
                details = f"Region({condition['x1']},{condition['y1']}-{condition['x2']},{condition['y2']}) Conf:{condition['confidence']:.2f}"
            elif condition_type == "ocr_text_match":
                details = f"Region({condition['x1']},{condition['y1']}-{condition['x2']},{condition['y2']}) Text: '{condition.get('expected_text','')[:20]}...'"
            elif condition_type == "or":
                details = f"OR (Sub1: {condition['conditions'][0].get('type', 'N/A')}, Sub2: {condition['conditions'][1].get('type', 'N/A')})"
            
            if condition.get("negate"): 
                details = "NOT " + details
            
            idx = self.conditions_list.InsertItem(i, condition_type)
            self.conditions_list.SetItem(idx, 1, details)
    
    def on_add_condition(self, condition_type_to_add):
        dialog = None
        if condition_type_to_add == "pixel_color":
            dialog = PixelColorConditionDialog(self.profile_editor_frame, "Add Pixel Color Sub-Condition")
        elif condition_type_to_add == "pixel_region_color":
            dialog = RegionColorConditionDialog(self.profile_editor_frame, "Add Region Color Sub-Condition")
        elif condition_type_to_add == "pixel_region_image":
            dialog = RegionImageConditionDialog(self.profile_editor_frame, "Add Region Image Sub-Condition")
        elif condition_type_to_add == "ocr_text_match":
            dialog = OCRTextMatchConditionDialog(self.profile_editor_frame, "Add OCR Text Match Sub-Condition")
        elif condition_type_to_add == "or":
            dialog = ORConditionDialog(self.profile_editor_frame, "Add OR Sub-Condition")

        if dialog:
            if dialog.ShowModal() == wx.ID_OK:
                condition = dialog.get_condition()
                if "conditions" not in self.ocr_region: 
                    self.ocr_region["conditions"] = []
                self.ocr_region["conditions"].append(condition)
                self.update_conditions_list()
            dialog.Destroy()

    def on_edit_condition(self, event):
        selected = self.conditions_list.GetFirstSelected()
        if selected == -1: 
            return
        
        condition_to_edit = self.ocr_region["conditions"][selected]
        condition_type = condition_to_edit.get("type")
        dialog = None

        if condition_type == "pixel_color":
            dialog = PixelColorConditionDialog(self.profile_editor_frame, "Edit Pixel Color Sub-Condition", condition=condition_to_edit)
        elif condition_type == "pixel_region_color":
            dialog = RegionColorConditionDialog(self.profile_editor_frame, "Edit Region Color Sub-Condition", condition=condition_to_edit)
        elif condition_type == "pixel_region_image":
            dialog = RegionImageConditionDialog(self.profile_editor_frame, "Edit Region Image Sub-Condition", condition=condition_to_edit)
        elif condition_type == "ocr_text_match":
            dialog = OCRTextMatchConditionDialog(self.profile_editor_frame, "Edit OCR Text Match Sub-Condition", condition=condition_to_edit)
        elif condition_type == "or":
            dialog = ORConditionDialog(self.profile_editor_frame, "Edit OR Sub-Condition", condition=condition_to_edit)
        
        if dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.ocr_region["conditions"][selected] = dialog.get_condition()
                self.update_conditions_list()
            dialog.Destroy()

    def on_delete_condition(self, event):
        selected = self.conditions_list.GetFirstSelected()
        if selected == -1: 
            return
        if wx.MessageBox("Are you sure you want to delete this condition?", "Confirm", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        del self.ocr_region["conditions"][selected]
        self.update_conditions_list()
    
    def on_close(self, event):
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        if hasattr(self, 'screen_capture'):
            self.screen_capture.close()
        event.Skip()
    
    def on_select_region(self, event):
        self.Iconize(True)
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Click and drag to select a region. Press ESC to cancel")
        except: 
            pass
        wx.CallAfter(self._do_select_region)
    
    def _do_select_region(self):
        overlay = wx.Dialog(None, title="OCR Region Selector", style=wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR | wx.NO_BORDER)
        self.screenshot = self.screen_capture.capture()
        screen_width, screen_height = self.screenshot.size
        overlay.SetSize(screen_width, screen_height)
        panel = wx.Panel(overlay)
        panel.SetSize(screen_width, screen_height)
        selection_start = None
        is_selecting = False
        buffer = wx.Bitmap(screen_width, screen_height)

        def draw_selection_rect(dc, rect_coords):
            dc.SetPen(wx.Pen(wx.GREEN, 2))
            dc.SetBrush(wx.Brush(wx.Colour(0, 255, 0, 64)))
            left, top, width, height = rect_coords
            dc.DrawRectangle(left, top, width, height)
            text = f"{width}x{height} px"
            dc.SetTextForeground(wx.WHITE)
            dc.DrawText(text, left + 5, top + 5)

        def on_paint(evt): 
            wx.BufferedPaintDC(panel, buffer)
        def on_mouse_down(evt):
            nonlocal selection_start, is_selecting
            selection_start = evt.GetPosition()
            is_selecting = True
        def on_mouse_move(evt):
            if is_selecting:
                dc = wx.BufferedDC(wx.ClientDC(panel), buffer)
                dc.Clear()
                x1, y1 = selection_start
                x2, y2 = panel.ScreenToClient(wx.GetMousePosition())
                draw_selection_rect(dc, (min(x1,x2), min(y1,y2), abs(x2-x1), abs(y2-y1)))
        def on_mouse_up(evt):
            nonlocal is_selecting
            if not is_selecting: 
                return
            is_selecting = False
            x1, y1 = selection_start
            x2, y2 = evt.GetPosition()
            overlay.Close()
            self.process_selection(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))
        def on_key_down(evt):
            if evt.GetKeyCode() == wx.WXK_ESCAPE:
                overlay.Close()
                self.on_selection_canceled()
        
        panel.Bind(wx.EVT_PAINT, on_paint)
        panel.Bind(wx.EVT_LEFT_DOWN, on_mouse_down)
        panel.Bind(wx.EVT_MOTION, on_mouse_move)
        panel.Bind(wx.EVT_LEFT_UP, on_mouse_up)
        panel.Bind(wx.EVT_KEY_DOWN, on_key_down)
        panel.SetFocus()

        dc = wx.BufferedDC(None, buffer)
        dc.Clear()
        info_text = "Click and drag to select an OCR region. Press ESC to cancel."
        font = wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        dc.SetTextForeground(wx.WHITE)
        text_width, text_height = dc.GetTextExtent(info_text)
        dc.DrawText(info_text, (screen_width - text_width) // 2, 30)
        
        overlay.SetTransparent(150)
        overlay.ShowFullScreen(True)
        overlay.ShowModal()
        overlay.Destroy()
    
    def on_selection_canceled(self):
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass
    
    def process_selection(self, x1, y1, x2, y2):
        self.x1_ctrl.SetValue(x1)
        self.y1_ctrl.SetValue(y1)
        self.x2_ctrl.SetValue(x2)
        self.y2_ctrl.SetValue(y2)
        try:
            region = self.screenshot.crop((x1, y1, x2, y2))
            region_size = region.size
            self.preview_text.SetLabel(f"OCR Region: {region_size[0]}x{region_size[1]} pixels")
        except Exception as e:
            self.preview_text.SetLabel(f"Error analyzing region: {str(e)}")
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass
    
    def get_ocr_region(self):
        self.ocr_region.update({
            "x1": self.x1_ctrl.GetValue(), "y1": self.y1_ctrl.GetValue(),
            "x2": self.x2_ctrl.GetValue(), "y2": self.y2_ctrl.GetValue(),
            "tag": self.tag_ctrl.GetValue() or "ocr1"
        })
        return self.ocr_region


# --- UI Element Dialog ---
class UIElementDialog(wx.Dialog):
    """Dialog for creating/editing a UI element"""
    
    def __init__(self, parent, title="Add UI Element", element=None):
        super().__init__(parent, title=title, size=(650, 900))
        
        self.element = element or [
            (0, 0), "New Element", "button", False, None, "default",
            [], None, 0, [], 0
        ]
        
        while len(self.element) < 11:
            if len(self.element) == 6: 
                self.element.append([])
            elif len(self.element) == 7: 
                self.element.append(None)
            elif len(self.element) == 8: 
                self.element.append(0)
            elif len(self.element) == 9: 
                self.element.append([])
            elif len(self.element) == 10: 
                self.element.append(0)
            else: 
                self.element.append(None)
        
        self.screenshot = None
        self.cursor_tracker = get_cursor_tracker()
        self.picker_thread = None
        self.profile_editor_frame = wx.GetApp().GetTopWindow()
        self.screen_capture = ScreenCapture()
        
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.lib.scrolledpanel.ScrolledPanel(self)
        panel.SetupScrolling(scroll_x=False, scroll_y=True)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Position section
        pos_box = wx.StaticBox(panel, label="Element Position")
        pos_sizer = wx.StaticBoxSizer(pos_box, wx.VERTICAL)
        coord_box = wx.BoxSizer(wx.HORIZONTAL)
        x_label = wx.StaticText(panel, label="X:")
        self.x_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.element[0][0]))
        y_label = wx.StaticText(panel, label="Y:")
        self.y_ctrl = wx.SpinCtrl(panel, min=0, max=9999, value=str(self.element[0][1]))
        coord_box.Add(x_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        coord_box.Add(self.x_ctrl, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        coord_box.Add(y_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        coord_box.Add(self.y_ctrl, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        
        color_box_disp = wx.BoxSizer(wx.HORIZONTAL)
        color_label = wx.StaticText(panel, label="Color at Position:")
        self.color_display = ColorDisplay(panel, initial_color=(200, 200, 200))
        color_box_disp.Add(color_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        color_box_disp.Add(self.color_display, 1, wx.EXPAND|wx.ALL, 5)
        
        instructions = wx.StaticText(panel, label="Move cursor to desired element, then click to select")
        self.pick_btn = wx.Button(panel, label="Pick Element Location on Screen")
        self.pick_btn.Bind(wx.EVT_BUTTON, self.on_pick_location)
        pos_sizer.Add(coord_box, 0, wx.EXPAND | wx.ALL, 5)
        pos_sizer.Add(color_box_disp, 0, wx.EXPAND | wx.ALL, 5)
        pos_sizer.Add(instructions, 0, wx.ALL, 5)
        pos_sizer.Add(self.pick_btn, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(pos_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Element properties section
        props_box = wx.StaticBox(panel, label="Element Properties")
        props_sizer = wx.StaticBoxSizer(props_box, wx.VERTICAL)
        
        name_box = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(panel, label="Name:")
        self.name_ctrl = wx.TextCtrl(panel, value=str(self.element[1]))
        name_box.Add(name_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        name_box.Add(self.name_ctrl, 1, wx.EXPAND|wx.ALL, 5)
        props_sizer.Add(name_box, 0, wx.EXPAND|wx.ALL, 5)

        type_box = wx.BoxSizer(wx.HORIZONTAL)
        type_label = wx.StaticText(panel, label="Type:")
        element_types = ["button", "dropdown", "menu", "tab", "toggle", "link"]
        self.type_ctrl = wx.Choice(panel, choices=element_types)
        if self.element[2] in element_types: 
            self.type_ctrl.SetStringSelection(self.element[2])
        else: 
            self.type_ctrl.SetSelection(0)
        type_box.Add(type_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        type_box.Add(self.type_ctrl, 1, wx.EXPAND|wx.ALL, 5)
        props_sizer.Add(type_box, 0, wx.EXPAND|wx.ALL, 5)

        self.speaks_ctrl = wx.CheckBox(panel, label="Speaks on Select")
        self.speaks_ctrl.SetValue(self.element[3])
        props_sizer.Add(self.speaks_ctrl, 0, wx.EXPAND|wx.ALL, 5)

        submenu_box = wx.BoxSizer(wx.HORIZONTAL)
        submenu_label = wx.StaticText(panel, label="Submenu ID:")
        self.submenu_ctrl = wx.TextCtrl(panel, value=str(self.element[4] or ""))
        submenu_box.Add(submenu_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        submenu_box.Add(self.submenu_ctrl, 1, wx.EXPAND|wx.ALL, 5)
        props_sizer.Add(submenu_box, 0, wx.EXPAND|wx.ALL, 5)

        group_box = wx.BoxSizer(wx.HORIZONTAL)
        group_label = wx.StaticText(panel, label="Group:")
        standard_groups = ["default", "tab-bar", "main-content", "side-panel", "footer"]
        self.group_ctrl = wx.ComboBox(panel, choices=standard_groups, value=str(self.element[5]))
        group_box.Add(group_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        group_box.Add(self.group_ctrl, 1, wx.EXPAND|wx.ALL, 5)
        props_sizer.Add(group_box, 0, wx.EXPAND|wx.ALL, 5)

        index_box = wx.BoxSizer(wx.HORIZONTAL)
        index_label = wx.StaticText(panel, label="Display Index:")
        self.index_ctrl = wx.SpinCtrl(panel, min=0, max=999, value=str(self.element[8]))
        index_help = wx.StaticText(panel, label="(Order in group)")
        index_box.Add(index_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        index_box.Add(self.index_ctrl, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        index_box.Add(index_help, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        props_sizer.Add(index_box, 0, wx.EXPAND|wx.ALL, 5)

        ocr_delay_box = wx.BoxSizer(wx.HORIZONTAL)
        ocr_delay_label = wx.StaticText(panel, label="OCR Delay (ms):")
        self.ocr_delay_ctrl = wx.SpinCtrl(panel, min=0, max=5000, value=str(self.element[10]))
        ocr_delay_help = wx.StaticText(panel, label="(Delay before OCR)")
        ocr_delay_box.Add(ocr_delay_label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        ocr_delay_box.Add(self.ocr_delay_ctrl, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        ocr_delay_box.Add(ocr_delay_help, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        props_sizer.Add(ocr_delay_box, 0, wx.EXPAND|wx.ALL, 5)
        vbox.Add(props_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # OCR Regions section
        ocr_box_static = wx.StaticBox(panel, label="OCR Regions")
        ocr_sizer = wx.StaticBoxSizer(ocr_box_static, wx.VERTICAL)
        self.ocr_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 100))
        self.ocr_list.InsertColumn(0, "Tag", width=60)
        self.ocr_list.InsertColumn(1, "Region", width=200)
        self.ocr_list.InsertColumn(2, "Conditions", width=80)
        self.update_ocr_list()
        ocr_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_ocr_btn = wx.Button(panel, label="Add")
        add_ocr_btn.Bind(wx.EVT_BUTTON, self.on_add_ocr_region)
        edit_ocr_btn = wx.Button(panel, label="Edit")
        edit_ocr_btn.Bind(wx.EVT_BUTTON, self.on_edit_ocr_region)
        del_ocr_btn = wx.Button(panel, label="Delete")
        del_ocr_btn.Bind(wx.EVT_BUTTON, self.on_delete_ocr_region)
        ocr_btn_sizer.Add(add_ocr_btn, 0, wx.RIGHT, 5)
        ocr_btn_sizer.Add(edit_ocr_btn, 0, wx.RIGHT, 5)
        ocr_btn_sizer.Add(del_ocr_btn, 0, wx.RIGHT, 5)
        ocr_sizer.Add(self.ocr_list, 1, wx.EXPAND | wx.ALL, 5)
        ocr_sizer.Add(ocr_btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(ocr_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Element Conditions section
        condition_box_static = wx.StaticBox(panel, label="Element Activation Conditions")
        condition_sizer = wx.StaticBoxSizer(condition_box_static, wx.VERTICAL)
        self.has_conditions_cb = wx.CheckBox(panel, label="This element has its own activation conditions")
        self.has_conditions_cb.SetValue(bool(self.element[9]))
        self.has_conditions_cb.Bind(wx.EVT_CHECKBOX, self.on_has_conditions_toggled)
        condition_sizer.Add(self.has_conditions_cb, 0, wx.EXPAND | wx.ALL, 5)
        self.conditions_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 120))
        self.conditions_list.InsertColumn(0, "Type", width=120)
        self.conditions_list.InsertColumn(1, "Details", width=350)
        self.conditions_list.Enable(self.has_conditions_cb.GetValue())
        self.update_conditions_list()
        
        condition_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_pixel_condition_btn = wx.Button(panel, label="Pixel")
        self.add_pixel_condition_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_element_condition("pixel_color"))
        self.add_region_color_condition_btn = wx.Button(panel, label="RegionColor")
        self.add_region_color_condition_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_element_condition("pixel_region_color"))
        self.add_image_condition_btn = wx.Button(panel, label="RegionImage")
        self.add_image_condition_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_element_condition("pixel_region_image"))
        self.add_or_condition_btn = wx.Button(panel, label="OR")
        self.add_or_condition_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_element_condition("or"))
        self.add_ocr_match_condition_btn = wx.Button(panel, label="OCR Match")
        self.add_ocr_match_condition_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_element_condition("ocr_text_match"))
        self.edit_condition_btn = wx.Button(panel, label="Edit")
        self.edit_condition_btn.Bind(wx.EVT_BUTTON, self.on_edit_element_condition)
        self.delete_condition_btn = wx.Button(panel, label="Delete")
        self.delete_condition_btn.Bind(wx.EVT_BUTTON, self.on_delete_element_condition)

        condition_btn_sizer.Add(self.add_pixel_condition_btn,0,wx.RIGHT,5)
        condition_btn_sizer.Add(self.add_region_color_condition_btn,0,wx.RIGHT,5)
        condition_btn_sizer.Add(self.add_image_condition_btn,0,wx.RIGHT,5)
        condition_btn_sizer.Add(self.add_or_condition_btn,0,wx.RIGHT,5)
        condition_btn_sizer.Add(self.add_ocr_match_condition_btn,0,wx.RIGHT,5)
        condition_btn_sizer.Add(self.edit_condition_btn,0,wx.RIGHT,5)
        condition_btn_sizer.Add(self.delete_condition_btn,0,wx.RIGHT,5)
        self.on_has_conditions_toggled(None)

        condition_sizer.Add(self.conditions_list, 1, wx.EXPAND | wx.ALL, 5)
        condition_sizer.Add(condition_btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        help_text_cond = wx.StaticText(panel, label="Element conditions are checked only when the parent menu is active.")
        help_text_cond.Wrap(500)
        condition_sizer.Add(help_text_cond, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(condition_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Custom Announcement section
        announce_box = wx.StaticBox(panel, label="Custom Announcement")
        announce_sizer = wx.StaticBoxSizer(announce_box, wx.VERTICAL)
        self.custom_announce_cb = wx.CheckBox(panel, label="Use custom announcement format")
        self.custom_announce_cb.SetValue(self.element[7] is not None)
        self.custom_announce_cb.Bind(wx.EVT_CHECKBOX, self.on_custom_announce_toggled)
        template_label = wx.StaticText(panel, label="Format Template:")
        self.template_ctrl = wx.TextCtrl(panel, value=str(self.element[7] or "{name}, {type}, {index}"), size=(-1, 80), style=wx.TE_MULTILINE)
        self.template_ctrl.Enable(self.element[7] is not None)
        help_text_announce = wx.StaticText(panel, label="Tags: {name}, {type}, {index}, {menu}, {submenu}, {group}, {ocr_tag_name}")
        announce_sizer.Add(self.custom_announce_cb, 0, wx.EXPAND | wx.ALL, 5)
        announce_sizer.Add(template_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        announce_sizer.Add(self.template_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        announce_sizer.Add(help_text_announce, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(announce_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Buttons
        button_box_main = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_box_main.AddButton(ok_button)
        button_box_main.AddButton(cancel_button)
        button_box_main.Realize()
        vbox.Add(button_box_main, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        wx.CallAfter(self.update_position_color)
        panel.SetSizer(vbox)
        panel.Layout()
        panel.SetMinSize(panel.GetBestSize())
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
    def on_close(self, event):
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        if hasattr(self, 'screen_capture'):
            self.screen_capture.close()
        event.Skip()
    
    def update_position_color(self):
        try:
            x, y = self.x_ctrl.GetValue(), self.y_ctrl.GetValue()
            if self.screenshot is None: 
                self.screenshot = self.screen_capture.capture()
            if 0 <= x < self.screenshot.width and 0 <= y < self.screenshot.height:
                pixel_color = self.screenshot.getpixel((x, y))
                if len(pixel_color) > 3: 
                    pixel_color = pixel_color[:3]
                self.color_display.SetColor(pixel_color)
        except Exception as e: 
            print(f"Error updating position color: {e}")
    
    def on_custom_announce_toggled(self, event):
        is_enabled = self.custom_announce_cb.GetValue()
        self.template_ctrl.Enable(is_enabled)
        if is_enabled and not self.template_ctrl.GetValue():
            self.template_ctrl.SetValue("{name}, {type}, {index}")
    
    def update_ocr_list(self):
        self.ocr_list.DeleteAllItems()
        ocr_regions = self.element[6]
        for i, region in enumerate(ocr_regions):
            tag = region.get("tag", f"ocr{i+1}")
            region_text = f"({region.get('x1',0)},{region.get('y1',0)})-({region.get('x2',0)},{region.get('y2',0)})"
            condition_count = len(region.get("conditions", []))
            idx = self.ocr_list.InsertItem(i, tag)
            self.ocr_list.SetItem(idx, 1, region_text)
            self.ocr_list.SetItem(idx, 2, str(condition_count) if condition_count else "")
    
    def on_add_ocr_region(self, event):
        ocr_regions = self.element[6]
        new_tag = f"ocr{len(ocr_regions) + 1}"
        dialog = OCRRegionDialog(self.profile_editor_frame, title="Add OCR Region", ocr_region={"tag": new_tag})
        if dialog.ShowModal() == wx.ID_OK:
            self.element[6].append(dialog.get_ocr_region())
            self.update_ocr_list()
        dialog.Destroy()
    
    def on_edit_ocr_region(self, event):
        selected = self.ocr_list.GetFirstSelected()
        if selected == -1: 
            return
        dialog = OCRRegionDialog(self.profile_editor_frame, title="Edit OCR Region", ocr_region=self.element[6][selected])
        if dialog.ShowModal() == wx.ID_OK:
            self.element[6][selected] = dialog.get_ocr_region()
            self.update_ocr_list()
        dialog.Destroy()
    
    def on_delete_ocr_region(self, event):
        selected = self.ocr_list.GetFirstSelected()
        if selected == -1: 
            return
        if wx.MessageBox("Delete this OCR region?", "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            del self.element[6][selected]
            self.update_ocr_list()
    
    def on_pick_location(self, event):
        self.Iconize(True)
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("Click to select element position, Esc to cancel")
        except: 
            pass
        self.screenshot = self.screen_capture.capture()
        
        picker_overlay = PixelPickerOverlay(self)
        result = picker_overlay.ShowModal()
        
        if result == wx.ID_OK and picker_overlay.get_result():
            self.end_picking(picker_overlay.get_result())
        else:
            self.end_picking(None)
        
        picker_overlay.cleanup()
        picker_overlay.Destroy()

    def end_picking(self, result):
        if hasattr(self, 'instruction_label') and self.instruction_label:
            self.instruction_label.Destroy()
            self.instruction_label = None
        if self.cursor_tracker.is_active: 
            self.cursor_tracker.stop_tracking()
        if result:
            x, y, pixel_color = result
            self.x_ctrl.SetValue(x)
            self.y_ctrl.SetValue(y)
            self.color_display.SetColor(pixel_color)
            if not self.name_ctrl.GetValue() or self.name_ctrl.GetValue() == "New Element":
                self.name_ctrl.SetValue(f"Element at {x},{y}")
        self.Iconize(False)
        self.Raise()
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText("")
        except: 
            pass
    
    def get_element(self):
        submenu_id = self.submenu_ctrl.GetValue() or None
        group = self.group_ctrl.GetValue() or "default"
        announcement = self.template_ctrl.GetValue() if self.custom_announce_cb.GetValue() else None
        conditions = self.element[9] if self.has_conditions_cb.GetValue() else []
        
        return [
            (self.x_ctrl.GetValue(), self.y_ctrl.GetValue()), self.name_ctrl.GetValue(),
            self.type_ctrl.GetStringSelection(), self.speaks_ctrl.GetValue(),
            submenu_id, group, self.element[6], announcement,
            self.index_ctrl.GetValue(), conditions, self.ocr_delay_ctrl.GetValue()
        ]

    def on_has_conditions_toggled(self, event):
        enabled = self.has_conditions_cb.GetValue()
        self.conditions_list.Enable(enabled)
        self.add_pixel_condition_btn.Enable(enabled)
        self.add_region_color_condition_btn.Enable(enabled)
        self.add_image_condition_btn.Enable(enabled)
        self.add_or_condition_btn.Enable(enabled)
        self.add_ocr_match_condition_btn.Enable(enabled)
        self.edit_condition_btn.Enable(enabled)
        self.delete_condition_btn.Enable(enabled)
        if not enabled:
            self.element[9] = []
            self.update_conditions_list()
    
    def update_conditions_list(self):
        self.conditions_list.DeleteAllItems()
        if not self.element[9]: 
            return
        for i, condition in enumerate(self.element[9]):
            condition_type = condition.get("type", "unknown")
            details = f"Negated: {condition.get('negate', False)}"
            if condition_type == "pixel_color": 
                details = f"({condition['x']},{condition['y']}) RGB{condition['color']} Tol:{condition['tolerance']}"
            elif condition_type == "pixel_region_color": 
                details = f"Region({condition['x1']},{condition['y1']}-{condition['x2']},{condition['y2']}) RGB{condition['color']} Tol:{condition['tolerance']} Thresh:{condition['threshold']}"
            elif condition_type == "pixel_region_image": 
                details = f"Region({condition['x1']},{condition['y1']}-{condition['x2']},{condition['y2']}) Conf:{condition['confidence']:.2f}"
            elif condition_type == "ocr_text_match": 
                details = f"Region({condition['x1']},{condition['y1']}-{condition['x2']},{condition['y2']}) Text: '{condition.get('expected_text','')[:20]}...'"
            elif condition_type == "or": 
                details = f"OR (Sub1: {condition['conditions'][0].get('type', 'N/A')}, Sub2: {condition['conditions'][1].get('type', 'N/A')})"
            if condition.get("negate"): 
                details = "NOT " + details
            idx = self.conditions_list.InsertItem(i, condition_type)
            self.conditions_list.SetItem(idx, 1, details)

    def on_add_element_condition(self, condition_type_to_add):
        dialog = None
        if condition_type_to_add == "pixel_color": 
            dialog = PixelColorConditionDialog(self.profile_editor_frame, "Add Element Condition")
        elif condition_type_to_add == "pixel_region_color": 
            dialog = RegionColorConditionDialog(self.profile_editor_frame, "Add Element Condition")
        elif condition_type_to_add == "pixel_region_image": 
            dialog = RegionImageConditionDialog(self.profile_editor_frame, "Add Element Condition")
        elif condition_type_to_add == "ocr_text_match": 
            dialog = OCRTextMatchConditionDialog(self.profile_editor_frame, "Add Element Condition")
        elif condition_type_to_add == "or": 
            dialog = ORConditionDialog(self.profile_editor_frame, "Add Element OR Condition")

        if dialog:
            if dialog.ShowModal() == wx.ID_OK:
                if not self.element[9]: 
                    self.element[9] = []
                self.element[9].append(dialog.get_condition())
                self.update_conditions_list()
            dialog.Destroy()
    
    def on_edit_element_condition(self, event):
        selected = self.conditions_list.GetFirstSelected()
        if selected == -1: 
            return
        condition_to_edit = self.element[9][selected]
        condition_type = condition_to_edit.get("type")
        dialog = None
        if condition_type == "pixel_color": 
            dialog = PixelColorConditionDialog(self.profile_editor_frame, "Edit Element Condition", condition=condition_to_edit)
        elif condition_type == "pixel_region_color": 
            dialog = RegionColorConditionDialog(self.profile_editor_frame, "Edit Element Condition", condition=condition_to_edit)
        elif condition_type == "pixel_region_image": 
            dialog = RegionImageConditionDialog(self.profile_editor_frame, "Edit Element Condition", condition=condition_to_edit)
        elif condition_type == "ocr_text_match": 
            dialog = OCRTextMatchConditionDialog(self.profile_editor_frame, "Edit Element Condition", condition=condition_to_edit)
        elif condition_type == "or": 
            dialog = ORConditionDialog(self.profile_editor_frame, "Edit Element OR Condition", condition=condition_to_edit)
        
        if dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.element[9][selected] = dialog.get_condition()
                self.update_conditions_list()
            dialog.Destroy()

    def on_delete_element_condition(self, event):
        selected = self.conditions_list.GetFirstSelected()
        if selected == -1: 
            return
        if wx.MessageBox("Delete this condition?", "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            del self.element[9][selected]
            self.update_conditions_list()