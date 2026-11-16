import os
import plistlib
import uuid
import zipfile

# Directorio de salida
OUTPUT_DIR = "atajos_ios"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Paleta de colores iOS Shortcuts (WFWorkflowIconStartColor)
COLOR_AMBER  = 4274264319  # Amarillo/Ámbar (Luz)
COLOR_BLUE   = 463140863   # Azul (Ventilador)
COLOR_RED    = 4282601983  # Rojo/Coral (Power/Off)
COLOR_PURPLE = 3679049983  # Morado (TV)
COLOR_GREEN  = 4292093695  # Verde (On/OK)
COLOR_TEAL   = 431817727   # Cyan (Especial)

# Iconos SF Symbols (WFWorkflowIconGlyphNumber)
GLYPH_LIGHT   = 59511  # Luz / Ajustes
GLYPH_FAN     = 59512  # Ventilador / Acción
GLYPH_TV      = 61440  # Pantalla / TV
GLYPH_POWER   = 59511  # General

IP_DEFAULT = "192.168.1.200"

def crear_accion_url(url):
    return {
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "WFURL": url,
            "WFHTTPMethod": "GET",
            "ShowHeaders": False,
            "UUID": str(uuid.uuid4()).upper()
        }
    }

def crear_shortcut(nombre, acciones, glyph=59511, color=COLOR_BLUE):
    return {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "2700.0.4",
        "WFWorkflowName": nombre,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": glyph,
            "WFWorkflowIconStartColor": color,
        },
        "WFWorkflowTypes": ["NCWidget", "WatchKit", "ActionExtension"],
        "WFWorkflowInputContentItemClasses": [],
        "WFWorkflowActions": acciones
    }

# 1. ATAJO MAESTRO CON MENÚ INTERACTIVO
menu_items = [
    ("💡 Encender Luz", "luz_on", 1),
    ("🌑 Apagar Luz", "luz_off", 1),
    ("🔆 Subir Brillo", "brillo_mas", 2),
    ("🔅 Bajar Brillo", "brillo_menos", 2),
    ("🔥 Luz Más Cálida", "calidez_mas", 3),
    ("❄️ Luz Más Fría", "calidez_menos", 3),
    ("🎨 Cambiar Modo Luz", "luz_modo", 1),
    ("🌀 Ventilador Vel 1", "vent_vel_1", 1),
    ("🌀 Ventilador Vel 2", "vent_vel_2", 1),
    ("🌀 Ventilador Vel 3", "vent_vel_3", 1),
    ("🛑 Apagar Ventilador", "vent_stop", 1),
    ("🔄 Ventilador Girar/Oscilar", "vent_girar", 1),
    ("⏳ Ventilador Timer 1h", "timer_1h", 1),
    ("⏳ Ventilador Timer 2h", "timer_2h", 1),
    ("📺 TV Encender / Apagar", "tv_power", 1),
    ("🔊 TV Subir Volumen (+3)", "tv_vol_up", 3),
    ("🔉 TV Bajar Volumen (-3)", "tv_vol_down", 3),
    ("🔇 TV Silenciar (Mute)", "tv_mute", 1),
    ("🔀 TV Cambiar Entrada (HDMI)", "tv_input", 1),
]

group_id = str(uuid.uuid4()).upper()
menu_actions = []

# Inicio del Menú
menu_actions.append({
    "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
    "WFWorkflowActionParameters": {
        "GroupingIdentifier": group_id,
        "WFControlFlowMode": 0,
        "WFMenuPrompt": "¿Qué deseas controlar en la habitación?",
        "WFMenuItems": [item[0] for item in menu_items]
    }
})

# Cada opción del menú
for title, cmd, reps in menu_items:
    menu_actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": group_id,
            "WFControlFlowMode": 1,
            "WFMenuItemTitle": title
        }
    })
    url = f"http://{IP_DEFAULT}/cmd?c={cmd}"
    if reps > 1:
        url += f"&n={reps}"
    menu_actions.append(crear_accion_url(url))

# Fin del menú
menu_actions.append({
    "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
    "WFWorkflowActionParameters": {
        "GroupingIdentifier": group_id,
        "WFControlFlowMode": 2
    }
})

shortcut_maestro = crear_shortcut("Control Habitación", menu_actions, glyph=GLYPH_LIGHT, color=COLOR_BLUE)

# Guardar atajo maestro
path_maestro = os.path.join(OUTPUT_DIR, "Control_Habitacion.shortcut")
with open(path_maestro, "wb") as f:
    plistlib.dump(shortcut_maestro, f, fmt=plistlib.FMT_BINARY)

# 2. ATAJOS INDIVIDUALES (Para usar con Siri por voz: "Oye Siri, Encender Luz")
atajos_individuales = [
    ("Encender Luz", "luz_on", 1, GLYPH_LIGHT, COLOR_AMBER),
    ("Apagar Luz", "luz_off", 1, GLYPH_LIGHT, COLOR_RED),
    ("Subir Brillo Luz", "brillo_mas", 3, GLYPH_LIGHT, COLOR_AMBER),
    ("Bajar Brillo Luz", "brillo_menos", 3, GLYPH_LIGHT, COLOR_AMBER),
    ("Luz Cálida", "calidez_mas", 3, GLYPH_LIGHT, COLOR_AMBER),
    ("Luz Fría", "calidez_menos", 3, GLYPH_LIGHT, COLOR_TEAL),
    ("Ventilador 1", "vent_vel_1", 1, GLYPH_FAN, COLOR_BLUE),
    ("Ventilador 2", "vent_vel_2", 1, GLYPH_FAN, COLOR_BLUE),
    ("Ventilador 3", "vent_vel_3", 1, GLYPH_FAN, COLOR_BLUE),
    ("Apagar Ventilador", "vent_stop", 1, GLYPH_FAN, COLOR_RED),
    ("Girar Ventilador", "vent_girar", 1, GLYPH_FAN, COLOR_BLUE),
    ("Encender Tele", "tv_power", 1, GLYPH_TV, COLOR_PURPLE),
    ("Apagar Tele", "tv_power", 1, GLYPH_TV, COLOR_RED),
    ("Subir Volumen", "tv_vol_up", 3, GLYPH_TV, COLOR_PURPLE),
    ("Bajar Volumen", "tv_vol_down", 3, GLYPH_TV, COLOR_PURPLE),
    ("Silenciar Tele", "tv_mute", 1, GLYPH_TV, COLOR_PURPLE),
    ("Cambiar Entrada Tele", "tv_input", 1, GLYPH_TV, COLOR_PURPLE),
]

archivos_creados = [path_maestro]

for nombre, cmd, reps, glyph, color in atajos_individuales:
    url = f"http://{IP_DEFAULT}/cmd?c={cmd}"
    if reps > 1:
        url += f"&n={reps}"
    sc = crear_shortcut(nombre, [crear_accion_url(url)], glyph=glyph, color=color)
    filename = nombre.replace(" ", "_") + ".shortcut"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "wb") as f:
        plistlib.dump(sc, f, fmt=plistlib.FMT_BINARY)
    archivos_creados.append(filepath)

# 3. CREAR ARCHIVO ZIP CON TODOS LOS ATAJOS
zip_path = os.path.join("Atajos_iOS_Control_Habitacion.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for ruta in archivos_creados:
        zipf.write(ruta, arcname=os.path.basename(ruta))

print(f"[OK] Se han generado {len(archivos_creados)} atajos en '{OUTPUT_DIR}/'")
print(f"[OK] Paquete ZIP creado exitosamente en: '{zip_path}'")
