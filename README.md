# Upload Speed Comparison Tool

* This tool compares the speed of uploading files/folders to a remote Windows VM using two methods: ZIP upload+extract vs. recursive SFTP upload. It is designed for Python 3.11.1.
* Getting Started

### 1. Clone the Repository

```sh
# Using HTTPS
git clone https://github.com/Lamonkey/nyquiste-scripts.git
cd nyquiste-scripts
```

### 2. Install the Environment

Make sure you have Python 3.11.1 installed. Then install dependencies:

```sh
pip install -r requirements.txt
```

### 3. Run the Script

Use the following command format to run the tool:

```sh
python main.py --username=<your-username> --host=<your-host-ip> --password=<your-password> \
  --local-path=<path-to-local-folder> \
  --remote-dir=<remote-directory-path> -v
```

- `--username`: SSH username for the remote VM
- `--host`: IP address or hostname of the remote VM
- `--password`: SSH password
- `--local-path`: Path to the local file or folder to upload (e.g., `tests/data_source` contains lightweight test files)
- `--remote-dir`: Remote directory path on the VM
- `-v`: (Optional) Enable verbose output

### 4. Example Output

When you run with `-v`, you will see a detailed speed comparison report like this:

```
================================================================================
SPEED COMPARISON REPORT
================================================================================

ZIP Upload Test:
  Upload time: 0.15 seconds
  Unzip time: 1.20 seconds
  Total time: 1.35 seconds
  Success: True

Recursive Upload Test:
  Upload time: 0.35 seconds
  Total time: 0.35 seconds
  Files uploaded: 2
  Files failed: 0
  Success: True

==================================================
COMPARISON SUMMARY
==================================================
Recursive method is 0.99 seconds FASTER
Recursive method is 0.26x faster than ZIP upload

Recommendation:
  Use recursive upload method for better performance
```

### 5. Test Data

The `tests/data_source` folder contains lightweight files for testing the upload process.
