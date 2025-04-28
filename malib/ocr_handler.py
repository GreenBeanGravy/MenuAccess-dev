"""
OCR text recognition handler for the MenuAccess application
"""

import logging
import numpy as np
import time
import threading
import sys
import queue

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
        self.init_complete = threading.Event()
        self.init_error = None
        
        # OCR cache to avoid repeated recognition of the same region
        self.ocr_cache = {}
        self.cache_lock = threading.Lock()  # Thread safety for cache access
        self.ocr_cache_ttl = 0.05  # OCR cache valid for 0.05 seconds
        
        # Limit for how many cache entries to keep to prevent memory leaks
        self.max_cache_entries = 1000
        
        # Thread pool for OCR operations (to limit concurrent OCR operations)
        self.ocr_queue = queue.Queue()
        self.max_ocr_threads = 2
        self.ocr_threads = []
    
    def initialize_reader(self):
        """
        Initialize the OCR reader if not already initialized
        """
        # Avoid redundant initialization if already done
        if self.init_complete.is_set():
            return True
            
        # Thread-safe initialization
        with self.reader_lock:
            # Double-check after lock acquisition
            if self.init_complete.is_set():
                return True
            
            try:
                import easyocr
                logger.info(f"Initializing EasyOCR reader with languages: {self.languages}")
                self.reader = easyocr.Reader(self.languages)
                logger.info("OCR reader initialized")
                self.init_complete.set()
                return True
            except Exception as e:
                logger.error(f"Failed to import or initialize EasyOCR: {e}")
                logger.error("OCR functionality will not be available")
                self.init_error = str(e)
                self.init_complete.set()  # Mark as complete even though it failed
                return False
    
    def wait_for_initialization(self, timeout=None):
        """
        Wait for OCR initialization to complete
        
        Args:
            timeout: Maximum time to wait (in seconds). None for infinite wait.
            
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        if self.init_complete.wait(timeout):
            return self.init_error is None
        return False
    
    def _clean_cache(self):
        """Clean old cache entries to prevent memory leaks"""
        if len(self.ocr_cache) <= self.max_cache_entries:
            return
            
        current_time = time.time()
        
        with self.cache_lock:
            # First, remove expired entries
            expired_keys = [
                key for key, value in self.ocr_cache.items() 
                if current_time - value['time'] > self.ocr_cache_ttl
            ]
            
            for key in expired_keys:
                del self.ocr_cache[key]
            
            # If still too many entries, remove oldest entries
            if len(self.ocr_cache) > self.max_cache_entries:
                # Sort by timestamp
                sorted_entries = sorted(
                    self.ocr_cache.items(),
                    key=lambda x: x[1]['time']
                )
                
                # Keep only the newest max_cache_entries
                keys_to_remove = [entry[0] for entry in sorted_entries[:-self.max_cache_entries]]
                
                for key in keys_to_remove:
                    del self.ocr_cache[key]
    
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
        # Ensure initialization is complete
        if not self.init_complete.is_set():
            if not self.wait_for_initialization(timeout=2.0):
                logger.warning("OCR extract_text called but initialization is incomplete")
                return ""
                
        # If initialization failed, return empty string
        if self.init_error is not None:
            return ""
                
        try:
            # If reader initialization failed or is not available yet, return empty string
            if self.reader is None:
                return ""
                
            # Create a cache key from the region or image hash
            if region:
                cache_key = (*region,)
            else:
                # Use a hash of the image data for a full-image cache key
                cache_key = ('full_image', hash(image.tobytes()) if hasattr(image, 'tobytes') else id(image))
            
            # Check cache first (thread-safe)
            current_time = time.time()
            with self.cache_lock:
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
            try:
                result = self.reader.readtext(img_np)
            except Exception as e:
                logger.error(f"EasyOCR error: {e}")
                return ""
            
            # Extract all detected text and join
            if result:
                # EasyOCR returns a list of [bbox, text, confidence]
                # Join all detected text pieces and convert to lowercase
                ocr_text = ' '.join([entry[1].lower() for entry in result])
            else:
                ocr_text = ""
            
            # Cache the result (thread-safe)
            with self.cache_lock:
                self.ocr_cache[cache_key] = {
                    'text': ocr_text,
                    'time': current_time
                }
                
                # Clean cache periodically to prevent memory leaks
                self._clean_cache()
            
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
        with self.cache_lock:
            self.ocr_cache = {}
    
    def shutdown(self):
        """Shutdown the OCR handler and free resources"""
        # Clear cache
        self.clear_cache()
        
        # Clear reader reference to help with GC
        with self.reader_lock:
            self.reader = None