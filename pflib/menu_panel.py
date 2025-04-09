"""
Menu panel for editing menu data
"""

import wx
import wx.lib.scrolledpanel as scrolled
import copy

from pflib.dialogs import PixelColorConditionDialog, RegionColorConditionDialog, UIElementDialog

class MenuPanel(scrolled.ScrolledPanel):
    """Panel for displaying and editing menu data"""
    
    def __init__(self, parent, menu_id, menu_data, profile_editor):
        super().__init__(parent)
        
        self.menu_id = menu_id
        self.menu_data = menu_data
        self.profile_editor = profile_editor
        
        # Bind keyboard events
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        
        self.init_ui()
        self.SetupScrolling()
        
    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Menu Header
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title = wx.StaticText(self, label=f"Menu: {self.menu_id}")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        header_sizer.Add(title, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        
        # Menu action buttons
        duplicate_btn = wx.Button(self, label="Duplicate")
        duplicate_btn.Bind(wx.EVT_BUTTON, self.on_duplicate_menu)
        
        rename_btn = wx.Button(self, label="Rename")
        rename_btn.Bind(wx.EVT_BUTTON, self.on_rename_menu)
        
        delete_btn = wx.Button(self, label="Delete")
        delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_menu)
        
        header_sizer.Add(duplicate_btn, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        header_sizer.Add(rename_btn, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        header_sizer.Add(delete_btn, flag=wx.ALIGN_CENTER_VERTICAL)
        
        main_sizer.Add(header_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Conditions section
        conditions_box = wx.StaticBox(self, label="Menu Detection Conditions")
        conditions_sizer = wx.StaticBoxSizer(conditions_box, wx.VERTICAL)
        
        # Add condition buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_pixel_btn = wx.Button(self, label="Add Pixel Color")
        add_pixel_btn.Bind(wx.EVT_BUTTON, self.on_add_pixel_condition)
        add_region_btn = wx.Button(self, label="Add Region Color")
        add_region_btn.Bind(wx.EVT_BUTTON, self.on_add_region_condition)
        
        paste_condition_btn = wx.Button(self, label="Paste Condition(s)")
        paste_condition_btn.Bind(wx.EVT_BUTTON, self.on_paste_condition)
        
        btn_sizer.Add(add_pixel_btn, flag=wx.RIGHT, border=5)
        btn_sizer.Add(add_region_btn, flag=wx.RIGHT, border=5)
        btn_sizer.Add(paste_condition_btn)
        conditions_sizer.Add(btn_sizer, flag=wx.ALL, border=5)
        
        # Conditions list - using just wx.LC_REPORT since multi-select is default
        self.conditions_list = wx.ListCtrl(self, style=wx.LC_REPORT, size=(-1, 150))
        self.conditions_list.InsertColumn(0, "Type", width=100)
        self.conditions_list.InsertColumn(1, "Details", width=300)
        
        # Populate conditions
        self.update_conditions_list()
        
        # Context menu for conditions
        self.conditions_list.Bind(wx.EVT_CONTEXT_MENU, self.on_condition_context_menu)
        
        # Install key event handlers for the list
        self.conditions_list.Bind(wx.EVT_KEY_DOWN, self.on_conditions_key)
        
        conditions_sizer.Add(self.conditions_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        main_sizer.Add(conditions_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # UI Elements section
        elements_box = wx.StaticBox(self, label="Menu UI Elements")
        elements_sizer = wx.StaticBoxSizer(elements_box, wx.VERTICAL)
        
        # Elements buttons
        element_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_element_btn = wx.Button(self, label="Add UI Element")
        add_element_btn.Bind(wx.EVT_BUTTON, self.on_add_element)
        
        paste_element_btn = wx.Button(self, label="Paste Element(s)")
        paste_element_btn.Bind(wx.EVT_BUTTON, self.on_paste_element)
        
        element_btn_sizer.Add(add_element_btn, flag=wx.RIGHT, border=5)
        element_btn_sizer.Add(paste_element_btn)
        elements_sizer.Add(element_btn_sizer, flag=wx.ALL, border=5)
        
        # Elements list - using just wx.LC_REPORT since multi-select is default
        self.elements_list = wx.ListCtrl(self, style=wx.LC_REPORT, size=(-1, 200))
        self.elements_list.InsertColumn(0, "Name", width=150)
        self.elements_list.InsertColumn(1, "Type", width=100)
        self.elements_list.InsertColumn(2, "Position", width=100)
        self.elements_list.InsertColumn(3, "Submenu", width=100)
        
        # Populate elements
        self.update_elements_list()
        
        # Context menu for elements
        self.elements_list.Bind(wx.EVT_CONTEXT_MENU, self.on_element_context_menu)
        
        # Install key event handlers for the list
        self.elements_list.Bind(wx.EVT_KEY_DOWN, self.on_elements_key)
        
        elements_sizer.Add(self.elements_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        main_sizer.Add(elements_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        self.SetSizer(main_sizer)
        
    def on_rename_menu(self, event):
        """Handle rename menu button click"""
        self.profile_editor.on_rename_menu(event)
        
    def on_duplicate_menu(self, event):
        """Handle duplicate menu button click"""
        self.profile_editor.on_duplicate_menu(event)
    
    def on_conditions_key(self, event):
        """Handle key events specifically for the conditions list"""
        key_code = event.GetKeyCode()
        is_ctrl = event.ControlDown()
        
        # Handle Ctrl+C (copy)
        if is_ctrl and key_code == ord('C'):
            self.on_copy_condition(None)
        # Handle Ctrl+V (paste)
        elif is_ctrl and key_code == ord('V'):
            self.on_paste_condition(None)
        # Handle Delete key
        elif key_code == wx.WXK_DELETE:
            self.on_delete_condition(None)
        else:
            event.Skip()  # Let other handlers process this event
    
    def on_elements_key(self, event):
        """Handle key events specifically for the elements list"""
        key_code = event.GetKeyCode()
        is_ctrl = event.ControlDown()
        
        # Handle Ctrl+C (copy)
        if is_ctrl and key_code == ord('C'):
            self.on_copy_element(None)
        # Handle Ctrl+V (paste)
        elif is_ctrl and key_code == ord('V'):
            self.on_paste_element(None)
        # Handle Delete key
        elif key_code == wx.WXK_DELETE:
            self.on_delete_element(None)
        else:
            event.Skip()  # Let other handlers process this event
    
    def on_key_down(self, event):
        """Handle keyboard shortcuts in the menu panel"""
        # Get key code and modifiers
        key_code = event.GetKeyCode()
        is_ctrl = event.ControlDown()
        
        # Let the event propagate to the focused control
        event.Skip()
    
    def update_conditions_list(self):
        """Update the conditions list with current data"""
        self.conditions_list.DeleteAllItems()
        
        if "conditions" not in self.menu_data:
            return
            
        for i, condition in enumerate(self.menu_data["conditions"]):
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
        
        # Only show edit if a single item is selected
        if self.conditions_list.GetSelectedItemCount() == 1:
            edit_item = menu.Append(wx.ID_ANY, "Edit Condition")
            self.Bind(wx.EVT_MENU, self.on_edit_condition, edit_item)
            menu.AppendSeparator()
        
        copy_item = menu.Append(wx.ID_ANY, "Copy Condition(s)")
        delete_item = menu.Append(wx.ID_ANY, "Delete Condition(s)")
        menu.AppendSeparator()
        paste_item = menu.Append(wx.ID_ANY, "Paste Condition(s)")
        
        self.Bind(wx.EVT_MENU, self.on_copy_condition, copy_item)
        self.Bind(wx.EVT_MENU, self.on_delete_condition, delete_item)
        self.Bind(wx.EVT_MENU, self.on_paste_condition, paste_item)
        
        self.PopupMenu(menu)
        menu.Destroy()
    
    def on_copy_condition(self, event):
        """Copy selected condition(s) to the clipboard"""
        # Clear previous conditions in clipboard
        self.profile_editor.clipboard['conditions'] = []
        
        # Get selected items
        selected_items = []
        item = self.conditions_list.GetFirstSelected()
        
        while item != -1:
            selected_items.append(item)
            item = self.conditions_list.GetNextSelected(item)
        
        if not selected_items:
            return
        
        # Copy each selected condition
        for idx in selected_items:
            condition = copy.deepcopy(self.menu_data["conditions"][idx])
            self.profile_editor.clipboard['conditions'].append(condition)
        
        # Update status
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            if len(selected_items) == 1:
                parent_frame.SetStatusText(f"Copied 1 condition")
            else:
                parent_frame.SetStatusText(f"Copied {len(selected_items)} conditions")
        except:
            pass

    def on_paste_condition(self, event):
        """Paste condition(s) from the clipboard"""
        # Check if we have conditions in clipboard
        if not self.profile_editor.clipboard['conditions']:
            wx.MessageBox("No conditions in clipboard", "Cannot Paste", wx.ICON_INFORMATION)
            return
        
        # Initialize conditions list if not present
        if "conditions" not in self.menu_data:
            self.menu_data["conditions"] = []
        
        # Get the conditions from clipboard (make deep copies)
        count = 0
        for condition in self.profile_editor.clipboard['conditions']:
            self.menu_data["conditions"].append(copy.deepcopy(condition))
            count += 1
        
        # Update UI
        self.update_conditions_list()
        self.profile_editor.mark_profile_changed()
        
        # Update status
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            if count == 1:
                parent_frame.SetStatusText(f"Pasted 1 condition")
            else:
                parent_frame.SetStatusText(f"Pasted {count} conditions")
        except:
            pass
    
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
        """Delete the selected condition(s)"""
        if self.conditions_list.GetSelectedItemCount() == 0:
            return
            
        # Get all selected indices in reverse order (to avoid index shifting during deletion)
        selected_indices = []
        item = self.conditions_list.GetFirstSelected()
        while item != -1:
            selected_indices.append(item)
            item = self.conditions_list.GetNextSelected(item)
        
        # Sort in reverse order
        selected_indices.sort(reverse=True)
        
        # Confirm deletion
        if len(selected_indices) == 1:
            prompt = "Are you sure you want to delete this condition?"
        else:
            prompt = f"Are you sure you want to delete these {len(selected_indices)} conditions?"
            
        if wx.MessageBox(prompt, "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        
        # Delete each selected item
        for idx in selected_indices:
            del self.menu_data["conditions"][idx]
        
        self.update_conditions_list()
        self.profile_editor.mark_profile_changed()
        
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            if len(selected_indices) == 1:
                parent_frame.SetStatusText(f"Deleted 1 condition")
            else:
                parent_frame.SetStatusText(f"Deleted {len(selected_indices)} conditions")
        except:
            pass
    
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
        
        # Only show edit if a single item is selected
        if self.elements_list.GetSelectedItemCount() == 1:
            edit_item = menu.Append(wx.ID_ANY, "Edit Element")
            self.Bind(wx.EVT_MENU, self.on_edit_element, edit_item)
            menu.AppendSeparator()
        
        copy_item = menu.Append(wx.ID_ANY, "Copy Element(s)")
        delete_item = menu.Append(wx.ID_ANY, "Delete Element(s)")
        menu.AppendSeparator()
        paste_item = menu.Append(wx.ID_ANY, "Paste Element(s)")
        
        self.Bind(wx.EVT_MENU, self.on_copy_element, copy_item)
        self.Bind(wx.EVT_MENU, self.on_delete_element, delete_item)
        self.Bind(wx.EVT_MENU, self.on_paste_element, paste_item)
        
        self.PopupMenu(menu)
        menu.Destroy()
    
    def on_copy_element(self, event):
        """Copy the selected element(s) to the clipboard"""
        # Clear previous elements in clipboard
        self.profile_editor.clipboard['elements'] = []
        
        # Get selected items
        selected_items = []
        item = self.elements_list.GetFirstSelected()
        
        while item != -1:
            selected_items.append(item)
            item = self.elements_list.GetNextSelected(item)
        
        if not selected_items:
            return
        
        # Copy each selected element
        for idx in selected_items:
            element = copy.deepcopy(self.menu_data["items"][idx])
            self.profile_editor.clipboard['elements'].append(element)
        
        # Update status
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            if len(selected_items) == 1:
                parent_frame.SetStatusText(f"Copied 1 element")
            else:
                parent_frame.SetStatusText(f"Copied {len(selected_items)} elements")
        except:
            pass

    def on_paste_element(self, event):
        """Paste element(s) from the clipboard"""
        # Check if we have elements in clipboard
        if not self.profile_editor.clipboard['elements']:
            wx.MessageBox("No elements in clipboard", "Cannot Paste", wx.ICON_INFORMATION)
            return
        
        # Initialize items list if not present
        if "items" not in self.menu_data:
            self.menu_data["items"] = []
        
        # Get the elements from clipboard (make deep copies)
        count = 0
        for element in self.profile_editor.clipboard['elements']:
            self.menu_data["items"].append(copy.deepcopy(element))
            count += 1
        
        # Update UI
        self.update_elements_list()
        self.profile_editor.mark_profile_changed()
        
        # Update status
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            if count == 1:
                parent_frame.SetStatusText(f"Pasted 1 element")
            else:
                parent_frame.SetStatusText(f"Pasted {count} elements")
        except:
            pass
    
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
        """Delete the selected element(s)"""
        if self.elements_list.GetSelectedItemCount() == 0:
            return
            
        # Get all selected indices in reverse order (to avoid index shifting during deletion)
        selected_indices = []
        item = self.elements_list.GetFirstSelected()
        while item != -1:
            selected_indices.append(item)
            item = self.elements_list.GetNextSelected(item)
        
        # Sort in reverse order
        selected_indices.sort(reverse=True)
        
        # Confirm deletion
        if len(selected_indices) == 1:
            prompt = "Are you sure you want to delete this element?"
        else:
            prompt = f"Are you sure you want to delete these {len(selected_indices)} elements?"
            
        if wx.MessageBox(prompt, "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        
        # Delete each selected item
        for idx in selected_indices:
            del self.menu_data["items"][idx]
        
        self.update_elements_list()
        self.profile_editor.mark_profile_changed()
        
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            if len(selected_indices) == 1:
                parent_frame.SetStatusText(f"Deleted 1 element")
            else:
                parent_frame.SetStatusText(f"Deleted {len(selected_indices)} elements")
        except:
            pass
    
    def on_delete_menu(self, event):
        """Delete this entire menu"""
        if wx.MessageBox(f"Are you sure you want to delete the menu '{self.menu_id}'?", 
                       "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.profile_editor.delete_menu(self.menu_id)