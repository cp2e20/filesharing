import tkinter as tk
from tkinter import filedialog, messagebox
import socket, os, threading, hashlib
from datetime import datetime

HOST = 'localhost'
PORT = 5002
DOWNLOAD = 'downloaded'
LOG_FILE = 'logs/client_log.txt'

os.makedirs(DOWNLOAD, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log(message, gui_log_widget=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")
    if gui_log_widget:
        gui_log_widget.insert(tk.END, f"[{timestamp}] {message}\n")
        gui_log_widget.see(tk.END)

class FileClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File Sharing Client")
        self.root.geometry("500x460")
        self.root.resizable(False, False)
        self.root.configure(bg="#f0f4f7")
        self.sock = None

        #this for the button format
        btn_style = {
            "font": ("Segoe UI", 9, "bold"),
            "fg": "white",
            "relief": "groove",
            "borderwidth": 2,
            "padx": 5,
            "pady": 5,
        }

        
        self.connect_btn = tk.Button(root, text="Connect to server", bg="#28a745", command=self.connect_to_server, **btn_style)
        self.connect_btn.pack(fill="x", padx=20, pady=(10, 2))

    
        frame_top = tk.Frame(root, bg="#f0f4f7")
        frame_top.pack(fill="x", padx=20)
        self.upload_btn = tk.Button(frame_top, text="Upload File", bg="#007bff", state="disabled", command=self.upload_file, **btn_style)
        self.upload_btn.pack(side="left", expand=True, fill="x", padx=2)

        self.download_btn = tk.Button(frame_top, text="Download File", bg="#fd7e14", state="disabled", command=self.download_file, **btn_style)
        self.download_btn.pack(side="right", expand=True, fill="x", padx=2)

        self.progress_label = tk.Label(root, text="Progress:", font=("Segoe UI", 9), bg="#f0f4f7")
        self.progress_label.pack(anchor="w", padx=22)
        self.progress = tk.Scale(root, from_=0, to=100, orient="horizontal", length=450, bg="#f0f4f7", troughcolor="#ccc")
        self.progress.pack(padx=20)

       
        self.file_listbox = tk.Listbox(root, height=8, font=("Segoe UI", 10))
        self.file_listbox.pack(fill="both", padx=20, pady=5)
        self.file_listbox.bind('<Double-1>', self.double_click_download)

        
        self.refresh_btn = tk.Button(root, text="Refresh File List", bg="#ffc107", fg="black", state="disabled",
                                     command=self.list_files, relief="groove", font=("Segoe UI", 9, "bold"))
        self.refresh_btn.pack(fill="x", padx=20, pady=5)

        
        self.log_text = tk.Text(root, height=6, font=("Consolas", 9), bg="white")
        self.log_text.pack(fill="both", padx=20, pady=(0, 10))

    def connect_to_server(self):
        try:
            if self.sock:
                self.sock.close()
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))
            self.upload_btn.config(state="normal")
            self.download_btn.config(state="normal")
            self.refresh_btn.config(state="normal")
            log("Connected to server", self.log_text)
            self.list_files()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            log(f"Connection failed: {e}", self.log_text)

    def recv_line(self):
        buffer = ''
        while True:
            data = self.sock.recv(1024).decode()
            if not data:
                break
            buffer += data
            if '\n' in buffer:
                line, _ = buffer.split('\n', 1)
                return line.strip()
        return buffer.strip()

    def list_files(self):
        try:
            self.sock.send("LIST\n".encode())
            files = self.sock.recv(4096).decode().split('\n')
            self.file_listbox.delete(0, tk.END)
            for f in files:
                if f.strip():
                    self.file_listbox.insert(tk.END, f)
            log("Listed files from server", self.log_text)
        except Exception as e:
            log(f"Failed to list files: {e}", self.log_text)

    def upload_file(self):
        filepath = filedialog.askopenfilename()
        if not filepath:
            return
        threading.Thread(target=self._upload_file_thread, args=(filepath,)).start()

    def _upload_file_thread(self, filepath):
        try:
            filename = os.path.basename(filepath)
            size = os.path.getsize(filepath)
            self.sock.send(f"UPLOAD {filename} {size}\n".encode())
            response = self.recv_line()

            if response == "READY":
                hasher = hashlib.sha256()
                sent = 0
                with open(filepath, 'rb') as f:
                    while chunk := f.read(1024):
                        self.sock.send(chunk)
                        hasher.update(chunk)
                        sent += len(chunk)
                        self.progress.set(int((sent / size) * 100))

                server_hash = self.recv_line()
                if server_hash == hasher.hexdigest():
                    messagebox.showinfo("Success", "Upload complete and verified.")
                    log(f"Uploaded {filename} successfully", self.log_text)
                else:
                    messagebox.showwarning("Warning", "Hash mismatch after upload.")
            else:
                messagebox.showerror("Error", "Server did not respond with READY.")
            self.progress.set(0)
            self.list_files()
        except Exception as e:
            log(f"Upload failed: {e}", self.log_text)
            messagebox.showerror("Upload Error", str(e))

    def download_file(self):
        selected = self.file_listbox.curselection()
        if not selected:
            return
        filename = self.file_listbox.get(selected[0])
        threading.Thread(target=self._download_file_thread, args=(filename,)).start()

    def double_click_download(self, event):
        selection = event.widget.curselection()
        if selection:
            filename = event.widget.get(selection[0])
            threading.Thread(target=self._download_file_thread, args=(filename,)).start()

    def _download_file_thread(self, filename):
        try:
            self.sock.send(f"DOWNLOAD {filename}\n".encode())
            size_data = self.recv_line()
            if size_data == "ERROR":
                messagebox.showerror("Error", "File not found on server.")
                return
            size = int(size_data)
            self.sock.send("READY\n".encode())
            filepath = os.path.join(DOWNLOAD, filename)

            received = 0
            with open(filepath, 'wb') as f:
                while received < size:
                    chunk = self.sock.recv(1024)
                    f.write(chunk)
                    received += len(chunk)
                    self.progress.set(int((received / size) * 100))

            server_hash = self.recv_line()
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                while chunk := f.read(1024):
                    hasher.update(chunk)

            if hasher.hexdigest() == server_hash:
                messagebox.showinfo("Download", f"Download of '{filename}' completed and verified.")
                log(f"Downloaded {filename} successfully", self.log_text)
            else:
                log(f"Hash mismatch after downloading {filename}", self.log_text)
                messagebox.showwarning("Download", "Hash mismatch after download, but file was saved.")
            self.progress.set(0)
        except Exception as e:
            log(f"Download failed: {e}", self.log_text)
            messagebox.showerror("Download Error", str(e))

if __name__== "__main__":
    root = tk.Tk()
    app = FileClientApp(root)
    root.mainloop()