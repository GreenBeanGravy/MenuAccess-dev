"""
Menu panel for editing menu data
"""

import wx
import wx.lib.scrolledpanel as scrolled

from pflib.dialogs import PixelColorConditionDialog, RegionColorConditionDialog, UIElementDialog

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