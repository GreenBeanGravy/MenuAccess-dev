"""
Menu condition checking functionality for the MenuAccess application
"""

import numpy as np
import cv2
import base64
import io
import time
import logging
import re # For ocr_text_match regex
from PIL import Image

from malib.screen_capture import ScreenCapture
# OCRHandler will be accessed via self.ocr_handler if needed by a condition type

logger = logging.getLogger("AccessibleMenuNav")

class MenuConditionChecker:
    """Highly optimized class for checking menu conditions with performance enhancements"""
    
    def __init__(self, ocr_handler=None): # Added ocr_handler parameter
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
        
        # Create screen capture instance
        self.screen_capture = ScreenCapture()
        self.ocr_handler = ocr_handler # Store OCR handler instance
    
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
        negate = condition.get("negate", False)
        result = False # Default to false

        if condition_type == "pixel_color":
            try:
                x = condition.get("x", 0)
                y = condition.get("y", 0) 
                expected_color = condition.get("color", [0, 0, 0])
                tolerance = condition.get("tolerance", 0)
                
                # Make sure coordinates are within bounds
                width, height = screenshot_pil.size
                if x < 0 or x >= width or y < 0 or y >= height:
                    if self.verbose:
                        logger.debug(f"Pixel at ({x},{y}) is out of bounds for image of size {width}x{height}")
                    result = False
                else:
                    # Get pixel color direct from PIL Image
                    pixel_color = screenshot_pil.getpixel((x, y))
                    
                    # Handle different color formats (RGB vs RGBA)
                    if len(pixel_color) > 3:
                        pixel_color = pixel_color[:3]  # Take only RGB components
                    
                    # Convert both colors to HSV for more perceptually relevant comparison
                    pixel_rgb_cv = np.array([[pixel_color]], dtype=np.uint8)
                    expected_rgb_cv = np.array([[expected_color]], dtype=np.uint8)
                    
                    pixel_hsv = cv2.cvtColor(pixel_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                    expected_hsv = cv2.cvtColor(expected_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                    
                    h1, s1, v1 = pixel_hsv.astype(float)
                    h2, s2, v2 = expected_hsv.astype(float)
                    
                    h_diff = min(abs(h1 - h2), 180 - abs(h1 - h2))
                    weighted_diff = (h_diff * 2.0) + (abs(s1 - s2) / 2.0) + (abs(v1 - v2) / 4.0)
                    
                    if self.verbose:
                        logger.debug(f"Pixel at ({x},{y}): found {pixel_color}, expected {expected_color}, diff={weighted_diff:.1f}, tolerance={tolerance}")
                    
                    result = weighted_diff <= tolerance
            except Exception as e:
                if self.verbose:
                    logger.error(f"Pixel check error: {str(e)}")
                result = False
                
        elif condition_type == "pixel_region_color":
            try:
                x1 = condition.get("x1", 0)
                y1 = condition.get("y1", 0)
                x2 = condition.get("x2", 0)
                y2 = condition.get("y2", 0)
                expected_color = condition.get("color", [0, 0, 0])
                tolerance = condition.get("tolerance", 0)
                threshold = condition.get("threshold", 0.5)
                
                width, height = screenshot_pil.size
                if x1 < 0 or x2 > width or y1 < 0 or y2 > height:
                    if self.verbose:
                        logger.debug(f"Region ({x1},{y1}) to ({x2},{y2}) outside image of size {width}x{height}")
                    result = False
                else:
                    region = screenshot_pil.crop((x1, y1, x2, y2))
                    matches = 0
                    total_pixels = 0
                    region_array = np.array(region)
                    
                    if region_array.shape[2] > 3:
                        non_transparent = np.sum(region_array[:,:,3] > 0)
                        if non_transparent == 0:
                            result = False
                        else:
                            total_pixels = non_transparent
                    else:
                        total_pixels = region_array.shape[0] * region_array.shape[1]

                    if total_pixels == 0: # Avoid division by zero if region is empty or fully transparent
                        result = False
                    elif total_pixels > 1000:
                        sample_count = min(100, max(25, total_pixels // 400))
                        reg_height, reg_width = region_array.shape[:2]
                        y_indices = np.linspace(0, reg_height-1, int(np.sqrt(sample_count)), dtype=int)
                        x_indices = np.linspace(0, reg_width-1, int(np.sqrt(sample_count)), dtype=int)
                        
                        for y_idx in y_indices:
                            for x_idx in x_indices:
                                pixel_color = region_array[y_idx, x_idx][:3]
                                pixel_rgb_cv = np.array([[pixel_color]], dtype=np.uint8)
                                expected_rgb_cv = np.array([[expected_color]], dtype=np.uint8)
                                pixel_hsv = cv2.cvtColor(pixel_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                                expected_hsv = cv2.cvtColor(expected_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                                h1, s1, v1 = pixel_hsv.astype(float)
                                h2, s2, v2 = expected_hsv.astype(float)
                                h_diff = min(abs(h1 - h2), 180 - abs(h1 - h2))
                                weighted_diff = (h_diff * 2.0) + (abs(s1 - s2) / 2.0) + (abs(v1 - v2) / 4.0)
                                if weighted_diff <= tolerance:
                                    matches += 1
                        total_pixels = len(y_indices) * len(x_indices) # Actual number of samples
                        if total_pixels == 0: result = False # Avoid division by zero
                        else: match_percentage = matches / total_pixels; result = match_percentage >= threshold
                    else:
                        for y_idx in range(region_array.shape[0]):
                            for x_idx in range(region_array.shape[1]):
                                pixel_color = region_array[y_idx, x_idx][:3]
                                pixel_rgb_cv = np.array([[pixel_color]], dtype=np.uint8)
                                expected_rgb_cv = np.array([[expected_color]], dtype=np.uint8)
                                pixel_hsv = cv2.cvtColor(pixel_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                                expected_hsv = cv2.cvtColor(expected_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
                                h1, s1, v1 = pixel_hsv.astype(float)
                                h2, s2, v2 = expected_hsv.astype(float)
                                h_diff = min(abs(h1 - h2), 180 - abs(h1 - h2))
                                weighted_diff = (h_diff * 2.0) + (abs(s1 - s2) / 2.0) + (abs(v1 - v2) / 4.0)
                                if weighted_diff <= tolerance:
                                    matches += 1
                        if total_pixels == 0: result = False # Avoid division by zero
                        else: match_percentage = matches / total_pixels; result = match_percentage >= threshold
                    
                    if self.verbose:
                        logger.debug(f"Region ({x1},{y1}) to ({x2},{y2}): match={match_percentage if total_pixels > 0 else 0:.2f}, threshold={threshold}")
            except Exception as e:
                if self.verbose:
                    logger.error(f"Region color check error: {str(e)}")
                result = False
                
        elif condition_type == "pixel_region_image":
            try:
                x1 = condition.get("x1", 0)
                y1 = condition.get("y1", 0)
                x2 = condition.get("x2", 0)
                y2 = condition.get("y2", 0)
                image_data = condition.get("image_data")
                confidence = condition.get("confidence", 0.8)
                
                if not image_data:
                    result = False
                else:
                    width, height = screenshot_pil.size
                    if x1 < 0 or x2 > width or y1 < 0 or y2 > height:
                        if self.verbose:
                            logger.debug(f"Region ({x1},{y1}) to ({x2},{y2}) outside image of size {width}x{height}")
                        result = False
                    else:
                        image_bytes = base64.b64decode(image_data)
                        template_pil = Image.open(io.BytesIO(image_bytes))
                        region = screenshot_pil.crop((x1, y1, x2, y2))
                        template_cv = np.array(template_pil)
                        region_cv = np.array(region)
                        
                        if len(template_cv.shape) > 2:
                            template_gray = cv2.cvtColor(template_cv, cv2.COLOR_RGB2GRAY)
                        else:
                            template_gray = template_cv
                            
                        if len(region_cv.shape) > 2:
                            region_gray = cv2.cvtColor(region_cv, cv2.COLOR_RGB2GRAY)
                        else:
                            region_gray = region_cv
                        
                        if template_gray.shape[:2] != region_gray.shape[:2]:
                            template_gray = cv2.resize(template_gray, (region_gray.shape[1], region_gray.shape[0]))
                        
                        match_val = cv2.matchTemplate(region_gray, template_gray, cv2.TM_SQDIFF_NORMED)[0, 0]
                        similarity = 1.0 - match_val
                        
                        if self.verbose:
                            logger.debug(f"Image match score: {similarity:.3f}, confidence threshold: {confidence:.3f}")
                        
                        result = similarity >= confidence
            except Exception as e:
                if self.verbose:
                    logger.error(f"Image match error: {str(e)}")
                result = False
        
        elif condition_type == "or":
            sub_conditions = condition.get("conditions", [])
            if len(sub_conditions) != 2: # OR condition expects exactly two sub-conditions
                if self.verbose:
                    logger.warning(f"OR condition expects 2 sub-conditions, found {len(sub_conditions)}")
                result = False
            else:
                res1 = self._check_condition(sub_conditions[0], screenshot_pil)
                res2 = self._check_condition(sub_conditions[1], screenshot_pil)
                result = res1 or res2
        
        elif condition_type == "ocr_text_match":
            if not self.ocr_handler:
                if self.verbose:
                    logger.warning("OCR handler not available for ocr_text_match condition.")
                result = False
            else:
                try:
                    x1 = condition.get("x1", 0)
                    y1 = condition.get("y1", 0)
                    x2 = condition.get("x2", 0)
                    y2 = condition.get("y2", 0)
                    expected_text = condition.get("expected_text", "")
                    match_mode = condition.get("match_mode", "contains") # "exact", "regex"
                    case_sensitive = condition.get("case_sensitive", False)

                    width, height = screenshot_pil.size
                    if x1 < 0 or x2 > width or y1 < 0 or y2 > height or x1 >= x2 or y1 >= y2:
                        if self.verbose:
                            logger.debug(f"OCR Region ({x1},{y1}) to ({x2},{y2}) invalid for image of size {width}x{height}")
                        result = False
                    else:
                        extracted_text = self.ocr_handler.extract_text(screenshot_pil, (x1, y1, x2, y2))
                        
                        if not case_sensitive:
                            extracted_text = extracted_text.lower()
                            expected_text_cmp = expected_text.lower()
                        else:
                            expected_text_cmp = expected_text

                        if match_mode == "exact":
                            result = extracted_text == expected_text_cmp
                        elif match_mode == "contains":
                            result = expected_text_cmp in extracted_text
                        elif match_mode == "regex":
                            try:
                                flags = 0 if case_sensitive else re.IGNORECASE
                                result = re.search(expected_text, extracted_text, flags) is not None
                            except re.error as re_err:
                                if self.verbose:
                                    logger.error(f"Regex error in ocr_text_match: {re_err}")
                                result = False
                        else: # Default to contains
                            result = expected_text_cmp in extracted_text
                        
                        if self.verbose:
                            logger.debug(f"OCR Text Match: Region=({x1},{y1},{x2},{y2}), Expected='{expected_text}', Extracted='{extracted_text}', Mode='{match_mode}', CaseSensitive={case_sensitive}, Result={result}")

                except Exception as e:
                    if self.verbose:
                        logger.error(f"OCR text match error: {str(e)}")
                    result = False
        else:
            # Unknown condition type
            if self.verbose:
                logger.warning(f"Unknown condition type: {condition_type}")
            result = False

        return not result if negate else result
    
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
            # Take a new screenshot using our screen capture class
            try:
                screenshot_pil = self.screen_capture.capture()
                
                # Update cache
                self._screenshot_cache = screenshot_pil
                self._last_screenshot_time = current_time
                
                # Clear outdated cache entries
                self._cache = {k: v for k, v in self._cache.items() 
                               if k[1] >= current_time - self._cache_ttl}
                    
            except Exception as e:
                if self.verbose:
                    logger.error(f"Screenshot error: {e}")
                return self.last_active_menu # Return last known active menu on screenshot error
        
        # Collect all matching menus and their condition counts
        matching_menus = []
        
        # Fast path: Check previously active menu first
        if self.last_active_menu and self.last_active_menu in all_menus:
            menu_data = all_menus[self.last_active_menu]
            if menu_data.get("is_manual", False): # If last active was manual, it remains active until explicitly changed
                return self.last_active_menu
            if self.check_menu_conditions(menu_data, screenshot_pil):
                # Current menu still active, no need to check others
                return self.last_active_menu
        
        # Check all other menus and their condition counts
        for menu_id, menu_data in all_menus.items():
            # Skip the already checked menu or manual menus
            if menu_id == self.last_active_menu or menu_data.get("is_manual", False):
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
        
        # No change detected, keep previous menu (could be None or a manual menu)
        # If last_active_menu was conditional and failed, it will become None here.
        # If it was manual, it would have been returned earlier.
        # If no menu matches, and last_active_menu was conditional and now fails, it should be None.
        if self.last_active_menu and self.last_active_menu in all_menus and not all_menus[self.last_active_menu].get("is_manual", False):
             # If the previously active menu was conditional and no longer matches, and no other menu matches, then no menu is active.
            self.last_active_menu = None

        return self.last_active_menu