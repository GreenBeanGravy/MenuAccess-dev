"""
Menu condition checking functionality
"""

import numpy as np

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
            pixel_color = pixel_color[::-1]
            
            # Calculate color difference
            diff = np.sqrt(np.sum((np.array(pixel_color) - np.array(color)) ** 2))
            
            return diff <= tolerance
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
            
            # Calculate color differences for each pixel
            color_diffs = np.sqrt(np.sum((region_rgb - np.array(color)) ** 2, axis=2))
            
            # Count matching pixels
            matching_pixels = np.count_nonzero(color_diffs <= tolerance)
            total_pixels = (x2 - x1) * (y2 - y1)
            
            # Check if enough pixels match
            return matching_pixels / total_pixels >= threshold
        except Exception as e:
            print(f"Error checking pixel region color: {str(e)}")
            return False