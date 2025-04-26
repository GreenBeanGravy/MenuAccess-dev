"""
OCR text recognition handler for the MenuAccess application
"""

import logging
import numpy as np
import time
import threading

logger = logging.getLogger("AccessibleMenuNav")

class OCRHandler:
    """Handles OCR text recognition with caching and thread safety"""
    
    def __init__(self, languages=None):
        """
        Initialize the OCR handler
        
        Args:
            languages: List of language codes to recognize (default: ['en'])
        """
        # Default to English if no languages specified
        self.languages = languages or ['en']
        
        # Lazy-loaded OCR reader to improve startup time
        self.reader = None
        self.reader_lock = threading.Lock()  # Thread safety for initialization
        
        # OCR cache to avoid repeated recognition of the same region
        self.ocr_cache = {}
        self.ocr_cache_ttl = 5.0  # OCR cache valid for 5 seconds
    
    def initialize_reader(self):
        """
        Initialize the OCR reader if not already initialized
        """
        # Avoid redundant initialization checks
        if self.reader is not None:
            return
            
        # Thread-safe initialization
        with self.reader_lock:
            # Double-check after lock acquisition
            if self.reader is not None:
                return
            
            try:
                import easyocr
                logger.info(f"Initializing EasyOCR reader with languages: {self.languages}")
                self.reader = easyocr.Reader(self.languages)
                logger.info("OCR reader initialized")
            except ImportError as e:
                logger.error(f"Failed to import EasyOCR: {e}")
                logger.error("OCR functionality will not be available")
    
    def extract_text(self, image, region=None):
        """
        Extract text from an image or region within an image
        
        Args:
            image: PIL Image or numpy array containing the screenshot
            region: Optional tuple (x1, y1, x2, y2) defining the region to extract from
                    If None, the entire image is processed
        
        Returns:
            str: Extracted text, or empty string if no text found
        """
        try:
            # Initialize reader if needed
            if self.reader is None:
                self.initialize_reader()
                
            # If reader initialization failed or is not available yet, return empty string
            if self.reader is None:
                return ""
                
            # Create a cache key from the region or image hash
            if region:
                cache_key = (*region,)
            else:
                # Use a hash of the image data for a full-image cache key
                cache_key = ('full_image', hash(image.tobytes()) if hasattr(image, 'tobytes') else id(image))
            
            # Check cache first
            current_time = time.time()
            if cache_key in self.ocr_cache and current_time - self.ocr_cache[cache_key]['time'] < self.ocr_cache_ttl:
                logger.debug(f"Using cached OCR result for region {cache_key}")
                return self.ocr_cache[cache_key]['text']
                
            # Process region if specified
            if region:
                x1, y1, x2, y2 = region
                if hasattr(image, 'crop'):  # PIL Image
                    cropped = image.crop((x1, y1, x2, y2))
                    img_np = np.array(cropped)
                else:  # Numpy array
                    img_np = image[y1:y2, x1:x2]
            else:
                # Use full image
                if hasattr(image, 'crop'):  # PIL Image
                    img_np = np.array(image)
                else:  # Numpy array
                    img_np = image
            
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
            
            if region:
                logger.debug(f"OCR result for region {region}: '{ocr_text}'")
            else:
                logger.debug(f"OCR result for full image: '{ocr_text}'")
                
            return ocr_text
            
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return ""
    
    def clear_cache(self):
        """Clear the OCR cache"""
        self.ocr_cache = {}
