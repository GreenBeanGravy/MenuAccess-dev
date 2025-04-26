"""
Utilities for the MenuAccess application
"""

import logging
import threading

# Windows constants for mouse_event
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

def setup_logging(debug=False):
    """
    Set up logging configuration for the application
    
    Args:
        debug: Whether to enable debug mode (file logging)
        
    Returns:
        logging.Logger: Configured logger
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("AccessibleMenuNav")
    
    # Set up file-based logging if debug mode is enabled
    if debug:
        log_file = "ma_debug.log"
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        print(f"Debug logging enabled. Log file: {log_file}")
    
    return logger
