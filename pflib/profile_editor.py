"""
Profile Editor - Main application frame
"""

import wx
import wx.adv
import json
import os
import time
import threading
import numpy as np
import pyautogui
import copy

from pflib.utils import APP_TITLE, APP_VERSION
from pflib.menu_panel import MenuPanel
from pflib.menu_condition import MenuCondition

class ProfileEditorFrame(wx.Frame):
    """Main frame for the profile editor application"""
    
    def __init__(self, parent, title):
        super().__init__(parent, title=f"{title} v{APP_VERSION}", size=(800, 700))
        
        self.profile_data = {}
        self.current_file = None
        self.is_changed = False
        self.clipboard = {
            'menu': None,
            'conditions': [],  # Now a list for multiple items
            'elements': []     # Now a list for multiple items
        }
        
        self.init_ui()
        
        # Create a global keyboard shortcut table
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('S'), wx.ID_SAVE),
        ])
        self.SetAcceleratorTable(accel_tbl)
        
        # Bind keyboard events
        self.Bind(wx.EVT_MENU, self.on_save, id=wx.ID_SAVE)
        
        self.Center()
        
        # Initialize with default main_menu
        self.add_menu("main_menu")
        
    def init_ui(self):
        panel = wx.Panel(self)
        
        # Menu Bar
        menubar = wx.MenuBar()
        
        # File Menu
        file_menu = wx.Menu()
        new_item = file_menu.Append(wx.ID_NEW, "New Profile", "Create a new profile")
        open_item = file_menu.Append(wx.ID_OPEN, "Open Profile", "Open an existing profile")
        save_item = file_menu.Append(wx.ID_SAVE, "Save Profile\tCtrl+S", "Save current profile")
        save_as_item = file_menu.Append(wx.ID_SAVEAS, "Save Profile As", "Save current profile with a new name")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "Exit", "Exit the application")
        
        # Edit Menu
        edit_menu = wx.Menu()
        copy_menu_item = edit_menu.Append(wx.ID_ANY, "Copy Menu\tCtrl+Shift+C", "Copy the current menu")
        duplicate_menu_item = edit_menu.Append(wx.ID_ANY, "Duplicate Menu", "Duplicate the current menu")
        rename_menu_item = edit_menu.Append(wx.ID_ANY, "Rename Menu", "Rename the current menu")
        
        # Tools Menu
        tools_menu = wx.Menu()
        test_item = tools_menu.Append(wx.ID_ANY, "Test Current Menu", "Test the detection of the current menu")
        export_py_item = tools_menu.Append(wx.ID_ANY, "Export as Python", "Export profile as Python code")
        
        # Help Menu
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "About", "About this application")
        
        # Bind file menu events
        self.Bind(wx.EVT_MENU, self.on_new, new_item)
        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        self.Bind(wx.EVT_MENU, self.on_save, save_item)
        self.Bind(wx.EVT_MENU, self.on_save_as, save_as_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        
        # Bind edit menu events
        self.Bind(wx.EVT_MENU, self.on_copy_menu_menu_item, copy_menu_item)
        self.Bind(wx.EVT_MENU, self.on_duplicate_menu, duplicate_menu_item)
        self.Bind(wx.EVT_MENU, self.on_rename_menu, rename_menu_item)
        
        # Bind tools menu events
        self.Bind(wx.EVT_MENU, self.on_test_menu, test_item)
        self.Bind(wx.EVT_MENU, self.on_export_python, export_py_item)
        
        # Bind help menu events
        self.Bind(wx.EVT_MENU, self.on_about, about_item)
        
        menubar.Append(file_menu, "&File")
        menubar.Append(edit_menu, "&Edit")
        menubar.Append(tools_menu, "&Tools")
        menubar.Append(help_menu, "&Help")
        self.SetMenuBar(menubar)
        
        # Main layout
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Top controls for adding menus
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        menu_label = wx.StaticText(panel, label="Menu ID:")
        self.menu_id_ctrl = wx.TextCtrl(panel)
        add_menu_btn = wx.Button(panel, label="Add Menu")
        add_menu_btn.Bind(wx.EVT_BUTTON, self.on_add_menu)
        
        top_sizer.Add(menu_label, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_sizer.Add(self.menu_id_ctrl, proportion=1, flag=wx.RIGHT, border=5)
        top_sizer.Add(add_menu_btn)
        
        main_sizer.Add(top_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Notebook for menus
        self.notebook = wx.Notebook(panel)
        main_sizer.Add(self.notebook, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        
        panel.SetSizer(main_sizer)
        
        # Status Bar
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText("New Profile")
        
        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)
    
    def on_copy_menu_menu_item(self, event):
        """Handle copy menu menu item"""
        self.copy_current_menu()
    
    def on_duplicate_menu(self, event):
        """Duplicate the current menu"""
        # First copy the menu
        self.copy_current_menu()
        
        # Then paste it with a suggested name
        if not self.clipboard['menu']:
            wx.MessageBox("No menu to duplicate", "Cannot Duplicate", wx.ICON_INFORMATION)
            return
        
        # Get original menu ID and data
        orig_id = self.clipboard['menu']['id']
        menu_data = copy.deepcopy(self.clipboard['menu']['data'])
        
        # Create a suggested name
        suggested_name = f"{orig_id}_copy"
        counter = 1
        while suggested_name in self.profile_data:
            suggested_name = f"{orig_id}_copy{counter}"
            counter += 1
        
        # Ask for new menu ID
        dialog = wx.TextEntryDialog(
            self, 
            f"Enter name for the duplicated menu (original: {orig_id}):",
            "Duplicate Menu", 
            suggested_name
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            new_id = dialog.GetValue().strip()
            dialog.Destroy()
            
            if not new_id:
                wx.MessageBox("Menu ID cannot be empty", "Error", wx.ICON_ERROR)
                return
                
            if new_id in self.profile_data:
                if wx.MessageBox(f"Menu '{new_id}' already exists. Replace it?", 
                              "Confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES:
                    return
                
                # Remove existing tab for this menu
                self.delete_menu(new_id)
            
            # Add the new menu with copied data
            self.profile_data[new_id] = menu_data
            menu_panel = MenuPanel(self.notebook, new_id, self.profile_data[new_id], self)
            self.notebook.AddPage(menu_panel, new_id)
            self.notebook.SetSelection(self.notebook.GetPageCount() - 1)
            
            self.mark_profile_changed()
            self.statusbar.SetStatusText(f"Duplicated menu as: {new_id}")
        else:
            dialog.Destroy()
    
    def on_rename_menu(self, event):
        """Rename the current menu"""
        current_tab = self.notebook.GetSelection()
        if current_tab == -1:
            wx.MessageBox("No menu selected", "Cannot Rename", wx.ICON_INFORMATION)
            return
            
        menu_panel = self.notebook.GetPage(current_tab)
        old_id = menu_panel.menu_id
        
        # Ask for new menu ID
        dialog = wx.TextEntryDialog(
            self, 
            f"Enter new name for the menu (current: {old_id}):",
            "Rename Menu", 
            old_id
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            new_id = dialog.GetValue().strip()
            dialog.Destroy()
            
            if not new_id:
                wx.MessageBox("Menu ID cannot be empty", "Error", wx.ICON_ERROR)
                return
                
            if new_id == old_id:
                # No change
                return
                
            if new_id in self.profile_data:
                if wx.MessageBox(f"Menu '{new_id}' already exists. Replace it?", 
                              "Confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES:
                    return
                
                # Remove existing tab for this menu
                self.delete_menu(new_id)
            
            # Get the menu data
            menu_data = self.profile_data[old_id]
            
            # Remove the old menu
            del self.profile_data[old_id]
            
            # Add with new ID
            self.profile_data[new_id] = menu_data
            
            # Update the tab
            self.notebook.DeletePage(current_tab)
            menu_panel = MenuPanel(self.notebook, new_id, self.profile_data[new_id], self)
            self.notebook.InsertPage(current_tab, menu_panel, new_id)
            self.notebook.SetSelection(current_tab)
            
            self.mark_profile_changed()
            self.statusbar.SetStatusText(f"Renamed menu from {old_id} to {new_id}")
        else:
            dialog.Destroy()
    
    def copy_current_menu(self):
        """Copy the currently selected menu"""
        current_tab = self.notebook.GetSelection()
        if current_tab == -1:
            return
            
        menu_panel = self.notebook.GetPage(current_tab)
        menu_id = menu_panel.menu_id
        
        # Make a deep copy to avoid reference issues
        self.clipboard['menu'] = {
            'id': menu_id,
            'data': copy.deepcopy(self.profile_data[menu_id])
        }
        
        self.statusbar.SetStatusText(f"Copied menu: {menu_id}")

    def paste_menu(self):
        """Paste a previously copied menu"""
        if not self.clipboard['menu']:
            wx.MessageBox("No menu in clipboard", "Cannot Paste", wx.ICON_INFORMATION)
            return
        
        # Get original menu ID and data
        orig_id = self.clipboard['menu']['id']
        menu_data = copy.deepcopy(self.clipboard['menu']['data'])
        
        # Ask for new menu ID
        dialog = wx.TextEntryDialog(
            self, 
            f"Enter new ID for the copied menu (original: {orig_id}):",
            "Paste Menu", 
            f"{orig_id}_copy"
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            new_id = dialog.GetValue().strip()
            dialog.Destroy()
            
            if not new_id:
                wx.MessageBox("Menu ID cannot be empty", "Error", wx.ICON_ERROR)
                return
                
            if new_id in self.profile_data:
                if wx.MessageBox(f"Menu '{new_id}' already exists. Replace it?", 
                              "Confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES:
                    return
                
                # Remove existing tab for this menu
                self.delete_menu(new_id)
            
            # Add the new menu with copied data
            self.profile_data[new_id] = menu_data
            menu_panel = MenuPanel(self.notebook, new_id, self.profile_data[new_id], self)
            self.notebook.AddPage(menu_panel, new_id)
            self.notebook.SetSelection(self.notebook.GetPageCount() - 1)
            
            self.mark_profile_changed()
            self.statusbar.SetStatusText(f"Pasted menu as: {new_id}")
        else:
            dialog.Destroy()
    
    def on_add_menu(self, event):
        """Add a new menu to the profile"""
        menu_id = self.menu_id_ctrl.GetValue().strip()
        
        if not menu_id:
            wx.MessageBox("Please enter a menu ID", "Error", wx.ICON_ERROR)
            return
            
        if menu_id in self.profile_data:
            wx.MessageBox(f"Menu '{menu_id}' already exists", "Error", wx.ICON_ERROR)
            return
            
        self.add_menu(menu_id)
        self.menu_id_ctrl.Clear()
    
    def add_menu(self, menu_id):
        """Add a menu to the profile and create a tab for it"""
        self.profile_data[menu_id] = {
            "conditions": [],
            "items": []
        }
        
        menu_panel = MenuPanel(self.notebook, menu_id, self.profile_data[menu_id], self)
        self.notebook.AddPage(menu_panel, menu_id)
        self.notebook.SetSelection(self.notebook.GetPageCount() - 1)
        
        self.mark_profile_changed()
    
    def delete_menu(self, menu_id):
        """Delete a menu from the profile and remove its tab"""
        if menu_id not in self.profile_data:
            return
            
        # Find the tab index
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if hasattr(page, 'menu_id') and page.menu_id == menu_id:
                self.notebook.DeletePage(i)
                break
        
        # Remove from profile data
        del self.profile_data[menu_id]
        self.mark_profile_changed()
    
    def mark_profile_changed(self):
        """Mark the profile as changed and update UI accordingly"""
        self.is_changed = True
        
        # Update title bar
        title = self.GetTitle()
        if not title.startswith('*'):
            self.SetTitle('*' + title)
            
        # Update status bar
        filename = self.current_file or "New Profile"
        self.statusbar.SetStatusText(f"Modified: {filename}")
    
    def on_new(self, event):
        """Create a new profile"""
        if self.is_changed:
            if wx.MessageBox("Current profile has unsaved changes. Continue?", 
                           "Please confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES:
                return
        
        self.profile_data = {}
        self.current_file = None
        self.is_changed = False
        
        # Clear notebook
        while self.notebook.GetPageCount() > 0:
            self.notebook.DeletePage(0)
        
        # Add default main menu
        self.add_menu("main_menu")
        
        # Update UI
        self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - New Profile")
        self.statusbar.SetStatusText("New Profile")
    
    def on_open(self, event):
        """Open an existing profile"""
        if self.is_changed:
            if wx.MessageBox("Current profile has unsaved changes. Continue?", 
                           "Please confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES:
                return
        
        with wx.FileDialog(self, "Open Profile", wildcard="JSON files (*.json)|*.json",
                         style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            
            # Get the path
            path = fileDialog.GetPath()
            
            try:
                with open(path, 'r') as file:
                    self.profile_data = json.load(file)
                
                self.current_file = path
                self.is_changed = False
                
                # Clear notebook
                while self.notebook.GetPageCount() > 0:
                    self.notebook.DeletePage(0)
                
                # Add pages for each menu
                for menu_id, menu_data in self.profile_data.items():
                    menu_panel = MenuPanel(self.notebook, menu_id, menu_data, self)
                    self.notebook.AddPage(menu_panel, menu_id)
                
                # Update UI
                self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - {os.path.basename(path)}")
                self.statusbar.SetStatusText(f"Loaded: {path}")
                
            except Exception as e:
                wx.MessageBox(f"Error loading profile: {str(e)}", "Error", wx.ICON_ERROR)
    
    def on_save(self, event):
        """Save the current profile"""
        if not self.current_file:
            self.on_save_as(event)
            return
            
        try:
            with open(self.current_file, 'w') as file:
                json.dump(self.profile_data, file, indent=2)
            
            self.is_changed = False
            
            # Update UI
            self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - {os.path.basename(self.current_file)}")
            self.statusbar.SetStatusText(f"Saved: {self.current_file}")
            
        except Exception as e:
            wx.MessageBox(f"Error saving profile: {str(e)}", "Error", wx.ICON_ERROR)
    
    def on_save_as(self, event):
        """Save the current profile with a new name"""
        with wx.FileDialog(self, "Save Profile", wildcard="JSON files (*.json)|*.json",
                         style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            
            # Get the path
            path = fileDialog.GetPath()
            
            # Add .json extension if missing
            if not path.endswith('.json'):
                path += '.json'
            
            try:
                with open(path, 'w') as file:
                    json.dump(self.profile_data, file, indent=2)
                
                self.current_file = path
                self.is_changed = False
                
                # Update UI
                self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - {os.path.basename(path)}")
                self.statusbar.SetStatusText(f"Saved: {path}")
                
            except Exception as e:
                wx.MessageBox(f"Error saving profile: {str(e)}", "Error", wx.ICON_ERROR)
    
    def on_test_menu(self, event):
        """Test the detection of the current menu"""
        # Get the currently selected menu
        current_tab = self.notebook.GetSelection()
        if current_tab == -1:
            wx.MessageBox("No menu selected", "Error", wx.ICON_ERROR)
            return
            
        menu_panel = self.notebook.GetPage(current_tab)
        menu_id = menu_panel.menu_id
        menu_data = self.profile_data[menu_id]
        
        if "conditions" not in menu_data or not menu_data["conditions"]:
            wx.MessageBox(f"Menu '{menu_id}' has no conditions to test", "Error", wx.ICON_ERROR)
            return
        
        # Create a dialog to show test results
        dialog = wx.Dialog(self, title=f"Testing Menu: {menu_id}", size=(500, 400))
        panel = wx.Panel(dialog)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Status text
        status_text = wx.StaticText(panel, label="Testing menu conditions...")
        sizer.Add(status_text, flag=wx.ALL, border=10)
        
        # Results list
        results_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        results_list.InsertColumn(0, "Condition", width=150)
        results_list.InsertColumn(1, "Result", width=100)
        results_list.InsertColumn(2, "Details", width=200)
        
        sizer.Add(results_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        
        # Overall result
        overall_result = wx.StaticText(panel, label="")
        overall_result.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(overall_result, flag=wx.ALL, border=10)
        
        # Close button
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda evt: dialog.Close())
        sizer.Add(close_btn, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        panel.SetSizer(sizer)
        
        # Start the test in a separate thread to avoid freezing UI
        condition_checker = MenuCondition()
        
        def run_test():
            # Take screenshot
            screenshot = np.array(pyautogui.screenshot())
            
            # Test each condition
            all_passed = True
            
            for i, condition in enumerate(menu_data["conditions"]):
                condition_type = condition["type"]
                
                try:
                    # Check the condition
                    result = condition_checker.check_condition(condition, screenshot)
                    
                    # Add to results list
                    if condition_type == "pixel_color":
                        description = f"Pixel at ({condition['x']}, {condition['y']})"
                    elif condition_type == "pixel_region_color":
                        description = f"Region ({condition['x1']}, {condition['y1']}) to ({condition['x2']}, {condition['y2']})"
                    else:
                        description = str(condition)
                    
                    result_text = "PASSED" if result else "FAILED"
                    details = f"RGB{condition['color']} +/-{condition['tolerance']}"
                    
                    # Update UI from main thread
                    wx.CallAfter(lambda: results_list.InsertItem(i, description))
                    wx.CallAfter(lambda: results_list.SetItem(i, 1, result_text))
                    wx.CallAfter(lambda: results_list.SetItem(i, 2, details))
                    
                    # Update status
                    all_passed = all_passed and result
                    
                except Exception as e:
                    wx.CallAfter(lambda: results_list.InsertItem(i, str(condition)))
                    wx.CallAfter(lambda: results_list.SetItem(i, 1, "ERROR"))
                    wx.CallAfter(lambda: results_list.SetItem(i, 2, str(e)))
                    all_passed = False
            
            # Update final result
            if all_passed:
                wx.CallAfter(lambda: overall_result.SetLabel("RESULT: ALL CONDITIONS PASSED - Menu is active"))
                wx.CallAfter(lambda: overall_result.SetForegroundColour(wx.Colour(0, 128, 0)))  # Green
            else:
                wx.CallAfter(lambda: overall_result.SetLabel("RESULT: SOME CONDITIONS FAILED - Menu is not active"))
                wx.CallAfter(lambda: overall_result.SetForegroundColour(wx.Colour(192, 0, 0)))  # Red
            
            wx.CallAfter(lambda: status_text.SetLabel("Test completed."))
        
        # Start the test thread
        test_thread = threading.Thread(target=run_test)
        test_thread.daemon = True
        test_thread.start()
        
        # Show the dialog
        dialog.ShowModal()
        dialog.Destroy()
    
    def on_export_python(self, event):
        """Export the profile as Python code"""
        if not self.profile_data:
            wx.MessageBox("No profile data to export", "Error", wx.ICON_ERROR)
            return
            
        with wx.FileDialog(self, "Export as Python", wildcard="Python files (*.py)|*.py",
                         style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            
            # Get the path
            path = fileDialog.GetPath()
            
            # Add .py extension if missing
            if not path.endswith('.py'):
                path += '.py'
            
            try:
                # Generate Python code
                py_code = self._generate_python_code()
                
                with open(path, 'w') as file:
                    file.write(py_code)
                
                self.statusbar.SetStatusText(f"Exported to: {path}")
                
                # Show success message with option to open file
                if wx.MessageBox(f"Profile exported to {path}\n\nOpen the file?", 
                               "Export Successful", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                    # Open the file with default system editor
                    import subprocess
                    import platform
                    
                    if platform.system() == 'Windows':
                        os.startfile(path)
                    elif platform.system() == 'Darwin':  # macOS
                        subprocess.call(('open', path))
                    else:  # Linux
                        subprocess.call(('xdg-open', path))
                
            except Exception as e:
                wx.MessageBox(f"Error exporting profile: {str(e)}", "Error", wx.ICON_ERROR)
    
    def _generate_python_code(self):
        """Generate Python code from the profile data"""
        code = [
            '"""',
            f'UI Menu Profile - Generated by {APP_TITLE} v{APP_VERSION}',
            f'Generated on: {time.strftime("%Y-%m-%d %H:%M:%S")}',
            'This file defines menu structures and detection conditions for navigation.',
            '"""',
            '',
            '# Menu structure definition',
            'menus = {'
        ]
        
        # Sort menu IDs to make output deterministic
        menu_ids = sorted(self.profile_data.keys())
        
        for menu_id in menu_ids:
            menu_data = self.profile_data[menu_id]
            
            code.append(f'    "{menu_id}": {{')
            
            # Add conditions
            if "conditions" in menu_data and menu_data["conditions"]:
                code.append('        "conditions": [')
                for condition in menu_data["conditions"]:
                    condition_str = json.dumps(condition, indent=12)
                    # Fix indentation in the JSON string
                    condition_str = condition_str.replace('\n', '\n            ')
                    code.append(f'            {condition_str},')
                code.append('        ],')
            else:
                code.append('        "conditions": [],')
            
            # Add items
            if "items" in menu_data and menu_data["items"]:
                code.append('        "items": [')
                for item in menu_data["items"]:
                    # Convert the item to a proper Python representation
                    coords = item[0]
                    name = item[1]
                    elem_type = item[2]
                    speaks = item[3]
                    submenu = item[4]
                    
                    code.append(f'            (({coords[0]}, {coords[1]}), "{name}", "{elem_type}", {speaks}, {repr(submenu)}),')
                code.append('        ],')
            else:
                code.append('        "items": [],')
            
            code.append('    },')
        
        code.append('}')
        code.append('')
        code.append('# Example usage:')
        code.append('if __name__ == "__main__":')
        code.append('    import json')
        code.append('    print(f"Loaded {len(menus)} menus:")')
        code.append('    for menu_id, menu_data in menus.items():')
        code.append('        conditions = len(menu_data.get("conditions", []))')
        code.append('        items = len(menu_data.get("items", []))')
        code.append('        print(f"  - {menu_id}: {conditions} conditions, {items} items")')
        
        return '\n'.join(code)
    
    def on_about(self, event):
        """Show the about dialog"""
        info = wx.adv.AboutDialogInfo()
        info.SetName(APP_TITLE)
        info.SetVersion(APP_VERSION)
        info.SetDescription("A tool for creating UI navigation profiles with screen detection conditions")
        info.SetCopyright("(C) 2025")
        
        try:
            wx.adv.AboutBox(info)
        except:
            # Fallback if wx.adv is not available
            wx.MessageBox(f"{APP_TITLE} v{APP_VERSION}\nA tool for creating UI navigation profiles", "About", wx.OK | wx.ICON_INFORMATION)
    
    def on_exit(self, event):
        """Exit the application"""
        self.Close()
    
    def on_close(self, event):
        """Handle window close event"""
        if self.is_changed:
            dlg = wx.MessageDialog(self, 
                                  "Save changes before closing?",
                                  "Please confirm",
                                  wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            
            if result == wx.ID_YES:
                self.on_save(event)
                event.Skip()  # Continue with close
            elif result == wx.ID_NO:
                event.Skip()  # Continue with close without saving
            else:  # wx.ID_CANCEL
                event.Veto()  # Stop the close
        else:
            event.Skip()  # No changes, continue with close