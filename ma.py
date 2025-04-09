"""
Accessible Menu Navigation Script - High Performance Edition

This script creates an invisible UI navigation system controlled with keyboard arrows.
Features:
- Ultra-fast mouse movement with ctypes
- Optimized menu detection with minimal CPU usage
- Advanced caching to prevent redundant processing
- Asynchronous, non-blocking architecture
- Multi-threaded design with minimal locking
- Optimized MSS screen capture
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
from PIL import Image
import mss
from functools import lru_cache

# Setup logging with faster string formatting
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("AccessibleMenuNav")

# Windows constants for mouse_event
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# No global MSS instance - will create per-thread instances
# MSS has thread-local storage issues when shared across threads

class MenuConditionChecker:
    """Ultra-optimized class for checking menu conditions"""
    
    def __init__(self):
        """Initialize the condition checker with performance optimizations"""
        self.verbose = False
        self.last_active_menu = None
        self._cache = {}  # Cache for condition results
        self._screenshot_cache = None
        self._last_screenshot_time = 0
        self._cache_ttl = 0.05  # 50ms TTL for caches
        self._sample_positions = {}  # Cache for sampling positions
    
    def set_verbose(self, verbose):
        """Set verbose mode"""
        self.verbose = verbose
    
    def check_menu_conditions(self, menu_data, screenshot_pil):
        """Ultra-fast check if all conditions for a menu are met"""
        conditions = menu_data.get("conditions", [])
        
        # If no conditions, return False (can't detect)
        if not conditions:
            return False
        
        # Quick check each condition, exit early on failure
        for i, condition in enumerate(conditions):
            # Use cached result if available and recent
            cache_key = (id(condition), self._last_screenshot_time)
            if cache_key in self._cache:
                result = self._cache[cache_key]
            else:
                result = self._check_condition_optimized(condition, screenshot_pil)
                self._cache[cache_key] = result
            
            if not result:
                return False
                
        # All conditions passed
        return True
    
    def _check_condition_optimized(self, condition, screenshot_pil):
        """Highly optimized condition checker"""
        if not condition:
            return False
            
        condition_type = condition.get("type", "")
        
        if condition_type == "pixel_color":
            try:
                x = condition.get("x", 0)
                y = condition.get("y", 0) 
                expected_color = condition.get("color", [0, 0, 0])
                tolerance = condition.get("tolerance", 0)
                
                # Get pixel color (faster direct access)
                pixel_color = screenshot_pil.getpixel((x, y))
                
                # Use Euclidean distance for more accurate color comparison
                # This is more precise than Manhattan distance for critical detection
                r_diff = pixel_color[0] - expected_color[0]
                g_diff = pixel_color[1] - expected_color[1]
                b_diff = pixel_color[2] - expected_color[2]
                diff = (r_diff * r_diff + g_diff * g_diff + b_diff * b_diff) ** 0.5
                
                # Debug info in verbose mode
                if self.verbose:
                    logger.debug(f"Pixel at ({x},{y}): found {pixel_color}, expected {expected_color}, diff={diff:.1f}, tolerance={tolerance}")
                
                return diff <= tolerance
            except Exception as e:
                if self.verbose:
                    logger.error(f"Pixel check error: {str(e)}")
                return False
                
        elif condition_type == "pixel_region_color":
            try:
                x1 = condition.get("x1", 0)
                y1 = condition.get("y1", 0)
                x2 = condition.get("x2", 0)
                y2 = condition.get("y2", 0)
                expected_color = condition.get("color", [0, 0, 0])
                tolerance = condition.get("tolerance", 0)
                threshold = condition.get("threshold", 0.5)
                
                # Get cached sampling positions or create new ones
                cache_key = (x1, y1, x2, y2)
                if cache_key in self._sample_positions:
                    sample_points = self._sample_positions[cache_key]
                else:
                    # Instead of processing the entire region, take samples
                    # For large regions, use adaptive sampling grid
                    if (x2 - x1) * (y2 - y1) > 10000:  # Large region (100x100)
                        # Use sparse grid sampling (16 points)
                        cols = min(4, max(2, (x2 - x1) // 50))
                        rows = min(4, max(2, (y2 - y1) // 50))
                        
                        x_step = (x2 - x1) / cols
                        y_step = (y2 - y1) / rows
                        
                        sample_points = []
                        for i in range(cols):
                            for j in range(rows):
                                px = int(x1 + i * x_step + x_step/2)
                                py = int(y1 + j * y_step + y_step/2)
                                sample_points.append((px, py))
                    else:
                        # For smaller regions, use 5 strategic points
                        sample_points = [
                            (x1, y1),                  # Top-left
                            (x1, y2-1),                # Bottom-left
                            (x2-1, y1),                # Top-right
                            (x2-1, y2-1),              # Bottom-right
                            ((x1+x2)//2, (y1+y2)//2)   # Center
                        ]
                    
                    self._sample_positions[cache_key] = sample_points
                
                # Optimized tolerance check
                adj_tolerance = tolerance * 3  # Adjusted for Manhattan distance
                
                # Count matches using fast point sampling
                matches = 0
                for x, y in sample_points:
                    try:
                        pixel = screenshot_pil.getpixel((x, y))
                        # Fast Manhattan distance
                        diff = abs(pixel[0] - expected_color[0]) + \
                               abs(pixel[1] - expected_color[1]) + \
                               abs(pixel[2] - expected_color[2])
                               
                        if diff <= adj_tolerance:
                            matches += 1
                    except:
                        pass
                
                # Calculate match percentage
                match_percentage = matches / len(sample_points)
                return match_percentage >= threshold
                
            except:
                return False
        
        # Unknown condition type
        return False
    
    def detect_active_menu(self, all_menus):
        """Ultra-fast detection of active menu with caching and optimizations"""
        if not all_menus:
            return None
        
        current_time = time.time()
        
        # Fast path: Use cached screenshot if recent enough
        if (self._screenshot_cache is not None and 
            current_time - self._last_screenshot_time < self._cache_ttl):
            screenshot_pil = self._screenshot_cache
        else:
            # Take a new screenshot with MSS (fastest method)
            # Create a new MSS instance each time for thread safety
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[0]  # Primary monitor
                    screenshot = sct.grab(monitor)
                    
                    # Convert to PIL only once - big performance gain
                    screenshot_pil = Image.frombytes("RGB", 
                                                  (screenshot.width, screenshot.height), 
                                                  screenshot.rgb)
                    
                    # Update cache
                    self._screenshot_cache = screenshot_pil
                    self._last_screenshot_time = current_time
                    
                    # Clear outdated cache entries
                    self._cache = {k: v for k, v in self._cache.items() 
                                 if k[1] >= current_time - self._cache_ttl}
                    
            except Exception as e:
                if self.verbose:
                    logger.error(f"Screenshot error: {e}")
                return self.last_active_menu
        
        # Collect all matching menus and their condition counts
        matching_menus = []
        
        # Fast path: Check previously active menu first
        if self.last_active_menu and self.last_active_menu in all_menus:
            if self.check_menu_conditions(all_menus[self.last_active_menu], screenshot_pil):
                # Current menu still active, no need to check others
                return self.last_active_menu
        
        # Check all other menus and their condition counts
        for menu_id, menu_data in all_menus.items():
            # Skip the already checked menu
            if menu_id == self.last_active_menu:
                continue
                
            # Count how many conditions this menu has
            condition_count = len(menu_data.get("conditions", []))
            
            if condition_count > 0 and self.check_menu_conditions(menu_data, screenshot_pil):
                matching_menus.append((menu_id, condition_count))
        
        # If we have matches, select the one with the most conditions
        # This helps with disambiguation when multiple menus could match
        if matching_menus:
            # Sort by condition count descending
            matching_menus.sort(key=lambda x: x[1], reverse=True)
            # Select the menu with the most specific conditions
            best_match = matching_menus[0][0]
            self.last_active_menu = best_match
            return best_match
        
        # No change detected, keep previous menu
        return self.last_active_menu

class AccessibleMenuNavigator:
    """Main class for menu navigation with high-performance optimizations"""
    
    def __init__(self):
        """Initialize the navigator with performance optimizations"""
        self.menu_stack = []
        self.current_position = 0
        self.last_positions = {}
        self.speaker = ao.Auto()
        self.menus = {}
        self.verbose = False
        
        # Performance optimizations
        self.condition_checker = MenuConditionChecker()
        self.menu_check_interval = 0.05
        self.last_menu_check = 0
        self.menu_check_ongoing = False
        self.last_detected_menu = None
        
        # Optimized thread management
        self.mouse_queue = queue.Queue()
        self.stop_requested = threading.Event()
        self.is_mouse_moving = threading.Event()
        
        # Create a lightweight speech queue to prevent blocking
        self.speech_queue = queue.Queue()
        
        # Reduce CPU usage during navigation
        self.pause_detection = threading.Event()
    
    def set_verbose(self, verbose):
        """Set verbose mode"""
        self.verbose = verbose
        self.condition_checker.set_verbose(verbose)
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
    
    def speak(self, message):
        """Non-blocking speech with queue"""
        if not message:
            return
            
        # Filter verbose messages
        if message.startswith("Menu detection") and not self.verbose:
            return
            
        # Add to speech queue instead of blocking
        self.speech_queue.put(message)
    
    def _speech_worker(self):
        """Background thread for speech to avoid blocking UI navigation"""
        while not self.stop_requested.is_set():
            try:
                # Get message with timeout to allow checking stop_requested
                message = self.speech_queue.get(timeout=0.1)
                self.speaker.speak(message)
                self.speech_queue.task_done()
            except queue.Empty:
                pass
    
    def log(self, message, level=logging.INFO):
        """Optimized logging"""
        if level == logging.DEBUG and not self.verbose:
            return
        logger.log(level, message)
    
    def start(self, profile_path):
        """Start the navigator with optimized threading"""
        self.log("Accessible Menu Navigation Active")
        self.speak("Accessible Menu Navigation started")
        
        self.last_menu_check = time.time()
        
        # Load menu profile
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
        
        # Start worker threads
        mouse_thread = threading.Thread(target=self._mouse_worker, daemon=True)
        speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
        detection_thread = threading.Thread(target=self._menu_detection_worker, daemon=True)
        
        mouse_thread.start()
        speech_thread.start()
        detection_thread.start()
        
        # Initialize position if we have a menu
        if self.menu_stack:
            current_menu = self.menu_stack[0]
            if current_menu in self.last_positions:
                self.set_position(self.last_positions[current_menu])
            else:
                self.set_position(0)
        
        try:
            # Start keyboard listener
            with keyboard.Listener(on_press=self._on_key_press) as listener:
                listener.join()
        finally:
            # Clean shutdown
            self.stop_requested.set()
            
            # Wait for threads to exit (with timeout)
            mouse_thread.join(timeout=1.0)
            speech_thread.join(timeout=1.0)
            detection_thread.join(timeout=1.0)
            
            # Explicit MSS cleanup
            if _sct:
                _sct.close()
                
            self.log("Exiting")
    
    def load_menu_profile(self, filepath):
        """Load a menu profile with optimized detection"""
        try:
            with open(filepath, 'r') as f:
                self.menus = json.load(f)
            
            self.log(f"Loaded profile with {len(self.menus)} menus")
        
            # Initialize with the first menu in the profile
            if self.menus:
                try:
                    # Detect active menu
                    active_menu = self.condition_checker.detect_active_menu(self.menus)
                
                    if active_menu:
                        self.menu_stack = [active_menu]
                        self.log(f"Detected active menu: {active_menu}")
                        self.speak(f"Menu profile loaded. Detected {active_menu.replace('-', ' ')} menu")
                    else:
                        # Default to first menu
                        first_menu = next(iter(self.menus))
                        self.menu_stack = [first_menu]
                        self.speak(f"Menu profile loaded. Starting with {first_menu.replace('-', ' ')}")
                except Exception as detection_error:
                    # If detection fails, just use the first menu
                    self.log(f"Menu detection failed: {detection_error}", logging.WARNING)
                    first_menu = next(iter(self.menus))
                    self.menu_stack = [first_menu]
                    self.speak(f"Menu profile loaded. Starting with {first_menu.replace('-', ' ')}")
                
                return True
            else:
                self.log("Loaded profile is empty", logging.WARNING)
                return False
                
        except Exception as e:
            self.log(f"Error loading menu profile: {e}", logging.ERROR)
            return False
    
    def _mouse_worker(self):
        """Optimized mouse worker thread"""
        while not self.stop_requested.is_set():
            try:
                # Get command with timeout to prevent blocking forever
                command = self.mouse_queue.get(timeout=0.05)
                
                # Signal mouse movement starting
                self.is_mouse_moving.set()
                self.pause_detection.set()  # Pause detection during movement
                
                # Process command
                if command['type'] == 'move':
                    self._set_cursor_position(command['end_pos'][0], command['end_pos'][1])
                elif command['type'] == 'click':
                    self._perform_click(command['position'][0], command['position'][1])
                elif command['type'] == 'navigate':
                    self._perform_navigation(command['direction'])
                elif command['type'] == 'select':
                    self._perform_selection()
                elif command['type'] == 'pop':
                    self._perform_menu_pop()
                
                # Clear flags
                self.pause_detection.clear()
                self.is_mouse_moving.clear()
                self.mouse_queue.task_done()
                
            except queue.Empty:
                # No commands in queue
                self.is_mouse_moving.clear()
                self.pause_detection.clear()
            except Exception as e:
                # Error handling
                self.log(f"Mouse worker error: {e}", logging.ERROR)
                self.is_mouse_moving.clear()
                self.pause_detection.clear()
    
    def _menu_detection_worker(self):
        """Dedicated thread for menu detection to prevent UI blocking"""
        while not self.stop_requested.is_set():
            try:
                # Skip detection if paused or mouse is moving
                if self.pause_detection.is_set() or self.is_mouse_moving.is_set():
                    time.sleep(0.01)
                    continue
                
                # Check if it's time for another detection
                current_time = time.time()
                if current_time - self.last_menu_check < self.menu_check_interval:
                    time.sleep(0.01)
                    continue
                
                # Update timestamp
                self.last_menu_check = current_time
                
                # Detect active menu
                active_menu = self.condition_checker.detect_active_menu(self.menus)
                
                # Process result if we have one and it's different
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
                
                # Brief pause to reduce CPU usage
                time.sleep(0.01)
                
            except Exception as e:
                self.log(f"Menu detection error: {e}", logging.ERROR)
                time.sleep(0.1)  # Longer pause on error
    
    def _set_cursor_position(self, x, y):
        """Ultra-fast cursor positioning using ctypes"""
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
    
    def _perform_click(self, x, y):
        """Optimized mouse click with minimal delay"""
        self._set_cursor_position(x, y)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.01)  # Minimal delay
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    
    def enqueue_mouse_move(self, end_pos):
        """Queue a mouse movement"""
        self.mouse_queue.put({
            'type': 'move',
            'end_pos': end_pos
        })
    
    def enqueue_mouse_click(self, position):
        """Queue a mouse click"""
        self.mouse_queue.put({
            'type': 'click',
            'position': position
        })
    
    def _perform_navigation(self, direction):
        """Perform navigation in the given direction"""
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
                self.announce_item(details)
            else:
                self.speak("Item not found")
        else:
            self.speak("No menu selected")
    
    def _perform_selection(self):
        """Perform selection of the current item"""
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
        
        # Optional speech on select
        if details['speaks_on_select']:
            self.speak(f"Selected {details['name']}")
        
        # Store last position
        if self.menu_stack:
            self.last_positions[self.menu_stack[-1]] = self.current_position
            
        # If item has submenu, announce
        if details['has_submenu']:
            self.speak(f"Selecting {details['name']}")
    
    def _perform_menu_pop(self):
        """Pop menu from stack and return to previous menu"""
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
    
    def get_current_menu_items(self):
        """Get items from current menu with minimal overhead"""
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
                menu_id = first_menu_id
            else:
                return []  # No menus available
        
        menu_data = self.menus[menu_id]
        return menu_data.get("items", [])
    
    @lru_cache(maxsize=128)
    def get_item_details(self, menu_id, position):
        """Get item details with caching for repeated calls"""
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
        """Announce an item with NVDA-like formatting"""
        if not details:
            self.speak("No item selected")
            return
            
        # Format message
        if details['has_submenu']:
            message = f"{details['name']}, {details['type']} with submenu, {details['index_message']}"
        else:
            message = f"{details['name']}, {details['type']}, {details['index_message']}"
        
        self.speak(message)
    
    def set_position(self, position):
        """Set position within a menu"""
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
    
    def check_for_menu_change(self):
        """Check for menu changes - now mostly handled by background thread"""
        # Just return the result of the last check from the detection thread
        current_time = time.time()
        
        # If it's been too long since our last check, force one now
        if current_time - self.last_menu_check > self.menu_check_interval * 3:
            # Direct check
            active_menu = self.condition_checker.detect_active_menu(self.menus)
            self.last_menu_check = current_time
            
            # Process if we have a new menu
            if active_menu and (not self.menu_stack or active_menu != self.menu_stack[0]):
                self.log(f"Force detected new menu: {active_menu}")
                self.menu_stack = [active_menu]
                self.current_position = 0
                return True
        
        return False
    
    def _on_key_press(self, key):
        """Handle key press events"""
        try:
            if key == keyboard.Key.up:
                self.mouse_queue.put({
                    'type': 'navigate',
                    'direction': -1
                })
            elif key == keyboard.Key.down:
                self.mouse_queue.put({
                    'type': 'navigate',
                    'direction': 1
                })
            elif key == keyboard.Key.space:
                self.mouse_queue.put({
                    'type': 'select'
                })
            elif key == keyboard.Key.esc:
                # If in a submenu, go back
                if len(self.menu_stack) > 1:
                    self.mouse_queue.put({
                        'type': 'pop'
                    })
                # Otherwise, exit if pressed again
                elif len(self.menu_stack) <= 1:
                    # Exit on double-esc
                    self.log("Exiting menu navigation")
                    return False
            elif key == keyboard.Key.left:
                # Go back to parent menu if in a submenu
                if len(self.menu_stack) > 1:
                    self.mouse_queue.put({
                        'type': 'pop'
                    })
            elif key == keyboard.Key.right:
                # If current item has a submenu, select it
                if self.menu_stack:
                    details = self.get_item_details(self.menu_stack[-1], self.current_position)
                    if details and details['has_submenu']:
                        self.mouse_queue.put({
                            'type': 'select'
                        })
        except Exception as e:
            self.log(f"Error during key handling: {e}", logging.ERROR)
        
        return True


def main():
    """Main function with optimized startup"""
    parser = argparse.ArgumentParser(description="High-Performance Accessible Menu Navigation")
    parser.add_argument("profile", nargs="?", default="fortnite.json", help="Path to menu profile JSON file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    
    # Create the navigator
    navigator = AccessibleMenuNavigator()
    
    # Set verbose mode
    navigator.set_verbose(args.verbose)
    
    try:
        # Start the navigator with the specified profile
        navigator.start(args.profile)
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\nKeyboard interrupt received. Exiting...")
        
        # No need to clean up MSS instances - they're created per-thread
            
        # Set stop flag for any running threads
        if hasattr(navigator, 'stop_requested'):
            navigator.stop_requested.set()
            
        # Exit cleanly
        sys.exit(0)


if __name__ == "__main__":
    main()