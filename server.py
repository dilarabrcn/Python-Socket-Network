import socket
import threading
import protocol

# --- AYARLAR ---
HOST = '10.134.54.2'
PORT = 12345

clients = {} # { "kullanici_adi": socket_objesi }

def broadcast(msg_dict):
    """ Tüm istemcilere mesaj gönderir."""
    # Liste üzerinde dönerken sözlük değişirse hata almamak için 
    # list(clients.values()) yapıyoruz.
    for user_sock in list(clients.values()):
        try:
            protocol.send_msg(user_sock, msg_dict)
        except:
            pass

def broadcast_user_list():
    """ 
    !!! EN ÖNEMLİ KISIM !!!
    Sadece tek bir kişiye değil, HERKESE güncel listeyi gönderir.
    Böylece Ali gelince Ayşe'nin ekranı da güncellenir.
    """
    user_list = list(clients.keys())
    msg = {"type": "USER_LIST", "users": user_list}
    broadcast(msg)

def handle_client(client_socket, addr):
    print(f"[BAĞLANTI] {addr} bağlandı.")
    username = None

    try:
        while True:
            request = protocol.recv_msg(client_socket)
            if not request:
                break

            msg_type = request.get("type")

            # --- LOGIN ---
            if msg_type == "LOGIN":
                requested_user = request.get("username")
                if requested_user in clients:
                    protocol.send_msg(client_socket, {"type": "ERROR", "message": "Bu kullanıcı adı dolu."})
                    return
                
                username = requested_user
                clients[username] = client_socket
                print(f"[GİRİŞ] {username}")
                
                # 1. Herkese "Biri geldi" de (Chat ekranına yazı düşmesi için)
                broadcast({"type": "USER_JOIN", "username": username})
                
                # 2. HERKESE GÜNCEL LİSTEYİ GÖNDER (Sağ taraftaki listeyi güncellemek için)
                broadcast_user_list()

            # --- CHAT_MSG ---
            elif msg_type == "CHAT_MSG":
                target_user = request.get("to")
                if target_user in clients:
                    protocol.send_msg(clients[target_user], request)
                else:
                    protocol.send_msg(client_socket, {"type": "ERROR", "message": "Kullanıcı çevrimdışı."})

            # --- FILE_OFFER ---
            elif msg_type == "FILE_OFFER":
                target_user = request.get("to")
                if target_user in clients:
                    request["type"] = "FILE_REQUEST" 
                    request["from"] = username 
                    protocol.send_msg(clients[target_user], request)
                else:
                    protocol.send_msg(client_socket, {"type": "ERROR", "message": "Kullanıcı çevrimdışı."})

            # --- FILE_RESPONSE ---
            elif msg_type == "FILE_RESPONSE":
                target_user = request.get("to")
                if target_user in clients:
                    protocol.send_msg(clients[target_user], request)

            # --- FILE_CHUNK ---
            elif msg_type == "FILE_CHUNK":
                chunk_len = request.get("chunk_len")
                raw_data = protocol.recv_raw_data(client_socket, chunk_len)
                
                if raw_data:
                    target_user = request.get("to")
                    if target_user in clients:
                        protocol.send_file_chunk(
                            clients[target_user],
                            request.get("transfer_id"),
                            request.get("seq"),
                            raw_data,
                            to_user=target_user
                        )

            # --- FILE_DONE ---
            elif msg_type == "FILE_DONE":
                target_user = request.get("to")
                if target_user in clients:
                    protocol.send_msg(clients[target_user], request)

    except Exception as e:
        print(f"Hata ({addr}): {e}")
    finally:
        if username and username in clients:
            del clients[username]
            print(f"[ÇIKIŞ] {username}")
            
            # Biri çıkınca da:
            # 1. Haber ver
            broadcast({"type": "USER_LEAVE", "username": username})
            # 2. LİSTEYİ HERKES İÇİN GÜNCELLE
            broadcast_user_list()
            
        client_socket.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[SUNUCU] {HOST}:{PORT} çalışıyor...")
    
    while True:
        client_sock, addr = server.accept()
        threading.Thread(target=handle_client, args=(client_sock, addr)).start()

if __name__ == "__main__":
    start_server()