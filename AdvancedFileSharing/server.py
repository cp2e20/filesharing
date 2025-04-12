import socket
import threading
import os
import hashlib
from datetime import datetime

HOST = 'localhost'
PORT = 5002
UPLOAD = 'uploaded'
LOG_FILE = 'logs/server_log.txt'


def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now()}] {msg}\n")

def handle_client(conn, addr):
    log(f"Connected by {addr}")
    try:
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break

            cmd_parts = data.split()
            command = cmd_parts[0]

            if command == "LIST":
                files = os.listdir(UPLOAD)
                conn.send('\n'.join(files).encode())

            elif command == "UPLOAD":
                filename = cmd_parts[1]
                size = int(cmd_parts[2])
                conn.send("READY".encode())


                with open(f"{UPLOAD}/{filename}", 'wb') as f:
                    bytes_received = 0
                    while bytes_received < size:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)

                log(f"Received {filename} from {addr}")

            elif command == "DOWNLOAD":
                filename = cmd_parts[1]
                filepath = f"{UPLOAD}/{filename}"
                if os.path.exists(filepath):
                    size = os.path.getsize(filepath)
                    conn.send(f"{size}".encode())
                    ack = conn.recv(1024)
                    if ack == ("READY".encode()):
                        with open(filepath, 'rb') as f:
                            conn.sendfile(f)
                    log(f"Sent {filename} to {addr}")
                else:
                    conn.send("ERROR".encode())

    except Exception as e:
        log(f"Error with {addr}: {e}")
    finally:
        conn.close()

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr)).start()

if __name__ == "__main__":
    main()
