"""
Menu panel for editing menu data with improved drag and drop
"""

import wx
import wx.lib.scrolledpanel as scrolled
import copy

from pflib.dialogs import (
    PixelColorConditionDialog, 
    RegionColorConditionDialog, 
    UIElementDialog,
    RegionImageConditionDialog, # Added in a previous step, ensure it's here
    OCRConditionDialog # New dialog for OCR condition
)
from pflib.bulk_edit_dialog import BulkEditElementsDialog
from pflib.condition_bulk_edit import BulkEditConditionsDialog

class GroupManagerDialog(wx.Dialog):
    """Dialog for managing element groups in a menu, with ordering support"""
    
    def __init__(self, parent, menu_data):
        super().__init__(parent, title="Group Manager", size=(500, 500))
        
        self.menu_data = menu_data
        # Store parent for immediate refresh
        self.menu_panel = parent
        
        # Collect all existing groups and their lowest element index
        self.groups = {"default": 0}  # Default group always starts with index 0
        if "items" in self.menu_data:
            for item in self.menu_data["items"]:
                if len(item) > 5 and item[5]:
                    group_name = item[5]
                    group_index = item[8] if len(item) > 8 else 0
                    
                    # Track the lowest index for each group
                    if group_name not in self.groups or group_index < self.groups[group_name]:
                        self.groups[group_name] = group_index
        
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Instructions
        instructions = wx.StaticText(panel, label="Manage element groups in this menu:")
        main_sizer.Add(instructions, flag=wx.ALL | wx.EXPAND, border=10)
        
        # Group list
        list_label = wx.StaticText(panel, label="Groups (drag to reorder):")
        main_sizer.Add(list_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        
        # Use a ListCtrl instead of ListBox to support drag and drop and showing indices
        self.group_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 250))
        self.group_list.InsertColumn(0, "Group Name", width=250)
        self.group_list.InsertColumn(1, "Index", width=60)
        self.group_list.InsertColumn(2, "Elements", width=70)
        
        # Populate the list with groups sorted by their index
        sorted_groups = sorted(self.groups.items(), key=lambda x: x[1])
        for i, (group_name, group_index) in enumerate(sorted_groups):
            idx = self.group_list.InsertItem(i, group_name)
            self.group_list.SetItem(idx, 1, str(group_index))
            element_count = self.count_elements_in_group(group_name)
            self.group_list.SetItem(idx, 2, str(element_count))
            
        main_sizer.Add(self.group_list, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        
        # Group actions
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.add_btn = wx.Button(panel, label="Add Group")
        self.rename_btn = wx.Button(panel, label="Rename Group")
        self.delete_btn = wx.Button(panel, label="Delete Group")
        self.move_up_btn = wx.Button(panel, label="Move Up")
        self.move_down_btn = wx.Button(panel, label="Move Down")
        
        self.add_btn.Bind(wx.EVT_BUTTON, self.on_add_group)
        self.rename_btn.Bind(wx.EVT_BUTTON, self.on_rename_group)
        self.delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_group)
        self.move_up_btn.Bind(wx.EVT_BUTTON, self.on_move_up)
        self.move_down_btn.Bind(wx.EVT_BUTTON, self.on_move_down)
        
        btn_sizer.Add(self.add_btn, flag=wx.RIGHT, border=5)
        btn_sizer.Add(self.rename_btn, flag=wx.RIGHT, border=5)
        btn_sizer.Add(self.delete_btn, flag=wx.RIGHT, border=5)
        btn_sizer.Add(self.move_up_btn, flag=wx.RIGHT, border=5)
        btn_sizer.Add(self.move_down_btn)
        
        main_sizer.Add(btn_sizer, flag=wx.ALL | wx.ALIGN_CENTER, border=10)
        
        # Manual reordering section
        index_box = wx.StaticBox(panel, label="Manual Group Index")
        index_sizer = wx.StaticBoxSizer(index_box, wx.VERTICAL)
        
        index_help = wx.StaticText(panel, label="Set custom index for the selected group:")
        index_sizer.Add(index_help, flag=wx.ALL, border=5)
        
        index_ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.index_spinner = wx.SpinCtrl(panel, min=0, max=999, value="0")
        set_index_btn = wx.Button(panel, label="Set Index")
        set_index_btn.Bind(wx.EVT_BUTTON, self.on_set_index)
        
        index_ctrl_sizer.Add(self.index_spinner, flag=wx.RIGHT, border=10)
        index_ctrl_sizer.Add(set_index_btn)
        
        index_sizer.Add(index_ctrl_sizer, flag=wx.ALL, border=5)
        
        main_sizer.Add(index_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # OK/Cancel buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        btn_sizer.AddButton(ok_button)
        btn_sizer.AddButton(cancel_button)
        btn_sizer.Realize()
        
        main_sizer.Add(btn_sizer, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
        
        panel.SetSizer(main_sizer)
        
        # Set up drag and drop events for the list
        self.group_list.Bind(wx.EVT_LIST_BEGIN_DRAG, self.on_begin_drag)
        self.group_list.Bind(wx.EVT_MOTION, self.on_motion)
        self.group_list.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.group_list.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave_window)
        
        # Initialize drag variables
        self.drag_item = None
        self.drag_image = None
        self.drop_target = None
        
        # Update button states
        self.update_ui()
        
        # Bind selection event
        self.group_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_group_selected)
        
    def on_group_selected(self, event):
        """Handle group selection"""
        self.update_ui()
        
        # Update index spinner with current group's index
        item = self.group_list.GetFirstSelected()
        if item != -1:
            group_name = self.group_list.GetItemText(item, 0)
            index = int(self.group_list.GetItemText(item, 1))
            self.index_spinner.SetValue(index)
    
    def update_ui(self):
        """Update UI based on current state"""
        selection = self.group_list.GetFirstSelected()
        has_selection = selection != -1
        
        # Update buttons
        self.rename_btn.Enable(has_selection)
        self.delete_btn.Enable(has_selection and self.group_list.GetItemText(selection, 0) != "default")
        self.move_up_btn.Enable(has_selection and selection > 0)
        self.move_down_btn.Enable(has_selection and selection < self.group_list.GetItemCount() - 1)
        
    def count_elements_in_group(self, group_name):
        """Count how many elements are in a specific group"""
        count = 0
        if "items" in self.menu_data:
            for item in self.menu_data["items"]:
                item_group = item[5] if len(item) > 5 else "default"
                if item_group == group_name:
                    count += 1
        return count
    
    def on_begin_drag(self, event):
        """Begin dragging a group item"""
        item = event.GetIndex()
        group_name = self.group_list.GetItemText(item, 0)
        
        # Don't allow dragging the default group
        if group_name == "default":
            return
            
        self.drag_item = item
        
        # Create drag image for visual feedback
        self.drag_image = wx.DragImage(group_name, wx.Icon("", wx.BITMAP_TYPE_ICO))
        self.drag_image.BeginDrag(wx.Point(0, 0), self.group_list, fullScreen=True)
        self.drag_image.Show()
        
    def on_motion(self, event):
        """Handle motion during drag operation"""
        if self.drag_item is not None:
            self.drag_image.Move(wx.GetMousePosition())
            
            # Determine drop target
            position = self.group_list.ScreenToClient(wx.GetMousePosition())
            item, flags = self.group_list.HitTest(position)
            
            # Update drop target indicator
            if item != -1 and item != self.drag_item:
                self.drop_target = item
                
                # Clear any previous selection
                for i in range(self.group_list.GetItemCount()):
                    self.group_list.SetItemBackgroundColour(i, self.group_list.GetBackgroundColour())
                    
                # Highlight drop target
                self.group_list.SetItemBackgroundColour(item, wx.Colour(200, 200, 255))
            elif item == -1 or item == self.drag_item:
                self.drop_target = None
                # Clear all highlighting
                for i in range(self.group_list.GetItemCount()):
                    self.group_list.SetItemBackgroundColour(i, self.group_list.GetBackgroundColour())
    
    def on_left_up(self, event):
        """Handle the end of a drag operation"""
        if self.drag_item is not None:
            # End drag
            self.drag_image.EndDrag()
            self.drag_image = None
            
            # Process drop
            if self.drop_target is not None:
                self.move_group(self.drag_item, self.drop_target)
            
            # Reset state
            self.drag_item = None
            self.drop_target = None
            
            # Clear all highlighting
            for i in range(self.group_list.GetItemCount()):
                self.group_list.SetItemBackgroundColour(i, self.group_list.GetBackgroundColour())
                
            self.update_ui()
    
    def on_leave_window(self, event):
        """Handle the case where mouse leaves the window during drag"""
        if self.drag_item is not None:
            # End drag
            self.drag_image.EndDrag()
            self.drag_image = None
            
            # Reset state
            self.drag_item = None
            self.drop_target = None
            
            # Clear all highlighting
            for i in range(self.group_list.GetItemCount()):
                self.group_list.SetItemBackgroundColour(i, self.group_list.GetBackgroundColour())
                
            self.update_ui()
            
    def move_group(self, src_idx, dst_idx):
        """Move a group in the order list by changing its index"""
        # Don't allow moving the default group
        src_name = self.group_list.GetItemText(src_idx, 0)
        if src_name == "default":
            return
            
        # Get the target group's index
        dst_name = self.group_list.GetItemText(dst_idx, 0) 
        dst_index = int(self.group_list.GetItemText(dst_idx, 1))
        
        # Calculate a new index for the source group
        if src_idx < dst_idx:
            # Moving down - place after target
            new_index = dst_index + 5
        else:
            # Moving up - place before target
            new_index = max(0, dst_index - 5)
            
        # Update our tracking dictionary
        self.groups[src_name] = new_index
        
        # Update all elements in this group to the new index
        for item in self.menu_data["items"]:
            item_group = item[5] if len(item) > 5 else "default"
            if item_group == src_name:
                # Ensure item has index field
                while len(item) < 9:
                    item.append(0)
                    
                # Update group's base index
                item[8] += new_index
        
        # Re-sort and update the listctrl
        self.update_group_list()
        
        # Set return code to indicate changes were made
        self.SetReturnCode(wx.ID_OK)
            
    def on_add_group(self, event):
        """Add a new group"""
        dialog = wx.TextEntryDialog(self, "Enter new group name:", "Add Group")
        if dialog.ShowModal() == wx.ID_OK:
            group_name = dialog.GetValue().strip()
            if group_name:
                if group_name in self.groups:
                    wx.MessageBox(f"Group '{group_name}' already exists", "Duplicate Group", wx.ICON_ERROR)
                else:
                    # Find the highest index and add 10
                    highest_index = max(self.groups.values() if self.groups else [0])
                    self.groups[group_name] = highest_index + 10
                    
                    self.update_group_list()
                    
                    # Select the new group
                    for i in range(self.group_list.GetItemCount()):
                        if self.group_list.GetItemText(i, 0) == group_name:
                            self.group_list.Select(i)
                            break
                            
                    self.update_ui()
                    
                    # Set return code and trigger immediate refresh in parent
                    self.SetReturnCode(wx.ID_OK)
                    
                    # CRITICAL: Immediately refresh parent panel
                    wx.CallAfter(self.menu_panel.refresh_entire_panel)
        dialog.Destroy()
    
    def on_rename_group(self, event):
        """Rename the selected group"""
        selection = self.group_list.GetFirstSelected()
        if selection == -1:
            return
            
        old_name = self.group_list.GetItemText(selection, 0)
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
                    for item in self.menu_data["items"]:
                        if len(item) > 5 and item[5] == old_name:
                            item[5] = new_name
                    
                    # Update group list
                    index = self.groups[old_name]
                    del self.groups[old_name]
                    self.groups[new_name] = index
                    self.update_group_list()
                    
                    # Select the renamed group
                    for i in range(self.group_list.GetItemCount()):
                        if self.group_list.GetItemText(i, 0) == new_name:
                            self.group_list.Select(i)
                            break
                            
                    self.update_ui()
                    
                    # Set result to true to indicate changes were made
                    self.SetReturnCode(wx.ID_OK)
                    
                    # CRITICAL: Immediately refresh parent panel
                    wx.CallAfter(self.menu_panel.refresh_entire_panel)
        dialog.Destroy()
    
    def on_delete_group(self, event):
        """Delete the selected group"""
        selection = self.group_list.GetFirstSelected()
        if selection == -1:
            return
            
        group_name = self.group_list.GetItemText(selection, 0)
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
            for item in self.menu_data["items"]:
                if len(item) > 5 and item[5] == group_name:
                    item[5] = "default"
        
        # Remove the group
        del self.groups[group_name]
        self.update_group_list()
        
        # Clear selection
        self.group_list.Select(-1)
        self.update_ui()
        
        # Set result to true to indicate changes were made
        self.SetReturnCode(wx.ID_OK)
        
        # CRITICAL: Immediately refresh parent panel
        wx.CallAfter(self.menu_panel.refresh_entire_panel)
    
    def on_move_up(self, event):
        """Move the selected group up in the order"""
        selection = self.group_list.GetFirstSelected()
        if selection <= 0:  # Can't move up if already at top
            return
            
        # Move by swapping with the previous item
        self.move_group(selection, selection - 1)
        
    def on_move_down(self, event):
        """Move the selected group down in the order"""
        selection = self.group_list.GetFirstSelected()
        if selection == -1 or selection >= self.group_list.GetItemCount() - 1:
            return  # Can't move down if already at bottom
            
        # Move by swapping with the next item
        self.move_group(selection, selection + 1)
    
    def on_set_index(self, event):
        """Set a custom index for the selected group"""
        selection = self.group_list.GetFirstSelected()
        if selection == -1:
            return
            
        group_name = self.group_list.GetItemText(selection, 0)
        new_index = self.index_spinner.GetValue()
        
        # Check if this would create any duplicates
        if any(idx == new_index for grp, idx in self.groups.items() if grp != group_name):
            # Ask if we should adjust other indices
            if wx.MessageBox(f"Another group already has index {new_index}. Adjust other indices?", 
                           "Index Conflict", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                # Shift other groups to make room
                for grp in self.groups:
                    if grp != group_name and self.groups[grp] >= new_index:
                        self.groups[grp] += 10
        
        # Update the group's index
        old_index = self.groups[group_name]
        self.groups[group_name] = new_index
        
        # Update all elements in this group
        for item in self.menu_data["items"]:
            item_group = item[5] if len(item) > 5 else "default"
            if item_group == group_name:
                # Ensure item has index field
                while len(item) < 9:
                    item.append(0)
                
                # Adjust the item's index by the difference
                item_index = item[8]
                if item_index >= old_index:
                    # Only adjust item indices that were based on the old group index
                    offset = item_index - old_index
                    item[8] = new_index + offset
        
        # Update the list control
        self.update_group_list()
        
        # Set return code and refresh parent
        self.SetReturnCode(wx.ID_OK)
        wx.CallAfter(self.menu_panel.refresh_entire_panel)
    
    def update_group_list(self):
        """Update the group list control with current data"""
        # Remember the current selection
        selection = self.group_list.GetFirstSelected()
        selected_group = None
        if selection != -1:
            selected_group = self.group_list.GetItemText(selection, 0)
        
        # Clear the list
        self.group_list.DeleteAllItems()
        
        # Resort groups by index
        sorted_groups = sorted(self.groups.items(), key=lambda x: x[1])
        
        # Repopulate the list
        for i, (group_name, group_index) in enumerate(sorted_groups):
            idx = self.group_list.InsertItem(i, group_name)
            self.group_list.SetItem(idx, 1, str(group_index))
            element_count = self.count_elements_in_group(group_name)
            self.group_list.SetItem(idx, 2, str(element_count))
            
            # Restore selection
            if group_name == selected_group:
                self.group_list.Select(idx)
        
        # Update UI state
        self.update_ui()


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
        self.drag_item_index = -1 # Use -1 to indicate no item
        self.drag_group = False
        self.drop_indicator_line = None
        self.potential_drag_item_index = -1 # Item potentially being dragged
        self.potential_drag_group = False   # If the potential item is a group header
        
        # Set minimum size to prevent squishing
        self.SetMinSize((750, 600))  # ADDED: Set minimum panel size
        
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
        self.reset_index_cb.SetValue(self.menu_data.get("reset_index", True))
        self.reset_index_cb.Bind(wx.EVT_CHECKBOX, self.on_reset_index_changed)
        option_sizer.Add(self.reset_index_cb, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=15)
        
        # Add reset group option
        reset_group_label = wx.StaticText(self, label="Reset to group:")
        standard_groups = ["default"]
        self.reset_group_ctrl = wx.ComboBox(self, choices=standard_groups,
                                            value=self.menu_data.get("reset_group", "default"))
        option_sizer.Add(reset_group_label, flag=wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        option_sizer.Add(self.reset_group_ctrl, proportion=1, flag=wx.RIGHT, border=15) # Added border

        # Manual Menu Checkbox
        self.manual_menu_cb = wx.CheckBox(self, label="Manual Menu (no visual conditions)")
        self.manual_menu_cb.SetValue(self.menu_data.get("is_manual", False))
        self.manual_menu_cb.Bind(wx.EVT_CHECKBOX, self.on_manual_menu_toggled)
        option_sizer.Add(self.manual_menu_cb, flag=wx.ALIGN_CENTER_VERTICAL)
        
        # Add options to header with proportion=1 to make it expand
        header_sizer.Add(option_sizer, proportion=1, flag=wx.LEFT, border=15)
        
        # Buttons in their own sizer
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        duplicate_btn = wx.Button(self, label="Duplicate")
        duplicate_btn.Bind(wx.EVT_BUTTON, self.on_duplicate_menu)
        rename_btn = wx.Button(self, label="Rename")
        rename_btn.Bind(wx.EVT_BUTTON, self.on_rename_menu)
        delete_btn = wx.Button(self, label="Delete")
        delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_menu)
        
        buttons_sizer.Add(duplicate_btn, flag=wx.RIGHT, border=5)
        buttons_sizer.Add(rename_btn, flag=wx.RIGHT, border=5)
        buttons_sizer.Add(delete_btn)
        
        # Add buttons to header without alignment flags
        header_sizer.Add(buttons_sizer, flag=wx.LEFT, border=10)
        
        self.main_sizer.Add(header_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Conditions section
        self.conditions_static_box = wx.StaticBox(self, label="Menu Detection Conditions")
        self.conditions_sizer = wx.StaticBoxSizer(self.conditions_static_box, wx.VERTICAL)
        
        # Conditions logic choice (AND/OR)
        logic_sizer = wx.BoxSizer(wx.HORIZONTAL)
        logic_label = wx.StaticText(self, label="Conditions Logic:")
        self.conditions_logic_combo = wx.ComboBox(self, choices=["AND", "OR"],
                                                 value=self.menu_data.get("conditions_logic", "AND"),
                                                 style=wx.CB_READONLY)
        self.conditions_logic_combo.Bind(wx.EVT_COMBOBOX, self.on_conditions_logic_changed)
        
        logic_sizer.Add(logic_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        logic_sizer.Add(self.conditions_logic_combo, flag=wx.ALIGN_CENTER_VERTICAL)
        conditions_sizer.Add(logic_sizer, flag=wx.ALL | wx.EXPAND, border=5)
        
        # Add condition buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)  # UPDATED: Changed to simple horizontal BoxSizer
        
        add_pixel_btn = wx.Button(self, label="Add Pixel Color")
        add_pixel_btn.Bind(wx.EVT_BUTTON, self.on_add_pixel_condition)
        btn_sizer.Add(add_pixel_btn, flag=wx.RIGHT, border=5)
        
        add_region_btn = wx.Button(self, label="Add Region Color")
        add_region_btn.Bind(wx.EVT_BUTTON, self.on_add_region_condition)
        btn_sizer.Add(add_region_btn, flag=wx.RIGHT, border=5)
        
        # Add new button for image region condition
        add_region_image_btn = wx.Button(self, label="Add Region Image")
        add_region_image_btn.Bind(wx.EVT_BUTTON, self.on_add_region_image_condition)
        btn_sizer.Add(add_region_image_btn, flag=wx.RIGHT, border=5)

        add_ocr_condition_btn = wx.Button(self, label="Add OCR Condition")
        add_ocr_condition_btn.Bind(wx.EVT_BUTTON, self.on_add_ocr_condition)
        btn_sizer.Add(add_ocr_condition_btn, flag=wx.RIGHT, border=5)
        
        paste_condition_btn = wx.Button(self, label="Paste Condition(s)")
        paste_condition_btn.Bind(wx.EVT_BUTTON, self.on_paste_condition)
        btn_sizer.Add(paste_condition_btn, proportion=1, flag=wx.EXPAND)  # UPDATED: Added proportion and expand
        
        conditions_sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=5)  # ADDED: Added to sizer
        
        # Conditions list - using just wx.LC_REPORT since multi-select is default
        # Make sure it's resizable by adding proportion=1
        self.conditions_list = wx.ListCtrl(self, style=wx.LC_REPORT, size=(-1, 150))
        self.conditions_list.InsertColumn(0, "Type", width=120)
        self.conditions_list.InsertColumn(1, "Details", width=400)
        
        # Populate conditions
        self.update_conditions_list()
        
        # Context menu for conditions
        self.conditions_list.Bind(wx.EVT_CONTEXT_MENU, self.on_condition_context_menu)
        
        # Add double-click for editing conditions
        self.conditions_list.Bind(wx.EVT_LEFT_DCLICK, self.on_condition_dclick)
        
        # Install key event handlers for the list
        self.conditions_list.Bind(wx.EVT_KEY_DOWN, self.on_conditions_key)
        
        self.conditions_sizer.Add(self.conditions_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        self.main_sizer.Add(self.conditions_sizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Set initial state of conditions section based on is_manual
        self._update_conditions_section_state()
        
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
        element_btn_sizer.Add(paste_element_btn, proportion=1, flag=wx.EXPAND)  # UPDATED: Added proportion
        elements_sizer.Add(element_btn_sizer, flag=wx.EXPAND | wx.ALL, border=5)
        
        # Elements list - with wider columns and drag-and-drop support
        # Removed wx.LC_SINGLE_SEL to enable multi-select
        self.elements_list = wx.ListCtrl(self, style=wx.LC_REPORT, size=(-1, 250))  # UPDATED: Increased height
        self.elements_list.InsertColumn(0, "Name", width=180)
        self.elements_list.InsertColumn(1, "Type", width=100)
        self.elements_list.InsertColumn(2, "Position", width=90)
        self.elements_list.InsertColumn(3, "Group", width=100)
        self.elements_list.InsertColumn(4, "Submenu", width=100)
        self.elements_list.InsertColumn(5, "OCR", width=60)
        self.elements_list.InsertColumn(6, "Custom Format", width=100)
        self.elements_list.InsertColumn(7, "Index", width=60)
        self.elements_list.InsertColumn(8, "Conditions", width=80)
        
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
        
        elements_sizer.Add(self.elements_list, proportion=2, flag=wx.EXPAND | wx.ALL, border=5)  # UPDATED: Increased proportion
        
        # Add drag and drop help text
        drag_help = wx.StaticText(self, label="Tip: Drag elements or group headers to rearrange them")
        drag_help.SetForegroundColour(wx.Colour(100, 100, 100))  # Gray text
        elements_sizer.Add(drag_help, flag=wx.ALL, border=5)
        
        self.main_sizer.Add(elements_sizer, proportion=2, flag=wx.EXPAND | wx.ALL, border=10)
        
        self.SetSizer(self.main_sizer)
        
        # Force proper layout before finishing
        self.main_sizer.Fit(self)
        self.Layout()

    def on_manual_menu_toggled(self, event):
        """Handle toggling the 'Manual Menu' checkbox."""
        is_manual = self.manual_menu_cb.GetValue()
        self.menu_data["is_manual"] = is_manual
        self.profile_editor.mark_profile_changed()
        self._update_conditions_section_state()

    def _update_conditions_section_state(self):
        """Enable/disable the conditions section based on the 'is_manual' flag."""
        is_manual = self.menu_data.get("is_manual", False)
        enable_conditions = not is_manual

        # Disable/Enable the StaticBox itself (visual cue)
        self.conditions_static_box.Enable(enable_conditions)

        # Explicitly enable/disable controls within the conditions sizer
        # This is often more reliable for ensuring all controls are affected.
        self.conditions_logic_combo.Enable(enable_conditions)
        
        # Iterate over buttons in btn_sizer (assuming it's stored or accessible)
        # Assuming self.add_pixel_btn, self.add_region_btn etc. are direct children for simplicity here.
        # A more robust way would be to iterate sizer items if they are not instance attributes.
        
        # Find the button sizer within conditions_sizer
        # This assumes a certain structure, might need adjustment if layout changes
        condition_buttons_sizer = None
        for item in self.conditions_sizer.GetChildren():
            sizer = item.GetSizer()
            if sizer and isinstance(sizer, wx.BoxSizer): # Check if it's the horizontal sizer for buttons
                 # Crude check, might need to be more specific if other BoxSizers are added
                is_button_sizer = False
                for s_item in sizer.GetChildren():
                    if s_item.IsWindow() and isinstance(s_item.GetWindow(), wx.Button):
                        is_button_sizer = True
                        break
                if is_button_sizer:
                    condition_buttons_sizer = sizer
                    break
        
        if condition_buttons_sizer:
            for item in condition_buttons_sizer.GetChildren():
                window = item.GetWindow()
                if window: # Check if it's a window (control)
                    window.Enable(enable_conditions)

        self.conditions_list.Enable(enable_conditions)
        
        # Refresh to reflect visual changes
        self.conditions_static_box.Refresh()
        # self.Layout() # May not be needed if only enabling/disabling

    def on_add_ocr_condition(self, event):
        """Add a new OCR text present condition"""
        dialog = OCRConditionDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            condition = dialog.get_condition()
            
            if "conditions" not in self.menu_data:
                self.menu_data["conditions"] = []
                
            self.menu_data["conditions"].append(condition)
            self.update_conditions_list()
            self.profile_editor.mark_profile_changed()
            
        dialog.Destroy()

    def on_conditions_logic_changed(self, event):
        """Handle changes in the conditions logic ComboBox"""
        selected_logic = self.conditions_logic_combo.GetValue()
        self.menu_data["conditions_logic"] = selected_logic
        self.profile_editor.mark_profile_changed()
        
        # Update status bar or provide some feedback
        try:
            parent_frame = wx.GetTopLevelParent(self.GetParent())
            parent_frame.SetStatusText(f"Menu '{self.menu_id}' conditions logic set to {selected_logic}")
        except Exception as e:
            print(f"Error updating status text for conditions_logic: {e}") # Fallback logging

    def on_add_region_image_condition(self, event):
        """Add a new region image condition"""
        from pflib.dialogs import RegionImageConditionDialog
        
        dialog = RegionImageConditionDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            condition = dialog.get_condition()
            
            if "conditions" not in self.menu_data:
                self.menu_data["conditions"] = []
                
            self.menu_data["conditions"].append(condition)
            self.update_conditions_list()
            self.profile_editor.mark_profile_changed()
            
        dialog.Destroy()
    
    # Drag and drop implementation for elements list
    def on_element_left_down(self, event):
        """Start drag operation on left mouse button down"""
        # Get the item under cursor
        item_idx, flags = self.elements_list.HitTest(event.GetPosition())

        if item_idx != -1: # Click was on an item
            self.drag_start_pos = event.GetPosition()
            self.potential_drag_item_index = item_idx

            text = self.elements_list.GetItemText(item_idx)
            if text.startswith("---") and text.endswith("---"): # Group header
                self.potential_drag_group = True
                if hasattr(self, 'potential_drag_group_name'): # Clear previous if any
                    delattr(self, 'potential_drag_group_name')
                self.potential_drag_group_name = text.strip("-").strip()
            else: # Regular item or separator
                self.potential_drag_group = False
                data_idx = self.elements_list.GetItemData(item_idx)
                if data_idx == -1: # Separator
                    self.potential_drag_item_index = -1 # Cannot drag separators
                    self.drag_start_pos = None 
        else: # Click was on empty space
            self.drag_start_pos = None
            self._clear_potential_drag_state()
        
        event.Skip() # IMPORTANT for native selection processing

    def _clear_potential_drag_state(self):
        """Clears variables related to a potential drag operation."""
        self.potential_drag_item_index = -1
        self.potential_drag_group = False
        if hasattr(self, 'potential_drag_group_name'):
            delattr(self, 'potential_drag_group_name')

    def on_element_motion(self, event):
        """Handle mouse motion for drag-and-drop operations"""
        if not event.Dragging() or not self.drag_start_pos or self.potential_drag_item_index == -1:
            self._clear_potential_drag_state()
            event.Skip()
            return
            
        if not self.dragging: # If not already dragging, check if we should start
            start_pos = self.drag_start_pos
            curr_pos = event.GetPosition()
            
            if abs(curr_pos.x - start_pos.x) > 5 or abs(curr_pos.y - start_pos.y) > 5: # Moved enough
                # Check if the potential item is actually selected
                item_to_drag_idx = self.potential_drag_item_index
                
                is_selected = self.elements_list.IsSelected(item_to_drag_idx)
                is_group_header_type = self.potential_drag_group
                data_idx = self.elements_list.GetItemData(item_to_drag_idx)

                # Condition to start drag:
                # 1. It's a group header (potential_drag_group is true) OR
                # 2. It's a regular item (data_idx != -1) AND it's selected.
                if is_group_header_type or (data_idx != -1 and is_selected):
                    self.dragging = True
                    self.drag_item_index = item_to_drag_idx # Commit to this item for dragging
                    
                    if is_group_header_type:
                        self.drag_group = True
                        self.drag_group_name = self.potential_drag_group_name
                    else:
                        self.drag_group = False
                    
                    self.elements_list.SetCursor(wx.Cursor(wx.CURSOR_HAND))
                    self.elements_list.SetItemBackgroundColour(self.drag_item_index, wx.Colour(230, 230, 255))
                else:
                    # Moved enough, but item not selected or not draggable type, so don't start drag.
                    # This allows rubber-band selection to take over.
                    self._clear_potential_drag_state()
                    self.drag_start_pos = None # Crucial: stop considering this a drag start
                    event.Skip() # Allow rubber-band
                    return
        
        if self.dragging:
            pos = event.GetPosition()
            item_hit_idx, flags = self.elements_list.HitTest(pos)
            
            if self.drop_indicator_line is not None:
                # Check if item index is valid before refreshing
                if self.drop_indicator_line < self.elements_list.GetItemCount():
                    self.elements_list.RefreshItem(self.drop_indicator_line)
                self.drop_indicator_line = None
            
            if item_hit_idx != -1 and item_hit_idx != self.drag_item_index:
                data_idx = self.elements_list.GetItemData(item_hit_idx)
                if data_idx != -1 or self.elements_list.GetItemText(item_hit_idx).startswith("---"):
                    self.drop_indicator_line = item_hit_idx
                    rect = self.elements_list.GetItemRect(item_hit_idx)
                    dc = wx.ClientDC(self.elements_list) # Use ClientDC for temporary drawing
                    dc.SetPen(wx.Pen(wx.BLUE, 2))
                    if pos.y < rect.y + rect.height/2:
                        dc.DrawLine(rect.x, rect.y, rect.x + rect.width, rect.y)
                    else:
                        dc.DrawLine(rect.x, rect.y + rect.height, rect.x + rect.width, rect.y + rect.height)
        else: # Not dragging (e.g. rubber-banding)
            event.Skip()

    def on_element_left_up(self, event):
        """Handle mouse button up to complete drag operation or selection."""
        if self.dragging and self.drag_item_index != -1:
            pos = event.GetPosition()
            drop_item_idx, flags = self.elements_list.HitTest(pos)
            
            if drop_item_idx != -1 and drop_item_idx != self.drag_item_index:
                if self.drag_group:
                    self.move_group(self.drag_group_name, drop_item_idx)
                else: # It's a regular element
                    src_data_idx = self.elements_list.GetItemData(self.drag_item_index)
                    if src_data_idx != -1: # Ensure it's a real element
                        self.move_element(self.drag_item_index, drop_item_idx)
            
            self.end_drag()
            self.update_elements_list() # Refresh list after potential reorder
            self.profile_editor.mark_profile_changed()
        else:
            # Not dragging, so this is the end of a click or rubber-band selection.
            # Native control has handled selection if event.Skip() was called correctly.
            self.end_drag() # Clears all drag states including potential ones.
            
        event.Skip() # Allow default processing for selection changes if any

    def on_element_leave_window(self, event):
        """Handle mouse leaving the window during drag"""
        # If a drag operation was truly in progress (self.dragging),
        # it's often best to cancel it or handle it based on application logic.
        # For now, just ending the drag visuals and state.
        if self.dragging:
             self.end_drag() # Full cleanup of an active drag
        else:
            # If only a potential drag was being considered (mouse down but not moved enough)
            self._clear_potential_drag_state()
            self.drag_start_pos = None # Clear this as mouse is up outside
        event.Skip()
    
    def end_drag(self):
        """Reset all drag-and-drop state, including potential drag."""
        if self.dragging:
            self.elements_list.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            if self.drag_item_index != -1 and self.drag_item_index < self.elements_list.GetItemCount():
                self.elements_list.SetItemBackgroundColour(self.drag_item_index, 
                                                          self.elements_list.GetBackgroundColour())
            if self.drop_indicator_line is not None and self.drop_indicator_line < self.elements_list.GetItemCount():
                self.elements_list.RefreshItem(self.drop_indicator_line)
                self.elements_list.Refresh() # Refresh whole list to be sure indicator is gone
        
        self.dragging = False
        self.drag_start_pos = None
        self.drag_item_index = -1
        self.drag_group = False
        self.drop_indicator_line = None
        if hasattr(self, 'drag_group_name'):
            delattr(self, 'drag_group_name')
        
        self._clear_potential_drag_state() # Clear potential drag state as well
    
    def move_element(self, src_list_idx, dst_list_idx):
        """Move an element in the UI elements list, updating indices appropriately"""
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
                
            # Find the lowest index in the destination group
            min_index = 999999
            for item in self.menu_data["items"]:
                item_group = item[5] if len(item) > 5 else "default"
                if item_group == dst_group:
                    item_index = item[8] if len(item) > 8 else 0
                    min_index = min(min_index, item_index)
            
            # Set the element's index to be one less than the minimum
            if min_index < 999999:
                if len(element) <= 8:
                    # Ensure element has enough fields
                    while len(element) < 9:
                        element.append(0)
                element[8] = max(0, min_index - 1)
                
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
        
        # Adjust index to place near destination element
        dst_index = dst_element[8] if len(dst_element) > 8 else 0
        
        # Ensure element has an index field
        while len(element) < 9:
            element.append(0)
            
        # Put it just after the destination element's index
        element[8] = dst_index + 1
        
        # Insert at destination
        self.menu_data["items"].insert(dst_data_idx, element)
        
        # Re-index all items in this group to ensure they're sequential
        self.reindex_group_elements(dst_group)
        
        return True

    def reindex_group_elements(self, group_name):
        """Reindex all elements in a group to ensure they remain in sequence"""
        if not self.menu_data or "items" not in self.menu_data:
            return
            
        # Get all elements in this group
        group_elements = []
        for i, element in enumerate(self.menu_data["items"]):
            element_group = element[5] if len(element) > 5 else "default"
            if element_group == group_name:
                # Get current index or default to 0
                element_index = element[8] if len(element) > 8 else 0
                group_elements.append((i, element, element_index))
        
        # Sort by current index
        group_elements.sort(key=lambda x: x[2])
        
        # Reassign indices to be sequential
        for i, (element_idx, element, _) in enumerate(group_elements):
            # Ensure element has enough fields
            while len(element) < 9:
                element.append(0)
            element[8] = i * 10  # Use multiples of 10 to leave room for manual adjustments
            
        return
    
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
        
        if not self.menu_data or "items" not in self.menu_data or dragged_group_name == "default":
            # Cannot drag the default group itself as a block to reorder relative to other groups
            # Default group elements can be moved individually.
            return False

        # 1. Identify elements to move
        items_to_move_details = []
        for i, element_data_loop in enumerate(self.menu_data["items"]):
            group = element_data_loop[5] if len(element_data_loop) > 5 else "default"
            if group == dragged_group_name:
                items_to_move_details.append({
                    "data_idx": i, # Original index in self.menu_data["items"]
                    "element_ref": element_data_loop, # Direct reference to the element
                    "orig_sort_idx": element_data_loop[8] if len(element_data_loop) > 8 else 0
                })
        
        if not items_to_move_details: return False
        items_to_move_details.sort(key=lambda x: x["orig_sort_idx"]) # Preserve internal order

        # 2. Determine target position's reference sort index from drop_target_list_idx
        ref_sort_index = 0
        place_before = False # True if dragged group should go before the reference item/group

        # Get the list item index where the drag started
        # self.drag_item_index is the list index of the dragged group's header
        original_dragged_header_list_idx = self.drag_item_index 

        # Determine reference based on the item at drop_target_list_idx
        # This needs to find the actual element or group header at drop_target_list_idx
        # and then map that to elements in self.menu_data["items"] to get their sort indices (element[8])

        # Find the element that is visually at the drop_target_list_idx
        target_data_idx_at_drop = self.elements_list.GetItemData(drop_target_list_idx)
        
        if target_data_idx_at_drop != -1: # Dropped onto an element
            target_element_data = self.menu_data["items"][target_data_idx_at_drop]
            ref_sort_index = target_element_data[8] if len(target_element_data) > 8 else 0
            # If the dragged group header was originally below the drop target element, place_before is true
            if original_dragged_header_list_idx > drop_target_list_idx:
                place_before = True
            # If it was above, place_before is false (meaning place after)
        else: # Dropped onto a group header or separator
            target_header_text = self.elements_list.GetItemText(drop_target_list_idx)
            if target_header_text.startswith("---"): # Dropped onto another group's header
                target_group_name_at_drop = target_header_text.strip("-").strip()
                if target_group_name_at_drop == dragged_group_name: # Dropped on itself
                    return False 

                # Find min sort_index of elements in this target_group_name_at_drop
                min_idx_in_target_group = float('inf')
                found_elements_in_target_group = False
                for el_data in self.menu_data["items"]:
                    g = el_data[5] if len(el_data) > 5 else "default"
                    if g == target_group_name_at_drop:
                        idx_val = el_data[8] if len(el_data) > 8 else 0
                        min_idx_in_target_group = min(min_idx_in_target_group, idx_val)
                        found_elements_in_target_group = True
                
                if found_elements_in_target_group:
                    ref_sort_index = min_idx_in_target_group
                else: # Target group is empty, find next non-empty group or place at end
                    # This case needs more robust handling to find a sensible ref_sort_index
                    # For now, let's assume target group has elements or this won't work perfectly.
                    # Fallback: use the logic for separators/empty space
                    pass # Let it fall to the separator logic below

                # If original drag was below this header, place before. Else after.
                if original_dragged_header_list_idx > drop_target_list_idx:
                     place_before = True

            # If still not resolved (e.g. separator or ambiguous drop)
            # try to find the nearest actual elements above and below the drop_target_list_idx
            # to infer a sort_index. This is complex.
            # Simplified: If we are here, it might be a separator.
            # If original drag was below drop target, we assume we want to move up (place_before)
            # relative to the item *after* the separator.
            # If original drag was above, we place after the item *before* the separator.
            if target_data_idx_at_drop == -1 and not target_header_text.startswith("---"): # separator
                if original_dragged_header_list_idx > drop_target_list_idx: # Dragged upwards over a separator
                    # Find next actual item or group header
                    for i_scan in range(drop_target_list_idx + 1, self.elements_list.GetItemCount()):
                        scan_data_idx = self.elements_list.GetItemData(i_scan)
                        scan_text = self.elements_list.GetItemText(i_scan)
                        if scan_data_idx != -1: # Found an element
                            ref_sort_index = self.menu_data["items"][scan_data_idx][8] if len(self.menu_data["items"][scan_data_idx]) > 8 else 0
                            break
                        elif scan_text.startswith("---"): # Found a group header
                            # Logic to get first element's index of this group
                            # For now, this is complex, so we might not get a perfect ref_sort_index here.
                            break 
                    place_before = True
                else: # Dragged downwards over a separator
                     # Find previous actual item or group header
                    for i_scan in range(drop_target_list_idx - 1, -1, -1):
                        scan_data_idx = self.elements_list.GetItemData(i_scan)
                        scan_text = self.elements_list.GetItemText(i_scan)
                        if scan_data_idx != -1:
                            ref_sort_index = self.menu_data["items"][scan_data_idx][8] if len(self.menu_data["items"][scan_data_idx]) > 8 else 0
                            break
                        elif scan_text.startswith("---"):
                            # Logic to get last element's index of this group
                            break
                    place_before = False


        # 3. Calculate new base sort index for the dragged group's items
        # This needs to be adaptive. The goal is to shift the dragged group's items
        # such that their sort_indices are collectively < or > ref_sort_index.
        # A simple strategy: take ref_sort_index and add/subtract a fixed offset.
        
        new_start_sort_index_for_group = 0
        if place_before:
            new_start_sort_index_for_group = ref_sort_index - (len(items_to_move_details) * 10 + 20) # Add larger buffer
        else: # Place after
            new_start_sort_index_for_group = ref_sort_index + 20 # Start after with a buffer

        # To prevent massive gaps or negative indices without bound, some normalization might be needed,
        # or a global re-indexing of all groups if this makes indices too weird.
        # For now, accept potentially large/negative indices if it maintains order.

        # 4. Update element[8] for items_to_move_details
        for i, item_detail in enumerate(items_to_move_details):
            element_to_update = item_detail["element_ref"] # Direct reference
            while len(element_to_update) < 9: element_to_update.append(0)
            element_to_update[8] = new_start_sort_index_for_group + (i * 10)

        self.profile_editor.mark_profile_changed()
        # Store data indices to re-select after update
        moved_data_indices = [item_detail["data_idx"] for item_detail in items_to_move_details]
        
        self.update_elements_list() # This will re-sort based on new indices

        # Re-select the moved items
        new_focused_list_idx = -1
        for i in range(self.elements_list.GetItemCount()):
            item_data_idx = self.elements_list.GetItemData(i)
            if item_data_idx in moved_data_indices:
                self.elements_list.Select(i, True)
                # Try to focus on the first item of the moved block in its new position
                if new_focused_list_idx == -1 or (move_up and i < new_focused_list_idx) or (not move_up and i > new_focused_list_idx) :
                     new_focused_list_idx = i
            else:
                self.elements_list.Select(i, False) # Deselect others for clarity
        
        if new_focused_list_idx != -1:
            self.elements_list.Focus(new_focused_list_idx)
            self.elements_list.EnsureVisible(new_focused_list_idx)
            
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
        elif event.ShiftDown() and (key_code == wx.WXK_UP or key_code == wx.WXK_DOWN):
            self.reorder_selected_conditions(key_code == wx.WXK_UP)
        else:
            event.Skip()  # Let other handlers process this event

    def reorder_selected_conditions(self, move_up):
        """Reorder selected conditions in the list up or down."""
        selected_indices = []
        item = self.conditions_list.GetFirstSelected()
        while item != -1:
            selected_indices.append(item)
            item = self.conditions_list.GetNextSelected(item)

        if not selected_indices:
            return

        conditions_data = self.menu_data.get("conditions", [])
        if not conditions_data:
            return

        # Store the actual condition objects that are selected
        selected_conditions_objects = [conditions_data[i] for i in selected_indices]

        # Sort indices for processing: ascending for up, descending for down
        # This helps manage index changes correctly when items are moved one by one.
        selected_indices.sort(reverse=not move_up)

        moved_count = 0
        for current_idx in selected_indices:
            # Calculate new index
            new_idx = current_idx - 1 if move_up else current_idx + 1

            # Check bounds
            if 0 <= new_idx < len(conditions_data):
                # Pop and insert
                condition_to_move = conditions_data.pop(current_idx)
                conditions_data.insert(new_idx, condition_to_move)
                moved_count +=1
            # If moving multiple items, the effective current_idx for subsequent items
            # in the original list changes. This simple pop & insert handles one item at a time
            # relative to its current position in the modified list.
            # For block movement, a more complex index tracking or temporary list is needed.
            # The current loop structure with sorted indices is designed for single-item-like moves
            # even if multiple are selected. Let's refine for block movement.

        # For block movement, it's easier to remove all selected, then re-insert at target.
        # This simplified version moves each item individually, which might not be true "block" move
        # if they are not contiguous. For true block, we'd find min/max selected index.

        # Let's stick to individual movements for now, as true block movement with Shift+Up/Down
        # usually means moving the whole contiguous block relative to the item above/below the block.
        # The current loop moves selected items past one unselected item at a time.

        if moved_count > 0:
            self.update_conditions_list() # This repopulates self.conditions_list

            # Re-select the moved items
            # This is tricky because indices change. We'll find them by object identity.
            for i in range(self.conditions_list.GetItemCount()):
                condition_in_list = self.menu_data["conditions"][i] # Assuming update_conditions_list maps directly
                if any(condition_in_list is obj for obj in selected_conditions_objects):
                    self.conditions_list.Select(i, True)
                else: # Ensure only moved items are selected if that's the desired behavior
                    self.conditions_list.Select(i, False)


            self.profile_editor.mark_profile_changed()
            # Ensure the last selected/focused item is visible
            # This might need a more specific item to focus on if multiple are selected
            if selected_indices:
                # Attempt to focus on the new position of the first/last moved item
                # This is heuristic
                first_moved_obj = selected_conditions_objects[0] if move_up else selected_conditions_objects[-1]
                try:
                    final_idx_of_an_item = conditions_data.index(first_moved_obj)
                    self.conditions_list.Focus(final_idx_of_an_item)
                    self.conditions_list.EnsureVisible(final_idx_of_an_item)
                except ValueError:
                    pass # Item not found, should not happen

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
        elif event.ShiftDown() and (key_code == wx.WXK_UP or key_code == wx.WXK_DOWN):
            self.reorder_selected_elements(key_code == wx.WXK_UP)
        else:
            event.Skip()  # Let other handlers process this event

    def reorder_selected_elements(self, move_up):
        """Reorder selected UI elements in the list up or down by adjusting their index field."""
        selected_list_indices = []
        item_idx = self.elements_list.GetFirstSelected()
        while item_idx != -1:
            selected_list_indices.append(item_idx)
            item_idx = self.elements_list.GetNextSelected(item_idx)

        if not selected_list_indices:
            return

        # Get current visual order of all actual elements with their data and list indices
        # This respects current filtering and sorting.
        visual_elements = []
        for i in range(self.elements_list.GetItemCount()):
            data_idx = self.elements_list.GetItemData(i)
            if data_idx != -1: # It's an actual element
                element_data = self.menu_data["items"][data_idx]
                visual_elements.append({
                    "list_idx": i, 
                    "data_idx": data_idx, 
                    "element": element_data,
                    "group": element_data[5] if len(element_data) > 5 else "default",
                    "current_sort_idx": element_data[8] if len(element_data) > 8 else 0
                })
        
        if not visual_elements:
            return

        # Map selected list indices to their entries in visual_elements
        selected_visual_elements = [ve for ve in visual_elements if ve["list_idx"] in selected_list_indices]
        if not selected_visual_elements:
            return # No actual elements selected

        # Sort selected elements by their visual order for consistent block movement
        selected_visual_elements.sort(key=lambda ve: ve["list_idx"], reverse=not move_up)

        items_moved_count = 0
        
        # For simplicity, this implementation will move each selected element individually
        # relative to its non-selected neighbor in the visual list, within the same group.
        # True block move of non-contiguous selections is more complex.
        
        for selected_ve in selected_visual_elements:
            current_visual_pos = -1
            for i, ve in enumerate(visual_elements):
                if ve["data_idx"] == selected_ve["data_idx"]:
                    current_visual_pos = i
                    break
            if current_visual_pos == -1: continue # Should not happen

            target_visual_pos = current_visual_pos - 1 if move_up else current_visual_pos + 1

            if 0 <= target_visual_pos < len(visual_elements):
                target_ve = visual_elements[target_visual_pos]
                
                # Only swap if they are in the same group and target is not selected
                if selected_ve["group"] == target_ve["group"] and target_ve["list_idx"] not in selected_list_indices:
                    # Swap their sort indices (element[8])
                    selected_element_data = self.menu_data["items"][selected_ve["data_idx"]]
                    target_element_data = self.menu_data["items"][target_ve["data_idx"]]

                    # Ensure index fields exist
                    while len(selected_element_data) < 9: selected_element_data.append(0)
                    while len(target_element_data) < 9: target_element_data.append(0)
                        
                    selected_idx_val = selected_element_data[8]
                    target_idx_val = target_element_data[8]

                    # Simple swap might not be enough if indices are not consecutive.
                    # A better way is to ensure selected_ve's index becomes smaller/larger.
                    if move_up: # Selected wants to move above target
                        if selected_idx_val > target_idx_val: # If it's not already above
                            selected_element_data[8] = target_idx_val
                            target_element_data[8] = selected_idx_val
                            items_moved_count += 1
                        elif selected_idx_val == target_idx_val: # If indices are same, nudge selected one
                            selected_element_data[8] = target_idx_val -1 # Nudge up
                            items_moved_count += 1
                    else: # move_down: Selected wants to move below target
                        if selected_idx_val < target_idx_val: # If it's not already below
                            selected_element_data[8] = target_idx_val
                            target_element_data[8] = selected_idx_val
                            items_moved_count += 1
                        elif selected_idx_val == target_idx_val: # If indices are same, nudge selected one
                            selected_element_data[8] = target_idx_val + 1 # Nudge down
                            items_moved_count += 1
                    
                    # After a swap, the visual_elements list is out of sync with element[8] values.
                    # For the next iteration, we'd need to re-evaluate visual_elements or accept
                    # that this loop handles one "effective" move per selected item based on initial state.
                    # For now, we'll update the data and then let update_elements_list() re-sort.
            
        if items_moved_count > 0:
            self.profile_editor.mark_profile_changed()
            
            # Store original data_idx of selected items to re-select them
            selected_data_indices = [ve["data_idx"] for ve in selected_visual_elements]
            
            self.update_elements_list() # This re-sorts and repopulates the ListCtrl

            # Re-select moved items
            new_focused_item_list_idx = -1
            for i in range(self.elements_list.GetItemCount()):
                item_data_idx = self.elements_list.GetItemData(i)
                if item_data_idx in selected_data_indices:
                    self.elements_list.Select(i, True)
                    if new_focused_item_list_idx == -1 : # Focus on the first one (topmost if moving up, bottommost if moving down due to sort)
                         new_focused_item_list_idx = i
                else:
                    # Ensure only originally selected items remain selected if that's the goal
                    # Or, if we want to clear others, do it here. Current wx behavior is additive.
                    pass 
            
            if new_focused_item_list_idx != -1:
                self.elements_list.Focus(new_focused_item_list_idx)
                self.elements_list.EnsureVisible(new_focused_item_list_idx)

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
        selected_idx = event.GetIndex() # Get item directly from event
        if selected_idx == -1:
            event.Skip() # Click was not on an item
            return

        # Inlined logic from on_edit_condition
        condition = self.menu_data["conditions"][selected_idx]
        
        dialog = None
        if condition["type"] == "pixel_color":
            dialog = PixelColorConditionDialog(self, title="Edit Pixel Color Condition", 
                                             condition=condition)
        elif condition["type"] == "pixel_region_color":
            dialog = RegionColorConditionDialog(self, title="Edit Region Color Condition", 
                                              condition=condition)
        elif condition["type"] == "pixel_region_image":
            # Note: RegionImageConditionDialog was imported in a previous step.
            # If it causes circular import issues, it should be imported locally in methods.
            dialog = RegionImageConditionDialog(self, title="Edit Region Image Condition", 
                                              condition=condition)
        elif condition["type"] == "ocr_text_present":
            dialog = OCRConditionDialog(self, title="Edit OCR Condition", condition=condition)
        else:
            wx.MessageBox(f"Cannot edit condition of type: {condition['type']}", 
                         "Error", wx.ICON_ERROR)
            return
        
        if dialog:
            if dialog.ShowModal() == wx.ID_OK:
                edited_condition = dialog.get_condition()
                self.menu_data["conditions"][selected_idx] = edited_condition
                self.update_conditions_list()
                self.profile_editor.mark_profile_changed()
            dialog.Destroy()
        # event.Skip(False) # Event handled
    
    def on_element_dclick(self, event):
        """Handle double-click on an element item"""
        if self.dragging: # Prevent edit during drag
            event.Skip()
            return
            
        selected_item_list_idx = event.GetIndex() # Get item directly from event
        if selected_item_list_idx == -1:
            event.Skip() # Click was not on an item
            return

        # Inlined logic from on_edit_element
        orig_idx = self.elements_list.GetItemData(selected_item_list_idx)
        if orig_idx == -1: # Skip group headers and separators
            event.Skip()
            return
            
        element = self.menu_data["items"][orig_idx]
        
        dialog = UIElementDialog(self, title="Edit UI Element", element=element)
        if dialog.ShowModal() == wx.ID_OK:
            edited_element = dialog.get_element()
            self.menu_data["items"][orig_idx] = edited_element
            self.refresh_entire_panel() # Ensure consistency
            self.profile_editor.mark_profile_changed()
        dialog.Destroy()
        # event.Skip(False) # Event handled
    
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
            is_negated = condition.get("negate", False)
            negation_prefix = "NOT " if is_negated else ""
            
            if condition_type == "pixel_color":
                details = f"{negation_prefix}({condition['x']}, {condition['y']}) = RGB{condition['color']} +/-{condition['tolerance']}"
            elif condition_type == "pixel_region_color":
                details = f"{negation_prefix}Region ({condition['x1']}, {condition['y1']}) to ({condition['x2']}, {condition['y2']}), " \
                          f"RGB{condition['color']} +/-{condition['tolerance']}, thresh={condition['threshold']}"
            elif condition_type == "pixel_region_image":
                details = f"{negation_prefix}Region ({condition['x1']}, {condition['y1']}) to ({condition['x2']}, {condition['y2']}), " \
                          f"confidence={condition['confidence']:.2f}, has_image={'Yes' if condition.get('image_data') else 'No'}"
            elif condition_type == "ocr_text_present":
                text = condition.get('text_to_find', '')
                region = condition.get('region', '[?, ?, ?, ?]')
                langs = ','.join(condition.get('languages', ['en']))
                case_sensitive = condition.get('case_sensitive', False)
                details = f"{negation_prefix}OCR: \"{text}\" in {region} (Langs: {langs}, Case: {'Yes' if case_sensitive else 'No'})"
            else:
                details = f"{negation_prefix}{str(condition)}"
            
            idx = self.conditions_list.InsertItem(i, condition_type)
            self.conditions_list.SetItem(idx, 1, details)
    
    def update_elements_list(self):
        """Update the elements list with current data, sorted by index field"""
        self.elements_list.DeleteAllItems()
        
        if "items" not in self.menu_data:
            return
        
        # Get current group filter
        filter_idx = self.group_filter.GetSelection()
        if filter_idx <= 0:  # "All Groups" or invalid selection
            selected_group = None
        else:
            selected_group = self.group_filter.GetString(filter_idx)
        
        # Sort items by group and index for grouped display
        sorted_items = []
        if "items" in self.menu_data:
            for i, element in enumerate(self.menu_data["items"]):
                # Get the group (default to "default" if not present)
                group = element[5] if len(element) > 5 else "default"
                # Get the index (default to 0 if not present)
                index = element[8] if len(element) > 8 else 0
                # Only include items matching the filter, if one is selected
                if selected_group is None or group == selected_group:
                    sorted_items.append((i, element, group, index))
        
        # Sort by group first, then by index within each group
        sorted_items.sort(key=lambda x: (x[2], x[3]))
        
        # Add items to the list
        current_group = None
        list_idx = 0
        
        for orig_idx, element, group, index in sorted_items:
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
            
            # Add index as last column 
            element_index = element[8] if len(element) > 8 else 0
            self.elements_list.SetItem(idx, 7, str(element_index))
            
            # Has conditional elements 
            has_conditions = len(element) > 9 and element[9]
            self.elements_list.SetItem(idx, 8, f"{len(element[9])}" if has_conditions else "")
            
            # Store the original index for this item
            self.elements_list.SetItemData(idx, orig_idx)
            
            list_idx += 1
        
        # End any drag operation in progress
        self.end_drag()
        
        # Force proper layout refresh
        self.Layout()
    
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
        pasted_conditions_objects = [copy.deepcopy(c) for c in self.profile_editor.clipboard['conditions']]
        count = len(pasted_conditions_objects)

        if not pasted_conditions_objects:
            return

        # Determine insertion index
        last_selected_idx = -1
        item = self.conditions_list.GetFirstSelected()
        while item != -1:
            last_selected_idx = item
            item = self.conditions_list.GetNextSelected(item)

        insert_at_idx = last_selected_idx + 1 if last_selected_idx != -1 else len(self.menu_data["conditions"])

        # Insert items
        for i, condition_obj in enumerate(pasted_conditions_objects):
            self.menu_data["conditions"].insert(insert_at_idx + i, condition_obj)
        
        # Update UI
        self.update_conditions_list() # This also clears existing selections

        # Re-select the newly pasted items
        first_pasted_list_idx = -1
        for i in range(self.conditions_list.GetItemCount()):
            # Assuming menu_data["conditions"] directly maps to list items after update
            condition_in_list_data = self.menu_data["conditions"][i] 
            is_pasted = False
            for pasted_obj in pasted_conditions_objects:
                if condition_in_list_data is pasted_obj: # Check by object identity
                    is_pasted = True
                    break
            
            if is_pasted:
                self.conditions_list.Select(i, True)
                if first_pasted_list_idx == -1:
                    first_pasted_list_idx = i
        
        if first_pasted_list_idx != -1:
            self.conditions_list.Focus(first_pasted_list_idx)
            self.conditions_list.EnsureVisible(first_pasted_list_idx)

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
        elif condition["type"] == "pixel_region_image":
            from pflib.dialogs import RegionImageConditionDialog  # Import here to avoid circular imports
            dialog = RegionImageConditionDialog(self, title="Edit Region Image Condition", 
                                              condition=condition)
        elif condition["type"] == "ocr_text_present":
            dialog = OCRConditionDialog(self, title="Edit OCR Condition", condition=condition)
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
        pasted_element_objects = [copy.deepcopy(e) for e in self.profile_editor.clipboard['elements']]
        count = len(pasted_element_objects)

        if not pasted_element_objects:
            return

        # Determine insertion point and context
        last_selected_list_idx = -1
        item_idx = self.elements_list.GetFirstSelected()
        while item_idx != -1:
            # Ensure it's an actual element, not a header/separator
            if self.elements_list.GetItemData(item_idx) != -1:
                last_selected_list_idx = item_idx
            item_idx = self.elements_list.GetNextSelected(item_idx)

        target_data_idx = -1
        target_group = "default" # Default group if no selection or pasted at end
        target_sort_idx = -10 # Default sort index if appending (will be adjusted)

        if last_selected_list_idx != -1:
            target_data_idx = self.elements_list.GetItemData(last_selected_list_idx)
            if target_data_idx != -1: # Check if it's a valid element
                target_element = self.menu_data["items"][target_data_idx]
                target_group = target_element[5] if len(target_element) > 5 else "default"
                target_sort_idx = target_element[8] if len(target_element) > 8 else 0
            else: # Selected item was a header/separator, revert to append logic
                target_data_idx = -1 # Mark to append

        # Insert elements and set their properties
        if target_data_idx != -1: # Insert after selected element
            # The actual insertion index into self.menu_data["items"]
            # This list is not sorted by element[8], so direct index works.
            # We insert them sequentially after the target_data_idx
            actual_insert_start_idx = target_data_idx + 1
            
            for i, pasted_el in enumerate(pasted_element_objects):
                # Inherit group from the target element
                while len(pasted_el) < 6: pasted_el.append(None)
                pasted_el[5] = target_group
                
                # Set initial sort index to be after the target element
                # We'll use small increments; reindex_group_elements will clean it up.
                while len(pasted_el) < 9: pasted_el.append(0)
                pasted_el[8] = target_sort_idx + (i + 1) * 0.1 # Temporary small increment
                
                self.menu_data["items"].insert(actual_insert_start_idx + i, pasted_el)
            
            # Re-index the entire group to normalize sort indices
            self.reindex_group_elements(target_group)

        else: # Append to the end of the items list
            for pasted_el in pasted_element_objects:
                # Element retains its original group or defaults if necessary
                current_group = pasted_el[5] if len(pasted_el) > 5 and pasted_el[5] else "default"
                while len(pasted_el) < 6: pasted_el.append(None)
                pasted_el[5] = current_group

                # Find max sort_idx in its group to append it logically at the end
                max_sort_idx_in_group = -1
                for item in self.menu_data["items"]:
                    item_grp = item[5] if len(item) > 5 and item[5] else "default"
                    if item_grp == current_group:
                        item_sort_idx = item[8] if len(item) > 8 else 0
                        if item_sort_idx > max_sort_idx_in_group:
                            max_sort_idx_in_group = item_sort_idx
                
                while len(pasted_el) < 9: pasted_el.append(0)
                pasted_el[8] = max_sort_idx_in_group + 10 # Append with a gap

                self.menu_data["items"].append(pasted_el)

        # Refresh everything to ensure consistency (this also re-sorts visually)
        self.profile_editor.mark_profile_changed() # Mark changed before refresh in case refresh clears selection state
        
        # Store references to pasted objects for re-selection
        # Note: pasted_element_objects already contains the deep-copied objects
        
        self.refresh_entire_panel() # This calls update_elements_list, which clears selections

        # Re-select the newly pasted items
        first_pasted_list_idx = -1
        # We need to map the pasted objects (which are now in self.menu_data["items"])
        # back to their new list indices in self.elements_list.
        # GetItemData stores the index into self.menu_data["items"].
        
        # Create a quick lookup for pasted objects by their original data_idx if needed,
        # but identity check is better.
        
        # Find the new list indices of the pasted items
        pasted_data_indices = []
        for pasted_obj in pasted_element_objects:
            try:
                # Find the index of this specific object in the (potentially reordered) menu_data items
                pasted_data_indices.append(self.menu_data["items"].index(pasted_obj))
            except ValueError:
                pass # Should not happen if objects were correctly inserted

        if pasted_data_indices:
            for i in range(self.elements_list.GetItemCount()):
                item_data_original_idx = self.elements_list.GetItemData(i)
                if item_data_original_idx in pasted_data_indices:
                    self.elements_list.Select(i, True)
                    if first_pasted_list_idx == -1 or i < first_pasted_list_idx: # Try to focus the topmost one
                        first_pasted_list_idx = i
        
        if first_pasted_list_idx != -1:
            self.elements_list.Focus(first_pasted_list_idx)
            self.elements_list.EnsureVisible(first_pasted_list_idx)
        
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
        
        # conditions_logic is saved on change, so no specific action here,
        # but ensuring it's part of menu_data is key.
        # self.menu_data["conditions_logic"] = self.conditions_logic_combo.GetValue() # Already done by on_conditions_logic_changed
        
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
        
        # Add index field to bulk edit dialog
        index_box = wx.BoxSizer(wx.HORIZONTAL)
        index_cb = wx.CheckBox(dialog.panel, label="Change index:")
        index_ctrl = wx.SpinCtrl(dialog.panel, min=0, max=999, value="0")
        index_ctrl.Enable(False)
        index_cb.Bind(wx.EVT_CHECKBOX, lambda evt: index_ctrl.Enable(evt.IsChecked()))
        
        index_box.Add(index_cb, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        index_box.Add(index_ctrl, proportion=1)
        dialog.main_sizer.Insert(4, index_box, flag=wx.ALL | wx.EXPAND, border=10)  # Insert at appropriate position
        
        if dialog.ShowModal() == wx.ID_OK:
            # Get the changes to apply
            changes = dialog.get_bulk_changes()
            
            # Add index to changes if selected
            if index_cb.GetValue():
                changes['index'] = index_ctrl.GetValue()
            
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
                
                # Apply index change if specified
                if 'index' in changes:
                    # Ensure element list is long enough
                    while len(element) < 9:
                        element.append(0)
                    element[8] = changes['index']
                
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