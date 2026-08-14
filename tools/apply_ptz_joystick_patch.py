from pathlib import Path

p = Path('custom_components/webrtc/www/webrtc-camera.js')
s = p.read_text()
start = s.index('    renderPTZ() {')
end = s.index('    saveScreenshot() {', start)
method = r'''    renderPTZ() {
        if (!this.config.ptz || !this.config.ptz.service) return;

        const joystickEnabled = Boolean(
            this.config.ptz.joystick &&
            this.config.ptz.data_joystick &&
            this.config.ptz.data_joystick_stop
        );
        let hasMove = joystickEnabled;
        let hasZoom = false;
        let hasHome = false;
        for (const prefix of ['', '_start', '_end', '_long']) {
            hasMove = hasMove || this.config.ptz['data' + prefix + '_right'];
            hasMove = hasMove || this.config.ptz['data' + prefix + '_left'];
            hasMove = hasMove || this.config.ptz['data' + prefix + '_up'];
            hasMove = hasMove || this.config.ptz['data' + prefix + '_down'];

            hasZoom = hasZoom || this.config.ptz['data' + prefix + '_zoom_in'];
            hasZoom = hasZoom || this.config.ptz['data' + prefix + '_zoom_out'];

            hasHome = hasHome || this.config.ptz['data' + prefix + '_home'];
        }

        const card = this.querySelector('.card');
        card.insertAdjacentHTML('beforebegin', `
            <style>
                .ptz {
                    position: absolute;
                    top: 50%;
                    right: 10px;
                    transform: translateY(-50%);
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                    transition: opacity .3s ease-in-out;
                    opacity: ${parseFloat(this.config.ptz.opacity) || 0.4};
                    z-index: 4;
                }
                .ptz:hover {
                    opacity: 1 !important;
                }
                .ptz-move {
                    position: relative;
                    background-color: rgba(0, 0, 0, 0.3);
                    border-radius: 50%;
                    width: 80px;
                    height: 80px;
                    display: ${hasMove ? 'block' : 'none'};
                    touch-action: none;
                    user-select: none;
                }
                .ptz-move.joystick {
                    box-sizing: border-box;
                    border: 1px solid rgba(255, 255, 255, 0.28);
                    cursor: grab;
                }
                .ptz-move.joystick:active {
                    cursor: grabbing;
                }
                .ptz-stick {
                    position: absolute;
                    width: 28px;
                    height: 28px;
                    left: 26px;
                    top: 26px;
                    box-sizing: border-box;
                    border-radius: 50%;
                    border: 1px solid rgba(255, 255, 255, 0.7);
                    background-color: rgba(0, 0, 0, 0.45);
                    pointer-events: none;
                    transform: translate(0, 0);
                    transition: transform 60ms linear;
                }
                .ptz-centre {
                    position: absolute;
                    width: 4px;
                    height: 4px;
                    left: 38px;
                    top: 38px;
                    border-radius: 50%;
                    background-color: rgba(255, 255, 255, 0.65);
                    pointer-events: none;
                }
                .ptz-zoom {
                    position: relative;
                    width: 80px;
                    height: 40px;
                    background-color: rgba(0, 0, 0, 0.3);
                    border-radius: 4px;
                    display: ${hasZoom ? 'block' : 'none'};
                }
                .ptz-home {
                    position: relative;
                    width: 40px;
                    height: 40px;
                    background-color: rgba(0, 0, 0, 0.3);
                    border-radius: 4px;
                    align-self: center;
                    display: ${hasHome ? 'block' : 'none'};
                }
                .up { position: absolute; top: 5px; left: 50%; transform: translateX(-50%); }
                .down { position: absolute; bottom: 5px; left: 50%; transform: translateX(-50%); }
                .left { position: absolute; left: 5px; top: 50%; transform: translateY(-50%); }
                .right { position: absolute; right: 5px; top: 50%; transform: translateY(-50%); }
                .zoom_out { position: absolute; left: 5px; top: 50%; transform: translateY(-50%); }
                .zoom_in { position: absolute; right: 5px; top: 50%; transform: translateY(-50%); }
                .home { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); }
            </style>
        `);
        card.insertAdjacentHTML('beforeend', `
            <div class="ptz">
                <div class="ptz-move ${joystickEnabled ? 'joystick' : ''}">
                    ${joystickEnabled ? `
                        <div class="ptz-centre"></div>
                        <div class="ptz-stick"></div>
                    ` : `
                        <ha-icon class="right" icon="mdi:arrow-right"></ha-icon>
                        <ha-icon class="left" icon="mdi:arrow-left"></ha-icon>
                        <ha-icon class="up" icon="mdi:arrow-up"></ha-icon>
                        <ha-icon class="down" icon="mdi:arrow-down"></ha-icon>
                    `}
                </div>
                <div class="ptz-zoom">
                    <ha-icon class="zoom_in" icon="mdi:plus"></ha-icon>
                    <ha-icon class="zoom_out" icon="mdi:minus"></ha-icon>
                </div>
                <div class="ptz-home">
                    <ha-icon class="home" icon="mdi:home"></ha-icon>
                </div>
            </div>
        `);

        const template = JSON.stringify(this.config.ptz);
        const handle = (path, vars = {}) => {
            if (!this.config.ptz['data_' + path]) return;
            const pan = Number(vars.pan || 0);
            const tilt = Number(vars.tilt || 0);
            const zoom = Number(vars.zoom || 0);
            const speed = Number(vars.speed || Math.hypot(pan, tilt));
            const config = template.indexOf('${') < 0 ? this.config.ptz : JSON.parse(eval('`' + template + '`'));
            const [domain, service] = config.service.split('.', 2);
            const data = config['data_' + path];
            this.hass.callService(domain, service, data);
        };

        const ptz = this.querySelector('.ptz');

        if (joystickEnabled) {
            const move = this.querySelector('.ptz-move');
            const stick = this.querySelector('.ptz-stick');
            const deadzone = Math.max(0, Math.min(0.8, parseFloat(this.config.ptz.joystick_deadzone) || 0.16));
            const minSpeed = Math.max(0, Math.min(1, parseFloat(this.config.ptz.joystick_min_speed) || 0.12));
            const curve = Math.max(0.2, parseFloat(this.config.ptz.joystick_curve) || 1.35);
            const updateMs = Math.max(40, parseInt(this.config.ptz.joystick_update_ms) || 120);
            let activePointer = null;
            let moving = false;
            let lastSend = 0;
            let lastPan = 0;
            let lastTilt = 0;

            const resetStick = () => {
                stick.style.transform = 'translate(0px, 0px)';
            };

            const stopMove = () => {
                if (moving) handle('joystick_stop');
                moving = false;
                lastPan = 0;
                lastTilt = 0;
                resetStick();
            };

            const updateJoystick = (ev, force = false) => {
                const rect = move.getBoundingClientRect();
                const dx = ev.clientX - (rect.left + rect.width / 2);
                const dy = ev.clientY - (rect.top + rect.height / 2);
                const maxDistance = Math.max(1, rect.width / 2 - 14);
                const distance = Math.hypot(dx, dy);
                const visualScale = Math.min(1, distance / maxDistance);
                const visualX = distance ? dx / distance * maxDistance * visualScale : 0;
                const visualY = distance ? dy / distance * maxDistance * visualScale : 0;
                stick.style.transform = `translate(${visualX.toFixed(1)}px, ${visualY.toFixed(1)}px)`;

                const radial = Math.min(1, distance / maxDistance);
                if (radial <= deadzone || distance === 0) {
                    if (moving) {
                        handle('joystick_stop');
                        moving = false;
                        lastPan = 0;
                        lastTilt = 0;
                    }
                    return;
                }

                const normalized = Math.min(1, (radial - deadzone) / (1 - deadzone));
                const magnitude = minSpeed + (1 - minSpeed) * Math.pow(normalized, curve);
                const pan = dx / distance * magnitude;
                const tilt = -dy / distance * magnitude;
                const now = performance.now();
                const changed = Math.hypot(pan - lastPan, tilt - lastTilt) >= 0.04;
                if (force || (changed && now - lastSend >= updateMs)) {
                    handle('joystick', {pan, tilt, zoom: 0, speed: magnitude});
                    lastSend = now;
                    lastPan = pan;
                    lastTilt = tilt;
                    moving = true;
                }
            };

            move.addEventListener('pointerdown', ev => {
                if (ev.pointerType === 'mouse' && ev.button !== 0) return;
                ev.preventDefault();
                ev.stopPropagation();
                activePointer = ev.pointerId;
                move.setPointerCapture(ev.pointerId);
                updateJoystick(ev, true);
            });
            move.addEventListener('pointermove', ev => {
                if (activePointer !== ev.pointerId) return;
                ev.preventDefault();
                ev.stopPropagation();
                updateJoystick(ev);
            });
            const finish = ev => {
                if (activePointer !== null && ev.pointerId !== activePointer) return;
                ev.preventDefault();
                ev.stopPropagation();
                activePointer = null;
                stopMove();
            };
            move.addEventListener('pointerup', finish);
            move.addEventListener('pointercancel', finish);
            move.addEventListener('lostpointercapture', ev => {
                if (activePointer === ev.pointerId) {
                    activePointer = null;
                    stopMove();
                }
            });
        }

        // Keep the legacy buttons for zoom/home and for non-joystick PTZ configs.
        for (const [startEvent, endEvent] of [['touchstart', 'touchend'], ['mousedown', 'mouseup']]) {
            ptz.addEventListener(startEvent, startEvt => {
                if (joystickEnabled && startEvt.target.closest?.('.ptz-move')) return;
                const {className} = startEvt.target;
                startEvt.preventDefault();
                handle('start_' + className);
                window.addEventListener(endEvent, endEvt => {
                    endEvt.preventDefault();
                    handle('end_' + className);
                    if (endEvt.timeStamp - startEvt.timeStamp > 400) {
                        handle('long_' + className);
                    } else {
                        handle(className);
                    }
                }, {once: true});
            });
        }
    }

'''
s = s[:start] + method + s[end:]
p.write_text(s)

manifest = Path('custom_components/webrtc/manifest.json')
m = manifest.read_text()
m = m.replace('"version": "v3.6.2-nav.5"', '"version": "v3.6.2-nav.6"', 1)
manifest.write_text(m)
