import socket
import threading
import os
import hashlib
from datetime import datetime

# Server configuration
HOST = 'localhost'
PORT = 5002
UPLOAD = 'uploaded'  # Directory where uploaded files will be saved
LOG_FILE = 'logs/server_log.txt'  # Path to the log file
CHECKPOINT_FILE = 'logs/download_checkpoints.json'  # File to store download progress


os.makedirs("logs", exist_ok=True)
os.makedirs(UPLOAD, exist_ok=True)  # Ensure upload directory exists

# Load existing checkpoints
def load_checkpoints():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}
# Save checkpoints to file
def save_checkpoints(checkpoints):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoints, f)

# Logs a message with timestamp
def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now()}] {msg}\n")

# Helper function to read a line (until newline) from socket
def recv_line(conn):
    buffer = ''
    while True:
        data = conn.recv(1024).decode()
        if not data:
            return None
        buffer += data
        if '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            return line.strip()

# Handles communication with a single client
def handle_client(conn, addr):
    conn.settimeout(30.0)  # 30 second timeout

    log(f"Connected by {addr}")
    checkpoints = load_checkpoints()

    try:
        while True:
            # Read command line until newline
            data = recv_line(conn)
            if data is None:
                break  # Client disconnected

            # Splits the received string into the command vs arguments
            cmd_parts = data.split()
            command = cmd_parts[0]

            # LIST command
            if command == "LIST":
                files = os.listdir(UPLOAD)
                conn.send(('\n'.join(files) + '\n').encode())

            # UPLOAD
            elif command == "UPLOAD":
                filename = cmd_parts[1]
                size = int(cmd_parts[2])  # Expected size
                file_dir = UPLOAD
                original_path = os.path.join(file_dir, filename)

                # Check if file exists
                if os.path.exists(original_path):
                    base, ext = os.path.splitext(filename)
                    archive_dir = os.path.join(file_dir, "VersionHistory")
                    os.makedirs(archive_dir, exist_ok=True)
                    version = 1
                    while os.path.exists(os.path.join(file_dir, f"{base}_v{version}{ext}")):
                        version += 1
                    archived_filename = f"{base}_v{version}{ext}"
                    archive_path = os.path.join(archive_dir, archived_filename)
                    log(f"Archiving existing file: {original_path} -> {archive_path}")
                    os.rename(original_path, archive_path)
                    new_filename = f"{base}_v{version+1}{ext}"
                    file_path = os.path.join(file_dir, new_filename)
                else:
                    file_path = original_path

                # Notify client to start sending file data
                conn.send("READY\n".encode())

                # Receive file in chunks
                with open(file_path, 'wb') as f:
                    bytes_received = 0
                    while bytes_received < size:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)

                # Compute hash of received file
                hasher = hashlib.sha256()
                with open(file_path, 'rb') as f:
                    while chunk := f.read(1024):
                        hasher.update(chunk)
                received_hash = hasher.hexdigest()

                # Send hash back to client
                conn.send((received_hash + '\n').encode())

            # DOWNLOAD
            elif command == "DOWNLOAD":
                filename = cmd_parts[1]
                filepath = os.path.join(UPLOAD, filename)
                if os.path.exists(filepath):
                    size = os.path.getsize(filepath)
                    conn.send(f"{size}\n".encode())
                    
                    # Wait for client to send "READY" or "RESUME"
                    ack = recv_line(conn)
                    if ack.startswith("READY") or ack.startswith("RESUME"):
                        if ack.startswith("RESUME"):
                            # Client wants to resume download
                            bytes_received = int(ack.split()[1])
                            log(f"Resuming download of {filename} from byte {bytes_received}")
                        else:
                            bytes_received = 0
                        
                        with open(filepath, 'rb') as f:
                            f.seek(bytes_received)
                            while True:
                                chunk = f.read(1024)
                                if not chunk:
                                    break
                                conn.send(chunk)
                        
                        # Send hash of the file
                        hasher = hashlib.sha256()
                        with open(filepath, 'rb') as f:
                            while chunk := f.read(1024):
                                hasher.update(chunk)
                        file_hash = hasher.hexdigest()
                        conn.send((file_hash + '\n').encode())
                        log(f"Sent {filename} to {addr} with hash {file_hash}")
                else:
                    conn.send("ERROR\n".encode())

            elif command == "CHECKPOINT":
                # Store download progress
                filename = cmd_parts[1]
                bytes_received = int(cmd_parts[2])
                client_id = f"{addr[0]}:{addr[1]}"
                checkpoints[client_id] = {
                    "filename": filename,
                    "bytes_received": bytes_received,
                    "timestamp": datetime.now().isoformat()
                }
                save_checkpoints(checkpoints)
                conn.send("OK\n".encode())

    except Exception as e:
        log(f"Error with {addr}: {e}")
    finally:
        conn.close()

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8192)  # 8KB send buffer
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)  # 8KB receive buffer
    s.bind((HOST, PORT))
    s.listen()
    print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")

    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr)).start()

if __name__ == "__main__":
    main()