"""
Main accessible menu navigator functionality - Fixed OCR Delay Implementation
"""

import os
import re
import json
import time
import queue
import logging
import threading
import ctypes
import pyautogui
import numpy as np
from PIL import Image
from functools import lru_cache
from pynput import keyboard

from malib.condition_checker import MenuConditionChecker
from malib.screen_capture import ScreenCapture
from malib.ocr_handler import OCRHandler
from malib.utils import MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

logger = logging.getLogger("AccessibleMenuNav")

class AccessibleMenuNavigator:
    """Main class for accessible menu navigation with performance optimizations"""
    
    def __init__(self):
        """Initialize the navigator with optimized structures and components"""
        self.menu_stack = []
        self.current_position = 0
        self.last_positions = {}
        self.speaker = None  # Will be initialized in start
        self.menus = {}
        self.verbose = False
        self.debug = False
        
        # Group navigation system
        self.current_group = "default"
        self.group_positions = {}  # Stores the position within each group
        self.menu_groups = {}      # Stores the groups for each menu
        self.menu_group_positions = {}  # Format: {menu_id: {group_name: position}}
        self.last_announced_group = None
        
        # Performance optimizations
        self.condition_checker = MenuConditionChecker()
        self.menu_check_interval = 0.05
        self.last_menu_check = 0
        self.menu_check_ongoing = False
        self.last_detected_menu = None
        
        # Thread-local storage for screen capture instances
        self.thread_locals = threading.local()
        
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
        
        # OCR handler
        self.ocr_handler = None
    
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
                    logger.error(f"Speech error: {speech_error}")
                    
                    # Try to reinitialize the speech engine
                    try:
                        import accessible_output2.outputs.auto as ao
                        self.speaker = ao.Auto()
                        logger.info("Reinitialized speech engine")
                    except:
                        logger.error("Failed to reinitialize speech engine")
                
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
    
    def start(self, profile_path, languages=None):
        """
        Start the navigator with the specified profile
        
        Args:
            profile_path: Path to menu profile JSON file
            languages: List of language codes for OCR
        """
        # Initialize speaker
        try:
            import accessible_output2.outputs.auto as ao
            self.speaker = ao.Auto()
        except ImportError:
            logger.error("Failed to import accessible_output2. Speech will not be available.")
            # Create a dummy speaker that logs instead
            class DummySpeaker:
                def speak(self, message):
                    logger.info(f"SPEECH: {message}")
            self.speaker = DummySpeaker()
        
        # Initialize OCR handler
        self.ocr_handler = OCRHandler(languages)
        
        self.log_message("Ready!")
        self.announce("Menu Access ready")
        
        # Initialize OCR reader in the background
        threading.Thread(target=self.ocr_handler.initialize_reader, daemon=True).start()
        
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
            
            # Clean up screen capture resources
            self.condition_checker.screen_capture.close()
            
            self.log_message("Exiting")
    
    def get_thread_screen_capture(self):
        """
        Get a thread-specific screen capture instance using thread-local storage
        
        Returns:
            ScreenCapture: A screen capture instance for the current thread
        """
        # Use thread-local storage to ensure each thread has its own capture instance
        if not hasattr(self.thread_locals, 'screen_capture'):
            self.thread_locals.screen_capture = ScreenCapture()
            thread_id = threading.get_ident()
            logger.debug(f"Created new ScreenCapture for thread {thread_id}")
        
        return self.thread_locals.screen_capture
    
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
                    
                    # If there's a callback, execute it with OCR delay handling
                    if 'callback' in command and command['callback']:
                        # Apply OCR delay if specified
                        if 'ocr_delay_ms' in command and command['ocr_delay_ms'] > 0:
                            delay_ms = command['ocr_delay_ms']
                            self.log_message(f"Applying OCR delay of {delay_ms}ms after mouse movement", logging.DEBUG)
                            time.sleep(delay_ms / 1000.0)  # Convert ms to seconds
                        
                        # Execute the callback function
                        callback_func = command['callback']
                        callback_func()
                    
                elif command['type'] == 'click':
                    self._click_at_position(command['position'][0], command['position'][1])
                    
                    # If there's a callback, execute it
                    if 'callback' in command and command['callback']:
                        callback_func = command['callback']
                        callback_func()
                        
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
                        # Create a callback function to handle announcing after movement
                        def announce_callback():
                            self.announce_element(details)
                        
                        # Queue cursor movement with callback and OCR delay
                        ocr_delay_ms = details.get('ocr_delay_ms', 0)
                        self.queue_cursor_movement(details['coordinates'], 
                                                  callback=announce_callback,
                                                  ocr_delay_ms=ocr_delay_ms)
                
                # Brief pause to reduce CPU usage
                time.sleep(0.01)
                
            except Exception as e:
                self.log_message(f"Menu detection error: {e}", logging.ERROR)
                time.sleep(0.1)  # Longer pause on error
    
    def is_element_active(self, element, screenshot=None):
        """
        Check if a UI element's conditions are met
        
        Args:
            element: Element data
            screenshot: Screenshot as PIL Image (optional)
            
        Returns:
            bool: True if element is active, False otherwise
        """
        # If element has no conditions, it's always active
        if len(element) <= 9 or not element[9]:
            return True
            
        # Take a screenshot if not provided (using thread-specific screen capture)
        if screenshot is None:
            screen_capture = self.get_thread_screen_capture()
            screenshot_pil = screen_capture.capture()
            screenshot = screenshot_pil
            
        # Check each condition - all must be met for the element to be active
        for condition in element[9]:
            if not self.condition_checker._check_condition(condition, screenshot):
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
        
        # Log that we're starting OCR processing for this element
        self.log_message(f"Starting OCR processing for element: {element_name}", logging.DEBUG)
        
        # Check if element has OCR regions
        if len(element) <= 6 or not element[6]:
            self.log_message(f"Element {element_name} has no OCR regions", logging.DEBUG)
            return {}
            
        ocr_regions = element[6]
        results = {}
        
        # Log OCR regions
        self.log_message(f"Element {element_name} has {len(ocr_regions)} OCR regions", logging.DEBUG)
        
        # Take a screenshot for condition checking (using thread-specific screen capture)
        screen_capture = self.get_thread_screen_capture()
        screenshot_pil = screen_capture.capture()
        
        # Process each OCR region
        for region in ocr_regions:
            tag = region.get("tag", "ocr1")
            x1 = region.get("x1", 0)
            y1 = region.get("y1", 0)
            x2 = region.get("x2", 0)
            y2 = region.get("y2", 0)
            
            # Log OCR region details
            self.log_message(f"Processing OCR region '{tag}' at ({x1},{y1},{x2},{y2})", logging.DEBUG)
            
            # Check if region has conditions. If so, check if they're met
            if "conditions" in region and region["conditions"]:
                # Only perform OCR if all conditions are met
                all_conditions_met = True
                for condition in region["conditions"]:
                    if not self.condition_checker._check_condition(condition, screenshot_pil):
                        all_conditions_met = False
                        break
                
                if not all_conditions_met:
                    self.log_message(f"OCR region '{tag}' conditions not met, skipping OCR", logging.DEBUG)
                    results[tag] = ""  # Empty result for condition not met
                    continue
            
            # All conditions met (or no conditions), perform OCR
            text = self.ocr_handler.extract_text(screenshot_pil, (x1, y1, x2, y2))
            results[tag] = text
            
            # Log result if in debug mode
            if self.debug:
                if text.strip():
                    self.log_message(f"OCR region '{tag}' extracted text: '{text}'", logging.DEBUG)
                else:
                    self.log_message(f"OCR region '{tag}' extracted NO TEXT (empty result)", logging.DEBUG)
        
        return results
    
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
    
    def queue_cursor_movement(self, end_pos, callback=None, ocr_delay_ms=0):
        """
        Add cursor movement to queue for processing by mouse thread
        
        Args:
            end_pos: Tuple of (x, y) coordinates
            callback: Optional function to execute after movement completes
            ocr_delay_ms: OCR delay in milliseconds to apply before callback
        """
        self.mouse_queue.put({
            'type': 'move',
            'end_pos': end_pos,
            'callback': callback,
            'ocr_delay_ms': ocr_delay_ms
        })
    
    def queue_mouse_click(self, position, callback=None):
        """
        Add mouse click to queue for processing by mouse thread
        
        Args:
            position: Tuple of (x, y) coordinates
            callback: Optional function to execute after click completes
        """
        self.mouse_queue.put({
            'type': 'click',
            'position': position,
            'callback': callback
        })
    
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
                        # Create a callback function to handle announcing after movement
                        def announce_callback():
                            self.announce_element(details)
                        
                        # Queue cursor movement with callback and OCR delay
                        ocr_delay_ms = details.get('ocr_delay_ms', 0)
                        self.queue_cursor_movement(details['coordinates'], 
                                                  callback=announce_callback,
                                                  ocr_delay_ms=ocr_delay_ms)
                        return
        
        # If we still have no items, check if there are any items at all
        all_items = self.get_active_items_in_current_menu()
        if not group_items and not all_items:
            self.announce(f"No items available in this menu")
            return
            
        # If there are items but none in any group, use the first item
        if not group_items:
            self.current_position = 0
            details = self.get_element_details(current_menu, self.current_position)
            if details:
                # Create a callback function to handle announcing after movement
                def announce_callback():
                    self.announce_element(details)
                
                # Queue cursor movement with callback and OCR delay
                ocr_delay_ms = details.get('ocr_delay_ms', 0)
                self.queue_cursor_movement(details['coordinates'], 
                                          callback=announce_callback,
                                          ocr_delay_ms=ocr_delay_ms)
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
                # Create a callback function to handle announcing after movement
                def announce_callback():
                    self.announce_element(details)
                
                # Queue cursor movement with callback and OCR delay
                ocr_delay_ms = details.get('ocr_delay_ms', 0)
                self.queue_cursor_movement(details['coordinates'], 
                                          callback=announce_callback,
                                          ocr_delay_ms=ocr_delay_ms)
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
        
        # Create a callback to run after the click is performed
        def after_click_callback():
            # Simplified announcement
            self.announce(f"{details['name']} selected")
            
            # Store last position
            if self.menu_stack:
                self.last_positions[self.menu_stack[-1]] = self.current_position
        
        # Perform click with callback
        self.queue_mouse_click(details['coordinates'], callback=after_click_callback)
    
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
            
        # Take a screenshot for condition checking (using thread-specific screen capture)
        screen_capture = self.get_thread_screen_capture()
        screenshot_pil = screen_capture.capture()
        
        # Filter items based on their conditions
        active_items = []
        for item in all_items:
            if self.is_element_active(item, screenshot_pil):
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
        
        # Check for OCR delay
        ocr_delay_ms = item[10] if len(item) > 10 else 0
        
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
            'custom_announcement': custom_announcement,
            'ocr_delay_ms': ocr_delay_ms  # Include OCR delay for reference
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
            # Check if group changed
            if details['group'] != self.current_group:
                self.current_group = details['group']
            
            if announce:
                # Create a callback function to handle announcing after movement
                def announce_callback():
                    self.announce_element(details)
                
                # Queue cursor movement with callback and OCR delay
                ocr_delay_ms = details.get('ocr_delay_ms', 0)
                self.queue_cursor_movement(details['coordinates'], 
                                          callback=announce_callback,
                                          ocr_delay_ms=ocr_delay_ms)
            else:
                # Just move the cursor without announcing
                self.queue_cursor_movement(details['coordinates'])
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
        groups = set(["default"])
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
                    # Create a callback function to handle announcing after movement
                    if announce:
                        def announce_callback():
                            self.announce_element(details)
                        
                        # Queue cursor movement with callback and OCR delay
                        ocr_delay_ms = details.get('ocr_delay_ms', 0)
                        self.queue_cursor_movement(details['coordinates'], 
                                                 callback=announce_callback,
                                                 ocr_delay_ms=ocr_delay_ms)
                    else:
                        # Just move the cursor without announcing
                        self.queue_cursor_movement(details['coordinates'])
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
        
        # Take a screenshot for condition checking (using thread-specific screen capture)
        screen_capture = self.get_thread_screen_capture()
        screenshot_pil = screen_capture.capture()
        
        # Filter items based on their conditions and group
        group_indices = []
        for i, item in enumerate(items):
            item_group = "default"
            if len(item) > 5 and item[5]:
                item_group = item[5]
                
            if item_group == group and self.is_element_active(item, screenshot_pil):
                group_indices.append(i)
                
        # Sort by index field if available
        return sorted(group_indices, key=lambda idx: items[idx][8] if len(items[idx]) > 8 else 0)

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