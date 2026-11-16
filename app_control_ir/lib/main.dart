import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );
  runApp(const ControlHabitacionApp());
}

class ControlHabitacionApp extends StatelessWidget {
  const ControlHabitacionApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Control Habitación IR',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0F172A),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF06B6D4),
          brightness: Brightness.dark,
          surface: const Color(0xFF1E293B),
        ),
        useMaterial3: true,
      ),
      home: const RemoteHomeScreen(),
    );
  }
}

class RemoteHomeScreen extends StatefulWidget {
  const RemoteHomeScreen({super.key});

  @override
  State<RemoteHomeScreen> createState() => _RemoteHomeScreenState();
}

class _RemoteHomeScreenState extends State<RemoteHomeScreen> {
  static const MethodChannel _irChannel = MethodChannel('com.alex.control/ir');

  bool _hasPhoneIr = false;
  bool _usePhoneIr = true; // true = IR del teléfono, false = Wi-Fi ESP32
  String _esp32Ip = '192.168.1.200';
  String _statusMessage = 'Listo para enviar comandos';

  // Timers para soporte de pulsación sostenida (mantener presionado)
  Timer? _holdInitialTimer;
  Timer? _holdRepeatTimer;

  // ============================================================
  // 14 CÓDIGOS NEC REALES DEL FOCO CON VENTILADOR
  // ============================================================
  static const Map<String, int> _codigosFoco = {
    'luz_on':        0xc5bff00f, // 1. Encender Luz
    'luz_off':       0xc5bf40bf, // 2. Apagar Luz
    'brillo_mas':    0xc5bfd52a, // 3. Brillo +
    'brillo_menos':  0xc5bf3dc2, // 4. Brillo -
    'calidez_mas':   0xc5bff708, // 5. Calidez + (Luz más cálida) [CORREGIDO]
    'calidez_menos': 0xc5bf17e8, // 6. Calidez - (Luz más fría)  [CORREGIDO]
    'luz_modo':      0xc5bfc837, // 7. Modo Predefinido
    'vent_vel_1':    0xe15aa857, // 8. Velocidad 1
    'vent_vel_2':    0xe15a18e7, // 9. Velocidad 2
    'vent_vel_3':    0xe15a6897, // 10. Velocidad 3
    'vent_stop':     0xe15aa25d, // 11. Stop Ventilador
    'vent_girar':    0xe15ae21d, // 12. Girar
    'timer_1h':      0xe15a52ad, // 13. Timer 1 Hora
    'timer_2h':      0xe15ad22d, // 14. Timer 2 Horas
  };

  // ============================================================
  // CÓDIGOS SONY BRAVIA TV: [codigoHex, numeroDeBits]
  // ============================================================
  static const Map<String, List<int>> _codigosSony = {
    'tv_power':    [0xA90, 12],
    'tv_vol_up':   [0x490, 12],
    'tv_vol_down': [0xC90, 12],
    'tv_mute':     [0x290, 12],
    'tv_ch_up':    [0x090, 12],
    'tv_ch_down':  [0x890, 12],
    'tv_input':    [0xA50, 12],
    'tv_up':       [0x2F0, 12],
    'tv_down':     [0xAF0, 12],
    'tv_left':     [0x2D0, 12],
    'tv_right':    [0xCD0, 12],
    'tv_ok':       [0xA70, 12],
    'tv_home':     [0x070, 12],
    'tv_back':     [0x62E9, 15],
  };

  @override
  void initState() {
    super.initState();
    _checkIrSupport();
  }

  @override
  void dispose() {
    _stopHold();
    super.dispose();
  }

  Future<void> _checkIrSupport() async {
    try {
      final bool hasIr = await _irChannel.invokeMethod<bool>('hasIrEmitter') ?? false;
      setState(() {
        _hasPhoneIr = hasIr;
        _usePhoneIr = hasIr;
        _statusMessage = hasIr
            ? '✅ Emisor IR del teléfono detectado'
            : '⚠️ Sin IR en teléfono (Usa modo Wi-Fi ESP32)';
      });
    } catch (_) {
      setState(() {
        _hasPhoneIr = false;
        _statusMessage = 'Modo listo';
      });
    }
  }

  /// Convierte un código NEC de 32 bits en un arreglo de pulsos en microsegundos (alternancia ON/OFF estricta)
  List<int> _buildNecPattern(int code32) {
    final List<int> pattern = [
      9000, // ON: Cabecera
      4500, // OFF: Cabecera
    ];
    for (int i = 31; i >= 0; i--) {
      pattern.add(560); // ON: Marca de bit
      if (((code32 >> i) & 1) == 1) {
        pattern.add(1690); // OFF: Espacio bit 1
      } else {
        pattern.add(560);  // OFF: Espacio bit 0
      }
    }
    pattern.add(560);   // ON: Pulso final de parada
    pattern.add(40000); // OFF: Silencio final
    return pattern;
  }

  /// Convierte un código Sony SIRC (12 o 15 bits) en un arreglo de pulsos estrictamente alternados ON/OFF
  List<int> _buildSonyPattern(int code, int bits) {
    final List<int> pattern = [];
    for (int rep = 0; rep < 3; rep++) {
      pattern.add(2400); // ON: Cabecera Sony
      pattern.add(600);  // OFF: Espacio tras cabecera
      for (int i = bits - 1; i >= 0; i--) {
        // Pulso ON del bit
        if (((code >> i) & 1) == 1) {
          pattern.add(1200); // ON: Bit 1 (1.2 ms)
        } else {
          pattern.add(600);  // ON: Bit 0 (0.6 ms)
        }
        // Espacio OFF tras el bit
        if (i > 0) {
          pattern.add(600);  // OFF normal entre bits
        } else {
          // Último bit de la trama: aquí va la pausa de 25ms antes de repetir
          pattern.add(25000); // OFF: Pausa entre repeticiones Sony
        }
      }
    }
    return pattern;
  }

  void _startHold(String cmd, String label) {
    _sendCommand(cmd, label);
    _holdInitialTimer?.cancel();
    _holdRepeatTimer?.cancel();
    // Espera inicial de 350ms antes de comenzar la repetición continua
    _holdInitialTimer = Timer(const Duration(milliseconds: 350), () {
      _holdRepeatTimer = Timer.periodic(const Duration(milliseconds: 180), (_) {
        _sendCommand(cmd, label);
      });
    });
  }

  void _stopHold() {
    _holdInitialTimer?.cancel();
    _holdRepeatTimer?.cancel();
    _holdInitialTimer = null;
    _holdRepeatTimer = null;
  }

  Future<void> _sendCommand(String cmdKey, String label) async {
    HapticFeedback.lightImpact();

    if (_usePhoneIr) {
      // MODO 1: Enviar directamente por el Infrarrojo del teléfono Android
      try {
        if (_codigosFoco.containsKey(cmdKey)) {
          final int code = _codigosFoco[cmdKey]!;
          final List<int> pattern = _buildNecPattern(code);
          await _irChannel.invokeMethod('transmit', {
            'frequency': 38000,
            'pattern': pattern,
          });
          setState(() {
            _statusMessage = '📡 IR: $label';
          });
        } else if (_codigosSony.containsKey(cmdKey)) {
          final List<int> info = _codigosSony[cmdKey]!;
          final List<int> pattern = _buildSonyPattern(info[0], info[1]);
          await _irChannel.invokeMethod('transmit', {
            'frequency': 40000,
            'pattern': pattern,
          });
          setState(() {
            _statusMessage = '📺 IR Sony: $label';
          });
        }
      } on PlatformException catch (e) {
        setState(() {
          _statusMessage = '❌ Error IR: ${e.message}';
        });
      }
    } else {
      // MODO 2: Enviar por Wi-Fi a la ESP32
      try {
        final client = HttpClient()..connectionTimeout = const Duration(seconds: 1);
        final request = await client.getUrl(Uri.parse('http://$_esp32Ip/cmd?c=$cmdKey'));
        final response = await request.close();
        await response.drain();
        client.close();
        setState(() {
          _statusMessage = '✅ ESP32: $label';
        });
      } catch (e) {
        setState(() {
          _statusMessage = '❌ Sin respuesta de ESP32 ($_esp32Ip)';
        });
      }
    }
  }

  void _showEspIpDialog() {
    final controller = TextEditingController(text: _esp32Ip);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('IP de tu ESP32'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            labelText: 'Dirección IP (ej. 192.168.1.200)',
            border: OutlineInputBorder(),
          ),
          keyboardType: TextInputType.url,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () {
              setState(() {
                _esp32Ip = controller.text.trim();
              });
              Navigator.pop(ctx);
            },
            child: const Text('Guardar'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: const Color(0xFF1E293B),
          elevation: 0,
          title: const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '🏠 Control Habitación',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              Text(
                'Foco Ventilador + Sony Bravia',
                style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
              ),
            ],
          ),
          actions: [
            IconButton(
              tooltip: 'Configurar IP ESP32',
              icon: const Icon(Icons.settings_ethernet),
              onPressed: _showEspIpDialog,
            ),
          ],
          bottom: const TabBar(
            indicatorColor: Color(0xFF38BDF8),
            tabs: [
              Tab(icon: Icon(Icons.wind_power), text: 'Foco y Ventilador'),
              Tab(icon: Icon(Icons.tv), text: 'Sony Bravia TV'),
            ],
          ),
        ),
        body: Column(
          children: [
            // Barra de modo (IR Teléfono vs Wi-Fi ESP32) y estado
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: const BoxDecoration(
                color: Color(0xFF162032),
                border: Border(
                  bottom: BorderSide(color: Color(0xFF334155)),
                ),
              ),
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: SegmentedButton<bool>(
                          segments: [
                            ButtonSegment<bool>(
                              value: true,
                              label: Text(
                                _hasPhoneIr ? '📱 IR Teléfono' : '📱 IR Teléfono (N/D)',
                                style: const TextStyle(fontSize: 12),
                              ),
                            ),
                            const ButtonSegment<bool>(
                              value: false,
                              label: Text('🌐 Wi-Fi ESP32', style: TextStyle(fontSize: 12)),
                            ),
                          ],
                          selected: {_usePhoneIr},
                          onSelectionChanged: (selection) {
                            setState(() {
                              _usePhoneIr = selection.first;
                            });
                          },
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _statusMessage,
                    style: const TextStyle(fontSize: 12, color: Color(0xFF38BDF8)),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),

            // Contenido de las pestañas
            Expanded(
              child: TabBarView(
                children: [
                  _buildFocoVentiladorTab(),
                  _buildSonyTvTab(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ============================================================
  // PESTAÑA 1: LOS 14 BOTONES DEL FOCO CON VENTILADOR
  // ============================================================
  Widget _buildFocoVentiladorTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _sectionHeader('ILUMINACIÓN (ENCENDIDO / APAGADO)'),
        Row(
          children: [
            Expanded(
              child: _irButton(
                cmd: 'luz_on',
                label: 'Encender Luz',
                icon: Icons.lightbulb,
                color: const Color(0xFF10B981),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _irButton(
                cmd: 'luz_off',
                label: 'Apagar Luz',
                icon: Icons.lightbulb_outline,
                color: const Color(0xFFEF4444),
              ),
            ),
          ],
        ),

        const SizedBox(height: 16),
        _sectionHeader('BRILLO Y CALIDEZ (MANTÉN PRESIONADO PARA REPETIR)'),
        Row(
          children: [
            Expanded(
              child: _irButton(
                cmd: 'brillo_mas',
                label: 'Brillo +',
                icon: Icons.brightness_high,
                color: const Color(0xFF475569),
                repeatable: true,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _irButton(
                cmd: 'brillo_menos',
                label: 'Brillo -',
                icon: Icons.brightness_low,
                color: const Color(0xFF475569),
                repeatable: true,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _irButton(
                cmd: 'calidez_mas',
                label: 'Calidez + (Cálida)',
                icon: Icons.wb_sunny,
                color: const Color(0xFFF59E0B),
                repeatable: true,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _irButton(
                cmd: 'calidez_menos',
                label: 'Calidez - (Fría)',
                icon: Icons.ac_unit,
                color: const Color(0xFF06B6D4),
                repeatable: true,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        _irButton(
          cmd: 'luz_modo',
          label: 'Modo Predefinido (Fría Máx ➔ Cálida Máx ➔ Intermedia ➔ Mín)',
          icon: Icons.palette_outlined,
          color: const Color(0xFF6366F1),
        ),

        const SizedBox(height: 16),
        _sectionHeader('VENTILADOR (PRESIONA VELOCIDAD PARA INICIAR)'),
        Row(
          children: [
            Expanded(
              child: _irButton(
                cmd: 'vent_vel_1',
                label: 'Vel 1',
                icon: Icons.air,
                color: const Color(0xFF0891B2),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _irButton(
                cmd: 'vent_vel_2',
                label: 'Vel 2',
                icon: Icons.wind_power,
                color: const Color(0xFF0891B2),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _irButton(
                cmd: 'vent_vel_3',
                label: 'Vel 3',
                icon: Icons.cyclone,
                color: const Color(0xFF0891B2),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _irButton(
                cmd: 'vent_stop',
                label: 'Stop Ventilador',
                icon: Icons.stop_circle_outlined,
                color: const Color(0xFFEF4444),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _irButton(
                cmd: 'vent_girar',
                label: 'Girar / Oscilar',
                icon: Icons.sync,
                color: const Color(0xFF6366F1),
              ),
            ),
          ],
        ),

        const SizedBox(height: 16),
        _sectionHeader('TEMPORIZADOR'),
        Row(
          children: [
            Expanded(
              child: _irButton(
                cmd: 'timer_1h',
                label: 'Timer 1 Hora',
                icon: Icons.timer_outlined,
                color: const Color(0xFF475569),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _irButton(
                cmd: 'timer_2h',
                label: 'Timer 2 Horas',
                icon: Icons.timer,
                color: const Color(0xFF475569),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ============================================================
  // PESTAÑA 2: SONY BRAVIA TV
  // ============================================================
  Widget _buildSonyTvTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Expanded(
              child: _irButton(
                cmd: 'tv_power',
                label: 'Power',
                icon: Icons.power_settings_new,
                color: const Color(0xFFEF4444),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _irButton(
                cmd: 'tv_input',
                label: 'Input',
                icon: Icons.input,
                color: const Color(0xFF475569),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _irButton(
                cmd: 'tv_home',
                label: 'Home',
                icon: Icons.home_outlined,
                color: const Color(0xFF6366F1),
              ),
            ),
          ],
        ),
        const SizedBox(height: 20),

        // Cruceta de Navegación (Soporta mantener presionado)
        Center(
          child: SizedBox(
            width: 220,
            height: 200,
            child: GridView.count(
              crossAxisCount: 3,
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              physics: const NeverScrollableScrollPhysics(),
              children: [
                const SizedBox.shrink(),
                _dpadButton('tv_up', 'Arriba', Icons.keyboard_arrow_up),
                const SizedBox.shrink(),
                _dpadButton('tv_left', 'Izquierda', Icons.keyboard_arrow_left),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF6366F1),
                    foregroundColor: Colors.white,
                    shape: const CircleBorder(),
                    padding: EdgeInsets.zero,
                  ),
                  onPressed: () => _sendCommand('tv_ok', 'OK'),
                  child: const Text('OK', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
                _dpadButton('tv_right', 'Derecha', Icons.keyboard_arrow_right),
                const SizedBox.shrink(),
                _dpadButton('tv_down', 'Abajo', Icons.keyboard_arrow_down),
                const SizedBox.shrink(),
              ],
            ),
          ),
        ),

        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _irButton(
                cmd: 'tv_back',
                label: 'Regresar',
                icon: Icons.arrow_back,
                color: const Color(0xFF475569),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _irButton(
                cmd: 'tv_mute',
                label: 'Mute',
                icon: Icons.volume_off,
                color: const Color(0xFF475569),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),

        // Volumen y Canales (Soportan mantener presionado para subir/bajar rápido)
        _sectionHeader('VOLUMEN Y CANAL (MANTÉN PRESIONADO PARA CONTINUO)'),
        Row(
          children: [
            Expanded(
              child: Column(
                children: [
                  _irButton(
                    cmd: 'tv_vol_up',
                    label: 'Volumen +',
                    icon: Icons.add,
                    color: const Color(0xFF0891B2),
                    repeatable: true,
                  ),
                  const SizedBox(height: 8),
                  _irButton(
                    cmd: 'tv_vol_down',
                    label: 'Volumen -',
                    icon: Icons.remove,
                    color: const Color(0xFF0891B2),
                    repeatable: true,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                children: [
                  _irButton(
                    cmd: 'tv_ch_up',
                    label: 'Canal +',
                    icon: Icons.keyboard_arrow_up,
                    color: const Color(0xFF475569),
                    repeatable: true,
                  ),
                  const SizedBox(height: 8),
                  _irButton(
                    cmd: 'tv_ch_down',
                    label: 'Canal -',
                    icon: Icons.keyboard_arrow_down,
                    color: const Color(0xFF475569),
                    repeatable: true,
                  ),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _sectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.8,
          color: Color(0xFF94A3B8),
        ),
      ),
    );
  }

  Widget _irButton({
    required String cmd,
    required String label,
    required IconData icon,
    required Color color,
    bool repeatable = false,
  }) {
    final buttonContent = Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 24),
        const SizedBox(height: 5),
        Text(
          label,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        ),
      ],
    );

    final style = ElevatedButton.styleFrom(
      backgroundColor: color.withValues(alpha: 0.22),
      foregroundColor: Colors.white,
      side: BorderSide(color: color.withValues(alpha: 0.55)),
      padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    );

    if (!repeatable) {
      return ElevatedButton(
        style: style,
        onPressed: () => _sendCommand(cmd, label),
        child: buttonContent,
      );
    }

    return Listener(
      onPointerDown: (_) => _startHold(cmd, label),
      onPointerUp: (_) => _stopHold(),
      onPointerCancel: (_) => _stopHold(),
      child: ElevatedButton(
        style: style,
        onPressed: () {},
        child: buttonContent,
      ),
    );
  }

  Widget _dpadButton(String cmd, String label, IconData icon) {
    final style = ElevatedButton.styleFrom(
      backgroundColor: const Color(0xFF273549),
      foregroundColor: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      padding: EdgeInsets.zero,
    );

    return Listener(
      onPointerDown: (_) => _startHold(cmd, label),
      onPointerUp: (_) => _stopHold(),
      onPointerCancel: (_) => _stopHold(),
      child: ElevatedButton(
        style: style,
        onPressed: () {},
        child: Icon(icon, size: 28),
      ),
    );
  }
}
