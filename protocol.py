import socket
import struct
import json

"""
 PROJE PROTOKOL MODÜLÜ
-------------------------------------------------
1. Framing (Çerçeveleme): 4 byte header
2. Veri Formatı: JSON
3. Dosya Aktarımı: JSON Header + Raw Binary
"""

# --- YARDIMCI: TCP AKIŞI OKUMA ---
def recv_all(sock, n):
    data = b''
    while len(data) < n:
        try:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        except OSError:
            return None
    return data

# --- TEMEL MESAJ GÖNDERME (JSON) ---
def send_msg(sock, data_dict):
    try:
        msg_json = json.dumps(data_dict)
        msg_bytes = msg_json.encode('utf-8')
        # 4 Byte Big-Endian Uzunluk Bilgisi
        msg_length = struct.pack('>I', len(msg_bytes))
        sock.sendall(msg_length + msg_bytes)
        return True
    except Exception as e:
        print(f"Hata (send_msg): {e}")
        return False

# --- TEMEL MESAJ ALMA (JSON) ---
def recv_msg(sock):
    try:
        raw_msglen = recv_all(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        data = recv_all(sock, msglen)
        if not data:
            return None
        return json.loads(data.decode('utf-8'))
    except Exception as e:
        # Bağlantı koptuğunda sessizce None dönmesi normaldir
        return None

# --- ÖZEL: DOSYA PARÇASI GÖNDERME (FILE_CHUNK) ---
def send_file_chunk(sock, transfer_id, seq, file_data, to_user=None):
    """
    Doküman gereği: JSON başlığının arkasından ham veri gönderilir.
    Güncelleme: 'to_user' eklendi, böylece sunucu kime ileteceğini bilir.
    """
    try:
        chunk_len = len(file_data)
        
        # 1. JSON Başlığını Hazırla
        header_json = {
            "type": "FILE_CHUNK",
            "transfer_id": transfer_id,
            "seq": seq,
            "chunk_len": chunk_len
        }
        # Eğer hedef kullanıcı belliyse (Client -> Server gönderiminde) ekle
        if to_user:
            header_json["to"] = to_user

        # 2. JSON'ı gönder
        if not send_msg(sock, header_json):
            return False
            
        # 3. HEMEN ARKASINDAN ham dosya verisini gönder
        sock.sendall(file_data)
        return True
    except Exception as e:
        print(f"Hata (send_file_chunk): {e}")
        return False

# --- ÖZEL: DOSYA PARÇASI OKUMA ---
def recv_raw_data(sock, length):
    return recv_all(sock, length)