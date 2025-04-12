"""
Dialog for bulk editing multiple UI elements
"""

import wx
import wx.lib.scrolledpanel as scrolled

class BulkEditElementsDialog(wx.Dialog):
    """Dialog for editing properties across multiple elements"""
    
    def __init__(self, parent):
        super().__init__(parent, title="Bulk Edit Elements", size=(400, 380))
        
        # Initialize UI
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Instructions
        instructions = wx.StaticText(panel, label="Select properties to modify for all selected elements:")
        instructions.Wrap(380)
        main_sizer.Add(instructions, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Element type
        type_box = wx.BoxSizer(wx.HORIZONTAL)
        self.type_cb = wx.CheckBox(panel, label="Change type:")
        element_types = ["button", "dropdown", "menu", "tab", "toggle", "link"]
        self.type_ctrl = wx.Choice(panel, choices=element_types)
        self.type_ctrl.SetSelection(0)
        self.type_ctrl.Enable(False)
        self.type_cb.Bind(wx.EVT_CHECKBOX, lambda evt: self.type_ctrl.Enable(evt.IsChecked()))
        
        type_box.Add(self.type_cb, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        type_box.Add(self.type_ctrl, proportion=1)
        main_sizer.Add(type_box, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Speaks on select
        speaks_box = wx.BoxSizer(wx.HORIZONTAL)
        self.speaks_cb = wx.CheckBox(panel, label="Change speaks on select:")
        self.speaks_ctrl = wx.CheckBox(panel, label="Enable")
        self.speaks_ctrl.Enable(False)
        self.speaks_cb.Bind(wx.EVT_CHECKBOX, lambda evt: self.speaks_ctrl.Enable(evt.IsChecked()))
        
        speaks_box.Add(self.speaks_cb, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        speaks_box.Add(self.speaks_ctrl, proportion=1)
        main_sizer.Add(speaks_box, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Submenu ID
        submenu_box = wx.BoxSizer(wx.HORIZONTAL)
        self.submenu_cb = wx.CheckBox(panel, label="Change submenu ID:")
        self.submenu_ctrl = wx.TextCtrl(panel)
        self.submenu_ctrl.Enable(False)
        self.submenu_cb.Bind(wx.EVT_CHECKBOX, lambda evt: self.submenu_ctrl.Enable(evt.IsChecked()))
        
        submenu_box.Add(self.submenu_cb, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        submenu_box.Add(self.submenu_ctrl, proportion=1)
        main_sizer.Add(submenu_box, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Group
        group_box = wx.BoxSizer(wx.HORIZONTAL)
        self.group_cb = wx.CheckBox(panel, label="Change group:")
        self.group_ctrl = wx.ComboBox(panel, choices=["default", "tab-bar", "main-content", "side-panel", "footer"])
        self.group_ctrl.SetValue("default")
        self.group_ctrl.Enable(False)
        self.group_cb.Bind(wx.EVT_CHECKBOX, lambda evt: self.group_ctrl.Enable(evt.IsChecked()))
        
        group_box.Add(self.group_cb, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        group_box.Add(self.group_ctrl, proportion=1)
        main_sizer.Add(group_box, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Custom announcement
        announcement_box = wx.BoxSizer(wx.HORIZONTAL)
        self.announcement_cb = wx.CheckBox(panel, label="Clear custom announcement")
        
        announcement_box.Add(self.announcement_cb, flag=wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(announcement_box, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Clear OCR regions
        ocr_box = wx.BoxSizer(wx.HORIZONTAL)
        self.ocr_cb = wx.CheckBox(panel, label="Clear OCR regions")
        
        ocr_box.Add(self.ocr_cb, flag=wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(ocr_box, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        apply_btn = wx.Button(panel, wx.ID_OK, "Apply")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        
        button_sizer.Add(apply_btn)
        button_sizer.Add(cancel_btn, flag=wx.LEFT, border=5)
        
        main_sizer.Add(button_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        panel.SetSizer(main_sizer)
    
    def get_bulk_changes(self):
        """Get the user-selected changes to apply in bulk"""
        changes = {}
        
        if self.type_cb.GetValue():
            type_idx = self.type_ctrl.GetSelection()
            if type_idx != -1:
                changes['type'] = self.type_ctrl.GetString(type_idx)
        
        if self.speaks_cb.GetValue():
            changes['speaks_on_select'] = self.speaks_ctrl.GetValue()
        
        if self.submenu_cb.GetValue():
            submenu = self.submenu_ctrl.GetValue()
            changes['submenu_id'] = submenu if submenu else None
        
        if self.group_cb.GetValue():
            group = self.group_ctrl.GetValue()
            changes['group'] = group if group else "default"
        
        if self.announcement_cb.GetValue():
            changes['clear_announcement'] = True
            
        if self.ocr_cb.GetValue():
            changes['clear_ocr'] = True
        
        return changes