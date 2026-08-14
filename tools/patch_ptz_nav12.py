from pathlib import Path

root = Path('custom_components/webrtc')
js = root / 'www/webrtc-camera.js'
s = js.read_text()

# Digital PTZ: when physical zoom is available, let renderPTZ arbitrate wheel events.
old = """        const media = this.imageMode ? this.staticImage : this.video;\n        this.digitalPTZ = new DigitalPTZ(\n            this.querySelector('.player'),\n            this.querySelector('.player .ptz-transform'),\n            media,\n            Object.assign({}, this.config.digital_ptz, {persist_key: this.config.image || this.config.url})\n        );\n"""
new = """        const media = this.imageMode ? this.staticImage : this.video;\n        const digitalOptions = Object.assign({}, this.config.digital_ptz, {persist_key: this.config.image || this.config.url});\n        const hasPhysicalWheelZoom = Boolean(\n            this.config.ptz?.service &&\n            this.config.ptz?.data_start_zoom_in && this.config.ptz?.data_end_zoom_in &&\n            this.config.ptz?.data_start_zoom_out && this.config.ptz?.data_end_zoom_out\n        );\n        if (hasPhysicalWheelZoom) digitalOptions.mouse_wheel_zoom = false;\n        this.digitalPTZ = new DigitalPTZ(\n            this.querySelector('.player'),\n            this.querySelector('.player .ptz-transform'),\n            media,\n            digitalOptions\n        );\n"""
assert old in s, 'renderDigitalPTZ block not found'
s = s.replace(old, new, 1)

# Dynamic physical drag owns long-press gestures by default.
old = """        const tapAction = this.config.tap_action;\n        const holdAction = this.config.hold_action;\n"""
new = """        const tapAction = this.config.tap_action;\n        const physicalDragOwnsSurface = Boolean(\n            this.config.ptz?.joystick && this.config.ptz?.physical_drag !== false\n        );\n        const holdAction = physicalDragOwnsSurface ? null : this.config.hold_action;\n"""
assert old in s, 'renderActions action block not found'
s = s.replace(old, new, 1)

# Slower, larger joystick defaults for precision control.
replacements = {
    "const fixedRadius = Math.max(40, Number(this.config.ptz.joystick_radius || 60));":
        "const fixedRadius = Math.max(40, Number(this.config.ptz.joystick_radius || 115));",
    "(this.config.ptz.joystick_radius_touch || 90)": "(this.config.ptz.joystick_radius_touch || 150)",
    "(this.config.ptz.joystick_radius || 60)": "(this.config.ptz.joystick_radius || 115)",
    "(this.config.ptz.joystick_deadband_touch || 24)": "(this.config.ptz.joystick_deadband_touch || 34)",
    "(this.config.ptz.joystick_deadband || 14)": "(this.config.ptz.joystick_deadband || 22)",
    "parseFloat(this.config.ptz.joystick_curve) || 1.35": "parseFloat(this.config.ptz.joystick_curve) || 1.9",
    "Number(this.config.ptz.keyboard_initial_speed || 0.12)": "Number(this.config.ptz.keyboard_initial_speed || 0.05)",
    "Number(this.config.ptz.keyboard_max_speed || 0.65)": "Number(this.config.ptz.keyboard_max_speed || 0.45)",
    "Number(this.config.ptz.keyboard_ramp_ms || 1500)": "Number(this.config.ptz.keyboard_ramp_ms || 2500)",
}
for old, new in replacements.items():
    assert old in s, f'default not found: {old}'
    s = s.replace(old, new, 1)

# Coalesce keyboard updates and ignore browser auto-repeat keydown events.
old = """                const rampMs = Math.max(0, Number(this.config.ptz.keyboard_ramp_ms || 2500));\n                const tick = force => {\n"""
new = """                const rampMs = Math.max(0, Number(this.config.ptz.keyboard_ramp_ms || 2500));\n                const keyboardUpdateMs = Math.max(150, Number(this.config.ptz.keyboard_update_ms || 300));\n                const tick = force => {\n"""
assert old in s, 'keyboard ramp block not found'
s = s.replace(old, new, 1)

old = """                    if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(ev.key)) return;\n                    if (!held.size) keyStarted=performance.now(); held.add(ev.key); tick(true);\n                    if (!keyTimer) keyTimer=setInterval(()=>tick(false),100);\n                    ev.preventDefault(); ev.stopPropagation();\n"""
new = """                    if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(ev.key)) return;\n                    if (ev.repeat) { ev.preventDefault(); ev.stopPropagation(); return; }\n                    if (!held.size) keyStarted=performance.now();\n                    held.add(ev.key);\n                    tick(true);\n                    if (!keyTimer) keyTimer=setInterval(()=>tick(false), keyboardUpdateMs);\n                    ev.preventDefault(); ev.stopPropagation();\n"""
assert old in s, 'keyboard keydown block not found'
s = s.replace(old, new, 1)

# Insert wheel arbitration before the legacy zoom/home button handler.
marker = """        // Keep the legacy buttons for zoom/home and for non-joystick PTZ configs.\n"""
insert = """        // Desktop wheel arbitration: physical optical zoom while unzoomed;\n        // Ctrl+wheel enters DigitalPTZ, and once digitally zoomed the wheel\n        // remains digital regardless of whether Ctrl stays pressed. Pinch remains\n        // handled by DigitalPTZ and is always digital.\n        const hasPhysicalWheelZoom = Boolean(\n            this.config.ptz.data_start_zoom_in && this.config.ptz.data_end_zoom_in &&\n            this.config.ptz.data_start_zoom_out && this.config.ptz.data_end_zoom_out\n        );\n        if (hasPhysicalWheelZoom && this.digitalPTZ) {\n            let wheelStopTimer = null;\n            let wheelDirection = null;\n            const pulseMs = Math.max(80, Number(this.config.ptz.wheel_zoom_pulse_ms || 180));\n            player.addEventListener('wheel', ev => {\n                const digitallyZoomed = isDigitallyZoomed();\n                if (digitallyZoomed || ev.ctrlKey) {\n                    const zoom = 1 - ev.deltaY / 1000;\n                    this.digitalPTZ.transform.zoomAtCoords(zoom, ev.pageX, ev.pageY);\n                    this.digitalPTZ.render();\n                    ev.preventDefault();\n                    ev.stopPropagation();\n                    return;\n                }\n\n                const direction = ev.deltaY < 0 ? 'zoom_in' : 'zoom_out';\n                if (wheelStopTimer && wheelDirection !== direction) {\n                    clearTimeout(wheelStopTimer);\n                    handle('end_' + wheelDirection);\n                    wheelStopTimer = null;\n                }\n                if (!wheelStopTimer || wheelDirection !== direction) {\n                    handle('start_' + direction);\n                }\n                wheelDirection = direction;\n                if (wheelStopTimer) clearTimeout(wheelStopTimer);\n                wheelStopTimer = setTimeout(() => {\n                    handle('end_' + wheelDirection);\n                    wheelStopTimer = null;\n                    wheelDirection = null;\n                }, pulseMs);\n                ev.preventDefault();\n                ev.stopPropagation();\n            }, {passive:false});\n        }\n\n"""
assert marker in s, 'legacy controls marker not found'
s = s.replace(marker, insert + marker, 1)

js.write_text(s)

manifest = root / 'manifest.json'
m = manifest.read_text()
assert '"version": "v3.6.2-nav.11"' in m, 'expected nav.11 manifest version'
manifest.write_text(m.replace('"version": "v3.6.2-nav.11"', '"version": "v3.6.2-nav.12"', 1))
