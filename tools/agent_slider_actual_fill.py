from pathlib import Path

p = Path('custom_components/webrtc/www/webrtc-camera.js')
text = p.read_text()

old_css = """                .ptz-zoom-slider input { accent-color:var(--primary-color); cursor:pointer; }\n                .ptz-zoom-slider.vertical input { width:120px; transform:rotate(-90deg); margin:48px -42px; }\n                .ptz-zoom-slider.horizontal input { width:120px; }\n"""
new_css = """                .ptz-zoom-slider input {\n                    --webrtc-zoom-actual:0%;\n                    -webkit-appearance:none; appearance:none;\n                    height:4px; border-radius:999px; cursor:pointer;\n                    background:linear-gradient(to right, var(--primary-color) 0 var(--webrtc-zoom-actual), rgba(255,255,255,.28) var(--webrtc-zoom-actual) 100%);\n                }\n                .ptz-zoom-slider input::-webkit-slider-runnable-track { height:4px; background:transparent; border:none; }\n                .ptz-zoom-slider input::-webkit-slider-thumb {\n                    -webkit-appearance:none; appearance:none; width:14px; height:14px; margin-top:-5px;\n                    border-radius:50%; border:2px solid rgba(255,255,255,.9); background:var(--primary-color);\n                }\n                .ptz-zoom-slider input::-moz-range-track { height:4px; background:transparent; border:none; }\n                .ptz-zoom-slider input::-moz-range-progress { background:transparent; }\n                .ptz-zoom-slider input::-moz-range-thumb {\n                    width:12px; height:12px; border-radius:50%; border:2px solid rgba(255,255,255,.9); background:var(--primary-color);\n                }\n                .ptz-zoom-slider.vertical input { width:120px; transform:rotate(-90deg); margin:48px -42px; }\n                .ptz-zoom-slider.horizontal input { width:120px; }\n"""
if old_css not in text:
    raise SystemExit('slider css not found')
text = text.replace(old_css, new_css, 1)

old_sync = """            const syncTimeoutMs = Math.max(300, Number(this.config.ptz.wheel_zoom_sync_timeout_ms ?? 1500));\n            const sendZoom = value => {\n"""
new_sync = """            const syncTimeoutMs = Math.max(300, Number(this.config.ptz.wheel_zoom_sync_timeout_ms ?? 1500));\n            const predictiveDisplayTimeoutMs = Math.max(syncTimeoutMs, Number(this.config.ptz.wheel_zoom_target_display_timeout_ms ?? 10000));\n            const setActualFill = (value, min, max) => {\n                const lo = Number.isFinite(min) ? min : 0;\n                const hi = Number.isFinite(max) && max > lo ? max : 100;\n                const pct = Math.max(0, Math.min(100, (Number(value) - lo) * 100 / (hi - lo)));\n                range.style.setProperty('--webrtc-zoom-actual', `${pct}%`);\n            };\n            const sendZoom = value => {\n"""
if old_sync not in text:
    raise SystemExit('sync block not found')
text = text.replace(old_sync, new_sync, 1)

old_update = """                if (pendingTarget !== null) {\n                    const tolerance = Math.max(0.05, Math.abs(Number(range.step)) / 2);\n                    if (Math.abs(value - pendingTarget) <= tolerance || Date.now() > pendingUntil) pendingTarget = null;\n                }\n                const shown = pendingTarget !== null ? pendingTarget : value;\n                if (!sliderActive) range.value = String(shown);\n                label.textContent = `${Math.round(shown)}%`;\n"""
new_update = """                setActualFill(value, min, max);\n                if (pendingTarget !== null) {\n                    const tolerance = Math.max(0.05, Math.abs(Number(range.step)) / 2);\n                    if (Math.abs(value - pendingTarget) <= tolerance || Date.now() > pendingUntil) pendingTarget = null;\n                }\n                const shown = pendingTarget !== null ? pendingTarget : value;\n                if (!sliderActive) range.value = String(shown);\n                label.textContent = `${Math.round(shown)}%`;\n"""
if old_update not in text:
    raise SystemExit('update block not found')
text = text.replace(old_update, new_update, 1)

old_show = """                showTarget: value => {\n                    const numeric = Number(value);\n                    if (!Number.isFinite(numeric)) return;\n                    pendingTarget = numeric;\n                    pendingUntil = Date.now() + syncTimeoutMs;\n                    range.value = String(numeric);\n                    label.textContent = `${Math.round(numeric)}%`;\n                },\n"""
new_show = """                showTarget: value => {\n                    const numeric = Number(value);\n                    if (!Number.isFinite(numeric)) return;\n                    pendingTarget = numeric;\n                    pendingUntil = Date.now() + predictiveDisplayTimeoutMs;\n                    range.value = String(numeric);\n                    label.textContent = `${Math.round(numeric)}%`;\n                },\n"""
if old_show not in text:
    raise SystemExit('show target block not found')
text = text.replace(old_show, new_show, 1)

p.write_text(text)
