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
import copy

from pflib.utils import APP_TITLE, APP_VERSION
from pflib.menu_panel import MenuPanel
from pflib.menu_condition import MenuCondition # For test menu
from pflib.ocr_handler import OCRHandler # For test menu with OCR conditions
from malib.screen_capture import ScreenCapture  # Use unified screen capture
from PIL import Image

class ProfileEditorFrame(wx.Frame):
    """Main frame for the profile editor application"""
    
    def __init__(self, parent, title):
        super().__init__(parent, title=f"{title} v{APP_VERSION}", size=(850, 750)) # Increased size
        
        self.profile_data = {}
        self.current_file = None
        self.is_changed = False
        self.clipboard = {
            'menu': None,
            'conditions': [],
            'elements': []
        }
        
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # pflib parent
        self.profiles_dir = os.path.join(script_dir, 'profiles')
        os.makedirs(self.profiles_dir, exist_ok=True)

        # Initialize unified screen capture for editor
        self.screen_capture = ScreenCapture()

        # Initialize OCR Handler for the editor (used by "Test Menu")
        # For simplicity, using default 'en'. Could be made configurable.
        self.editor_ocr_handler = OCRHandler(['en'])
        # Start OCR initialization in background if not already done
        if not self.editor_ocr_handler.init_complete.is_set():
             threading.Thread(target=self.editor_ocr_handler.initialize_reader, daemon=True).start()
        
        self.init_ui()
        
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord('S'), wx.ID_SAVE),
            (wx.ACCEL_CTRL, ord('O'), wx.ID_OPEN),
            (wx.ACCEL_CTRL, ord('N'), wx.ID_NEW),
            # Add more shortcuts as needed, e.g., for copy/paste if global handling is desired
        ])
        self.SetAcceleratorTable(accel_tbl)
        
        self.Bind(wx.EVT_MENU, self.on_save, id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self.on_open, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.on_new, id=wx.ID_NEW)
        
        self.Center()
        
        # Initialize with default main_menu if no last profile is loaded
        config = self.load_config()
        last_profile = config.get('last_profile')
        loaded_last = False
        
        if last_profile and os.path.exists(last_profile):
            message = f"Do you want to open your last profile?\n\n{os.path.basename(last_profile)}"
            dlg = wx.MessageDialog(self, message, "Open Last Profile", wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            
            if result == wx.ID_YES:
                self.load_profile(last_profile)
                loaded_last = True
        
        if not loaded_last:
            self.add_menu("main_menu") # Add default if nothing loaded
            
    def init_ui(self):
        panel = wx.Panel(self)
        menubar = wx.MenuBar()
        
        file_menu = wx.Menu()
        new_item = file_menu.Append(wx.ID_NEW, "New Profile\tCtrl+N", "Create a new profile")
        open_item = file_menu.Append(wx.ID_OPEN, "Open Profile\tCtrl+O", "Open an existing profile")
        save_item = file_menu.Append(wx.ID_SAVE, "Save Profile\tCtrl+S", "Save current profile")
        save_as_item = file_menu.Append(wx.ID_SAVEAS, "Save Profile As", "Save current profile with a new name")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "Exit", "Exit the application")
        
        edit_menu = wx.Menu()
        copy_menu_item = edit_menu.Append(wx.ID_ANY, "Copy Menu", "Copy the current menu") # Ctrl+Shift+C might conflict
        paste_menu_item = edit_menu.Append(wx.ID_ANY, "Paste Menu", "Paste a copied menu")
        edit_menu.AppendSeparator()
        duplicate_menu_item = edit_menu.Append(wx.ID_ANY, "Duplicate Menu", "Duplicate the current menu")
        rename_menu_item = edit_menu.Append(wx.ID_ANY, "Rename Menu", "Rename the current menu")
        
        tools_menu = wx.Menu()
        test_item = tools_menu.Append(wx.ID_ANY, "Test Current Menu", "Test the detection of the current menu")
        export_py_item = tools_menu.Append(wx.ID_ANY, "Export as Python", "Export profile as Python code")
        
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "About", "About this application")
        
        self.Bind(wx.EVT_MENU, self.on_new, new_item)
        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        self.Bind(wx.EVT_MENU, self.on_save, save_item)
        self.Bind(wx.EVT_MENU, self.on_save_as, save_as_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        
        self.Bind(wx.EVT_MENU, self.on_copy_menu_menu_item, copy_menu_item)
        self.Bind(wx.EVT_MENU, self.on_paste_menu_menu_item, paste_menu_item) # Bind paste
        self.Bind(wx.EVT_MENU, self.on_duplicate_menu, duplicate_menu_item)
        self.Bind(wx.EVT_MENU, self.on_rename_menu, rename_menu_item)
        
        self.Bind(wx.EVT_MENU, self.on_test_menu, test_item)
        self.Bind(wx.EVT_MENU, self.on_export_python, export_py_item)
        self.Bind(wx.EVT_MENU, self.on_about, about_item)
        
        menubar.Append(file_menu, "&File"); menubar.Append(edit_menu, "&Edit")
        menubar.Append(tools_menu, "&Tools"); menubar.Append(help_menu, "&Help")
        self.SetMenuBar(menubar)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        menu_label = wx.StaticText(panel, label="Menu ID:")
        self.menu_id_ctrl = wx.TextCtrl(panel)
        add_menu_btn = wx.Button(panel, label="Add Menu")
        add_menu_btn.Bind(wx.EVT_BUTTON, self.on_add_menu_button) # Renamed handler
        
        top_sizer.Add(menu_label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        top_sizer.Add(self.menu_id_ctrl, 1, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5) # Proportion 1
        top_sizer.Add(add_menu_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(top_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        self.notebook = wx.Notebook(panel)
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(main_sizer)
        
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText("New Profile")
        self.Bind(wx.EVT_CLOSE, self.on_close)
    
    def is_profile_empty(self):
        if not self.profile_data: return True
        if len(self.profile_data) == 1 and 'main_menu' in self.profile_data:
            main_menu = self.profile_data['main_menu']
            if not main_menu.get('items') and not main_menu.get('conditions') and not main_menu.get('is_manual'):
                return True
        return False
    
    def save_config(self):
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(script_dir, 'pflib')
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, 'config.json')
        config = {'last_profile': self.current_file}
        try:
            with open(config_path, 'w') as file: json.dump(config, file)
        except Exception as e: print(f"Failed to save config: {e}")
    
    def load_config(self):
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(script_dir, 'pflib')
        config_path = os.path.join(config_dir, 'config.json')
        config = {'last_profile': None}
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as file: config.update(json.load(file))
        except Exception as e: print(f"Failed to load config: {e}")
        return config
    
    def load_profile(self, path):
        try:
            with open(path, 'r') as file: self.profile_data = json.load(file)
            self.current_file = path
            self.is_changed = False
            
            while self.notebook.GetPageCount() > 0: self.notebook.DeletePage(0)
            
            # Ensure default fields exist for older profiles
            for menu_id, menu_data in self.profile_data.items():
                menu_data.setdefault("is_manual", False)
                menu_data.setdefault("reset_index", True)
                menu_data.setdefault("reset_group", "default")
                menu_data.setdefault("group_order_indices", {"default": 0}) # Add this
                menu_data.setdefault("conditions", [])
                menu_data.setdefault("items", [])
                for item in menu_data["items"]:
                    while len(item) < 11: # Ensure 11 fields for items
                        if len(item) == 6: item.append([])    # ocr_regions
                        elif len(item) == 7: item.append(None) # custom_announcement
                        elif len(item) == 8: item.append(0)    # index
                        elif len(item) == 9: item.append([])    # conditions
                        elif len(item) == 10: item.append(0)   # ocr_delay_ms
                        else: item.append(None)


            for menu_id, menu_data in self.profile_data.items():
                menu_panel = MenuPanel(self.notebook, menu_id, menu_data, self)
                self.notebook.AddPage(menu_panel, menu_id)
            
            self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - {os.path.basename(path)}")
            self.statusbar.SetStatusText(f"Loaded: {path}")
            self.save_config()
        except Exception as e:
            wx.MessageBox(f"Error loading profile: {str(e)}", "Error", wx.ICON_ERROR)
    
    def on_copy_menu_menu_item(self, event): self.copy_current_menu()
    def on_paste_menu_menu_item(self, event): self.paste_menu() # Added handler

    def on_duplicate_menu(self, event):
        current_tab_idx = self.notebook.GetSelection()
        if current_tab_idx == -1:
            wx.MessageBox("No menu selected to duplicate.", "Error", wx.ICON_ERROR); return
        
        current_menu_panel = self.notebook.GetPage(current_tab_idx)
        orig_id = current_menu_panel.menu_id
        
        # Create a deep copy of the menu data
        menu_data_to_copy = copy.deepcopy(self.profile_data[orig_id])
        
        suggested_name = f"{orig_id}_copy"
        counter = 1
        while suggested_name in self.profile_data:
            suggested_name = f"{orig_id}_copy{counter}"; counter += 1
        
        dialog = wx.TextEntryDialog(self, f"Enter name for duplicated menu (original: {orig_id}):", "Duplicate Menu", suggested_name)
        if dialog.ShowModal() == wx.ID_OK:
            new_id = dialog.GetValue().strip()
            if not new_id: wx.MessageBox("Menu ID cannot be empty.", "Error", wx.ICON_ERROR); dialog.Destroy(); return
            if new_id in self.profile_data:
                if wx.MessageBox(f"Menu '{new_id}' already exists. Replace?", "Confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES:
                    dialog.Destroy(); return
                self.delete_menu(new_id) # Delete existing if replacing
            
            self.profile_data[new_id] = menu_data_to_copy # Use the deep copied data
            menu_panel = MenuPanel(self.notebook, new_id, self.profile_data[new_id], self)
            self.notebook.AddPage(menu_panel, new_id)
            self.notebook.SetSelection(self.notebook.GetPageCount() - 1)
            self.mark_profile_changed()
            self.statusbar.SetStatusText(f"Duplicated menu as: {new_id}")
        dialog.Destroy()
    
    def on_rename_menu(self, event):
        current_tab_idx = self.notebook.GetSelection()
        if current_tab_idx == -1: wx.MessageBox("No menu selected.", "Error", wx.ICON_ERROR); return
        menu_panel = self.notebook.GetPage(current_tab_idx)
        old_id = menu_panel.menu_id
        
        dialog = wx.TextEntryDialog(self, f"New name for menu (current: {old_id}):", "Rename Menu", old_id)
        if dialog.ShowModal() == wx.ID_OK:
            new_id = dialog.GetValue().strip()
            if not new_id: wx.MessageBox("Menu ID cannot be empty.", "Error", wx.ICON_ERROR); dialog.Destroy(); return
            if new_id == old_id: dialog.Destroy(); return
            if new_id in self.profile_data:
                if wx.MessageBox(f"Menu '{new_id}' already exists. Replace?", "Confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES:
                    dialog.Destroy(); return
                self.delete_menu(new_id)
            
            menu_data = self.profile_data.pop(old_id) # Remove old, get data
            self.profile_data[new_id] = menu_data # Add with new ID
            
            # Update tab
            self.notebook.DeletePage(current_tab_idx)
            new_menu_panel = MenuPanel(self.notebook, new_id, self.profile_data[new_id], self)
            self.notebook.InsertPage(current_tab_idx, new_menu_panel, new_id) # Insert at same position
            self.notebook.SetSelection(current_tab_idx)
            
            self.mark_profile_changed()
            self.statusbar.SetStatusText(f"Renamed menu from {old_id} to {new_id}")
        dialog.Destroy()
    
    def copy_current_menu(self):
        current_tab_idx = self.notebook.GetSelection()
        if current_tab_idx == -1: return
        menu_panel = self.notebook.GetPage(current_tab_idx)
        menu_id = menu_panel.menu_id
        self.clipboard['menu'] = {'id': menu_id, 'data': copy.deepcopy(self.profile_data[menu_id])}
        self.statusbar.SetStatusText(f"Copied menu: {menu_id}")

    def paste_menu(self):
        if not self.clipboard['menu']: wx.MessageBox("No menu in clipboard.", "Error", wx.ICON_INFORMATION); return
        orig_id = self.clipboard['menu']['id']
        menu_data_to_paste = copy.deepcopy(self.clipboard['menu']['data'])
        
        suggested_name = f"{orig_id}_pasted"
        counter = 1
        while suggested_name in self.profile_data:
            suggested_name = f"{orig_id}_pasted{counter}"; counter += 1

        dialog = wx.TextEntryDialog(self, f"New ID for pasted menu (original: {orig_id}):", "Paste Menu", suggested_name)
        if dialog.ShowModal() == wx.ID_OK:
            new_id = dialog.GetValue().strip()
            if not new_id: wx.MessageBox("Menu ID cannot be empty.", "Error", wx.ICON_ERROR); dialog.Destroy(); return
            if new_id in self.profile_data:
                if wx.MessageBox(f"Menu '{new_id}' already exists. Replace?", "Confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES:
                    dialog.Destroy(); return
                self.delete_menu(new_id)
            
            self.profile_data[new_id] = menu_data_to_paste
            menu_panel = MenuPanel(self.notebook, new_id, self.profile_data[new_id], self)
            self.notebook.AddPage(menu_panel, new_id)
            self.notebook.SetSelection(self.notebook.GetPageCount() - 1)
            self.mark_profile_changed()
            self.statusbar.SetStatusText(f"Pasted menu as: {new_id}")
        dialog.Destroy()
    
    def on_add_menu_button(self, event): # Renamed
        menu_id = self.menu_id_ctrl.GetValue().strip()
        if not menu_id: wx.MessageBox("Please enter a menu ID.", "Error", wx.ICON_ERROR); return
        if menu_id in self.profile_data: wx.MessageBox(f"Menu '{menu_id}' already exists.", "Error", wx.ICON_ERROR); return
        self.add_menu(menu_id)
        self.menu_id_ctrl.Clear()
    
    def add_menu(self, menu_id):
        self.profile_data[menu_id] = {
            "conditions": [], "items": [], "is_manual": False,
            "reset_index": True, "reset_group": "default",
            "group_order_indices": {"default": 0} # Initialize group order
        }
        menu_panel = MenuPanel(self.notebook, menu_id, self.profile_data[menu_id], self)
        self.notebook.AddPage(menu_panel, menu_id)
        self.notebook.SetSelection(self.notebook.GetPageCount() - 1)
        self.mark_profile_changed()
    
    def delete_menu(self, menu_id_to_delete):
        if menu_id_to_delete not in self.profile_data: return
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            if hasattr(page, 'menu_id') and page.menu_id == menu_id_to_delete:
                self.notebook.DeletePage(i); break
        del self.profile_data[menu_id_to_delete]
        self.mark_profile_changed()
    
    def mark_profile_changed(self):
        self.is_changed = True
        title = self.GetTitle()
        if not title.startswith('*'): self.SetTitle('*' + title)
        filename = os.path.basename(self.current_file) if self.current_file else "New Profile"
        self.statusbar.SetStatusText(f"Modified: {filename}")
    
    def on_new(self, event):
        if self.is_changed and not self.is_profile_empty():
            if wx.MessageBox("Unsaved changes. Continue?", "Confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES: return
        self.profile_data = {}
        self.current_file = None
        self.is_changed = False
        while self.notebook.GetPageCount() > 0: self.notebook.DeletePage(0)
        self.add_menu("main_menu")
        self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - New Profile")
        self.statusbar.SetStatusText("New Profile")
    
    def on_open(self, event):
        if self.is_changed and not self.is_profile_empty():
            if wx.MessageBox("Unsaved changes. Continue?", "Confirm", wx.ICON_QUESTION | wx.YES_NO) != wx.YES: return
        with wx.FileDialog(self, "Open Profile", defaultDir=self.profiles_dir,
                         wildcard="JSON files (*.json)|*.json",
                         style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
            if fd.ShowModal() == wx.ID_CANCEL: return
            self.load_profile(fd.GetPath())
    
    def on_save(self, event):
        if not self.current_file: self.on_save_as(event); return
        current_tab_idx = self.notebook.GetSelection()
        if current_tab_idx != -1:
            current_page = self.notebook.GetPage(current_tab_idx)
            if hasattr(current_page, 'on_save'): current_page.on_save() # Save active tab's data
        try:
            with open(self.current_file, 'w') as file: json.dump(self.profile_data, file, indent=2)
            self.is_changed = False
            self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - {os.path.basename(self.current_file)}")
            self.statusbar.SetStatusText(f"Saved: {self.current_file}")
            self.save_config()
        except Exception as e: wx.MessageBox(f"Error saving: {e}", "Error", wx.ICON_ERROR)
    
    def on_save_as(self, event):
        current_tab_idx = self.notebook.GetSelection()
        if current_tab_idx != -1: # Save active tab's data before Save As
            current_page = self.notebook.GetPage(current_tab_idx)
            if hasattr(current_page, 'on_save'): current_page.on_save()

        with wx.FileDialog(self, "Save Profile As", defaultDir=self.profiles_dir,
                         wildcard="JSON files (*.json)|*.json",
                         style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
            if fd.ShowModal() == wx.ID_CANCEL: return
            path = fd.GetPath()
            if not path.lower().endswith('.json'): path += '.json'
            try:
                with open(path, 'w') as file: json.dump(self.profile_data, file, indent=2)
                self.current_file = path
                self.is_changed = False
                self.SetTitle(f"{APP_TITLE} v{APP_VERSION} - {os.path.basename(path)}")
                self.statusbar.SetStatusText(f"Saved: {path}")
                self.save_config()
            except Exception as e: wx.MessageBox(f"Error saving as: {e}", "Error", wx.ICON_ERROR)
    
    def on_test_menu(self, event):
        current_tab_idx = self.notebook.GetSelection()
        if current_tab_idx == -1: wx.MessageBox("No menu selected.", "Error", wx.ICON_ERROR); return
        menu_panel = self.notebook.GetPage(current_tab_idx)
        menu_id = menu_panel.menu_id
        menu_data = self.profile_data[menu_id]
        
        if menu_data.get("is_manual", False):
            wx.MessageBox(f"Menu '{menu_id}' is manual and cannot be tested by conditions.", "Info", wx.ICON_INFORMATION); return
        if not menu_data.get("conditions"):
            wx.MessageBox(f"Menu '{menu_id}' has no conditions.", "Error", wx.ICON_ERROR); return
        
        dialog = wx.Dialog(self, title=f"Testing Menu: {menu_id}", size=(500, 400))
        panel = wx.Panel(dialog); sizer = wx.BoxSizer(wx.VERTICAL)
        status_text = wx.StaticText(panel, label="Testing menu conditions...")
        sizer.Add(status_text, 0, wx.ALL, 10)
        results_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        results_list.InsertColumn(0, "Condition", width=150); results_list.InsertColumn(1, "Result", width=100); results_list.InsertColumn(2, "Details", width=200)
        sizer.Add(results_list, 1, wx.EXPAND | wx.ALL, 10)
        overall_result_text = wx.StaticText(panel, label="") # Renamed
        overall_result_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(overall_result_text, 0, wx.ALL, 10)
        close_btn = wx.Button(panel, wx.ID_CLOSE, "Close"); close_btn.Bind(wx.EVT_BUTTON, lambda evt: dialog.Close())
        sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(sizer)
        
        # Pass the editor's OCR handler to MenuCondition for testing
        condition_checker = MenuCondition(ocr_handler=self.editor_ocr_handler)
        
        def run_test_thread():
            try:
                screenshot_pil = self.screen_capture.capture() # Use unified screen capture
                all_passed = True
                for i, condition_item in enumerate(menu_data["conditions"]): # Renamed
                    result = condition_checker.check_condition(condition_item, screenshot_pil)
                    
                    cond_type_str = condition_item.get("type", "N/A")
                    details_str = str(condition_item)[:50] # Basic details
                    if condition_item.get("negate"): cond_type_str = "NOT " + cond_type_str

                    wx.CallAfter(results_list.InsertItem, i, cond_type_str)
                    wx.CallAfter(results_list.SetItem, i, 1, "PASSED" if result else "FAILED")
                    wx.CallAfter(results_list.SetItem, i, 2, details_str)
                    all_passed = all_passed and result
                
                if all_passed:
                    wx.CallAfter(overall_result_text.SetLabel, "RESULT: ALL CONDITIONS PASSED - Menu is active")
                    wx.CallAfter(overall_result_text.SetForegroundColour, wx.Colour(0, 128, 0))
                else:
                    wx.CallAfter(overall_result_text.SetLabel, "RESULT: SOME FAILED - Menu not active")
                    wx.CallAfter(overall_result_text.SetForegroundColour, wx.Colour(192, 0, 0))
                wx.CallAfter(status_text.SetLabel, "Test completed.")
            except Exception as e_test:
                 wx.CallAfter(status_text.SetLabel, f"Test Error: {e_test}")

        test_thread = threading.Thread(target=run_test_thread); test_thread.daemon = True; test_thread.start()
        dialog.ShowModal(); dialog.Destroy()
    
    def on_export_python(self, event):
        if not self.profile_data: wx.MessageBox("No profile data to export.", "Error", wx.ICON_ERROR); return
        with wx.FileDialog(self, "Export as Python", wildcard="Python files (*.py)|*.py",
                         style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
            if fd.ShowModal() == wx.ID_CANCEL: return
            path = fd.GetPath()
            if not path.lower().endswith('.py'): path += '.py'
            try:
                py_code = self._generate_python_code()
                with open(path, 'w') as file: file.write(py_code)
                self.statusbar.SetStatusText(f"Exported to: {path}")
                if wx.MessageBox(f"Exported to {path}\nOpen file?", "Success", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                    import os
                    import sys
                    import subprocess
                    if os.name == 'nt': os.startfile(path) # Windows
                    elif sys.platform == 'darwin': subprocess.call(('open', path)) # macOS
                    else: subprocess.call(('xdg-open', path)) # Linux
            except Exception as e: wx.MessageBox(f"Error exporting: {e}", "Error", wx.ICON_ERROR)
    
    def _generate_python_code(self):
        # ... (This method should be updated if data structures changed significantly,
        #      especially if elements are now dicts instead of lists) ...
        # For now, assuming the core structure for export is similar.
        # Key change: include "is_manual", "reset_index", "reset_group", "group_order_indices"
        # and ensure all 11 fields for items are handled if they exist.
        code = [
            '"""', f'UI Menu Profile - Generated by {APP_TITLE} v{APP_VERSION}',
            f'Generated on: {time.strftime("%Y-%m-%d %H:%M:%S")}', '"""', '',
            'menus = {'
        ]
        menu_ids = sorted(self.profile_data.keys())
        for menu_id in menu_ids:
            menu_data = self.profile_data[menu_id]
            code.append(f'    "{menu_id}": {{')
            code.append(f'        "is_manual": {menu_data.get("is_manual", False)},')
            code.append(f'        "reset_index": {menu_data.get("reset_index", True)},')
            code.append(f'        "reset_group": "{menu_data.get("reset_group", "default")}",')
            code.append(f'        "group_order_indices": {json.dumps(menu_data.get("group_order_indices", {"default":0}))},')

            if "conditions" in menu_data and menu_data["conditions"]:
                code.append('        "conditions": [')
                for condition in menu_data["conditions"]:
                    code.append(f'            {json.dumps(condition)},')
                code.append('        ],')
            else: code.append('        "conditions": [],')
            
            if "items" in menu_data and menu_data["items"]:
                code.append('        "items": [')
                for item in menu_data["items"]:
                    # Ensure item is a list and has enough elements before accessing
                    item_str_parts = []
                    if isinstance(item, list):
                        item_str_parts.append(f"({item[0][0]}, {item[0][1]})" if len(item) > 0 and isinstance(item[0], (list, tuple)) and len(item[0]) == 2 else "(0,0)")
                        item_str_parts.append(f'"{item[1]}"' if len(item) > 1 else '"Unknown"')
                        item_str_parts.append(f'"{item[2]}"' if len(item) > 2 else '"button"')
                        item_str_parts.append(f'{item[3]}' if len(item) > 3 else 'False')
                        item_str_parts.append(f'{repr(item[4])}' if len(item) > 4 else 'None')
                        item_str_parts.append(f'"{item[5]}"' if len(item) > 5 and item[5] else '"default"')
                        item_str_parts.append(f'{json.dumps(item[6])}' if len(item) > 6 and item[6] else '[]')
                        item_str_parts.append(f'{repr(item[7])}' if len(item) > 7 else 'None')
                        item_str_parts.append(f'{item[8]}' if len(item) > 8 else '0')
                        item_str_parts.append(f'{json.dumps(item[9])}' if len(item) > 9 and item[9] else '[]')
                        item_str_parts.append(f'{item[10]}' if len(item) > 10 else '0')
                        code.append(f'            [{", ".join(item_str_parts)}],')
                    else: # Should not happen with proper data
                        code.append(f'            # Malformed item: {item}')

                code.append('        ],')
            else: code.append('        "items": [],')
            code.append('    },')
        code.append('}')
        # ... (Example usage remains same) ...
        code.append('\nif __name__ == "__main__":')
        code.append('    import json')
        code.append('    print(f"Loaded {len(menus)} menus:")')
        code.append('    for menu_id, menu_data in menus.items():')
        code.append('        conditions = len(menu_data.get("conditions", []))')
        code.append('        items = len(menu_data.get("items", []))')
        code.append('        print(f"  - {menu_id}: {conditions} conditions, {items} items, Manual: {menu_data.get("is_manual", False)}")')

        return '\n'.join(code)

    def on_about(self, event):
        info = wx.adv.AboutDialogInfo()
        info.SetName(APP_TITLE); info.SetVersion(APP_VERSION)
        info.SetDescription("Profile editor for MenuAccess."); info.SetCopyright("(C) 2025")
        try: wx.adv.AboutBox(info)
        except: wx.MessageBox(f"{APP_TITLE} v{APP_VERSION}\nProfile editor for MenuAccess.", "About", wx.OK | wx.ICON_INFORMATION)
    
    def on_exit(self, event): self.Close()
    
    def on_close(self, event):
        if self.is_changed and not self.is_profile_empty():
            dlg = wx.MessageDialog(self, "Save changes before closing?", "Confirm", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
            result = dlg.ShowModal(); dlg.Destroy()
            if result == wx.ID_YES: self.on_save(event); event.Skip()
            elif result == wx.ID_NO: event.Skip()
            else: event.Veto()
        else: event.Skip()

    def __del__(self):
        # Ensure screen capture and OCR handler are shut down
        if hasattr(self, 'screen_capture'):
            self.screen_capture.close()
        if hasattr(self, 'editor_ocr_handler') and self.editor_ocr_handler:
            self.editor_ocr_handler.shutdown()
        try:
            super().__del__()
        except:
            pass