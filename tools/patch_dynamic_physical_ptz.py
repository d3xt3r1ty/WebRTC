from pathlib import Path
import re

root = Path('custom_components/webrtc')
js = root / 'www/webrtc-camera.js'
s = js.read_text()

s = s.replace("        new DigitalPTZ(\n", "        this.digitalPTZ = new DigitalPTZ(\n", 1)

new_func = r'''    renderPTZ() {
        if (!this.config.ptz || !this.config.ptz.service) return;

        const joystickEnabled = Boolean(
            this.config.ptz.joystick &&
            this.config.ptz.data_joystick &&
            this.config.ptz.data_joystick_stop
        );
        const physicalDrag = joystickEnabled && this.config.ptz.physical_drag !== false;
        const joystickMode = String(this.config.ptz.joystick_mode || 'dynamic').toLowerCase();
        const dynamicJoystick = physicalDrag && joystickMode === 'dynamic';
        const keyboardEnabled = joystickEnabled && this.config.ptz.keyboard !== false;

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

        const handle = (path, vars = {}) => {
            const dataTemplate = this.config.ptz['data_' + path];
            if (!dataTemplate) return;
            const pan = Number(vars.pan || 0);
            const tilt = Number(vars.tilt || 0);
            const zoom = Number(vars.zoom || 0);
            const speed = Number(vars.speed || Math.hypot(pan, tilt));
            const substitute = value => {
                if (typeof value === 'string') return value
                    .replaceAll('${pan}', String(pan))
                    .replaceAll('${tilt}', String(tilt))
                    .replaceAll('${zoom}', String(zoom))
                    .replaceAll('${speed}', String(speed));
                if (Array.isArray(value)) return value.map(substitute);
                if (value && typeof value === 'object') return Object.fromEntries(
                    Object.entries(value).map(([key, item]) => [key, substitute(item)])
                );
                return value;
            };
            const [domain, service] = String(this.config.ptz.service).split('.', 2);
            if (!domain || !service) return console.error('WebRTC PTZ: invalid service', this.config.ptz.service);
            const data = substitute(dataTemplate);
            this.hass.callService(domain, service, data).catch(err =>
                console.error(`WebRTC PTZ ${path} service call failed`, err, data));
        };

        const card = this.querySelector('.card');
        const player = this.querySelector('.player');
        const position = String(this.config.ptz.position || (dynamicJoystick ? 'center-right' : 'center-right')).toLowerCase();
        const offsetX = Number(this.config.ptz.offset_x ?? 10);
        const offsetY = Number(this.config.ptz.offset_y ?? 10);
        const anchors = {
            'top-left': `top:${offsetY}px;left:${offsetX}px;`,
            'top-center': `top:${offsetY}px;left:50%;transform:translateX(-50%);`,
            'top-right': `top:${offsetY}px;right:${offsetX}px;`,
            'center-left': `top:50%;left:${offsetX}px;transform:translateY(-50%);`,
            'center': 'top:50%;left:50%;transform:translate(-50%,-50%);',
            'center-right': `top:50%;right:${offsetX}px;transform:translateY(-50%);`,
            'bottom-left': `bottom:${offsetY}px;left:${offsetX}px;`,
            'bottom-center': `bottom:${offsetY}px;left:50%;transform:translateX(-50%);`,
            'bottom-right': `bottom:${offsetY}px;right:${offsetX}px;`,
        };
        const anchorCSS = anchors[position] || anchors['center-right'];
        const fixedRadius = Math.max(40, Number(this.config.ptz.joystick_radius || 60));
        const fixedDiameter = fixedRadius * 2;

        card.insertAdjacentHTML('beforebegin', `
            <style>
                .ptz { position:absolute; ${anchorCSS} display:flex; flex-direction:column; gap:10px; transition:opacity .3s ease-in-out; opacity:${parseFloat(this.config.ptz.opacity) || 0.4}; z-index:4; }
                .ptz:hover { opacity:1 !important; }
                .ptz-move { position:relative; background:rgba(0,0,0,.3); border-radius:50%; width:${fixedDiameter}px; height:${fixedDiameter}px; display:${hasMove && !dynamicJoystick ? 'block' : 'none'}; touch-action:none; user-select:none; box-sizing:border-box; }
                .ptz-move.joystick { border:1px solid rgba(255,255,255,.28); cursor:grab; }
                .ptz-stick { position:absolute; width:30px; height:30px; left:50%; top:50%; margin:-15px 0 0 -15px; border:1px solid rgba(255,255,255,.7); background:rgba(0,0,0,.45); border-radius:50%; pointer-events:none; }
                .ptz-centre { position:absolute; width:6px; height:6px; left:50%; top:50%; margin:-3px; border-radius:50%; background:rgba(255,255,255,.65); pointer-events:none; }
                .ptz-dynamic { position:absolute; display:none; border:1px solid rgba(255,255,255,.4); background:rgba(0,0,0,.18); border-radius:50%; box-sizing:border-box; z-index:5; pointer-events:none; }
                .ptz-dynamic .ptz-stick { transition:transform 40ms linear; }
                .ptz-deadband { position:absolute; left:50%; top:50%; border:1px dashed rgba(255,255,255,.32); border-radius:50%; transform:translate(-50%,-50%); pointer-events:none; }
                .ptz-zoom { position:relative; width:80px; height:40px; background:rgba(0,0,0,.3); border-radius:4px; display:${hasZoom ? 'block' : 'none'}; }
                .ptz-home { position:relative; width:40px; height:40px; background:rgba(0,0,0,.3); border-radius:4px; align-self:center; display:${hasHome ? 'block' : 'none'}; }
                .up { position:absolute; top:5px; left:50%; transform:translateX(-50%); }.down { position:absolute; bottom:5px; left:50%; transform:translateX(-50%); }.left { position:absolute; left:5px; top:50%; transform:translateY(-50%); }.right { position:absolute; right:5px; top:50%; transform:translateY(-50%); }
                .zoom_out { position:absolute; left:5px; top:50%; transform:translateY(-50%); }.zoom_in { position:absolute; right:5px; top:50%; transform:translateY(-50%); }.home { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); }
            </style>`);
        card.insertAdjacentHTML('beforeend', `
            <div class="ptz">
                <div class="ptz-move ${joystickEnabled ? 'joystick' : ''}">${joystickEnabled ? '<div class="ptz-centre"></div><div class="ptz-stick"></div>' : '<ha-icon class="right" icon="mdi:arrow-right"></ha-icon><ha-icon class="left" icon="mdi:arrow-left"></ha-icon><ha-icon class="up" icon="mdi:arrow-up"></ha-icon><ha-icon class="down" icon="mdi:arrow-down"></ha-icon>'}</div>
                <div class="ptz-zoom"><ha-icon class="zoom_in" icon="mdi:plus"></ha-icon><ha-icon class="zoom_out" icon="mdi:minus"></ha-icon></div>
                <div class="ptz-home"><ha-icon class="home" icon="mdi:home"></ha-icon></div>
            </div>
            <div class="ptz-dynamic"><div class="ptz-deadband"></div><div class="ptz-centre"></div><div class="ptz-stick"></div></div>`);

        const ptz = this.querySelector('.ptz');
        const fixedMove = this.querySelector('.ptz-move');
        const dynamicMove = this.querySelector('.ptz-dynamic');
        const isDigitallyZoomed = () => Boolean(this.digitalPTZ && this.digitalPTZ.transform && this.digitalPTZ.transform.scale > 1.001);

        if (joystickEnabled) {
            const surface = dynamicJoystick ? player : fixedMove;
            let activePointer = null, originX = 0, originY = 0, moving = false;
            let lastPan = 0, lastTilt = 0, lastSpeed = 0, lastSend = 0, heartbeat = null;
            let radius = fixedRadius, deadbandPx = 14;
            const updateMs = Math.max(40, parseInt(this.config.ptz.joystick_update_ms) || 100);
            const heartbeatMs = Math.max(250, parseInt(this.config.ptz.joystick_heartbeat_ms) || 600);
            const minSpeed = Math.max(0, Math.min(1, parseFloat(this.config.ptz.joystick_min_speed) || 0.12));
            const curve = Math.max(0.2, parseFloat(this.config.ptz.joystick_curve) || 1.35);

            const hideDynamic = () => { if (dynamicJoystick) dynamicMove.style.display = 'none'; };
            const stopMove = () => {
                if (heartbeat) clearInterval(heartbeat);
                heartbeat = null;
                if (moving) handle('joystick_stop');
                moving = false; lastPan = lastTilt = lastSpeed = 0;
                const stick = (dynamicJoystick ? dynamicMove : fixedMove).querySelector('.ptz-stick');
                if (stick) stick.style.transform = 'translate(0px,0px)';
                hideDynamic();
            };
            const startHeartbeat = () => {
                if (heartbeat) return;
                heartbeat = setInterval(() => {
                    if (activePointer === null || !moving) return;
                    handle('joystick', {pan:lastPan, tilt:lastTilt, zoom:0, speed:lastSpeed});
                    lastSend = performance.now();
                }, heartbeatMs);
            };
            const begin = ev => {
                if (ev.pointerType === 'mouse' && ev.button !== 0) return;
                if (dynamicJoystick && isDigitallyZoomed()) return;
                activePointer = ev.pointerId;
                originX = ev.clientX; originY = ev.clientY;
                radius = Math.max(40, Number(ev.pointerType === 'touch' ? (this.config.ptz.joystick_radius_touch || 90) : (this.config.ptz.joystick_radius || 60)));
                deadbandPx = Math.max(4, Number(ev.pointerType === 'touch' ? (this.config.ptz.joystick_deadband_touch || 24) : (this.config.ptz.joystick_deadband || 14)));
                if (dynamicJoystick) {
                    const rect = player.getBoundingClientRect();
                    dynamicMove.style.width = `${radius*2}px`; dynamicMove.style.height = `${radius*2}px`;
                    dynamicMove.style.left = `${originX - rect.left}px`; dynamicMove.style.top = `${originY - rect.top}px`;
                    dynamicMove.style.transform = 'translate(-50%,-50%)'; dynamicMove.style.display = 'block';
                    const db = dynamicMove.querySelector('.ptz-deadband'); db.style.width = `${deadbandPx*2}px`; db.style.height = `${deadbandPx*2}px`;
                }
                player.focus({preventScroll:true});
                surface.setPointerCapture?.(ev.pointerId);
                ev.preventDefault(); ev.stopPropagation();
            };
            const move = ev => {
                if (activePointer !== ev.pointerId) return;
                const dx = ev.clientX-originX, dy = ev.clientY-originY, dist = Math.hypot(dx,dy);
                const ctl = dynamicJoystick ? dynamicMove : fixedMove;
                const stick = ctl.querySelector('.ptz-stick');
                const visual = Math.min(radius, dist);
                if (stick) stick.style.transform = dist ? `translate(${(dx/dist*visual).toFixed(1)}px,${(dy/dist*visual).toFixed(1)}px)` : 'translate(0,0)';
                if (dist <= deadbandPx) {
                    if (moving) { handle('joystick_stop'); moving=false; if (heartbeat) clearInterval(heartbeat); heartbeat=null; }
                    ev.preventDefault(); ev.stopPropagation(); return;
                }
                const norm = Math.min(1, (dist-deadbandPx)/Math.max(1,radius-deadbandPx));
                const magnitude = minSpeed + (1-minSpeed)*Math.pow(norm,curve);
                const pan = dx/dist*magnitude, tilt = -dy/dist*magnitude;
                const now=performance.now(), changed=Math.hypot(pan-lastPan,tilt-lastTilt)>=0.03;
                if (!moving || (changed && now-lastSend>=updateMs)) {
                    handle('joystick',{pan,tilt,zoom:0,speed:magnitude});
                    lastPan=pan; lastTilt=tilt; lastSpeed=magnitude; lastSend=now; moving=true; startHeartbeat();
                }
                ev.preventDefault(); ev.stopPropagation();
            };
            const end = ev => {
                if (activePointer === null || ev.pointerId !== activePointer) return;
                activePointer=null; stopMove(); ev.preventDefault(); ev.stopPropagation();
            };
            surface.addEventListener('pointerdown', begin, true);
            surface.addEventListener('pointermove', move, true);
            surface.addEventListener('pointerup', end, true);
            surface.addEventListener('pointercancel', end, true);
            surface.addEventListener('lostpointercapture', ev => { if (activePointer===ev.pointerId) { activePointer=null; stopMove(); } });

            if (keyboardEnabled) {
                if (!player.hasAttribute('tabindex')) player.tabIndex = 0;
                const held = new Set();
                let keyTimer = null, keyStarted = 0, keyLastSend = 0, keyPan = 0, keyTilt = 0;
                const initial = Math.max(0.01, Math.min(1, Number(this.config.ptz.keyboard_initial_speed || 0.12)));
                const maximum = Math.max(initial, Math.min(1, Number(this.config.ptz.keyboard_max_speed || 0.65)));
                const rampMs = Math.max(0, Number(this.config.ptz.keyboard_ramp_ms || 1500));
                const tick = force => {
                    let x=(held.has('ArrowRight')?1:0)-(held.has('ArrowLeft')?1:0);
                    let y=(held.has('ArrowUp')?1:0)-(held.has('ArrowDown')?1:0);
                    if (!x && !y) { if (keyPan || keyTilt) handle('joystick_stop'); keyPan=keyTilt=0; return; }
                    const len=Math.hypot(x,y); x/=len; y/=len;
                    const elapsed=performance.now()-keyStarted;
                    const speed=initial+(maximum-initial)*(rampMs ? Math.min(1,elapsed/rampMs) : 1);
                    const pan=x*speed, tilt=y*speed, now=performance.now();
                    if (force || Math.hypot(pan-keyPan,tilt-keyTilt)>=0.025 || now-keyLastSend>=heartbeatMs) {
                        handle('joystick',{pan,tilt,zoom:0,speed}); keyPan=pan; keyTilt=tilt; keyLastSend=now;
                    }
                };
                player.addEventListener('keydown', ev => {
                    if (ev.key === 'Escape') { held.clear(); tick(true); if(keyTimer)clearInterval(keyTimer); keyTimer=null; player.blur(); ev.preventDefault(); return; }
                    if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(ev.key)) return;
                    if (!held.size) keyStarted=performance.now(); held.add(ev.key); tick(true);
                    if (!keyTimer) keyTimer=setInterval(()=>tick(false),100);
                    ev.preventDefault(); ev.stopPropagation();
                });
                player.addEventListener('keyup', ev => {
                    if (!held.has(ev.key)) return; held.delete(ev.key); tick(true);
                    if (!held.size && keyTimer) { clearInterval(keyTimer); keyTimer=null; }
                    ev.preventDefault(); ev.stopPropagation();
                });
                player.addEventListener('blur', () => { if (held.size) { held.clear(); tick(true); } if(keyTimer)clearInterval(keyTimer); keyTimer=null; });
            }
        }

        for (const [startEvent, endEvent] of [['touchstart','touchend'],['mousedown','mouseup']]) {
            ptz.addEventListener(startEvent, startEvt => {
                if (joystickEnabled && startEvt.target.closest?.('.ptz-move')) return;
                const {className}=startEvt.target; startEvt.preventDefault(); handle('start_'+className);
                window.addEventListener(endEvent, endEvt => { endEvt.preventDefault(); handle('end_'+className); if(endEvt.timeStamp-startEvt.timeStamp>400)handle('long_'+className); else handle(className); }, {once:true});
            });
        }
    }'''

pat = re.compile(r"    renderPTZ\(\) \{.*?\n    \}\n\n    saveScreenshot", re.S)
assert pat.search(s), 'renderPTZ block not found'
s = pat.sub(new_func + '\n\n    saveScreenshot', s, count=1)
js.write_text(s)

manifest = root / 'manifest.json'
m = manifest.read_text().replace('"version": "v3.6.2-nav.9"', '"version": "v3.6.2-nav.10"')
manifest.write_text(m)
