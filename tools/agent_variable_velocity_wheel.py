from pathlib import Path

js_path = Path('custom_components/webrtc/www/webrtc-camera.js')
text = js_path.read_text()
old = '''        const hasPhysicalWheelZoom = showZoomSlider || joystickEnabled || hasLegacyPhysicalWheelZoom;
        if (hasPhysicalWheelZoom) {
            let wheelStopTimer = null;
            let wheelDirection = null;
            const pulseMs = Math.max(80, Number(this.config.ptz.wheel_zoom_pulse_ms ?? 300));
            const wheelZoomSpeed = Math.max(0, Math.min(1, Number(this.config.ptz.wheel_zoom_speed ?? 0.20)));
            const wheelUsesJoystick = joystickEnabled && wheelZoomSpeed > 0;
            player.addEventListener('wheel', ev => {
                const digitallyZoomed = isDigitallyZoomed();
                if (this.digitalPTZ && (digitallyZoomed || ev.ctrlKey)) {
                    const zoom = 1 - ev.deltaY / 1000;
                    this.digitalPTZ.transform.zoomAtCoords(zoom, ev.pageX, ev.pageY);
                    this.digitalPTZ.render();
                    ev.preventDefault();
                    ev.stopPropagation();
                    return;
                }

                const direction = ev.deltaY < 0 ? 'zoom_in' : 'zoom_out';
                if (showZoomSlider) {
                    entityWheelZoom?.(direction);
                } else if (wheelUsesJoystick) {
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
                ev.preventDefault();
                ev.stopPropagation();
            }, {passive:false, capture:true});
        }
'''
new = '''        const hasPhysicalWheelZoom = showZoomSlider || joystickEnabled || hasLegacyPhysicalWheelZoom;
        if (hasPhysicalWheelZoom) {
            let wheelStopTimer = null;
            let wheelDirection = null;
            let wheelIntensity = 0;
            let lastWheelEvent = 0;
            let lastVelocitySend = 0;
            let lastVelocitySpeed = 0;
            const pulseMs = Math.max(80, Number(this.config.ptz.wheel_zoom_pulse_ms ?? 300));
            const wheelMode = String(this.config.ptz.wheel_zoom_mode ?? (joystickEnabled ? 'velocity' : 'absolute')).toLowerCase();
            const velocityWheel = wheelMode === 'velocity' && joystickEnabled;
            const configuredMinWheelSpeed = Number(this.config.ptz.wheel_zoom_min_speed ?? 0.08);
            const configuredMaxWheelSpeed = Number(this.config.ptz.wheel_zoom_max_speed ?? 1.0);
            const minWheelSpeed = Math.max(0, Math.min(1, Number.isFinite(configuredMinWheelSpeed) ? configuredMinWheelSpeed : 0.08));
            const maxWheelSpeed = Math.max(minWheelSpeed, Math.min(1, Number.isFinite(configuredMaxWheelSpeed) ? configuredMaxWheelSpeed : 1.0));
            const wheelCurve = Math.max(0.2, Number(this.config.ptz.wheel_zoom_curve ?? 1.6));
            const wheelRamp = Math.max(0.01, Math.min(1, Number(this.config.ptz.wheel_zoom_ramp ?? 0.35)));
            const wheelDeltaReference = Math.max(1, Number(this.config.ptz.wheel_zoom_delta_reference ?? 120));
            const wheelCadenceMs = Math.max(16, Number(this.config.ptz.wheel_zoom_cadence_ms ?? 120));
            const velocityUpdateMs = Math.max(30, Number(this.config.ptz.wheel_zoom_velocity_update_ms ?? 80));
            const fixedWheelSpeed = Math.max(0, Math.min(1, Number(this.config.ptz.wheel_zoom_speed ?? 0.20)));
            const stopVelocityWheel = () => {
                if (wheelStopTimer) clearTimeout(wheelStopTimer);
                wheelStopTimer = null;
                if (wheelDirection !== null) handle('joystick_stop');
                wheelDirection = null;
                wheelIntensity = 0;
                lastWheelEvent = 0;
                lastVelocitySend = 0;
                lastVelocitySpeed = 0;
            };
            player.addEventListener('wheel', ev => {
                const digitallyZoomed = isDigitallyZoomed();
                if (this.digitalPTZ && (digitallyZoomed || ev.ctrlKey)) {
                    if (velocityWheel && wheelDirection !== null) stopVelocityWheel();
                    const zoom = 1 - ev.deltaY / 1000;
                    this.digitalPTZ.transform.zoomAtCoords(zoom, ev.pageX, ev.pageY);
                    this.digitalPTZ.render();
                    ev.preventDefault();
                    ev.stopPropagation();
                    return;
                }

                const direction = ev.deltaY < 0 ? 'zoom_in' : 'zoom_out';
                if (velocityWheel) {
                    const now = performance.now();
                    const reversing = wheelDirection !== null && wheelDirection !== direction;
                    if (reversing) {
                        handle('joystick_stop');
                        wheelIntensity = 0;
                        lastWheelEvent = 0;
                        lastVelocitySend = 0;
                        lastVelocitySpeed = 0;
                    }

                    let delta = Math.abs(Number(ev.deltaY) || 0);
                    if (ev.deltaMode === 1) delta *= 16;
                    else if (ev.deltaMode === 2) delta *= Math.max(400, window.innerHeight || 800);
                    const hadRecentEvent = lastWheelEvent > 0 && now - lastWheelEvent <= Math.max(pulseMs * 2, wheelCadenceMs * 3);
                    const dt = hadRecentEvent ? Math.max(8, now - lastWheelEvent) : wheelCadenceMs;
                    const deltaIntensity = Math.min(1, delta / wheelDeltaReference);
                    const cadenceIntensity = hadRecentEvent ? Math.min(1, wheelCadenceMs / dt) : 0;
                    const instantaneous = Math.min(1, deltaIntensity * cadenceIntensity);
                    if (!hadRecentEvent || reversing) wheelIntensity = 0;
                    wheelIntensity += (instantaneous - wheelIntensity) * wheelRamp;
                    wheelIntensity = Math.max(0, Math.min(1, wheelIntensity));
                    const speed = minWheelSpeed + (maxWheelSpeed - minWheelSpeed) * Math.pow(wheelIntensity, wheelCurve);
                    const zoom = direction === 'zoom_in' ? speed : -speed;
                    const shouldSend = wheelDirection !== direction ||
                        now - lastVelocitySend >= velocityUpdateMs ||
                        Math.abs(speed - lastVelocitySpeed) >= 0.025;
                    if (shouldSend) {
                        handle('joystick', {pan:0, tilt:0, zoom, speed});
                        lastVelocitySend = now;
                        lastVelocitySpeed = speed;
                    }
                    wheelDirection = direction;
                    lastWheelEvent = now;
                    if (wheelStopTimer) clearTimeout(wheelStopTimer);
                    wheelStopTimer = setTimeout(stopVelocityWheel, pulseMs);
                } else if (wheelMode === 'absolute' && showZoomSlider) {
                    entityWheelZoom?.(direction);
                } else if (joystickEnabled && fixedWheelSpeed > 0) {
                    const zoom = direction === 'zoom_in' ? fixedWheelSpeed : -fixedWheelSpeed;
                    handle('joystick', {pan:0, tilt:0, zoom, speed:fixedWheelSpeed});
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
                ev.preventDefault();
                ev.stopPropagation();
            }, {passive:false, capture:true});
        }
'''
if old not in text:
    raise SystemExit('wheel block not found')
text = text.replace(old, new, 1)
js_path.write_text(text)

manifest = Path('custom_components/webrtc/manifest.json')
mtext = manifest.read_text()
if '"version": "3.6.6"' not in mtext:
    raise SystemExit('expected 3.6.6 manifest version')
manifest.write_text(mtext.replace('"version": "3.6.6"', '"version": "3.6.7"', 1))
