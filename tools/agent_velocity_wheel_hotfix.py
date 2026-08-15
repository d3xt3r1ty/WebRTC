from pathlib import Path

p = Path('custom_components/webrtc/www/webrtc-camera.js')
s = p.read_text()

old = """        const hasJoystickWheelZoom = Boolean(\n            this.config.ptz?.service &&\n            this.config.ptz?.joystick &&\n            this.config.ptz?.data_joystick &&\n            this.config.ptz?.data_joystick_stop\n        );\n"""
new = """        const hasContinuousWheelZoom = Boolean(\n            this.config.ptz?.service &&\n            this.config.ptz?.data_joystick &&\n            this.config.ptz?.data_joystick_stop\n        );\n"""
s = s.replace(old, new)
s = s.replace("const hasPhysicalWheelZoom = hasEntityWheelZoom || hasJoystickWheelZoom || hasLegacyWheelZoom;", "const hasPhysicalWheelZoom = hasEntityWheelZoom || hasContinuousWheelZoom || hasLegacyWheelZoom;")

old = """        const joystickEnabled = Boolean(\n            this.config.ptz.service &&\n            this.config.ptz.joystick &&\n            this.config.ptz.data_joystick &&\n            this.config.ptz.data_joystick_stop\n        );\n"""
new = """        const continuousZoomEnabled = Boolean(\n            this.config.ptz.service &&\n            this.config.ptz.data_joystick &&\n            this.config.ptz.data_joystick_stop\n        );\n        const joystickEnabled = Boolean(\n            continuousZoomEnabled && this.config.ptz.joystick\n        );\n"""
s = s.replace(old, new)
s = s.replace("const hasPhysicalWheelZoom = showZoomSlider || joystickEnabled || hasLegacyPhysicalWheelZoom;", "const hasPhysicalWheelZoom = showZoomSlider || continuousZoomEnabled || hasLegacyPhysicalWheelZoom;")
s = s.replace("const wheelMode = String(this.config.ptz.wheel_zoom_mode ?? (joystickEnabled ? 'velocity' : 'absolute')).toLowerCase();", "const wheelMode = String(this.config.ptz.wheel_zoom_mode ?? (continuousZoomEnabled ? 'velocity' : 'absolute')).toLowerCase();")
s = s.replace("const velocityWheel = wheelMode === 'velocity' && joystickEnabled;", "const velocityWheel = wheelMode === 'velocity' && continuousZoomEnabled;")
s = s.replace("} else if (wheelMode === 'absolute' && showZoomSlider) {", "} else if ((wheelMode === 'absolute' || (wheelMode === 'velocity' && !continuousZoomEnabled)) && showZoomSlider) {")
s = s.replace("} else if (joystickEnabled && fixedWheelSpeed > 0) {", "} else if (continuousZoomEnabled && fixedWheelSpeed > 0) {")

p.write_text(s)

m = Path('custom_components/webrtc/manifest.json')
ms = m.read_text().replace('"version": "3.6.7"', '"version": "3.6.8"')
m.write_text(ms)
