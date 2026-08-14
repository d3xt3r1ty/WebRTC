from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / 'custom_components/webrtc/www/webrtc-camera.js'
MANIFEST = ROOT / 'custom_components/webrtc/manifest.json'


def replace_once(path: Path, old: str, new: str):
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Expected text not found in {path}: {old[:160]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

# DigitalPTZ must relinquish the ordinary wheel whenever physical PTZ can handle zoom,
# including joystick-only configurations that do not define legacy zoom button services.
replace_once(JS,
'''        const hasPhysicalWheelZoom = Boolean(\n            this.config.ptz?.service &&\n            this.config.ptz?.data_start_zoom_in && this.config.ptz?.data_end_zoom_in &&\n            this.config.ptz?.data_start_zoom_out && this.config.ptz?.data_end_zoom_out\n        );\n''',
'''        const hasJoystickWheelZoom = Boolean(\n            this.config.ptz?.service &&\n            this.config.ptz?.joystick &&\n            this.config.ptz?.data_joystick &&\n            this.config.ptz?.data_joystick_stop\n        );\n        const hasLegacyWheelZoom = Boolean(\n            this.config.ptz?.service &&\n            this.config.ptz?.data_start_zoom_in && this.config.ptz?.data_end_zoom_in &&\n            this.config.ptz?.data_start_zoom_out && this.config.ptz?.data_end_zoom_out\n        );\n        const hasPhysicalWheelZoom = hasJoystickWheelZoom || hasLegacyWheelZoom;\n''')

# The native range control lives inside .ptz. Do not let the generic PTZ mouse/touch
# button handler preventDefault on the range; that was making the slider read-only.
replace_once(JS,
'''            ptz.addEventListener(startEvent, startEvt => {\n                if (joystickEnabled && startEvt.target.closest?.('.ptz-move')) return;\n''',
'''            ptz.addEventListener(startEvent, startEvt => {\n                if (startEvt.target.closest?.('.ptz-zoom-slider')) return;\n                if (joystickEnabled && startEvt.target.closest?.('.ptz-move')) return;\n''')

# Wheel arbitration in renderPTZ should be available for joystick zoom even when there
# are no legacy zoom-in/out start/end templates.
replace_once(JS,
'''        const hasPhysicalWheelZoom = Boolean(\n            this.config.ptz.data_start_zoom_in && this.config.ptz.data_end_zoom_in &&\n            this.config.ptz.data_start_zoom_out && this.config.ptz.data_end_zoom_out\n        );\n        if (hasPhysicalWheelZoom && this.digitalPTZ) {\n''',
'''        const hasLegacyPhysicalWheelZoom = Boolean(\n            this.config.ptz.data_start_zoom_in && this.config.ptz.data_end_zoom_in &&\n            this.config.ptz.data_start_zoom_out && this.config.ptz.data_end_zoom_out\n        );\n        const hasPhysicalWheelZoom = joystickEnabled || hasLegacyPhysicalWheelZoom;\n        if (hasPhysicalWheelZoom) {\n''')

# Ctrl+wheel/digitally-zoomed routing is only meaningful when DigitalPTZ exists.
replace_once(JS,
'''                if (digitallyZoomed || ev.ctrlKey) {\n                    const zoom = 1 - ev.deltaY / 1000;\n                    this.digitalPTZ.transform.zoomAtCoords(zoom, ev.pageX, ev.pageY);\n                    this.digitalPTZ.render();\n                    ev.preventDefault();\n                    ev.stopPropagation();\n                    return;\n                }\n''',
'''                if (this.digitalPTZ && (digitallyZoomed || ev.ctrlKey)) {\n                    const zoom = 1 - ev.deltaY / 1000;\n                    this.digitalPTZ.transform.zoomAtCoords(zoom, ev.pageX, ev.pageY);\n                    this.digitalPTZ.render();\n                    ev.preventDefault();\n                    ev.stopPropagation();\n                    return;\n                }\n''')

manifest = MANIFEST.read_text(encoding='utf-8')
new_manifest = manifest.replace('"version": "3.6.3"', '"version": "3.6.4"')
if new_manifest == manifest:
    raise RuntimeError('Manifest version replacement failed')
MANIFEST.write_text(new_manifest, encoding='utf-8')
