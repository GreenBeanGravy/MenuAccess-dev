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
        self.verbose = False
        self._sample_positions = {}  # Cache for sampling positions
        
        # Initialize ORB feature detector for image matching
        self.orb = cv2.ORB_create(nfeatures=1000)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    
    def set_verbose(self, verbose):
        """Enable or disable verbose logging mode"""
        self.verbose = verbose
    
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
        expected_color: list, 
        tolerance: int
    ) -> bool:
        """
        Check if a pixel at coordinates (x, y) has a specific color.
        
        Args:
            screenshot: Screenshot as numpy array
            x: X coordinate
            y: Y coordinate
            expected_color: RGB color to check [R, G, B]
            tolerance: Color difference tolerance
            
        Returns:
            bool: True if pixel color matches, False otherwise
        """
        try:
            # Make sure coordinates are within bounds
            height, width = screenshot.shape[:2]
            if x < 0 or x >= width or y < 0 or y >= height:
                if self.verbose:
                    print(f"Pixel at ({x},{y}) is out of bounds for image of size {width}x{height}")
                return False
            
            # Get the pixel color
            if hasattr(screenshot, 'getpixel'):  # PIL Image
                pixel_color = screenshot.getpixel((x, y))
            else:  # NumPy array
                pixel_color = screenshot[y, x]
                # Convert from BGR to RGB if needed (OpenCV format)
                if len(pixel_color) == 3:  # Only if we have a 3-channel color
                    pixel_color = pixel_color[::-1]  # BGR to RGB

            # Convert to uint8 arrays for OpenCV
            pixel_rgb_cv = np.array([[pixel_color]], dtype=np.uint8)
            expected_rgb_cv = np.array([[expected_color]], dtype=np.uint8)
            
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
            
            if self.verbose:
                print(f"Pixel at ({x},{y}): found {pixel_color}, expected {expected_color}, diff={weighted_diff:.1f}, tolerance={tolerance}")
            
            return weighted_diff <= tolerance
        except Exception as e:
            if self.verbose:
                print(f"Error checking pixel color: {str(e)}")
            return False
            
    def _check_pixel_region_color(
        self, 
        screenshot: np.ndarray, 
        x1: int, 
        y1: int, 
        x2: int, 
        y2: int, 
        expected_color: list, 
        tolerance: int,
        threshold: float
    ) -> bool:
        """
        Check if a region of pixels has a specific color.
        
        Args:
            screenshot: Screenshot as numpy array
            x1, y1: Top-left coordinates
            x2, y2: Bottom-right coordinates
            expected_color: RGB color to check [R, G, B]
            tolerance: Color difference tolerance
            threshold: Percentage of pixels that must match
            
        Returns:
            bool: True if enough pixels match the color, False otherwise
        """
        try:
            # Calculate region dimensions
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
                    if hasattr(screenshot, 'getpixel'):  # PIL Image
                        pixel_color = screenshot.getpixel((px, py))
                    else:  # NumPy array
                        pixel_color = screenshot[py, px]
                        # Convert from BGR to RGB if needed (OpenCV format)
                        if len(pixel_color) == 3:  # Only if we have a 3-channel color
                            pixel_color = pixel_color[::-1]  # BGR to RGB
                    
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
                except Exception as e:
                    # Skip any errors (e.g., out of bounds)
                    if self.verbose:
                        print(f"Error checking pixel at ({px},{py}): {str(e)}")
                
            # Calculate match percentage
            match_percentage = matches / len(sample_points)
            result = match_percentage >= threshold
            
            if self.verbose:
                print(f"Region ({x1},{y1}) to ({x2},{y2}): match={match_percentage:.2f}, threshold={threshold}")
            
            return result
                
        except Exception as e:
            if self.verbose:
                print(f"Region color check error: {str(e)}")
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
            
            # Extract the region from the screenshot to check
            if hasattr(screenshot, 'crop'):  # PIL Image
                region = screenshot.crop((x1, y1, x2, y2))
                region_cv = np.array(region)
            else:  # NumPy array
                region = screenshot[y1:y2, x1:x2]
                region_cv = region

            # Convert PIL images to OpenCV format (numpy arrays)
            template_cv = np.array(template_pil)
            
            # Convert to grayscale for feature detection
            if len(template_cv.shape) > 2:  # If it has 3 channels (RGB)
                template_gray = cv2.cvtColor(template_cv, cv2.COLOR_RGB2GRAY)
            else:
                template_gray = template_cv
                
            if len(region_cv.shape) > 2:  # If it has 3 channels (RGB)
                region_gray = cv2.cvtColor(region_cv, cv2.COLOR_RGB2GRAY)
            else:
                region_gray = region_cv
            
            # Resize template to match region if sizes don't match
            if template_gray.shape != region_gray.shape:
                template_gray = cv2.resize(template_gray, (region_gray.shape[1], region_gray.shape[0]))
            
            # Detect ORB features and compute descriptors
            kp1, des1 = self.orb.detectAndCompute(template_gray, None)
            kp2, des2 = self.orb.detectAndCompute(region_gray, None)
            
            # If no features found, try structural similarity as fallback
            if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
                # Use structural similarity index as fallback
                ssim_score = cv2.matchTemplate(
                    template_gray, region_gray, cv2.TM_CCOEFF_NORMED)[0, 0]
                
                if self.verbose:
                    print(f"Using template matching fallback: score={ssim_score:.3f}, threshold={confidence:.3f}")
                
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
                print(f"Image match score: {similarity_score:.3f}, confidence threshold: {confidence:.3f}")
            
            # Compare with the confidence threshold
            return similarity_score >= confidence
            
        except Exception as e:
            if self.verbose:
                print(f"Image match error: {str(e)}")
            return False