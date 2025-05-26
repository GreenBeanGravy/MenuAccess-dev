"""
Menu condition checking functionality for the MenuAccess application
"""

import numpy as np
import cv2
import base64
import io
import time
import logging
from PIL import Image

from malib.screen_capture import ScreenCapture

logger = logging.getLogger("AccessibleMenuNav")

class MenuConditionChecker:
    """Highly optimized class for checking menu conditions with performance enhancements"""
    
    def __init__(self, ocr_handler=None):
        """Initialize the condition checker with performance optimizations"""
        self.verbose = False
        self.last_active_menu = None
        self.ocr_handler = ocr_handler
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
        conditions_logic = menu_data.get("conditions_logic", "AND") # Default to AND
        
        # If no conditions, return False (can't detect)
        if not conditions:
            return False
        
        if conditions_logic == "OR":
            # For OR logic, return True if any condition is met
            for i, condition in enumerate(conditions):
                cache_key = (id(condition), self._last_screenshot_time)
                if cache_key in self._cache:
                    result = self._cache[cache_key]
                else:
                    result = self._check_condition(condition, screenshot_pil)
                    self._cache[cache_key] = result
                
                if result:
                    return True # Any condition met
            return False # No conditions met
        else: # Default to AND logic
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
                    
            # All conditions passed (for AND logic)
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
        
        should_negate = condition.get("negate", False)
        actual_result = False
            
        condition_type = condition.get("type", "")
        
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
                    return False
                
                # Get pixel color direct from PIL Image
                pixel_color = screenshot_pil.getpixel((x, y))
                
                # Handle different color formats (RGB vs RGBA)
                if len(pixel_color) > 3:
                    pixel_color = pixel_color[:3]  # Take only RGB components
                
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
                
                # Debug info in verbose mode
                if self.verbose:
                    logger.debug(f"Pixel at ({x},{y}): found {pixel_color}, expected {expected_color}, diff={weighted_diff:.1f}, tolerance={tolerance}")
                
                actual_result = weighted_diff <= tolerance
            except Exception as e:
                if self.verbose:
                    logger.error(f"Pixel check error: {str(e)}")
                actual_result = False
                
        elif condition_type == "pixel_region_color":
            try:
                x1 = condition.get("x1", 0)
                y1 = condition.get("y1", 0)
                x2 = condition.get("x2", 0)
                y2 = condition.get("y2", 0)
                expected_color = condition.get("color", [0, 0, 0])
                tolerance = condition.get("tolerance", 0)
                threshold = condition.get("threshold", 0.5)
                
                # Check if region is within bounds
                width, height = screenshot_pil.size
                if x1 < 0 or x2 > width or y1 < 0 or y2 > height:
                    if self.verbose:
                        logger.debug(f"Region ({x1},{y1}) to ({x2},{y2}) outside image of size {width}x{height}")
                    return False
                
                # Crop region from PIL Image
                region = screenshot_pil.crop((x1, y1, x2, y2))
                
                # Examine every pixel in the region
                matches = 0
                total_pixels = 0
                
                # Extract the entire region as numpy array for faster processing
                region_array = np.array(region)
                
                # Count total non-transparent pixels
                if region_array.shape[2] > 3:  # If there's an alpha channel
                    non_transparent = np.sum(region_array[:,:,3] > 0)
                    if non_transparent == 0:
                        return False  # Empty region
                    total_pixels = non_transparent
                else:
                    total_pixels = region_array.shape[0] * region_array.shape[1]
                
                # For large regions, sample instead of checking every pixel
                if total_pixels > 1000:
                    # Use sampling approach
                    sample_count = min(100, max(25, total_pixels // 400))
                    
                    # Create grid sampling pattern
                    height, width = region_array.shape[:2]
                    y_indices = np.linspace(0, height-1, int(np.sqrt(sample_count)), dtype=int)
                    x_indices = np.linspace(0, width-1, int(np.sqrt(sample_count)), dtype=int)
                    
                    for y_idx in y_indices:
                        for x_idx in x_indices:
                            pixel_color = region_array[y_idx, x_idx][:3]  # Get RGB
                            
                            # Convert to OpenCV format
                            pixel_rgb_cv = np.array([[pixel_color]], dtype=np.uint8)
                            expected_rgb_cv = np.array([[expected_color]], dtype=np.uint8)
                            
                            # Convert to HSV
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
                    
                    total_pixels = len(y_indices) * len(x_indices)
                else:
                    # For small regions, check every pixel
                    for y in range(region_array.shape[0]):
                        for x in range(region_array.shape[1]):
                            pixel_color = region_array[y, x][:3]  # Get RGB
                            
                            # Convert to OpenCV format
                            pixel_rgb_cv = np.array([[pixel_color]], dtype=np.uint8)
                            expected_rgb_cv = np.array([[expected_color]], dtype=np.uint8)
                            
                            # Convert to HSV
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
                
                # Calculate match percentage
                match_percentage = matches / total_pixels
                result = match_percentage >= threshold
                
                if self.verbose:
                    logger.debug(f"Region ({x1},{y1}) to ({x2},{y2}): match={match_percentage:.2f}, threshold={threshold}")
                
                actual_result = result
                
            except Exception as e:
                if self.verbose:
                    logger.error(f"Region color check error: {str(e)}")
                actual_result = False
                
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
                
                # Check if region is within bounds
                width, height = screenshot_pil.size
                if x1 < 0 or x2 > width or y1 < 0 or y2 > height:
                    if self.verbose:
                        logger.debug(f"Region ({x1},{y1}) to ({x2},{y2}) outside image of size {width}x{height}")
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
                
                # Make sure template and region have the same size
                if template_gray.shape[:2] != region_gray.shape[:2]:
                    # Resize template to match region
                    template_gray = cv2.resize(template_gray, (region_gray.shape[1], region_gray.shape[0]))
                
                # Template matching using normalized squared difference
                # This method is more consistent across brightness variations
                match_result = cv2.matchTemplate(region_gray, template_gray, cv2.TM_SQDIFF_NORMED)[0, 0]
                
                # Convert to a similarity score (0-1 where 1 is perfect match)
                # TM_SQDIFF_NORMED returns 0 for perfect match, 1 for complete mismatch
                similarity = 1.0 - match_result
                
                if self.verbose:
                    logger.debug(f"Image match score: {similarity:.3f}, confidence threshold: {confidence:.3f}")
                
                # Compare with the confidence threshold
                actual_result = similarity >= confidence
                
            except Exception as e:
                if self.verbose:
                    logger.error(f"Image match error: {str(e)}")
                actual_result = False
        
        elif condition_type == "ocr_text_present":
            if not self.ocr_handler:
                logger.warning("OCR handler not available to MenuConditionChecker for ocr_text_present condition.")
                actual_result = False
            else:
                try:
                    text_to_find = condition.get("text_to_find", "")
                    region = condition.get("region", [0,0,0,0]) # x1, y1, x2, y2
                    languages = condition.get("languages", ["en"])
                    case_sensitive = condition.get("case_sensitive", False)

                    # Validate region
                    if not (isinstance(region, list) and len(region) == 4 and 
                            all(isinstance(n, int) for n in region)):
                        logger.warning(f"Invalid region format for ocr_text_present: {region}")
                        actual_result = False
                    elif not text_to_find:
                         logger.warning(f"Empty text_to_find for ocr_text_present.")
                         actual_result = False # Or True if empty string means "any text"? For now, False.
                    else:
                        # Crop the region from the screenshot_pil
                        # Ensure region coordinates are valid for the screenshot size
                        img_width, img_height = screenshot_pil.size
                        x1, y1, x2, y2 = region
                        
                        # Clamp coordinates to be within image bounds
                        x1 = max(0, min(x1, img_width -1))
                        y1 = max(0, min(y1, img_height -1))
                        x2 = max(0, min(x2, img_width))
                        y2 = max(0, min(y2, img_height))

                        if x1 >= x2 or y1 >= y2:
                            logger.warning(f"Invalid region coordinates ({region}) for ocr_text_present after clamping for image size {img_width}x{img_height}.")
                            actual_result = False
                        else:
                            # The OCRHandler's extract_text expects a PIL image of the region
                            # However, recognize_text_in_region expects the full screenshot and coordinates
                            # Let's assume extract_text is the one to use if we already have a region from condition
                            # No, looking at ocr_handler.py, recognize_text_in_region is more suitable
                            # as it handles the cropping internally.
                            
                            recognized_text = self.ocr_handler.recognize_text_in_region(
                                screenshot_pil, 
                                region_coords=(x1, y1, x2, y2), 
                                languages=languages
                            )
                            
                            if self.verbose:
                                logger.debug(f"OCR found '{recognized_text}' in region {region} for condition text '{text_to_find}'")

                            if case_sensitive:
                                actual_result = text_to_find in recognized_text
                            else:
                                actual_result = text_to_find.lower() in recognized_text.lower()
                
                except Exception as e:
                    if self.verbose:
                        logger.error(f"OCR text present check error: {str(e)}")
                    actual_result = False
        else:
            # Unknown condition type
            actual_result = False

        return not actual_result if should_negate else actual_result
    
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