import os
import time
import zipfile
import paramiko
import asyncio
import shutil
from concurrent.futures import ThreadPoolExecutor

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
    start = time.time()
    sftp.put(local_path, remote_path)
    end = time.time()
    return end - start

def sftp_upload_folder_recursive(sftp, local_folder, remote_folder):
    """Upload a folder recursively via SFTP."""
    start = time.time()
    
    def upload_file(local_file, remote_file):
        try:
            sftp.put(local_file, remote_file)
            return True
        except Exception as e:
            print(f"Failed to upload {local_file}: {e}")
            return False
    
    uploaded_count = 0
    failed_count = 0
    
    for root, _, files in os.walk(local_folder):
        for file in files:
            local_file = os.path.join(root, file)
            rel_path = os.path.relpath(local_file, local_folder)
            remote_file = os.path.join(remote_folder, rel_path).replace('\\', '/')
            
            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_file)
            try:
                sftp.mkdir(remote_dir)
            except:
                pass  # Directory might already exist
            
            if upload_file(local_file, remote_file):
                uploaded_count += 1
            else:
                failed_count += 1
    
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
    clear_cmd = f'powershell -Command "if (Test-Path \'{remote_dir_unix}\') {{ Remove-Item -Path \'{remote_dir_unix}\' -Recurse -Force }}; Write-Host \'Directory cleared: {remote_dir_unix}\'"'
    
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
    unzip_cmd = f'powershell -Command "Expand-Archive -Path {remote_zip} -DestinationPath {remote_dest} -Force"'
    stdin, stdout, stderr = ssh.exec_command(unzip_cmd)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        print("Unzip failed:", stderr.read().decode())
        return False
    else:
        print("Unzip succeeded.")
        return True

async def run_async_test(host, port, username, password, local_path, remote_dir, test_name):
    """Run a single test asynchronously."""
    loop = asyncio.get_event_loop()
    
    with ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(
            executor, 
            run_single_test, 
            host, port, username, password, local_path, remote_dir, test_name
        )

def run_single_test(host, port, username, password, local_path, remote_dir, test_name):
    """Run a single test synchronously."""
    print(f"\n{'='*60}")
    print(f"Running {test_name}")
    print(f"{'='*60}")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, port=port, username=username, password=password)
    
    # Clear and recreate remote directory
    print(f"Clearing remote directory: {remote_dir}")
    clear_remote_directory(ssh, remote_dir)
    print(f"Creating remote directory: {remote_dir}")
    create_remote_dir(ssh, remote_dir)
    
    sftp = ssh.open_sftp()
    
    if test_name == "ZIP Upload Test":
        # Zip upload test
        zip_path = local_path + '.zip'
        remote_zip = os.path.join(remote_dir, os.path.basename(zip_path)).replace('\\', '/')
        
        print(f"Creating zip file: {zip_path}")
        if os.path.isdir(local_path):
            zip_folder(local_path, zip_path)
        else:
            zip_file(local_path, zip_path)
        
        print("Uploading zip file...")
        upload_time = sftp_upload(sftp, zip_path, remote_zip)
        print(f"Upload time: {upload_time:.2f} seconds")
        
        print("Extracting zip file...")
        unzip_start = time.time()
        unzip_success = ssh_unzip(ssh, remote_zip, remote_dir)
        unzip_time = time.time() - unzip_start
        
        total_time = upload_time + unzip_time
        print(f"Total time: {total_time:.2f} seconds")
        
        # Clean up local zip
        if os.path.exists(zip_path):
            os.remove(zip_path)
        
        result = {
            'test_name': test_name,
            'upload_time': upload_time,
            'unzip_time': unzip_time,
            'total_time': total_time,
            'success': unzip_success
        }
        
    elif test_name == "Recursive Upload Test":
        # Recursive upload test
        print("Uploading folder recursively...")
        upload_time, uploaded_count, failed_count = sftp_upload_folder_recursive(
            sftp, local_path, remote_dir
        )
        
        result = {
            'test_name': test_name,
            'upload_time': upload_time,
            'total_time': upload_time,
            'uploaded_files': uploaded_count,
            'failed_files': failed_count,
            'success': failed_count == 0
        }
    
    sftp.close()
    ssh.close()
    
    return result

async def run_comprehensive_tests(host, port, username, password, local_path, remote_dir):
    """Run comprehensive speed comparison tests."""
    print(f"\n{'='*80}")
    print(f"COMPREHENSIVE UPLOAD SPEED COMPARISON TEST")
    print(f"{'='*80}")
    print(f"Local path: {local_path}")
    print(f"Remote directory: {remote_dir}")
    print(f"Server: {host}:{port}")
    
    # Run tests asynchronously
    tasks = [
        run_async_test(host, port, username, password, local_path, remote_dir, "ZIP Upload Test"),
        run_async_test(host, port, username, password, local_path, remote_dir, "Recursive Upload Test")
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Generate comprehensive report
    print(f"\n{'='*80}")
    print(f"SPEED COMPARISON REPORT")
    print(f"{'='*80}")
    
    zip_result = next(r for r in results if r['test_name'] == "ZIP Upload Test")
    recursive_result = next(r for r in results if r['test_name'] == "Recursive Upload Test")
    
    print(f"\nZIP Upload Test:")
    print(f"  Upload time: {zip_result['upload_time']:.2f} seconds")
    print(f"  Unzip time: {zip_result['unzip_time']:.2f} seconds")
    print(f"  Total time: {zip_result['total_time']:.2f} seconds")
    print(f"  Success: {zip_result['success']}")
    
    print(f"\nRecursive Upload Test:")
    print(f"  Upload time: {recursive_result['upload_time']:.2f} seconds")
    print(f"  Total time: {recursive_result['total_time']:.2f} seconds")
    print(f"  Files uploaded: {recursive_result['uploaded_files']}")
    print(f"  Files failed: {recursive_result['failed_files']}")
    print(f"  Success: {recursive_result['success']}")
    
    # Calculate speed difference
    time_diff = recursive_result['total_time'] - zip_result['total_time']
    speed_ratio = zip_result['total_time'] / recursive_result['total_time'] if recursive_result['total_time'] > 0 else float('inf')
    
    print(f"\n{'='*50}")
    print(f"COMPARISON SUMMARY")
    print(f"{'='*50}")
    
    if time_diff > 0:
        print(f"ZIP method is {time_diff:.2f} seconds FASTER")
        print(f"ZIP method is {speed_ratio:.2f}x faster than recursive upload")
    else:
        print(f"Recursive method is {abs(time_diff):.2f} seconds FASTER")
        print(f"Recursive method is {1/speed_ratio:.2f}x faster than ZIP upload")
    
    print(f"\nRecommendation:")
    if zip_result['total_time'] < recursive_result['total_time']:
        print(f"  Use ZIP upload method for better performance")
    else:
        print(f"  Use recursive upload method for better performance")
    
    return results

def run_tests(host, port, username, password, local_path, remote_dir):
    """Legacy function for backward compatibility."""
    asyncio.run(run_comprehensive_tests(host, port, username, password, local_path, remote_dir))

if __name__ == "__main__":
    run_tests(
        host="your.server.ip",
        port=22,
        username="your_username",
        password="your_password",
        local_path="/path/to/local/file.txt",
        remote_dir="C:/Users/YourUser/Uploads"
    )
