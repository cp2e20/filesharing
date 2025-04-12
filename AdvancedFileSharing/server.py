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

                conn.send("READY".encode())  # Notify client to start sending file data

                # Open a new file to write the incoming bytes
                with open(f"{UPLOAD}/{filename}", 'wb') as f:
                    bytes_received = 0
                    # Keep receiving chunks until we've read the full file
                    while bytes_received < size:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)

                # Log the upload completion
                log(f"Received {filename} from {addr}")

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
                    log(f"Sent {filename} to {addr}")
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
