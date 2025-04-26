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
