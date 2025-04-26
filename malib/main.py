"""
Main entry point for the MenuAccess application
"""

import sys
import argparse
import logging

from malib.utils import setup_logging
from malib.navigator import AccessibleMenuNavigator

def main():
    """Main function with optimized startup and debug mode"""
    parser = argparse.ArgumentParser(description="High-Performance Accessible Menu Navigation")
    parser.add_argument("profile", nargs="?", default="fortnite.json", help="Path to menu profile JSON file")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode (logs to file)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--languages", type=str, default="en", help="OCR languages, comma-separated (e.g., 'en,fr,es')")
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging(args.debug)
    
    # Parse OCR languages
    ocr_languages = [lang.strip() for lang in args.languages.split(',')]
    
    # Create the navigator
    navigator = AccessibleMenuNavigator()
    
    # Set verbose and debug modes
    navigator.set_verbose(args.verbose)
    navigator.set_debug(args.debug)
    
    try:
        # Start the navigator with the specified profile and languages
        navigator.start(args.profile, ocr_languages)
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\nKeyboard interrupt received. Exiting...")
        
        # Set stop flag for any running threads
        if hasattr(navigator, 'stop_requested'):
            navigator.stop_requested.set()
            
        # Exit cleanly
        sys.exit(0)

if __name__ == "__main__":
    main()
