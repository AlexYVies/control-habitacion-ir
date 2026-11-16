# ============================================================
# LECTOR INFRARROJO 1838 PARA MICROPYTHON (THONNY)
# Conecta el 1838 (mirándolo de frente):
#   - Patita Izquierda (OUT) -> Pin GPIO 15 de la ESP32
#   - Patita del Medio (GND) -> GND de la ESP32
#   - Patita Derecha   (VCC) -> 3V3 de la ESP32
# ============================================================
from machine import Pin
import time

PIN_RECEPTOR = 15
ir_pin = Pin(PIN_RECEPTOR, Pin.IN, Pin.PULL_UP)

def leer_senal_ir():
    # Esperar a que el sensor baje a 0 (inicio de señal IR)
    if ir_pin.value() == 1:
        return None

    pulsos = []
    t_inicio = time.ticks_us()
    estado_actual = 0

    while True:
        t_cambio = time.ticks_us()
        while ir_pin.value() == estado_actual:
            if time.ticks_diff(time.ticks_us(), t_cambio) > 15000:
                # Silencio mayor a 15ms = fin de la trama infrarroja
                return pulsos
        duracion = time.ticks_diff(time.ticks_us(), t_cambio)
        pulsos.append(duracion)
        estado_actual = 1 - estado_actual
        if len(pulsos) > 100:
            break
    return pulsos

def decodificar_pulsos(pulsos):
    if not pulsos or len(pulsos) < 10:
        return None

    # 1. Intentar decodificar protocolo NEC (32 bits -> ~67 pulsos)
    # Cabecera NEC: ~9000us LOW + ~4500us HIGH
    if len(pulsos) >= 65 and 7000 < pulsos[0] < 11000 and 3500 < pulsos[1] < 5500:
        codigo = 0
        for i in range(2, 66, 2):
            espacio = pulsos[i + 1]
            codigo <<= 1
            if espacio > 1100:  # ~1690us = bit 1, ~560us = bit 0
                codigo |= 1
        return ("NEC", hex(codigo), 32, pulsos)

    # 2. Intentar decodificar protocolo SONY SIRC (12, 15 o 20 bits)
    # Cabecera Sony: ~2400us LOW
    if len(pulsos) >= 25 and 1900 < pulsos[0] < 2900:
        bits = (len(pulsos) - 1) // 2
        codigo = 0
        for i in range(2, len(pulsos), 2):
            marca = pulsos[i]
            codigo <<= 1
            if marca > 900:  # ~1200us = bit 1, ~600us = bit 0
                codigo |= 1
        return ("SONY", hex(codigo), bits, pulsos)

    # 3. Si usa otro protocolo (ej. controles genéricos chinos), generamos su huella y guardamos pulsos
    codigo_raw = 0
    for i in range(2, min(len(pulsos), 66), 2):
        if i + 1 < len(pulsos):
            codigo_raw = (codigo_raw << 1) | (1 if pulsos[i + 1] > 1000 else 0)
    return ("OTRO", hex(codigo_raw), len(pulsos), pulsos)

print("====================================================")
print("📡 LECTOR IR MICROPYTHON LISTO EN PIN GPIO 15")
print("Apunta tu control al sensor 1838 y presiona un botón")
print("====================================================")

while True:
    pulsos = leer_senal_ir()
    if pulsos:
        res = decodificar_pulsos(pulsos)
        if res:
            proto, codigo_hex, bits, raw = res
            print("----------------------------------------------------")
            print(f"✅ Protocolo: {proto} | Código: {codigo_hex} ({bits} bits)")
            if proto == "OTRO":
                print(f"Pulsos RAW ({len(raw)}): {raw}")
        time.sleep_ms(250)  # Pequeña pausa para evitar repeticiones
