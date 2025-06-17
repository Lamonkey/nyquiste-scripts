"""
Integration Test for SFTP Upload Speed Comparison

This file is NOT a unit test, but rather an integration test that validates
the complete end-to-end functionality of the SFTP upload speed comparison tool.

Integration Test Purpose:
- Tests the full workflow of connecting to a remote server via SSH/SFTP
- Validates both ZIP upload and recursive upload methods work correctly
- Ensures the comprehensive speed comparison report is generated properly
- Verifies that the tool can handle real file transfers and measurements

This test requires:
- A real SSH server with valid credentials
- Network connectivity to the remote server
- Actual files/folders to transfer
- Proper SFTP permissions on the remote server

The test uses configuration from a .env file to connect to a real server
and perform actual file transfers, making it a true integration test
rather than isolated unit tests.
"""
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