#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <IRremoteESP8266.h>
#include <IRsend.h>
#include <IRrecv.h>
#include <IRutils.h>

// ============================================================
// 1. CONFIGURACIÓN DE TU RED WI-FI
// ============================================================
const char* ssid     = "TU_NOMBRE_DE_WIFI";
const char* password = "TU_PASSWORD_DE_WIFI";

// ============================================================
// 2. PINES DE LA ESP32
// ============================================================
const uint16_t kRecvPin  = 15; // Patita izquierda del receptor 1838 (GPIO 15)
const uint16_t kIrLedPin = 4;  // Patita larga (+) del LED transparente Emisor IR (GPIO 4)

IRsend irsend(kIrLedPin);
IRrecv irrecv(kRecvPin);
decode_results results;

WebServer server(80);

// Guarda el último código leído por el sensor 1838 para verlo en el Monitor Serie o en la Web
String ultimoCodigoLeido = "Ninguno todavía. Apunta tu control al 1838...";

// ============================================================
// 3. CÓDIGOS INFRARROJOS (FOCO CON VENTILADOR - 14 BOTONES)
// Reemplazaremos estos valores conforme presiones cada botón
// ============================================================
// --- Luz (Encendido / Apagado) ---
uint64_t CODE_LUZ_ON        = 0x000000; // 1. Encender Luz
uint64_t CODE_LUZ_OFF       = 0x000000; // 2. Apagar Luz

// --- Brillo y Calidez ---
uint64_t CODE_BRILLO_MAS    = 0x000000; // 3. Aumentar Brillo
uint64_t CODE_BRILLO_MENOS  = 0x000000; // 4. Disminuir Brillo
uint64_t CODE_CALIDEZ_MAS   = 0xc5bff708; // 5. Aumentar Calidez (Luz más cálida)
uint64_t CODE_CALIDEZ_MENOS = 0xc5bf17e8; // 6. Disminuir Calidez (Luz más fría)
uint64_t CODE_LUZ_MODO      = 0x000000; // 7. Modos Predefinidos (Fría máx -> Cálida máx -> Intermedia máx -> Fría mín)

// --- Ventilador (Velocidades, Stop y Giro) ---
uint64_t CODE_VENT_VEL_1    = 0x000000; // 8. Velocidad 1
uint64_t CODE_VENT_VEL_2    = 0x000000; // 9. Velocidad 2
uint64_t CODE_VENT_VEL_3    = 0x000000; // 10. Velocidad 3
uint64_t CODE_VENT_STOP     = 0x000000; // 11. Stop del Ventilador
uint64_t CODE_VENT_GIRAR    = 0x000000; // 12. Botón para que gire

// --- Temporizadores ---
uint64_t CODE_TIMER_1H      = 0x000000; // 13. Temporizador 1 Hora
uint64_t CODE_TIMER_2H      = 0x000000; // 14. Temporizador 2 Horas

// ============================================================
// 4. CÓDIGOS INFRARROJOS ESTÁNDAR SONY BRAVIA (Protocolo SONY)
// ============================================================
uint64_t CODE_TV_POWER   = 0xA90;  // 12 bits
uint64_t CODE_TV_VOL_UP  = 0x490;  // 12 bits
uint64_t CODE_TV_VOL_DN  = 0xC90;  // 12 bits
uint64_t CODE_TV_MUTE    = 0x290;  // 12 bits
uint64_t CODE_TV_CH_UP   = 0x090;  // 12 bits
uint64_t CODE_TV_CH_DN   = 0x890;  // 12 bits
uint64_t CODE_TV_INPUT   = 0xA50;  // 12 bits
uint64_t CODE_TV_UP      = 0x2F0;  // 12 bits
uint64_t CODE_TV_DOWN    = 0xAF0;  // 12 bits
uint64_t CODE_TV_LEFT    = 0x2D0;  // 12 bits
uint64_t CODE_TV_RIGHT   = 0xCD0;  // 12 bits
uint64_t CODE_TV_OK      = 0xA70;  // 12 bits
uint64_t CODE_TV_HOME    = 0x070;  // 12 bits
uint64_t CODE_TV_BACK    = 0x62E9; // 15 bits

// Función auxiliar para enviar código Sony (se envía 3 veces por norma de Sony)
void enviarSony(uint64_t codigo, uint16_t bits = 12) {
  irrecv.disableIRIn();
  for (int i = 0; i < 3; i++) {
    irsend.sendSony(codigo, bits);
    delay(40);
  }
  irrecv.enableIRIn();
}

// Función auxiliar para enviar código NEC (32 bits)
void enviarNEC(uint64_t codigo) {
  irrecv.disableIRIn();
  irsend.sendNEC(codigo, 32);
  delay(40);
  irrecv.enableIRIn();
}

// ============================================================
// 5. PÁGINA WEB INTEGRADA EN LA ESP32
// ============================================================
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>Control Habitación - ESP32</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --amber: #f59e0b;
      --amber-glow: rgba(245, 158, 11, 0.22);
      --cyan: #06b6d4;
      --cyan-glow: rgba(6, 182, 212, 0.22);
      --red: #ef4444;
      --red-glow: rgba(239, 68, 68, 0.22);
      --green: #10b981;
      --green-glow: rgba(16, 185, 129, 0.22);
      --indigo: #6366f1;
      --btn-bg: #273549;
      --btn-hover: #334155;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; -webkit-tap-highlight-color: transparent; user-select: none; }
    body { background: radial-gradient(circle at top, #1e293b 0%, var(--bg) 70%); color: var(--text); min-height: 100vh; padding: 18px 14px 40px; }
    .container { max-width: 860px; margin: 0 auto; }
    header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; padding: 14px 18px; background: rgba(30, 41, 59, 0.75); border: 1px solid var(--card-border); border-radius: 18px; backdrop-filter: blur(10px); }
    .title-group h1 { font-size: 1.2rem; font-weight: 700; }
    .title-group p { font-size: 0.78rem; color: var(--muted); margin-top: 2px; }
    .status-badge { display: flex; align-items: center; gap: 8px; font-size: 0.78rem; background: rgba(16, 185, 129, 0.14); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); padding: 6px 12px; border-radius: 999px; font-weight: 600; }
    .dot { width: 8px; height: 8px; background: var(--green); border-radius: 50%; box-shadow: 0 0 8px var(--green); }
    .scanner-bar { margin-bottom: 18px; padding: 12px 16px; background: rgba(15, 23, 42, 0.75); border: 1px dashed #38bdf8; border-radius: 14px; display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: 0.82rem; }
    .scanner-bar code { color: #38bdf8; font-weight: 700; }
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
    .toast { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%) translateY(80px); background: #0f172a; border: 1px solid #38bdf8; color: #e0f2fe; padding: 10px 18px; border-radius: 999px; font-size: 0.85rem; font-weight: 600; transition: transform 0.25s ease; z-index: 999; }
    .toast.show { transform: translateX(-50%) translateY(0); }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>🏠 Control de Habitación</h1>
        <p>ESP32 Infrarrojo &bull; Foco Ventilador + Sony Bravia</p>
      </div>
      <div class="status-badge">
        <span class="dot"></span>
        <span>ESP32 Activo</span>
      </div>
    </header>

    <div class="scanner-bar">
      <div>📡 <strong>Última señal leída (1838):</strong> <code id="lastIr">Esperando...</code></div>
      <button style="padding:6px 12px; font-size:0.75rem;" onclick="checkLastIR()">🔄 Actualizar</button>
    </div>

    <div class="grid-main">
      <!-- TARJETA 1: FOCO CON VENTILADOR (14 BOTONES EXACTOS) -->
      <section class="card">
        <div class="card-header">
          <div class="card-title"><span>💡🌀</span><span>Foco con Ventilador</span></div>
          <span class="tag">14 Botones IR</span>
        </div>

        <div class="section-label">Encendido de Luz</div>
        <div class="btn-grid-2">
          <button class="btn-on" onclick="sendCmd('luz_on', 'Encender Luz')">
            <span class="icon">💡</span><span>Encender Luz</span>
          </button>
          <button class="btn-power" onclick="sendCmd('luz_off', 'Apagar Luz')">
            <span class="icon">🌑</span><span>Apagar Luz</span>
          </button>
        </div>

        <div class="section-label">Brillo y Temperatura de Luz</div>
        <div class="btn-grid-2">
          <button onclick="sendCmd('brillo_mas', 'Brillo +')">
            <span class="icon">🔆</span><span>Brillo +</span>
          </button>
          <button onclick="sendCmd('brillo_menos', 'Brillo -')">
            <span class="icon">🔅</span><span>Brillo -</span>
          </button>
          <button class="btn-amber" onclick="sendCmd('calidez_mas', 'Calidez +')">
            <span class="icon">🔥</span><span>Calidez +</span>
          </button>
          <button class="btn-cyan" onclick="sendCmd('calidez_menos', 'Calidez -')">
            <span class="icon">❄️</span><span>Calidez -</span>
          </button>
        </div>

        <button class="btn-indigo btn-full" onclick="sendCmd('luz_modo', 'Modo de Luz Predefinido')">
          <div>🎨 <strong>Modo Predefinido</strong></div>
          <span class="sub">Fría Máx ➔ Cálida Máx ➔ Intermedia Máx ➔ Fría Mín</span>
        </button>

        <div class="section-label">Ventilador (Presiona velocidad para iniciar)</div>
        <div class="btn-grid-3">
          <button class="btn-cyan" onclick="sendCmd('vent_vel_1', 'Velocidad 1')">
            <span class="icon">💨</span><span>Vel 1</span>
          </button>
          <button class="btn-cyan" onclick="sendCmd('vent_vel_2', 'Velocidad 2')">
            <span class="icon">💨💨</span><span>Vel 2</span>
          </button>
          <button class="btn-cyan" onclick="sendCmd('vent_vel_3', 'Velocidad 3')">
            <span class="icon">🌪️</span><span>Vel 3</span>
          </button>
        </div>

        <div class="btn-grid-2" style="margin-top: 10px;">
          <button class="btn-power" onclick="sendCmd('vent_stop', 'Stop Ventilador')">
            <span class="icon">🛑</span><span>Stop Ventilador</span>
          </button>
          <button class="btn-indigo" onclick="sendCmd('vent_girar', 'Girar / Oscilar')">
            <span class="icon">🔄</span><span>Girar</span>
          </button>
        </div>

        <div class="section-label">Temporizador</div>
        <div class="btn-grid-2">
          <button onclick="sendCmd('timer_1h', 'Temporizador 1 Hora')">
            <span class="icon">⏱️</span><span>Timer 1 Hora</span>
          </button>
          <button onclick="sendCmd('timer_2h', 'Temporizador 2 Horas')">
            <span class="icon">⏲️</span><span>Timer 2 Horas</span>
          </button>
        </div>
      </section>

      <!-- TARJETA 2: SONY BRAVIA TV -->
      <section class="card">
        <div class="card-header">
          <div class="card-title"><span>📺</span><span>Sony Bravia TV</span></div>
          <span class="tag">IR Sony</span>
        </div>

        <div class="btn-grid-3">
          <button class="btn-power" onclick="sendCmd('tv_power', 'TV Power')"><span class="icon">⏻</span><span>Power</span></button>
          <button onclick="sendCmd('tv_input', 'Input / HDMI')"><span class="icon">🔌</span><span>Input</span></button>
          <button class="btn-indigo" onclick="sendCmd('tv_home', 'Home')"><span class="icon">🏠</span><span>Home</span></button>
        </div>

        <div class="dpad-wrapper">
          <div></div>
          <button class="dpad-btn" onclick="sendCmd('tv_up', 'Arriba')">▲</button>
          <div></div>
          <button class="dpad-btn" onclick="sendCmd('tv_left', 'Izquierda')">◀</button>
          <button class="dpad-btn dpad-ok" onclick="sendCmd('tv_ok', 'OK')">OK</button>
          <button class="dpad-btn" onclick="sendCmd('tv_right', 'Derecha')">▶</button>
          <div></div>
          <button class="dpad-btn" onclick="sendCmd('tv_down', 'Abajo')">▼</button>
          <div></div>
        </div>

        <div class="btn-grid-2">
          <button onclick="sendCmd('tv_back', 'Regresar')">↩ Back</button>
          <button onclick="sendCmd('tv_mute', 'Mute')">🔇 Mute</button>
        </div>

        <div class="rocker-row">
          <div class="rocker">
            <button onclick="sendCmd('tv_vol_up', 'Volumen +')">➕</button>
            <span>VOL</span>
            <button onclick="sendCmd('tv_vol_down', 'Volumen -')">➖</button>
          </div>
          <div class="rocker" style="justify-content:center;">
            <span style="text-align:center;">SONY<br>BRAVIA</span>
          </div>
          <div class="rocker">
            <button onclick="sendCmd('tv_ch_up', 'Canal +')">➕</button>
            <span>CANAL</span>
            <button onclick="sendCmd('tv_ch_down', 'Canal -')">➖</button>
          </div>
        </div>
      </section>
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

    async function sendCmd(cmd, label) {
      if (navigator.vibrate) navigator.vibrate(25);
      showToast('📡 Enviando: ' + label);
      try {
        const res = await fetch('/cmd?c=' + encodeURIComponent(cmd));
        const txt = await res.text();
        showToast('✅ ' + txt);
      } catch (e) {
        showToast('❌ Error de conexión con ESP32');
      }
    }

    async function checkLastIR() {
      try {
        const res = await fetch('/last_ir');
        const txt = await res.text();
        document.getElementById('lastIr').textContent = txt;
      } catch (e) {}
    }
    setInterval(checkLastIR, 2000);
  </script>
</body>
</html>
)rawliteral";

// ============================================================
// 6. MANEJADORES DE RUTAS DEL SERVIDOR WEB
// ============================================================
void handleRoot() {
  server.send_P(200, "text/html", INDEX_HTML);
}

void handleLastIR() {
  server.send(200, "text/plain", ultimoCodigoLeido);
}

void handleCommand() {
  if (!server.hasArg("c")) {
    server.send(400, "text/plain", "Falta parametro c");
    return;
  }
  String c = server.arg("c");
  Serial.println("Comando recibido desde Web: " + c);

  // --- Comandos Foco con Ventilador (14 botones) ---
  if (c == "luz_on")             enviarNEC(CODE_LUZ_ON);
  else if (c == "luz_off")       enviarNEC(CODE_LUZ_OFF);
  else if (c == "brillo_mas")    enviarNEC(CODE_BRILLO_MAS);
  else if (c == "brillo_menos")  enviarNEC(CODE_BRILLO_MENOS);
  else if (c == "calidez_mas")   enviarNEC(CODE_CALIDEZ_MAS);
  else if (c == "calidez_menos") enviarNEC(CODE_CALIDEZ_MENOS);
  else if (c == "luz_modo")      enviarNEC(CODE_LUZ_MODO);
  else if (c == "vent_vel_1")    enviarNEC(CODE_VENT_VEL_1);
  else if (c == "vent_vel_2")    enviarNEC(CODE_VENT_VEL_2);
  else if (c == "vent_vel_3")    enviarNEC(CODE_VENT_VEL_3);
  else if (c == "vent_stop")     enviarNEC(CODE_VENT_STOP);
  else if (c == "vent_girar")    enviarNEC(CODE_VENT_GIRAR);
  else if (c == "timer_1h")      enviarNEC(CODE_TIMER_1H);
  else if (c == "timer_2h")      enviarNEC(CODE_TIMER_2H);

  // --- Comandos Sony Bravia TV ---
  else if (c == "tv_power")      enviarSony(CODE_TV_POWER, 12);
  else if (c == "tv_vol_up")     enviarSony(CODE_TV_VOL_UP, 12);
  else if (c == "tv_vol_down")   enviarSony(CODE_TV_VOL_DN, 12);
  else if (c == "tv_mute")       enviarSony(CODE_TV_MUTE, 12);
  else if (c == "tv_ch_up")      enviarSony(CODE_TV_CH_UP, 12);
  else if (c == "tv_ch_down")    enviarSony(CODE_TV_CH_DN, 12);
  else if (c == "tv_input")      enviarSony(CODE_TV_INPUT, 12);
  else if (c == "tv_up")         enviarSony(CODE_TV_UP, 12);
  else if (c == "tv_down")       enviarSony(CODE_TV_DOWN, 12);
  else if (c == "tv_left")       enviarSony(CODE_TV_LEFT, 12);
  else if (c == "tv_right")      enviarSony(CODE_TV_RIGHT, 12);
  else if (c == "tv_ok")         enviarSony(CODE_TV_OK, 12);
  else if (c == "tv_home")       enviarSony(CODE_TV_HOME, 12);
  else if (c == "tv_back")       enviarSony(CODE_TV_BACK, 15);
  else {
    server.send(404, "text/plain", "Comando desconocido");
    return;
  }

  server.send(200, "text/plain", "OK: " + c);
}

void setup() {
  Serial.begin(115200);
  irsend.begin();
  irrecv.enableIRIn();

  Serial.println();
  Serial.println("Conectando a WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int intentos = 0;
  while (WiFi.status() != WL_CONNECTED && intentos < 30) {
    delay(500);
    Serial.print(".");
    intentos++;
  }

  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("=== CONECTADO A WIFI ===");
    Serial.print("Abre esta direccion en tu celular o PC: http://");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("No se pudo conectar al WiFi. Verifica el nombre y password.");
  }

  server.on("/", handleRoot);
  server.on("/cmd", handleCommand);
  server.on("/last_ir", handleLastIR);
  server.begin();
}

void loop() {
  server.handleClient();

  // Si el sensor 1838 detecta un botón de cualquier control remoto:
  if (irrecv.decode(&results)) {
    String proto = typeToString(results.decode_type);
    String hexCode = "0x" + uint64ToString(results.value, HEX);
    ultimoCodigoLeido = proto + " : " + hexCode + " (" + String(results.bits) + " bits)";

    Serial.println("-----------------------------------------");
    Serial.println("Señal detectada -> " + ultimoCodigoLeido);
    irrecv.resume();
  }
}
