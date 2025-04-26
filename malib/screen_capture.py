"""
Screen capture functionality for the MenuAccess application
"""

import logging
import threading
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
        
        logger.info(f"Using {self.capture_method} for screen capture")
    
    def capture(self, region=None):
        """
        Capture a screenshot
        
        Args:
            region: Optional region to capture (x, y, width, height) or None for full screen
            
        Returns:
            PIL.Image: Screenshot as PIL Image
        """
        if self.capture_method == "dxcam":
            return self._capture_dxcam(region)
        elif self.capture_method == "mss":
            return self._capture_mss(region)
        else:
            return self._capture_pyautogui(region)
    
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
                # Fallback to MSS in case of failure
                logger.warning("dxcam capture failed, falling back to MSS")
                return self._capture_mss(region)
            
            # Convert to PIL Image
            img = Image.fromarray(frame)
            return img
            
        except Exception as e:
            logger.error(f"dxcam error: {e}, falling back to MSS")
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
        if self.dxcam_instance:
            self.dxcam_instance.stop()
        
        # Close any MSS instances we've created
        if hasattr(self.thread_locals, 'mss_instance'):
            try:
                self.thread_locals.mss_instance.close()
            except:
                pass
