"""
Main entry point for the MenuAccess application
"""

import sys
import os
import argparse
import logging
import time

from malib.utils import setup_logging
from malib.navigator import AccessibleMenuNavigator

def main():
    """Main function with optimized startup and debug mode"""
    parser = argparse.ArgumentParser(description="High-Performance Accessible Menu Navigation")
    parser.add_argument("profile", nargs="?", default=None, help="Path to menu profile JSON file")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode (logs to file)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--languages", type=str, default="en", help="OCR languages, comma-separated (e.g., 'en,fr,es')")
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging(args.debug)
    
    # Parse OCR languages
    ocr_languages = [lang.strip() for lang in args.languages.split(',')]
    
    # Handle profile selection
    profile_path = args.profile
    
    # If no profile specified, prompt with file dialog
    if profile_path is None:
        # Get the application's directory
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        
        try:
            import tkinter as tk
            from tkinter import filedialog
            
            # Create profiles directory if it doesn't exist
            profiles_dir = os.path.join(app_dir, 'profiles')
            if not os.path.exists(profiles_dir):
                os.makedirs(profiles_dir)
                logger.info(f"Created profiles directory: {profiles_dir}")
            
            # Initialize Tkinter (hide main window)
            root = tk.Tk()
            root.withdraw()
            
            # Show file dialog starting in profiles directory
            selected_path = filedialog.askopenfilename(
                initialdir=profiles_dir,
                title="Select Menu Profile",
                filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
            )
            
            # Use selected path if user didn't cancel
            if selected_path:
                profile_path = selected_path
                logger.info(f"Selected profile: {profile_path}")
            else:
                # No profile selected, inform the user and exit
                logger.info("No profile selected, exiting")
                try:
                    # Try to use accessible_output2 directly for announcement
                    import accessible_output2.outputs.auto as ao
                    speaker = ao.Auto()
                    speaker.speak("No profile selected. Please select a profile to run MenuAccess.")
                except ImportError:
                    # Fall back to print if accessible_output2 not available
                    print("Ao2 not available!")
                    print("No profile selected. Please select a profile to run MenuAccess.")
                
                # Wait 3 seconds before exiting
                time.sleep(3)
                sys.exit(0)
                
        except Exception as e:
            # Error with file dialog
            logger.error(f"Error during profile selection: {e}")
            try:
                # Try to use accessible_output2 directly for announcement
                import accessible_output2.outputs.auto as ao
                speaker = ao.Auto()
                speaker.speak("Error showing file selection dialog. Please select a profile to run MenuAccess.")
            except ImportError:
                # Fall back to print if accessible_output2 not available]
                print("Ao2 not available!")
                print("Error showing file selection dialog. Please select a profile to run MenuAccess.")
            
            # Wait 5 seconds before exiting
            time.sleep(5)
            sys.exit(0)
    
    # Create the navigator
    navigator = AccessibleMenuNavigator()
    
    # Set verbose and debug modes
    navigator.set_verbose(args.verbose)
    navigator.set_debug(args.debug)
    
    try:
        # Start the navigator with the specified profile and languages
        navigator.start(profile_path, ocr_languages)
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