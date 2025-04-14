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

os.makedirs("logs", exist_ok=True)
os.makedirs(UPLOAD, exist_ok=True)  # Optionally ensure UPLOAD exists to
# Logs a message with timestamp 
def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now()}] {msg}\n")

# Handles communication with a single client (handler function sent by main to each thread)
def handle_client(conn, addr):
    log(f"Connected by {addr}")
    try:
        while True:
            # Wait for the client to send a command
            data = conn.recv(1024).decode()
            if not data:
                # If no data is received, client disconnects 
                break

            # Splits the received string into the command vs arguments
            cmd_parts = data.split()
            command = cmd_parts[0]

            # LIST command
            if command == "LIST":
                files = os.listdir(UPLOAD)  # Get list of filenames in upload directory
                conn.send('\n'.join(files).encode())  # Send filenames joined by newline

            # UPLOAD 
            elif command == "UPLOAD":
                 filename = cmd_parts[1]  # Get file name from command
                 size = int(cmd_parts[2])  # Get expected file size from command
                 file_dir = UPLOAD  # Upload directory
                 original_path = os.path.join(file_dir, filename)
    
                # Here we check if a file with this name already exists
                 if os.path.exists(original_path):
                     # Now we use the base name and extension for versioning
                    base, ext = os.path.splitext(filename)
                     #  After that wedefine the archive directory for version history
                    archive_dir = os.path.join(file_dir, "VersionHistory")
                    # ensuring whether archive_dir exists
                    os.makedirs(archive_dir, exist_ok=True)
                    # calculating the version number for the archived file
                    version = 1
                    while os.path.exists(os.path.join(file_dir, f"{base}_v{version}{ext}")):
                        version += 1
        
             # Here we archive the existing file with the next available version number
                    archived_filename = f"{base}_v{version}{ext}"
                    archive_path=os.path.join(archive_dir,archived_filename)
                    log(f"Archiving existing file: {original_path} -> {archive_path}")
                    os.rename(original_path, archive_path)
        
             # Now, automatically assign a new name to the incoming file
                #New file’s version is one higher than the archived version
                    new_filename = f"{base}_v{version+1}{ext}"
                    file_path = os.path.join(file_dir, new_filename)
                 else:
        #if no duplicate, save with the original name
                    file_path = original_path

                 conn.send("READY".encode())  # Notify client to start sending file data

    # Open (or create) the target file and write the incoming bytes
                 with open(file_path, 'wb') as f:
                    bytes_received = 0
                    while bytes_received < size:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)
                ###Computing Hash
                 hasher= hashlib.sha256()
                 with open(filepath, 'rb') as f:
                     while chunk := f.read(1024):
                        hasher.update(chunk)
                 received_hash = hasher.hexdigest()

                # Send the calculated hash back to the client for verification
                 conn.send(received_hash.encode())  
                 conn.send("SUCCESS".encode())
                 log(f"Received {filename} from {addr} [Hash OK]") #Log hash success
                


    # Log the upload completion with the new file's path
                 log(f"Received {file_path} from {addr}")

            # DOWNLOAD: client wants to download a file from the server
 # DOWNLOAD: client wants to download a file from the server
            elif command == "DOWNLOAD":
                filename = cmd_parts[1]  # Get requested filename
                filepath = f"{UPLOAD}/{filename}"  # Path to the file on server

                # Check if the file exists before sending
                if os.path.exists(filepath):
                    size = os.path.getsize(filepath)  # Get file size
                    conn.send(f"{size}".encode())  # Send size to client first

                    ack = conn.recv(1024)  # Wait for client to send "READY"
                    if ack == ("READY".encode()):
                        with open(filepath, 'rb') as f:
                            while chunk := f.read(1024):
                                conn.send(chunk)

                        ###Compute the hash of the file being sent
                        hasher = hashlib.sha256()
                        with open(filepath, 'rb') as f:
                            while chunk := f.read(1024):
                                hasher.update(chunk)
                        file_hash = hasher.hexdigest()

                        ### Send the computed hash to the client
                        conn.send(file_hash.encode())
                        log(f"Sent {filename} to {addr} with hash {file_hash}")
                else:
                    # If file not found, notify client 
                    conn.send("ERROR".encode())

    except Exception as e:
        # If any error happens during communication, log it
        log(f"Error with {addr}: {e}")

    finally:
        # close connection after handling the client
        conn.close()


# Main server loop that accepts incoming connections
def main():
    # Create a TCP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))  # Bind to specified host and port
    s.listen()  # Start listening for connections
    print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")

    # For every client that connects,
    # start a new thread that handles communication with that client
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr)).start()

# Start the server
if __name__ == "__main__":
    main()
