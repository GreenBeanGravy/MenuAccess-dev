"""
Accessible Menu Navigation Script - NVDA Compatible Version

This script creates an invisible UI navigation system controlled with keyboard arrows.
Features:
- Fast mouse movement with ctypes for maximum performance
- Hierarchical menu navigation with stack system
- Speech feedback using accessible_output2
- NVDA-compatible menu behavior
- Support for custom menu profiles
- Active menu detection based on screen conditions
- MSS for high-performance screen capture
"""

import ctypes
from pynput import keyboard
import accessible_output2.outputs.auto as ao
import threading
import queue
import json
import os
import sys
import logging
import time
import numpy as np
import argparse
import mss  # MSS for faster screenshots

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("AccessibleMenuNav")

# Windows constants for mouse_event
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

class MenuConditionChecker:
    """Class for checking menu conditions with optimized MSS-based implementation"""
    
    def __init__(self):
        """Initialize the condition checker"""
        self.verbose = False
        self.last_active_menu = None
    
    def set_verbose(self, verbose):
        """Set verbose mode"""
        self.verbose = verbose
    
    def check_menu_conditions(self, menu_data, screenshot):
        """Fast check if all conditions for a menu are met"""
        conditions = menu_data.get("conditions", [])
        
        # If no conditions, return False (can't detect)
        if not conditions:
            return False
            
        # Quick check each condition, exit early on failure
        for condition in conditions:
            result, _ = self._check_condition_fast(condition, screenshot)
            if not result:
                return False
                
        # All conditions passed
        return True
    
    def _check_condition_fast(self, condition, screenshot):
        """Optimized version for faster checking"""
        if not condition:
            return False, "Empty condition"
            
        condition_type = condition.get("type", "")
        
        if condition_type == "pixel_color":
            try:
                x = condition.get("x", 0)
                y = condition.get("y", 0) 
                expected_color = condition.get("color", [0, 0, 0])
                tolerance = condition.get("tolerance", 0)
                
                pixel_color = screenshot.getpixel((x, y))
                # Manhattan distance is faster than Euclidean
                diff = sum(abs(a-b) for a, b in zip(pixel_color, expected_color))
                matched = diff <= (tolerance * 3)  # Adjusted for Manhattan distance
                
                return matched, ""
            except:
                return False, ""
                
        elif condition_type == "pixel_region_color":
            try:
                x1 = condition.get("x1", 0)
                y1 = condition.get("y1", 0)
                x2 = condition.get("x2", 0)
                y2 = condition.get("y2", 0)
                
                # Use a smaller sample instead of the full region
                if x2 - x1 > 10 or y2 - y1 > 10:
                    # Take 5 sample points instead of the whole region
                    sample_points = [
                        (x1, y1),
                        (x1, y2-1),
                        (x2-1, y1),
                        (x2-1, y2-1),
                        ((x1+x2)//2, (y1+y2)//2)  # Center point
                    ]
                    
                    expected_color = condition.get("color", [0, 0, 0])
                    tolerance = condition.get("tolerance", 0)
                    threshold = condition.get("threshold", 0.5)
                    
                    matches = 0
                    for x, y in sample_points:
                        try:
                            pixel = screenshot.getpixel((x, y))
                            diff = sum(abs(a-b) for a, b in zip(pixel, expected_color))
                            if diff <= (tolerance * 3):
                                matches += 1
                        except:
                            pass
                    
                    match_percentage = matches / len(sample_points)
                    return match_percentage >= threshold, ""
                else:
                    # Small region, use the original logic
                    # (implementation omitted for brevity)
                    pass
            except:
                return False, ""
        
        return False, ""
    
    def detect_active_menu(self, all_menus, sct):
        """Detect which menu is currently active based on screen conditions"""
        if not all_menus:
            return None
        
        try:
            monitor = sct.monitors[0]  # Primary monitor
            screenshot = sct.grab(monitor)
            
            # Convert MSS screenshot to PIL format for processing
            from PIL import Image
            screenshot_pil = Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)
            
            # Store all results to log them together
            results = {}
            details = {}
            
            # Fast path - check the previously active menu first
            if self.last_active_menu and self.last_active_menu in all_menus:
                if self.check_menu_conditions(all_menus[self.last_active_menu], screenshot_pil):
                    return self.last_active_menu
            
            # Check all menus with the same screenshot
            for menu_id, menu_data in all_menus.items():
                # Skip the already checked menu
                if menu_id == self.last_active_menu:
                    continue
                    
                conditions = menu_data.get("conditions", [])
                all_passed = True
                condition_results = []
                
                for i, condition in enumerate(conditions):
                    passed, info = self._check_condition_with_details(condition, screenshot_pil)
                    condition_results.append((passed, info))
                    if not passed:
                        all_passed = False
                        break
                
                results[menu_id] = all_passed
                details[menu_id] = condition_results
                
                # Early exit if we found a match
                if all_passed:
                    self.last_active_menu = menu_id
                    break
            
            # Log all results together in one clean batch if verbose
            if self.verbose:
                log_lines = ["Menu detection results:"]
                for menu_id, passed in results.items():
                    status = "ACTIVE" if passed else "failed"
                    log_lines.append(f"  {menu_id}: {status}")
                    
                    # Show details for all menus
                    if menu_id in details:
                        for i, (result, info) in enumerate(details[menu_id]):
                            prefix = "  + " if result else "  - "
                            log_lines.append(f"{prefix}{info}")
                
                logger.info("\n".join(log_lines))
            
            # Find matching menu
            matching_menus = [menu_id for menu_id, result in results.items() if result]
            if matching_menus:
                self.last_active_menu = matching_menus[0]
                return matching_menus[0]
                
        except Exception as e:
            logger.error(f"Menu detection error: {e}")
            
        return None
    
    def _check_condition_with_details(self, condition, screenshot):
        """Check a condition and return both result and detailed info"""
        if not condition:
            return False, "Empty condition"
            
        condition_type = condition.get("type", "")
        
        if condition_type == "pixel_color":
            x = condition.get("x", 0)
            y = condition.get("y", 0) 
            expected_color = condition.get("color", [0, 0, 0])
            tolerance = condition.get("tolerance", 0)
            
            try:
                pixel_color = screenshot.getpixel((x, y))
                diff = np.sqrt(np.sum((np.array(pixel_color) - np.array(expected_color)) ** 2))
                matched = diff <= tolerance
                
                info = f"Pixel ({x},{y}): found {pixel_color}, expected {expected_color}, diff {diff:.1f}, tolerance {tolerance}"
                return matched, info
                
            except Exception as e:
                return False, f"Error checking pixel: {e}"
                
        elif condition_type == "pixel_region_color":
            x1 = condition.get("x1", 0)
            y1 = condition.get("y1", 0)
            x2 = condition.get("x2", 0)
            y2 = condition.get("y2", 0)
            expected_color = condition.get("color", [0, 0, 0])
            tolerance = condition.get("tolerance", 0)
            threshold = condition.get("threshold", 0.5)
            
            try:
                # Make sure coordinates make sense
                if x2 <= x1 or y2 <= y1:
                    return False, f"Invalid region: ({x1},{y1})-({x2},{y2})"
                    
                # Extract region - more efficient with numpy
                region = np.array(screenshot.crop((x1, y1, x2, y2)))
                
                # Fast vectorized color difference calculation
                if region.size == 0:
                    return False, f"Empty region: ({x1},{y1})-({x2},{y2})"
                
                # Sample pixel for logging
                sample_pixel = region[0, 0] if region.size > 0 else None
                
                # Calculate differences efficiently with numpy
                r_diff = np.abs(region[:,:,0] - expected_color[0])
                g_diff = np.abs(region[:,:,1] - expected_color[1])
                b_diff = np.abs(region[:,:,2] - expected_color[2])
                
                # Use a faster approximation of Euclidean distance
                # Manhattan distance is faster than Euclidean
                diffs = r_diff + g_diff + b_diff
                matches = diffs <= (tolerance * 1.5)  # Adjust tolerance for Manhattan distance
                
                # Count matching pixels
                matching_pixels = np.count_nonzero(matches)
                total_pixels = region.shape[0] * region.shape[1]
                
                if total_pixels == 0:
                    return False, f"Empty region: ({x1},{y1})-({x2},{y2})"
                    
                match_percentage = matching_pixels / total_pixels
                matched = match_percentage >= threshold
                
                info = (f"Region ({x1},{y1})-({x2},{y2}): {match_percentage:.2f} matched, needed {threshold}, "
                       f"sample pixel {sample_pixel}, expected {expected_color}")
                return matched, info
                
            except Exception as e:
                return False, f"Error checking region: {e}"
        else:
            return False, f"Unknown condition type: {condition_type}"


class AccessibleMenuNavigator:
    """Main class for menu navigation"""
    
    def __init__(self):
        """Initialize the navigator"""
        self.menu_stack = []
        self.current_position = 0
        self.last_positions = {}  # Stores the last position for each menu
        self.speaker = ao.Auto()
        self.mouse_queue = queue.Queue()
        self.stop_worker = threading.Event()
        self.menus = {}  # Will be loaded from profile
        self.menu_check_interval = 0.05  # Faster menu check frequency (as requested)
        self.last_menu_check = 0
        self.condition_checker = MenuConditionChecker()
        self.verbose = False
        
        # Add flags to control processing
        self.is_mouse_moving = threading.Event()
        self.detection_paused = threading.Event()
        self.detection_results = queue.Queue(maxsize=1)
    
    def set_verbose(self, verbose):
        """Set verbose mode"""
        self.verbose = verbose
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
    
    def speak(self, message):
        """Speak a message, respecting verbose setting"""
        if message and (not message.startswith("Menu detection") or self.verbose):
            self.speaker.speak(message)
            
    def log(self, message, level=logging.INFO):
        """Log a message, respecting verbose setting"""
        if level == logging.DEBUG and not self.verbose:
            return
        logger.log(level, message)
    
    def start(self, profile_path):
        """Start the navigator with the specified profile"""
        self.log("Accessible Menu Navigation Active")
        self.speak("Accessible Menu Navigation started")
        
        # Initialize last menu check time
        self.last_menu_check = time.time()
        
        # Ensure the profile exists
        if not os.path.exists(profile_path):
            self.log(f"Profile '{profile_path}' not found, using default settings")
            self.speak("Menu profile not found, using default settings")
            
            # Create basic menu structure as fallback
            self.menus["main_menu"] = {
                "items": [
                    ((100, 100), "Menu Item 1", "button", True, None),
                    ((100, 150), "Menu Item 2", "button", True, None),
                ]
            }
            self.menu_stack = ["main_menu"]
        else:
            # Load the profile
            if not self.load_menu_profile(profile_path):
                self.log("Failed to load menu profile, using default settings")
                self.speak("Failed to load menu profile, using default settings")
                
                # Create basic menu structure as fallback
                self.menus["main_menu"] = {
                    "items": [
                        ((100, 100), "Menu Item 1", "button", True, None),
                        ((100, 150), "Menu Item 2", "button", True, None),
                    ]
                }
                self.menu_stack = ["main_menu"]
        
        # Start the mouse worker thread
        worker_thread = threading.Thread(target=self._mouse_worker, daemon=True)
        worker_thread.start()
        
        # Start the menu detection thread
        detection_thread = self._start_menu_detection_thread()
        
        # Initialize position if we have a menu
        if self.menu_stack:
            current_menu = self.menu_stack[0]
            if current_menu in self.last_positions:
                self.set_position(self.last_positions[current_menu])
            else:
                self.set_position(0)
        
        try:
            # Start listening for keyboard events
            with keyboard.Listener(on_press=self._on_key_press) as listener:
                listener.join()
        finally:
            # Cleanup
            self.stop_worker.set()
            worker_thread.join(timeout=1.0)
            detection_thread.join(timeout=1.0)
            self.log("Exiting")
    
    def load_menu_profile(self, filepath):
        """Load a menu profile from a JSON file"""
        try:
            with open(filepath, 'r') as f:
                self.menus = json.load(f)
            
            self.log(f"Loaded menu profile from {filepath}")
            self.log(f"Loaded profile with {len(self.menus)} menus")
        
            # Initialize with the first menu in the profile
            if self.menus:
                # Create a temporary MSS instance for detection
                with mss.mss() as sct:
                    active_menu = self.condition_checker.detect_active_menu(self.menus, sct)
            
                if active_menu:
                    self.menu_stack = [active_menu]
                    self.log(f"Detected active menu: {active_menu}")
                    self.speak(f"Menu profile loaded. Detected {active_menu.replace('-', ' ')} menu")
                else:
                    # Default to first menu
                    first_menu = next(iter(self.menus))
                    self.menu_stack = [first_menu]
                    self.speak(f"Menu profile loaded. Starting with {first_menu.replace('-', ' ')}")
                
                return True
            else:
                self.log("Loaded profile is empty", logging.WARNING)
                return False
                
        except Exception as e:
            self.log(f"Error loading menu profile: {e}", logging.ERROR)
            self.speak(f"Error loading menu profile: {e}")
            return False
    
    def _mouse_worker(self):
        """Worker thread that handles mouse movements with priority"""
        while not self.stop_worker.is_set():
            try:
                command = self.mouse_queue.get(timeout=0.05)
                
                # Signal that we're about to move the mouse
                self.is_mouse_moving.set()
                
                if command['type'] == 'move':
                    self._set_cursor_position(command['end_pos'][0], command['end_pos'][1])
                elif command['type'] == 'click':
                    self._perform_click(command['position'][0], command['position'][1])
                elif command['type'] == 'navigate':
                    self.navigate(command['direction'])
                elif command['type'] == 'select':
                    self.select_current()
                elif command['type'] == 'pop':
                    self.pop_menu()
                
                # Signal that we're done moving the mouse
                self.is_mouse_moving.clear()
                self.mouse_queue.task_done()
                
            except queue.Empty:
                self.is_mouse_moving.clear()  # Ensure flag is cleared if queue is empty
            except Exception as e:
                self.is_mouse_moving.clear()  # Ensure flag is cleared on error
                self.log(f"Error in mouse worker: {e}", logging.ERROR)
    
    def _set_cursor_position(self, x, y):
        """Set the cursor position using ctypes"""
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
    
    def _perform_click(self, x, y):
        """Perform a mouse click at the specified position"""
        self._set_cursor_position(x, y)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.01)  # 10ms delay for more reliable clicks (as requested)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.01)  # Additional 10ms delay after click (as requested)
    
    def enqueue_mouse_move(self, end_pos):
        """Enqueue a mouse movement to be executed by the worker thread"""
        self.mouse_queue.put({
            'type': 'move',
            'end_pos': end_pos
        })
    
    def enqueue_mouse_click(self, position):
        """Enqueue a mouse click to be executed by the worker thread"""
        self.mouse_queue.put({
            'type': 'click',
            'position': position
        })
    
    def _queue_navigation(self, direction):
        """Queue navigation to be performed off the main thread"""
        self.mouse_queue.put({
            'type': 'navigate',
            'direction': direction
        })

    def _queue_selection(self):
        """Queue selection to be performed off the main thread"""
        self.mouse_queue.put({
            'type': 'select',
        })

    def _queue_menu_pop(self):
        """Queue menu pop to be performed off the main thread"""
        self.mouse_queue.put({
            'type': 'pop',
        })
    
    def _start_menu_detection_thread(self):
        """Start a thread to periodically check for menu changes without blocking mouse"""
        def check_menu_periodically():
            while not self.stop_worker.is_set():
                try:
                    # Skip detection if mouse is currently moving
                    if self.is_mouse_moving.is_set():
                        time.sleep(0.01)  # Brief pause before checking again
                        continue
                    
                    # Do the menu check
                    self.check_for_menu_change()
                    
                    # Small delay between checks
                    time.sleep(self.menu_check_interval)
                    
                except Exception as e:
                    self.log(f"Error in menu detection thread: {e}", logging.ERROR)
                    time.sleep(0.1)  # Avoid tight loop on error
        
        detection_thread = threading.Thread(target=check_menu_periodically, daemon=True)
        detection_thread.start()
        return detection_thread
    
    def process_menu_detection(self, active_menu):
        """Process a menu detection result without blocking mouse movement"""
        # Skip if mouse is moving
        if self.is_mouse_moving.is_set():
            return False
        
        # If we found an active menu and it's different from the current one
        if active_menu and (not self.menu_stack or active_menu != self.menu_stack[0]):
            self.log(f"Detected new active menu: {active_menu}")
            
            # Reset menu stack to just this menu
            self.menu_stack = [active_menu]
            self.current_position = 0
            
            # Announce menu change
            self.speak(f"Switched to {active_menu.replace('-', ' ')} menu")
            
            # Update cursor position
            details = self.get_item_details(active_menu, self.current_position)
            if details:
                self.enqueue_mouse_move(details['coordinates'])
                self.announce_item(details)
            
            return True
        
        return False
    
    def get_current_menu_items(self):
        """Returns the items in the currently active menu"""
        # Check if menu detection finds a different active menu
        self.check_for_menu_change()
        
        if not self.menu_stack:
            # If menu_stack is empty, use the first menu as default
            if self.menus:
                self.menu_stack = [next(iter(self.menus))]
            else:
                return []  # No menus available
        
        menu_id = self.menu_stack[-1]
        if menu_id not in self.menus:
            # Menu doesn't exist, try to use the first menu if available
            if self.menus:
                first_menu_id = next(iter(self.menus))
                self.menu_stack = [first_menu_id]
                self.log(f"Menu '{menu_id}' not found, defaulting to '{first_menu_id}'", logging.WARNING)
                menu_id = first_menu_id
            else:
                return []  # No menus available
        
        menu_data = self.menus[menu_id]
        return menu_data.get("items", [])
    
    def get_item_details(self, menu_id, position):
        """Get item details with standardized position message"""
        if menu_id not in self.menus:
            return None
            
        items = self.menus[menu_id].get("items", [])
        
        if not items or position >= len(items):
            return None
            
        item = items[position]
        
        # Determine if this item has a submenu
        has_submenu = item[4] is not None
        submenu_indicator = "submenu" if has_submenu else ""
        
        return {
            'coordinates': item[0],
            'name': item[1],
            'type': item[2],
            'speaks_on_select': item[3],
            'submenu': item[4],
            'index_message': f"{position + 1} of {len(items)}",
            'has_submenu': has_submenu,
            'submenu_indicator': submenu_indicator
        }
    
    def announce_item(self, details):
        """Announce an item with consistent NVDA-like formatting"""
        if not details:
            self.speak("No item selected")
            return
            
        # For items with submenus, indicate this in the announcement
        if details['has_submenu']:
            message = f"{details['name']}, {details['type']} with submenu, {details['index_message']}"
        else:
            message = f"{details['name']}, {details['type']}, {details['index_message']}"
        
        self.log(message)
        self.speak(message)
    
    def navigate(self, direction):
        """
        Navigate through menu items
        
        Args:
            direction (int): 1 for down, -1 for up
        """
        # Check if menu has changed before navigation
        if self.check_for_menu_change():
            return  # Menu changed, don't continue with navigation
        
        items = self.get_current_menu_items()
        if not items:
            self.speak("No items available")
            return
            
        # Update position with wrapping
        self.current_position = (self.current_position + direction) % len(items)
        
        # Store this position for the current menu
        if self.menu_stack:
            self.last_positions[self.menu_stack[-1]] = self.current_position
        
        # Get details and move mouse
        current_menu = self.menu_stack[-1] if self.menu_stack else None
        if current_menu:
            details = self.get_item_details(current_menu, self.current_position)
            if details:
                self.enqueue_mouse_move(details['coordinates'])
                # Announce the new position
                self.announce_item(details)
            else:
                self.speak("Item not found")
        else:
            self.speak("No menu selected")
    
    def select_current(self):
        """Select the current menu item"""
        # Check if menu has changed before selection
        if self.check_for_menu_change():
            return  # Menu changed, don't continue with selection
        
        if not self.menu_stack:
            self.speak("No menu selected")
            return
            
        items = self.get_current_menu_items()
        if not items:
            self.speak("No items available")
            return
            
        details = self.get_item_details(self.menu_stack[-1], self.current_position)
        if not details:
            self.speak("Item not found")
            return
        
        # Perform click
        self.enqueue_mouse_click(details['coordinates'])
        self.log(f"Selected: {details['name']}, {details['type']}")
        
        # Optional speech on select
        if details['speaks_on_select']:
            self.speak(f"Selected {details['name']}")
        
        # Handle submenu - ONLY if menu detection confirms it (as requested)
        # Don't immediately assume submenu is active; wait for detection
        submenu_id = details['submenu']
        if submenu_id:
            # Just remember the current position
            self.last_positions[self.menu_stack[-1]] = self.current_position
            
            # Note: We'll let the menu detection thread update the menu stack
            # rather than immediately assuming the submenu is active
            self.log(f"Clicked item with potential submenu: {submenu_id}")
            
            # Only announce potential submenu entry
            if details['has_submenu']:
                self.speak(f"Selecting {details['name']}")
            
    def set_position(self, position):
        """Set position within a menu and move cursor there"""
        # Check if menu has changed
        if self.check_for_menu_change():
            return  # Menu changed, don't continue
        
        if not self.menu_stack:
            self.speak("No menu selected")
            return
            
        self.current_position = position
        
        details = self.get_item_details(self.menu_stack[-1], position)
        if details:
            self.enqueue_mouse_move(details['coordinates'])
            self.announce_item(details)
        else:
            self.speak("Item not found")
    
    def pop_menu(self):
        """
        Pop the current menu from the stack and return to the previous menu
        Returns True if a menu was popped, False if the stack is empty
        """
        # Check if menu has changed
        if self.check_for_menu_change():
            return True  # Menu changed, don't continue with pop
        
        if len(self.menu_stack) <= 1:
            current_menu = self.menu_stack[0] if self.menu_stack else "No menu"
            self.speak(f"Main menu: {current_menu}")
            return False
        
        # Store the name of the menu we're leaving
        leaving_menu_name = self.menu_stack[-1]
        
        # Remove current menu
        self.menu_stack.pop()
        
        # Restore last position in the parent menu
        parent_menu = self.menu_stack[-1]
        if parent_menu in self.last_positions:
            self.set_position(self.last_positions[parent_menu])
        else:
            self.set_position(0)
        
        # Announce menu exit
        self.speak(f"Exited submenu, returned to {parent_menu.replace('-', ' ')}")
        return True
    
    def force_pop_all(self):
        """Pop all menus and return to main menu"""
        # Check if menu detection finds a different active menu
        if self.check_for_menu_change():
            return  # Menu changed, don't continue
        
        if not self.menus:
            self.speak("No menus available")
            return
            
        # Use the first menu in the loaded profile
        first_menu = next(iter(self.menus))
        self.menu_stack = [first_menu]
        
        # Use last position if available, otherwise go to first item
        if first_menu in self.last_positions:
            self.set_position(self.last_positions[first_menu])
        else:
            self.set_position(0)
        
        self.speak(f"Returned to {first_menu.replace('-', ' ')}")
    
    def _on_key_press(self, key):
        """Handle key press events"""
        try:
            # Check for menu changes on every key press
            menu_changed = self.check_for_menu_change()
            
            # If menu changed, don't process navigation keys
            if menu_changed:
                return True
                
            if key == keyboard.Key.up:
                self._queue_navigation(-1)
            elif key == keyboard.Key.down:
                self._queue_navigation(1)
            elif key == keyboard.Key.space:
                self._queue_selection()
            elif key == keyboard.Key.esc:
                if not self.pop_menu() and len(self.menu_stack) <= 1:
                    print("Exiting menu navigation")
                    return False
            # Add left/right arrow navigation for compatible menu types
            elif key == keyboard.Key.left:
                # Go back to parent menu if in a submenu
                if len(self.menu_stack) > 1:
                    self._queue_menu_pop()
            elif key == keyboard.Key.right:
                # If current item has a submenu, select it
                if self.menu_stack:
                    details = self.get_item_details(self.menu_stack[-1], self.current_position)
                    if details and details['has_submenu']:
                        self._queue_selection()
        except Exception as e:
            self.log(f"Error during key handling: {e}", logging.ERROR)
        
        return True

    def check_for_menu_change(self):
        """Check if the active menu has changed and update accordingly"""
        current_time = time.time()
        if current_time - self.last_menu_check < self.menu_check_interval:
            return False
        
        self.last_menu_check = current_time
        
        # Create a temporary MSS instance
        with mss.mss() as sct:
            # Detect the active menu
            active_menu = self.condition_checker.detect_active_menu(self.menus, sct)
            
            # If we found an active menu and it's different from the current one
            if active_menu and (not self.menu_stack or active_menu != self.menu_stack[0]):
                self.log(f"Detected new active menu: {active_menu}")
            
                # Reset menu stack to just this menu
                self.menu_stack = [active_menu]
                self.current_position = 0
            
                # Announce menu change
                self.speak(f"Switched to {active_menu.replace('-', ' ')} menu")
            
                # Update cursor position
                details = self.get_item_details(active_menu, self.current_position)
                if details:
                    self.enqueue_mouse_move(details['coordinates'])
                    self.announce_item(details)
                
                return True
            
            # If no active menu detected but we have a menu stack, maintain the last known menu
            if not active_menu and self.menu_stack:
                self.log(f"No menu detected, maintaining last known menu: {self.menu_stack[0]}", logging.DEBUG)
                return False
            
            return False

def main():
    """Main function to parse arguments and start the navigator"""
    parser = argparse.ArgumentParser(description="Accessible Menu Navigation")
    parser.add_argument("profile", nargs="?", default="fortnite.json", help="Path to menu profile JSON file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging and speaking")
    args = parser.parse_args()
    
    # Create the navigator
    navigator = AccessibleMenuNavigator()
    
    # Set verbose mode
    navigator.set_verbose(args.verbose)
    navigator.condition_checker.set_verbose(args.verbose)
    
    # Start the navigator with the specified profile
    navigator.start(args.profile)


if __name__ == "__main__":
    main()