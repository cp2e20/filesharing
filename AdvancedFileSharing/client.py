import socket
import os
import hashlib
from datetime import datetime
import sys
import math
import time
import json

# server configuration
HOST = 'localhost'
PORT = 5002
DOWNLOAD = 'downloaded'  # directory to save downloaded files
LOG_FILE = 'logs/client_log.txt'  # log file for clients
CHECKPOINT_FILE = 'logs/client_checkpoints.json'  # File to store download progress

# function to log events
def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

# helper to read a full line ending with '\n'
def recv_line(sock, expect_binary=False):
    buffer = b'' if expect_binary else ''
    while True:
        data = sock.recv(1024)
        if not data:
            break
        if expect_binary:
            buffer += data
        else:
            buffer += data.decode()
        if b'\n' in buffer if expect_binary else '\n' in buffer:
            line, _ = buffer.split(b'\n' if expect_binary else '\n', 1)
            return line
    return buffer

# list files on server
def list_files(sock):
    sock.send("LIST\n".encode())
    files = sock.recv(4096).decode()
    print("Files on Server:\n", files)
    log("Requested list of files from server.")

# upload file
def upload_file(sock, path):
    filename = os.path.basename(path)
    if not os.path.exists(path):
        print("File does not exist.")
        log(f"Upload failed: File '{path}' does not exist.")
        return

    size = os.path.getsize(path)
    print(f"File size: {size} bytes")

    # Compute SHA-256 hash
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(1024):
            hasher.update(chunk)
    sha256_hash = hasher.hexdigest()

    print(f"Uploading {filename} (size: {size}, hash: {sha256_hash[:8]}...)")

    try:
        # Send command with newline
        sock.send(f"UPLOAD {filename} {size}\n".encode())

        # Wait for server's response
        response = recv_line(sock)
        if response != "READY":
            print("Server not ready for upload")
            return

        # Send file in chunks with progress
        uploaded = 0
        chunk_size = 4096  # Increased chunk size
        with open(path, 'rb') as f:
            while chunk := f.read(chunk_size):
                try:
                    sock.sendall(chunk)  # sendall ensures complete transmission
                    uploaded += len(chunk)
                    # Show progress
                    progress = (uploaded / size) * 100
                    print(f"\rUpload progress: {progress:.1f}%", end='', flush=True)
                except (ConnectionResetError, BrokenPipeError) as e:
                    print(f"\nUpload interrupted: {e}")
                    log(f"Upload interrupted for '{filename}' at {uploaded} bytes")
                    return

        print("\nWaiting for hash verification...")
        # Receive hash from server
        received_hash = recv_line(sock)
        if received_hash == sha256_hash:
            print(f"Upload successful [Hash verified]")
            log(f"Uploaded file '{filename}' ({size} bytes)")
        else:
            print("Hash mismatch after upload.")
            log(f"Hash mismatch for '{filename}'. Expected: {sha256_hash}, Received: {received_hash}")

    except ConnectionResetError as e:
        print(f"\nConnection lost during upload: {e}")
        log(f"Connection lost during upload of '{filename}': {e}")
    except Exception as e:
        print(f"\nUpload error: {e}")
        log(f"Error uploading '{filename}': {e}")

# download file

def download_file(sock, filename):
    # Check for existing partial download
    checkpoints = {}
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            try:
                checkpoints = json.load(f)
            except json.JSONDecodeError:
                checkpoints = {}
    
    resume_from = 0
    partial_file = os.path.join(DOWNLOAD, filename)
    if filename in checkpoints and os.path.exists(partial_file):
        resume_from = checkpoints[filename]["bytes_received"]
        print(f"Resuming download from byte {resume_from}")
        actual_size = os.path.getsize(partial_file)
        if actual_size != resume_from:
            print(f"Warning: Partial file size ({actual_size}) doesn't match checkpoint ({resume_from}). Adjusting.")
            resume_from = actual_size
        print(f"Resuming download from byte {resume_from}")
    
    sock.send(f"DOWNLOAD {filename}\n".encode())
    size_data = recv_line(sock)
    if size_data == "ERROR":
        print("File not found on server.")
        log(f"Download failed: File '{filename}' not found on server.")
        return
    
    total_size = int(size_data)
    if resume_from > 0:
        sock.send(f"RESUME {resume_from}\n".encode())
    else:
        sock.send("READY\n".encode())
    
    mode = 'ab' if resume_from > 0 else 'wb'
    
    # Initialize progress bar
    start_time = time.time()
    bytes_received = resume_from
    last_update_time = start_time

    
    def format_size(size):
        """Convert bytes to human-readable format"""
        if size == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size, 1024)))
        p = math.pow(1024, i)
        s = round(size / p, 2)
        return f"{s} {size_name[i]}"
    
    def format_time(seconds):
        """Convert seconds to MM:SS format"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def draw_progress_bar(progress, speed, elapsed):
        """Draw a progress bar in the console"""
        bar_length = 50
        filled_length = int(round(bar_length * progress))
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        percent = round(progress * 100, 1)
        
        # Calculate estimated time remaining
        if progress > 0 and speed > 0:
            remaining_bytes = total_size - bytes_received
            eta = remaining_bytes / speed
            eta_str = format_time(eta)
        else:
            eta_str = "--:--"
        
        sys.stdout.write(
            f"\rDownloading: |{bar}| {percent}% "
            f"{format_size(bytes_received)}/{format_size(total_size)} "
            f"[{speed:.2f} KB/s, ETA: {eta_str}, Elapsed: {format_time(elapsed)}]"
)
        sys.stdout.flush()
    
    with open(partial_file, mode) as f:
        while bytes_received < total_size:
            chunk = sock.recv(1024)
            if not chunk:
                break
            f.write(chunk)
            bytes_received += len(chunk)
            
            # Update progress every 100ms or when download completes
            current_time = time.time()
            if current_time - last_update_time > 0.1 or bytes_received == total_size:
                elapsed_time = current_time - start_time
                progress = bytes_received / total_size
                speed = (bytes_received - resume_from) / elapsed_time / 1024  # KB/s
                draw_progress_bar(progress, speed, elapsed_time)
                last_update_time = current_time
            
            # Save checkpoint every 1MB
            if bytes_received % (1024 * 1024) == 0:
                checkpoints[filename] = {
                    "bytes_received": bytes_received,
                    "timestamp": datetime.now().isoformat()
                }
                with open(CHECKPOINT_FILE, 'w') as cp_file:
                    json.dump(checkpoints, cp_file)
                
    
    # Print new line after progress bar completes
    print()
    
    # Receive hash of downloaded file
    server_hash = recv_line(sock)

    # Compute local hash
    hasher = hashlib.sha256()
    with open(partial_file, 'rb') as f:
        while chunk := f.read(1024):
            hasher.update(chunk)
    local_hash = hasher.hexdigest()

    if local_hash == server_hash:
        print(f"Downloaded {filename} [Hash verified]")
        log(f"Downloaded '{filename}' ({total_size} bytes) with matching hash.")
        # Remove checkpoint if download completed successfully
        if filename in checkpoints:
            del checkpoints[filename]
            with open(CHECKPOINT_FILE, 'w') as cp_file:
                json.dump(checkpoints, cp_file)
    else:
        print("Hash mismatch after download.")
        log(f"Hash mismatch for '{filename}': local {local_hash}, server {server_hash}")

def main():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        log(f"Connected to server at {HOST}:{PORT}")
    except Exception as e:
        log(f"Connection failed: {e}")
        print("Failed to connect to server.")
        return

    while True:
        cmd = input("Enter command (LIST, UPLOAD x, DOWNLOAD x, EXIT): ").strip()
        if cmd.upper() == "LIST":
            list_files(sock)
        elif cmd.upper().startswith("UPLOAD"):
            try:
                _, path = cmd.split(maxsplit=1)
                upload_file(sock, path)
            except ValueError:
                print("Invalid UPLOAD command format.")
                log("UPLOAD command failed: Invalid format.")
        elif cmd.upper().startswith("DOWNLOAD"):
            parts = cmd.split()
            if len(parts) != 2:
                print("Invalid DOWNLOAD command format. Use: DOWNLOAD filename")
                log("DOWNLOAD command failed: Invalid format.")
            else:
                filename = parts[1]
                download_file(sock, filename)
        elif cmd.upper() == "EXIT":
            log("Client exited session.")
            break
        else:
            print("Unknown command.")
            log(f"Unknown command entered: '{cmd}'")
    sock.close()
    log("Socket closed.")

if __name__ == "__main__":
    main()
