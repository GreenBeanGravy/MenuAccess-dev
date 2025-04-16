"""
Menu panel for editing menu data with improved drag and drop
"""

import wx
import wx.lib.scrolledpanel as scrolled
import copy

from pflib.dialogs import PixelColorConditionDialog, RegionColorConditionDialog, UIElementDialog
from pflib.bulk_edit_dialog import BulkEditElementsDialog
from pflib.condition_bulk_edit import BulkEditConditionsDialog

class GroupManagerDialog(wx.Dialog):
    """Dialog for managing element groups in a menu"""
    
    def __init__(self, parent, menu_data):
        super().__init__(parent, title="Group Manager", size=(400, 400))
        
        self.menu_data = menu_data
        # Store parent for immediate refresh
        self.menu_panel = parent
        
        # Collect all existing groups
        self.groups = set(["default"])
        if "items" in self.menu_data:
            for item in self.menu_data["items"]:
                if len(item) > 5 and item[5]:
                    self.groups.add(item[5])
        
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Instructions
        instructions = wx.StaticText(panel, label="Manage element groups in this menu:")
        main_sizer.Add(instructions, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Group list
        list_label = wx.StaticText(panel, label="Groups:")
        main_sizer.Add(list_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        
        self.group_list = wx.ListBox(panel, choices=sorted(list(self.groups)), size=(-1, 200))
        main_sizer.Add(self.group_list, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        
        # Group actions
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.add_btn = wx.Button(panel, label="Add Group")
        self.rename_btn = wx.Button(panel, label="Rename Group")
        self.delete_btn = wx.Button(panel, label="Delete Group")
        
        self.add_btn.Bind(wx.EVT_BUTTON, self.on_add_group)
        self.rename_btn.Bind(wx.EVT_BUTTON, self.on_rename_group)
        self.delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_group)
        
        btn_sizer.Add(self.add_btn, flag=wx.RIGHT, border=5)
        btn_sizer.Add(self.rename_btn, flag=wx.RIGHT, border=5)
        btn_sizer.Add(self.delete_btn)
        
        main_sizer.Add(btn_sizer, flag=wx.ALL | wx.ALIGN_CENTER, border=10)
        
        # Element count per group
        self.count_text = wx.StaticText(panel, label="")
        main_sizer.Add(self.count_text, flag=wx.ALL | wx.EXPAND, border=10)
        
        # OK/Cancel buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        btn_sizer.AddButton(ok_button)
        btn_sizer.AddButton(cancel_button)
        btn_sizer.Realize()
        
        main_sizer.Add(btn_sizer, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
        
        panel.SetSizer(main_sizer)
        
        # Update button states
        self.update_ui()
        
        # Bind list selection event
        self.group_list.Bind(wx.EVT_LISTBOX, self.on_group_selected)
        
    def on_group_selected(self, event):
        """Handle group selection"""
        self.update_ui()
    
    def update_ui(self):
        """Update UI based on current state"""
        selection = self.group_list.GetSelection()
        has_selection = selection != wx.NOT_FOUND
        
        # Update buttons
        self.rename_btn.Enable(has_selection)
        self.delete_btn.Enable(has_selection and self.group_list.GetString(selection) != "default")
        
        # Update element count text
        if has_selection:
            group_name = self.group_list.GetString(selection)
            count = self.count_elements_in_group(group_name)
            self.count_text.SetLabel(f"Elements in group '{group_name}': {count}")
        else:
            self.count_text.SetLabel("")
    
    def count_elements_in_group(self, group_name):
        """Count how many elements are in a specific group"""
        count = 0
        if "items" in self.menu_data:
            for item in self.menu_data["items"]:
                item_group = item[5] if len(item) > 5 else "default"
                if item_group == group_name:
                    count += 1
        return count
    
    def on_add_group(self, event):
        """Add a new group"""
        dialog = wx.TextEntryDialog(self, "Enter new group name:", "Add Group")
        if dialog.ShowModal() == wx.ID_OK:
            group_name = dialog.GetValue().strip()
            if group_name:
                if group_name in self.groups:
                    wx.MessageBox(f"Group '{group_name}' already exists", "Duplicate Group", wx.ICON_ERROR)
                else:
                    self.groups.add(group_name)
                    self.group_list.Set(sorted(list(self.groups)))
                    # Select the new group
                    self.group_list.SetSelection(self.group_list.FindString(group_name))
                    self.update_ui()
                    
                    # Set return code and trigger immediate refresh in parent
                    self.SetReturnCode(wx.ID_OK)
                    
                    # CRITICAL: Immediately refresh parent panel
                    wx.CallAfter(self.menu_panel.refresh_entire_panel)
        dialog.Destroy()
    
    def on_rename_group(self, event):
        """Rename the selected group"""
        selection = self.group_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return
            
        old_name = self.group_list.GetString(selection)
        if old_name == "default":
            wx.MessageBox("Cannot rename the 'default' group", "Error", wx.ICON_ERROR)
            return
            
        dialog = wx.TextEntryDialog(self, "Enter new group name:", "Rename Group", old_name)
        if dialog.ShowModal() == wx.ID_OK:
            new_name = dialog.GetValue().strip()
            if new_name:
                if new_name in self.groups and new_name != old_name:
                    wx.MessageBox(f"Group '{new_name}' already exists", "Duplicate Group", wx.ICON_ERROR)
                else:
                    # Update all elements with this group
                    if "items" in self.menu_data:
                        for item in self.menu_data["items"]:
                            if len(item) > 5 and item[5] == old_name:
                                item[5] = new_name
                    
                    # Update group list
                    self.groups.remove(old_name)
                    self.groups.add(new_name)
                    self.group_list.Set(sorted(list(self.groups)))
                    # Select the renamed group
                    self.group_list.SetSelection(self.group_list.FindString(new_name))
                    self.update_ui()
                    
                    # Set result to true to indicate changes were made
                    self.SetReturnCode(wx.ID_OK)
                    
                    # CRITICAL: Immediately refresh parent panel
                    wx.CallAfter(self.menu_panel.refresh_entire_panel)
        dialog.Destroy()
    
    def on_delete_group(self, event):
        """Delete the selected group"""
        selection = self.group_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return
            
        group_name = self.group_list.GetString(selection)
        if group_name == "default":
            wx.MessageBox("Cannot delete the 'default' group", "Error", wx.ICON_ERROR)
            return
            
        count = self.count_elements_in_group(group_name)
        if count > 0:
            msg = f"Group '{group_name}' contains {count} elements. "
            msg += "Deleting this group will move these elements to the 'default' group. Continue?"
            
            if wx.MessageBox(msg, "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
                return
                
            # Move elements to default group
            if "items" in self.menu_data:
                for item in self.menu_data["items"]:
                    if len(item) > 5 and item[5] == group_name:
                        item[5] = "default"
        
        # Remove the group
        self.groups.remove(group_name)
        self.group_list.Set(sorted(list(self.groups)))
        
        # Clear selection
        self.group_list.SetSelection(wx.NOT_FOUND)
        self.update_ui()
        
        # Set result to true to indicate changes were made
        self.SetReturnCode(wx.ID_OK)
        
        # CRITICAL: Immediately refresh parent panel
        wx.CallAfter(self.menu_panel.refresh_entire_panel)


class MenuPanel(scrolled.ScrolledPanel):
    """Panel for displaying and editing menu data"""
    
    def __init__(self, parent, menu_id, menu_data, profile_editor):
        super().__init__(parent)
        
        self.menu_id = menu_id
        self.menu_data = menu_data
        self.profile_editor = profile_editor
        
        # Drag and drop state
        self.dragging = False
        self.drag_start_pos = None
        self.drag_item_index = None
        self.drag_group = False
        self.drop_indicator_line = None
        
        # Bind keyboard events
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        
        # Initialize UI
        self.init_ui()
        
        # Update reset group options
        self.update_reset_group_options()
        
        # Configure scrolling to work properly
        self.SetupScrolling(scrollToTop=False, scrollIntoView=False, rate_x=20, rate_y=20)
        
    def init_ui(self):
        # Main sizer that contains everything
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Menu Header
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title = wx.StaticText(self, label=f"Menu: {self.menu_id}")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        header_sizer.Add(title, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        
        # Add reset index checkbox
        option_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.reset_index_cb = wx.CheckBox(self, label="Reset index when entering menu")
        self.reset_index_cb.SetValue(self.menu_data.get("reset_index", True))  # Default to True for backward compatibility
        self.reset_index_cb.Bind(wx.EVT_CHECKBOX, self.on_reset_index_changed)
        option_sizer.Add(self.reset_index_cb, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=15)
        
        # Add reset group option
        reset_group_label = wx.StaticText(self, label="Reset to group:")
        # Default group options (will be populated with actual groups later)
        standard_groups = ["default"]
        # Use a combobox to allow both selection from predefined options and custom input
        self.reset_group_ctrl = wx.ComboBox(self, choices=standard_groups,
                                         value=self.menu_data.get("reset_group", "default"))
        option_sizer.Add(reset_group_label, flag=wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        option_sizer.Add(self.reset_group_ctrl, proportion=1)
        
        # Add to header sizer
        header_sizer.Add(option_sizer, flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=15)
        
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
        
        self.main_sizer.Add(header_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        
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
        # Make sure it's resizable by adding proportion=1
        self.conditions_list = wx.ListCtrl(self, style=wx.LC_REPORT, size=(-1, 150))
        self.conditions_list.InsertColumn(0, "Type", width=150)
        self.conditions_list.InsertColumn(1, "Details", width=450)
        
        # Populate conditions
        self.update_conditions_list()
        
        # Context menu for conditions
        self.conditions_list.Bind(wx.EVT_CONTEXT_MENU, self.on_condition_context_menu)
        
        # Add double-click for editing conditions
        self.conditions_list.Bind(wx.EVT_LEFT_DCLICK, self.on_condition_dclick)
        
        # Install key event handlers for the list
        self.conditions_list.Bind(wx.EVT_KEY_DOWN, self.on_conditions_key)
        
        conditions_sizer.Add(self.conditions_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        self.main_sizer.Add(conditions_sizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        
        # UI Elements section
        elements_box = wx.StaticBox(self, label="Menu UI Elements")
        elements_sizer = wx.StaticBoxSizer(elements_box, wx.VERTICAL)
        
        # Group filter
        group_filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        group_filter_label = wx.StaticText(self, label="Filter by Group:")
        
        # Collect all groups
        all_groups = self.get_all_groups()
        all_groups.insert(0, "All Groups")  # Add option to show all
        
        self.group_filter = wx.Choice(self, choices=all_groups)
        self.group_filter.SetSelection(0)  # Default to "All Groups"
        self.group_filter.Bind(wx.EVT_CHOICE, self.on_group_filter_changed)
        
        # Manage groups button
        manage_groups_btn = wx.Button(self, label="Manage Groups")
        manage_groups_btn.Bind(wx.EVT_BUTTON, self.on_manage_groups)
        
        group_filter_sizer.Add(group_filter_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        group_filter_sizer.Add(self.group_filter, proportion=1, flag=wx.RIGHT, border=10)
        group_filter_sizer.Add(manage_groups_btn)
        
        elements_sizer.Add(group_filter_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Elements buttons
        element_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_element_btn = wx.Button(self, label="Add UI Element")
        add_element_btn.Bind(wx.EVT_BUTTON, self.on_add_element)
        
        paste_element_btn = wx.Button(self, label="Paste Element(s)")
        paste_element_btn.Bind(wx.EVT_BUTTON, self.on_paste_element)
        
        element_btn_sizer.Add(add_element_btn, flag=wx.RIGHT, border=5)
        element_btn_sizer.Add(paste_element_btn)
        elements_sizer.Add(element_btn_sizer, flag=wx.ALL, border=5)
        
        # Elements list - with wider columns and drag-and-drop support
        self.elements_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 200))
        self.elements_list.InsertColumn(0, "Name", width=225)
        self.elements_list.InsertColumn(1, "Type", width=120)
        self.elements_list.InsertColumn(2, "Position", width=120)
        self.elements_list.InsertColumn(3, "Group", width=120)
        self.elements_list.InsertColumn(4, "Submenu", width=120)
        self.elements_list.InsertColumn(5, "OCR", width=90)
        self.elements_list.InsertColumn(6, "Custom Format", width=120)
        
        # Set up drag and drop events
        self.elements_list.Bind(wx.EVT_LEFT_DOWN, self.on_element_left_down)
        self.elements_list.Bind(wx.EVT_MOTION, self.on_element_motion)
        self.elements_list.Bind(wx.EVT_LEFT_UP, self.on_element_left_up)
        self.elements_list.Bind(wx.EVT_LEAVE_WINDOW, self.on_element_leave_window)
        
        # Populate elements
        self.update_elements_list()
        
        # Context menu for elements
        self.elements_list.Bind(wx.EVT_CONTEXT_MENU, self.on_element_context_menu)
        
        # Add double-click for editing elements
        self.elements_list.Bind(wx.EVT_LEFT_DCLICK, self.on_element_dclick)
        
        # Install key event handlers for the list
        self.elements_list.Bind(wx.EVT_KEY_DOWN, self.on_elements_key)
        
        elements_sizer.Add(self.elements_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Add drag and drop help text
        drag_help = wx.StaticText(self, label="Tip: Drag elements or group headers to rearrange them")
        drag_help.SetForegroundColour(wx.Colour(100, 100, 100))  # Gray text
        elements_sizer.Add(drag_help, flag=wx.ALL, border=5)
        
        self.main_sizer.Add(elements_sizer, proportion=2, flag=wx.EXPAND | wx.ALL, border=10)
        
        self.SetSizer(self.main_sizer)
    
    # Drag and drop implementation for elements list
    def on_element_left_down(self, event):
        """Start drag operation on left mouse button down"""
        # Get the item under cursor
        item, flags = self.elements_list.HitTest(event.GetPosition())
        
        if item != -1:
            # Check if it's a group header
            text = self.elements_list.GetItemText(item)
            
            # Select the item
            self.elements_list.Select(item)
            
            # Store the starting information
            self.drag_start_pos = event.GetPosition()
            self.drag_item_index = item
            
            # Check if it's a group header (special format)
            if text.startswith("---") and text.endswith("---"):
                # It's a group header
                self.drag_group = True
                # Extract group name
                self.drag_group_name = text.strip("-").strip()
            else:
                # It's a regular element
                self.drag_group = False
                # Only allow dragging if it's a real element with data
                data_idx = self.elements_list.GetItemData(item)
                if data_idx == -1:  # It's a separator, not a real element
                    self.drag_item_index = None
                    self.drag_start_pos = None
        
        event.Skip()
    
    def on_element_motion(self, event):
        """Handle mouse motion for drag-and-drop operations"""
        if not self.drag_start_pos or not self.drag_item_index:
            event.Skip()
            return
            
        # Only start drag after moving a bit
        if not self.dragging:
            # Check if we've moved enough to start dragging
            start_pos = self.drag_start_pos
            curr_pos = event.GetPosition()
            
            # Require at least 5 pixels of movement
            if abs(curr_pos.x - start_pos.x) > 5 or abs(curr_pos.y - start_pos.y) > 5:
                self.dragging = True
                
                # Setting hand cursor
                self.elements_list.SetCursor(wx.Cursor(wx.CURSOR_HAND))
                
                # Provide better visual hint for the item being dragged
                self.elements_list.SetItemBackgroundColour(self.drag_item_index, wx.Colour(230, 230, 255))
        
        if self.dragging:
            # Find potential drop position
            pos = event.GetPosition()
            item, flags = self.elements_list.HitTest(pos)
            
            # Clear old indicator if it exists
            if self.drop_indicator_line is not None:
                self.elements_list.RefreshItem(self.drop_indicator_line)
                self.drop_indicator_line = None
            
            # Show drop indicator if over a valid item
            if item != -1 and item != self.drag_item_index:
                # Don't allow dropping into separators
                data_idx = self.elements_list.GetItemData(item)
                if data_idx != -1 or self.elements_list.GetItemText(item).startswith("---"):
                    self.drop_indicator_line = item
                    
                    # Get item rectangle
                    rect = self.elements_list.GetItemRect(item)
                    
                    # Draw drop indicator line
                    dc = wx.ClientDC(self.elements_list)
                    dc.SetPen(wx.Pen(wx.BLUE, 2))
                    
                    # Draw at top or bottom based on position
                    if pos.y < rect.y + rect.height/2:
                        # Draw at top
                        dc.DrawLine(rect.x, rect.y, rect.x + rect.width, rect.y)
                    else:
                        # Draw at bottom
                        dc.DrawLine(rect.x, rect.y + rect.height, 
                                   rect.x + rect.width, rect.y + rect.height)
        
        event.Skip()
    
    def on_element_left_up(self, event):
        """Handle mouse button up to complete drag operation"""
        if self.dragging and self.drag_item_index is not None:
            # Find drop target
            pos = event.GetPosition()
            drop_item, flags = self.elements_list.HitTest(pos)
            
            if drop_item != -1 and drop_item != self.drag_item_index:
                # Get destination item data
                if self.drag_group:
                    # Moving a group
                    self.move_group(self.drag_group_name, drop_item)
                else:
                    # Moving an element - get actual item data index
                    src_data_idx = self.elements_list.GetItemData(self.drag_item_index)
                    if src_data_idx != -1:  # Only move real elements, not separators
                        self.move_element(self.drag_item_index, drop_item)
            
            # Reset drag state
            self.end_drag()
            
            # Update the UI
            self.update_elements_list()
            self.profile_editor.mark_profile_changed()
        else:
            # Reset any drag state
            self.end_drag()
            
        event.Skip()
    
    def on_element_leave_window(self, event):
        """Handle mouse leaving the window during drag"""
        self.end_drag()
        event.Skip()
    
    def end_drag(self):
        """Reset all drag-and-drop state"""
        if self.dragging:
            # Setting default cursor
            self.elements_list.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            
            # Clear any highlighting
            if self.drag_item_index is not None:
                self.elements_list.SetItemBackgroundColour(self.drag_item_index, 
                                                          self.elements_list.GetBackgroundColour())
            
            # Clear drop indicator
            if self.drop_indicator_line is not None:
                self.elements_list.RefreshItem(self.drop_indicator_line)
        
        # Reset all drag state
        self.dragging = False
        self.drag_start_pos = None
        self.drag_item_index = None
        self.drag_group = False
        self.drop_indicator_line = None
        if hasattr(self, 'drag_group_name'):
            delattr(self, 'drag_group_name')
    
    def move_element(self, src_list_idx, dst_list_idx):
        """Move an element in the UI elements list"""
        if not self.menu_data or "items" not in self.menu_data:
            return False
            
        # Convert list indices to data indices
        src_data_idx = self.elements_list.GetItemData(src_list_idx)
        if src_data_idx == -1:  # Not a real element
            return False
            
        # Check destination - if it's a group header, find first item in that group
        dst_text = self.elements_list.GetItemText(dst_list_idx)
        dst_data_idx = self.elements_list.GetItemData(dst_list_idx)
        
        if dst_text.startswith("---"):  # It's a group header
            # Extract group name from the header text
            dst_group = dst_text.strip("-").strip()
            
            # Change element's group membership
            element = self.menu_data["items"][src_data_idx]
            if len(element) <= 5:
                element.append(dst_group)
            else:
                element[5] = dst_group
                
            return True
        elif dst_data_idx == -1:  # It's a separator or other non-element
            # Find next valid element
            found_idx = None
            for i in range(dst_list_idx + 1, self.elements_list.GetItemCount()):
                idx = self.elements_list.GetItemData(i)
                if idx != -1:
                    found_idx = idx
                    break
            
            if found_idx is None:
                # Try previous element
                for i in range(dst_list_idx - 1, -1, -1):
                    idx = self.elements_list.GetItemData(i)
                    if idx != -1:
                        found_idx = idx
                        break
            
            if found_idx is None:
                return False  # No valid target found
                
            dst_data_idx = found_idx
        
        # Move the element in the data
        element = self.menu_data["items"].pop(src_data_idx)
        
        # If destination comes after source in the original array, adjust index
        if dst_data_idx > src_data_idx:
            dst_data_idx -= 1
            
        # Find group of destination
        dst_element = self.menu_data["items"][dst_data_idx]
        dst_group = dst_element[5] if len(dst_element) > 5 else "default"
        
        # Change group if needed
        src_group = element[5] if len(element) > 5 else "default"
        if src_group != dst_group:
            if len(element) <= 5:
                element.append(dst_group)
            else:
                element[5] = dst_group
        
        # Insert at destination
        self.menu_data["items"].insert(dst_data_idx, element)
        return True
    
    def move_group(self, group_name, dst_list_idx):
        """Move a group in the UI elements list"""
        if not self.menu_data or "items" not in self.menu_data:
            return False
            
        # Find all elements in the source group
        src_elements = []
        src_indices = []
        
        for i, element in enumerate(self.menu_data["items"]):
            element_group = element[5] if len(element) > 5 else "default"
            if element_group == group_name:
                src_elements.append(copy.deepcopy(element))
                src_indices.append(i)
        
        if not src_elements:
            return False  # Nothing to move
        
        # Determine destination group
        dst_group = None
        
        # Check if the destination is a group header
        dst_text = self.elements_list.GetItemText(dst_list_idx)
        if dst_text.startswith("---"):
            # It's a group header - extract group name
            dst_group = dst_text.strip("-").strip()
        else:
            # It's an element or separator - find its group
            dst_data_idx = self.elements_list.GetItemData(dst_list_idx)
            if dst_data_idx != -1:
                # It's a real element - get its group
                dst_element = self.menu_data["items"][dst_data_idx]
                dst_group = dst_element[5] if len(dst_element) > 5 else "default"
            else:
                # Find next group
                for i in range(dst_list_idx, self.elements_list.GetItemCount()):
                    text = self.elements_list.GetItemText(i)
                    if text.startswith("---"):
                        dst_group = text.strip("-").strip()
                        break
                
                if dst_group is None:
                    # Find previous group
                    for i in range(dst_list_idx, -1, -1):
                        text = self.elements_list.GetItemText(i)
                        if text.startswith("---"):
                            dst_group = text.strip("-").strip()
                            break
        
        if dst_group is None or dst_group == group_name:
            return False  # No valid target found or same group
        
        # Find all elements in the destination group
        dst_indices = []
        for i, element in enumerate(self.menu_data["items"]):
            element_group = element[5] if len(element) > 5 else "default"
            if element_group == dst_group:
                dst_indices.append(i)
        
        if not dst_indices:
            # Destination group is empty - just add at the end
            # First remove source elements (in reverse order)
            for idx in sorted(src_indices, reverse=True):
                self.menu_data["items"].pop(idx)
            
            # Add to the end
            for element in src_elements:
                self.menu_data["items"].append(element)
        else:
            # Destination group exists - insert before the first element of that group
            dst_idx = min(dst_indices)
            
            # First remove source elements (in reverse order)
            for idx in sorted(src_indices, reverse=True):
                self.menu_data["items"].pop(idx)
                if idx < dst_idx:
                    dst_idx -= 1
            
            # Insert at destination
            for i, element in enumerate(src_elements):
                self.menu_data["items"].insert(dst_idx + i, element)
        
        return True
    
    def get_all_groups(self):
        """Get all groups used in this menu - always fresh from element data"""
        groups = set(["default"])
        
        if "items" in self.menu_data:
            for item in self.menu_data["items"]:
                if len(item) > 5 and item[5]:
                    groups.add(item[5])
        
        return sorted(list(groups))
    
    def on_manage_groups(self, event):
        """Open the group manager dialog"""
        dialog = GroupManagerDialog(self, self.menu_data)
        result = dialog.ShowModal()
        
        if result == wx.ID_OK:
            # The immediate refresh happens in the dialog methods directly
            # Mark profile as changed
            self.profile_editor.mark_profile_changed()
        
        dialog.Destroy()
    
    def refresh_entire_panel(self):
        """Completely refresh the entire panel and all its components"""
        print("Complete panel refresh triggered!")
        
        # 1. Update the reset_group options in menu properties
        self.update_reset_group_options()
        
        # 2. Completely rebuild the group filter dropdown with fresh data
        self.rebuild_group_filter()
        
        # 3. Force a complete refresh of the elements list
        self.update_elements_list()
        
        # 4. Force a complete refresh of the conditions list
        self.update_conditions_list()
        
        # 5. Force a layout refresh to ensure everything is properly sized
        self.Layout()
        self.Refresh()
    
    def rebuild_group_filter(self):
        """Completely rebuild the group filter dropdown with fresh data"""
        # Remember what was selected before
        old_selection = self.group_filter.GetSelection()
        old_group = None
        if old_selection != wx.NOT_FOUND:
            old_group = self.group_filter.GetString(old_selection)
        
        # Get fresh group data
        fresh_groups = self.get_all_groups()
        
        # Rebuild the dropdown
        self.group_filter.Clear()
        self.group_filter.Append("All Groups")
        for group in fresh_groups:
            self.group_filter.Append(group)
        
        # Try to restore selection
        if old_group:
            new_index = self.group_filter.FindString(old_group)
            if new_index != wx.NOT_FOUND:
                self.group_filter.SetSelection(new_index)
            else:
                # If the group was renamed, just select "All Groups"
                self.group_filter.SetSelection(0)
        else:
            self.group_filter.SetSelection(0)
    
    def on_group_filter_changed(self, event):
        """Handle group filter dropdown change"""
        # Force a complete refresh of the elements list
        self.update_elements_list()
    
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
        # Handle Ctrl+A (select all)
        elif is_ctrl and key_code == ord('A'):
            self.select_all_conditions()
        # Handle Delete key
        elif key_code == wx.WXK_DELETE:
            self.on_delete_condition(None)
        else:
            event.Skip()  # Let other handlers process this event
    
    def select_all_conditions(self):
        """Select all conditions in the list"""
        for i in range(self.conditions_list.GetItemCount()):
            self.conditions_list.Select(i)
    
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
        # Handle Ctrl+A (select all)
        elif is_ctrl and key_code == ord('A'):
            self.select_all_elements()
        # Handle Delete key
        elif key_code == wx.WXK_DELETE:
            self.on_delete_element(None)
        else:
            event.Skip()  # Let other handlers process this event
    
    def select_all_elements(self):
        """Select all elements in the list"""
        for i in range(self.elements_list.GetItemCount()):
            # Only select actual elements (not group headers or separators)
            # Now checking for item data != -1 instead of is not None
            item_data = self.elements_list.GetItemData(i)
            if item_data != -1:
                self.elements_list.Select(i)
    
    def on_key_down(self, event):
        """Handle keyboard shortcuts in the menu panel"""
        # Let the event propagate to the focused control
        event.Skip()
    
    def on_condition_dclick(self, event):
        """Handle double-click on a condition item"""
        self.on_edit_condition(event)
    
    def on_element_dclick(self, event):
        """Handle double-click on an element item"""
        # We want to distinguish between drag operations and double-clicks
        # If we're in the middle of a drag operation, don't trigger edit
        if self.dragging:
            return
            
        self.on_edit_element(event)
    
    def update_reset_group_options(self):
        """Update the available groups in the reset_group dropdown"""
        # Collect all unique group values from items
        groups = self.get_all_groups()
        
        # Remember current value
        current_value = self.reset_group_ctrl.GetValue()
        
        # Update control
        self.reset_group_ctrl.Clear()
        self.reset_group_ctrl.AppendItems(groups)
        
        # Restore current value if still valid
        if current_value in groups:
            self.reset_group_ctrl.SetValue(current_value)
        else:
            self.reset_group_ctrl.SetValue("default")
    
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
        
        # Get current group filter
        filter_idx = self.group_filter.GetSelection()
        if filter_idx <= 0:  # "All Groups" or invalid selection
            selected_group = None
        else:
            selected_group = self.group_filter.GetString(filter_idx)
        
        # Sort items by group for grouped display
        sorted_items = []
        if "items" in self.menu_data:
            for i, element in enumerate(self.menu_data["items"]):
                # Get the group (default to "default" if not present)
                group = element[5] if len(element) > 5 else "default"
                # Only include items matching the filter, if one is selected
                if selected_group is None or group == selected_group:
                    sorted_items.append((i, element, group))
        
        # Sort by group
        sorted_items.sort(key=lambda x: x[2])
        
        # Add items to the list
        current_group = None
        list_idx = 0
        
        for orig_idx, element, group in sorted_items:
            # Add group header if this is a new group
            if current_group != group:
                if list_idx > 0:  # Add separator if not the first group
                    separator_idx = self.elements_list.InsertItem(list_idx, "")
                    # Use -1 for separators as a special marker
                    self.elements_list.SetItemData(separator_idx, -1)
                    list_idx += 1
                
                # Add group header - using a different format to make it clearer
                header_text = f"--- {group} ---"  # Clearer visual indicator
                header_idx = self.elements_list.InsertItem(list_idx, header_text)
                # Make group header visually distinct but not like a button
                self.elements_list.SetItemTextColour(header_idx, wx.Colour(0, 0, 128))  # Dark blue
                self.elements_list.SetItemBackgroundColour(header_idx, wx.Colour(200, 220, 255))  # Light blue background
                self.elements_list.SetItemFont(header_idx, wx.Font(wx.NORMAL_FONT.GetPointSize(), wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                # Use -1 for headers as a special marker
                self.elements_list.SetItemData(header_idx, -1)
                current_group = group
                list_idx += 1
            
            # Add the element
            idx = self.elements_list.InsertItem(list_idx, element[1])  # Name
            self.elements_list.SetItem(idx, 1, element[2])      # Type
            self.elements_list.SetItem(idx, 2, f"({element[0][0]}, {element[0][1]})")  # Position
            self.elements_list.SetItem(idx, 3, group)  # Group
            self.elements_list.SetItem(idx, 4, str(element[4] or ""))  # Submenu
            
            # Check for OCR regions
            has_ocr = len(element) > 6 and element[6]
            ocr_count = len(element[6]) if has_ocr else 0
            self.elements_list.SetItem(idx, 5, str(ocr_count) if ocr_count else "")
            
            # Check for custom announcement format
            has_custom_format = len(element) > 7 and element[7]
            self.elements_list.SetItem(idx, 6, "Yes" if has_custom_format else "")
            
            # Store the original index for this item
            self.elements_list.SetItemData(idx, orig_idx)
            
            list_idx += 1
        
        # End any drag operation in progress
        self.end_drag()
    
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
        selected_count = self.conditions_list.GetSelectedItemCount()
        if selected_count == 0:
            return
            
        menu = wx.Menu()
        
        # Show appropriate edit option based on selection count 
        if selected_count == 1:
            edit_item = menu.Append(wx.ID_ANY, "Edit Condition")
            self.Bind(wx.EVT_MENU, self.on_edit_condition, edit_item)
        else:
            edit_item = menu.Append(wx.ID_ANY, f"Edit {selected_count} Conditions...")
            self.Bind(wx.EVT_MENU, self.on_bulk_edit_conditions, edit_item)
            
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
            
            # Refresh everything to ensure consistency
            self.refresh_entire_panel()
            self.profile_editor.mark_profile_changed()
            
        dialog.Destroy()
    
    def on_element_context_menu(self, event):
        """Show context menu for elements list"""
        selected_count = self.elements_list.GetSelectedItemCount()
        if selected_count == 0:
            return
            
        # Check if any of the selected items are group headers or separators
        has_non_elements = False
        item = self.elements_list.GetFirstSelected()
        while item != -1:
            # Check for special marker -1 instead of None
            if self.elements_list.GetItemData(item) == -1:
                has_non_elements = True
                break
            item = self.elements_list.GetNextSelected(item)
        
        if has_non_elements:
            return  # Don't show context menu for headers/separators
            
        menu = wx.Menu()
        
        # Show appropriate edit option based on selection count
        if selected_count == 1:
            edit_item = menu.Append(wx.ID_ANY, "Edit Element")
            self.Bind(wx.EVT_MENU, self.on_edit_element, edit_item)
        else:
            edit_item = menu.Append(wx.ID_ANY, f"Edit {selected_count} Elements...")
            self.Bind(wx.EVT_MENU, self.on_bulk_edit_elements, edit_item)
            
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
            # Skip group headers and separators (data == -1)
            item_data = self.elements_list.GetItemData(item)
            if item_data != -1:
                selected_items.append(item_data)
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
        
        # Refresh everything to ensure consistency
        self.refresh_entire_panel()
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
        selected_item = self.elements_list.GetFirstSelected()
        if selected_item == -1:
            return
        
        # Get the original index stored in item data
        orig_idx = self.elements_list.GetItemData(selected_item)
        # Check for -1 (header or separator) instead of checking for None or 0
        if orig_idx == -1:
            return  # Skip group headers and separators
            
        element = self.menu_data["items"][orig_idx]
        
        dialog = UIElementDialog(self, title="Edit UI Element", element=element)
        if dialog.ShowModal() == wx.ID_OK:
            edited_element = dialog.get_element()
            self.menu_data["items"][orig_idx] = edited_element
            
            # Refresh everything to ensure consistency
            self.refresh_entire_panel()
            self.profile_editor.mark_profile_changed()
            
        dialog.Destroy()
    
    def on_delete_element(self, event):
        """Delete the selected element(s)"""
        if self.elements_list.GetSelectedItemCount() == 0:
            return
        
        # Get all selected indices
        selected_indices = []
        item = self.elements_list.GetFirstSelected()
        while item != -1:
            # Only include actual elements (with item data)
            item_data = self.elements_list.GetItemData(item)
            if item_data != -1:
                selected_indices.append(item_data)
            item = self.elements_list.GetNextSelected(item)
        
        if not selected_indices:
            return
            
        # Sort in reverse order to avoid index shifting
        selected_indices.sort(reverse=True)
        
        # Confirm deletion
        if len(selected_indices) == 1:
            prompt = "Are you sure you want to delete this element?"
        else:
            prompt = f"Are you sure you want to delete these {len(selected_indices)} elements?"
            
        if wx.MessageBox(prompt, "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        
        # Delete each selected item with safety check
        items_deleted = 0
        for idx in selected_indices:
            # Add safety check to ensure index is valid
            if 0 <= idx < len(self.menu_data["items"]):
                del self.menu_data["items"][idx]
                items_deleted += 1
            else:
                print(f"Skipping invalid index: {idx}, items length: {len(self.menu_data['items'])}")
        
        # Refresh everything to ensure consistency
        self.refresh_entire_panel()
        self.profile_editor.mark_profile_changed()
        
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            if items_deleted == 1:
                parent_frame.SetStatusText(f"Deleted 1 element")
            else:
                parent_frame.SetStatusText(f"Deleted {items_deleted} elements")
        except:
            pass
    
    def on_save(self):
        """Save any current state changes to menu_data"""
        # Ensure the reset_index value is saved in menu_data
        self.menu_data["reset_index"] = self.reset_index_cb.GetValue()
        
        # Save the reset_group value
        self.menu_data["reset_group"] = self.reset_group_ctrl.GetValue()
        
        return True
        
    def on_delete_menu(self, event):
        """Delete this entire menu"""
        if wx.MessageBox(f"Are you sure you want to delete the menu '{self.menu_id}'?", 
                       "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.profile_editor.delete_menu(self.menu_id)
    
    def on_bulk_edit_elements(self, event):
        """Edit properties for multiple selected elements at once"""
        # Get all selected indices
        selected_indices = []
        item = self.elements_list.GetFirstSelected()
        while item != -1:
            # Only include actual elements (with item data)
            item_data = self.elements_list.GetItemData(item)
            if item_data != -1:
                selected_indices.append(item_data)
            item = self.elements_list.GetNextSelected(item)
        
        if not selected_indices:
            return
            
        # Get existing groups to populate dropdown
        groups = set(["default"])
        for item in self.menu_data.get("items", []):
            if len(item) > 5 and item[5]:
                groups.add(item[5])
        
        # Create and show the bulk edit dialog
        dialog = BulkEditElementsDialog(self)
        
        # Update the group choices to include all existing groups
        dialog.group_ctrl.SetItems(sorted(list(groups)))
        
        if dialog.ShowModal() == wx.ID_OK:
            # Get the changes to apply
            changes = dialog.get_bulk_changes()
            
            if not changes:
                dialog.Destroy()
                return  # No changes selected
            
            # Apply changes to all selected elements
            modified = 0
            for idx in selected_indices:
                # Safety check
                if idx >= len(self.menu_data["items"]):
                    continue
                    
                element = self.menu_data["items"][idx]
                
                # Apply type change if specified
                if 'type' in changes:
                    element[2] = changes['type']
                
                # Apply speaks_on_select change if specified
                if 'speaks_on_select' in changes:
                    element[3] = changes['speaks_on_select']
                
                # Apply submenu_id change if specified
                if 'submenu_id' in changes:
                    element[4] = changes['submenu_id']
                
                # Apply group change if specified
                if 'group' in changes:
                    # Ensure element list is long enough
                    while len(element) < 6:
                        element.append(None)
                    element[5] = changes['group']
                
                # Apply clear_announcement change if specified
                if 'clear_announcement' in changes:
                    # Ensure element list is long enough
                    while len(element) < 8:
                        element.append(None)
                    element[7] = None
                    
                # Apply clear_ocr change if specified
                if 'clear_ocr' in changes:
                    # Ensure element list is long enough
                    while len(element) < 7:
                        element.append([])
                    element[6] = []
                
                modified += 1
            
            # Refresh everything to ensure consistency
            self.refresh_entire_panel()
            
            # Mark profile as changed
            self.profile_editor.mark_profile_changed()
            
            # Update status
            try:
                parent_frame = wx.GetTopLevelParent(self.GetParent())
                parent_frame.SetStatusText(f"Applied changes to {modified} elements")
            except:
                pass
        
        dialog.Destroy()
    
    def on_bulk_edit_conditions(self, event):
        """Edit properties for multiple selected conditions at once"""
        # Get all selected indices
        selected_indices = []
        item = self.conditions_list.GetFirstSelected()
        while item != -1:
            selected_indices.append(item)
            item = self.conditions_list.GetNextSelected(item)
        
        if not selected_indices:
            return
        
        # Collect conditions for editing
        pixel_color_indices = []
        region_color_indices = []
        
        for idx in selected_indices:
            condition = self.menu_data["conditions"][idx]
            condition_type = condition.get("type")
            
            if condition_type == "pixel_color":
                pixel_color_indices.append(idx)
            elif condition_type == "pixel_region_color":
                region_color_indices.append(idx)
        
        # Check if we have any compatible conditions
        if not pixel_color_indices and not region_color_indices:
            wx.MessageBox("No compatible conditions selected for bulk editing.", 
                         "Bulk Edit", wx.ICON_INFORMATION)
            return
            
        # Create and show the bulk edit dialog
        dialog = BulkEditConditionsDialog(self)
        
        if dialog.ShowModal() == wx.ID_OK:
            # Get the changes to apply
            changes = dialog.get_bulk_changes()
            
            if not changes:
                dialog.Destroy()
                return  # No changes selected
            
            # Apply changes to all selected compatible conditions
            modified = 0
            
            # Apply to pixel color conditions
            for idx in pixel_color_indices:
                condition = self.menu_data["conditions"][idx]
                
                # Apply color change if specified
                if 'color' in changes:
                    condition['color'] = changes['color']
                
                # Apply tolerance change if specified
                if 'tolerance' in changes:
                    condition['tolerance'] = changes['tolerance']
                
                modified += 1
            
            # Apply to region color conditions 
            for idx in region_color_indices:
                condition = self.menu_data["conditions"][idx]
                
                # Apply color change if specified
                if 'color' in changes:
                    condition['color'] = changes['color']
                
                # Apply tolerance change if specified
                if 'tolerance' in changes:
                    condition['tolerance'] = changes['tolerance']
                
                modified += 1
            
            # Update the conditions list
            self.update_conditions_list()
            
            # Mark profile as changed
            self.profile_editor.mark_profile_changed()
            
            # Update status
            try:
                parent_frame = wx.GetTopLevelParent(self.GetParent())
                parent_frame.SetStatusText(f"Applied changes to {modified} conditions")
            except:
                pass
        
        dialog.Destroy()
    
    def on_reset_index_changed(self, event):
        """Handle reset_index checkbox state change"""
        # Update the menu_data with the new reset_index value
        self.menu_data["reset_index"] = self.reset_index_cb.GetValue()
        self.profile_editor.mark_profile_changed()
        
        # Update status
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            value = "will reset" if self.reset_index_cb.GetValue() else "will maintain"
            parent_frame.SetStatusText(f"Menu '{self.menu_id}' {value} selection index when entered")
        except:
            pass