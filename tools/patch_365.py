from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / 'custom_components/webrtc/www/webrtc-camera.js'
MANIFEST = ROOT / 'custom_components/webrtc/manifest.json'


def replace_once(path, old, new):
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Expected text not found in {path}: {old[:180]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

# When an authoritative HA number zoom entity is configured, use it directly for
# ordinary wheel optical zoom. This avoids depending on the user's generic
# data_joystick template containing a ${zoom} field and gives the same camera-
# selected movement behaviour as the working slider. Ctrl+wheel/digital zoom is
# still handled first and unchanged.
old = '''                const direction = ev.deltaY < 0 ? 'zoom_in' : 'zoom_out';\n                if (wheelUsesJoystick) {\n                    const zoom = direction === 'zoom_in' ? wheelZoomSpeed : -wheelZoomSpeed;\n                    handle('joystick', {pan:0, tilt:0, zoom, speed:wheelZoomSpeed});\n                    wheelDirection = direction;\n                    if (wheelStopTimer) clearTimeout(wheelStopTimer);\n                    wheelStopTimer = setTimeout(() => {\n                        handle('joystick_stop');\n                        wheelStopTimer = null;\n                        wheelDirection = null;\n                    }, pulseMs);\n                } else {\n'''
new = '''                const direction = ev.deltaY < 0 ? 'zoom_in' : 'zoom_out';\n                if (showZoomSlider) {\n                    const state = this.hass?.states?.[zoomEntity];\n                    const current = Number(state?.state);\n                    const min = Number(state?.attributes?.min ?? 0);\n                    const max = Number(state?.attributes?.max ?? 100);\n                    const configuredStep = Number(this.config.ptz.wheel_zoom_step ?? 3);\n                    const entityStep = Number(state?.attributes?.step ?? 1);\n                    const step = Math.max(\n                        Number.isFinite(entityStep) && entityStep > 0 ? entityStep : 1,\n                        Number.isFinite(configuredStep) && configuredStep > 0 ? configuredStep : 3\n                    );\n                    if (Number.isFinite(current)) {\n                        const target = Math.max(\n                            Number.isFinite(min) ? min : 0,\n                            Math.min(Number.isFinite(max) ? max : 100, current + (direction === 'zoom_in' ? step : -step))\n                        );\n                        this.hass.callService('number', 'set_value', {entity_id: zoomEntity, value: target})\n                            .catch(err => console.error('WebRTC PTZ wheel zoom service call failed', err));\n                    }\n                } else if (wheelUsesJoystick) {\n                    const zoom = direction === 'zoom_in' ? wheelZoomSpeed : -wheelZoomSpeed;\n                    handle('joystick', {pan:0, tilt:0, zoom, speed:wheelZoomSpeed});\n                    wheelDirection = direction;\n                    if (wheelStopTimer) clearTimeout(wheelStopTimer);\n                    wheelStopTimer = setTimeout(() => {\n                        handle('joystick_stop');\n                        wheelStopTimer = null;\n                        wheelDirection = null;\n                    }, pulseMs);\n                } else {\n'''
replace_once(JS, old, new)

manifest = MANIFEST.read_text(encoding='utf-8')
new_manifest = manifest.replace('"version": "3.6.4"', '"version": "3.6.5"')
if new_manifest == manifest:
    raise RuntimeError('Manifest version replacement failed')
MANIFEST.write_text(new_manifest, encoding='utf-8')
