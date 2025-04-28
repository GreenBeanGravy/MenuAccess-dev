"""
Main entry point for the MenuAccess application
"""

import sys
import os
import argparse
import logging
import time
import threading
import queue

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
    
    # Initialize the OCR handler before starting the navigator
    # This prevents crashes and improves overall stability
    logger.info("Initializing OCR engine. Please wait...")
    
    try:
        # Show a loading message
        try:
            import accessible_output2.outputs.auto as ao
            speaker = ao.Auto()
            speaker.speak("Initializing OCR engine. Please wait...")
        except ImportError:
            print("Initializing OCR engine. Please wait...")
        
        # Pre-initialize OCR in a controlled manner
        ocr_ready = threading.Event()
        ocr_error = queue.Queue()
        
        def init_ocr():
            try:
                # Create and initialize OCR handler
                from malib.ocr_handler import OCRHandler
                ocr_handler = OCRHandler(ocr_languages)
                ocr_handler.initialize_reader()
                navigator.ocr_handler = ocr_handler
                ocr_ready.set()
            except Exception as e:
                logger.error(f"OCR initialization error: {e}")
                ocr_error.put(str(e))
                ocr_ready.set()  # Signal that we're done even though there was an error
        
        # Start OCR initialization in a background thread
        ocr_thread = threading.Thread(target=init_ocr, daemon=True)
        ocr_thread.start()
        
        # Show a loading progress indication
        progress_chars = ["|", "/", "-", "\\"]
        progress_idx = 0
        
        while not ocr_ready.is_set():
            sys.stdout.write(f"\rInitializing OCR engine {progress_chars[progress_idx]} ")
            sys.stdout.flush()
            progress_idx = (progress_idx + 1) % len(progress_chars)
            time.sleep(0.1)
        
        sys.stdout.write("\rOCR engine initialized!       \n")
        
        # Check if there was an error
        if not ocr_error.empty():
            error_msg = ocr_error.get()
            logger.error(f"Failed to initialize OCR: {error_msg}")
            print(f"OCR initialization failed: {error_msg}")
            print("MenuAccess will continue without OCR functionality.")
            
            try:
                import accessible_output2.outputs.auto as ao
                speaker = ao.Auto()
                speaker.speak("OCR initialization failed. MenuAccess will continue without OCR functionality.")
            except ImportError:
                pass
            
            # Wait a moment to let the message be heard
            time.sleep(3)
        else:
            logger.info("OCR engine successfully initialized")
            print("OCR engine successfully initialized")
            
            try:
                import accessible_output2.outputs.auto as ao
                speaker = ao.Auto()
                speaker.speak("OCR engine successfully initialized")
            except ImportError:
                pass
        
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
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Fatal error: {e}")
        
        try:
            import accessible_output2.outputs.auto as ao
            speaker = ao.Auto()
            speaker.speak(f"Fatal error occurred. MenuAccess will now exit.")
        except ImportError:
            pass
        
        # Exit with error
        sys.exit(1)

if __name__ == "__main__":
    main()