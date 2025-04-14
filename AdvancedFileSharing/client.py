import socket
import os
import hashlib
import threading
from datetime import datetime

#server configuration
HOST = 'localhost'
PORT = 5002
DOWNLOAD = 'downloaded'    #directory to save the dowloaded files
LOG_FILE = 'logs/client_log.txt'   #log file for clients


#function to log events with a timestamp
def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

#function to request the files and show the list of them on the server
def list_files(sock):
    sock.send("LIST".encode())   #send the list command to the server
    files = sock.recv(4096).decode()    #receive and decode the file list
    print("Files on Server:\n", files)
    log("Requested list of files from server.")

# function to upload the file to the server
def upload_file(sock, path):
    filename = os.path.basename(path)  #extract filename
    if not os.path.exists(path):    #check if the file exists before you upload
        print("File does not exist.")
        log(f"Upload failed: File '{path}' does not exist.")
        return

    size = os.path.getsize(path)     #get the size of file

    ###Compute SHA-256 hash before sending
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(1024):
            hasher.update(chunk)
    sha256_hash = hasher.hexdigest()

    ### Log the upload details
    print(f"Uploading {filename} with size {size} and calculated hash {sha256_hash}")

    sock.send(f"UPLOAD {filename} {size}".encode()) ###send the upload with name and size command then encode it
   
    ### Wait for server readiness
    if sock.recv(1024) == "READY".encode():
        with open(path, 'rb') as f:
            sock.sendfile(f)
        received_hash = sock.recv(1024).decode() ###Rreceive hash from serever
        ###Wait fo final comfirmation
        if received_hash == sha256_hash:
            print(f"Uploaded {filename} [Hash verified]")
            log(f"Uploaded file '{filename}' ({size} bytes) with hash {sha256_hash}")
        else:
            print(f"Upload failed: Hash mismatch")
            log(f"Hash mismatch detected for file '{filename}'")
        
    else:
        log(f"Upload aborted: Server did not respond with READY for '{filename}'.")

#function to download file from server
def download_file(sock, filename):
    sock.send(f"DOWNLOAD {filename}".encode())  #send the file and encode it
    size_data = sock.recv(1024)   #receive the file size or error
    if size_data == "ERROR".encode():
        print("File not found on server.")
        log(f"Download failed: File '{filename}' not found on server.")
        return

    size = int(size_data.decode())    #parse file size
    sock.send("READY".encode())    #send a signal that shows readiness
    filepath = f"{DOWNLOAD}/{filename}"     #create a file path (local one)
    #receive file in chuks and write to local file
    with open(filepath, 'wb') as f:
        bytes_received = 0
        while bytes_received < size:
            chunk = sock.recv(1024)
            f.write(chunk)
            bytes_received += len(chunk)

    ### Ask server for hash of the downloaded file
    sock.send(f"HASH {filename}".encode())
    server_hash = sock.recv(1024).decode()

    ### Compute local hash
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(1024):
            hasher.update(chunk)
    local_hash = hasher.hexdigest()

    ###Compare client hash computed with the server one just requested before
    if local_hash == server_hash:
        print(f"Downloaded {filename} [Hash verified]")
        log(f"Downloaded '{filename}' ({size} bytes) with matching SHA-256 hash.")
    else:
        print("Download completed, but hash mismatch!")
        log(f"Hash mismatch after downloading '{filename}'.")



def main():
    try:
        #establish TCP connection to server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        log(f"Connected to server at {HOST}:{PORT}")
    except Exception as e:
        log(f"Connection failed: {e}")
        print("Failed to connect to server.")
        return
    #client interaction
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
    #close the socket after exiting the loop
    sock.close()
    log("Socket closed.")

if __name__ == "__main__":
    main()