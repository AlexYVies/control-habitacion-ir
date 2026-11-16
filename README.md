# Control Habitación IR — Smart Room IoT Controller

**Flutter Mobile App + ESP32 Infrared & Network Controller + iOS Shortcuts Integration**  
Control room lighting, fan speeds, and TV over Wi-Fi / Infrared from Android (**Flutter**), **iOS Shortcuts**, or a local **ESP32** web server.

> 🇪🇸 **Resumen en Español:** Sistema domótico para controlar luces, ventilador y TV de una habitación desde una app móvil en **Flutter**, un microcontrolador **ESP32** (con emisor infrarrojo y servidor HTTP) e integración con **Atajos de iOS (Siri)**.

---

## Architecture & Components

- **Mobile App (`app_control_ir/` — Flutter / Dart):**
  - Cross-platform mobile interface to configure the ESP32 IP and trigger IR/network commands.
  - Prebuilt Android APK available in **GitHub Releases**.
- **ESP32 Firmware (`main.py` & `control.ino`):**
  - **MicroPython (`main.py`)** and **Arduino C++ (`control.ino`)** implementations for Wi-Fi HTTP command handling, IR signal transmission, and Sony TV network control.
  - `leer_ir.py`: Helper script to capture and decode raw IR signals.
- **iOS Shortcuts (`generar_shortcuts_ios.py`, `atajos_ios/`, `GUIA_ATAJOS_IOS.md`):**
  - Automated `.shortcut` generator and installation guide for Siri / iOS voice & widget control.

---

## Quick Start

1. **ESP32:** Set `WIFI_SSID`, `WIFI_PASS`, and `APP_SECRET` in `main.py` (or `control.ino`) and flash to your ESP32.
2. **Flutter App:**
   ```bash
   cd app_control_ir
   flutter pub get
   flutter run
   ```
3. **iOS Shortcuts (optional):** See [GUIA_ATAJOS_IOS.md](GUIA_ATAJOS_IOS.md) or run `python generar_shortcuts_ios.py`.
