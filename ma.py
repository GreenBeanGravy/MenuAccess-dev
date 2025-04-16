"""
MenuAccess main script
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
import cv2
import argparse
from PIL import Image
import mss
from functools import lru_cache
import easyocr

# Setup logging with faster string formatting
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("AccessibleMenuNav")

# Windows constants for mouse_event
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


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
                
                # Convert both colors to HSV for more perceptually relevant comparison
                # First, convert to the format OpenCV expects (0-255 uint8)
                pixel_rgb_cv = np.array([[pixel_color]], dtype=np.uint8)
                expected_rgb_cv = np.array([[expected_color]], dtype=np.uint8)
                
                # Convert RGB to HSV
                pixel_hsv = cv2.cvtColor(pixel_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                expected_hsv = cv2.cvtColor(expected_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                
                # Hue is circular, so we need special handling
                h1, s1, v1 = pixel_hsv.astype(float)
                h2, s2, v2 = expected_hsv.astype(float)
                
                # Handle hue wrapping (0 and 180 are adjacent in HSV)
                h_diff = min(abs(h1 - h2), 180 - abs(h1 - h2))
                
                # Weight hue more than saturation and value for better color detection
                # regardless of lighting changes
                weighted_diff = (h_diff * 2.0) + (abs(s1 - s2) / 2.0) + (abs(v1 - v2) / 4.0)
                diff = weighted_diff  # Use weighted HSV difference score
                
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
                        # Convert to HSV for better color comparison
                        pixel_rgb_cv = np.array([[pixel]], dtype=np.uint8)
                        expected_rgb_cv = np.array([[expected_color]], dtype=np.uint8)
                        
                        # Convert RGB to HSV
                        pixel_hsv = cv2.cvtColor(pixel_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                        expected_hsv = cv2.cvtColor(expected_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                        
                        # Convert to float to avoid overflow
                        h1 = float(pixel_hsv[0])
                        h2 = float(expected_hsv[0])
                        s1 = float(pixel_hsv[1])
                        s2 = float(expected_hsv[1])
                        v1 = float(pixel_hsv[2])
                        v2 = float(expected_hsv[2])
                        
                        # Calculate weighted HSV difference
                        h_diff = min(abs(h1 - h2), 180.0 - abs(h1 - h2))
                        s_diff = abs(s1 - s2)
                        v_diff = abs(v1 - v2)
                        
                        # Weight hue more than saturation and value for better color detection
                        diff = (h_diff * 2.0) + (s_diff / 2.0) + (v_diff / 4.0)
                               
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
        
        # Group navigation - update this section
        self.current_group = "default"
        self.group_positions = {}  # Stores the position within each group
        self.menu_groups = {}      # Stores the groups for each menu
        self.menu_group_positions = {}  # Format: {menu_id: {group_name: position}}
        
        # OCR setup
        self.reader = None  # Will be initialized when needed
        
        # OCR cache to avoid repeated recognition of the same region
        self.ocr_cache = {}
        self.ocr_cache_ttl = 10.0  # OCR cache valid for 10 seconds
        
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
        
        # Track shift key state
        self.shift_pressed = False
    
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
                
                try:
                    self.speaker.speak(message)
                except Exception as speech_error:
                    # Log the error but continue operation
                    self.log(f"Speech error: {speech_error}", logging.ERROR)
                    
                    # Try to reinitialize the speech engine
                    try:
                        self.speaker = ao.Auto()
                        self.log("Reinitialized speech engine", logging.INFO)
                    except:
                        self.log("Failed to reinitialize speech engine", logging.ERROR)
                
                self.speech_queue.task_done()
            except queue.Empty:
                pass
    
    def log(self, message, level=logging.INFO):
        """Optimized logging"""
        if level == logging.DEBUG and not self.verbose:
            return
        logger.log(level, message)
    
    def init_ocr_reader(self, languages=None):
        """Initialize the EasyOCR reader with specified languages"""
        if self.reader is None:
            # Default to English if no languages specified
            if not languages:
                languages = ['en']
                
            self.log(f"Initializing EasyOCR reader with languages: {languages}")
            self.reader = easyocr.Reader(languages)
            self.log("EasyOCR reader initialized")
    
    def start(self, profile_path, languages=None):
        """Start the navigator with optimized threading"""
        self.log("Accessible Menu Navigation Active")
        self.speak("Accessible Menu Navigation started")
        
        # Initialize OCR reader in the background
        threading.Thread(target=self.init_ocr_reader, args=(languages,), daemon=True).start()
        
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
            # Set up keyboard listeners with separate listeners for press and release
            # This allows us to track modifier keys properly
            with keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            ) as listener:
                listener.join()
        finally:
            # Clean shutdown
            self.stop_requested.set()
            
            # Wait for threads to exit (with timeout)
            mouse_thread.join(timeout=1.0)
            speech_thread.join(timeout=1.0)
            detection_thread.join(timeout=1.0)
            
            # No need for explicit MSS cleanup - instances are managed per thread
                
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
                    
                    old_menu = self.menu_stack[0] if self.menu_stack else None
                    
                    # Check if we should reset the index when entering this menu
                    should_reset_index = True
                    if active_menu in self.menus:
                        # Get reset_index property (default True for backwards compatibility)
                        should_reset_index = self.menus[active_menu].get("reset_index", True)
                        self.log(f"Menu '{active_menu}' has reset_index = {should_reset_index}")
                    
                    # Store the current position if we're going to maintain it
                    current_pos = 0
                    if not should_reset_index and old_menu:
                        # Save current position for possible reuse
                        current_pos = self.current_position
                    
                    # Get original menu position for logging
                    old_pos = 0
                    if old_menu:
                        old_pos = self.current_position
                    
                    # Reset menu stack to just this menu
                    self.menu_stack = [active_menu]
                    
                    # Reset the menu group cache
                    if active_menu not in self.menu_groups:
                        self.get_menu_groups(active_menu)
                    
                    # Get the group to reset to if specified
                    reset_group = self.menus[active_menu].get("reset_group", "default")
                    
                    # Reset position only if needed, otherwise maintain existing position
                    if should_reset_index:
                        # Find a valid group to use (starting with the specified reset_group)
                        valid_group = self.find_valid_group(active_menu, reset_group)
                        self.current_group = valid_group
                        self.log(f"Resetting index for menu: {active_menu} (was at position {old_pos})")
                        
                        # Navigate to the first item in the valid group
                        group_items = self.get_group_items(active_menu, valid_group)
                        if group_items:
                            self.current_position = group_items[0]
                            self.log(f"Resetting to group '{valid_group}' at position {self.current_position}")
                        else:
                            # If somehow still no items, set to position 0
                            self.current_position = 0
                            self.log(f"No items in any group, defaulting to position 0")
                    else:
                        # Keep the same group if it exists in the new menu
                        if old_menu:
                            # Check if the current group exists in this menu
                            old_group = self.current_group
                            if old_group in self.get_menu_groups(active_menu):
                                # Keep the group
                                self.log(f"Maintaining group '{old_group}' when switching menus")
                                
                                # Get items in the group
                                group_items = self.get_group_items(active_menu, old_group)
                                if group_items:
                                    # Try to position at the same index within the group
                                    group_position = 0
                                    if old_group in self.group_positions:
                                        group_position = min(self.group_positions[old_group], len(group_items)-1)
                                    
                                    self.current_position = group_items[group_position]
                                    self.log(f"Maintaining position {group_position} within group '{old_group}'")
                                    continue  # Skip the default position handling
                            
                        # Try to use the same position if it exists in the new menu
                        items = self.get_current_menu_items()
                        if items and current_pos < len(items):
                            self.current_position = current_pos
                            self.log(f"Maintaining index {current_pos} for menu: {active_menu} (reset_index is {should_reset_index})")
                        else:
                            # Find a valid group
                            valid_group = self.find_valid_group(active_menu)
                            self.current_group = valid_group
                            
                            # Get the first item in the valid group
                            group_items = self.get_group_items(active_menu, valid_group)
                            if group_items:
                                self.current_position = group_items[0]
                            else:
                                # If somehow still no items, set to position 0
                                self.current_position = 0
                    
                    # Announce menu change but in a more streamlined way
                    menu_name = active_menu.replace('-', ' ')
                    # Don't announce the menu change since we already said what was selected
                    
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
    
    def find_valid_group(self, menu_id, preferred_group="default"):
        """Find a group that contains at least one element, preferring the specified group"""
        if menu_id not in self.menus:
            return "default"
            
        # Get all groups in this menu
        all_groups = self.get_menu_groups(menu_id)
        
        # First try the preferred group
        if preferred_group in all_groups:
            items = self.get_group_items(menu_id, preferred_group)
            if items:
                return preferred_group
                
        # If preferred group is empty or not found, try each group in order
        for group in all_groups:
            items = self.get_group_items(menu_id, group)
            if items:
                return group
                
        # If no group has items, return the preferred one anyway
        return preferred_group
    
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
    
    def perform_ocr(self, x1, y1, x2, y2):
        """Perform OCR on a screen region using EasyOCR"""
        try:
            # Check cache first
            cache_key = (x1, y1, x2, y2)
            current_time = time.time()
            
            # If we have a valid cached result, use it
            if cache_key in self.ocr_cache and current_time - self.ocr_cache[cache_key]['time'] < self.ocr_cache_ttl:
                self.log(f"Using cached OCR result for region ({x1},{y1},{x2},{y2})", logging.DEBUG)
                return self.ocr_cache[cache_key]['text']
            
            # Initialize reader if needed
            if self.reader is None:
                self.init_ocr_reader()
                
            # Take a screenshot
            with mss.mss() as sct:
                region = {"top": y1, "left": x1, "width": x2-x1, "height": y2-y1}
                screenshot = sct.grab(region)
                img = Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)
            
            # Convert to numpy array for EasyOCR
            img_np = np.array(img)
            
            # Perform OCR with EasyOCR
            result = self.reader.readtext(img_np)
            
            # Extract all detected text and join
            if result:
                # EasyOCR returns a list of [bbox, text, confidence]
                # Join all detected text pieces
                ocr_text = ' '.join([entry[1] for entry in result])
            else:
                ocr_text = ""
            
            # Cache the result
            self.ocr_cache[cache_key] = {
                'text': ocr_text,
                'time': current_time
            }
            
            self.log(f"OCR result for region ({x1},{y1},{x2},{y2}): '{ocr_text}'", logging.DEBUG)
            return ocr_text
            
        except Exception as e:
            self.log(f"OCR error: {e}", logging.ERROR)
            return ""
    
    def process_ocr_regions(self, menu_id, element_index):
        """Process all OCR regions for a UI element"""
        if not self.menu_stack:
            return {}
            
        if menu_id not in self.menus:
            return {}
            
        items = self.menus[menu_id].get("items", [])
        if element_index >= len(items):
            return {}
            
        element = items[element_index]
        
        # Check if element has OCR regions
        if len(element) <= 6 or not element[6]:
            return {}
            
        ocr_regions = element[6]
        results = {}
        
        # Process each OCR region
        for region in ocr_regions:
            tag = region.get("tag", "ocr1")
            x1 = region.get("x1", 0)
            y1 = region.get("y1", 0)
            x2 = region.get("x2", 0)
            y2 = region.get("y2", 0)
            
            # Perform OCR
            text = self.perform_ocr(x1, y1, x2, y2)
            results[tag] = text
        
        return results
    
    def _perform_navigation(self, direction):
        """Perform navigation in the given direction"""
        if not self.menu_stack:
            self.speak("No menu selected")
            return
        
        current_menu = self.menu_stack[-1]
        
        # Get items in the current group
        group_items = self.get_group_items(current_menu, self.current_group)
        
        if not group_items:
            self.log(f"No items in group '{self.current_group}' for menu '{current_menu}'", logging.WARNING)
            
            # Find a valid group
            valid_group = self.find_valid_group(current_menu, self.current_group)
            
            # If we found a different group with items, switch to it
            if valid_group != self.current_group:
                self.log(f"Switching to group '{valid_group}' which has items", logging.INFO)
                self.current_group = valid_group
                group_items = self.get_group_items(current_menu, valid_group)
                
                if group_items:
                    # Get last saved position for this group in this menu
                    if current_menu in self.menu_group_positions and valid_group in self.menu_group_positions[current_menu]:
                        self.current_position = self.menu_group_positions[current_menu][valid_group]
                    else:
                        # Default to first item in group
                        self.current_position = group_items[0]
                    
                    details = self.get_item_details(current_menu, self.current_position)
                    if details:
                        self.enqueue_mouse_move(details['coordinates'])
                        self.announce_item(details)
                        return
            
            # If we still have no items, check if there are any items at all
            all_items = self.get_current_menu_items()
            if not all_items:
                self.speak(f"No items available in this menu")
                return
                
            # If there are items but none in any group, use the first item
            self.current_position = 0
            details = self.get_item_details(current_menu, self.current_position)
            if details:
                self.enqueue_mouse_move(details['coordinates'])
                self.announce_item(details)
            return
        
        # Find the current item's position within the group
        try:
            group_index = group_items.index(self.current_position)
        except ValueError:
            # Current position not in this group, start from beginning
            group_index = 0
        
        # Update position with wrapping within the group
        new_group_index = (group_index + direction) % len(group_items)
        self.current_position = group_items[new_group_index]
        
        # Store this position for the current group and current menu
        if current_menu not in self.menu_group_positions:
            self.menu_group_positions[current_menu] = {}
        self.menu_group_positions[current_menu][self.current_group] = self.current_position
        
        # Also store for backward compatibility
        self.group_positions[self.current_group] = new_group_index
        
        # Also store for the current menu (for backward compatibility)
        if self.menu_stack:
            self.last_positions[self.menu_stack[-1]] = self.current_position
        
        # Get details and move mouse
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
        
        # Simplified announcement
        self.speak(f"{details['name']} selected")
        
        # Store last position
        if self.menu_stack:
            self.last_positions[self.menu_stack[-1]] = self.current_position
    
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
        
        # Check for OCR regions
        has_ocr = len(item) > 6 and item[6]
        
        # Check for custom announcement format
        custom_announcement = item[7] if len(item) > 7 else None
        
        return {
            'coordinates': item[0],
            'name': item[1],
            'type': item[2],
            'speaks_on_select': item[3],
            'submenu': item[4],
            'index_message': f"{position + 1} of {len(items)}",
            'has_submenu': has_submenu,
            'submenu_indicator': submenu_indicator,
            'group': item[5] if len(item) > 5 else "default",
            'has_ocr': has_ocr,
            'custom_announcement': custom_announcement
        }
    
    def format_announcement(self, details, ocr_results={}):
        """Format an announcement message using the template or defaults"""
        # If no custom template, use default format
        if not details.get('custom_announcement'):
            # Default format: "{name}, {type}, {index}"
            return f"{details['name']}, {details['type']}, {details['index_message']}"
        
        # Use custom template with replacements
        template = details['custom_announcement']
        
        # Prepare replacements
        replacements = {
            'name': details['name'],
            'type': details['type'],
            'index': details['index_message'],
            'menu': self.menu_stack[-1].replace('-', ' ') if self.menu_stack else "no menu",
            'submenu': "submenu" if details['has_submenu'] else "",
            'group': details['group']
        }
        
        # Add OCR results to replacements
        for tag, text in ocr_results.items():
            replacements[tag] = text
        
        # Perform replacements
        result = template
        for key, value in replacements.items():
            result = result.replace(f"{{{key}}}", str(value))
        
        return result
    
    def announce_item(self, details):
        """Announce an item with enhanced formatting"""
        if not details:
            self.speak("No item selected")
            return
        
        # Process OCR regions if present
        ocr_results = {}
        if details.get('has_ocr'):
            ocr_results = self.process_ocr_regions(self.menu_stack[-1], self.current_position)
        
        # Format the announcement
        message = self.format_announcement(details, ocr_results)
        
        self.speak(message)
    
    def set_position(self, position, announce=True):
        """Set position within a menu"""
        if not self.menu_stack:
            self.speak("No menu selected")
            return
            
        self.current_position = position
        
        details = self.get_item_details(self.menu_stack[-1], position)
        if details:
            self.enqueue_mouse_move(details['coordinates'])
            if announce:
                self.announce_item(details)
        else:
            self.speak("Item not found")
    
    def get_menu_groups(self, menu_id):
        """Get all unique groups in a menu"""
        if menu_id not in self.menus:
            return ["default"]
            
        # Check if we already have the groups cached
        if menu_id in self.menu_groups:
            return self.menu_groups[menu_id]
        
        # Find all unique groups in the menu
        groups = set()
        items = self.menus[menu_id].get("items", [])
        
        for item in items:
            # Add group (with default fallback if not present)
            if len(item) > 5 and item[5]:
                groups.add(item[5])
            else:
                groups.add("default")
        
        # Always include default group
        if not groups:
            groups.add("default")
            
        # Sort groups for consistent navigation
        sorted_groups = sorted(list(groups))
        
        # Cache the result
        self.menu_groups[menu_id] = sorted_groups
        
        return sorted_groups
    
    def get_next_group(self, current_group, menu_id):
        """Get the next group in the menu"""
        groups = self.get_menu_groups(menu_id)
        if not groups:
            return "default"
            
        try:
            idx = groups.index(current_group)
            next_idx = (idx + 1) % len(groups)
            return groups[next_idx]
        except ValueError:
            # Current group not found, return first group
            return groups[0]
    
    def get_prev_group(self, current_group, menu_id):
        """Get the previous group in the menu"""
        groups = self.get_menu_groups(menu_id)
        if not groups:
            return "default"
            
        try:
            idx = groups.index(current_group)
            prev_idx = (idx - 1) % len(groups)
            return groups[prev_idx]
        except ValueError:
            # Current group not found, return first group
            return groups[0]
        
    def navigate_to_group(self, group, announce=True):
        """Navigate to a specific group"""
        if not self.menu_stack:
            return False
            
        menu_id = self.menu_stack[-1]
        items = self.get_group_items(menu_id, group)
        
        if not items:
            # Look for a different group that has items
            self.log(f"No items found in group '{group}' for menu '{menu_id}', looking for alternative", logging.WARNING)
            
            all_groups = self.get_menu_groups(menu_id)
            alternative_group = None
            
            # Try to find any group with items
            for g in all_groups:
                if g != group:  # Skip the original group
                    group_items = self.get_group_items(menu_id, g)
                    if group_items:
                        alternative_group = g
                        break
            
            if alternative_group:
                self.log(f"Found alternative group '{alternative_group}' with items", logging.INFO)
                group = alternative_group
                items = self.get_group_items(menu_id, group)
            else:
                self.log(f"No groups with items found in menu '{menu_id}'", logging.WARNING)
                # Check if there are any items at all
                all_items = self.get_current_menu_items()
                if not all_items:
                    self.speak(f"No items available in this menu")
                    return False
                
                # If there are items but none in any group, use position 0
                self.current_position = 0
                details = self.get_item_details(menu_id, 0)
                if details:
                    self.enqueue_mouse_move(details['coordinates'])
                    if announce:
                        self.announce_item(details)
                return True
        
        # Save current position in current group and menu
        if self.current_group:
            if menu_id not in self.menu_group_positions:
                self.menu_group_positions[menu_id] = {}
            self.menu_group_positions[menu_id][self.current_group] = self.current_position
        
        # Set new group
        self.current_group = group
        
        # Get the last known position for this group in this menu, if any
        position = None
        if menu_id in self.menu_group_positions and group in self.menu_group_positions[menu_id]:
            position = self.menu_group_positions[menu_id][group]
            # Verify the position still exists in the items
            if position not in items:
                position = None
        
        # If no valid saved position, use the first item or fallback to the group_positions dictionary
        if position is None:
            if group in self.group_positions:
                # Use the saved index, but ensure it's within bounds
                index = min(self.group_positions[group], len(items) - 1)
                position = items[index]
            else:
                # Default to first item
                position = items[0]
        
        # Set position
        self.set_position(position, announce=announce)
        
        return True
    
    def get_group_items(self, menu_id, group):
        """Get indices of items in a specific group"""
        if menu_id not in self.menus:
            self.log(f"Menu '{menu_id}' not found when looking for group '{group}' items", logging.WARNING)
            return []
            
        items = self.menus[menu_id].get("items", [])
        if not items:
            self.log(f"Menu '{menu_id}' has no items when looking for group '{group}'", logging.WARNING)
            return []
            
        group_indices = []
        
        for i, item in enumerate(items):
            item_group = "default"
            if len(item) > 5 and item[5]:
                item_group = item[5]
                
            if item_group == group:
                group_indices.append(i)
        
        if not group_indices:
            self.log(f"No items in group '{group}' for menu '{menu_id}'", logging.WARNING)
            
        return group_indices
    
    def navigate_to_next_group(self):
        """Navigate to the next group with items"""
        if not self.menu_stack:
            self.speak("No menu selected")
            return
            
        menu_id = self.menu_stack[-1]
        
        # Get all groups
        all_groups = self.get_menu_groups(menu_id)
        if not all_groups:
            self.speak("No groups available")
            return
            
        # If current group isn't in the list, use the first one
        if self.current_group not in all_groups:
            self.current_group = all_groups[0]
            
        # Start from the next group
        idx = all_groups.index(self.current_group)
        
        # Try each group until we find one with items
        for i in range(len(all_groups)):
            # Get next group with wrapping
            next_idx = (idx + i + 1) % len(all_groups)
            next_group = all_groups[next_idx]
            
            # Skip if it's the current group
            if next_group == self.current_group:
                continue
                
            # Check if this group has items
            items = self.get_group_items(menu_id, next_group)
            if items:
                # Found a group with items
                if self.navigate_to_group(next_group):
                    self.speak(f"Group: {next_group}")
                    return
        
        # If we get here, no other group has items
        self.speak(f"No other groups with items available")
    
    def navigate_to_prev_group(self):
        """Navigate to the previous group with items"""
        if not self.menu_stack:
            self.speak("No menu selected")
            return
            
        menu_id = self.menu_stack[-1]
        
        # Get all groups
        all_groups = self.get_menu_groups(menu_id)
        if not all_groups:
            self.speak("No groups available")
            return
            
        # If current group isn't in the list, use the first one
        if self.current_group not in all_groups:
            self.current_group = all_groups[0]
            
        # Start from the previous group
        idx = all_groups.index(self.current_group)
        
        # Try each group until we find one with items
        for i in range(len(all_groups)):
            # Get previous group with wrapping
            prev_idx = (idx - i - 1) % len(all_groups)
            prev_group = all_groups[prev_idx]
            
            # Skip if it's the current group
            if prev_group == self.current_group:
                continue
                
            # Check if this group has items
            items = self.get_group_items(menu_id, prev_group)
            if items:
                # Found a group with items
                if self.navigate_to_group(prev_group):
                    self.speak(f"Group: {prev_group}")
                    return
        
        # If we get here, no other group has items
        self.speak(f"No other groups with items available")
    
    def check_for_menu_change(self):
        """Check for menu changes - now handles group positions better"""
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
                old_menu = self.menu_stack[0] if self.menu_stack else None
                self.menu_stack = [active_menu]
                
                # Get the group to reset to if specified
                reset_group = self.menus[active_menu].get("reset_group", "default")
                
                # Find a valid group (with items)
                valid_group = self.find_valid_group(active_menu, reset_group)
                self.current_group = valid_group
                
                # Check if we have a saved position for this group in this menu
                if active_menu in self.menu_group_positions and valid_group in self.menu_group_positions[active_menu]:
                    self.current_position = self.menu_group_positions[active_menu][valid_group]
                else:
                    # Use position 0 in the specific group
                    group_items = self.get_group_items(active_menu, valid_group)
                    if group_items:
                        self.current_position = group_items[0]
                    else:
                        self.current_position = 0
                    
                return True
        
        return False
    
    def _on_key_press(self, key):
        """Handle key press events"""
        try:
            # Track shift key state
            if key == keyboard.Key.shift:
                self.shift_pressed = True
                return True
                
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
            elif key == keyboard.Key.tab:
                # Check if shift is pressed using our tracked state
                if self.shift_pressed:
                    # Previous group
                    self.navigate_to_prev_group()
                else:
                    # Next group
                    self.navigate_to_next_group()
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
    
    def _on_key_release(self, key):
        """Handle key release events"""
        try:
            # Track shift key state
            if key == keyboard.Key.shift:
                self.shift_pressed = False
        except Exception as e:
            self.log(f"Error during key release handling: {e}", logging.ERROR)
        
        return True


def main():
    """Main function with optimized startup"""
    parser = argparse.ArgumentParser(description="High-Performance Accessible Menu Navigation")
    parser.add_argument("profile", nargs="?", default="fortnite.json", help="Path to menu profile JSON file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--languages", type=str, default="en", help="OCR languages, comma-separated (e.g., 'en,fr,es')")
    args = parser.parse_args()
    
    # Parse OCR languages
    ocr_languages = [lang.strip() for lang in args.languages.split(',')]
    
    # Create the navigator
    navigator = AccessibleMenuNavigator()
    
    # Set verbose mode based on command line flag (default is False)
    navigator.set_verbose(args.verbose)
    
    try:
        # Start the navigator with the specified profile and languages
        navigator.start(args.profile, ocr_languages)
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