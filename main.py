"""
This is the main entry point for the agent. 
It can be used to initialize the agent and start its main loop.
"""
import logging
from core.imap_listener import IMAPListener
def main():
    """Main function to start the email polling agent."""
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting Email AI Service...")
    
    listener = IMAPListener()
    listener.start()
if __name__ == "__main__":
    main()
