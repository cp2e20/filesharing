import socket
import os
import hashlib
from datetime import datetime

# server configuration
HOST = 'localhost'
PORT = 5002
DOWNLOAD = 'downloaded'  # directory to save downloaded files
LOG_FILE = 'logs/client_log.txt'  # log file for clients

# function to log events
def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

# helper to read a full line ending with '\n'
def recv_line(sock):
    buffer = ''
    while True:
        data = sock.recv(1024).decode()
        if not data:
            break
        buffer += data
        if '\n' in buffer:
            line, _ = buffer.split('\n', 1)
            return line.strip()
    return buffer.strip()

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
    print(f"File size: {size} bytes")  # Debug: check size

    # Compute SHA-256 hash
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(1024):
            hasher.update(chunk)
    sha256_hash = hasher.hexdigest()

    print(f"Uploading {filename} with size {size} and hash {sha256_hash}")

    # Send command with newline
    sock.send(f"UPLOAD {filename} {size}\n".encode())

    # Wait for server's response using recv_line
    response = recv_line(sock)
    if response == "READY":
        # Send file in chunks
        with open(path, 'rb') as f:
            while chunk := f.read(1024):
                sock.send(chunk)

        # Receive hash from server cleanly
        received_hash = recv_line(sock)
        if received_hash == sha256_hash:
            print(f"Uploaded {filename} [Hash verified]")
            log(f"Uploaded file '{filename}' ({size} bytes) with hash {sha256_hash}")
        else:
            print("Hash mismatch after upload.")
            log(f"Hash mismatch for '{filename}'. Client hash: {sha256_hash}, Server hash: {received_hash}")
    else:
        print("Server did not respond with READY.")

# download file
def download_file(sock, filename):
    sock.send(f"DOWNLOAD {filename}\n".encode())
    size_data = recv_line(sock)
    if size_data == "ERROR":
        print("File not found on server.")
        log(f"Download failed: File '{filename}' not found on server.")
        return
    size = int(size_data)
    sock.send("READY\n".encode())
    filepath = os.path.join(DOWNLOAD, filename)
    with open(filepath, 'wb') as f:
        bytes_received = 0
        while bytes_received < size:
            chunk = sock.recv(1024)
            if not chunk:
                break
            f.write(chunk)
            bytes_received += len(chunk)

    # Receive hash of downloaded file
    server_hash = recv_line(sock)

    # Compute local hash
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(1024):
            hasher.update(chunk)
    local_hash = hasher.hexdigest()

    if local_hash == server_hash:
        print(f"Downloaded {filename} [Hash verified]")
        log(f"Downloaded '{filename}' ({size} bytes) with matching hash.")
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
            try:
                _, filename = cmd.split(maxsplit=1)
                download_file(sock, filename)
            except ValueError:
                print("Invalid DOWNLOAD command format.")
                log("DOWNLOAD command failed: Invalid format.")
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
