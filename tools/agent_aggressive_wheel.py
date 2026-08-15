from pathlib import Path

js = Path('custom_components/webrtc/www/webrtc-camera.js')
text = js.read_text()

text = text.replace(
"""        const hasPhysicalWheelZoom = showZoomSlider || joystickEnabled || hasLegacyPhysicalWheelZoom;\n        if (hasPhysicalWheelZoom) {\n""",
"""        const hasContinuousZoom = Boolean(\n            this.config.ptz.service &&\n            this.config.ptz.data_joystick &&\n            this.config.ptz.data_joystick_stop\n        );\n        const hasPhysicalWheelZoom = showZoomSlider || hasContinuousZoom || hasLegacyPhysicalWheelZoom;\n        if (hasPhysicalWheelZoom) {\n"""
)

text = text.replace(
"""            const wheelMode = String(this.config.ptz.wheel_zoom_mode ?? (joystickEnabled ? 'velocity' : 'absolute')).toLowerCase();\n            const velocityWheel = wheelMode === 'velocity' && joystickEnabled;\n""",
"""            const requestedWheelMode = String(this.config.ptz.wheel_zoom_mode ?? (hasContinuousZoom ? 'velocity' : 'absolute')).toLowerCase();\n            const wheelMode = requestedWheelMode === 'velocity' && !hasContinuousZoom && showZoomSlider ? 'absolute' : requestedWheelMode;\n            const velocityWheel = wheelMode === 'velocity' && hasContinuousZoom;\n"""
)

text = text.replace(
"""            const wheelCurve = Math.max(0.2, Number(this.config.ptz.wheel_zoom_curve ?? 1.6));\n            const wheelRamp = Math.max(0.01, Math.min(1, Number(this.config.ptz.wheel_zoom_ramp ?? 0.35)));\n            const wheelDeltaReference = Math.max(1, Number(this.config.ptz.wheel_zoom_delta_reference ?? 120));\n""",
"""            // Expo convention: larger values make the response more aggressive.\n            // wheel_zoom_curve remains accepted as a backwards-compatible alias.\n            const wheelExpo = Math.max(0.2, Number(this.config.ptz.wheel_zoom_expo ?? this.config.ptz.wheel_zoom_curve ?? 1.6));\n            const wheelRamp = Math.max(0.01, Math.min(1, Number(this.config.ptz.wheel_zoom_ramp ?? 0.35)));\n            const wheelDeltaReference = Math.max(1, Number(this.config.ptz.wheel_zoom_delta_reference ?? 120));\n"""
)

old = """                    const deltaIntensity = Math.min(1, delta / wheelDeltaReference);\n                    const cadenceIntensity = hadRecentEvent ? Math.min(1, wheelCadenceMs / dt) : 0;\n                    const instantaneous = Math.min(1, deltaIntensity * cadenceIntensity);\n                    if (!hadRecentEvent || reversing) wheelIntensity = 0;\n                    wheelIntensity += (instantaneous - wheelIntensity) * wheelRamp;\n                    wheelIntensity = Math.max(0, Math.min(1, wheelIntensity));\n                    const speed = minWheelSpeed + (maxWheelSpeed - minWheelSpeed) * Math.pow(wheelIntensity, wheelCurve);\n"""
new = """                    const deltaIntensity = Math.min(1, delta / wheelDeltaReference);\n                    const cadenceIntensity = hadRecentEvent ? Math.min(1, wheelCadenceMs / dt) : 0;\n                    // A large free-spin delta OR a rapid cadence can demand high speed.\n                    // Do not multiply them: that made the first/large event artificially slow.\n                    const instantaneous = Math.max(deltaIntensity, cadenceIntensity);\n                    if (!hadRecentEvent || reversing) wheelIntensity = instantaneous;\n                    else wheelIntensity += (instantaneous - wheelIntensity) * wheelRamp;\n                    wheelIntensity = Math.max(0, Math.min(1, wheelIntensity));\n                    const shapedIntensity = 1 - Math.pow(1 - wheelIntensity, wheelExpo);\n                    const speed = minWheelSpeed + (maxWheelSpeed - minWheelSpeed) * shapedIntensity;\n"""
if old not in text:
    raise SystemExit('target wheel intensity block not found')
text = text.replace(old, new)

js.write_text(text)

manifest = Path('custom_components/webrtc/manifest.json')
m = manifest.read_text()
m = m.replace('"version": "3.6.7"', '"version": "3.6.8"')
manifest.write_text(m)
