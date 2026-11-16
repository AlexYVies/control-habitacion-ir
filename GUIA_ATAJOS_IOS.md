# 📱 Atajos para iOS (Apple Shortcuts & Siri) - Control de Habitación

Este paquete contiene los archivos de atajos (`.shortcut`) listos para importar y ejecutar en tu **iPhone**, **iPad**, **Apple Watch** o **Mac**, compatibles con la app oficial **Atajos (Shortcuts)** y comandos de voz de **Siri**.

---

## 📦 Contenido Generado

1. **`Atajos_iOS_Control_Habitacion.zip`**: Paquete comprimido con todos los atajos.
2. **Carpeta `atajos_ios/`**: Contiene los archivos individuales:
   - ⭐ **`Control_Habitacion.shortcut`**: **Atajo Maestro**. Al tocarlo, abre un menú flotante en tu iPhone con todas las opciones (Luz, Brillo, Ventilador, Tele Sony Bravia).
   - 💡 **`Encender_Luz.shortcut`**: Enciende la luz (*"Oye Siri, Encender Luz"*).
   - 🌑 **`Apagar_Luz.shortcut`**: Apaga la luz (*"Oye Siri, Apagar Luz"*).
   - 🔆 **`Subir_Brillo_Luz.shortcut`**: Aumenta el brillo del foco.
   - 🔅 **`Bajar_Brillo_Luz.shortcut`**: Reduce el brillo del foco.
   - 🔥 **`Luz_Cálida.shortcut`**: Tono amarillo/cálido.
   - ❄️ **`Luz_Fría.shortcut`**: Tono blanco/frío.
   - 🌀 **`Ventilador_1.shortcut`**: Velocidad 1 (*"Oye Siri, Ventilador 1"*).
   - 🌀 **`Ventilador_2.shortcut`**: Velocidad 2 (*"Oye Siri, Ventilador 2"*).
   - 🌀 **`Ventilador_3.shortcut`**: Velocidad 3 (*"Oye Siri, Ventilador 3"*).
   - 🛑 **`Apagar_Ventilador.shortcut`**: Detiene el ventilador (*"Oye Siri, Apagar Ventilador"*).
   - 🔄 **`Girar_Ventilador.shortcut`**: Activa el giro/oscilación.
   - 📺 **`Encender_Tele.shortcut`**: Enciende la TV Sony Bravia (*"Oye Siri, Encender Tele"*).
   - 📺 **`Apagar_Tele.shortcut`**: Apaga la TV Sony Bravia (*"Oye Siri, Apagar Tele"*).
   - 🔊 **`Subir_Volumen.shortcut`**: Sube 3 niveles de volumen.
   - 🔉 **`Bajar_Volumen.shortcut`**: Baja 3 niveles de volumen.
   - 🔇 **`Silenciar_Tele.shortcut`**: Activa Mute en la TV.
   - 🔀 **`Cambiar_Entrada_Tele.shortcut`**: Cambia entre HDMI / entradas.
3. **`instalar_atajos_ios.html`**: Panel interactivo para probar los comandos y descargar atajos desde Safari en el iPhone.

---

## 🚀 Método 1: Abrir e Instalar los archivos `.shortcut` en iPhone

1. **Pasa los archivos a tu iPhone:**
   - Puedes enviarte el archivo `Control_Habitacion.shortcut` (o el `.zip`) por **AirDrop**, subirlo a **iCloud Drive**, o enviártelo a tu propio chat de **WhatsApp / Telegram**.
2. **Abrir el archivo:**
   - En tu iPhone, entra en la app **Archivos** (Files) o toca el archivo en WhatsApp / Telegram y selecciona **Guardar en Archivos**.
   - Toca el archivo `.shortcut`.
3. **Añadir a Atajos:**
   - iOS abrirá la aplicación **Atajos** automáticamente mostrando el botón azul **"Añadir atajo"** (Add Shortcut).
4. **¡Listo para usar!**
   - Puedes ponerlo como widget en tu pantalla de inicio, en la pantalla de bloqueo, o activarlo diciéndole su nombre a Siri.

---

## 🛠️ Método 2: Crear el Atajo Manualmente en la app Atajos (En 15 segundos)

Si tu iPhone tiene iOS 15, 16, 17 o 18 y te pide autorización de atajos no firmados, crear cada comando toma literalmente 2 clics:

1. Abre la app **Atajos** en tu iPhone y pulsa **`+`** (arriba a la derecha).
2. Toca **Añadir acción**:
   - Busca **URL** y escribe la dirección del comando (ejemplo: `http://192.168.1.200/cmd?c=luz_on`).
3. Toca **+** para añadir la segunda acción:
   - Busca **Obtener contenido de URL** (*Get Contents of URL*).
4. Arriba, cámbiale el nombre al atajo (por ejemplo: `Encender Luz`).
5. Pulsa **OK**. Ahora cuando digas *"Oye Siri, Encender Luz"*, ejecutará la orden de inmediato.

---

## 🌐 URLs de Referencia para tus Atajos

Todas las llamadas se hacen por HTTP GET al ESP32:

| Acción | URL HTTP |
| :--- | :--- |
| **Menú Completo** | `Control_Habitacion.shortcut` |
| **Encender Luz** | `http://192.168.1.200/cmd?c=luz_on` |
| **Apagar Luz** | `http://192.168.1.200/cmd?c=luz_off` |
| **Subir Brillo** | `http://192.168.1.200/cmd?c=brillo_mas&n=3` |
| **Bajar Brillo** | `http://192.168.1.200/cmd?c=brillo_menos&n=3` |
| **Luz Cálida** | `http://192.168.1.200/cmd?c=calidez_mas&n=3` |
| **Luz Fría** | `http://192.168.1.200/cmd?c=calidez_menos&n=3` |
| **Ventilador Vel 1** | `http://192.168.1.200/cmd?c=vent_vel_1` |
| **Ventilador Vel 2** | `http://192.168.1.200/cmd?c=vent_vel_2` |
| **Ventilador Vel 3** | `http://192.168.1.200/cmd?c=vent_vel_3` |
| **Apagar Ventilador** | `http://192.168.1.200/cmd?c=vent_stop` |
| **Girar Ventilador** | `http://192.168.1.200/cmd?c=vent_girar` |
| **TV Encender/Apagar** | `http://192.168.1.200/cmd?c=tv_power` |
| **TV Subir Volumen** | `http://192.168.1.200/cmd?c=tv_vol_up&n=3` |
| **TV Bajar Volumen** | `http://192.168.1.200/cmd?c=tv_vol_down&n=3` |
| **TV Silenciar** | `http://192.168.1.200/cmd?c=tv_mute` |
| **TV Cambiar Entrada** | `http://192.168.1.200/cmd?c=tv_input` |

> *Nota:* Si la IP de tu ESP32 es distinta (por ejemplo `192.168.3.200`), solo reemplaza `192.168.1.200` por la IP asignada a tu placa.
