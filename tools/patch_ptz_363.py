from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / 'custom_components/webrtc/www/webrtc-camera.js'
MANIFEST = ROOT / 'custom_components/webrtc/manifest.json'


def replace_once(path: Path, old: str, new: str):
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Expected text not found in {path}: {old[:120]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

replace_once(JS,
"""            const minSpeed = Math.max(0, Math.min(1, parseFloat(this.config.ptz.joystick_min_speed) || 0.12));
            const curve = Math.max(0.2, parseFloat(this.config.ptz.joystick_curve) || 1.9);
""",
"""            const configuredMinSpeed = Number(this.config.ptz.joystick_min_speed ?? 0.03);
            const configuredMaxSpeed = Number(this.config.ptz.joystick_max_speed ?? 1.0);
            const minSpeed = Math.max(0, Math.min(1, Number.isFinite(configuredMinSpeed) ? configuredMinSpeed : 0.03));
            const maxSpeed = Math.max(minSpeed, Math.min(1, Number.isFinite(configuredMaxSpeed) ? configuredMaxSpeed : 1.0));
            const curve = Math.max(0.2, Number(this.config.ptz.joystick_curve ?? 1.9));
""")
replace_once(JS,
"""                const magnitude = minSpeed + (1-minSpeed)*Math.pow(norm,curve);
""",
"""                const magnitude = minSpeed + (maxSpeed-minSpeed)*Math.pow(norm,curve);
""")
replace_once(JS,
"""                const initial = Math.max(0.01, Math.min(1, Number(this.config.ptz.keyboard_initial_speed || 0.05)));
""",
"""                const initial = Math.max(0, Math.min(1, Number(this.config.ptz.keyboard_initial_speed ?? 0.04)));
""")
replace_once(JS,
"""            const pulseMs = Math.max(80, Number(this.config.ptz.wheel_zoom_pulse_ms || 180));
            player.addEventListener('wheel', ev => {
""",
"""            const pulseMs = Math.max(80, Number(this.config.ptz.wheel_zoom_pulse_ms ?? 180));
            const wheelZoomSpeed = Math.max(0, Math.min(1, Number(this.config.ptz.wheel_zoom_speed ?? 0.20)));
            const wheelUsesJoystick = joystickEnabled && wheelZoomSpeed > 0;
            player.addEventListener('wheel', ev => {
""")
replace_once(JS,
"""                const direction = ev.deltaY < 0 ? 'zoom_in' : 'zoom_out';
                if (wheelStopTimer && wheelDirection !== direction) {
                    clearTimeout(wheelStopTimer);
                    handle('end_' + wheelDirection);
                    wheelStopTimer = null;
                }
                if (!wheelStopTimer || wheelDirection !== direction) {
                    handle('start_' + direction);
                }
                wheelDirection = direction;
                if (wheelStopTimer) clearTimeout(wheelStopTimer);
                wheelStopTimer = setTimeout(() => {
                    handle('end_' + wheelDirection);
                    wheelStopTimer = null;
                    wheelDirection = null;
                }, pulseMs);
""",
"""                const direction = ev.deltaY < 0 ? 'zoom_in' : 'zoom_out';
                if (wheelUsesJoystick) {
                    const zoom = direction === 'zoom_in' ? wheelZoomSpeed : -wheelZoomSpeed;
                    handle('joystick', {pan:0, tilt:0, zoom, speed:wheelZoomSpeed});
                    wheelDirection = direction;
                    if (wheelStopTimer) clearTimeout(wheelStopTimer);
                    wheelStopTimer = setTimeout(() => {
                        handle('joystick_stop');
                        wheelStopTimer = null;
                        wheelDirection = null;
                    }, pulseMs);
                } else {
                    if (wheelStopTimer && wheelDirection !== direction) {
                        clearTimeout(wheelStopTimer);
                        handle('end_' + wheelDirection);
                        wheelStopTimer = null;
                    }
                    if (!wheelStopTimer || wheelDirection !== direction) {
                        handle('start_' + direction);
                    }
                    wheelDirection = direction;
                    if (wheelStopTimer) clearTimeout(wheelStopTimer);
                    wheelStopTimer = setTimeout(() => {
                        handle('end_' + wheelDirection);
                        wheelStopTimer = null;
                        wheelDirection = null;
                    }, pulseMs);
                }
""")
replace_once(JS,
"""        const fixedRadius = Math.max(40, Number(this.config.ptz.joystick_radius || 115));
        const fixedDiameter = fixedRadius * 2;
""",
"""        const fixedRadius = Math.max(40, Number(this.config.ptz.joystick_radius ?? 115));
        const fixedDiameter = fixedRadius * 2;
        const zoomEntity = String(this.config.ptz.zoom_entity || '').trim();
        const showZoomSlider = Boolean(zoomEntity && this.config.ptz.zoom_slider !== false);
        const zoomSliderOrientation = String(this.config.ptz.zoom_slider_orientation || 'vertical').toLowerCase();
""")
replace_once(JS,
"""                .ptz-home { position:relative; width:40px; height:40px; background:rgba(0,0,0,.3); border-radius:4px; align-self:center; display:${hasHome ? 'block' : 'none'}; }
""",
"""                .ptz-home { position:relative; width:40px; height:40px; background:rgba(0,0,0,.3); border-radius:4px; align-self:center; display:${hasHome ? 'block' : 'none'}; }
                .ptz-zoom-slider { display:${showZoomSlider ? 'flex' : 'none'}; align-items:center; justify-content:center; gap:6px; padding:7px 6px; border-radius:6px; background:rgba(0,0,0,.3); color:white; font-size:12px; }
                .ptz-zoom-slider.vertical { flex-direction:column; min-height:150px; }
                .ptz-zoom-slider.horizontal { flex-direction:row; min-width:170px; }
                .ptz-zoom-slider input { accent-color:var(--primary-color); cursor:pointer; }
                .ptz-zoom-slider.vertical input { width:120px; transform:rotate(-90deg); margin:48px -42px; }
                .ptz-zoom-slider.horizontal input { width:120px; }
                .ptz-zoom-value { min-width:34px; text-align:center; font-variant-numeric:tabular-nums; }
""")
replace_once(JS,
"""                <div class=\"ptz-zoom\"><ha-icon class=\"zoom_in\" icon=\"mdi:plus\"></ha-icon><ha-icon class=\"zoom_out\" icon=\"mdi:minus\"></ha-icon></div>
                <div class=\"ptz-home\"><ha-icon class=\"home\" icon=\"mdi:home\"></ha-icon></div>
""",
"""                <div class=\"ptz-zoom\"><ha-icon class=\"zoom_in\" icon=\"mdi:plus\"></ha-icon><ha-icon class=\"zoom_out\" icon=\"mdi:minus\"></ha-icon></div>
                <div class=\"ptz-zoom-slider ${zoomSliderOrientation === 'horizontal' ? 'horizontal' : 'vertical'}\">
                    <ha-icon icon=\"mdi:magnify\"></ha-icon>
                    <input class=\"ptz-zoom-range\" type=\"range\" min=\"0\" max=\"100\" step=\"1\" value=\"0\">
                    <span class=\"ptz-zoom-value\">0%</span>
                </div>
                <div class=\"ptz-home\"><ha-icon class=\"home\" icon=\"mdi:home\"></ha-icon></div>
""")
replace_once(JS,
"""        const isDigitallyZoomed = () => Boolean(this.digitalPTZ && this.digitalPTZ.transform && this.digitalPTZ.transform.scale > 1.001);

        if (joystickEnabled) {
""",
"""        const isDigitallyZoomed = () => Boolean(this.digitalPTZ && this.digitalPTZ.transform && this.digitalPTZ.transform.scale > 1.001);

        if (showZoomSlider) {
            const range = this.querySelector('.ptz-zoom-range');
            const label = this.querySelector('.ptz-zoom-value');
            let sliderActive = false;
            let lastSent = null;
            const updateZoomSlider = () => {
                const state = this.hass?.states?.[zoomEntity];
                if (!state) return;
                const value = Number(state.state);
                if (!Number.isFinite(value)) return;
                const min = Number(state.attributes?.min ?? 0);
                const max = Number(state.attributes?.max ?? 100);
                const step = Number(state.attributes?.step ?? 1);
                range.min = String(Number.isFinite(min) ? min : 0);
                range.max = String(Number.isFinite(max) ? max : 100);
                range.step = String(Number.isFinite(step) && step > 0 ? step : 1);
                if (!sliderActive) range.value = String(value);
                label.textContent = `${Math.round(value)}%`;
            };
            this.onhass.push(updateZoomSlider);
            updateZoomSlider();
            const sendZoom = value => {
                const numeric = Number(value);
                if (!Number.isFinite(numeric) || numeric === lastSent) return;
                lastSent = numeric;
                this.hass.callService('number', 'set_value', {entity_id: zoomEntity, value: numeric})
                    .catch(err => console.error('WebRTC PTZ zoom slider service call failed', err));
            };
            range.addEventListener('pointerdown', ev => { sliderActive = true; ev.stopPropagation(); });
            range.addEventListener('input', ev => {
                const value = Number(ev.target.value);
                label.textContent = `${Math.round(value)}%`;
            });
            range.addEventListener('change', ev => sendZoom(ev.target.value));
            const finishSlider = ev => {
                if (!sliderActive) return;
                sliderActive = false;
                sendZoom(range.value);
                ev?.stopPropagation?.();
            };
            range.addEventListener('pointerup', finishSlider);
            range.addEventListener('pointercancel', finishSlider);
            range.addEventListener('click', ev => ev.stopPropagation());
        }

        if (joystickEnabled) {
""")

manifest = MANIFEST.read_text(encoding='utf-8')
new_manifest = manifest.replace('"version": "3.6.2.14"', '"version": "3.6.3"')
if new_manifest == manifest:
    raise RuntimeError('Manifest version replacement failed')
MANIFEST.write_text(new_manifest, encoding='utf-8')
