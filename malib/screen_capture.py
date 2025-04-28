"""
Screen capture functionality for the MenuAccess application
"""

import logging
import threading
import time
import numpy as np
import pyautogui
from PIL import Image

logger = logging.getLogger("AccessibleMenuNav")

# Try to import dxcam-cpp if available
try:
    import dxcam
    DXCAM_AVAILABLE = True
    logger.info("dxcam-cpp is available and will be used for screen capture")
except ImportError:
    DXCAM_AVAILABLE = False
    logger.info("dxcam-cpp not available, falling back to MSS for screen capture")

# Try to import mss for fallback
try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    logger.warning("MSS not available, falling back to pyautogui for screen capture")

class ScreenCapture:
    """Screen capture class that uses dxcam-cpp if available, or MSS as fallback"""
    
    def __init__(self):
        """Initialize the appropriate screen capture mechanism"""
        self.capture_method = "dxcam" if DXCAM_AVAILABLE else ("mss" if MSS_AVAILABLE else "pyautogui")
        self.dxcam_instance = None
        
        # Thread-local storage for MSS instances
        self.thread_locals = threading.local()
        
        # Cache the last screenshot to reduce capture frequency
        self.last_screenshot = None
        self.last_screenshot_time = 0
        self.screenshot_cache_ttl = 0.05  # 50ms TTL for screenshot cache
        self.screenshot_lock = threading.Lock()
        
        # Throttling for CPU usage control
        self.last_capture_time = 0
        self.min_capture_interval = 0.01  # Minimum 10ms between captures
        
        # Count failures to detect persistent issues
        self.dxcam_consecutive_failures = 0
        self.max_consecutive_failures = 3  # Switch methods after this many failures
        
        logger.info(f"Using {self.capture_method} for screen capture")
    
    def capture(self, region=None, force_new=False):
        """
        Capture a screenshot
        
        Args:
            region: Optional region to capture (x, y, width, height) or None for full screen
            force_new: Force a new capture even if cached screenshot is available
            
        Returns:
            PIL.Image: Screenshot as PIL Image
        """
        current_time = time.time()
        
        # Check if we need to throttle captures to reduce CPU usage
        if not force_new and current_time - self.last_capture_time < self.min_capture_interval:
            time.sleep(0.005)  # Short sleep to yield CPU
        
        # Use cached screenshot if available and recent enough
        with self.screenshot_lock:
            if not force_new and self.last_screenshot is not None and region is None:
                if current_time - self.last_screenshot_time < self.screenshot_cache_ttl:
                    return self.last_screenshot
        
        # Update capture timestamp
        self.last_capture_time = current_time
        
        # Capture based on selected method
        if self.capture_method == "dxcam":
            screenshot = self._capture_dxcam(region)
        elif self.capture_method == "mss":
            screenshot = self._capture_mss(region)
        else:
            screenshot = self._capture_pyautogui(region)
        
        # Cache the full screen capture for future use
        if region is None:
            with self.screenshot_lock:
                self.last_screenshot = screenshot
                self.last_screenshot_time = current_time
        
        return screenshot
    
    def _capture_dxcam(self, region=None):
        """Capture using dxcam-cpp"""
        try:
            # Initialize dxcam instance if not already done
            if self.dxcam_instance is None:
                self.dxcam_instance = dxcam.create()
            
            # Capture frame
            if region:
                # dxcam region format is (left, top, right, bottom)
                dxcam_region = (region[0], region[1], region[0] + region[2], region[1] + region[3])
                frame = self.dxcam_instance.grab(region=dxcam_region)
            else:
                frame = self.dxcam_instance.grab()
            
            if frame is None:
                # Count the failure
                self.dxcam_consecutive_failures += 1
                
                # If too many consecutive failures, fall back to MSS permanently
                if self.dxcam_consecutive_failures >= self.max_consecutive_failures:
                    logger.warning(f"DXCam failed {self.dxcam_consecutive_failures} times in a row, switching to MSS permanently")
                    self.capture_method = "mss" if MSS_AVAILABLE else "pyautogui"
                    
                    # Clean up dxcam resources
                    if self.dxcam_instance:
                        try:
                            self.dxcam_instance.stop()
                        except:
                            pass
                        self.dxcam_instance = None
                
                # Fallback to MSS for this capture
                return self._capture_mss(region)
            
            # Reset failure counter on success
            self.dxcam_consecutive_failures = 0
            
            # Convert to PIL Image
            img = Image.fromarray(frame)
            return img
            
        except Exception as e:
            logger.error(f"dxcam error: {e}, falling back to MSS")
            # Count the failure
            self.dxcam_consecutive_failures += 1
            
            # Switch methods if too many failures
            if self.dxcam_consecutive_failures >= self.max_consecutive_failures:
                logger.warning(f"DXCam failed {self.dxcam_consecutive_failures} times, switching to MSS permanently")
                self.capture_method = "mss" if MSS_AVAILABLE else "pyautogui"
                
                # Clean up dxcam resources
                if self.dxcam_instance:
                    try:
                        self.dxcam_instance.stop()
                    except:
                        pass
                    self.dxcam_instance = None
            
            return self._capture_mss(region)
    
    def _capture_mss(self, region=None):
        """Capture using MSS with thread-safe instance management"""
        if not MSS_AVAILABLE:
            return self._capture_pyautogui(region)
            
        try:
            # Each thread gets its own MSS instance
            if not hasattr(self.thread_locals, 'mss_instance'):
                # Create a new MSS instance for this thread
                self.thread_locals.mss_instance = mss.mss()
                thread_id = threading.get_ident()
                logger.debug(f"Created new MSS instance for thread {thread_id}")
            
            # Use the thread-local MSS instance
            sct = self.thread_locals.mss_instance
            
            if region:
                mss_region = {"left": region[0], "top": region[1], 
                            "width": region[2], "height": region[3]}
                screenshot = sct.grab(mss_region)
            else:
                screenshot = sct.grab(sct.monitors[0])
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)
            return img
            
        except Exception as e:
            logger.error(f"MSS error: {e}, falling back to pyautogui")
            return self._capture_pyautogui(region)
    
    def _capture_pyautogui(self, region=None):
        """Capture using pyautogui as last resort"""
        try:
            if region:
                screenshot = pyautogui.screenshot(region=(region[0], region[1], region[2], region[3]))
            else:
                screenshot = pyautogui.screenshot()
            return screenshot
        except Exception as e:
            logger.error(f"Failed to capture screenshot with pyautogui: {e}")
            # Create a small black image as a last resort
            return Image.new('RGB', (800, 600), (0, 0, 0))
    
    def close(self):
        """Clean up resources"""
        # Clear cached screenshot
        with self.screenshot_lock:
            self.last_screenshot = None
        
        # Close dxcam instance
        if self.dxcam_instance:
            try:
                self.dxcam_instance.stop()
            except:
                pass
            self.dxcam_instance = None
        
        # Close any MSS instances we've created
        if hasattr(self.thread_locals, 'mss_instance'):
            try:
                self.thread_locals.mss_instance.close()
            except:
                pass