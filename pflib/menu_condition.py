"""
Menu condition checking functionality
"""

import numpy as np
import cv2  # OpenCV for HSV conversion

class MenuCondition:
    """Class for defining and checking menu detection conditions"""
    
    def __init__(self):
        """Initialize the condition checker"""
        pass
    
    def check_condition(self, condition: dict, screenshot: np.ndarray) -> bool:
        """
        Check a single condition.
        
        Args:
            condition: Condition dictionary with type and parameters
            screenshot: Screenshot as numpy array
            
        Returns:
            bool: True if condition is met, False otherwise
        """
        condition_type = condition.get("type", "")
        
        if condition_type == "pixel_color":
            return self._check_pixel_color(
                screenshot,
                condition.get("x", 0),
                condition.get("y", 0),
                condition.get("color", [0, 0, 0]),
                condition.get("tolerance", 0)
            )
            
        elif condition_type == "pixel_region_color":
            return self._check_pixel_region_color(
                screenshot,
                condition.get("x1", 0),
                condition.get("y1", 0),
                condition.get("x2", 0),
                condition.get("y2", 0),
                condition.get("color", [0, 0, 0]),
                condition.get("tolerance", 0),
                condition.get("threshold", 0.5)
            )
            
        return False
    
    def check_menu_conditions(self, menu_conditions: list, screenshot: np.ndarray) -> bool:
        """
        Check if a menu is currently active based on its conditions.
        
        Args:
            menu_conditions: List of condition dictionaries
            screenshot: Screenshot as numpy array
            
        Returns:
            bool: True if all conditions are met, False otherwise
        """
        # If menu has no conditions, it's not active
        if not menu_conditions:
            return False
            
        # Check each condition - all must be met for the menu to be active
        for condition in menu_conditions:
            if not self.check_condition(condition, screenshot):
                return False
                
        return True
    
    def _check_pixel_color(
        self, 
        screenshot: np.ndarray, 
        x: int, 
        y: int, 
        color: list, 
        tolerance: int
    ) -> bool:
        """
        Check if a pixel at coordinates (x, y) has a specific color.
        
        Args:
            screenshot: Screenshot as numpy array
            x: X coordinate
            y: Y coordinate
            color: RGB color to check [R, G, B]
            tolerance: Color difference tolerance
            
        Returns:
            bool: True if pixel color matches, False otherwise
        """
        try:
            # Get the pixel color (BGR format)
            pixel_color = screenshot[y, x]
            
            # Convert to RGB for comparison (screenshot is BGR)
            pixel_rgb = pixel_color[::-1]
            
            # Convert both colors to HSV for more perceptually relevant comparison
            # First, convert to the format OpenCV expects (0-255 uint8)
            pixel_rgb_cv = np.array([[pixel_rgb]], dtype=np.uint8)
            expected_rgb_cv = np.array([[color]], dtype=np.uint8)
            
            # Convert RGB to HSV
            pixel_hsv = cv2.cvtColor(pixel_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
            expected_hsv = cv2.cvtColor(expected_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
            
            # Hue is circular, so we need special handling
            h1, s1, v1 = pixel_hsv.astype(float)
            h2, s2, v2 = expected_hsv.astype(float)
            
            # Handle hue wrapping (0 and 180 are adjacent in HSV)
            h_diff = min(abs(h1 - h2), 180.0 - abs(h1 - h2))
            
            # Weight hue more than saturation and value for better color detection
            # regardless of lighting changes
            weighted_diff = (h_diff * 2.0) + (abs(s1 - s2) / 2.0) + (abs(v1 - v2) / 4.0)
            
            return weighted_diff <= tolerance
        except Exception as e:
            print(f"Error checking pixel color: {str(e)}")
            return False
            
    def _check_pixel_region_color(
        self, 
        screenshot: np.ndarray, 
        x1: int, 
        y1: int, 
        x2: int, 
        y2: int, 
        color: list, 
        tolerance: int,
        threshold: float
    ) -> bool:
        """
        Check if a region of pixels has a specific color.
        
        Args:
            screenshot: Screenshot as numpy array
            x1, y1: Top-left coordinates
            x2, y2: Bottom-right coordinates
            color: RGB color to check [R, G, B]
            tolerance: Color difference tolerance
            threshold: Percentage of pixels that must match
            
        Returns:
            bool: True if enough pixels match the color, False otherwise
        """
        try:
            # Extract region
            region = screenshot[y1:y2, x1:x2]
            
            # Convert BGR to RGB
            region_rgb = region[:, :, ::-1]
            
            # Convert region to HSV for better color comparison
            region_hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
            
            # Convert expected color to HSV
            expected_rgb_cv = np.array([[color]], dtype=np.uint8)
            expected_hsv = cv2.cvtColor(expected_rgb_cv, cv2.COLOR_RGB2HSV)[0][0]
            
            # Extract HSV channels and convert to float to avoid overflow
            h = region_hsv[:,:,0].astype(float)
            s = region_hsv[:,:,1].astype(float)
            v = region_hsv[:,:,2].astype(float)
            h_expected = float(expected_hsv[0])
            s_expected = float(expected_hsv[1])
            v_expected = float(expected_hsv[2])
            
            # Calculate hue difference (consider circular nature of hue)
            h_diff = np.minimum(np.abs(h - h_expected), 180.0 - np.abs(h - h_expected))
            
            # Calculate saturation and value differences
            s_diff = np.abs(s - s_expected)
            v_diff = np.abs(v - v_expected)
            
            # Weight hue more than saturation and value
            weighted_diffs = (h_diff * 2.0) + (s_diff / 2.0) + (v_diff / 4.0)
            
            # Count matching pixels
            matching_pixels = np.count_nonzero(weighted_diffs <= tolerance)
            total_pixels = (x2 - x1) * (y2 - y1)
            
            # Check if enough pixels match
            return matching_pixels / total_pixels >= threshold
        except Exception as e:
            print(f"Error checking pixel region color: {str(e)}")
            return False