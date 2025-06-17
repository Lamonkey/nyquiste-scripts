import os
import sys
from dotenv import load_dotenv

# Add parent directory to system path for importing main module
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Path to .env file and load it
ENV_FILE_PATH = os.path.join(parent_dir, '.env')

# Check if .env file exists and load it
if not os.path.exists(ENV_FILE_PATH):
    raise FileNotFoundError(
        f".env file not found at {ENV_FILE_PATH}. "
        "Please create it with your configuration."
    )

# Load .env file
if not load_dotenv(ENV_FILE_PATH):
    raise RuntimeError(f"Failed to load .env file from {ENV_FILE_PATH}")

# Export environment variables as Python variables
HOST = os.getenv('HOST')
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

# Hardcoded values
PORT = 22
LOCAL_DIR = os.path.join(parent_dir, 'tests', 'data_source')
REMOTE_DIR = '/test-upload'

import main

# Export main module and environment variables for easy importing
__all__ = [
    'main', 'HOST', 'PORT', 'USERNAME', 'PASSWORD', 
    'REMOTE_DIR', 'LOCAL_DIR'
] 