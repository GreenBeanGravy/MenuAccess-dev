"""
Menu condition checking functionality
"""

import numpy as np
import cv2  # OpenCV for HSV conversion
import base64
import io
from PIL import Image

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
            
        elif condition_type == "pixel_region_image":
            return self._check_pixel_region_image(
                screenshot,
                condition.get("x1", 0),
                condition.get("y1", 0),
                condition.get("x2", 0),
                condition.get("y2", 0),
                condition.get("image_data", None),
                condition.get("confidence", 0.8)
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
    
    def _check_pixel_region_image(
        self,
        screenshot: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        image_data: str,
        confidence: float
    ) -> bool:
        """
        Check if a region matches a previously captured image.
        
        Args:
            screenshot: Screenshot as numpy array
            x1, y1: Top-left coordinates of the region to check
            x2, y2: Bottom-right coordinates of the region to check
            image_data: Base64 encoded image data
            confidence: Confidence threshold (0.0 to 1.0)
            
        Returns:
            bool: True if the image matches with the specified confidence
        """
        try:
            if not image_data:
                return False
            
            # Decode the base64 image data
            image_bytes = base64.b64decode(image_data)
            
            # Create a PIL Image from the decoded data
            template_pil = Image.open(io.BytesIO(image_bytes))
            
            # Convert PIL Image to numpy array
            template = np.array(template_pil)
            
            # Convert RGB to BGR (OpenCV format)
            if template.shape[2] == 3:  # If it has 3 channels (RGB)
                template = template[:, :, ::-1]
            
            # Extract the region from the screenshot to check
            region = screenshot[y1:y2, x1:x2]
            
            # Make sure template and region have the same size
            if template.shape[:2] != region.shape[:2]:
                # Resize template to match region
                template = cv2.resize(template, (region.shape[1], region.shape[0]))
            
            # Convert both to grayscale for template matching
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            region_gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            
            # Template matching 
            # Using simple sum of squared differences (TM_SQDIFF_NORMED)
            # Lower values mean better match
            match_result = cv2.matchTemplate(region_gray, template_gray, cv2.TM_SQDIFF_NORMED)[0, 0]
            
            # Convert to a similarity score (0-1 where 1 is perfect match)
            # TM_SQDIFF_NORMED returns 0 for perfect match, 1 for complete mismatch
            # So we need to invert the scale to get our confidence
            similarity = 1.0 - match_result
            
            # Using a secondary metric based on histogram comparison for color information
            # This helps avoid false positives from grayscale matching alone
            
            # Compare histograms in HSV space for better color matching
            region_hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
            template_hsv = cv2.cvtColor(template, cv2.COLOR_BGR2HSV)
            
            # Compare histograms (using correlation method)
            h_bins = 50
            s_bins = 50
            hist_size = [h_bins, s_bins]
            # hue varies from 0 to 180, saturation from 0 to 255
            h_ranges = [0, 180]
            s_ranges = [0, 256]
            ranges = h_ranges + s_ranges
            channels = [0, 1]  # Use hue and saturation channels
            
            region_hist = cv2.calcHist([region_hsv], channels, None, hist_size, ranges)
            template_hist = cv2.calcHist([template_hsv], channels, None, hist_size, ranges)
            
            # Normalize histograms
            cv2.normalize(region_hist, region_hist, 0, 1, cv2.NORM_MINMAX)
            cv2.normalize(template_hist, template_hist, 0, 1, cv2.NORM_MINMAX)
            
            # Compare histograms using correlation method
            # Returns value between 0 (no correlation) and 1 (perfect match)
            hist_match = cv2.compareHist(region_hist, template_hist, cv2.HISTCMP_CORREL)
            
            # Combine both metrics with weights 
            # Template matching is more important but color should match too
            combined_score = (similarity * 0.7) + (hist_match * 0.3)
            
            print(f"Image match score: {combined_score:.3f}, confidence threshold: {confidence:.3f}")
            
            # Check if combined score exceeds confidence threshold
            return combined_score >= confidence
            
        except Exception as e:
            print(f"Error checking pixel region image: {str(e)}")
            return False