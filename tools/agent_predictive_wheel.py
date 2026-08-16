from pathlib import Path

js = Path('custom_components/webrtc/www/webrtc-camera.js')
text = js.read_text()

# Expose a lightweight absolute-zoom controller to the wheel handler. It reuses
# the slider's optimistic pendingTarget without transmitting every virtual update.
text = text.replace(
    '        let entityWheelZoom = null;\n',
    '        let entityWheelZoom = null;\n        let predictiveWheelZoom = null;\n',
    1,
)

needle = """                }, wheelSettleMs);\n            };\n        }\n\n        if (joystickEnabled) {\n"""
replacement = """                }, wheelSettleMs);\n            };\n\n            predictiveWheelZoom = {\n                getPosition: () => {\n                    const state = this.hass?.states?.[zoomEntity];\n                    const reported = Number(state?.state);\n                    if (!Number.isFinite(reported)) return null;\n                    const min = Number(state.attributes?.min ?? 0);\n                    const max = Number(state.attributes?.max ?? 100);\n                    return {\n                        value: pendingTarget !== null ? pendingTarget : reported,\n                        reported,\n                        min: Number.isFinite(min) ? min : 0,\n                        max: Number.isFinite(max) ? max : 100,\n                    };\n                },\n                showTarget: value => {\n                    const numeric = Number(value);\n                    if (!Number.isFinite(numeric)) return;\n                    pendingTarget = numeric;\n                    pendingUntil = Date.now() + syncTimeoutMs;\n                    range.value = String(numeric);\n                    label.textContent = `${Math.round(numeric)}%`;\n                },\n                sendTarget: value => sendZoom(value),\n            };\n        }\n\n        if (joystickEnabled) {\n"""
if needle not in text:
    raise SystemExit('slider insertion point not found')
text = text.replace(needle, replacement, 1)

start_marker = "        // Desktop wheel arbitration: physical optical zoom while unzoomed;\n"
end_marker = "        for (const [startEvent, endEvent] of [['touchstart','touchend'],['mousedown','mouseup']]) {\n"
start = text.index(start_marker)
end = text.index(end_marker, start)

wheel_block = r'''        // Desktop wheel arbitration: physical optical zoom while unzoomed;
        // Ctrl+wheel enters DigitalPTZ, and once digitally zoomed the wheel
        // remains digital regardless of whether Ctrl stays pressed. Pinch remains
        // handled by DigitalPTZ and is always digital.
        const hasLegacyPhysicalWheelZoom = Boolean(
            this.config.ptz.data_start_zoom_in && this.config.ptz.data_end_zoom_in &&
            this.config.ptz.data_start_zoom_out && this.config.ptz.data_end_zoom_out
        );
        const hasContinuousZoom = Boolean(
            this.config.ptz.service &&
            this.config.ptz.data_joystick &&
            this.config.ptz.data_joystick_stop
        );
        const hasPhysicalWheelZoom = showZoomSlider || hasContinuousZoom || hasLegacyPhysicalWheelZoom;
        if (hasPhysicalWheelZoom) {
            let wheelStopTimer = null;
            let wheelDirection = null;
            let wheelIntensity = 0;
            let lastWheelEvent = 0;
            let lastVelocitySend = 0;
            let lastVelocitySpeed = 0;

            const pulseMs = Math.max(80, Number(this.config.ptz.wheel_zoom_pulse_ms ?? 300));
            const requestedWheelMode = String(this.config.ptz.wheel_zoom_mode ?? (hasContinuousZoom ? 'velocity' : 'absolute')).toLowerCase();
            const wheelMode = (requestedWheelMode === 'predictive' || requestedWheelMode === 'target') && showZoomSlider
                ? 'predictive'
                : requestedWheelMode === 'velocity' && !hasContinuousZoom && showZoomSlider
                    ? 'absolute'
                    : requestedWheelMode;
            const velocityWheel = wheelMode === 'velocity' && hasContinuousZoom;
            const predictiveWheel = wheelMode === 'predictive' && Boolean(predictiveWheelZoom);

            const configuredMinWheelSpeed = Number(this.config.ptz.wheel_zoom_min_speed ?? 0.08);
            const configuredMaxWheelSpeed = Number(this.config.ptz.wheel_zoom_max_speed ?? 1.0);
            const minWheelSpeed = Math.max(0, Math.min(1, Number.isFinite(configuredMinWheelSpeed) ? configuredMinWheelSpeed : 0.08));
            const maxWheelSpeed = Math.max(minWheelSpeed, Math.min(1, Number.isFinite(configuredMaxWheelSpeed) ? configuredMaxWheelSpeed : 1.0));
            const wheelExpo = Math.max(0.2, Number(this.config.ptz.wheel_zoom_expo ?? this.config.ptz.wheel_zoom_curve ?? 1.6));
            const wheelRamp = Math.max(0.01, Math.min(1, Number(this.config.ptz.wheel_zoom_ramp ?? 0.35)));
            const wheelDeltaReference = Math.max(1, Number(this.config.ptz.wheel_zoom_delta_reference ?? 120));
            const wheelCadenceMs = Math.max(16, Number(this.config.ptz.wheel_zoom_cadence_ms ?? 120));
            const velocityUpdateMs = Math.max(30, Number(this.config.ptz.wheel_zoom_velocity_update_ms ?? 80));
            const fixedWheelSpeed = Math.max(0, Math.min(1, Number(this.config.ptz.wheel_zoom_speed ?? 0.20)));

            // Predictive absolute-position model. Wheel cadence becomes positional
            // intent; the camera receives a sparse DRIVE -> optional RE-DRIVE -> FINAL
            // sequence while the slider follows the virtual final target optimistically.
            const predictiveGain = Math.max(0.01, Number(this.config.ptz.wheel_zoom_target_gain ?? 0.5));
            const predictiveMeasureMs = Math.max(10, Number(this.config.ptz.wheel_zoom_measure_ms ?? 50));
            const predictiveSettleMs = Math.max(80, Number(this.config.ptz.wheel_zoom_target_settle_ms ?? 350));
            const predictiveLookMin = Math.max(0, Number(this.config.ptz.wheel_zoom_lookahead_min ?? 5));
            const predictiveLookMax = Math.max(predictiveLookMin, Number(this.config.ptz.wheel_zoom_lookahead_max ?? 100));
            const predictiveFullRate = Math.max(1, Number(this.config.ptz.wheel_zoom_full_rate ?? 80));
            const predictiveExpo = Math.max(0.05, Number(this.config.ptz.wheel_zoom_lookahead_expo ?? 0.3));
            const predictiveSmoothing = Math.max(0.01, Math.min(1, Number(this.config.ptz.wheel_zoom_cadence_smoothing ?? 0.35)));
            const predictiveReverseMs = Math.max(0, Number(this.config.ptz.wheel_zoom_reverse_ms ?? 120));

            let predictiveState = 'idle';
            let predictiveVirtual = null;
            let predictiveDrive = null;
            let predictiveDirection = 0;
            let predictiveLastEvent = 0;
            let predictiveRawRate = 0;
            let predictiveSmoothRate = 0;
            let predictiveMeasureTimer = null;
            let predictiveSettleTimer = null;
            let predictiveRedriveUsed = false;
            let predictiveLastDirectionChange = 0;

            const predictiveClamp = (value, position) => Math.max(position.min, Math.min(position.max, value));
            const predictiveLookahead = rate => {
                const x = Math.max(0, Math.min(1, rate / predictiveFullRate));
                const shaped = 1 - Math.pow(1 - x, predictiveExpo);
                return predictiveLookMin + (predictiveLookMax - predictiveLookMin) * shaped;
            };
            const clearPredictiveTimers = () => {
                if (predictiveMeasureTimer) clearTimeout(predictiveMeasureTimer);
                if (predictiveSettleTimer) clearTimeout(predictiveSettleTimer);
                predictiveMeasureTimer = predictiveSettleTimer = null;
            };
            const resetPredictive = () => {
                clearPredictiveTimers();
                predictiveState = 'idle';
                predictiveVirtual = predictiveDrive = null;
                predictiveDirection = 0;
                predictiveLastEvent = 0;
                predictiveRawRate = predictiveSmoothRate = 0;
                predictiveRedriveUsed = false;
            };
            const launchPredictive = () => {
                if (predictiveState !== 'measuring' || predictiveVirtual === null) return;
                const position = predictiveWheelZoom?.getPosition();
                if (!position) { resetPredictive(); return; }
                const look = predictiveLookahead(predictiveSmoothRate || predictiveRawRate || 0);
                predictiveDrive = predictiveClamp(predictiveVirtual + predictiveDirection * look, position);
                predictiveWheelZoom.sendTarget(predictiveDrive);
                predictiveState = 'active';
            };
            const finishPredictive = () => {
                if (predictiveState === 'idle' || predictiveVirtual === null) return;
                if (predictiveState === 'measuring') launchPredictive();
                predictiveWheelZoom?.showTarget(predictiveVirtual);
                predictiveWheelZoom?.sendTarget(predictiveVirtual);
                resetPredictive();
            };
            const startPredictive = (now, direction) => {
                const position = predictiveWheelZoom?.getPosition();
                if (!position) return false;
                clearPredictiveTimers();
                predictiveState = 'measuring';
                predictiveVirtual = position.value;
                predictiveDrive = null;
                predictiveDirection = direction;
                predictiveLastEvent = 0;
                predictiveRawRate = predictiveSmoothRate = 0;
                predictiveRedriveUsed = false;
                predictiveLastDirectionChange = now;
                predictiveMeasureTimer = setTimeout(launchPredictive, predictiveMeasureMs);
                return true;
            };

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
                    if (predictiveWheel && predictiveState !== 'idle') finishPredictive();
                    const zoom = 1 - ev.deltaY / 1000;
                    this.digitalPTZ.transform.zoomAtCoords(zoom, ev.pageX, ev.pageY);
                    this.digitalPTZ.render();
                    ev.preventDefault();
                    ev.stopPropagation();
                    return;
                }

                const direction = ev.deltaY < 0 ? 'zoom_in' : 'zoom_out';
                if (predictiveWheel) {
                    const now = performance.now();
                    const dir = direction === 'zoom_in' ? 1 : -1;
                    if (predictiveState === 'idle' && !startPredictive(now, dir)) return;

                    if (dir !== predictiveDirection && now - predictiveLastDirectionChange >= predictiveReverseMs) {
                        // Finish the old intended target, then treat reversal as a new gesture.
                        finishPredictive();
                        if (!startPredictive(now, dir)) return;
                    }

                    const dt = predictiveLastEvent ? Math.max(1, now - predictiveLastEvent) : 0;
                    if (dt) {
                        predictiveRawRate = 1000 / dt;
                        predictiveSmoothRate = predictiveSmoothRate
                            ? predictiveSmoothRate + (predictiveRawRate - predictiveSmoothRate) * predictiveSmoothing
                            : predictiveRawRate;
                    } else {
                        predictiveRawRate = 0;
                    }

                    const position = predictiveWheelZoom.getPosition();
                    if (!position) { resetPredictive(); return; }
                    predictiveVirtual = predictiveClamp(predictiveVirtual + dir * predictiveGain, position);
                    predictiveWheelZoom.showTarget(predictiveVirtual);

                    // If the accumulated virtual target catches the original drive target,
                    // allow exactly one re-drive based on the now-current cadence. This
                    // restores headroom without falling back into incremental final sends.
                    if (predictiveState === 'active' && !predictiveRedriveUsed && predictiveDrive !== null) {
                        const caught = predictiveDirection > 0
                            ? predictiveVirtual >= predictiveDrive
                            : predictiveVirtual <= predictiveDrive;
                        if (caught && predictiveVirtual > position.min && predictiveVirtual < position.max) {
                            const look = predictiveLookahead(predictiveSmoothRate || predictiveRawRate || 0);
                            const newDrive = predictiveClamp(predictiveVirtual + predictiveDirection * look, position);
                            if (Math.abs(newDrive - predictiveDrive) >= 0.5) {
                                predictiveDrive = newDrive;
                                predictiveRedriveUsed = true;
                                predictiveWheelZoom.sendTarget(predictiveDrive);
                            }
                        }
                    }

                    predictiveLastEvent = now;
                    if (predictiveSettleTimer) clearTimeout(predictiveSettleTimer);
                    predictiveSettleTimer = setTimeout(finishPredictive, predictiveSettleMs);
                } else if (velocityWheel) {
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
                    const instantaneous = Math.max(deltaIntensity, cadenceIntensity);
                    if (!hadRecentEvent || reversing) wheelIntensity = instantaneous;
                    else wheelIntensity += (instantaneous - wheelIntensity) * wheelRamp;
                    wheelIntensity = Math.max(0, Math.min(1, wheelIntensity));
                    const shapedIntensity = 1 - Math.pow(1 - wheelIntensity, wheelExpo);
                    const speed = minWheelSpeed + (maxWheelSpeed - minWheelSpeed) * shapedIntensity;
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
                } else if (hasContinuousZoom && fixedWheelSpeed > 0) {
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

text = text[:start] + wheel_block + text[end:]
js.write_text(text)

manifest = Path('custom_components/webrtc/manifest.json')
m = manifest.read_text()
if '"version": "3.6.9"' not in m:
    raise SystemExit('expected 3.6.9 manifest version not found')
manifest.write_text(m.replace('"version": "3.6.9"', '"version": "3.6.10"'))
