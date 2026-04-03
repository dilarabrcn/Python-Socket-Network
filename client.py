import socket
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import os
import protocol
import time

# --- AYARLAR ---
HOST = '10.134.54.2'
PORT = 12345
CHUNK_SIZE = 65536 

class ChatClient:
    def __init__(self, root):
        self.root = root
        # BAŞLIK GÜNCELLENDİ:
        self.root.title("Bilgisayar Ağlarına Giriş Proje")
        self.sock = None
        self.username = ""
        self.target_user = None
        self.incoming_files = {} 
        self.build_gui()

    def build_gui(self):
        # 1. Giriş Alanı
        frame_top = tk.Frame(self.root)
        frame_top.pack(pady=5, fill=tk.X, padx=5)
        
        tk.Label(frame_top, text="Kullanıcı Adı:").pack(side=tk.LEFT)
        self.entry_user = tk.Entry(frame_top)
        self.entry_user.pack(side=tk.LEFT, padx=5)
        
        self.btn_connect = tk.Button(frame_top, text="Giriş Yap", command=self.connect_to_server)
        self.btn_connect.pack(side=tk.LEFT)
        
        # 2. Ana Alan (Chat ve Liste)
        frame_main = tk.Frame(self.root)
        frame_main.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        self.chat_area = scrolledtext.ScrolledText(frame_main, state='disabled', width=50, height=20)
        self.chat_area.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        frame_right = tk.Frame(frame_main)
        frame_right.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        tk.Label(frame_right, text="Çevrimiçi Kişiler").pack()
        self.listbox = tk.Listbox(frame_right, width=20)
        self.listbox.pack(expand=True, fill=tk.Y)
        self.listbox.bind('<<ListboxSelect>>', self.on_user_select)
        
        # 3. Alt Alan
        frame_bottom = tk.Frame(self.root)
        frame_bottom.pack(fill=tk.X, padx=5, pady=5)
        
        self.lbl_target = tk.Label(frame_bottom, text="Kime: (Seçilmedi)", fg="blue")
        self.lbl_target.pack(anchor="w")
        
        self.entry_msg = tk.Entry(frame_bottom)
        self.entry_msg.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.entry_msg.bind("<Return>", lambda e: self.send_message())
        
        self.btn_send = tk.Button(frame_bottom, text="Mesaj Gönder", command=self.send_message)
        self.btn_send.pack(side=tk.LEFT)
        
        self.btn_file = tk.Button(frame_bottom, text="Dosya Gönder", command=self.offer_file)
        self.btn_file.pack(side=tk.LEFT, padx=5)

    def log(self, message):
        # Arayüz güncellemelerini ana thread'e yönlendiriyoruz
        self.root.after(0, lambda: self._log_impl(message))

    def _log_impl(self, message):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, message + "\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state='disabled')

    def connect_to_server(self):
        user = self.entry_user.get().strip()
        if not user:
            messagebox.showerror("Hata", "Kullanıcı adı boş olamaz!")
            return
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))
            protocol.send_msg(self.sock, {"type": "LOGIN", "username": user})
            
            threading.Thread(target=self.listen_server, daemon=True).start()
            
            self.username = user
            self.btn_connect.config(state='disabled')
            self.entry_user.config(state='disabled')
            self.log(f"--- {HOST}:{PORT} Bağlanıldı ---")
        except Exception as e:
            messagebox.showerror("Bağlantı Hatası", str(e))

    def on_user_select(self, event):
        selection = self.listbox.curselection()
        if selection:
            self.target_user = self.listbox.get(selection[0])
            self.lbl_target.config(text=f"Kime: {self.target_user}")

    # --- LİSTE GÜNCELLEMELERİ İÇİN GÜVENLİ FONKSİYONLAR ---
    def safe_list_insert(self, user):
        self.listbox.insert(tk.END, user)

    def safe_list_delete(self, user):
        try:
            idx = self.listbox.get(0, tk.END).index(user)
            self.listbox.delete(idx)
        except ValueError:
            pass
            
    def safe_list_update(self, users):
        self.listbox.delete(0, tk.END)
        for u in users:
            if u != self.username:
                self.listbox.insert(tk.END, u)

    def listen_server(self):
        while True:
            try:
                msg = protocol.recv_msg(self.sock)
                if not msg:
                    self.log("--- Bağlantı kesildi ---")
                    break
                
                msg_type = msg.get("type")
                
                if msg_type == "USER_LIST":
                    # Thread güvenli güncelleme:
                    self.root.after(0, lambda: self.safe_list_update(msg.get("users")))

                elif msg_type == "USER_JOIN":
                    new_user = msg.get('username')
                    self.log(f"--- {new_user} katıldı ---")
                    if new_user != self.username:
                        # Thread güvenli ekleme:
                        self.root.after(0, lambda: self.safe_list_insert(new_user))
                    
                elif msg_type == "USER_LEAVE":
                    left_user = msg.get('username')
                    self.log(f"--- {left_user} ayrıldı ---")
                    # Thread güvenli silme:
                    self.root.after(0, lambda: self.safe_list_delete(left_user))
                
                elif msg_type == "CHAT_MSG":
                    text = msg.get("text")
                    sender = msg.get("from", "?")
                    self.log(f"[{sender}]: {text}")
                
                elif msg_type == "ERROR":
                    messagebox.showerror("Hata", msg.get("message"))
                
                elif msg_type == "FILE_REQUEST":
                    self.handle_file_request(msg)

                elif msg_type == "FILE_RESPONSE":
                    if msg.get("accept"):
                        self.log("Dosya kabul edildi, gönderiliyor...")
                        threading.Thread(target=self.start_file_transfer, 
                                             args=(msg.get("transfer_id"),)).start()
                    else:
                        self.log("Dosya reddedildi.")

                elif msg_type == "FILE_CHUNK":
                    tid = msg.get("transfer_id")
                    chunk_len = msg.get("chunk_len")
                    raw_data = protocol.recv_raw_data(self.sock, chunk_len)
                    if tid in self.incoming_files and raw_data:
                        self.incoming_files[tid].write(raw_data)

                elif msg_type == "FILE_DONE":
                    tid = msg.get("transfer_id")
                    if tid in self.incoming_files:
                        self.incoming_files[tid].close()
                        del self.incoming_files[tid]
                        self.log(f"Dosya alındı (ID: {tid})")
                        self.root.after(0, lambda: messagebox.showinfo("Tamamlandı", "Dosya transferi bitti."))

            except Exception as e:
                print("Dinleme hatası:", e)
                break

    def handle_file_request(self, msg):
        sender = msg.get("from")
        filename = msg.get("name")
        filesize = msg.get("size")
        transfer_id = f"{sender}_{int(time.time())}"
        
        # Pop-up penceresini ana thread'de açtırıyoruz
        self.root.after(0, lambda: self._show_file_dialog(sender, filename, filesize, transfer_id))

    def _show_file_dialog(self, sender, filename, filesize, transfer_id):
        resp = messagebox.askyesno("Dosya", f"{sender} size '{filename}' ({filesize} b) gönderiyor. Kabul?")
        if resp:
            save_path = filedialog.asksaveasfilename(initialfile=filename)
            if save_path:
                self.incoming_files[transfer_id] = open(save_path, "wb")
                protocol.send_msg(self.sock, {
                    "type": "FILE_RESPONSE",
                    "to": sender,
                    "transfer_id": transfer_id,
                    "accept": True
                })
            else:
                protocol.send_msg(self.sock, {"type": "FILE_RESPONSE", "to": sender, "accept": False})
        else:
            protocol.send_msg(self.sock, {"type": "FILE_RESPONSE", "to": sender, "accept": False})

    def send_message(self):
        text = self.entry_msg.get()
        if not text or not self.target_user:
            return
        
        msg = {
            "type": "CHAT_MSG",
            "from": self.username,
            "to": self.target_user,
            "text": text,
            "timestamp": str(time.time())
        }
        if protocol.send_msg(self.sock, msg):
            self.log(f"[Ben -> {self.target_user}]: {text}")
            self.entry_msg.delete(0, tk.END)

    def offer_file(self):
        if not self.target_user:
            messagebox.showwarning("Uyarı", "Kullanıcı seçin!")
            return
        filepath = filedialog.askopenfilename()
        if not filepath: return
        
        self.current_file_path = filepath
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        
        protocol.send_msg(self.sock, {
            "type": "FILE_OFFER",
            "from": self.username,
            "to": self.target_user,
            "name": filename,
            "size": filesize
        })
        self.log(f"Dosya teklifi gönderildi: {filename}")

    def start_file_transfer(self, transfer_id):
        try:
            with open(self.current_file_path, "rb") as f:
                seq = 0
                while True:
                    bytes_read = f.read(CHUNK_SIZE)
                    if not bytes_read:
                        break
                    protocol.send_file_chunk(
                        self.sock, transfer_id, seq, bytes_read, to_user=self.target_user
                    )
                    seq += 1
            
            protocol.send_msg(self.sock, {
                "type": "FILE_DONE",
                "to": self.target_user,
                "transfer_id": transfer_id
            })
            self.log("Dosya gönderimi bitti.")
        except Exception as e:
            self.log(f"Dosya hatası: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()