"""
Menu panel for editing menu data with improved drag and drop
"""

import wx
import wx.lib.scrolledpanel as scrolled
import copy

from pflib.dialogs import (
    PixelColorConditionDialog, RegionColorConditionDialog, 
    RegionImageConditionDialog, UIElementDialog,
    OCRTextMatchConditionDialog, ORConditionDialog # New condition dialogs
)
from pflib.bulk_edit_dialog import BulkEditElementsDialog
from pflib.condition_bulk_edit import BulkEditConditionsDialog

class GroupManagerDialog(wx.Dialog):
    """Dialog for managing element groups in a menu, with ordering support"""
    
    def __init__(self, parent, menu_data, menu_id): # Added menu_id
        super().__init__(parent, title="Group Manager", size=(500, 500))
        
        self.menu_data = menu_data
        self.menu_id = menu_id # Store menu_id for updating profile_editor
        self.menu_panel = parent # This is the MenuPanel instance
        
        # Initialize group_order_indices if not present
        if "group_order_indices" not in self.menu_data:
            self.menu_data["group_order_indices"] = {"default": 0}
        
        # Collect all existing groups from items and ensure they are in group_order_indices
        # Assign a high index to new groups found in items but not in order_indices
        # to place them at the end initially.
        max_existing_order_index = 0
        if self.menu_data["group_order_indices"]:
             max_existing_order_index = max(self.menu_data["group_order_indices"].values() or [0])

        if "items" in self.menu_data:
            for item in self.menu_data["items"]:
                group_name = item[5] if len(item) > 5 and item[5] else "default"
                if group_name not in self.menu_data["group_order_indices"]:
                    max_existing_order_index += 10 # Increment for new group
                    self.menu_data["group_order_indices"][group_name] = max_existing_order_index
        
        self.init_ui()
        self.Center()
        
    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        instructions = wx.StaticText(panel, label="Manage element groups in this menu:")
        main_sizer.Add(instructions, flag=wx.ALL | wx.EXPAND, border=10)
        
        list_label = wx.StaticText(panel, label="Groups (drag to reorder):")
        main_sizer.Add(list_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        
        self.group_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 250))
        self.group_list.InsertColumn(0, "Group Name", width=250)
        self.group_list.InsertColumn(1, "Order Index", width=100) # Changed label
        self.group_list.InsertColumn(2, "Elements", width=70)
        
        self.update_group_list_display() # Populate the list
            
        main_sizer.Add(self.group_list, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        
        btn_sizer_actions = wx.BoxSizer(wx.HORIZONTAL) # Renamed
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
        
        btn_sizer_actions.Add(self.add_btn, 0, wx.RIGHT, 5)
        btn_sizer_actions.Add(self.rename_btn, 0, wx.RIGHT, 5)
        btn_sizer_actions.Add(self.delete_btn, 0, wx.RIGHT, 5)
        btn_sizer_actions.Add(self.move_up_btn, 0, wx.RIGHT, 5)
        btn_sizer_actions.Add(self.move_down_btn, 0)
        main_sizer.Add(btn_sizer_actions, flag=wx.ALL | wx.ALIGN_CENTER, border=10)
        
        index_box = wx.StaticBox(panel, label="Manual Group Order Index")
        index_sizer = wx.StaticBoxSizer(index_box, wx.VERTICAL)
        index_help = wx.StaticText(panel, label="Set custom order index for the selected group:")
        index_sizer.Add(index_help, flag=wx.ALL, border=5)
        index_ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.index_spinner = wx.SpinCtrl(panel, min=0, max=9999, value="0") # Increased max
        set_index_btn = wx.Button(panel, label="Set Index")
        set_index_btn.Bind(wx.EVT_BUTTON, self.on_set_index)
        index_ctrl_sizer.Add(self.index_spinner, flag=wx.RIGHT, border=10)
        index_ctrl_sizer.Add(set_index_btn)
        index_sizer.Add(index_ctrl_sizer, flag=wx.ALL, border=5)
        main_sizer.Add(index_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        btn_sizer_std = wx.StdDialogButtonSizer() # Renamed
        ok_button = wx.Button(panel, wx.ID_OK)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        btn_sizer_std.AddButton(ok_button); btn_sizer_std.AddButton(cancel_button)
        btn_sizer_std.Realize()
        main_sizer.Add(btn_sizer_std, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
        
        panel.SetSizer(main_sizer)
        
        self.group_list.Bind(wx.EVT_LIST_BEGIN_DRAG, self.on_begin_drag)
        self.group_list.Bind(wx.EVT_MOTION, self.on_motion)
        self.group_list.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.group_list.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave_window)
        
        self.drag_item_idx = None # Store list index of dragged item
        self.drag_image = None
        self.drop_target_idx = None # Store list index of drop target
        
        self.update_ui_buttons()
        self.group_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_group_selected)
        
    def on_group_selected(self, event):
        self.update_ui_buttons()
        item_idx = self.group_list.GetFirstSelected()
        if item_idx != -1:
            order_index_str = self.group_list.GetItemText(item_idx, 1)
            try:
                self.index_spinner.SetValue(int(order_index_str))
            except ValueError:
                self.index_spinner.SetValue(0) # Fallback
    
    def update_ui_buttons(self):
        selection_idx = self.group_list.GetFirstSelected()
        has_selection = selection_idx != -1
        
        self.rename_btn.Enable(has_selection)
        can_delete = False
        if has_selection:
            group_name = self.group_list.GetItemText(selection_idx, 0)
            can_delete = group_name != "default"
        self.delete_btn.Enable(can_delete)
        
        self.move_up_btn.Enable(has_selection and selection_idx > 0)
        self.move_down_btn.Enable(has_selection and selection_idx < self.group_list.GetItemCount() - 1)
        
    def count_elements_in_group(self, group_name_to_count):
        count = 0
        if "items" in self.menu_data:
            for item in self.menu_data["items"]:
                item_group = item[5] if len(item) > 5 and item[5] else "default"
                if item_group == group_name_to_count:
                    count += 1
        return count
    
    def on_begin_drag(self, event):
        item_idx = event.GetIndex()
        group_name = self.group_list.GetItemText(item_idx, 0)
        if group_name == "default": return # Cannot drag default
            
        self.drag_item_idx = item_idx
        
        # For simplicity, not using wx.DragImage here, will use visual cues in list
        self.group_list.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        event.Allow() # Important for D&D in ListCtrl

    def on_motion(self, event):
        if self.drag_item_idx is not None and event.Dragging():
            pos = event.GetPosition()
            item_idx_over, flags = self.group_list.HitTest(pos)

            # Clear previous drop indicator
            if self.drop_target_idx is not None and self.drop_target_idx < self.group_list.GetItemCount():
                 self.group_list.SetItemBackgroundColour(self.drop_target_idx, self.group_list.GetBackgroundColour())

            if item_idx_over != -1 and item_idx_over != self.drag_item_idx:
                self.drop_target_idx = item_idx_over
                self.group_list.SetItemBackgroundColour(self.drop_target_idx, wx.Colour(200, 220, 255)) # Highlight
            else:
                self.drop_target_idx = None
        event.Skip()
    
    def on_left_up(self, event):
        if self.drag_item_idx is not None:
            self.group_list.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            if self.drop_target_idx is not None and self.drop_target_idx != self.drag_item_idx:
                self.reorder_group(self.drag_item_idx, self.drop_target_idx)
            
            # Clear highlighting
            if self.drop_target_idx is not None and self.drop_target_idx < self.group_list.GetItemCount():
                self.group_list.SetItemBackgroundColour(self.drop_target_idx, self.group_list.GetBackgroundColour())

            self.drag_item_idx = None
            self.drop_target_idx = None
            self.update_ui_buttons()
        event.Skip()
    
    def on_leave_window(self, event):
        if self.drag_item_idx is not None:
            self.group_list.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            if self.drop_target_idx is not None and self.drop_target_idx < self.group_list.GetItemCount():
                 self.group_list.SetItemBackgroundColour(self.drop_target_idx, self.group_list.GetBackgroundColour())
            self.drag_item_idx = None
            self.drop_target_idx = None
            self.update_ui_buttons()
        event.Skip()
            
    def reorder_group(self, src_list_idx, dst_list_idx):
        src_group_name = self.group_list.GetItemText(src_list_idx, 0)
        dst_group_name = self.group_list.GetItemText(dst_list_idx, 0)

        src_order_index = self.menu_data["group_order_indices"][src_group_name]
        dst_order_index = self.menu_data["group_order_indices"][dst_group_name]

        if src_list_idx < dst_list_idx: # Moving down
            # Shift items between src and dst up
            for name, order_idx in self.menu_data["group_order_indices"].items():
                if src_order_index < order_idx <= dst_order_index:
                    self.menu_data["group_order_indices"][name] = order_idx - 1 # Or some other step
            self.menu_data["group_order_indices"][src_group_name] = dst_order_index
        else: # Moving up
            # Shift items between dst and src down
            for name, order_idx in self.menu_data["group_order_indices"].items():
                if dst_order_index <= order_idx < src_order_index:
                    self.menu_data["group_order_indices"][name] = order_idx + 1 # Or some other step
            self.menu_data["group_order_indices"][src_group_name] = dst_order_index
        
        # Normalize indices to be somewhat sequential if gaps are too large or collisions happened
        self.normalize_group_order_indices()
        self.update_group_list_display()
        self.menu_panel.profile_editor.mark_profile_changed()
        self.SetReturnCode(wx.ID_OK) # Indicate changes made
            
    def on_add_group(self, event):
        dialog = wx.TextEntryDialog(self, "Enter new group name:", "Add Group")
        if dialog.ShowModal() == wx.ID_OK:
            group_name = dialog.GetValue().strip()
            if group_name:
                if group_name in self.menu_data["group_order_indices"]:
                    wx.MessageBox(f"Group '{group_name}' already exists", "Duplicate Group", wx.ICON_ERROR)
                else:
                    max_order_idx = 0
                    if self.menu_data["group_order_indices"]:
                        max_order_idx = max(self.menu_data["group_order_indices"].values() or [0])
                    self.menu_data["group_order_indices"][group_name] = max_order_idx + 10
                    
                    self.update_group_list_display()
                    self.menu_panel.profile_editor.mark_profile_changed()
                    self.SetReturnCode(wx.ID_OK)
        dialog.Destroy()
    
    def on_rename_group(self, event):
        selection_idx = self.group_list.GetFirstSelected()
        if selection_idx == -1: return
        old_name = self.group_list.GetItemText(selection_idx, 0)
        if old_name == "default":
            wx.MessageBox("Cannot rename the 'default' group", "Error", wx.ICON_ERROR); return
            
        dialog = wx.TextEntryDialog(self, "Enter new group name:", "Rename Group", old_name)
        if dialog.ShowModal() == wx.ID_OK:
            new_name = dialog.GetValue().strip()
            if new_name and new_name != old_name:
                if new_name in self.menu_data["group_order_indices"]:
                    wx.MessageBox(f"Group '{new_name}' already exists", "Duplicate Group", wx.ICON_ERROR); return
                
                # Update group_order_indices
                order_idx = self.menu_data["group_order_indices"].pop(old_name)
                self.menu_data["group_order_indices"][new_name] = order_idx
                
                # Update elements
                for item in self.menu_data.get("items", []):
                    if len(item) > 5 and item[5] == old_name: item[5] = new_name
                
                self.update_group_list_display()
                self.menu_panel.profile_editor.mark_profile_changed()
                self.SetReturnCode(wx.ID_OK)
        dialog.Destroy()
    
    def on_delete_group(self, event):
        selection_idx = self.group_list.GetFirstSelected()
        if selection_idx == -1: return
        group_name_to_delete = self.group_list.GetItemText(selection_idx, 0)
        if group_name_to_delete == "default":
            wx.MessageBox("Cannot delete the 'default' group", "Error", wx.ICON_ERROR); return
            
        count = self.count_elements_in_group(group_name_to_delete)
        msg = f"Group '{group_name_to_delete}' contains {count} elements. Deleting this group will move these elements to the 'default' group. Continue?"
        if wx.MessageBox(msg, "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) != wx.YES: return
            
        # Move elements to default group
        for item in self.menu_data.get("items", []):
            if len(item) > 5 and item[5] == group_name_to_delete: item[5] = "default"
        
        del self.menu_data["group_order_indices"][group_name_to_delete]
        self.update_group_list_display()
        self.menu_panel.profile_editor.mark_profile_changed()
        self.SetReturnCode(wx.ID_OK)
    
    def on_move_up(self, event):
        selection_idx = self.group_list.GetFirstSelected()
        if selection_idx <= 0: return
        self.reorder_group(selection_idx, selection_idx - 1)
        
    def on_move_down(self, event):
        selection_idx = self.group_list.GetFirstSelected()
        if selection_idx == -1 or selection_idx >= self.group_list.GetItemCount() - 1: return
        self.reorder_group(selection_idx, selection_idx + 1)
    
    def on_set_index(self, event):
        selection_idx = self.group_list.GetFirstSelected()
        if selection_idx == -1: return
        group_name = self.group_list.GetItemText(selection_idx, 0)
        new_order_index = self.index_spinner.GetValue()
        
        # Check for conflicts and adjust if necessary
        for g_name, o_idx in self.menu_data["group_order_indices"].items():
            if g_name != group_name and o_idx == new_order_index:
                # Shift others to make space, simple increment for now
                self.menu_data["group_order_indices"][g_name] = o_idx + 10 
        
        self.menu_data["group_order_indices"][group_name] = new_order_index
        self.normalize_group_order_indices()
        self.update_group_list_display()
        self.menu_panel.profile_editor.mark_profile_changed()
        self.SetReturnCode(wx.ID_OK)

    def normalize_group_order_indices(self):
        """Ensures group order indices are somewhat sequential without gaps/major collisions."""
        sorted_groups = sorted(self.menu_data["group_order_indices"].items(), key=lambda item: item[1])
        current_idx = 0
        for name, _ in sorted_groups:
            self.menu_data["group_order_indices"][name] = current_idx
            current_idx += 10 # Use steps of 10
    
    def update_group_list_display(self):
        self.group_list.DeleteAllItems()
        # Sort groups by their order index for display
        sorted_groups_for_display = sorted(
            self.menu_data["group_order_indices"].items(), 
            key=lambda item: item[1]
        )
        for i, (group_name, order_index) in enumerate(sorted_groups_for_display):
            idx = self.group_list.InsertItem(i, group_name)
            self.group_list.SetItem(idx, 1, str(order_index))
            element_count = self.count_elements_in_group(group_name)
            self.group_list.SetItem(idx, 2, str(element_count))
        self.update_ui_buttons()


class MenuPanel(scrolled.ScrolledPanel):
    """Panel for displaying and editing menu data"""
    
    def __init__(self, parent, menu_id, menu_data, profile_editor):
        super().__init__(parent)
        
        self.menu_id = menu_id
        self.menu_data = menu_data 
        self.profile_editor = profile_editor # This is the ProfileEditorFrame instance
        
        self.dragging_element = False
        self.drag_element_start_pos = None
        self.drag_element_list_idx = None 
        self.drop_element_indicator_line = None
        
        self.SetMinSize((750, 600))
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        
        self.init_ui() 
        self.update_reset_group_options()
        self.SetupScrolling(scrollToTop=False, scrollIntoView=False, rate_x=20, rate_y=20)
        
    def init_ui(self):
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title = wx.StaticText(self, label=f"Menu: {self.menu_id}")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        header_sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        option_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.is_manual_cb = wx.CheckBox(self, label="Manual Menu (ignores conditions)")
        self.is_manual_cb.SetValue(self.menu_data.get("is_manual", False))
        self.is_manual_cb.Bind(wx.EVT_CHECKBOX, self.on_is_manual_changed)
        option_sizer.Add(self.is_manual_cb, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 10)

        self.reset_index_cb = wx.CheckBox(self, label="Reset index on entry")
        self.reset_index_cb.SetValue(self.menu_data.get("reset_index", True))
        self.reset_index_cb.Bind(wx.EVT_CHECKBOX, self.on_reset_index_changed)
        option_sizer.Add(self.reset_index_cb, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 10)
        
        reset_group_label = wx.StaticText(self, label="Reset to group:")
        self.reset_group_ctrl = wx.ComboBox(self, choices=["default"], value=self.menu_data.get("reset_group", "default"))
        self.reset_group_ctrl.Bind(wx.EVT_COMBOBOX, self.on_reset_group_changed)
        option_sizer.Add(reset_group_label, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        option_sizer.Add(self.reset_group_ctrl, 1, wx.ALIGN_CENTER_VERTICAL) 
        header_sizer.Add(option_sizer, 1, wx.LEFT | wx.EXPAND, 15) 
        
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        duplicate_btn = wx.Button(self, label="Duplicate"); duplicate_btn.Bind(wx.EVT_BUTTON, self.on_duplicate_menu)
        rename_btn = wx.Button(self, label="Rename"); rename_btn.Bind(wx.EVT_BUTTON, self.on_rename_menu)
        delete_btn = wx.Button(self, label="Delete"); delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_menu)
        buttons_sizer.Add(duplicate_btn, 0, wx.RIGHT, 5); buttons_sizer.Add(rename_btn, 0, wx.RIGHT, 5); buttons_sizer.Add(delete_btn, 0)
        header_sizer.Add(buttons_sizer, 0, wx.LEFT, 10)
        self.main_sizer.Add(header_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        self.conditions_box_static = wx.StaticBox(self, label="Menu Detection Conditions")
        self.conditions_sizer = wx.StaticBoxSizer(self.conditions_box_static, wx.VERTICAL) 
        btn_sizer_cond = wx.BoxSizer(wx.HORIZONTAL)
        
        add_pixel_btn = wx.Button(self, label="Pixel"); add_pixel_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_menu_condition("pixel_color"))
        add_region_btn = wx.Button(self, label="RegionColor"); add_region_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_menu_condition("pixel_region_color"))
        add_region_image_btn = wx.Button(self, label="RegionImage"); add_region_image_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_menu_condition("pixel_region_image"))
        add_or_btn = wx.Button(self, label="OR"); add_or_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_menu_condition("or"))
        add_ocr_match_btn = wx.Button(self, label="OCR Match"); add_ocr_match_btn.Bind(wx.EVT_BUTTON, lambda e: self.on_add_menu_condition("ocr_text_match"))
        paste_condition_btn = wx.Button(self, label="Paste"); paste_condition_btn.Bind(wx.EVT_BUTTON, self.on_paste_condition)
        
        btn_sizer_cond.Add(add_pixel_btn,0,wx.RIGHT,5); btn_sizer_cond.Add(add_region_btn,0,wx.RIGHT,5)
        btn_sizer_cond.Add(add_region_image_btn,0,wx.RIGHT,5); btn_sizer_cond.Add(add_or_btn,0,wx.RIGHT,5)
        btn_sizer_cond.Add(add_ocr_match_btn,0,wx.RIGHT,5); btn_sizer_cond.Add(paste_condition_btn, 1, wx.EXPAND)
        self.conditions_sizer.Add(btn_sizer_cond, 0, wx.EXPAND | wx.ALL, 5)
        
        self.conditions_list = wx.ListCtrl(self, style=wx.LC_REPORT, size=(-1, 150)) 
        self.conditions_list.InsertColumn(0, "Type", width=120); self.conditions_list.InsertColumn(1, "Details", width=400)
        self.update_conditions_list()
        self.conditions_list.Bind(wx.EVT_CONTEXT_MENU, self.on_condition_context_menu)
        self.conditions_list.Bind(wx.EVT_LEFT_DCLICK, self.on_condition_dclick)
        self.conditions_list.Bind(wx.EVT_KEY_DOWN, self.on_conditions_key)
        self.conditions_sizer.Add(self.conditions_list, 1, wx.EXPAND | wx.ALL, 5)
        self.main_sizer.Add(self.conditions_sizer, 1, wx.EXPAND | wx.ALL, 10)
        
        elements_box = wx.StaticBox(self, label="Menu UI Elements")
        elements_sizer = wx.StaticBoxSizer(elements_box, wx.VERTICAL)
        group_filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        group_filter_label = wx.StaticText(self, label="Filter by Group:")
        self.group_filter = wx.Choice(self, choices=["All Groups"])
        self.group_filter.SetSelection(0)
        self.group_filter.Bind(wx.EVT_CHOICE, self.on_group_filter_changed)
        manage_groups_btn = wx.Button(self, label="Manage Groups"); manage_groups_btn.Bind(wx.EVT_BUTTON, self.on_manage_groups)
        group_filter_sizer.Add(group_filter_label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        group_filter_sizer.Add(self.group_filter, 1, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 10)
        group_filter_sizer.Add(manage_groups_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        elements_sizer.Add(group_filter_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        element_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_element_btn = wx.Button(self, label="Add UI Element"); add_element_btn.Bind(wx.EVT_BUTTON, self.on_add_element)
        paste_element_btn = wx.Button(self, label="Paste Element(s)"); paste_element_btn.Bind(wx.EVT_BUTTON, self.on_paste_element)
        element_btn_sizer.Add(add_element_btn, 0, wx.RIGHT, 5)
        element_btn_sizer.Add(paste_element_btn, 1, wx.EXPAND)
        elements_sizer.Add(element_btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        self.elements_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_EDIT_LABELS, size=(-1, 250)) 
        self.elements_list.InsertColumn(0, "Name", width=150); self.elements_list.InsertColumn(1, "Type", width=80)
        self.elements_list.InsertColumn(2, "Pos", width=70); self.elements_list.InsertColumn(3, "Group", width=100)
        self.elements_list.InsertColumn(4, "Submenu", width=100); self.elements_list.InsertColumn(5, "OCR", width=40)
        self.elements_list.InsertColumn(6, "Format", width=60); self.elements_list.InsertColumn(7, "Idx", width=40)
        self.elements_list.InsertColumn(8, "Cond", width=50)
        
        self.elements_list.Bind(wx.EVT_LIST_BEGIN_DRAG, self.on_element_begin_drag)
        self.elements_list.Bind(wx.EVT_MOTION, self.on_element_motion)
        self.elements_list.Bind(wx.EVT_LEFT_UP, self.on_element_left_up)
        self.elements_list.Bind(wx.EVT_LEAVE_WINDOW, self.on_element_leave_window)
        
        self.update_elements_list()
        self.elements_list.Bind(wx.EVT_CONTEXT_MENU, self.on_element_context_menu)
        self.elements_list.Bind(wx.EVT_LEFT_DCLICK, self.on_element_dclick)
        self.elements_list.Bind(wx.EVT_KEY_DOWN, self.on_elements_key)
        elements_sizer.Add(self.elements_list, 1, wx.EXPAND | wx.ALL, 5)
        
        drag_help = wx.StaticText(self, label="Tip: Drag elements to reorder within their group, or to group headers to change group.")
        drag_help.SetForegroundColour(wx.Colour(100, 100, 100))
        elements_sizer.Add(drag_help, 0, wx.ALL, 5)
        self.main_sizer.Add(elements_sizer, 2, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(self.main_sizer)
        self.main_sizer.Fit(self)
        self.Layout()
        self.on_is_manual_changed(None) 

    def on_is_manual_changed(self, event):
        is_manual = self.is_manual_cb.GetValue()
        self.menu_data["is_manual"] = is_manual
        
        self.conditions_box_static.Enable(not is_manual)
        
        # Iterate through children of the sizer associated with the StaticBox
        if self.conditions_sizer: 
            for i in range(self.conditions_sizer.GetItemCount()):
                child_item = self.conditions_sizer.GetItem(i)
                if child_item and child_item.GetWindow():
                    # Don't disable the StaticBox itself again, only its contents
                    if child_item.GetWindow() != self.conditions_box_static:
                        child_item.GetWindow().Enable(not is_manual)
        
        self.profile_editor.mark_profile_changed()
        status = "manual (ignores conditions)" if is_manual else "conditional"
        try:
            # Use the stored profile_editor reference
            if self.profile_editor and self.profile_editor.statusbar:
                 self.profile_editor.statusbar.SetStatusText(f"Menu '{self.menu_id}' set to {status}")
        except Exception as e:
            print(f"Error setting status text from MenuPanel: {e}")


    def on_reset_group_changed(self, event):
        self.menu_data["reset_group"] = self.reset_group_ctrl.GetValue()
        self.profile_editor.mark_profile_changed()

    def on_add_menu_condition(self, condition_type_to_add):
        dialog = None
        parent_frame = self.profile_editor # Use the stored reference

        if condition_type_to_add == "pixel_color":
            dialog = PixelColorConditionDialog(parent_frame, "Add Menu Condition")
        elif condition_type_to_add == "pixel_region_color":
            dialog = RegionColorConditionDialog(parent_frame, "Add Menu Condition")
        elif condition_type_to_add == "pixel_region_image":
            dialog = RegionImageConditionDialog(parent_frame, "Add Menu Condition")
        elif condition_type_to_add == "ocr_text_match":
            dialog = OCRTextMatchConditionDialog(parent_frame, "Add Menu Condition")
        elif condition_type_to_add == "or":
            dialog = ORConditionDialog(parent_frame, "Add Menu OR Condition")

        if dialog:
            if dialog.ShowModal() == wx.ID_OK:
                condition = dialog.get_condition()
                if "conditions" not in self.menu_data: self.menu_data["conditions"] = []
                self.menu_data["conditions"].append(condition)
                self.update_conditions_list()
                self.profile_editor.mark_profile_changed()
            dialog.Destroy()

    def on_element_begin_drag(self, event): 
        item_idx, flags = self.elements_list.HitTest(event.GetPoint())
        if item_idx != -1:
            data_idx = self.elements_list.GetItemData(item_idx)
            if data_idx != -1: 
                self.drag_element_list_idx = item_idx
                self.drag_element_start_pos = event.GetPoint()
                self.dragging_element = False 
                event.Allow() 
            else: 
                event.Veto()
        else:
            event.Veto()

    def on_element_motion(self, event):
        if self.drag_element_list_idx is None or not event.Dragging():
            event.Skip(); return

        if not self.dragging_element:
            if abs(event.GetX() - self.drag_element_start_pos.x) > 5 or \
               abs(event.GetY() - self.drag_element_start_pos.y) > 5:
                self.dragging_element = True
                self.elements_list.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        
        if self.dragging_element:
            pos = event.GetPosition()
            item_over_idx, flags = self.elements_list.HitTest(pos)

            if self.drop_element_indicator_line is not None:
                self.elements_list.Refresh() 
                self.drop_element_indicator_line = None

            if item_over_idx != -1 and item_over_idx != self.drag_element_list_idx:
                self.drop_element_indicator_line = item_over_idx 
                rect = self.elements_list.GetItemRect(item_over_idx)
                dc = wx.ClientDC(self.elements_list)
                dc.SetPen(wx.Pen(wx.BLUE, 2))
                if pos.y < rect.y + rect.height / 2:
                    dc.DrawLine(rect.x, rect.y, rect.x + rect.width, rect.y)
                else:
                    dc.DrawLine(rect.x, rect.y + rect.height, rect.x + rect.width, rect.y + rect.height)
        event.Skip()
    
    def on_element_left_up(self, event):
        if self.dragging_element and self.drag_element_list_idx is not None:
            self.elements_list.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))

            if self.drop_element_indicator_line is not None:
                self.elements_list.Refresh() 

                src_data_idx = self.elements_list.GetItemData(self.drag_element_list_idx)
                drop_target_text = self.elements_list.GetItemText(self.drop_element_indicator_line)
                
                if drop_target_text.startswith("---") and drop_target_text.endswith("---"):
                    target_group_name = drop_target_text.strip("-").strip()
                    self.move_element_to_group(src_data_idx, target_group_name)
                else:
                    drop_target_data_idx = self.elements_list.GetItemData(self.drop_element_indicator_line)
                    if drop_target_data_idx != -1: 
                        rect = self.elements_list.GetItemRect(self.drop_element_indicator_line)
                        insert_before = event.GetY() < rect.y + rect.height / 2
                        self.move_element_relative(src_data_idx, drop_target_data_idx, insert_before)
                
                self.update_elements_list() 
                self.profile_editor.mark_profile_changed()

        self.dragging_element = False
        self.drag_element_list_idx = None
        self.drag_element_start_pos = None
        self.drop_element_indicator_line = None
        event.Skip()
    
    def on_element_leave_window(self, event):
        if self.dragging_element:
            self.elements_list.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
            if self.drop_element_indicator_line is not None:
                self.elements_list.Refresh() 
            self.dragging_element = False
            self.drag_element_list_idx = None
            self.drag_element_start_pos = None
            self.drop_element_indicator_line = None
        event.Skip()

    def move_element_to_group(self, src_data_idx, target_group_name):
        if src_data_idx < 0 or src_data_idx >= len(self.menu_data["items"]): return

        element_to_move = self.menu_data["items"][src_data_idx]
        
        original_group_of_moved_element = element_to_move[5] if len(element_to_move) > 5 and element_to_move[5] else "default"

        if len(element_to_move) <= 5:
            while len(element_to_move) < 5: element_to_move.append(None)
            element_to_move.append(target_group_name)
        else:
            element_to_move[5] = target_group_name
        
        new_display_idx = -10 
        if len(element_to_move) <= 8:
            while len(element_to_move) < 8: element_to_move.append(0) 
            element_to_move.append(new_display_idx)
        else:
            element_to_move[8] = new_display_idx
            
        self.reindex_group_elements(target_group_name) 
        if original_group_of_moved_element != target_group_name:
            self.reindex_group_elements(original_group_of_moved_element)


    def move_element_relative(self, src_data_idx, target_data_idx, insert_before):
        if src_data_idx < 0 or src_data_idx >= len(self.menu_data["items"]) or \
           target_data_idx < 0 or target_data_idx >= len(self.menu_data["items"]) or \
           src_data_idx == target_data_idx:
            return

        element_to_move = self.menu_data["items"][src_data_idx]
        target_element = self.menu_data["items"][target_data_idx]

        target_group = target_element[5] if len(target_element) > 5 and target_element[5] else "default"
        target_display_idx = target_element[8] if len(target_element) > 8 else 0

        original_group_of_moved_element = element_to_move[5] if len(element_to_move) > 5 and element_to_move[5] else "default"

        if len(element_to_move) <= 5:
            while len(element_to_move) < 5: element_to_move.append(None)
            element_to_move.append(target_group)
        else:
            element_to_move[5] = target_group
        
        new_display_idx = target_display_idx - 5 if insert_before else target_display_idx + 5
        if len(element_to_move) <= 8:
            while len(element_to_move) < 8: element_to_move.append(0)
            element_to_move.append(new_display_idx)
        else:
            element_to_move[8] = new_display_idx
            
        self.reindex_group_elements(target_group)
        if original_group_of_moved_element != target_group:
            self.reindex_group_elements(original_group_of_moved_element)
    
    def reindex_group_elements(self, group_name_to_reindex):
        items_in_group = []
        for i, item_data in enumerate(self.menu_data.get("items", [])):
            current_item_group = item_data[5] if len(item_data) > 5 and item_data[5] else "default"
            if current_item_group == group_name_to_reindex:
                items_in_group.append({
                    "original_data_idx": i, 
                    "current_display_idx": item_data[8] if len(item_data) > 8 else 0
                })
        
        items_in_group.sort(key=lambda x: x["current_display_idx"])
        
        for new_idx, item_info in enumerate(items_in_group):
            element_data = self.menu_data["items"][item_info["original_data_idx"]]
            new_val = new_idx * 10
            if len(element_data) <= 8:
                while len(element_data) < 8: element_data.append(0)
                element_data.append(new_val)
            else:
                element_data[8] = new_val
    
    def get_all_groups(self):
        group_order_indices = self.menu_data.get("group_order_indices", {"default": 0})
        item_groups = set(["default"])
        for item in self.menu_data.get("items", []):
            g = item[5] if len(item) > 5 and item[5] else "default"
            item_groups.add(g)
            if g not in group_order_indices: 
                max_idx = max(group_order_indices.values() or [-10]) + 10
                group_order_indices[g] = max_idx
        
        sorted_group_names = sorted(group_order_indices.keys(), key=lambda g: group_order_indices.get(g, float('inf')))
        return sorted_group_names
    
    def on_manage_groups(self, event):
        dialog = GroupManagerDialog(self, self.menu_data, self.menu_id)
        if dialog.ShowModal() == wx.ID_OK:
            self.update_elements_list() 
            self.update_reset_group_options() 
            self.profile_editor.mark_profile_changed()
        dialog.Destroy()
    
    def refresh_entire_panel(self):
        self.update_reset_group_options()
        self.rebuild_group_filter()
        self.update_elements_list()
        self.update_conditions_list()
        self.Layout()
        self.Refresh()
    
    def rebuild_group_filter(self):
        old_selection_str = self.group_filter.GetStringSelection()
        fresh_groups = self.get_all_groups()
        self.group_filter.Clear()
        self.group_filter.Append("All Groups")
        self.group_filter.AppendItems(fresh_groups)
        if old_selection_str in fresh_groups:
            self.group_filter.SetStringSelection(old_selection_str)
        else:
            self.group_filter.SetSelection(0)
    
    def on_group_filter_changed(self, event):
        self.update_elements_list()
    
    def on_rename_menu(self, event):
        self.profile_editor.on_rename_menu(event)
        
    def on_duplicate_menu(self, event):
        self.profile_editor.on_duplicate_menu(event)
    
    def on_conditions_key(self, event):
        key_code = event.GetKeyCode()
        is_ctrl = event.ControlDown()
        if is_ctrl and key_code == ord('C'): self.on_copy_condition(None)
        elif is_ctrl and key_code == ord('V'): self.on_paste_condition(None)
        elif is_ctrl and key_code == ord('A'): self.select_all_conditions()
        elif key_code == wx.WXK_DELETE: self.on_delete_condition(None)
        else: event.Skip()
    
    def select_all_conditions(self):
        for i in range(self.conditions_list.GetItemCount()):
            self.conditions_list.Select(i, True) 
    
    def on_elements_key(self, event):
        key_code = event.GetKeyCode()
        is_ctrl = event.ControlDown()
        if is_ctrl and key_code == ord('C'): self.on_copy_element(None)
        elif is_ctrl and key_code == ord('V'): self.on_paste_element(None)
        elif is_ctrl and key_code == ord('A'): self.select_all_elements()
        elif key_code == wx.WXK_DELETE: self.on_delete_element(None)
        else: event.Skip()
    
    def select_all_elements(self):
        for i in range(self.elements_list.GetItemCount()):
            if self.elements_list.GetItemData(i) != -1: 
                self.elements_list.Select(i, True)
    
    def on_key_down(self, event): event.Skip()
    
    def on_condition_dclick(self, event): self.on_edit_condition(event)
    
    def on_element_dclick(self, event):
        if self.dragging_element: return 
        self.on_edit_element(event)
    
    def update_reset_group_options(self):
        groups = self.get_all_groups()
        current_value = self.reset_group_ctrl.GetValue()
        self.reset_group_ctrl.Clear()
        self.reset_group_ctrl.AppendItems(groups)
        if current_value in groups: self.reset_group_ctrl.SetValue(current_value)
        elif groups: self.reset_group_ctrl.SetValue(groups[0]) 
        else: self.reset_group_ctrl.SetValue("default") 
    
    def update_conditions_list(self):
        self.conditions_list.DeleteAllItems()
        if "conditions" not in self.menu_data: return
        for i, condition in enumerate(self.menu_data["conditions"]):
            condition_type = condition.get("type", "unknown")
            details = "" 
            if condition_type == "pixel_color": details = f"({condition['x']},{condition['y']}) RGB{condition['color']} Tol:{condition['tolerance']}"
            elif condition_type == "pixel_region_color": details = f"Region({condition['x1']},{condition['y1']}-{condition['x2']},{condition['y2']}) RGB{condition['color']} Tol:{condition['tolerance']} Thresh:{condition['threshold']}"
            elif condition_type == "pixel_region_image": details = f"Region({condition['x1']},{condition['y1']}-{condition['x2']},{condition['y2']}) Conf:{condition['confidence']:.2f} Img:{'Yes' if condition.get('image_data') else 'No'}"
            elif condition_type == "ocr_text_match": details = f"Region({condition['x1']},{condition['y1']}-{condition['x2']},{condition['y2']}) Text: '{condition.get('expected_text','')[:20]}...'"
            elif condition_type == "or": details = f"OR (Sub1: {condition['conditions'][0].get('type', 'N/A')}, Sub2: {condition['conditions'][1].get('type', 'N/A')})"
            else: details = str(condition)[:50]
            if condition.get("negate"): details = "NOT " + details
            
            idx = self.conditions_list.InsertItem(i, condition_type)
            self.conditions_list.SetItem(idx, 1, details)
    
    def update_elements_list(self):
        self.elements_list.DeleteAllItems()
        if "items" not in self.menu_data: return
        
        filter_idx = self.group_filter.GetSelection()
        selected_group_filter = None
        if filter_idx > 0: selected_group_filter = self.group_filter.GetString(filter_idx)
        
        ordered_groups = self.get_all_groups() 

        list_ctrl_idx = 0
        for group_name in ordered_groups:
            if selected_group_filter and group_name != selected_group_filter:
                continue

            header_text = f"--- {group_name} ---"
            header_list_idx = self.elements_list.InsertItem(list_ctrl_idx, header_text)
            self.elements_list.SetItemTextColour(header_list_idx, wx.Colour(0, 0, 128))
            self.elements_list.SetItemBackgroundColour(header_list_idx, wx.Colour(200, 220, 255))
            self.elements_list.SetItemFont(header_list_idx, wx.Font(wx.NORMAL_FONT.GetPointSize(), wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            self.elements_list.SetItemData(header_list_idx, -1) 
            list_ctrl_idx += 1

            items_in_this_group = []
            for original_data_idx, element_data in enumerate(self.menu_data["items"]):
                el_group = element_data[5] if len(element_data) > 5 and element_data[5] else "default"
                if el_group == group_name:
                    display_idx = element_data[8] if len(element_data) > 8 else 0
                    items_in_this_group.append({"data": element_data, "original_idx": original_data_idx, "display_idx": display_idx})
            
            items_in_this_group.sort(key=lambda x: x["display_idx"])

            for item_info in items_in_this_group:
                element = item_info["data"]
                el_list_idx = self.elements_list.InsertItem(list_ctrl_idx, element[1]) 
                self.elements_list.SetItem(el_list_idx, 1, element[2]) 
                self.elements_list.SetItem(el_list_idx, 2, f"({element[0][0]},{element[0][1]})") 
                self.elements_list.SetItem(el_list_idx, 3, group_name) 
                self.elements_list.SetItem(el_list_idx, 4, str(element[4] or "")) 
                ocr_count = len(element[6]) if len(element) > 6 and element[6] else 0
                self.elements_list.SetItem(el_list_idx, 5, str(ocr_count) if ocr_count else "") 
                has_custom_fmt = len(element) > 7 and element[7]
                self.elements_list.SetItem(el_list_idx, 6, "Yes" if has_custom_fmt else "") 
                self.elements_list.SetItem(el_list_idx, 7, str(element[8] if len(element) > 8 else 0)) 
                cond_count = len(element[9]) if len(element) > 9 and element[9] else 0
                self.elements_list.SetItem(el_list_idx, 8, str(cond_count) if cond_count else "") 
                self.elements_list.SetItemData(el_list_idx, item_info["original_idx"])
                list_ctrl_idx += 1
        
        self.Layout() 
    
    def on_condition_context_menu(self, event):
        selected_count = self.conditions_list.GetSelectedItemCount()
        if selected_count == 0: return
        menu = wx.Menu()
        if selected_count == 1:
            edit_item = menu.Append(wx.ID_ANY, "Edit Condition"); self.Bind(wx.EVT_MENU, self.on_edit_condition, edit_item)
        else: 
            edit_item = menu.Append(wx.ID_ANY, f"Bulk Edit {selected_count} Conditions..."); self.Bind(wx.EVT_MENU, self.on_bulk_edit_conditions, edit_item)
        menu.AppendSeparator()
        copy_item = menu.Append(wx.ID_ANY, "Copy Condition(s)"); self.Bind(wx.EVT_MENU, self.on_copy_condition, copy_item)
        delete_item = menu.Append(wx.ID_ANY, "Delete Condition(s)"); self.Bind(wx.EVT_MENU, self.on_delete_condition, delete_item)
        menu.AppendSeparator()
        paste_item = menu.Append(wx.ID_ANY, "Paste Condition(s)"); self.Bind(wx.EVT_MENU, self.on_paste_condition, paste_item)
        self.PopupMenu(menu); menu.Destroy()
    
    def on_copy_condition(self, event):
        self.profile_editor.clipboard['conditions'] = []
        item_idx = -1
        count = 0
        while True:
            item_idx = self.conditions_list.GetNextItem(item_idx, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if item_idx == -1: break
            condition = copy.deepcopy(self.menu_data["conditions"][item_idx])
            self.profile_editor.clipboard['conditions'].append(condition)
            count +=1
        if count > 0 and self.profile_editor.statusbar: self.profile_editor.statusbar.SetStatusText(f"Copied {count} condition(s)")

    def on_paste_condition(self, event):
        if not self.profile_editor.clipboard['conditions']:
            wx.MessageBox("No conditions in clipboard", "Cannot Paste", wx.ICON_INFORMATION); return
        
        if "conditions" not in self.menu_data: self.menu_data["conditions"] = []
        
        insert_after_idx = self.conditions_list.GetFirstSelected() 
        
        pasted_count = 0
        for i, condition_to_paste in enumerate(self.profile_editor.clipboard['conditions']):
            if insert_after_idx != -1:
                self.menu_data["conditions"].insert(insert_after_idx + 1 + i, copy.deepcopy(condition_to_paste))
            else: 
                self.menu_data["conditions"].append(copy.deepcopy(condition_to_paste))
            pasted_count += 1
            
        self.update_conditions_list()
        self.profile_editor.mark_profile_changed()
        if pasted_count > 0 and self.profile_editor.statusbar: self.profile_editor.statusbar.SetStatusText(f"Pasted {pasted_count} condition(s)")
    
    def on_edit_condition(self, event):
        selected_idx = self.conditions_list.GetFirstSelected()
        if selected_idx == -1: return
        condition = self.menu_data["conditions"][selected_idx]
        condition_type = condition.get("type")
        dialog = None; parent_frame = self.profile_editor 
        if condition_type == "pixel_color": dialog = PixelColorConditionDialog(parent_frame, "Edit Menu Condition", condition=condition)
        elif condition_type == "pixel_region_color": dialog = RegionColorConditionDialog(parent_frame, "Edit Menu Condition", condition=condition)
        elif condition_type == "pixel_region_image": dialog = RegionImageConditionDialog(parent_frame, "Edit Menu Condition", condition=condition)
        elif condition_type == "ocr_text_match": dialog = OCRTextMatchConditionDialog(parent_frame, "Edit Menu Condition", condition=condition)
        elif condition_type == "or": dialog = ORConditionDialog(parent_frame, "Edit Menu OR Condition", condition=condition)
        else: wx.MessageBox(f"Cannot edit condition type: {condition_type}", "Error", wx.ICON_ERROR); return
        
        if dialog.ShowModal() == wx.ID_OK:
            self.menu_data["conditions"][selected_idx] = dialog.get_condition()
            self.update_conditions_list()
            self.profile_editor.mark_profile_changed()
        dialog.Destroy()
    
    def on_delete_condition(self, event):
        if self.conditions_list.GetSelectedItemCount() == 0: return
        selected_indices = []
        item_idx = -1
        while True:
            item_idx = self.conditions_list.GetNextItem(item_idx, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if item_idx == -1: break
            selected_indices.append(item_idx)
        
        if not selected_indices: return
        prompt = f"Delete {len(selected_indices)} condition(s)?"
        if wx.MessageBox(prompt, "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) != wx.YES: return
        
        for idx in sorted(selected_indices, reverse=True):
            del self.menu_data["conditions"][idx]
        
        self.update_conditions_list()
        self.profile_editor.mark_profile_changed()
        if self.profile_editor.statusbar: self.profile_editor.statusbar.SetStatusText(f"Deleted {len(selected_indices)} condition(s)")
    
    def on_add_element(self, event):
        dialog = UIElementDialog(self.profile_editor, title="Add UI Element") 
        if dialog.ShowModal() == wx.ID_OK:
            element = dialog.get_element()
            if "items" not in self.menu_data: self.menu_data["items"] = []
            
            filter_sel_idx = self.group_filter.GetSelection()
            target_group = "default"
            if filter_sel_idx > 0: 
                target_group = self.group_filter.GetString(filter_sel_idx)
            
            if len(element) <= 5: element.append(target_group)
            else: element[5] = target_group

            max_idx_in_group = -1
            for item_data in self.menu_data["items"]:
                item_group = item_data[5] if len(item_data) > 5 and item_data[5] else "default"
                if item_group == target_group:
                    item_display_idx = item_data[8] if len(item_data) > 8 else 0
                    max_idx_in_group = max(max_idx_in_group, item_display_idx)
            
            new_display_idx = max_idx_in_group + 10
            if len(element) <= 8:
                while len(element) < 8: element.append(0)
                element.append(new_display_idx)
            else:
                element[8] = new_display_idx

            self.menu_data["items"].append(element)
            self.refresh_entire_panel()
            self.profile_editor.mark_profile_changed()
        dialog.Destroy()
    
    def on_element_context_menu(self, event):
        selected_count = self.elements_list.GetSelectedItemCount()
        if selected_count == 0: return
        
        item_idx = -1; has_non_elements = False
        while True:
            item_idx = self.elements_list.GetNextItem(item_idx, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if item_idx == -1: break
            if self.elements_list.GetItemData(item_idx) == -1: has_non_elements = True; break
        if has_non_elements: return 

        menu = wx.Menu()
        if selected_count == 1:
            edit_item = menu.Append(wx.ID_ANY, "Edit Element"); self.Bind(wx.EVT_MENU, self.on_edit_element, edit_item)
        else:
            edit_item = menu.Append(wx.ID_ANY, f"Bulk Edit {selected_count} Elements..."); self.Bind(wx.EVT_MENU, self.on_bulk_edit_elements, edit_item)
        menu.AppendSeparator()
        copy_item = menu.Append(wx.ID_ANY, "Copy Element(s)"); self.Bind(wx.EVT_MENU, self.on_copy_element, copy_item)
        delete_item = menu.Append(wx.ID_ANY, "Delete Element(s)"); self.Bind(wx.EVT_MENU, self.on_delete_element, delete_item)
        menu.AppendSeparator()
        paste_item = menu.Append(wx.ID_ANY, "Paste Element(s)"); self.Bind(wx.EVT_MENU, self.on_paste_element, paste_item)
        self.PopupMenu(menu); menu.Destroy()
    
    def on_copy_element(self, event):
        self.profile_editor.clipboard['elements'] = []
        item_idx = -1; count = 0
        while True:
            item_idx = self.elements_list.GetNextItem(item_idx, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if item_idx == -1: break
            data_idx = self.elements_list.GetItemData(item_idx)
            if data_idx != -1: 
                element = copy.deepcopy(self.menu_data["items"][data_idx])
                self.profile_editor.clipboard['elements'].append(element)
                count += 1
        if count > 0 and self.profile_editor.statusbar: self.profile_editor.statusbar.SetStatusText(f"Copied {count} element(s)")

    def on_paste_element(self, event):
        if not self.profile_editor.clipboard['elements']:
            wx.MessageBox("No elements in clipboard", "Cannot Paste", wx.ICON_INFORMATION); return
        if "items" not in self.menu_data: self.menu_data["items"] = []

        last_selected_list_idx = -1
        item_idx = -1
        while True: 
            item_idx = self.elements_list.GetNextItem(item_idx, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if item_idx == -1: break
            last_selected_list_idx = item_idx
        
        insert_after_data_idx = -1
        target_group_for_pasted = "default" 
        current_max_display_idx_in_target_group = -10 

        if last_selected_list_idx != -1:
            data_idx_of_last_selected = self.elements_list.GetItemData(last_selected_list_idx)
            if data_idx_of_last_selected != -1: 
                insert_after_data_idx = data_idx_of_last_selected
                target_element = self.menu_data["items"][data_idx_of_last_selected]
                target_group_for_pasted = target_element[5] if len(target_element) > 5 and target_element[5] else "default"
                current_max_display_idx_in_target_group = target_element[8] if len(target_element) > 8 else 0
            else: 
                header_text = self.elements_list.GetItemText(last_selected_list_idx)
                if header_text.startswith("---"):
                    target_group_for_pasted = header_text.strip("-").strip()
                min_idx_in_group = float('inf')
                found_group_items = False
                for item_d in self.menu_data["items"]:
                    item_g = item_d[5] if len(item_d) > 5 and item_d[5] else "default"
                    if item_g == target_group_for_pasted:
                        found_group_items = True
                        min_idx_in_group = min(min_idx_in_group, item_d[8] if len(item_d) > 8 else 0)
                current_max_display_idx_in_target_group = min_idx_in_group - 10 if found_group_items else -10
        else: 
            if self.menu_data["items"]:
                 last_item = self.menu_data["items"][-1]
                 target_group_for_pasted = last_item[5] if len(last_item) > 5 and last_item[5] else "default"
                 current_max_display_idx_in_target_group = last_item[8] if len(last_item) > 8 else 0

        pasted_count = 0
        for element_to_paste_orig in self.profile_editor.clipboard['elements']:
            element_to_paste = copy.deepcopy(element_to_paste_orig)
            if len(element_to_paste) <= 5: element_to_paste.append(target_group_for_pasted)
            else: element_to_paste[5] = target_group_for_pasted
            
            current_max_display_idx_in_target_group += 10 
            if len(element_to_paste) <= 8:
                while len(element_to_paste) < 8: element_to_paste.append(0)
                element_to_paste.append(current_max_display_idx_in_target_group)
            else:
                element_to_paste[8] = current_max_display_idx_in_target_group
            
            self.menu_data["items"].append(element_to_paste)
            pasted_count += 1
        
        self.reindex_group_elements(target_group_for_pasted) 
        self.refresh_entire_panel()
        self.profile_editor.mark_profile_changed()
        if pasted_count > 0 and self.profile_editor.statusbar: self.profile_editor.statusbar.SetStatusText(f"Pasted {pasted_count} element(s)")
    
    def on_edit_element(self, event):
        selected_item_list_idx = self.elements_list.GetFirstSelected()
        if selected_item_list_idx == -1: return
        orig_data_idx = self.elements_list.GetItemData(selected_item_list_idx)
        if orig_data_idx == -1: return 
            
        element = self.menu_data["items"][orig_data_idx]
        dialog = UIElementDialog(self.profile_editor, title="Edit UI Element", element=element)
        if dialog.ShowModal() == wx.ID_OK:
            self.menu_data["items"][orig_data_idx] = dialog.get_element()
            self.refresh_entire_panel()
            self.profile_editor.mark_profile_changed()
        dialog.Destroy()
    
    def on_delete_element(self, event):
        if self.elements_list.GetSelectedItemCount() == 0: return
        selected_data_indices = []
        item_idx = -1
        while True:
            item_idx = self.elements_list.GetNextItem(item_idx, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if item_idx == -1: break
            data_idx = self.elements_list.GetItemData(item_idx)
            if data_idx != -1: selected_data_indices.append(data_idx)
        
        if not selected_data_indices: return
        prompt = f"Delete {len(selected_data_indices)} element(s)?"
        if wx.MessageBox(prompt, "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) != wx.YES: return
        
        for data_idx_to_delete in sorted(selected_data_indices, reverse=True):
            if 0 <= data_idx_to_delete < len(self.menu_data["items"]):
                del self.menu_data["items"][data_idx_to_delete]
        
        self.refresh_entire_panel()
        self.profile_editor.mark_profile_changed()
        if self.profile_editor.statusbar: self.profile_editor.statusbar.SetStatusText(f"Deleted {len(selected_data_indices)} element(s)")
    
    def on_save(self):
        self.menu_data["reset_index"] = self.reset_index_cb.GetValue()
        self.menu_data["reset_group"] = self.reset_group_ctrl.GetValue()
        self.menu_data["is_manual"] = self.is_manual_cb.GetValue()
        return True
        
    def on_delete_menu(self, event):
        if wx.MessageBox(f"Delete menu '{self.menu_id}'?", "Confirm", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            self.profile_editor.delete_menu(self.menu_id)
    
    def on_bulk_edit_elements(self, event):
        selected_data_indices = []
        item_idx = -1
        while True:
            item_idx = self.elements_list.GetNextItem(item_idx, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if item_idx == -1: break
            data_idx = self.elements_list.GetItemData(item_idx)
            if data_idx != -1: selected_data_indices.append(data_idx)
        if not selected_data_indices: return
            
        dialog = BulkEditElementsDialog(self.profile_editor) 
        all_menu_groups = self.get_all_groups()
        dialog.group_ctrl.SetItems(all_menu_groups)
        if dialog.group_ctrl.GetCount() > 0: dialog.group_ctrl.SetSelection(0)

        if dialog.ShowModal() == wx.ID_OK:
            changes = dialog.get_bulk_changes()
            if not changes: dialog.Destroy(); return
            
            modified_count = 0
            affected_groups = set()
            for data_idx in selected_data_indices:
                if 0 <= data_idx < len(self.menu_data["items"]):
                    element = self.menu_data["items"][data_idx]
                    original_group = element[5] if len(element) > 5 and element[5] else "default"
                    affected_groups.add(original_group)

                    if 'type' in changes: element[2] = changes['type']
                    if 'speaks_on_select' in changes: element[3] = changes['speaks_on_select']
                    if 'submenu_id' in changes: element[4] = changes['submenu_id']
                    if 'group' in changes:
                        new_group = changes['group']
                        if len(element) <= 5: element.append(new_group)
                        else: element[5] = new_group
                        affected_groups.add(new_group)
                    if changes.get('clear_announcement'):
                        if len(element) <= 7: element.append(None)
                        else: element[7] = None
                    if changes.get('clear_ocr'):
                        if len(element) <= 6: element.append([])
                        else: element[6] = []
                    modified_count += 1
            
            for group_to_reindex in affected_groups:
                self.reindex_group_elements(group_to_reindex)

            self.refresh_entire_panel()
            self.profile_editor.mark_profile_changed()
            if modified_count > 0 and self.profile_editor.statusbar: self.profile_editor.statusbar.SetStatusText(f"Bulk edited {modified_count} element(s)")
        dialog.Destroy()
        
    def on_bulk_edit_conditions(self, event):
        selected_indices_in_list = [] 
        item_idx = -1
        while True:
            item_idx = self.conditions_list.GetNextItem(item_idx, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if item_idx == -1: break
            selected_indices_in_list.append(item_idx)
        if not selected_indices_in_list: return

        compatible_indices = []
        for list_idx in selected_indices_in_list:
            cond_type = self.menu_data["conditions"][list_idx].get("type")
            if cond_type in ["pixel_color", "pixel_region_color"]: 
                compatible_indices.append(list_idx)
        
        if not compatible_indices:
            wx.MessageBox("Selected conditions are not compatible for this bulk edit (only pixel/region color).", "Bulk Edit", wx.ICON_INFORMATION); return

        dialog = BulkEditConditionsDialog(self.profile_editor) 
        if dialog.ShowModal() == wx.ID_OK:
            changes = dialog.get_bulk_changes()
            if not changes: dialog.Destroy(); return
            
            modified_count = 0
            for list_idx in compatible_indices: 
                condition = self.menu_data["conditions"][list_idx]
                if 'color' in changes: condition['color'] = changes['color']
                if 'tolerance' in changes: condition['tolerance'] = changes['tolerance']
                modified_count += 1
            
            self.update_conditions_list()
            self.profile_editor.mark_profile_changed()
            if modified_count > 0 and self.profile_editor.statusbar: self.profile_editor.statusbar.SetStatusText(f"Bulk edited {modified_count} condition(s)")
        dialog.Destroy()
    
    def on_reset_index_changed(self, event):
        self.menu_data["reset_index"] = self.reset_index_cb.GetValue()
        self.profile_editor.mark_profile_changed()
        value = "will reset" if self.reset_index_cb.GetValue() else "will maintain"
        try: 
            if self.profile_editor and self.profile_editor.statusbar:
                self.profile_editor.statusbar.SetStatusText(f"Menu '{self.menu_id}' {value} selection index")
        except: pass