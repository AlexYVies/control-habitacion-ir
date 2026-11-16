package com.alex.control.app_control_ir

import android.content.Context
import android.hardware.ConsumerIrManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.alex.control/ir"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                val irManager = getSystemService(Context.CONSUMER_IR_SERVICE) as? ConsumerIrManager

                when (call.method) {
                    "hasIrEmitter" -> {
                        val hasIr = irManager?.hasIrEmitter() ?: false
                        result.success(hasIr)
                    }
                    "transmit" -> {
                        if (irManager == null || !irManager.hasIrEmitter()) {
                            result.error("NO_IR", "Este dispositivo no tiene emisor infrarrojo integrado.", null)
                            return@setMethodCallHandler
                        }
                        var frequency = call.argument<Int>("frequency") ?: 38000
                        val patternList = call.argument<List<Int>>("pattern")
                        if (patternList == null || patternList.isEmpty()) {
                            result.error("INVALID_ARGS", "Patrón IR vacío.", null)
                            return@setMethodCallHandler
                        }

                        // Validar si la frecuencia solicitada está en el rango soportado por el hardware
                        val ranges = irManager.carrierFrequencies
                        if (ranges != null && ranges.isNotEmpty()) {
                            var supported = false
                            for (range in ranges) {
                                if (frequency in range.minFrequency..range.maxFrequency) {
                                    supported = true
                                    break
                                }
                            }
                            if (!supported) {
                                frequency = 38000
                            }
                        }

                        try {
                            irManager.transmit(frequency, patternList.toIntArray())
                            result.success(true)
                        } catch (e: Exception) {
                            result.error("TRANSMIT_ERROR", e.message, null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }
}
