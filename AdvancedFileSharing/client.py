import socket
import os

HOST = 'localhost'
PORT = 5002
DOWNLOAD_DIR = 'received'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def list_files(sock):
    sock.send(b"LIST")
    files = sock.recv(4096).decode()
    print("Files on Server:\n", files)

def upload_file(sock, path):
    filename = os.path.basename(path)
    size = os.path.getsize(path)
    sock.send(f"UPLOAD {filename} {size}".encode())
    if sock.recv(1024) == b"READY":
        with open(path, 'rb') as f:
            sock.sendfile(f)
        print(f"Uploaded {filename}")

def download_file(sock, filename):
    sock.send(f"DOWNLOAD {filename}".encode())
    size_data = sock.recv(1024)
    if size_data == b"ERROR":
        print("File not found on server.")
        return

    size = int(size_data.decode())
    sock.send(b"READY")
    with open(f"{DOWNLOAD_DIR}/{filename}", 'wb') as f:
        bytes_received = 0
        while bytes_received < size:
            chunk = sock.recv(1024)
            f.write(chunk)
            bytes_received += len(chunk)
    print(f"Downloaded {filename}")

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    
    while True:
        cmd = input("Enter command (LIST, UPLOAD <file>, DOWNLOAD <file>, EXIT): ").strip()
        if cmd.upper() == "LIST":
            list_files(sock)
        elif cmd.upper().startswith("UPLOAD"):
            _, path = cmd.split(maxsplit=1)
            upload_file(sock, path)
        elif cmd.upper().startswith("DOWNLOAD"):
            _, filename = cmd.split(maxsplit=1)
            download_file(sock, filename)
        elif cmd.upper() == "EXIT":
            break
    sock.close()

if __name__ == "__main__":
    main()
