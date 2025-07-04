import os
import time
import zipfile
import paramiko
import argparse
import sys
import tempfile

def zip_file(input_file, output_zip):
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(input_file, arcname=os.path.basename(input_file))

def zip_folder(input_folder, output_zip):
    """Zip a folder recursively."""
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(input_folder):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, input_folder)
                zipf.write(abs_path, arcname=rel_path)

def sftp_upload(sftp, local_path, remote_path):
    """Upload a file with progress reporting and timeout handling."""
    start = time.time()
    
    # Get file size for progress reporting
    file_size = os.path.getsize(local_path)
    print(f"Uploading {os.path.basename(local_path)} ({file_size / (1024*1024):.1f} MB)...")
    
    # Set longer timeout for large files
    sftp.get_channel().settimeout(300)  # 5 minutes timeout
    
    try:
        sftp.put(local_path, remote_path)
        end = time.time()
        print(f"Upload completed in {end - start:.2f} seconds")
        return end - start
    except Exception as e:
        print(f"Upload failed: {e}")
        raise

def exists_remote(sftp, path):
    """Return True if a file or directory exists on the server."""
    try:
        sftp.stat(path)
    except IOError:
        return False
    return True

def sftp_mkdirs(sftp, remote_directory):
    """Change to this dir, recursively making parent dirs if needed."""
    dirs = []
    head, tail = os.path.split(remote_directory.rstrip('/'))
    while head and tail and not exists_remote(sftp, head):
        dirs.insert(0, head)
        head, tail = os.path.split(head)
    for directory in dirs + [remote_directory]:
        try:
            sftp.mkdir(directory)
        except IOError:
            pass  # already exists

def put_r(sftp, local_path, remote_path):
    """Recursively upload a local directory to the remote path."""
    if os.path.isfile(local_path):
        # Simple file
        dirname = os.path.dirname(remote_path)
        if dirname:
            sftp_mkdirs(sftp, dirname)
        sftp.put(local_path, remote_path)
    else:
        # Directory: walk tree
        for root, dirs, files in os.walk(local_path):
            # compute remote directory for this root
            rel = os.path.relpath(root, local_path).replace('\\', '/')
            if rel == '.':
                rdir = remote_path.rstrip('/')
            else:
                rdir = (remote_path.rstrip('/') + '/' + rel)
            sftp_mkdirs(sftp, rdir)
            for fname in files:
                local_file = os.path.join(root, fname)
                remote_file = rdir + '/' + fname
                sftp.put(local_file, remote_file)

def sftp_upload_folder_recursive(sftp, local_folder, remote_folder, ssh=None):
    """Upload a folder recursively via SFTP with explicit directory creation."""
    start = time.time()
    
    # Convert to Unix-style path for remote
    remote_folder = remote_folder.replace('\\', '/')
    
    print(f"Uploading folder recursively: {local_folder} -> {remote_folder}")
    
    uploaded_count = 0
    failed_count = 0
    
    # Count total files first
    total_files = sum(len(files) for _, _, files in os.walk(local_folder))
    print(f"Found {total_files} files to upload...")
    
    try:
        # Use the improved put_r function
        put_r(sftp, local_folder, remote_folder)
        
        # Count successful uploads by walking the local directory
        for root, _, files in os.walk(local_folder):
            for file in files:
                local_file = os.path.join(root, file)
                rel_path = os.path.relpath(local_file, local_folder)
                file_size = os.path.getsize(local_file)
                print(f"  ✓ {rel_path} ({file_size / 1024:.1f} KB)")
                uploaded_count += 1
                
    except Exception as e:
        print(f"  ✗ Upload failed: {e}")
        failed_count = total_files
    
    end = time.time()
    return end - start, uploaded_count, failed_count

def create_remote_dir(ssh, remote_dir):
    """Create remote directory if it doesn't exist."""
    # Convert Windows path to Unix-style for PowerShell
    remote_dir_unix = remote_dir.replace('\\', '/')
    
    # PowerShell command to create directory if it doesn't exist
    mkdir_cmd = (
        f'powershell -Command "if (!(Test-Path \'{remote_dir_unix}\')) {{ '
        f'New-Item -ItemType Directory -Path \'{remote_dir_unix}\' -Force }}; '
        f'Write-Host \'Directory ready: {remote_dir_unix}\'"'
    )
    
    stdin, stdout, stderr = ssh.exec_command(mkdir_cmd)
    exit_status = stdout.channel.recv_exit_status()
    
    if exit_status != 0:
        error_msg = stderr.read().decode().strip()
        print(f"Warning: Could not create remote directory: {error_msg}")
        return False
    else:
        result = stdout.read().decode().strip()
        print(result)
        return True

def clear_remote_directory(ssh, remote_dir):
    """Clear the remote directory completely."""
    remote_dir_unix = remote_dir.replace('\\', '/')
    clear_cmd = (
        f'powershell -Command "if (Test-Path \'{remote_dir_unix}\') {{ '
        f'Remove-Item -Path \'{remote_dir_unix}\' -Recurse -Force }}; '
        f'Write-Host \'Directory cleared: {remote_dir_unix}\'"'
    )
    
    stdin, stdout, stderr = ssh.exec_command(clear_cmd)
    exit_status = stdout.channel.recv_exit_status()
    
    if exit_status != 0:
        error_msg = stderr.read().decode().strip()
        print(f"Warning: Could not clear remote directory: {error_msg}")
        return False
    else:
        result = stdout.read().decode().strip()
        print(result)
        return True

def ssh_unzip(ssh, remote_zip, remote_dest):
    unzip_cmd = (
        f'powershell -Command "Expand-Archive -Path {remote_zip} '
        f'-DestinationPath {remote_dest} -Force"'
    )
    stdin, stdout, stderr = ssh.exec_command(unzip_cmd)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        print("Unzip failed:", stderr.read().decode())
        return False
    else:
        print("Unzip succeeded.")
        return True

def create_zip_file(local_path):
    """Create a zip file from the given local path and return the zip file path."""
    temp_dir = tempfile.gettempdir()
    zip_filename = f"upload_test_{int(time.time())}.zip"
    zip_path = os.path.join(temp_dir, zip_filename)
    
    print(f"Creating zip file: {zip_path}")
    if os.path.isdir(local_path):
        zip_folder(local_path, zip_path)
    else:
        zip_file(local_path, zip_path)
    
    # Get zip file size for progress reporting
    zip_size = os.path.getsize(zip_path)
    print(f"Zip file created: {zip_size / (1024*1024):.1f} MB")
    
    return zip_path

def test_ssh_connection(host, port, username, password):
    """Simple SSH connection test."""
    print("Testing SSH connection...")
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=host, 
            port=port, 
            username=username, 
            password=password,
            timeout=10
        )
        ssh.close()
        print("✓ SSH connection successful")
        return True
    except Exception as e:
        print(f"✗ SSH connection failed: {e}")
        print("Please check your connection parameters and try again.")
        return False

def calculate_directory_stats(local_path):
    """Calculate file count and total size of a directory."""
    if os.path.isfile(local_path):
        return 1, os.path.getsize(local_path)
    
    total_files = 0
    total_size = 0
    
    for root, _, files in os.walk(local_path):
        for file in files:
            file_path = os.path.join(root, file)
            total_files += 1
            total_size += os.path.getsize(file_path)
    
    return total_files, total_size

def run_single_test(host, port, username, password, local_path,
                   remote_dir, test_name):
    """Run a single test synchronously."""
    print(f"\n{'='*60}")
    print(f"Running {test_name}")
    print(f"{'='*60}")
    
    # Calculate directory statistics
    file_count, total_size = calculate_directory_stats(local_path)
    size_mb = total_size / (1024 * 1024)
    print(f"Directory stats: {file_count} files, {size_mb:.1f} MB")
    
    if test_name == "ZIP Upload Test":
        # Create zip file BEFORE establishing connection
        print("Creating zip file before connection...")
        zip_start = time.time()
        zip_path = create_zip_file(local_path)
        zip_time = time.time() - zip_start
        print(f"Zip creation time: {zip_time:.2f} seconds")
        
        # Now establish SSH connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=host, port=port, username=username, 
                   password=password)
        
        # Clear and recreate remote directory
        print(f"Clearing remote directory: {remote_dir}")
        clear_remote_directory(ssh, remote_dir)
        print(f"Creating remote directory: {remote_dir}")
        create_remote_dir(ssh, remote_dir)
        
        sftp = ssh.open_sftp()
        
        # Upload the pre-created zip file
        remote_zip = (os.path.join(remote_dir, os.path.basename(zip_path))
                     .replace('\\', '/'))
        
        print("Uploading zip file...")
        upload_time = sftp_upload(sftp, zip_path, remote_zip)
        print(f"Upload time: {upload_time:.2f} seconds")
        
        print("Extracting zip file...")
        unzip_start = time.time()
        unzip_success = ssh_unzip(ssh, remote_zip, remote_dir)
        unzip_time = time.time() - unzip_start
        
        total_time = zip_time + upload_time + unzip_time
        print(f"Total time: {total_time:.2f} seconds")
        
        # Clean up local zip
        if os.path.exists(zip_path):
            os.remove(zip_path)
        
        result = {
            'test_name': test_name,
            'file_count': file_count,
            'total_size_mb': size_mb,
            'zip_time': zip_time,
            'upload_time': upload_time,
            'unzip_time': unzip_time,
            'total_time': total_time,
            'success': unzip_success
        }
        
        sftp.close()
        ssh.close()
        
    elif test_name == "Recursive Upload Test":
        # Establish SSH connection for recursive upload
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=host, port=port, username=username, 
                   password=password)
        
        # Clear and recreate remote directory
        print(f"Clearing remote directory: {remote_dir}")
        clear_remote_directory(ssh, remote_dir)
        print(f"Creating remote directory: {remote_dir}")
        create_remote_dir(ssh, remote_dir)
        
        sftp = ssh.open_sftp()
        
        # Recursive upload test
        print("Uploading folder recursively...")
        upload_time, uploaded_count, failed_count = (
            sftp_upload_folder_recursive(sftp, local_path, remote_dir, ssh)
        )
        
        result = {
            'test_name': test_name,
            'file_count': file_count,
            'total_size_mb': size_mb,
            'upload_time': upload_time,
            'total_time': upload_time,
            'uploaded_files': uploaded_count,
            'failed_files': failed_count,
            'success': failed_count == 0
        }
        
        sftp.close()
        ssh.close()
    
    return result

def run_comprehensive_tests(host, port, username, password, local_path, 
                           remote_dir):
    """Run comprehensive speed comparison tests."""
    print(f"\n{'='*80}")
    print("COMPREHENSIVE UPLOAD SPEED COMPARISON TEST")
    print(f"{'='*80}")
    print(f"Local path: {local_path}")
    print(f"Remote directory: {remote_dir}")
    print(f"Server: {host}:{port}")
    
    # Run tests sequentially to avoid conflicts
    print("\nRunning tests sequentially...")
    
    # Run ZIP test first
    zip_result = run_single_test(
        host, port, username, password, local_path, remote_dir, 
        "ZIP Upload Test"
    )
    
    # Run recursive test second
    recursive_result = run_single_test(
        host, port, username, password, local_path, remote_dir, 
        "Recursive Upload Test"
    )
    
    results = [zip_result, recursive_result]
    
    # Generate comprehensive report
    print(f"\n{'='*80}")
    print("SPEED COMPARISON REPORT")
    print(f"{'='*80}")
    
    print(f"\nDirectory Information:")
    print(f"  Files: {zip_result['file_count']}")
    print(f"  Total size: {zip_result['total_size_mb']:.1f} MB")
    
    print("\nZIP Upload Test:")
    print(f"  Zip creation time: {zip_result['zip_time']:.2f} seconds")
    print(f"  Upload time: {zip_result['upload_time']:.2f} seconds")
    print(f"  Unzip time: {zip_result['unzip_time']:.2f} seconds")
    print(f"  Total time: {zip_result['total_time']:.2f} seconds")
    print(f"  Success: {zip_result['success']}")
    
    print("\nRecursive Upload Test:")
    print(f"  Upload time: {recursive_result['upload_time']:.2f} seconds")
    print(f"  Total time: {recursive_result['total_time']:.2f} seconds")
    print(f"  Files uploaded: {recursive_result['uploaded_files']}")
    print(f"  Files failed: {recursive_result['failed_files']}")
    print(f"  Success: {recursive_result['success']}")
    
    # Calculate speed difference
    time_diff = recursive_result['total_time'] - zip_result['total_time']
    speed_ratio = (zip_result['total_time'] / recursive_result['total_time'] 
                   if recursive_result['total_time'] > 0 else float('inf'))
    
    print(f"\n{'='*50}")
    print("COMPARISON SUMMARY")
    print(f"{'='*50}")
    
    if time_diff > 0:
        print(f"ZIP method is {time_diff:.2f} seconds FASTER")
        print(f"ZIP method is {speed_ratio:.2f}x faster than recursive upload")
    else:
        print(f"Recursive method is {abs(time_diff):.2f} seconds FASTER")
        print(f"Recursive method is {1/speed_ratio:.2f}x faster than ZIP upload")
    
    print("\nRecommendation:")
    if zip_result['total_time'] < recursive_result['total_time']:
        print("  Use ZIP upload method for better performance")
    else:
        print("  Use recursive upload method for better performance")
    
    return results

def main():
    """CLI entry point for the upload speed comparison tool."""
    parser = argparse.ArgumentParser(
        description="Upload Speed Comparison Tool - Compare ZIP vs Recursive upload methods",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --host 192.168.1.100 --username admin --password secret --local-path ./data --remote-dir "C:/Uploads"
  python main.py -H 10.0.0.5 -u user -p pass -l ./files -r "D:/TestUploads" --port 2222
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--host', '-H',
        required=True,
        help='SSH server hostname or IP address'
    )
    parser.add_argument(
        '--username', '-u',
        required=True,
        help='SSH username'
    )
    parser.add_argument(
        '--password', '-p',
        required=True,
        help='SSH password'
    )
    parser.add_argument(
        '--local-path', '-l',
        required=True,
        help='Local file or directory path to upload'
    )
    parser.add_argument(
        '--remote-dir', '-r',
        required=True,
        help='Remote directory path on the server'
    )
    
    # Optional arguments
    parser.add_argument(
        '--port',
        type=int,
        default=22,
        help='SSH port (default: 22)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Validate local path exists
    if not os.path.exists(args.local_path):
        print(f"Error: Local path '{args.local_path}' does not exist.")
        sys.exit(1)
    
    # Validate port range
    if not (1 <= args.port <= 65535):
        print(f"Error: Port must be between 1 and 65535, got {args.port}")
        sys.exit(1)
    
    try:
        print("Starting upload speed comparison test...")
        print(f"Host: {args.host}:{args.port}")
        print(f"Local path: {args.local_path}")
        print(f"Remote directory: {args.remote_dir}")
        
        # Simple SSH connection test before doing anything expensive
        if not test_ssh_connection(args.host, args.port, args.username, args.password):
            sys.exit(1)
        
        # Check if the local path is very large
        if os.path.isdir(args.local_path):
            total_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(args.local_path)
                for filename in filenames
            )
            size_mb = total_size / (1024 * 1024)
            print(f"Total size to upload: {size_mb:.1f} MB")
            
            if size_mb > 100:  # Warning for files larger than 100MB
                print(f"\n⚠️  WARNING: Large folder detected ({size_mb:.1f} MB)")
                print("   This may cause connection timeouts. Consider using a smaller test folder.")
                print("   For testing, try using: tests/data_source")
                
                if not args.verbose:
                    response = input("Continue anyway? (y/N): ")
                    if response.lower() != 'y':
                        print("Test cancelled.")
                        sys.exit(0)
        
        # Run the comprehensive tests
        run_comprehensive_tests(
            host=args.host,
            port=args.port,
            username=args.username,
            password=args.password,
            local_path=args.local_path,
            remote_dir=args.remote_dir
        )
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error running tests: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
