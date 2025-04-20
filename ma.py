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
import pyautogui
import time
import numpy as np
import cv2
import argparse
from PIL import Image
import mss
from functools import lru_cache
import easyocr
import base64
import io
import re

# Setup logging with faster string formatting
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AccessibleMenuNav")

# Windows constants for mouse_event
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class MenuConditionChecker:
    """Highly optimized class for checking menu conditions with performance enhancements"""
    
    def __init__(self):
        """Initialize the condition checker with performance optimizations"""
        self.verbose = False
        self.last_active_menu = None
        self._cache = {}  # Cache for condition results
        self._screenshot_cache = None
        self._last_screenshot_time = 0
        self._cache_ttl = 0.05  # 50ms TTL for caches
        self._sample_positions = {}  # Cache for sampling positions
        
        # Initialize ORB feature detector for image matching
        self.orb = cv2.ORB_create(nfeatures=1000)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    
    def set_verbose(self, verbose):
        """Enable or disable verbose logging mode"""
        self.verbose = verbose
    
    def check_menu_conditions(self, menu_data, screenshot_pil):
        """
        Check if all conditions for a menu are met
        
        Args:
            menu_data: Dictionary containing menu conditions
            screenshot_pil: PIL Image of current screen
            
        Returns:
            bool: True if all conditions are met, False otherwise
        """
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
                result = self._check_condition(condition, screenshot_pil)
                self._cache[cache_key] = result
            
            if not result:
                return False
                
        # All conditions passed
        return True
    
    def _check_condition(self, condition, screenshot_pil):
        """
        Check if a single condition is met with optimized algorithms
        
        Args:
            condition: Dictionary containing condition parameters
            screenshot_pil: PIL Image of current screen
            
        Returns:
            bool: True if condition is met, False otherwise
        """
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
                
                # Improved region sampling approach
                region_width = x2 - x1
                region_height = y2 - y1
                region_size = region_width * region_height
                
                # Get cached sampling positions or create new ones
                cache_key = (x1, y1, x2, y2)
                if cache_key in self._sample_positions:
                    sample_points = self._sample_positions[cache_key]
                else:
                    # Adaptive sampling based on region size
                    if region_size > 40000:  # Large region (200x200+)
                        # Sparse grid sampling
                        sample_count = min(25, max(9, region_size // 4000))
                        grid_size = int(np.sqrt(sample_count))
                        
                        x_step = region_width / grid_size
                        y_step = region_height / grid_size
                        
                        sample_points = []
                        for i in range(grid_size):
                            for j in range(grid_size):
                                px = int(x1 + (i + 0.5) * x_step)
                                py = int(y1 + (j + 0.5) * y_step)
                                sample_points.append((px, py))
                    elif region_size > 10000:  # Medium region
                        # Use 9 strategic points
                        x_step = region_width / 3
                        y_step = region_height / 3
                        
                        sample_points = []
                        for i in range(3):
                            for j in range(3):
                                px = int(x1 + (i + 0.5) * x_step)
                                py = int(y1 + (j + 0.5) * y_step)
                                sample_points.append((px, py))
                    else:  # Small region
                        # Use 5 strategic points
                        sample_points = [
                            (x1, y1),                     # Top-left
                            (x2-1, y1),                   # Top-right
                            ((x1+x2)//2, (y1+y2)//2),     # Center
                            (x1, y2-1),                   # Bottom-left
                            (x2-1, y2-1)                  # Bottom-right
                        ]
                    
                    self._sample_positions[cache_key] = sample_points
                
                # Calculate similarity for each sample point
                matches = 0
                for px, py in sample_points:
                    try:
                        # Get color at this point
                        pixel_color = screenshot_pil.getpixel((px, py))
                        
                        # Convert to compatible numpy array format
                        pixel_rgb_cv = np.array([[pixel_color]], dtype=np.uint8)
                        expected_rgb_cv = np.array([[expected_color]], dtype=np.uint8)
                        
                        # Convert RGB to HSV
                        pixel_hsv = cv2.cvtColor(pixel_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                        expected_hsv = cv2.cvtColor(expected_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                        
                        # Calculate HSV differences
                        h1, s1, v1 = pixel_hsv.astype(float)
                        h2, s2, v2 = expected_hsv.astype(float)
                        
                        # Handle hue wrapping
                        h_diff = min(abs(h1 - h2), 180 - abs(h1 - h2))
                        
                        # Weight hue more than saturation and value for better color detection
                        weighted_diff = (h_diff * 2.0) + (abs(s1 - s2) / 2.0) + (abs(v1 - v2) / 4.0)
                        
                        if weighted_diff <= tolerance:
                            matches += 1
                    except:
                        # Skip any errors (e.g., out of bounds)
                        pass
                
                # Calculate match percentage
                match_percentage = matches / len(sample_points)
                result = match_percentage >= threshold
                
                if self.verbose:
                    logger.debug(f"Region ({x1},{y1}) to ({x2},{y2}): match={match_percentage:.2f}, threshold={threshold}")
                
                return result
                
            except Exception as e:
                if self.verbose:
                    logger.error(f"Region color check error: {str(e)}")
                return False
                
        elif condition_type == "pixel_region_image":
            try:
                x1 = condition.get("x1", 0)
                y1 = condition.get("y1", 0)
                x2 = condition.get("x2", 0)
                y2 = condition.get("y2", 0)
                image_data = condition.get("image_data")
                confidence = condition.get("confidence", 0.8)
                
                if not image_data:
                    return False
                
                # Decode the base64 image data
                image_bytes = base64.b64decode(image_data)
                
                # Create a PIL Image from the decoded data
                template_pil = Image.open(io.BytesIO(image_bytes))
                
                # Extract the region from the screenshot to check
                region = screenshot_pil.crop((x1, y1, x2, y2))
                
                # Convert PIL images to OpenCV format (numpy arrays)
                template_cv = np.array(template_pil)
                region_cv = np.array(region)
                
                # Convert to grayscale for feature detection
                if len(template_cv.shape) > 2:  # If it has 3 channels (RGB)
                    template_gray = cv2.cvtColor(template_cv, cv2.COLOR_RGB2GRAY)
                else:
                    template_gray = template_cv
                    
                if len(region_cv.shape) > 2:  # If it has 3 channels (RGB)
                    region_gray = cv2.cvtColor(region_cv, cv2.COLOR_RGB2GRAY)
                else:
                    region_gray = region_cv
                
                # Detect ORB features and compute descriptors
                kp1, des1 = self.orb.detectAndCompute(template_gray, None)
                kp2, des2 = self.orb.detectAndCompute(region_gray, None)
                
                # If no features found, try structural similarity as fallback
                if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
                    # Use structural similarity index as fallback
                    ssim_score = cv2.matchTemplate(
                        template_gray, region_gray, cv2.TM_CCOEFF_NORMED)[0, 0]
                    return ssim_score >= confidence
                
                # Match descriptors
                matches = self.matcher.match(des1, des2)
                
                # Sort matches by distance
                matches = sorted(matches, key=lambda x: x.distance)
                
                # Calculate match ratio (number of good matches / total matches)
                good_matches_threshold = 0.8  # Lower distance = better match
                good_matches = [m for m in matches if m.distance < good_matches_threshold]
                
                # Compute similarity score based on number of good matches
                if len(kp1) == 0:  # Prevent division by zero
                    similarity_score = 0
                else:
                    similarity_score = len(good_matches) / len(kp1)
                
                if self.verbose:
                    logger.debug(f"Image match score: {similarity_score:.3f}, confidence threshold: {confidence:.3f}")
                
                # Compare with the confidence threshold
                return similarity_score >= confidence
                
            except Exception as e:
                if self.verbose:
                    logger.error(f"Image match error: {str(e)}")
                return False
        
        # Unknown condition type
        return False
    
    def find_active_menu(self, all_menus):
        """
        Find currently active menu based on conditions with optimized performance
        
        Args:
            all_menus: Dictionary of menu definitions
            
        Returns:
            str: ID of the active menu, or None if no menu is active
        """
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
    """Main class for accessible menu navigation with performance optimizations"""
    
    def __init__(self):
        """Initialize the navigator with optimized structures and components"""
        self.menu_stack = []
        self.current_position = 0
        self.last_positions = {}
        self.speaker = ao.Auto()
        self.menus = {}
        self.verbose = False
        self.debug = False
        
        # Group navigation system
        self.current_group = "default"
        self.group_positions = {}  # Stores the position within each group
        self.menu_groups = {}      # Stores the groups for each menu
        self.menu_group_positions = {}  # Format: {menu_id: {group_name: position}}
        self.last_announced_group = None
        
        # OCR system
        self.reader = None  # Will be initialized when needed
        
        # OCR cache to avoid repeated recognition of the same region
        self.ocr_cache = {}
        self.ocr_cache_ttl = 5.0  # OCR cache valid for 5 seconds (reduced from 10)
        
        # Performance optimizations
        self.condition_checker = MenuConditionChecker()
        self.menu_check_interval = 0.05
        self.last_menu_check = 0
        self.menu_check_ongoing = False
        self.last_detected_menu = None
        
        # Thread management
        self.mouse_queue = queue.Queue()
        self.stop_requested = threading.Event()
        self.is_mouse_moving = threading.Event()
        
        # Speech queue to prevent blocking
        self.speech_queue = queue.Queue()
        
        # Reduce CPU usage during navigation
        self.pause_detection = threading.Event()
        
        # Track shift key state
        self.shift_pressed = False
    
    def set_verbose(self, verbose):
        """
        Enable or disable verbose logging mode
        
        Args:
            verbose: Boolean indicating whether to enable verbose mode
        """
        self.verbose = verbose
        self.condition_checker.set_verbose(verbose)
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
    
    def set_debug(self, debug):
        """
        Enable or disable debug logging mode
        
        Args:
            debug: Boolean indicating whether to enable debug mode
        """
        self.debug = debug
    
    def announce(self, message):
        """
        Queue a message to be spoken by screen reader (non-blocking)
        
        Args:
            message: Text string to be spoken
        """
        if not message:
            return
            
        # Filter verbose messages
        if message.startswith("Menu detection") and not self.verbose:
            return
            
        # Add to speech queue instead of blocking
        self.speech_queue.put(message)
    
    def _speech_thread_worker(self):
        """Background thread that processes speech queue to avoid blocking UI navigation"""
        while not self.stop_requested.is_set():
            try:
                # Get message with timeout to allow checking stop_requested
                message = self.speech_queue.get(timeout=0.1)
                
                try:
                    self.speaker.speak(message)
                except Exception as speech_error:
                    # Log the error but continue operation
                    self.log_message(f"Speech error: {speech_error}", logging.ERROR)
                    
                    # Try to reinitialize the speech engine
                    try:
                        self.speaker = ao.Auto()
                        self.log_message("Reinitialized speech engine", logging.INFO)
                    except:
                        self.log_message("Failed to reinitialize speech engine", logging.ERROR)
                
                self.speech_queue.task_done()
            except queue.Empty:
                pass
    
    def log_message(self, message, level=logging.INFO):
        """
        Log a message with the specified level
        
        Args:
            message: Text to log
            level: Logging level (default: INFO)
        """
        if level == logging.DEBUG and not (self.verbose or self.debug):
            return
        logger.log(level, message)
    
    def initialize_ocr_reader(self, languages=None):
        """
        Initialize the EasyOCR reader for text recognition
        
        Args:
            languages: List of language codes to recognize (default: ['en'])
        """
        if self.reader is None:
            # Default to English if no languages specified
            if not languages:
                languages = ['en']
                
            self.log_message(f"Initializing EasyOCR reader with languages: {languages}")
            self.reader = easyocr.Reader(languages)
            self.log_message("OCR reader initialized")
    
    def start(self, profile_path, languages=None):
        """
        Start the navigator with the specified profile
        
        Args:
            profile_path: Path to menu profile JSON file
            languages: List of language codes for OCR
        """
        self.log_message("Ready!")
        
        # Initialize OCR reader in the background
        threading.Thread(target=self.initialize_ocr_reader, args=(languages,), daemon=True).start()
        
        self.last_menu_check = time.time()
        
        # Load menu profile
        if not os.path.exists(profile_path):
            self.log_message(f"Profile '{profile_path}' not found, using default settings")
            self.announce("Menu profile not found, using default settings")
            
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
                self.log_message("Failed to load menu profile, using default settings")
                self.announce("Failed to load menu profile, using default settings")
                
                # Create basic menu structure as fallback
                self.menus["main_menu"] = {
                    "items": [
                        ((100, 100), "Menu Item 1", "button", True, None),
                        ((100, 150), "Menu Item 2", "button", True, None),
                    ]
                }
                self.menu_stack = ["main_menu"]
        
        # Start worker threads
        mouse_thread = threading.Thread(target=self._mouse_thread_worker, daemon=True)
        speech_thread = threading.Thread(target=self._speech_thread_worker, daemon=True)
        detection_thread = threading.Thread(target=self._menu_detection_thread_worker, daemon=True)
        
        mouse_thread.start()
        speech_thread.start()
        detection_thread.start()
        
        # Initialize position if we have a menu
        if self.menu_stack:
            current_menu = self.menu_stack[0]
            if current_menu in self.last_positions:
                self.set_current_position(self.last_positions[current_menu])
            else:
                self.set_current_position(0)
        
        try:
            # Set up keyboard listeners with separate listeners for press and release
            # This allows us to track modifier keys properly
            with keyboard.Listener(
                on_press=self._handle_key_press,
                on_release=self._handle_key_release
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
                
            self.log_message("Exiting")
    
    def load_menu_profile(self, filepath):
        """
        Load menu profile from JSON file
        
        Args:
            filepath: Path to the profile JSON file
            
        Returns:
            bool: True if profile loaded successfully, False otherwise
        """
        try:
            with open(filepath, 'r') as f:
                self.menus = json.load(f)
            
            self.log_message(f"Loaded profile with {len(self.menus)} menus")
        
            # Initialize with the first menu in the profile
            if self.menus:
                try:
                    # Detect active menu
                    active_menu = self.condition_checker.find_active_menu(self.menus)
                
                    if active_menu:
                        self.menu_stack = [active_menu]
                        self.log_message(f"Detected active menu: {active_menu}")
                        self.announce(f"Menu profile loaded. Detected {active_menu.replace('-', ' ')} menu")
                    else:
                        # Default to first menu
                        first_menu = next(iter(self.menus))
                        self.menu_stack = [first_menu]
                        self.announce(f"Menu profile loaded. Starting with {first_menu.replace('-', ' ')}")
                except Exception as detection_error:
                    # If detection fails, just use the first menu
                    self.log_message(f"Menu detection failed: {detection_error}", logging.WARNING)
                    first_menu = next(iter(self.menus))
                    self.menu_stack = [first_menu]
                    self.announce(f"Menu profile loaded. Starting with {first_menu.replace('-', ' ')}")
                
                return True
            else:
                self.log_message("Loaded profile is empty", logging.WARNING)
                return False
                
        except Exception as e:
            self.log_message(f"Error loading menu profile: {e}", logging.ERROR)
            return False
    
    def _mouse_thread_worker(self):
        """Background thread that processes mouse movement and click operations"""
        while not self.stop_requested.is_set():
            try:
                # Get command with timeout to prevent blocking forever
                command = self.mouse_queue.get(timeout=0.05)
                
                # Signal mouse movement starting
                self.is_mouse_moving.set()
                self.pause_detection.set()  # Pause detection during movement
                
                # Process command
                if command['type'] == 'move':
                    self._move_cursor_to(command['end_pos'][0], command['end_pos'][1])
                elif command['type'] == 'click':
                    self._click_at_position(command['position'][0], command['position'][1])
                elif command['type'] == 'navigate':
                    self._navigate_in_direction(command['direction'])
                elif command['type'] == 'select':
                    self._select_current_item()
                elif command['type'] == 'pop':
                    self._return_to_parent_menu()
                
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
                self.log_message(f"Mouse worker error: {e}", logging.ERROR)
                self.is_mouse_moving.clear()
                self.pause_detection.clear()
    
    def _menu_detection_thread_worker(self):
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
                active_menu = self.condition_checker.find_active_menu(self.menus)
                
                # Process result if we have one and it's different
                if active_menu and (not self.menu_stack or active_menu != self.menu_stack[0]):
                    self.log_message(f"Detected new active menu: {active_menu}")
                    
                    old_menu = self.menu_stack[0] if self.menu_stack else None
                    
                    # Check if we should reset the index when entering this menu
                    should_reset_index = True
                    if active_menu in self.menus:
                        # Get reset_index property (default True for backwards compatibility)
                        should_reset_index = self.menus[active_menu].get("reset_index", True)
                        self.log_message(f"Menu '{active_menu}' has reset_index = {should_reset_index}")
                    
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
                        self.get_unique_groups_in_menu(active_menu)
                    
                    # Get the group to reset to if specified
                    reset_group = self.menus[active_menu].get("reset_group", None)
                    
                    # Reset position only if needed, otherwise maintain existing position
                    if should_reset_index:
                        # Find a valid group to use (starting with the specified reset_group)
                        valid_group = self.find_valid_group(active_menu, reset_group)
                        self.current_group = valid_group
                        self.log_message(f"Resetting index for menu: {active_menu} (was at position {old_pos})")
                        
                        # Navigate to the first item in the valid group
                        group_items = self.get_items_in_group(active_menu, valid_group)
                        if group_items:
                            self.current_position = group_items[0]
                            self.log_message(f"Resetting to group '{valid_group}' at position {self.current_position}")
                        else:
                            # If somehow still no items, set to position 0
                            self.current_position = 0
                            self.log_message(f"No items in any group, defaulting to position 0")
                    else:
                        # Keep the same group if it exists in the new menu
                        if old_menu:
                            # Check if the current group exists in this menu
                            old_group = self.current_group
                            if old_group in self.get_unique_groups_in_menu(active_menu):
                                # Keep the group
                                self.log_message(f"Maintaining group '{old_group}' when switching menus")
                                
                                # Get items in the group
                                group_items = self.get_items_in_group(active_menu, old_group)
                                if group_items:
                                    # Try to position at the same index within the group
                                    group_position = 0
                                    if old_group in self.group_positions:
                                        group_position = min(self.group_positions[old_group], len(group_items)-1)
                                    
                                    self.current_position = group_items[group_position]
                                    self.log_message(f"Maintaining position {group_position} within group '{old_group}'")
                                    continue  # Skip the default position handling
                            
                        # Try to use the same position if it exists in the new menu
                        items = self.get_active_items_in_current_menu()
                        if items and current_pos < len(items):
                            self.current_position = current_pos
                            self.log_message(f"Maintaining index {current_pos} for menu: {active_menu} (reset_index is {should_reset_index})")
                        else:
                            # Find a valid group
                            valid_group = self.find_valid_group(active_menu)
                            self.current_group = valid_group
                            
                            # Get the first item in the valid group
                            group_items = self.get_items_in_group(active_menu, valid_group)
                            if group_items:
                                self.current_position = group_items[0]
                            else:
                                # If somehow still no items, set to position 0
                                self.current_position = 0
                    
                    # Update cursor position
                    details = self.get_element_details(active_menu, self.current_position)
                    if details:
                        self.queue_cursor_movement(details['coordinates'])
                        self.announce_element(details)
                
                # Brief pause to reduce CPU usage
                time.sleep(0.01)
                
            except Exception as e:
                self.log_message(f"Menu detection error: {e}", logging.ERROR)
                time.sleep(0.1)  # Longer pause on error
    
    def is_ocr_region_active(self, ocr_region, screenshot=None):
        """
        Check if an OCR region's conditions are met
        
        Args:
            ocr_region: OCR region data with potential conditions
            screenshot: Screenshot as numpy array (optional)
            
        Returns:
            bool: True if region is active (all conditions met), False otherwise
        """
        # If region has no conditions, it's always active
        if "conditions" not in ocr_region or not ocr_region["conditions"]:
            return True
            
        # Take a screenshot if not provided
        if screenshot is None:
            screenshot = np.array(pyautogui.screenshot())
        
        # Convert PIL screenshot to numpy array if needed
        if isinstance(screenshot, Image.Image):
            screenshot = np.array(screenshot)
            
        # Check each condition - all must be met for the region to be active
        for condition in ocr_region["conditions"]:
            # Directly check condition rather than using the condition checker's wrapper
            condition_type = condition.get("type", "unknown")
            
            if condition_type == "pixel_color":
                x = condition.get("x", 0)
                y = condition.get("y", 0)
                expected_color = condition.get("color", [0, 0, 0])
                tolerance = condition.get("tolerance", 0)
                
                # Get the pixel color (BGR by default)
                try:
                    if y >= screenshot.shape[0] or x >= screenshot.shape[1]:
                        self.log_message(f"OCR condition pixel position ({x},{y}) out of bounds", logging.DEBUG)
                        return False
                        
                    pixel_color = screenshot[y, x]
                    # Convert BGR to RGB if it's a 3-channel image
                    if len(pixel_color) == 3:
                        pixel_color = pixel_color[::-1]  # Reverse order for BGR to RGB
                    
                    # Calculate simple color distance
                    diff = sum(abs(a - b) for a, b in zip(pixel_color, expected_color))
                    
                    # Check if within tolerance
                    if diff > tolerance * 3:  # Multiply by 3 for the channels
                        if self.debug:
                            self.log_message(f"OCR condition failed: pixel at ({x}, {y}) " +
                                           f"expected {expected_color}, got {pixel_color}, " +
                                           f"diff={diff}, tolerance={tolerance*3}", logging.DEBUG)
                        return False
                except Exception as e:
                    self.log_message(f"Error checking pixel color: {str(e)}", logging.ERROR)
                    return False
            elif not self.condition_checker._check_condition(condition, Image.fromarray(screenshot)):
                if self.debug:
                    self.log_message(f"OCR condition failed: {condition_type}", logging.DEBUG)
                return False
                
        return True
    
    def get_ocr_text_for_element(self, menu_id, element_index):
        """
        Process all OCR regions for a UI element and return extracted text
        
        Args:
            menu_id: Menu identifier
            element_index: Index of element in the menu
            
        Returns:
            dict: Dictionary of OCR region tags to extracted text
        """
        if not self.menu_stack:
            return {}
            
        if menu_id not in self.menus:
            return {}
            
        items = self.menus[menu_id].get("items", [])
        if element_index >= len(items):
            return {}
            
        element = items[element_index]
        
        # Get element name for better logging
        element_name = element[1] if len(element) > 1 else "Unknown"
        
        # Log that we're starting OCR for this element
        self.log_message(f"Starting OCR processing for element: {element_name}", logging.DEBUG)
        
        # Check if element has OCR regions
        if len(element) <= 6 or not element[6]:
            self.log_message(f"Element {element_name} has no OCR regions", logging.DEBUG)
            return {}
            
        ocr_regions = element[6]
        results = {}
        
        # Log OCR regions
        self.log_message(f"Element {element_name} has {len(ocr_regions)} OCR regions", logging.DEBUG)
        
        # Take a screenshot for condition checking
        screenshot = np.array(pyautogui.screenshot())
        
        # Process each OCR region
        for region in ocr_regions:
            tag = region.get("tag", "ocr1")
            x1 = region.get("x1", 0)
            y1 = region.get("y1", 0)
            x2 = region.get("x2", 0)
            y2 = region.get("y2", 0)
            
            # Log OCR region details
            self.log_message(f"Processing OCR region '{tag}' at ({x1},{y1},{x2},{y2})", logging.DEBUG)
            
            # Check if region's conditions are met
            if not self.is_ocr_region_active(region, screenshot):
                # If conditions aren't met, add empty result
                self.log_message(f"OCR region '{tag}' conditions not met, skipping OCR", logging.DEBUG)
                results[tag] = ""
                continue
            
            # All conditions met, perform OCR
            text = self.extract_text_from_region(x1, y1, x2, y2)
            results[tag] = text
            
            # Log result if in debug mode
            if self.debug:
                if text.strip():
                    self.log_message(f"OCR region '{tag}' extracted text: '{text}'", logging.DEBUG)
                else:
                    self.log_message(f"OCR region '{tag}' extracted NO TEXT (empty result)", logging.DEBUG)
        
        return results
    
    def extract_text_from_region(self, x1, y1, x2, y2):
        """
        Perform OCR on a screen region to extract text
        
        Args:
            x1, y1: Top-left coordinates
            x2, y2: Bottom-right coordinates
            
        Returns:
            str: Extracted text from the region (converted to lowercase)
        """
        try:
            # Check cache first
            cache_key = (x1, y1, x2, y2)
            current_time = time.time()
            
            # If we have a valid cached result, use it
            if cache_key in self.ocr_cache and current_time - self.ocr_cache[cache_key]['time'] < self.ocr_cache_ttl:
                self.log_message(f"Using cached OCR result for region ({x1},{y1},{x2},{y2})", logging.DEBUG)
                return self.ocr_cache[cache_key]['text']
            
            # Initialize reader if needed
            if self.reader is None:
                self.initialize_ocr_reader()
                
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
                # Join all detected text pieces and convert to lowercase
                ocr_text = ' '.join([entry[1].lower() for entry in result])
            else:
                ocr_text = ""
            
            # Cache the result
            self.ocr_cache[cache_key] = {
                'text': ocr_text,
                'time': current_time
            }
            
            self.log_message(f"OCR result for region ({x1},{y1},{x2},{y2}): '{ocr_text}'", logging.DEBUG)
            return ocr_text
            
        except Exception as e:
            self.log_message(f"OCR error: {e}", logging.ERROR)
            return ""

    def format_element_announcement(self, details, ocr_results={}):
        """
        Format announcement message for an element with enhanced OCR tag handling
        
        Args:
            details: Element details dictionary
            ocr_results: OCR text results for the element
            
        Returns:
            str: Formatted announcement text
        """
        # Get element name for better debugging
        element_name = details.get('name', 'Unknown')
        
        # Log start of template formatting
        self.log_message(f"Formatting announcement for element: {element_name}", logging.DEBUG)
        
        # If no custom template, use default format
        if not details.get('custom_announcement'):
            # Default format: "{name}, {type}, {index}"
            return f"{details['name']}, {details['type']}, {details['index_message']}"
        
        # Use custom template with replacements
        template = details['custom_announcement']
        self.log_message(f"Using custom template: {template}", logging.DEBUG)
        
        # Log available OCR results
        for tag, text in ocr_results.items():
            if text.strip():
                self.log_message(f"OCR result '{tag}': '{text}'", logging.DEBUG)
            else:
                self.log_message(f"OCR result '{tag}': EMPTY", logging.DEBUG)
        
        # Prepare basic replacements
        replacements = {
            'name': details['name'],
            'type': details['type'],
            'index': details['index_message'],
            'menu': self.menu_stack[-1].replace('-', ' ') if self.menu_stack else "no menu",
            'submenu': "submenu" if details['has_submenu'] else "",
            'group': details['group']
        }
        
        # First check for OCR fallback chains like {ocr1,ocr2,ocr3}
        # Find all tags with commas inside braces
        fallback_pattern = r'{([^{}]+,[^{}]+)}'
        fallback_matches = re.findall(fallback_pattern, template)
        
        # Log fallback patterns found
        if fallback_matches:
            for match in fallback_matches:
                self.log_message(f"Found OCR fallback chain: {{{match}}}", logging.DEBUG)
        else:
            self.log_message(f"No OCR fallback chains found in template", logging.DEBUG)
        
        # Process each fallback chain
        for match in fallback_matches:
            # Get the full tag pattern (with braces)
            full_tag = '{' + match + '}'
            
            # Split by comma to get individual tags
            tags = [tag.strip() for tag in match.split(',')]
            
            # Log the tags in this chain
            self.log_message(f"Processing fallback chain with tags: {tags}", logging.DEBUG)
            
            # Try each tag in the chain until we find one with non-empty text
            replacement_text = ""
            used_tag = None
            
            for tag in tags:
                # Log the tag being checked
                if tag in ocr_results:
                    text = ocr_results[tag].strip()
                    if text:
                        replacement_text = text
                        used_tag = tag
                        self.log_message(f"Using OCR from '{tag}' in fallback chain: '{replacement_text}'", logging.DEBUG)
                        break
                    else:
                        self.log_message(f"Tag '{tag}' has empty text, trying next in chain", logging.DEBUG)
                else:
                    self.log_message(f"Tag '{tag}' not found in OCR results", logging.DEBUG)
            
            # If none of the tags had content, use empty string
            if not replacement_text:
                self.log_message(f"No content found in OCR fallback chain {tags}", logging.DEBUG)
            
            # Replace the fallback pattern with the selected text
            self.log_message(f"Replacing '{full_tag}' with '{replacement_text}'", logging.DEBUG)
            template = template.replace(full_tag, replacement_text)
        
        # Now process remaining individual tags
        for tag, text in ocr_results.items():
            # Add individual tags to replacements (only handle those not already in fallback chains)
            replacements[tag] = text.strip()
        
        # Perform all standard replacements
        result = template
        for key, value in replacements.items():
            pattern = f"{{{key}}}"
            if pattern in result:
                self.log_message(f"Replacing '{pattern}' with '{value}'", logging.DEBUG)
                result = result.replace(pattern, str(value))
        
        self.log_message(f"Final announcement: '{result}'", logging.DEBUG)
        return result
    
    def find_valid_group(self, menu_id, preferred_group=None):
        """
        Find a group that contains at least one element
        
        Args:
            menu_id: Menu identifier
            preferred_group: Preferred group to use if it has elements
            
        Returns:
            str: Name of valid group
        """
        if menu_id not in self.menus:
            # Get the first group if available, otherwise use empty string
            all_groups = self.get_unique_groups_in_menu(menu_id)
            return all_groups[0] if all_groups else ""
            
        # Get all groups in this menu
        all_groups = self.get_unique_groups_in_menu(menu_id)
        if not all_groups:
            return ""  # Return empty string if no groups exist
        
        # If preferred_group is specified, try it first
        if preferred_group and preferred_group in all_groups:
            items = self.get_items_in_group(menu_id, preferred_group)
            if items:
                return preferred_group
        
        # If preferred group is empty, not found, or not specified, try each group in order
        for group in all_groups:
            items = self.get_items_in_group(menu_id, group)
            if items:
                return group
                
        # If no group has items, return the first group
        return all_groups[0]

    def _move_cursor_to(self, x, y):
        """
        Move cursor to specific coordinates using Windows API for speed
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
    
    def _click_at_position(self, x, y):
        """
        Perform mouse click at specified coordinates
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        self._move_cursor_to(x, y)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.01)  # Minimal delay
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    
    def queue_cursor_movement(self, end_pos):
        """
        Add cursor movement to queue for processing by mouse thread
        
        Args:
            end_pos: Tuple of (x, y) coordinates
        """
        self.mouse_queue.put({
            'type': 'move',
            'end_pos': end_pos
        })
    
    def queue_mouse_click(self, position):
        """
        Add mouse click to queue for processing by mouse thread
        
        Args:
            position: Tuple of (x, y) coordinates
        """
        self.mouse_queue.put({
            'type': 'click',
            'position': position
        })
    
    def is_element_active(self, element, screenshot=None):
        """
        Check if a UI element's conditions are met
        
        Args:
            element: Element data
            screenshot: Screenshot as numpy array (optional)
            
        Returns:
            bool: True if element is active, False otherwise
        """
        # If element has no conditions, it's always active
        if len(element) <= 9 or not element[9]:
            return True
            
        # Take a screenshot if not provided
        if screenshot is None:
            screenshot = np.array(pyautogui.screenshot())
            
        # Check each condition - all must be met for the element to be active
        for condition in element[9]:
            if not self.condition_checker._check_condition(condition, screenshot):
                return False
                
        return True
    
    def _navigate_in_direction(self, direction):
        """
        Navigate to next/previous item in the menu
        
        Args:
            direction: 1 for next, -1 for previous
        """
        if not self.menu_stack:
            self.announce("No menu selected")
            return
        
        current_menu = self.menu_stack[-1]
        
        # Get items in the current group
        group_items = self.get_items_in_group(current_menu, self.current_group)
        
        if not group_items:
            self.log_message(f"No items in group '{self.current_group}' for menu '{current_menu}'", logging.WARNING)
            
            # Find a valid group
            valid_group = self.find_valid_group(current_menu, self.current_group)
            
            # If we found a different group with items, switch to it
            if valid_group != self.current_group:
                self.log_message(f"Switching to group '{valid_group}' which has items", logging.INFO)
                self.current_group = valid_group
                group_items = self.get_items_in_group(current_menu, valid_group)
                
                if group_items:
                    # Get last saved position for this group in this menu
                    if current_menu in self.menu_group_positions and valid_group in self.menu_group_positions[current_menu]:
                        self.current_position = self.menu_group_positions[current_menu][valid_group]
                    else:
                        # Default to first item in group
                        self.current_position = group_items[0]
                    
                    details = self.get_element_details(current_menu, self.current_position)
                    if details:
                        self.queue_cursor_movement(details['coordinates'])
                        self.announce_element(details)
                        return
            
            # If we still have no items, check if there are any items at all
            all_items = self.get_active_items_in_current_menu()
            if not all_items:
                self.announce(f"No items available in this menu")
                return
                
            # If there are items but none in any group, use the first item
            self.current_position = 0
            details = self.get_element_details(current_menu, self.current_position)
            if details:
                self.queue_cursor_movement(details['coordinates'])
                self.announce_element(details)
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
            details = self.get_element_details(current_menu, self.current_position)
            if details:
                self.queue_cursor_movement(details['coordinates'])
                self.announce_element(details)
            else:
                self.announce("Item not found")
        else:
            self.announce("No menu selected")
    
    def _select_current_item(self):
        """Select the currently focused item"""
        if not self.menu_stack:
            self.announce("No menu selected")
            return
            
        items = self.get_active_items_in_current_menu()
        if not items:
            self.announce("No items available")
            return
            
        details = self.get_element_details(self.menu_stack[-1], self.current_position)
        if not details:
            self.announce("Item not found")
            return
        
        # Perform click
        self.queue_mouse_click(details['coordinates'])
        
        # Simplified announcement
        self.announce(f"{details['name']} selected")
        
        # Store last position
        if self.menu_stack:
            self.last_positions[self.menu_stack[-1]] = self.current_position
    
    def _return_to_parent_menu(self):
        """Pop current menu from stack and return to previous menu"""
        if len(self.menu_stack) <= 1:
            current_menu = self.menu_stack[0] if self.menu_stack else "No menu"
            self.announce(f"{current_menu}")
            return False
        
        # Store the name of the menu we're leaving
        leaving_menu_name = self.menu_stack[-1]
        
        # Remove current menu
        self.menu_stack.pop()
        
        # Restore last position in the parent menu
        parent_menu = self.menu_stack[-1]
        if parent_menu in self.last_positions:
            self.set_current_position(self.last_positions[parent_menu])
        else:
            self.set_current_position(0)
        
        return True
    
    def get_active_items_in_current_menu(self):
        """
        Get all active items from current menu, filtering by element conditions
        
        Returns:
            list: Active menu items
        """
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
        all_items = menu_data.get("items", [])
        
        # Check if we need to filter items based on conditions
        has_conditional_items = any(len(item) > 9 and item[9] for item in all_items)
        
        if not has_conditional_items:
            return all_items  # No filtering needed
            
        # Take a screenshot for condition checking
        screenshot = np.array(pyautogui.screenshot())
        
        # Filter items based on their conditions
        active_items = []
        for item in all_items:
            if self.is_element_active(item, screenshot):
                active_items.append(item)
                
        return active_items
    
    @lru_cache(maxsize=128)
    def get_element_details(self, menu_id, position):
        """
        Get detailed information about a menu element
        
        Args:
            menu_id: Menu identifier
            position: Index of element in the menu
            
        Returns:
            dict: Element details or None if not found
        """
        if menu_id not in self.menus:
            return None
            
        items = self.menus[menu_id].get("items", [])
        
        if not items or position >= len(items):
            return None
            
        item = items[position]
        
        # Determine if this item has a submenu
        has_submenu = item[4] is not None
        submenu_indicator = "submenu" if has_submenu else ""
        
        # Get the group for this item
        item_group = item[5] if len(item) > 5 else "default"
        
        # Get all items in this group to calculate position within group
        group_items = self.get_items_in_group(menu_id, item_group)
        
        # Find the index of this position within the group
        try:
            group_index = group_items.index(position)
            group_index_message = f"{group_index + 1} of {len(group_items)}"
        except ValueError:
            # Fallback if item not found in its own group (shouldn't happen)
            group_index_message = f"1 of {len(group_items)}"
        
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
            'index_message': group_index_message,  # Now uses group-specific index
            'overall_index_message': f"{position + 1} of {len(items)}",  # Keep overall index for reference
            'has_submenu': has_submenu,
            'submenu_indicator': submenu_indicator,
            'group': item_group,
            'has_ocr': has_ocr,
            'custom_announcement': custom_announcement
        }
    
    def announce_element(self, details):
        """
        Announce an element with proper formatting
        
        Args:
            details: Element details dictionary
        """
        if not details:
            self.announce("No item selected")
            return
        
        # Process OCR regions if present
        ocr_results = {}
        if details.get('has_ocr'):
            ocr_results = self.get_ocr_text_for_element(self.menu_stack[-1], self.current_position)
        
        # Check if the group has changed since last announcement
        current_group = details['group']
        if current_group != self.last_announced_group:
            # Group has changed, announce the group name first (without "Group:" prefix)
            self.announce(f"{current_group}")
            self.last_announced_group = current_group
        
        # Format the announcement
        message = self.format_element_announcement(details, ocr_results)
        self.announce(message)
    
    def set_current_position(self, position, announce=True):
        """
        Set current position within the menu
        
        Args:
            position: Index of element to focus
            announce: Whether to announce the element (default: True)
        """
        if not self.menu_stack:
            self.announce("No menu selected")
            return
            
        self.current_position = position
        
        details = self.get_element_details(self.menu_stack[-1], position)
        if details:
            self.queue_cursor_movement(details['coordinates'])
            if announce:
                # Check if group changed
                if details['group'] != self.current_group:
                    self.current_group = details['group']
                self.announce_element(details)
        else:
            self.announce("Item not found")
    
    def get_unique_groups_in_menu(self, menu_id):
        """
        Get all unique groups in a menu
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            list: List of group names, sorted
        """
        if menu_id not in self.menus:
            return []  # Return empty list instead of ["default"]
            
        # Check if we already have the groups cached
        if menu_id in self.menu_groups:
            return self.menu_groups[menu_id]
        
        # Find all unique groups in the menu
        groups = set()
        items = self.menus[menu_id].get("items", [])
        
        for item in items:
            # Add group (with empty string fallback if not present)
            if len(item) > 5 and item[5]:
                groups.add(item[5])
            else:
                groups.add("default")  # Use default instead of empty string for better UX
        
        # Sort groups for consistent navigation
        sorted_groups = sorted(list(groups))
        
        # Cache the result
        self.menu_groups[menu_id] = sorted_groups
        
        return sorted_groups
    
    def get_next_group_in_menu(self, current_group, menu_id):
        """
        Get the next group in the menu
        
        Args:
            current_group: Current group name
            menu_id: Menu identifier
            
        Returns:
            str: Name of next group
        """
        groups = self.get_unique_groups_in_menu(menu_id)
        if not groups:
            return "default"
            
        try:
            idx = groups.index(current_group)
            next_idx = (idx + 1) % len(groups)
            return groups[next_idx]
        except ValueError:
            # Current group not found, return first group
            return groups[0]
    
    def get_previous_group_in_menu(self, current_group, menu_id):
        """
        Get the previous group in the menu
        
        Args:
            current_group: Current group name
            menu_id: Menu identifier
            
        Returns:
            str: Name of previous group
        """
        groups = self.get_unique_groups_in_menu(menu_id)
        if not groups:
            return "default"
            
        try:
            idx = groups.index(current_group)
            prev_idx = (idx - 1) % len(groups)
            return groups[prev_idx]
        except ValueError:
            # Current group not found, return first group
            return groups[0]
        
    def navigate_to_group_by_name(self, group, announce=True):
        """
        Navigate to a specific group by name
        
        Args:
            group: Group name to navigate to
            announce: Whether to announce the element (default: True)
            
        Returns:
            bool: True if navigation successful, False otherwise
        """
        if not self.menu_stack:
            return False
            
        menu_id = self.menu_stack[-1]
        items = self.get_items_in_group(menu_id, group)
        
        if not items:
            # Look for a different group that has items
            self.log_message(f"No items found in group '{group}' for menu '{menu_id}', looking for alternative", logging.WARNING)
            
            all_groups = self.get_unique_groups_in_menu(menu_id)
            alternative_group = None
            
            # Try to find any group with items
            for g in all_groups:
                if g != group:  # Skip the original group
                    group_items = self.get_items_in_group(menu_id, g)
                    if group_items:
                        alternative_group = g
                        break
            
            if alternative_group:
                self.log_message(f"Found alternative group '{alternative_group}' with items", logging.INFO)
                group = alternative_group
                items = self.get_items_in_group(menu_id, group)
            else:
                self.log_message(f"No groups with items found in menu '{menu_id}'", logging.WARNING)
                # Check if there are any items at all
                all_items = self.get_active_items_in_current_menu()
                if not all_items:
                    self.announce(f"No items available in this menu")
                    return False
                
                # If there are items but none in any group, use position 0
                self.current_position = 0
                details = self.get_element_details(menu_id, 0)
                if details:
                    self.queue_cursor_movement(details['coordinates'])
                    if announce:
                        self.announce_element(details)
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
        self.set_current_position(position, announce=announce)
        
        # Update last_announced_group to prevent duplicate announcement
        self.last_announced_group = group
        
        return True
    
    def get_items_in_group(self, menu_id, group):
        """
        Get indices of items in a specific group
        
        Args:
            menu_id: Menu identifier
            group: Group name
            
        Returns:
            list: List of item indices in the group
        """
        if menu_id not in self.menus:
            self.log_message(f"Menu '{menu_id}' not found when looking for group '{group}' items", logging.WARNING)
            return []
            
        items = self.menus[menu_id].get("items", [])
        if not items:
            self.log_message(f"Menu '{menu_id}' has no items when looking for group '{group}'", logging.WARNING)
            return []
            
        # Check if we need to filter items based on conditions
        has_conditional_items = any(len(item) > 9 and item[9] for item in items)
        
        if not has_conditional_items:
            # No filtering needed, just return items in the group
            group_indices = []
            for i, item in enumerate(items):
                item_group = "default"
                if len(item) > 5 and item[5]:
                    item_group = item[5]
                    
                if item_group == group:
                    group_indices.append(i)
                    
            return sorted(group_indices, key=lambda idx: items[idx][8] if len(items[idx]) > 8 else 0)
        
        # Take a screenshot for condition checking
        screenshot = np.array(pyautogui.screenshot())
        
        # Filter items based on their conditions and group
        group_indices = []
        for i, item in enumerate(items):
            item_group = "default"
            if len(item) > 5 and item[5]:
                item_group = item[5]
                
            if item_group == group and self.is_element_active(item, screenshot):
                group_indices.append(i)
                
        # Sort by index field if available
        return sorted(group_indices, key=lambda idx: items[idx][8] if len(items[idx]) > 8 else 0)

    def get_unique_groups_sorted(self, menu_id):
        """
        Get all unique groups in a menu, sorted by their lowest element index
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            list: List of group names, sorted by lowest index
        """
        if menu_id not in self.menus:
            return ["default"]
            
        # Check if we already have the groups cached
        if menu_id in self.menu_groups:
            return self.menu_groups[menu_id]
        
        # Find all unique groups in the menu and track their lowest element index
        groups = {}  # Dict mapping group name to lowest index
        items = self.menus[menu_id].get("items", [])
        
        for item in items:
            # Check if item is active based on conditions
            if len(item) > 9 and item[9] and not self.is_element_active(item):
                continue  # Skip inactive items
                
            # Get item group and index
            if len(item) > 5 and item[5]:
                group_name = item[5]
            else:
                group_name = "default"
                
            index = item[8] if len(item) > 8 else 0
            
            # Update group with lowest index
            if group_name not in groups or index < groups[group_name]:
                groups[group_name] = index
        
        # Always include default group
        if not groups:
            groups["default"] = 0
            
        # Sort groups by their lowest element index
        sorted_groups = sorted(groups.keys(), key=lambda g: groups[g])
        
        # Cache the result
        self.menu_groups[menu_id] = sorted_groups
        
        return sorted_groups
    
    def navigate_to_next_group_with_items(self):
        """Navigate to next group that contains items"""
        if not self.menu_stack:
            self.announce("No menu selected")
            return
            
        menu_id = self.menu_stack[-1]
        
        # Get all groups
        all_groups = self.get_unique_groups_in_menu(menu_id)
        if not all_groups:
            self.announce("No groups available")
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
            items = self.get_items_in_group(menu_id, next_group)
            if items:
                # Found a group with items
                if self.navigate_to_group_by_name(next_group):
                    # Don't announce the group name here, it will be announced in navigate_to_group
                    return
        
        # If we get here, no other group has items
        self.announce(f"No other groups with items available")
    
    def navigate_to_previous_group_with_items(self):
        """Navigate to previous group that contains items"""
        if not self.menu_stack:
            self.announce("No menu selected")
            return
            
        menu_id = self.menu_stack[-1]
        
        # Get all groups
        all_groups = self.get_unique_groups_in_menu(menu_id)
        if not all_groups:
            self.announce("No groups available")
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
            items = self.get_items_in_group(menu_id, prev_group)
            if items:
                # Found a group with items
                if self.navigate_to_group_by_name(prev_group):
                    # Don't announce the group name here, it will be announced in navigate_to_group
                    return
        
        # If we get here, no other group has items
        self.announce(f"No other groups with items available")
        
        return True
    
    def detect_menu_changes(self):
        """
        Check for menu changes with improved group handling
        
        Returns:
            bool: True if menu changed, False otherwise
        """
        # Just return the result of the last check from the detection thread
        current_time = time.time()
        
        # If it's been too long since our last check, force one now
        if current_time - self.last_menu_check > self.menu_check_interval * 3:
            # Direct check
            active_menu = self.condition_checker.find_active_menu(self.menus)
            self.last_menu_check = current_time
            
            # Process if we have a new menu
            if active_menu and (not self.menu_stack or active_menu != self.menu_stack[0]):
                self.log_message(f"Force detected new menu: {active_menu}")
                old_menu = self.menu_stack[0] if self.menu_stack else None
                self.menu_stack = [active_menu]
                
                # Get the group to reset to if specified
                reset_group = self.menus[active_menu].get("reset_group", None)
                
                # Find a valid group (with items)
                valid_group = self.find_valid_group(active_menu, reset_group)
                self.current_group = valid_group
                
                # Check if we have a saved position for this group in this menu
                if active_menu in self.menu_group_positions and valid_group in self.menu_group_positions[active_menu]:
                    self.current_position = self.menu_group_positions[active_menu][valid_group]
                else:
                    # Use position 0 in the specific group
                    group_items = self.get_items_in_group(active_menu, valid_group)
                    if group_items:
                        self.current_position = group_items[0]
                    else:
                        self.current_position = 0
                    
                return True
        
        return False
    
    def _handle_key_press(self, key):
        """
        Handle keyboard key press events
        
        Args:
            key: Key object from pynput
            
        Returns:
            bool: False to stop listening, True to continue
        """
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
                    self.navigate_to_previous_group_with_items()
                else:
                    # Next group
                    self.navigate_to_next_group_with_items()
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
                    self.log_message("Exiting menu navigation")
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
                    details = self.get_element_details(self.menu_stack[-1], self.current_position)
                    if details and details['has_submenu']:
                        self.mouse_queue.put({
                            'type': 'select'
                        })
        except Exception as e:
            self.log_message(f"Error during key handling: {e}", logging.ERROR)
        
        return True
    
    def _handle_key_release(self, key):
        """
        Handle keyboard key release events
        
        Args:
            key: Key object from pynput
            
        Returns:
            bool: False to stop listening, True to continue
        """
        try:
            # Track shift key state
            if key == keyboard.Key.shift:
                self.shift_pressed = False
        except Exception as e:
            self.log_message(f"Error during key release handling: {e}", logging.ERROR)
        
        return True


def main():
    """Main function with optimized startup and debug mode"""
    parser = argparse.ArgumentParser(description="High-Performance Accessible Menu Navigation")
    parser.add_argument("profile", nargs="?", default="fortnite.json", help="Path to menu profile JSON file")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode (logs to file)")
    parser.add_argument("--languages", type=str, default="en", help="OCR languages, comma-separated (e.g., 'en,fr,es')")
    args = parser.parse_args()
    
    # Parse OCR languages
    ocr_languages = [lang.strip() for lang in args.languages.split(',')]
    
    # Set up file-based logging if debug mode is enabled
    if args.debug:
        log_file = "ma_debug.log"
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        print(f"Debug logging enabled. Log file: {log_file}")
    
    # Create the navigator
    navigator = AccessibleMenuNavigator()
    
    # Set debug mode based on command line flag
    navigator.set_debug(args.debug)
    
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
