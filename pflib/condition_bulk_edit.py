"""
Dialog for bulk editing multiple conditions
"""

import wx
from pflib.ui_components import ColorDisplay

class BulkEditConditionsDialog(wx.Dialog):
    """Dialog for editing properties across multiple conditions"""
    
    def __init__(self, parent):
        super().__init__(parent, title="Bulk Edit Conditions", size=(400, 250))
        
        # Initialize UI
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Instructions
        instructions = wx.StaticText(panel, label="Select properties to modify for all selected conditions:")
        instructions.Wrap(380)
        main_sizer.Add(instructions, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Color
        color_box = wx.BoxSizer(wx.HORIZONTAL)
        self.color_cb = wx.CheckBox(panel, label="Change color:")
        self.color_display = ColorDisplay(panel, initial_color=(255, 255, 255))
        self.color_display.Enable(False)
        
        # Add a "Pick Color" button
        self.pick_color_btn = wx.Button(panel, label="Pick Color")
        self.pick_color_btn.Enable(False)
        self.pick_color_btn.Bind(wx.EVT_BUTTON, self.on_pick_color)
        
        self.color_cb.Bind(wx.EVT_CHECKBOX, self.on_color_checked)
        
        color_box.Add(self.color_cb, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        color_box.Add(self.color_display, proportion=1, flag=wx.RIGHT, border=5)
        color_box.Add(self.pick_color_btn)
        main_sizer.Add(color_box, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Tolerance
        tolerance_box = wx.BoxSizer(wx.HORIZONTAL)
        self.tolerance_cb = wx.CheckBox(panel, label="Change tolerance:")
        self.tolerance_ctrl = wx.SpinCtrl(panel, min=0, max=255, value="10")
        self.tolerance_ctrl.Enable(False)
        self.tolerance_cb.Bind(wx.EVT_CHECKBOX, lambda evt: self.tolerance_ctrl.Enable(evt.IsChecked()))
        
        tolerance_box.Add(self.tolerance_cb, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        tolerance_box.Add(self.tolerance_ctrl, proportion=1)
        main_sizer.Add(tolerance_box, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        apply_btn = wx.Button(panel, wx.ID_OK, "Apply")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        
        button_sizer.Add(apply_btn)
        button_sizer.Add(cancel_btn, flag=wx.LEFT, border=5)
        
        main_sizer.Add(button_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        panel.SetSizer(main_sizer)
    
    def on_color_checked(self, event):
        """Handle color checkbox state change"""
        is_checked = event.IsChecked()
        self.color_display.Enable(is_checked)
        self.pick_color_btn.Enable(is_checked)
    
    def on_pick_color(self, event):
        """Open color picker dialog"""
        color_data = wx.ColourData()
        color_data.SetColour(wx.Colour(*self.color_display.GetColor()))
        
        dialog = wx.ColourDialog(self, color_data)
        if dialog.ShowModal() == wx.ID_OK:
            color = dialog.GetColourData().GetColour()
            rgb = (color.Red(), color.Green(), color.Blue())
            self.color_display.SetColor(rgb)
        
        dialog.Destroy()
    
    def get_bulk_changes(self):
        """Get the user-selected changes to apply in bulk"""
        changes = {}
        
        if self.color_cb.GetValue():
            changes['color'] = list(self.color_display.GetColor())
        
        if self.tolerance_cb.GetValue():
            changes['tolerance'] = self.tolerance_ctrl.GetValue()
        
        return changes
