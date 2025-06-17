import os
import sys

# Import context to set up system path and load .env variables
from context import (
    main, HOST, PORT, USERNAME, PASSWORD, REMOTE_DIR, LOCAL_DIR
)
from main import run_comprehensive_tests


def main():
    """Main test function using .env configuration."""
    # Validate required parameters from .env
    if not all([HOST, USERNAME, PASSWORD, REMOTE_DIR, LOCAL_DIR]):
        print(
            "Error: Missing required parameters in .env file. "
            "Please check your configuration."
        )
        print(
            "Required parameters: HOST, USERNAME, PASSWORD, REMOTE_DIR, "
            "LOCAL_DIR"
        )
        sys.exit(1)
    
    if not os.path.exists(LOCAL_DIR):
        print(f"Error: Local directory '{LOCAL_DIR}' does not exist.")
        sys.exit(1)
    
    print(f"Running comprehensive speed comparison tests")
    print(f"Local directory: {LOCAL_DIR}")
    print(f"Remote directory: {REMOTE_DIR}")
    print(f"Server: {HOST}:{PORT}")
    
    # Run the comprehensive speed comparison tests
    import asyncio
    asyncio.run(run_comprehensive_tests(HOST, PORT, USERNAME, PASSWORD, LOCAL_DIR, REMOTE_DIR))


if __name__ == "__main__":
    main()