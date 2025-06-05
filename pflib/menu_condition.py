"""
Menu condition checking functionality
"""

import numpy as np
import cv2  # OpenCV for HSV conversion
import base64
import io
import re # For ocr_text_match regex
from PIL import Image

# Import the unified screen capture from main app
from malib.screen_capture import ScreenCapture

# This class is for the editor's "Test Menu" feature.
# It should mirror malib.condition_checker.MenuConditionChecker as much as possible.
# For OCR, it will need its own OCR handler instance if testing OCR conditions.

class MenuCondition:
    """Class for defining and checking menu detection conditions"""
    
    def __init__(self, ocr_handler=None): # Added ocr_handler
        """Initialize the condition checker"""
        self.verbose = False
        self._sample_positions = {}  # Cache for sampling positions
        
        # Initialize ORB feature detector for image matching
        self.orb = cv2.ORB_create(nfeatures=1000)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.ocr_handler = ocr_handler
        
        # Use unified screen capture
        self.screen_capture = ScreenCapture()
    
    def set_verbose(self, verbose):
        """Enable or disable verbose logging mode"""
        self.verbose = verbose
    
    def check_condition(self, condition: dict, screenshot_pil: Image.Image) -> bool: # Changed to screenshot_pil
        """
        Check a single condition.
        
        Args:
            condition: Condition dictionary with type and parameters
            screenshot_pil: Screenshot as PIL Image
            
        Returns:
            bool: True if condition is met, False otherwise
        """
        condition_type = condition.get("type", "")
        negate = condition.get("negate", False)
        result = False # Default to false

        if condition_type == "pixel_color":
            result = self._check_pixel_color(
                screenshot_pil, # Pass PIL image
                condition.get("x", 0),
                condition.get("y", 0),
                condition.get("color", [0, 0, 0]),
                condition.get("tolerance", 0)
            )
            
        elif condition_type == "pixel_region_color":
            result = self._check_pixel_region_color(
                screenshot_pil, # Pass PIL image
                condition.get("x1", 0),
                condition.get("y1", 0),
                condition.get("x2", 0),
                condition.get("y2", 0),
                condition.get("color", [0, 0, 0]),
                condition.get("tolerance", 0),
                condition.get("threshold", 0.5)
            )
            
        elif condition_type == "pixel_region_image":
            result = self._check_pixel_region_image(
                screenshot_pil, # Pass PIL image
                condition.get("x1", 0),
                condition.get("y1", 0),
                condition.get("x2", 0),
                condition.get("y2", 0),
                condition.get("image_data", None),
                condition.get("confidence", 0.8)
            )
        
        elif condition_type == "or":
            sub_conditions = condition.get("conditions", [])
            if len(sub_conditions) != 2:
                if self.verbose:
                    print(f"OR condition expects 2 sub-conditions, found {len(sub_conditions)}")
                result = False
            else:
                # Recursively call check_condition for sub-conditions
                res1 = self.check_condition(sub_conditions[0], screenshot_pil)
                res2 = self.check_condition(sub_conditions[1], screenshot_pil)
                result = res1 or res2
        
        elif condition_type == "ocr_text_match":
            if not self.ocr_handler:
                if self.verbose:
                    print("OCR handler not available for ocr_text_match condition in editor test.")
                result = False # Or raise an error, or return a specific status
            else:
                try:
                    x1 = condition.get("x1", 0)
                    y1 = condition.get("y1", 0)
                    x2 = condition.get("x2", 0)
                    y2 = condition.get("y2", 0)
                    expected_text = condition.get("expected_text", "")
                    match_mode = condition.get("match_mode", "contains")
                    case_sensitive = condition.get("case_sensitive", False)

                    width, height = screenshot_pil.size
                    if x1 < 0 or x2 > width or y1 < 0 or y2 > height or x1 >= x2 or y1 >= y2:
                        if self.verbose:
                            print(f"OCR Region ({x1},{y1}) to ({x2},{y2}) invalid for image of size {width}x{height}")
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
                                    print(f"Regex error in ocr_text_match (editor test): {re_err}")
                                result = False
                        else: # Default to contains
                            result = expected_text_cmp in extracted_text
                        
                        if self.verbose:
                            print(f"OCR Text Match (editor test): Region=({x1},{y1},{x2},{y2}), Expected='{expected_text}', Extracted='{extracted_text}', Result={result}")
                except Exception as e:
                    if self.verbose:
                        print(f"OCR text match error (editor test): {str(e)}")
                    result = False
        else:
            if self.verbose:
                print(f"Unknown condition type in editor test: {condition_type}")
            result = False
            
        return not result if negate else result
    
    def check_menu_conditions(self, menu_conditions: list, screenshot_pil: Image.Image) -> bool: # Changed to screenshot_pil
        """
        Check if a menu is currently active based on its conditions.
        
        Args:
            menu_conditions: List of condition dictionaries
            screenshot_pil: Screenshot as PIL Image
            
        Returns:
            bool: True if all conditions are met, False otherwise
        """
        # If menu has no conditions, it's not active
        if not menu_conditions:
            return False
            
        # Check each condition - all must be met for the menu to be active
        for condition in menu_conditions:
            if not self.check_condition(condition, screenshot_pil):
                return False
                
        return True
    
    def take_screenshot(self):
        """Take a screenshot using unified screen capture"""
        return self.screen_capture.capture()
    
    def _check_pixel_color(
        self, 
        screenshot_pil: Image.Image, # Changed to screenshot_pil
        x: int, 
        y: int, 
        expected_color: list, 
        tolerance: int
    ) -> bool:
        """
        Check if a pixel at coordinates (x, y) has a specific color.
        
        Args:
            screenshot_pil: Screenshot as PIL Image
            x: X coordinate
            y: Y coordinate
            expected_color: RGB color to check [R, G, B]
            tolerance: Color difference tolerance
            
        Returns:
            bool: True if pixel color matches, False otherwise
        """
        try:
            # Make sure coordinates are within bounds
            width, height = screenshot_pil.size
            if x < 0 or x >= width or y < 0 or y >= height:
                if self.verbose:
                    print(f"Pixel at ({x},{y}) is out of bounds for image of size {width}x{height}")
                return False
            
            # Get the pixel color
            pixel_color = screenshot_pil.getpixel((x, y))
            if len(pixel_color) > 3: # Handle RGBA
                pixel_color = pixel_color[:3]


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
        screenshot_pil: Image.Image, # Changed to screenshot_pil
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
            screenshot_pil: Screenshot as PIL Image
            x1, y1: Top-left coordinates
            x2, y2: Bottom-right coordinates
            expected_color: RGB color to check [R, G, B]
            tolerance: Color difference tolerance
            threshold: Percentage of pixels that must match
            
        Returns:
            bool: True if enough pixels match the color, False otherwise
        """
        try:
            # Ensure coordinates are valid
            width, height = screenshot_pil.size
            if x1 < 0 or x2 > width or y1 < 0 or y2 > height or x1 >= x2 or y1 >= y2:
                if self.verbose:
                    print(f"Region ({x1},{y1}) to ({x2},{y2}) invalid for image of size {width}x{height}")
                return False

            region_pil = screenshot_pil.crop((x1, y1, x2, y2))
            region_array = np.array(region_pil)

            # Calculate region dimensions
            region_width = x2 - x1
            region_height = y2 - y1
            region_size = region_width * region_height
            
            # Get cached sampling positions or create new ones
            cache_key = (x1, y1, x2, y2) # Use original coords for cache key
            if cache_key in self._sample_positions:
                sample_points_relative = self._sample_positions[cache_key]
            else:
                # Adaptive sampling based on region size
                if region_size > 40000:  # Large region (200x200+)
                    sample_count = min(25, max(9, region_size // 4000))
                    grid_size = int(np.sqrt(sample_count))
                    x_step = region_width / grid_size
                    y_step = region_height / grid_size
                    sample_points_relative = [(int((i + 0.5) * x_step), int((j + 0.5) * y_step)) for i in range(grid_size) for j in range(grid_size)]
                elif region_size > 10000:  # Medium region
                    x_step = region_width / 3
                    y_step = region_height / 3
                    sample_points_relative = [(int((i + 0.5) * x_step), int((j + 0.5) * y_step)) for i in range(3) for j in range(3)]
                else:  # Small region
                    sample_points_relative = [
                        (0, 0), (region_width-1, 0),
                        (region_width//2, region_height//2),
                        (0, region_height-1), (region_width-1, region_height-1)
                    ]
                self._sample_positions[cache_key] = sample_points_relative
            
            # Calculate similarity for each sample point
            matches = 0
            if not sample_points_relative: return False # Avoid division by zero if no sample points

            for rel_px, rel_py in sample_points_relative:
                try:
                    # Ensure relative coordinates are within the cropped region_array bounds
                    if rel_px >= region_array.shape[1] or rel_py >= region_array.shape[0]:
                        if self.verbose: print(f"Sample point ({rel_px},{rel_py}) out of bounds for cropped region.")
                        continue

                    pixel_color = region_array[rel_py, rel_px]
                    if len(pixel_color) > 3: pixel_color = pixel_color[:3] # Handle RGBA
                    
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
                except Exception as e:
                    if self.verbose:
                        print(f"Error checking pixel at relative ({rel_px},{rel_py}): {str(e)}")
                
            # Calculate match percentage
            match_percentage = matches / len(sample_points_relative)
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
        screenshot_pil: Image.Image, # Changed to screenshot_pil
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
            screenshot_pil: Screenshot as PIL Image
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

            # Ensure coordinates are valid
            width, height = screenshot_pil.size
            if x1 < 0 or x2 > width or y1 < 0 or y2 > height or x1 >= x2 or y1 >= y2:
                if self.verbose:
                    print(f"Region ({x1},{y1}) to ({x2},{y2}) invalid for image of size {width}x{height}")
                return False
            
            # Decode the base64 image data
            image_bytes = base64.b64decode(image_data)
            
            # Create a PIL Image from the decoded data
            template_pil = Image.open(io.BytesIO(image_bytes))
            
            # Extract the region from the screenshot to check
            region_pil = screenshot_pil.crop((x1, y1, x2, y2))
            region_cv = np.array(region_pil) # Convert to OpenCV BGR by default from PIL RGB

            # Convert PIL images to OpenCV format (numpy arrays)
            template_cv = np.array(template_pil) # Also BGR if from PIL RGB
            
            # Convert to grayscale for feature detection
            if len(template_cv.shape) > 2 and template_cv.shape[2] == 3:
                template_gray = cv2.cvtColor(template_cv, cv2.COLOR_RGB2GRAY)
            elif len(template_cv.shape) > 2 and template_cv.shape[2] == 4: # RGBA
                template_gray = cv2.cvtColor(template_cv, cv2.COLOR_RGBA2GRAY)
            else: # Already grayscale
                template_gray = template_cv
                
            if len(region_cv.shape) > 2 and region_cv.shape[2] == 3:
                region_gray = cv2.cvtColor(region_cv, cv2.COLOR_RGB2GRAY)
            elif len(region_cv.shape) > 2 and region_cv.shape[2] == 4: # RGBA
                region_gray = cv2.cvtColor(region_cv, cv2.COLOR_RGBA2GRAY)
            else: # Already grayscale
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
                # Ensure images are single channel for matchTemplate
                if len(template_gray.shape) > 2: template_gray = template_gray[:,:,0]
                if len(region_gray.shape) > 2: region_gray = region_gray[:,:,0]

                match_val = cv2.matchTemplate(
                    region_gray, template_gray, cv2.TM_CCOEFF_NORMED)[0, 0] # region_gray is template, template_gray is source
                
                if self.verbose:
                    print(f"Using template matching fallback: score={match_val:.3f}, threshold={confidence:.3f}")
                
                return match_val >= confidence
            
            # Match descriptors
            matches = self.matcher.match(des1, des2)
            
            # Sort matches by distance
            matches = sorted(matches, key=lambda x: x.distance)
            
            # Calculate match ratio (number of good matches / total matches)
            # For ORB, a common threshold for "good" matches is based on distance.
            # A simple ratio of good matches to keypoints in the template can be used.
            # Let's consider matches with distance < 50 as good (Hamming distance for ORB)
            good_matches = [m for m in matches if m.distance < 75] # Adjusted threshold
            
            # Compute similarity score based on number of good matches
            if len(kp1) == 0:  # Prevent division by zero
                similarity_score = 0.0
            else:
                similarity_score = len(good_matches) / float(len(kp1))
            
            if self.verbose:
                print(f"Image match score: {similarity_score:.3f}, confidence threshold: {confidence:.3f}, Good matches: {len(good_matches)}/{len(kp1)}")
            
            # Compare with the confidence threshold
            return similarity_score >= confidence
            
        except Exception as e:
            if self.verbose:
                print(f"Image match error: {str(e)}")
            return False
    
    def close(self):
        """Clean up resources"""
        if hasattr(self, 'screen_capture'):
            self.screen_capture.close()