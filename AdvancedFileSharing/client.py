import socket
import os
from datetime import datetime

HOST = 'localhost'
PORT = 5002
DOWNLOAD = 'downloaded'
LOG_FILE = 'logs/client_log.txt'



def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

def list_files(sock):
    sock.send("LIST".encode())
    files = sock.recv(4096).decode()
    print("Files on Server:\n", files)
    log("Requested list of files from server.")

def upload_file(sock, path):
    filename = os.path.basename(path)
    if not os.path.exists(path):
        print("File does not exist.")
        log(f"Upload failed: File '{path}' does not exist.")
        return

    size = os.path.getsize(path)
    sock.send(f"UPLOAD {filename} {size}".encode())
    if sock.recv(1024) == b"READY":
        with open(path, 'rb') as f:
            sock.sendfile(f)
        print(f"Uploaded {filename}")
        log(f"Uploaded file '{filename}' ({size} bytes) to server.")
    else:
        log(f"Upload aborted: Server did not respond with READY for '{filename}'.")

def download_file(sock, filename):
    sock.send(f"DOWNLOAD {filename}".encode())
    size_data = sock.recv(1024)
    if size_data == b"ERROR":
        print("File not found on server.")
        log(f"Download failed: File '{filename}' not found on server.")
        return

    size = int(size_data.decode())
    sock.send(b"READY")
    filepath = f"{DOWNLOAD}/{filename}"
    with open(filepath, 'wb') as f:
        bytes_received = 0
        while bytes_received < size:
            chunk = sock.recv(1024)
            f.write(chunk)
            bytes_received += len(chunk)
    print(f"Downloaded {filename}")
    log(f"Downloaded file '{filename}' ({size} bytes) from server.")

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
