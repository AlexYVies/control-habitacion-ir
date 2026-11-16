# ============================================================
# CONTROL HABITACIÓN: ESP32 + SINRIC PRO (ALEXA ECHO DOT 5)
# Compatible con:
#   - Alexa Echo Dot 5 (Por la nube segura de Sinric Pro)
#   - Servidor Web local en puerto 80
#   - Siri Shortcuts por URLs HTTP
#   - Sony Bravia KDL-42W801A (Wi-Fi + Infrarrojo)
#   - Foco con Ventilador (14 botones Infrarrojo NEC)
# ============================================================
import network
import socket
import ssl
import select
import struct
import json
import os
import time
import gc
import binascii
import hashlib
import machine
from machine import Pin, PWM

# ============================================================
# BUFFER DE REGISTROS (LOGS EN VIVO VISIBLES VÍA WEB)
# ============================================================
LOG_BUFFER = []
MAX_LOGS = 80

def log(msg):
    try:
        t = time.localtime()
        t_str = "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])
    except Exception:
        t_str = ""
    line = f"[{t_str}] {msg}" if t_str else str(msg)
    print(line)
    try:
        LOG_BUFFER.append(line)
        if len(LOG_BUFFER) > MAX_LOGS:
            LOG_BUFFER.pop(0)
    except Exception:
        pass

# ============================================================
# 1. TUS CREDENCIALES DE SINRIC PRO
# ============================================================
APP_KEY    = "e07ada5e-f599-4e81-bd24-bb0044a4085d"
APP_SECRET = "YOUR_APP_SECRET_KEY"

DEVICE_LUZ  = "6ad5b5e973c3542245c11255"
DEVICE_VENT = "6ad5b5a1c3ac0b0a5a074e8f"
DEVICE_TV   = "6ad59dbaefe6033b0530bedd"

# ============================================================
# 2. CONFIGURACIÓN DE TU RED WI-FI
# ============================================================
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASS = "YOUR_WIFI_PASSWORD"

IP_ULTIMO_NUMERO_FIJO = 200
CONFIG_FILE = "wifi_config.json"

# ============================================================
# 3. PINES DE LA ESP32
# ============================================================
PIN_RECEPTOR = 15
PIN_EMISOR   = 4

ir_rx = Pin(PIN_RECEPTOR, Pin.IN, Pin.PULL_UP)
ir_tx = PWM(Pin(PIN_EMISOR), freq=38000, duty=0)

# ============================================================
# 4. CÓDIGOS DE LOS 14 BOTONES DEL FOCO CON VENTILADOR (NEC)
# ============================================================
CODIGOS_FOCO = {
    "luz_on":        0xc5bff00f,  # 1. Encender Luz
    "luz_off":       0xc5bf40bf,  # 2. Apagar Luz
    "brillo_mas":    0xc5bfd52a,  # 3. Aumentar Brillo
    "brillo_menos":  0xc5bf3dc2,  # 4. Disminuir Brillo
    "calidez_mas":   0xc5bff708,  # 5. Aumentar Calidez (Luz más cálida) [CORREGIDO]
    "calidez_menos": 0xc5bf17e8,  # 6. Disminuir Calidez (Luz más fría)  [CORREGIDO]
    "luz_modo":      0xc5bfc837,  # 7. Modo Predefinido

    "vent_vel_1":    0xe15aa857,  # 8. Velocidad 1
    "vent_vel_2":    0xe15a18e7,  # 9. Velocidad 2
    "vent_vel_3":    0xe15a6897,  # 10. Velocidad 3
    "vent_stop":     0xe15aa25d,  # 11. Stop del Ventilador
    "vent_girar":    0xe15ae21d,  # 12. Botón para que gire

    "timer_1h":      0xe15a52ad,  # 13. Temporizador 1 Hora
    "timer_2h":      0xe15ad22d,  # 14. Temporizador 2 Horas
}

# ============================================================
# 5. CÓDIGOS SONY BRAVIA TV (Protocolo SONY SIRC)
# ============================================================
CODIGOS_SONY = {
    "tv_power":    (0xA90, 12),
    "tv_vol_up":   (0x490, 12),
    "tv_vol_down": (0xC90, 12),
    "tv_mute":     (0x290, 12),
    "tv_ch_up":    (0x090, 12),
    "tv_ch_down":  (0x890, 12),
    "tv_input":    (0xA50, 12),
    "tv_up":       (0x2F0, 12),
    "tv_down":     (0xAF0, 12),
    "tv_left":     (0x2D0, 12),
    "tv_right":    (0xCD0, 12),
    "tv_ok":       (0xA70, 12),
    "tv_home":     (0x070, 12),
    "tv_back":     (0x62E9, 15),
}

# Configuración Wi-Fi directa de tu Sony Bravia KDL-42W801A
SONY_TV_IP = "192.168.3.243"
SONY_AUTH_COOKIE = "auth=7eb46bafdf2c24b8dcf7cb8892dfb4ac2fbe3b5999779a0a09f7054f7872b63b"

# ============================================================
# 6. FUNCIONES EMISORAS DE INFRARROJO Y WI-FI
# ============================================================
def _pulso_on(microsegundos):
    ir_tx.duty(512)
    time.sleep_us(microsegundos)
    ir_tx.duty(0)

def enviar_nec(codigo):
    ir_tx.freq(38000)
    _pulso_on(9000)
    time.sleep_us(4500)
    for i in range(31, -1, -1):
        _pulso_on(560)
        if (codigo >> i) & 1:
            time.sleep_us(1690)
        else:
            time.sleep_us(560)
    _pulso_on(560)
    ir_tx.duty(0)

def enviar_sony(codigo, bits=12):
    ir_tx.freq(40000)
    for _ in range(3):
        _pulso_on(2400)
        time.sleep_us(600)
        for i in range(bits - 1, -1, -1):
            if (codigo >> i) & 1:
                _pulso_on(1200)
            else:
                _pulso_on(600)
            time.sleep_us(600)
        time.sleep_ms(25)
    ir_tx.duty(0)

def sony_wifi_api(service, method, params, timeout=0.35):
    try:
        s = socket.socket()
        s.settimeout(timeout)
        s.connect((SONY_TV_IP, 80))
        body = json.dumps({"method": method, "params": params, "id": 1, "version": "1.0"})
        headers = (
            f"POST /sony/{service} HTTP/1.1\r\n"
            f"Host: {SONY_TV_IP}\r\n"
            "Content-Type: application/json\r\n"
            f"Cookie: {SONY_AUTH_COOKIE}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        )
        s.sendall((headers + body).encode("utf-8"))
        s.close()
        return True
    except Exception:
        return False

def sony_wifi_set_volume(vol_num):
    vol_num = max(0, min(int(vol_num), 100))
    log(f"📡 Intentando por Wi-Fi a Sony Bravia: volumen {vol_num}...")
    ok = sony_wifi_api("audio", "setAudioVolume", [{"target": "speaker", "volume": str(vol_num)}], timeout=0.4)
    if ok:
        log(f"✅ Sony Bravia cambió a volumen exacto {vol_num} por Wi-Fi")
        return True
    log("⚠️ Wi-Fi no respondió en TV")
    return False

def ejecutar_comando(cmd, repeticiones=1):
    repeticiones = max(1, min(repeticiones, 30))
    log(f"▶ Ejecutando IR: {cmd} (x{repeticiones} veces)")
    for r in range(repeticiones):
        if cmd in CODIGOS_FOCO:
            codigo = CODIGOS_FOCO[cmd]
            enviar_nec(codigo)
        elif cmd in CODIGOS_SONY:
            codigo, bits = CODIGOS_SONY[cmd]
            enviar_sony(codigo, bits)
        if r < repeticiones - 1:
            time.sleep_ms(150)
    return f"OK: {cmd} (x{repeticiones})"

def ejecutar_tv_hibrido(cmd, param=None, reps=1):
    """Primero intenta por Wi-Fi (rápido 350ms); si no responde o está apagada, usa Infrarrojo al instante."""
    if cmd == "tv_power":
        log("📡 Probando encender/apagar TV por Wi-Fi...")
        ok = False
        try:
            ok = sony_wifi_api("system", "setPowerStatus", [{"status": True if param == "On" else False}], timeout=0.35)
        except Exception:
            ok = False
        if not ok:
            log("🔄 Tele no respondió por Wi-Fi; enviando Infrarrojo (Power)")
            ejecutar_comando("tv_power")
        else:
            log("✅ TV Power cambiado exitosamente por Wi-Fi")
    elif cmd == "tv_vol_up":
        ok = sony_wifi_api("audio", "setAudioVolume", [{"target": "speaker", "volume": "+1"}], timeout=0.35)
        if not ok:
            ejecutar_comando("tv_vol_up", reps)
    elif cmd == "tv_vol_down":
        ok = sony_wifi_api("audio", "setAudioVolume", [{"target": "speaker", "volume": "-1"}], timeout=0.35)
        if not ok:
            ejecutar_comando("tv_vol_down", reps)
    elif cmd == "tv_mute":
        ok = sony_wifi_api("audio", "setAudioMute", [{"status": bool(param)}], timeout=0.35)
        if not ok:
            ejecutar_comando("tv_mute")
    else:
        ejecutar_comando(cmd, reps)

# ============================================================
# 7. CLIENTE SINRIC PRO OFICIAL (WEBSOCKET WSS DIRECTO)
# ============================================================
sinric_ws = None
sinric_conectado = False
ultimo_ping = time.time()

def hmac_sha256(key_str, msg_str):
    k = key_str.encode("utf-8")
    m = msg_str.encode("utf-8")
    block_size = 64
    if len(k) > block_size:
        k = hashlib.sha256(k).digest()
    if len(k) < block_size:
        k = k + b"\x00" * (block_size - len(k))
    o_key_pad = bytearray(b ^ 0x5C for b in k)
    i_key_pad = bytearray(b ^ 0x36 for b in k)
    inner = hashlib.sha256(i_key_pad + m).digest()
    return hashlib.sha256(o_key_pad + inner).digest()

def ws_send_frame(sock, payload_str):
    data = payload_str.encode("utf-8")
    length = len(data)
    # Masking key de 4 bytes
    mask = bytearray(os.urandom(4))
    masked_data = bytearray(length)
    for i in range(length):
        masked_data[i] = data[i] ^ mask[i % 4]

    if length <= 125:
        header = bytearray([0x81, 0x80 | length]) + mask
    elif length <= 65535:
        header = bytearray([0x81, 0x80 | 126]) + struct.pack(">H", length) + mask
    else:
        header = bytearray([0x81, 0x80 | 127]) + struct.pack(">Q", length) + mask

    if hasattr(sock, "sendall"):
        sock.sendall(header + masked_data)
    else:
        sock.write(header + masked_data)

def ws_send_ping(sock):
    mask = bytearray(os.urandom(4))
    header = bytearray([0x89, 0x80]) + mask
    if hasattr(sock, "sendall"):
        sock.sendall(header)
    else:
        sock.write(header)

def ws_send_pong(sock, data=b""):
    length = len(data)
    mask = bytearray(os.urandom(4))
    masked_data = bytearray(length)
    for i in range(length):
        masked_data[i] = data[i] ^ mask[i % 4]
    header = bytearray([0x8A, 0x80 | length]) + mask + masked_data
    if hasattr(sock, "sendall"):
        sock.sendall(header)
    else:
        sock.write(header)

def enviar_heartbeat_sinric():
    """Envía latido de aplicación Sinric Pro cada 30-40s para mantener la sesión viva."""
    global sinric_ws
    if not sinric_ws:
        return
    payload = {
        "action": "heartbeat",
        "cause": {"type": "periodic"},
        "createdAt": get_timestamp(),
        "deviceId": "",
        "replyToken": "",
        "success": True,
        "type": "request",
        "value": {}
    }
    payload_str = json.dumps(payload)
    sig = hmac_sha256(APP_SECRET, payload_str)
    sig_b64 = binascii.b2a_base64(sig).strip().decode("ascii")
    wire_message = '{"header":{"payloadVersion":2,"signatureVersion":1},"payload":' + payload_str + ',"signature":{"HMAC":"' + sig_b64 + '"}}'
    ws_send_frame(sinric_ws, wire_message)

def _leer_exacto(sock, n):
    buf = b""
    while len(buf) < n:
        if hasattr(sock, "recv"):
            c = sock.recv(n - len(buf))
        else:
            c = sock.read(n - len(buf))
        if not c:
            break
        buf += c
    return buf

def ws_read_frame(sock):
    head = _leer_exacto(sock, 2)
    if not head or len(head) < 2:
        return None
    b1, b2 = head[0], head[1]
    opcode = b1 & 0x0F

    # Si es frame de desconexión (0x08)
    if opcode == 0x08:
        return None

    is_masked = (b2 & 0x80) != 0
    plen = b2 & 0x7F

    if plen == 126:
        ext = _leer_exacto(sock, 2)
        if len(ext) < 2:
            return None
        plen = struct.unpack(">H", ext)[0]
    elif plen == 127:
        ext = _leer_exacto(sock, 8)
        if len(ext) < 8:
            return None
        plen = struct.unpack(">Q", ext)[0]

    mask = _leer_exacto(sock, 4) if is_masked else None
    if is_masked and (not mask or len(mask) < 4):
        return None

    data = _leer_exacto(sock, plen)
    if len(data) < plen:
        return None

    if is_masked and mask:
        unmasked = bytearray(len(data))
        for i in range(len(data)):
            unmasked[i] = data[i] ^ mask[i % 4]
        data = unmasked

    # Si el servidor Sinric nos manda un Ping (0x09), le contestamos Pong (0x0A)
    if opcode == 0x09:
        try:
            ws_send_pong(sock, data)
        except Exception:
            pass
        return ""

    # Si el servidor responde un Pong
    if opcode == 0x0A:
        return ""

    return data.decode("utf-8", "ignore")

sinric_ts_offset = 0
sinric_ts_sync_ticks = 0

def set_timestamp(ts):
    global sinric_ts_offset, sinric_ts_sync_ticks
    sinric_ts_offset = int(ts)
    try:
        sinric_ts_sync_ticks = time.ticks_ms()
    except Exception:
        sinric_ts_sync_ticks = int(time.time() * 1000)

def get_timestamp():
    global sinric_ts_offset, sinric_ts_sync_ticks
    if sinric_ts_offset > 0:
        try:
            diff_ms = time.ticks_diff(time.ticks_ms(), sinric_ts_sync_ticks)
            return sinric_ts_offset + (diff_ms // 1000)
        except Exception:
            return sinric_ts_offset + int(time.time())
    return int(time.time())

def conectar_sinric_pro():
    global sinric_ws, sinric_conectado
    log("🔵 Conectando con servidor de Alexa (Sinric Pro)...")
    gc.collect()
    try:
        if sinric_ws:
            try:
                sinric_ws.close()
            except Exception:
                pass
            sinric_ws = None
            sinric_conectado = False

        ai = socket.getaddrinfo("ws.sinric.pro", 80)[0][-1]
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(6.0)
        s.connect(ai)
        ws = s

        # Generar llave de apretón de manos WebSocket
        ws_key = binascii.b2a_base64(os.urandom(16)).strip().decode("ascii")
        dev_ids_str = f"{DEVICE_LUZ};{DEVICE_VENT};{DEVICE_TV}"
        handshake = (
            "GET / HTTP/1.1\r\n"
            "Host: ws.sinric.pro\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"appkey: {APP_KEY}\r\n"
            f"deviceids: {dev_ids_str}\r\n"
            "platform: ESP32\r\n"
            "restoredevicestates: false\r\n"
            "\r\n"
        )
        ws.send(handshake.encode("ascii"))

        # Leer encabezados HTTP 101 exactamente hasta \r\n\r\n sin consumir bytes extra
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = ws.recv(1)
            if not chunk:
                break
            buf += chunk
        resp = buf.decode("utf-8", "ignore")
        if "101" not in resp:
            log("❌ Error en handshake Sinric: " + resp[:60])
            ws.close()
            return None

        # Leer frame de saludo del servidor con el timestamp
        saludo = ws_read_frame(ws)
        if not saludo or "timestamp" not in saludo:
            log("❌ No se recibió timestamp de Sinric")
            ws.close()
            return None

        ts = json.loads(saludo)["timestamp"]
        set_timestamp(ts)

        # Firmar con HMAC-SHA256 usando tu APP_SECRET
        sig = hmac_sha256(APP_SECRET, str(ts))
        sig_b64 = binascii.b2a_base64(sig).strip().decode("ascii")

        # Enviar firma de autenticación (el servidor no envía ACK, queda en escucha)
        auth_msg = json.dumps({"signature": sig_b64})
        ws_send_frame(ws, auth_msg)

        log("✅ ¡CONECTADO EXITOSAMENTE A ALEXA / SINRIC PRO!")
        sinric_ws = ws
        sinric_conectado = True
        return ws
    except Exception as e:
        log("⚠️ Aviso conexión Sinric: " + str(e))
        sinric_ws = None
        sinric_conectado = False
        return None

def enviar_respuesta_sinric(request_payload, value_dict):
    """Envía confirmación instantánea a los servidores de Alexa (<15ms) para evitar 'no responde'."""
    global sinric_ws
    if not sinric_ws:
        return
    try:
        action = request_payload.get("action", "")
        client_id = request_payload.get("clientId", "alexa")
        dev_id = request_payload.get("deviceId", "")
        reply_token = request_payload.get("replyToken", "")

        payload = {
            "action": action,
            "clientId": client_id,
            "createdAt": get_timestamp(),
            "deviceId": dev_id,
            "message": "OK",
            "replyToken": reply_token,
            "success": True,
            "type": "response",
            "value": value_dict
        }
        if "instanceId" in request_payload:
            payload["instanceId"] = request_payload["instanceId"]

        # Serializar payload exactamente y firmarlo
        payload_str = json.dumps(payload)
        sig = hmac_sha256(APP_SECRET, payload_str)
        sig_b64 = binascii.b2a_base64(sig).strip().decode("ascii")

        wire_message = '{"header":{"payloadVersion":2,"signatureVersion":1},"payload":' + payload_str + ',"signature":{"HMAC":"' + sig_b64 + '"}}'
        ws_send_frame(sinric_ws, wire_message)
        log(f"⚡ Confirmación enviada a Alexa en <15ms para: {action}")
    except Exception as e:
        log("❌ Error enviando respuesta a Sinric: " + str(e))

def procesar_mensaje_sinric(raw_json):
    try:
        msg = json.loads(raw_json)
        msg_type = msg.get("payload", {}).get("type") or msg.get("type", "")

        if msg_type == "response":
            p = msg.get("payload", {})
            return

        payload = msg.get("payload", {})
        action      = payload.get("action")
        dev_id      = payload.get("deviceId")
        reply_token = payload.get("replyToken", "")
        value       = payload.get("value", {})

        log(f"🗣️ Comando Alexa: Acción={action} | Dispositivo={dev_id} | Valor={value}")

        # ========================================================
        # 1. ENCENDER / APAGAR (setPowerState)
        # ========================================================
        if action == "setPowerState":
            state = value.get("state", "On") # "On" o "Off"
            # Responder de inmediato a Alexa
            enviar_respuesta_sinric(payload, {"state": state})

            # Ejecutar físicamente
            if dev_id == DEVICE_LUZ:
                ejecutar_comando("luz_on" if state == "On" else "luz_off")
            elif dev_id == DEVICE_VENT:
                ejecutar_comando("vent_vel_2" if state == "On" else "vent_stop")
            elif dev_id == DEVICE_TV:
                ejecutar_tv_hibrido("tv_power", param=state)

        # ========================================================
        # 2. VELOCIDAD FIJA DE VENTILADOR (setRangeValue: 1, 2, 3, 4=Giro)
        # ========================================================
        elif action == "setRangeValue":
            range_val = value.get("rangeValue", 2)
            enviar_respuesta_sinric(payload, {"rangeValue": range_val})

            if dev_id == DEVICE_VENT:
                if range_val == 0:
                    ejecutar_comando("vent_stop")
                elif range_val == 4:
                    log("🌀 Activando giro / oscilación del ventilador (Vía velocidad 4 / Rutina)")
                    ejecutar_comando("vent_girar")
                elif range_val == 1 or (1 <= range_val <= 33):
                    ejecutar_comando("vent_vel_1")
                elif range_val == 2 or (34 <= range_val <= 66):
                    ejecutar_comando("vent_vel_2")
                elif range_val == 3 or (67 <= range_val <= 100):
                    ejecutar_comando("vent_vel_3")
                else:
                    ejecutar_comando("vent_vel_2")

        # ========================================================
        # 3. SUBIR / BAJAR VELOCIDAD (adjustRangeValue)
        # ========================================================
        elif action == "adjustRangeValue":
            delta = value.get("rangeValueDelta", 1)
            enviar_respuesta_sinric(payload, {"rangeValue": 2})

            if dev_id == DEVICE_VENT:
                if delta > 0:
                    ejecutar_comando("vent_vel_3")
                else:
                    ejecutar_comando("vent_vel_1")

        # ========================================================
        # 4. GIRAR / OSCILAR VENTILADOR (setMode o setToggleState)
        # ========================================================
        elif action in ["setMode", "setToggleState"]:
            enviar_respuesta_sinric(payload, value)
            if dev_id == DEVICE_VENT:
                log("🌀 Activando giro / oscilación del ventilador")
                ejecutar_comando("vent_girar")

        # ========================================================
        # 5. BRILLO FIJO (setBrightness) o VOLUMEN EXACTO (setVolume)
        # ========================================================
        elif action in ["setBrightness", "setVolume"]:
            if action == "setVolume" and dev_id == DEVICE_TV:
                vol = value.get("volume", 15)
                enviar_respuesta_sinric(payload, {"volume": vol})
                sony_wifi_set_volume(vol)
            elif action == "setBrightness" and dev_id == DEVICE_LUZ:
                b = value.get("brightness", 50)
                enviar_respuesta_sinric(payload, {"brightness": b})
                if b <= 25:
                    ejecutar_comando("brillo_menos", 5) # Mínimo
                elif b <= 60:
                    ejecutar_comando("brillo_menos", 2) # Mitad
                else:
                    ejecutar_comando("brillo_mas", 5)   # Máximo
            else:
                enviar_respuesta_sinric(payload, value)

        # ========================================================
        # 6. AJUSTAR BRILLO RELATIVO (adjustBrightness)
        # ========================================================
        elif action == "adjustBrightness":
            delta = value.get("brightnessDelta", 10)
            enviar_respuesta_sinric(payload, {"brightness": 50})
            if dev_id == DEVICE_LUZ:
                if delta > 0:
                    ejecutar_comando("brillo_mas", 3)
                else:
                    ejecutar_comando("brillo_menos", 3)

        # ========================================================
        # 7. TEMPERATURA DE COLOR / CALIDEZ
        # ========================================================
        elif action in ["setColorTemperature", "increaseColorTemperature", "decreaseColorTemperature"]:
            if action == "decreaseColorTemperature": # Más cálida
                enviar_respuesta_sinric(payload, {"colorTemperature": 2700})
                ejecutar_comando("calidez_mas", 4)
            elif action == "increaseColorTemperature": # Más fría
                enviar_respuesta_sinric(payload, {"colorTemperature": 6500})
                ejecutar_comando("calidez_menos", 4)
            else:
                temp = value.get("colorTemperature", 4000)
                enviar_respuesta_sinric(payload, {"colorTemperature": temp})
                if temp <= 3000:   # Luz cálida (amarilla)
                    ejecutar_comando("calidez_mas", 5)
                elif temp <= 4500: # Luz intermedia
                    ejecutar_comando("calidez_mas", 2)
                else:              # Luz fría (blanca)
                    ejecutar_comando("calidez_menos", 5)

        # ========================================================
        # 8. SUBIR / BAJAR VOLUMEN TV (adjustVolume)
        # ========================================================
        elif action == "adjustVolume":
            steps = value.get("volumeSteps", 1)
            enviar_respuesta_sinric(payload, {"volume": 20})
            if dev_id == DEVICE_TV:
                if steps > 0:
                    ejecutar_tv_hibrido("tv_vol_up", reps=abs(steps))
                else:
                    ejecutar_tv_hibrido("tv_vol_down", reps=abs(steps))

        # ========================================================
        # 9. SILENCIAR TV (setMute)
        # ========================================================
        elif action == "setMute":
            mute = value.get("mute", True)
            enviar_respuesta_sinric(payload, {"mute": mute})
            if dev_id == DEVICE_TV:
                ejecutar_tv_hibrido("tv_mute", param=mute)

        # ========================================================
        # 10. REPRODUCCIÓN / PAUSA TV (mediaControl)
        # ========================================================
        elif action == "mediaControl":
            ctrl = value.get("control", "Play")
            enviar_respuesta_sinric(payload, {"control": ctrl})
            if dev_id == DEVICE_TV:
                ejecutar_comando("tv_ok")

        # ========================================================
        # 11. CAMBIAR ENTRADA TV (selectInput)
        # ========================================================
        elif action == "selectInput":
            inp = value.get("input", "HDMI")
            enviar_respuesta_sinric(payload, {"input": inp})
            if dev_id == DEVICE_TV:
                ejecutar_comando("tv_input")

        # ========================================================
        # 12. FALLBACK PARA OTRAS ACCIONES
        # ========================================================
        else:
            enviar_respuesta_sinric(payload, value)

    except Exception as e:
        log("❌ Error procesando mensaje Sinric: " + str(e))

# ============================================================
# 8. PÁGINA WEB INTEGRADA
# ============================================================
HTML_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>Control Habitación - ESP32</title>
  <style>
    :root {
      --bg: #0f172a; --card: #1e293b; --card-border: #334155;
      --text: #f8fafc; --muted: #94a3b8;
      --amber: #f59e0b; --amber-glow: rgba(245, 158, 11, 0.22);
      --cyan: #06b6d4; --cyan-glow: rgba(6, 182, 212, 0.22);
      --red: #ef4444; --red-glow: rgba(239, 68, 68, 0.22);
      --green: #10b981; --green-glow: rgba(16, 185, 129, 0.22);
      --indigo: #6366f1; --btn-bg: #273549; --btn-hover: #334155;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; -webkit-tap-highlight-color: transparent; user-select: none; }
    body { background: radial-gradient(circle at top, #1e293b 0%, var(--bg) 70%); color: var(--text); min-height: 100vh; padding: 18px 14px 40px; }
    .container { max-width: 860px; margin: 0 auto; }
    header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; padding: 14px 18px; background: rgba(30, 41, 59, 0.75); border: 1px solid var(--card-border); border-radius: 18px; flex-wrap: wrap; gap: 10px; }
    .title-group h1 { font-size: 1.2rem; font-weight: 700; }
    .title-group p { font-size: 0.78rem; color: var(--muted); margin-top: 2px; }
    .status-badge { display: flex; align-items: center; gap: 8px; font-size: 0.78rem; background: rgba(16, 185, 129, 0.14); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); padding: 6px 12px; border-radius: 999px; font-weight: 600; }
    .dot { width: 8px; height: 8px; background: var(--green); border-radius: 50%; box-shadow: 0 0 8px var(--green); }
    .grid-main { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 18px; }
    .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 22px; padding: 20px; box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35); }
    .card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.07); }
    .card-title { display: flex; align-items: center; gap: 10px; font-size: 1.05rem; font-weight: 700; }
    .tag { font-size: 0.72rem; padding: 4px 9px; border-radius: 8px; background: rgba(255, 255, 255, 0.06); color: var(--muted); }
    .section-label { font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin: 14px 0 8px; font-weight: 600; }
    .btn-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .btn-grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
    .btn-full { width: 100%; margin-top: 10px; }
    button { border: 1px solid rgba(255, 255, 255, 0.08); background: var(--btn-bg); color: var(--text); padding: 13px 10px; border-radius: 14px; font-size: 0.88rem; font-weight: 600; cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; transition: transform 0.1s ease, background 0.15s ease; }
    button:hover { background: var(--btn-hover); }
    button:active { transform: scale(0.95); }
    button .icon { font-size: 1.25rem; line-height: 1; }
    button .sub { font-size: 0.7rem; color: var(--muted); font-weight: 500; }
    .btn-on { background: var(--green-glow); border-color: rgba(16, 185, 129, 0.45); color: #a7f3d0; }
    .btn-amber { background: var(--amber-glow); border-color: rgba(245, 158, 11, 0.45); color: #fde68a; }
    .btn-cyan { background: var(--cyan-glow); border-color: rgba(6, 182, 212, 0.45); color: #a5f3fc; }
    .btn-power { background: var(--red-glow); border-color: rgba(239, 68, 68, 0.45); color: #fecaca; }
    .btn-indigo { background: rgba(99, 102, 241, 0.2); border-color: rgba(99, 102, 241, 0.45); color: #c7d2fe; }
    .dpad-wrapper { display: grid; grid-template-columns: repeat(3, 68px); grid-template-rows: repeat(3, 56px); gap: 8px; justify-content: center; margin: 14px 0; }
    .dpad-btn { padding: 0; border-radius: 14px; font-size: 1.05rem; }
    .dpad-ok { background: var(--indigo); border-color: #818cf8; color: white; font-weight: 700; border-radius: 50%; }
    .rocker-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 12px; }
    .rocker { background: rgba(15, 23, 42, 0.6); border: 1px solid var(--card-border); border-radius: 16px; padding: 8px; display: flex; flex-direction: column; gap: 8px; align-items: center; }
    .rocker span { font-size: 0.72rem; color: var(--muted); font-weight: 700; }
    .rocker button { width: 100%; padding: 11px 0; }
    .voice-box { margin-top: 18px; background: var(--card); border: 1px solid var(--card-border); border-radius: 18px; padding: 16px; font-size: 0.82rem; line-height: 1.55; color: var(--muted); }
    .voice-box strong { color: var(--text); }
    .voice-box code { color: #38bdf8; user-select: all; }
    .toast { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%) translateY(80px); background: #0f172a; border: 1px solid #38bdf8; color: #e0f2fe; padding: 10px 18px; border-radius: 999px; font-size: 0.85rem; font-weight: 600; transition: transform 0.25s ease; z-index: 999; }
    .toast.show { transform: translateX(-50%) translateY(0); }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>🏠 Control de Habitación</h1>
        <p>Alexa Echo Dot 5 + Web + Infrarrojo + Wi-Fi</p>
      </div>
      <div class="status-badge"><span class="dot"></span><span>Alexa Activa</span></div>
    </header>

    <div class="grid-main">
      <!-- TARJETA 1: FOCO CON VENTILADOR (14 BOTONES) -->
      <section class="card">
        <div class="card-header">
          <div class="card-title"><span>💡🌀</span><span>Foco con Ventilador</span></div>
          <span class="tag">14 Botones IR</span>
        </div>

        <div class="section-label">Encendido de Luz</div>
        <div class="btn-grid-2">
          <button class="btn-on" onclick="sendCmd('luz_on', 'Encender Luz')"><span class="icon">💡</span><span>Encender Luz</span></button>
          <button class="btn-power" onclick="sendCmd('luz_off', 'Apagar Luz')"><span class="icon">🌑</span><span>Apagar Luz</span></button>
        </div>

        <div class="section-label">Brillo y Calidez (Mantén para repetir)</div>
        <div class="btn-grid-2">
          <button onpointerdown="startHold('brillo_mas', 'Brillo +')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;"><span class="icon">🔆</span><span>Brillo +</span></button>
          <button onpointerdown="startHold('brillo_menos', 'Brillo -')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;"><span class="icon">🔅</span><span>Brillo -</span></button>
          <button class="btn-amber" onpointerdown="startHold('calidez_mas', 'Calidez +')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;"><span class="icon">🔥</span><span>Calidez +</span></button>
          <button class="btn-cyan" onpointerdown="startHold('calidez_menos', 'Calidez -')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;"><span class="icon">❄️</span><span>Calidez -</span></button>
        </div>

        <button class="btn-indigo btn-full" onclick="sendCmd('luz_modo', 'Modo Predefinido')">
          <div>🎨 <strong>Modo Predefinido</strong></div>
          <span class="sub">Fría Máx ➔ Cálida Máx ➔ Intermedia Máx ➔ Fría Mín</span>
        </button>

        <div class="section-label">Ventilador (Presiona velocidad para iniciar)</div>
        <div class="btn-grid-3">
          <button class="btn-cyan" onclick="sendCmd('vent_vel_1', 'Velocidad 1')"><span class="icon">💨</span><span>Vel 1</span></button>
          <button class="btn-cyan" onclick="sendCmd('vent_vel_2', 'Velocidad 2')"><span class="icon">💨💨</span><span>Vel 2</span></button>
          <button class="btn-cyan" onclick="sendCmd('vent_vel_3', 'Velocidad 3')"><span class="icon">🌪️</span><span>Vel 3</span></button>
        </div>

        <div class="btn-grid-2" style="margin-top: 10px;">
          <button class="btn-power" onclick="sendCmd('vent_stop', 'Stop Ventilador')"><span class="icon">🛑</span><span>Stop Ventilador</span></button>
          <button class="btn-indigo" onclick="sendCmd('vent_girar', 'Girar / Oscilar')"><span class="icon">🔄</span><span>Girar</span></button>
        </div>

        <div class="section-label">Temporizador</div>
        <div class="btn-grid-2">
          <button onclick="sendCmd('timer_1h', 'Temporizador 1 Hora')"><span class="icon">⏱️</span><span>Timer 1 Hora</span></button>
          <button onclick="sendCmd('timer_2h', 'Temporizador 2 Horas')"><span class="icon">⏲️</span><span>Timer 2 Horas</span></button>
        </div>
      </section>

      <!-- TARJETA 2: SONY BRAVIA TV -->
      <section class="card">
        <div class="card-header">
          <div class="card-title"><span>📺</span><span>Sony Bravia TV</span></div>
          <span class="tag">IR + Wi-Fi</span>
        </div>

        <div class="btn-grid-3">
          <button class="btn-power" onclick="sendCmd('tv_power', 'TV Power')"><span class="icon">⏻</span><span>Power</span></button>
          <button onclick="sendCmd('tv_input', 'Input / HDMI')"><span class="icon">🔌</span><span>Input</span></button>
          <button class="btn-indigo" onclick="sendCmd('tv_home', 'Home')"><span class="icon">🏠</span><span>Home</span></button>
        </div>

        <div class="dpad-wrapper">
          <div></div>
          <button class="dpad-btn" onpointerdown="startHold('tv_up', 'Arriba')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;">▲</button>
          <div></div>
          <button class="dpad-btn" onpointerdown="startHold('tv_left', 'Izquierda')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;">◀</button>
          <button class="dpad-btn dpad-ok" onclick="sendCmd('tv_ok', 'OK')">OK</button>
          <button class="dpad-btn" onpointerdown="startHold('tv_right', 'Derecha')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;">▶</button>
          <div></div>
          <button class="dpad-btn" onpointerdown="startHold('tv_down', 'Abajo')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;">▼</button>
          <div></div>
        </div>

        <div class="btn-grid-2">
          <button onclick="sendCmd('tv_back', 'Regresar')">↩ Back</button>
          <button onclick="sendCmd('tv_mute', 'Mute')">🔇 Mute</button>
        </div>

        <div class="rocker-row">
          <div class="rocker">
            <button onpointerdown="startHold('tv_vol_up', 'Volumen +')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;">➕</button>
            <span>VOL</span>
            <button onpointerdown="startHold('tv_vol_down', 'Volumen -')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;">➖</button>
          </div>
          <div class="rocker" style="justify-content:center;">
            <span style="text-align:center;">SONY<br>BRAVIA</span>
          </div>
          <div class="rocker">
            <button onpointerdown="startHold('tv_ch_up', 'Canal +')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;">➕</button>
            <span>CANAL</span>
            <button onpointerdown="startHold('tv_ch_down', 'Canal -')" onpointerup="stopHold()" onpointerleave="stopHold()" oncontextmenu="return false;">➖</button>
          </div>
        </div>
      </section>
    </div>

    <div class="voice-box">
      <strong>🔵 Comandos de Voz con tu Echo Dot 5:</strong><br/>
      • <em>"Alexa, enciende la luz"</em> / <em>"apaga la luz"</em><br/>
      • <em>"Alexa, enciende el ventilador"</em> / <em>"apaga el ventilador"</em><br/>
      • <em>"Alexa, enciende la tele"</em> / <em>"apaga la tele"</em><br/>
      • <em>"Alexa, pon el volumen de la tele en 30"</em> (o sube/baja volumen)
    </div>

    <!-- TARJETA 3: LOGS EN VIVO -->
    <div class="card" style="margin-top: 18px;">
      <div class="card-header" style="margin-bottom: 8px;">
        <div class="card-title"><span>📋</span><span>Consola / Registro en Vivo (Logs)</span></div>
        <button onclick="fetchLogs()" style="padding: 6px 12px; font-size: 0.78rem; border-radius: 8px; flex-direction: row; gap: 6px;">🔄 Refrescar</button>
      </div>
      <div id="logBox" style="background: #090d16; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px; font-family: monospace; font-size: 0.75rem; color: #38bdf8; max-height: 200px; overflow-y: auto; white-space: pre-wrap; user-select: text;">Cargando registros...</div>
    </div>

    <!-- TARJETA 4: ACTUALIZACIÓN REMOTA (OTA) -->
    <div class="card" style="margin-top: 18px; text-align: center;">
      <div class="card-header" style="margin-bottom: 8px;">
        <div class="card-title"><span>⚡</span><span>Actualización por Wi-Fi (Sin Cables)</span></div>
      </div>
      <p style="font-size: 0.78rem; color: var(--muted); margin-bottom: 12px;">Sube una nueva versión de main.py directamente desde tu celular o computadora sin desconectarla de la pared.</p>
      <div style="display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;">
        <input type="file" id="otaFile" accept=".py" style="display: none;" onchange="subirOTA(this)">
        <button onclick="document.getElementById('otaFile').click()" style="padding: 10px 18px; background: #0284c7; flex-direction: row; gap: 8px; font-size: 0.82rem;">
          <span>📤</span><span>Elegir main.py y Actualizar</span>
        </button>
        <button onclick="reiniciarESP()" style="padding: 10px 14px; background: #dc2626; flex-direction: row; gap: 6px; font-size: 0.82rem;">
          <span>🔄</span><span>Reiniciar ESP32</span>
        </button>
      </div>
      <div id="otaStatus" style="margin-top: 10px; font-size: 0.78rem; color: #38bdf8;"></div>
    </div>
  </div>

  <div id="toast" class="toast">Comando enviado</div>

  <script>
    let toastTimer;
    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
    }

    let holdDelay = null;
    let holdInterval = null;

    function startHold(cmd, label) {
      sendCmd(cmd, label);
      stopHold();
      holdDelay = setTimeout(() => {
        holdInterval = setInterval(() => {
          sendCmd(cmd, label, true);
        }, 180);
      }, 350);
    }

    function stopHold() {
      clearTimeout(holdDelay);
      clearInterval(holdInterval);
      holdDelay = null;
      holdInterval = null;
    }

    async function sendCmd(cmd, label, silent = false) {
      if (navigator.vibrate) navigator.vibrate(25);
      if (!silent) showToast('📡 Enviando: ' + label);
      try {
        const res = await fetch('/cmd?c=' + encodeURIComponent(cmd));
        const txt = await res.text();
        if (!silent) showToast('✅ ' + txt);
      } catch (e) {
        if (!silent) showToast('❌ Error de conexión con ESP32');
      }
    }

    async function fetchLogs() {
      try {
        const res = await fetch('/logs');
        const txt = await res.text();
        const box = document.getElementById('logBox');
        if (box) {
          box.textContent = txt || "Sin registros aún.";
          box.scrollTop = box.scrollHeight;
        }
      } catch (e) {}
    }
    fetchLogs();
    setInterval(fetchLogs, 4000);

    async function subirOTA(input) {
      const file = input.files[0];
      if (!file) return;
      if (!confirm('¿Deseas enviar "' + file.name + '" a la ESP32 y reiniciarla?')) {
        input.value = '';
        return;
      }
      const st = document.getElementById('otaStatus');
      st.textContent = '⏳ Subiendo ' + file.name + ' (' + file.size + ' bytes)...';
      showToast('⏳ Subiendo actualización...');
      try {
        const res = await fetch('/upload', {
          method: 'POST',
          body: file
        });
        const txt = await res.text();
        st.textContent = '✅ ' + txt + ' Reiniciando en 5s...';
        showToast('✅ Actualizado. Reiniciando...');
        setTimeout(() => { location.reload(); }, 6000);
      } catch (e) {
        st.textContent = '❌ Error subiendo: ' + e;
        showToast('❌ Error en actualización');
      }
      input.value = '';
    }

    async function reiniciarESP() {
      if (!confirm('¿Seguro que deseas reiniciar la ESP32?')) return;
      showToast('🔄 Reiniciando ESP32...');
      try {
        await fetch('/cmd?c=reboot');
      } catch (e) {}
      setTimeout(() => { location.reload(); }, 4000);
    }
  </script>
</body>
</html>
"""

# ============================================================
# PÁGINA INDEPENDIENTE DE ACTUALIZACIÓN REMOTA (OTA)
# ============================================================
OTA_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Actualizar ESP32 por Wi-Fi</title>
  <style>
    body { background: #0f172a; color: #f8fafc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 14px; }
    .card { background: #1e293b; padding: 24px; border-radius: 20px; max-width: 400px; width: 100%; border: 1px solid #334155; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    h2 { font-size: 1.25rem; margin-bottom: 8px; color: #38bdf8; }
    p { font-size: 0.85rem; color: #94a3b8; line-height: 1.4; margin-bottom: 20px; }
    input[type=file] { display: block; width: 100%; font-size: 0.85rem; margin-bottom: 16px; color: #cbd5e1; }
    button { background: #0284c7; color: #fff; border: none; padding: 12px 18px; border-radius: 12px; font-weight: 700; width: 100%; cursor: pointer; font-size: 0.95rem; }
    button:disabled { opacity: 0.5; }
    #msg { margin-top: 16px; font-size: 0.85rem; font-weight: 600; min-height: 24px; }
    .back { display: inline-block; margin-top: 18px; font-size: 0.8rem; color: #94a3b8; text-decoration: none; }
  </style>
</head>
<body>
<div class="card">
  <h2>⚡ Actualizar Código por Wi-Fi</h2>
  <p>Elige tu archivo <strong>main.py</strong> de tu computadora o celular para actualizar la ESP32 sin necesidad de cables USB.</p>
  <input type="file" id="f" accept=".py">
  <button id="btn" onclick="subir()">📤 Subir y Reiniciar</button>
  <div id="msg"></div>
  <a href="/" class="back">← Volver al Control Remoto</a>
</div>
<script>
async function subir() {
  const file = document.getElementById('f').files[0];
  if (!file) { alert('Selecciona el archivo main.py primero'); return; }
  const btn = document.getElementById('btn');
  const msg = document.getElementById('msg');
  btn.disabled = true;
  msg.style.color = '#38bdf8';
  msg.textContent = '⏳ Enviando ' + file.name + ' (' + file.size + ' bytes)...';
  try {
    const res = await fetch('/upload', { method: 'POST', body: file });
    const txt = await res.text();
    msg.style.color = '#34d399';
    msg.textContent = '✅ ' + txt + ' Espera 6 segundos...';
    setTimeout(() => { window.location.href = '/'; }, 6500);
  } catch (e) {
    btn.disabled = false;
    msg.style.color = '#ef4444';
    msg.textContent = '❌ Error: ' + e;
  }
}
</script>
</body>
</html>
"""

# ============================================================
# 9. CONEXIÓN WI-FI Y BUCLE PRINCIPAL
# ============================================================
wlan_obj = None

def conectar_wifi():
    global wlan_obj
    wlan = network.WLAN(network.STA_IF)
    wlan_obj = wlan
    try:
        wlan.active(False)
        time.sleep_ms(300)
        wlan.active(True)
        time.sleep_ms(200)
    except Exception:
        pass

    # Desactivar ahorro de energía de Wi-Fi para que el módem nunca se duerma
    try:
        wlan.config(pm=wlan.PM_NONE)
    except Exception:
        pass

    # Forzar IP fija 192.168.3.200 antes de conectar
    try:
        wlan.ifconfig(("192.168.3.200", "255.255.255.0", "192.168.3.1", "192.168.3.1"))
    except Exception:
        pass

    if not wlan.isconnected():
        log(f"📶 Conectando a Wi-Fi '{WIFI_SSID}'...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        intentos = 0
        while not wlan.isconnected() and intentos < 30:
            time.sleep_ms(500)
            intentos += 1

    if wlan.isconnected():
        cur_ip, mask, gw, dns = wlan.ifconfig()
        # Asegurar que siempre quede en .200
        if not cur_ip.endswith(".200"):
            partes = cur_ip.split(".")
            nueva_ip = f"{partes[0]}.{partes[1]}.{partes[2]}.200"
            try:
                wlan.ifconfig((nueva_ip, mask, gw, dns))
                time.sleep_ms(200)
            except Exception:
                pass

        ip = wlan.ifconfig()[0]
        log("====================================================")
        log("✅ CONECTADO A WI-FI")
        log(f"🌐 Servidor Web: http://{ip}")
        log(f"📋 Consola de Logs: http://{ip}/logs")
        log("====================================================")
        return ip
    return None

def iniciar_todo():
    global sinric_ws, sinric_conectado, wlan_obj

    # Hardware Watchdog Timer (45s) para auto-recuperación ante bloqueos
    try:
        from machine import WDT
        wdt = WDT(timeout=45000)
    except Exception:
        wdt = None

    ip = conectar_wifi()
    if not ip:
        log("❌ No se pudo conectar a Wi-Fi")
        return

    # Iniciar WebREPL para consola y archivos inalámbricos (clave: 1234)
    try:
        import webrepl
        webrepl.start(password="1234")
        log("📶 WebREPL activo en puerto 8266 (clave: 1234)")
    except Exception:
        pass

    # Iniciar servidor web local en puerto 80
    web_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    web_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    web_sock.bind(("0.0.0.0", 80))
    web_sock.listen(4)
    web_sock.setblocking(False)

    # Conectar con la nube de Sinric Pro para tu Echo Dot 5
    conectar_sinric_pro()

    poller = select.poll()
    poller.register(web_sock, select.POLLIN)
    if sinric_ws:
        poller.register(sinric_ws, select.POLLIN)

    ultimo_heartbeat = time.time()
    ultimo_check_wifi = time.time()
    ultimo_reconnect = 0
    segundos_sin_wifi = 0
    ultimo_gc = time.time()

    log("🚀 Sistema listo: Escuchando órdenes de Alexa y Servidor Web...")

    while True:
        try:
            if wdt:
                wdt.feed()

            ahora = time.time()

            # Liberación periódica de RAM cada 30s para evitar MemoryError
            if ahora - ultimo_gc > 30:
                ultimo_gc = ahora
                gc.collect()

            # 1. Monitoreo y auto-reconexión robusta de Wi-Fi
            if ahora - ultimo_check_wifi > 8:
                ultimo_check_wifi = ahora
                if wlan_obj and not wlan_obj.isconnected():
                    segundos_sin_wifi += 8
                    log(f"⚠️ Wi-Fi desconectado ({segundos_sin_wifi}s). Reconectando...")
                    try:
                        wlan_obj.disconnect()
                        time.sleep_ms(150)
                        wlan_obj.connect(WIFI_SSID, WIFI_PASS)
                    except Exception:
                        pass

                    # Si el router o la red no responde por más de 45s, auto-reiniciar
                    if segundos_sin_wifi >= 45:
                        log("🚨 Wi-Fi no responde tras 45s. Auto-reiniciando ESP32...")
                        time.sleep_ms(500)
                        machine.reset()
                else:
                    segundos_sin_wifi = 0

            # 2. Re-conexión automática a Sinric Pro si se cayó
            if not sinric_conectado or not sinric_ws:
                if ahora - ultimo_reconnect > 6:
                    ultimo_reconnect = ahora
                    log("🔄 Reconectando a Sinric Pro...")
                    conectar_sinric_pro()
                    if sinric_ws:
                        try:
                            poller.register(sinric_ws, select.POLLIN)
                        except Exception:
                            pass
                        ultimo_heartbeat = ahora

            # 3. Mantener vivo el WebSocket (Ping y Heartbeat cada 30 segundos)
            elif sinric_conectado and sinric_ws:
                if ahora - ultimo_heartbeat > 30:
                    ultimo_heartbeat = ahora
                    try:
                        ws_send_ping(sinric_ws)
                        enviar_heartbeat_sinric()
                    except Exception as e:
                        log("⚠️ Error en ping/heartbeat Sinric: " + str(e))
                        try:
                            poller.unregister(sinric_ws)
                        except Exception:
                            pass
                        try:
                            sinric_ws.close()
                        except Exception:
                            pass
                        sinric_conectado = False
                        sinric_ws = None

            # 4. Atender eventos de red
            eventos = poller.poll(50)
            for sock, ev in eventos:
                # Detección de error en el socket por el poll
                if ev & (select.POLLERR | select.POLLHUP):
                    if sinric_ws and sock == sinric_ws:
                        log("⚠️ Desconexión detectada por poll en Sinric Pro")
                        try:
                            poller.unregister(sinric_ws)
                        except Exception:
                            pass
                        try:
                            sinric_ws.close()
                        except Exception:
                            pass
                        sinric_conectado = False
                        sinric_ws = None
                        continue

                # 1. Petición del Servidor Web / Siri / Logs / OTA
                if sock == web_sock:
                    try:
                        cl, _ = web_sock.accept()
                        cl.settimeout(2.5)
                        raw = cl.recv(1024)
                        if raw:
                            req = raw.decode("utf-8", "ignore")
                            primera = req.split("\r\n")[0].split(" ")
                            ruta = primera[1] if len(primera) > 1 else "/"

                            # --- ACTUALIZACIÓN REMOTA POR WI-FI (OTA) ---
                            if ruta == "/update":
                                cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n")
                                cl.sendall(OTA_PAGE)
                                cl.close()

                            elif ruta == "/upload" or ruta.startswith("/upload"):
                                try:
                                    cl_len = 0
                                    for linea in req.split("\r\n"):
                                        if linea.lower().startswith("content-length:"):
                                            cl_len = int(linea.split(":")[1].strip())
                                            break

                                    sep_idx = raw.find(b"\r\n\r\n")
                                    body_start = raw[sep_idx + 4:] if sep_idx != -1 else b""

                                    log(f"📥 Recibiendo actualización OTA: {cl_len} bytes")
                                    with open("main_new.py", "wb") as f_out:
                                        f_out.write(body_start)
                                        recibido = len(body_start)
                                        while recibido < cl_len:
                                            if wdt: wdt.feed()
                                            chunk = cl.recv(min(1024, cl_len - recibido))
                                            if not chunk:
                                                break
                                            f_out.write(chunk)
                                            recibido += len(chunk)

                                    if recibido >= cl_len and cl_len > 100:
                                        log(f"✅ Archivo recibido ({recibido} bytes). Reemplazando main.py...")
                                        cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n\r\nActualizacion exitosa. Reiniciando...")
                                        cl.close()
                                        time.sleep_ms(300)
                                        try:
                                            os.remove("main.py")
                                        except Exception:
                                            pass
                                        os.rename("main_new.py", "main.py")
                                        log("🚀 Reiniciando con nuevo código en 1 segundo...")
                                        time.sleep_ms(700)
                                        machine.reset()
                                    else:
                                        log("❌ Archivo incompleto recibido en OTA")
                                        cl.send("HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nArchivo incompleto")
                                        cl.close()
                                except Exception as err:
                                    log("❌ Error en subida OTA: " + str(err))
                                    try:
                                        cl.send("HTTP/1.1 500 Error\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nError: " + str(err))
                                        cl.close()
                                    except Exception:
                                        pass

                            elif ruta.startswith("/cmd?c="):
                                params = ruta.split("/cmd?")[1]
                                cmd = ""
                                reps = 1
                                vol_exacto = None
                                for p in params.split("&"):
                                    if p.startswith("c="):
                                        cmd = p.split("c=")[1]
                                    elif p.startswith("n="):
                                        try:
                                            reps = int(p.split("n=")[1])
                                        except Exception:
                                            reps = 1
                                    elif p.startswith("v="):
                                        try:
                                            vol_exacto = int(p.split("v=")[1])
                                        except Exception:
                                            pass

                                if cmd == "reboot":
                                    cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n\r\nReiniciando...")
                                    cl.close()
                                    log("🔄 Reinicio solicitado por Web. Reiniciando en 500ms...")
                                    time.sleep_ms(500)
                                    machine.reset()
                                elif vol_exacto is not None:
                                    sony_wifi_set_volume(vol_exacto)
                                    resp = f"OK: Volumen {vol_exacto}"
                                elif cmd in ["tv_power", "tv_vol_up", "tv_vol_down", "tv_mute"]:
                                    ejecutar_tv_hibrido(cmd, reps=reps)
                                    resp = f"OK: {cmd} (Híbrido)"
                                else:
                                    resp = ejecutar_comando(cmd, reps)
                                cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n\r\n" + resp)
                                cl.close()

                            elif ruta == "/logs" or ruta.startswith("/logs"):
                                log_txt = "\n".join(LOG_BUFFER)
                                cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n\r\n" + log_txt)
                                cl.close()

                            else:
                                cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n")
                                cl.sendall(HTML_PAGE)
                                cl.close()
                    except Exception:
                        pass
                    gc.collect()

                # 2. Comando en vivo de Alexa desde Sinric Pro
                elif sinric_ws and sock == sinric_ws:
                    try:
                        frame_str = ws_read_frame(sinric_ws)
                        if frame_str is None:
                            # Socket cerrado por el servidor remoto
                            raise Exception("Conexión finalizada por el servidor")
                        if frame_str:
                            procesar_mensaje_sinric(frame_str)
                    except Exception as e:
                        log("⚠️ Sinric desconectado: " + str(e))
                        try:
                            poller.unregister(sinric_ws)
                        except Exception:
                            pass
                        try:
                            sinric_ws.close()
                        except Exception:
                            pass
                        sinric_conectado = False
                        sinric_ws = None

        except Exception as e:
            pass

if __name__ == "__main__":
    iniciar_todo()




