/** Chrome 63+, Safari 11.1+ */
import {VideoRTC} from './video-rtc.js?v=1.9.9';
import {DigitalPTZ} from './digital-ptz.js?v=3.4.0';

class WebRTCCamera extends VideoRTC {
    static keepAliveRegistry = [];

    connectedCallback() {
        if (this.keepAliveTID) {
            clearTimeout(this.keepAliveTID);
            this.keepAliveTID = 0;
        }
        WebRTCCamera.keepAliveRegistry = WebRTCCamera.keepAliveRegistry.filter(item => item.card !== this);
        super.connectedCallback();
    }

    disconnectedCallback() {
        const seconds = Math.max(0, Number(this.config?.keep_alive || 0));
        if (!seconds || this.background) {
            super.disconnectedCallback();
            return;
        }
        if (this.keepAliveTID) return;
        if (this.wsState === WebSocket.CLOSED && this.pcState === WebSocket.CLOSED) return;

        const detachedAt = Date.now();
        this.keepAliveTID = setTimeout(() => {
            this.keepAliveTID = 0;
            WebRTCCamera.keepAliveRegistry = WebRTCCamera.keepAliveRegistry.filter(item => item.card !== this);
            if (!this.isConnected) this.ondisconnect();
        }, seconds * 1000);

        WebRTCCamera.keepAliveRegistry = WebRTCCamera.keepAliveRegistry.filter(item => item.card !== this);
        WebRTCCamera.keepAliveRegistry.push({card: this, detachedAt});

        const max = Math.max(0, parseInt(this.config?.keep_alive_streams_max ?? 0));
        if (max > 0) {
            WebRTCCamera.keepAliveRegistry.sort((a, b) => a.detachedAt - b.detachedAt);
            while (WebRTCCamera.keepAliveRegistry.length > max) {
                const oldest = WebRTCCamera.keepAliveRegistry.shift();
                if (!oldest || oldest.card === this && max > 0 && WebRTCCamera.keepAliveRegistry.length < max) continue;
                if (oldest.card.keepAliveTID) {
                    clearTimeout(oldest.card.keepAliveTID);
                    oldest.card.keepAliveTID = 0;
                }
                if (!oldest.card.isConnected) oldest.card.ondisconnect();
            }
        }
    }
    /**
     * Step 1. Called by the Hass, when config changed.
     * @param {Object} config
     */
    setConfig(config) {
        if (!config.url && !config.entity && !config.streams && !config.image) throw new Error('Missing `url`, `entity`, `streams` or `image`');
        this.imageMode = Boolean(config.image);

        if (config.background) this.background = config.background;

        if (config.intersection === 0) this.visibilityThreshold = 0;
        else this.visibilityThreshold = config.intersection || 0.75;

        this.config = Object.assign({
            mode: config.mse === false ? 'webrtc' : config.webrtc === false ? 'mse' : this.mode,
            media: this.media,
            streams: [{url: config.url, entity: config.entity}],
            poster_remote: config.poster && (config.poster.indexOf('://') > 0 || config.poster.charAt(0) === '/'),
            keep_alive: 0,
            keep_alive_streams_max: 0,
        }, config);

        this.streamID = -1;
        if (!this.imageMode) this.nextStream(false);

        this.onhass = [];
    }

    set hass(hass) {
        this._hass = hass;
        if (this.imageMode) this.updateStaticImage();
        this.onhass.forEach(fn => fn());
    }

    get hass() {
        return this._hass;
    }

    updateStaticImage() {
        if (!this.imageMode || !this.staticImage || !this.hass) return;
        let source = String(this.config.image || '').trim();
        const state = this.hass.states?.[source];
        if (state?.attributes?.entity_picture) source = state.attributes.entity_picture;
        if (!source) return;
        if (!/^https?:\/\//i.test(source)) source = this.hass.hassUrl(source);

        // HA image entities often keep a stable entity_picture URL while the
        // underlying JPEG changes. Give each snapshot revision its own URL so
        // browser/proxy caches cannot leave a newly-opened card one image behind.
        const revision = state?.attributes?.event_id ||
            state?.attributes?.snapshot_id ||
            state?.attributes?.timestamp ||
            state?.last_updated;
        if (revision) {
            try {
                const url = new URL(source, window.location.href);
                url.searchParams.set('_webrtc_v', String(revision));
                source = url.toString();
            } catch (err) {
                const separator = source.includes('?') ? '&' : '?';
                source += `${separator}_webrtc_v=${encodeURIComponent(String(revision))}`;
            }
        }

        if (this.staticImage.src !== source) this.staticImage.src = source;
    }

    getCardSize() {
        return 5;
    }

    static getStubConfig() {
        return {'url': ''};
    }

    setStatus(mode, status) {
        const divMode = this.querySelector('.mode').innerText;
        if (mode === 'error' && divMode !== 'Loading..' && divMode !== 'Loading...') return;

        this.querySelector('.mode').innerText = mode;
        this.querySelector('.status').innerText = status || '';
    }

    /** @param reload {boolean} */
    nextStream(reload) {
        if (this.imageMode) return;
        this.streamID = (this.streamID + 1) % this.config.streams.length;

        const stream = this.config.streams[this.streamID];
        this.config.url = stream.url;
        this.config.entity = stream.entity;
        this.mode = stream.mode || this.config.mode;
        this.media = stream.media || this.config.media;

        if (reload) {
            this.ondisconnect();
            setTimeout(() => this.onconnect(), 100);
        }
    }

    get streamName() {
        return this.config.streams[this.streamID].name || `S${this.streamID}`;
    }

    oninit() {
        super.oninit();
        this.renderMain();
        this.renderDigitalPTZ();
        this.renderActions();
        this.renderPTZ();
        this.renderCustomUI();
        this.renderAudioControl();
        this.renderShortcuts();
        this.renderStyle();
    }

    onconnect() {
        if (!this.config || !this.hass) return false;
        if (this.imageMode) {
            this.updateStaticImage();
            this.setStatus('IMG', this.config.title || '');
            return false;
        }
        if (!this.isConnected || this.ws || this.pc) return false;

        const divMode = this.querySelector('.mode').innerText;
        if (divMode === 'Loading..') return;

        this.setStatus('Loading..');

        this.hass.callWS({
            type: 'auth/sign_path', path: '/api/webrtc/ws'
        }).then(data => {
            if (this.config.poster && !this.config.poster_remote) {
                this.video.poster = this.hass.hassUrl(data.path) + '&poster=' + encodeURIComponent(this.config.poster);
            }

            this.wsURL = 'ws' + this.hass.hassUrl(data.path).substring(4);

            if (this.config.entity) {
                this.wsURL += '&entity=' + this.config.entity;
            } else if (this.config.url) {
                this.wsURL += '&url=' + encodeURIComponent(this.config.url);
            } else {
                this.setStatus('IMG');
                return;
            }

            if (this.config.server) {
                this.wsURL += '&server=' + encodeURIComponent(this.config.server);
            }

            if (super.onconnect()) {
                this.setStatus('Loading...');
            } else {
                this.setStatus('error', 'unable to connect');
            }
        }).catch(er => {
            this.setStatus('error', er);
        });
    }

    onopen() {
        const result = super.onopen();

        this.onmessage['stream'] = msg => {
            switch (msg.type) {
                case 'error':
                    this.setStatus('error', msg.value);
                    break;
                case 'mse':
                case 'hls':
                case 'mp4':
                case 'mjpeg':
                    this.setStatus(msg.type.toUpperCase(), this.config.title || '');
                    break;
            }
        };

        return result;
    }

    onpcvideo(ev) {
        super.onpcvideo(ev);

        if (this.pcState !== WebSocket.CLOSED) {
            this.setStatus('RTC', this.config.title || '');
        }
    }

    renderMain() {
        const shadow = this.attachShadow({mode: 'open'});
        shadow.innerHTML = `
        <style>
            ha-card {
                width: 100%;
                height: 100%;
                margin: auto;
                overflow: hidden;
                position: relative;
            }
            ha-icon {
                color: white;
                cursor: pointer;
            }
            .player {
                background-color: black;
                height: 100%;
                position: relative;
            }
            .player:active {
                cursor: move;
            }
            .player .ptz-transform {
                height: 100%;
            }
            .static-image {
                width: 100%;
                height: 100%;
                display: block;
                object-fit: contain;
                transform-origin: center center;
                user-select: none;
                -webkit-user-drag: none;
            }
            .region-overlay {
                position: absolute;
                pointer-events: none;
                overflow: visible;
            }
            .region-overlay rect {
                fill: none;
                stroke: var(--webrtc-roi-color, #ff3030);
                vector-effect: non-scaling-stroke;
            }
            .header {
                position: absolute;
                top: 6px;
                left: 10px;
                right: 10px;
                color: white;
                display: flex;
                justify-content: space-between;
                pointer-events: none;
            }
            .mode {
                cursor: pointer;
                opacity: 0.6;
                pointer-events: auto;
            }
        </style>
        <ha-card class="card">
            <div class="player">
                <div class="ptz-transform"></div>
            </div>
            <div class="header">
                <div class="status"></div>
                <div class="mode"></div>
            </div>
        </ha-card>
        `;

        this.querySelector = selectors => this.shadowRoot.querySelector(selectors);
        if (this.imageMode) {
            this.staticImage = document.createElement('img');
            this.staticImage.className = 'static-image';
            this.staticImage.alt = this.config.title || 'Camera snapshot';
            this.staticImage.draggable = false;
            this.querySelector('.ptz-transform').appendChild(this.staticImage);
            this.regionOverlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            this.regionOverlay.classList.add('region-overlay');
            this.regionOverlay.setAttribute('viewBox', '0 0 1 1');
            this.regionOverlay.setAttribute('preserveAspectRatio', 'none');
            this.querySelector('.ptz-transform').appendChild(this.regionOverlay);
            this.updateStaticImage();
        } else {
            this.querySelector('.ptz-transform').appendChild(this.video);
        }

        const mode = this.querySelector('.mode');
        mode.addEventListener('click', () => this.nextStream(true));

        if (!this.imageMode) {
            if (this.config.muted !== undefined) this.video.muted = this.config.muted;
            if (this.config.poster_remote) this.video.poster = this.config.poster;
        }
    }

    getDigitalRegions() {
        if (!this.imageMode || !this.hass) return {regions: [], primary: null, state: null};
        const entity = String(this.config.image || '').trim();
        const state = this.hass.states?.[entity];
        const regionCfg = this.config.digital_ptz?.regions || {};
        const attribute = regionCfg.attribute || this.config.digital_ptz?.initial_region?.attribute || 'detections';
        let regions = state?.attributes?.[attribute];
        if (!Array.isArray(regions)) regions = [];
        regions = regions.filter(item => item && Array.isArray(item.bbox) && item.bbox.length === 4);
        const primaryValue = state?.attributes?.primary_detection;
        const primary = Number.isInteger(Number(primaryValue)) ? Number(primaryValue) : (regions.length ? 0 : null);
        return {regions, primary, state};
    }

    updateRegionOverlay() {
        if (!this.regionOverlay || !this.digitalPTZ) return;
        const cfg = this.config.digital_ptz?.region_overlay || {};
        const {regions, primary} = this.getDigitalRegions();
        this.regionOverlay.innerHTML = '';
        this.regionOverlay.style.display = cfg.show === false || !regions.length ? 'none' : 'block';
        if (this.regionOverlay.style.display === 'none') return;
        const tr = this.digitalPTZ.transform;
        if (!tr.videoRect || !tr.containerRect) return;
        this.regionOverlay.style.left = `${tr.videoRect.x - tr.containerRect.x}px`;
        this.regionOverlay.style.top = `${tr.videoRect.y - tr.containerRect.y}px`;
        this.regionOverlay.style.width = `${tr.videoRect.width}px`;
        this.regionOverlay.style.height = `${tr.videoRect.height}px`;
        const selection = String(cfg.selection ?? 'all').toLowerCase();
        const selected = selection === 'primary' && primary !== null ? [regions[primary]].filter(Boolean) : regions;
        const lineWidth = Math.max(0.5, Number(cfg.line_width ?? 2));
        selected.forEach(region => {
            const [x1,y1,x2,y2] = region.bbox.map(Number);
            if (![x1,y1,x2,y2].every(Number.isFinite)) return;
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', String(Math.min(x1,x2)));
            rect.setAttribute('y', String(Math.min(y1,y2)));
            rect.setAttribute('width', String(Math.abs(x2-x1)));
            rect.setAttribute('height', String(Math.abs(y2-y1)));
            rect.setAttribute('stroke-width', String(lineWidth));
            this.regionOverlay.appendChild(rect);
        });
    }

    applyInitialRegion(force = false) {
        if (!this.digitalPTZ || !this.imageMode) return;
        const cfg = this.config.digital_ptz?.initial_region;
        if (!cfg) return;
        const {regions, primary, state} = this.getDigitalRegions();
        if (!regions.length) return;
        const key = state?.attributes?.event_id || state?.attributes?.snapshot_id || state?.last_updated || this.staticImage?.src;
        if (!force && key && key === this._digitalRegionKey) return;
        const selection = cfg.selection ?? 'primary';
        const padding = Math.max(0, Number(cfg.padding ?? 0.5));
        const minScale = Math.max(1, Number(cfg.min_scale ?? 1));
        const maxScale = Math.max(minScale, Number(cfg.max_scale ?? this.config.digital_ptz?.max_scale ?? 10));
        let selected;
        if (String(selection).toLowerCase() === 'all') selected = regions;
        else if (String(selection).toLowerCase() === 'primary') selected = [regions[primary ?? 0]].filter(Boolean);
        else selected = [regions[Math.max(0, Number(selection) || 0)]].filter(Boolean);
        if (!selected.length) return;
        if (this.digitalPTZ.fitRegions(selected, {padding, minScale, maxScale})) {
            this._digitalRegionKey = key;
            this.updateRegionOverlay();
        }
    }

    showDigitalRegion(selection = 'primary') {
        if (!this.digitalPTZ) return false;
        const {regions, primary} = this.getDigitalRegions();
        if (!regions.length) return false;
        let selected;
        if (String(selection).toLowerCase() === 'all') selected = regions;
        else if (String(selection).toLowerCase() === 'primary') selected = [regions[primary ?? 0]].filter(Boolean);
        else selected = [regions[Math.max(0, Number(selection) || 0)]].filter(Boolean);
        const cfg = this.config.digital_ptz?.initial_region || {};
        return this.digitalPTZ.fitRegions(selected, {
            padding: Math.max(0, Number(cfg.padding ?? 0.5)),
            minScale: 1,
            maxScale: Math.max(1, Number(this.config.digital_ptz?.max_scale ?? 10)),
        });
    }

    showDigitalFullFrame() {
        if (!this.digitalPTZ) return false;
        this.digitalPTZ.reset();
        return true;
    }

    renderDigitalPTZ() {
        if (this.config.digital_ptz === false) return;
        const media = this.imageMode ? this.staticImage : this.video;
        const digitalOptions = Object.assign({}, this.config.digital_ptz, {persist_key: this.config.image || this.config.url});
        const hasEntityWheelZoom = Boolean(
            this.config.ptz?.zoom_entity && this.config.ptz?.zoom_slider !== false
        );
        const hasJoystickWheelZoom = Boolean(
            this.config.ptz?.service &&
            this.config.ptz?.joystick &&
            this.config.ptz?.data_joystick &&
            this.config.ptz?.data_joystick_stop
        );
        const hasLegacyWheelZoom = Boolean(
            this.config.ptz?.service &&
            this.config.ptz?.data_start_zoom_in && this.config.ptz?.data_end_zoom_in &&
            this.config.ptz?.data_start_zoom_out && this.config.ptz?.data_end_zoom_out
        );
        const hasPhysicalWheelZoom = hasEntityWheelZoom || hasJoystickWheelZoom || hasLegacyWheelZoom;
        if (hasPhysicalWheelZoom) digitalOptions.mouse_wheel_zoom = false;
        this.digitalPTZ = new DigitalPTZ(
            this.querySelector('.player'),
            this.querySelector('.player .ptz-transform'),
            media,
            digitalOptions
        );
        if (this.imageMode) {
            const refreshRegions = () => {
                requestAnimationFrame(() => {
                    this.updateRegionOverlay();
                    this.applyInitialRegion();
                });
            };
            media.addEventListener('load', refreshRegions);
            this.onhass.push(refreshRegions);
            refreshRegions();
        }
    }

    navigate(path) {
        if (!path) return;
        history.pushState(null, '', path);
        window.dispatchEvent(new CustomEvent('location-changed'));
    }

    async performAction(action, source = this) {
        if (Array.isArray(action)) {
            for (const step of action) await this.performAction(step, source);
            return;
        }
        if (!action || !action.action || action.action === 'none') return;

        const entity = action.entity || this.config.entity;
        switch (action.action) {
            case 'navigate':
                this.navigate(action.navigation_path);
                break;

            case 'delay': {
                let ms = Number(action.milliseconds ?? action.ms ?? 0);
                if (!ms && action.seconds !== undefined) ms = Number(action.seconds) * 1000;
                if (!Number.isFinite(ms) || ms < 0) return;
                await new Promise(resolve => setTimeout(resolve, ms));
                break;
            }

            case 'more-info': {
                if (!entity) return;
                const event = new Event('hass-more-info', {bubbles:true, cancelable:true, composed:true});
                event.detail = {entityId: entity};
                source.dispatchEvent(event);
                break;
            }

            case 'toggle':
                if (entity) await this.hass.callService('homeassistant', 'toggle', {entity_id: entity});
                break;

            case 'perform-action':
            case 'call-service': {
                const service = action.perform_action || action.service;
                if (!service) return;
                const [domain, name] = service.split('.', 2);
                if (!domain || !name) return;
                await this.hass.callService(domain, name, action.data || action.service_data || {}, action.target || {});
                break;
            }

            case 'url': {
                const url = action.url_path || action.url;
                if (!url) return;
                if (action.new_tab) window.open(url, '_blank', 'noopener');
                else window.location.href = url;
                break;
            }
        }
    }

    renderActions() {
        const tapAction = this.config.tap_action;
        const physicalDragOwnsSurface = Boolean(
            this.config.ptz?.joystick && this.config.ptz?.physical_drag !== false
        );
        const holdAction = physicalDragOwnsSurface ? null : this.config.hold_action;
        if (!tapAction && !holdAction) return;

        // A configured card action owns the video surface. This prevents native
        // browser media controls (pause/seek/mute/fullscreen) intercepting taps.
        if (!this.imageMode) this.video.controls = false;

        const player = this.querySelector('.player');
        const activePointers = new Set();
        const maxMove = 10;
        const doubleTapMs = 400;
        const holdMs = 550;
        let startX = 0;
        let startY = 0;
        let moved = false;
        let multiTouch = false;
        let held = false;
        let lastTap = 0;
        let pendingTap = null;
        let holdTimer = null;

        const clearHold = () => {
            if (holdTimer) clearTimeout(holdTimer);
            holdTimer = null;
        };

        const resetGesture = () => {
            clearHold();
            activePointers.clear();
            moved = false;
            multiTouch = false;
            held = false;
        };

        player.addEventListener('pointerdown', ev => {
            if (ev.pointerType === 'mouse' && ev.button !== 0) return;

            // A second tap belongs to DigitalPTZ's double-click/double-tap zoom,
            // so cancel the pending single-tap action before it can fire.
            if (pendingTap && ev.timeStamp - lastTap < doubleTapMs) {
                clearTimeout(pendingTap);
                pendingTap = null;
            }

            activePointers.add(ev.pointerId);
            if (activePointers.size === 1) {
                startX = ev.clientX;
                startY = ev.clientY;
                moved = false;
                multiTouch = false;
                held = false;

                if (holdAction && holdAction.action !== 'none') {
                    const pointerId = ev.pointerId;
                    holdTimer = setTimeout(() => {
                        holdTimer = null;
                        if (!activePointers.has(pointerId) || moved || multiTouch) return;
                        held = true;
                        this.performAction(holdAction, player).catch(err => console.error('WebRTC hold action failed', err));
                    }, holdMs);
                }
            } else {
                multiTouch = true;
                clearHold();
            }
        }, true);

        player.addEventListener('pointermove', ev => {
            if (!activePointers.has(ev.pointerId)) return;
            if (Math.hypot(ev.clientX - startX, ev.clientY - startY) > maxMove) {
                moved = true;
                clearHold();
            }
        }, true);

        player.addEventListener('pointerup', ev => {
            if (!activePointers.has(ev.pointerId)) return;
            activePointers.delete(ev.pointerId);
            clearHold();

            if (activePointers.size > 0) {
                multiTouch = true;
                return;
            }

            if (held) {
                held = false;
                moved = false;
                multiTouch = false;
                lastTap = 0;
                return;
            }

            const isTap = !moved && !multiTouch &&
                Math.hypot(ev.clientX - startX, ev.clientY - startY) <= maxMove;

            moved = false;
            multiTouch = false;

            if (!isTap || !tapAction || tapAction.action === 'none') return;

            if (ev.timeStamp - lastTap < doubleTapMs) {
                if (pendingTap) clearTimeout(pendingTap);
                pendingTap = null;
                lastTap = 0;
                return;
            }

            lastTap = ev.timeStamp;
            pendingTap = setTimeout(() => {
                pendingTap = null;
                this.performAction(tapAction, player).catch(err => console.error('WebRTC tap action failed', err));
            }, doubleTapMs);
        }, true);

        player.addEventListener('pointercancel', resetGesture, true);
        player.addEventListener('contextmenu', ev => {
            if (holdAction && holdAction.action !== 'none') ev.preventDefault();
        });
    }

    renderPTZ() {
        if (!this.config.ptz) return;
        const zoomEntity = String(this.config.ptz.zoom_entity || '').trim();
        const showZoomSlider = Boolean(zoomEntity && this.config.ptz.zoom_slider !== false);
        if (!this.config.ptz.service && !showZoomSlider) return;

        const joystickEnabled = Boolean(
            this.config.ptz.service &&
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
        const fixedRadius = Math.max(40, Number(this.config.ptz.joystick_radius ?? 115));
        const fixedDiameter = fixedRadius * 2;
        const zoomSliderOrientation = String(this.config.ptz.zoom_slider_orientation || 'vertical').toLowerCase();

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
                .ptz-zoom-slider { display:${showZoomSlider ? 'flex' : 'none'}; align-items:center; justify-content:center; gap:6px; padding:7px 6px; border-radius:6px; background:rgba(0,0,0,.3); color:white; font-size:12px; }
                .ptz-zoom-slider.vertical { flex-direction:column; min-height:150px; }
                .ptz-zoom-slider.horizontal { flex-direction:row; min-width:170px; }
                .ptz-zoom-slider input { accent-color:var(--primary-color); cursor:pointer; }
                .ptz-zoom-slider.vertical input { width:120px; transform:rotate(-90deg); margin:48px -42px; }
                .ptz-zoom-slider.horizontal input { width:120px; }
                .ptz-zoom-value { min-width:34px; text-align:center; font-variant-numeric:tabular-nums; }
                .up { position:absolute; top:5px; left:50%; transform:translateX(-50%); }.down { position:absolute; bottom:5px; left:50%; transform:translateX(-50%); }.left { position:absolute; left:5px; top:50%; transform:translateY(-50%); }.right { position:absolute; right:5px; top:50%; transform:translateY(-50%); }
                .zoom_out { position:absolute; left:5px; top:50%; transform:translateY(-50%); }.zoom_in { position:absolute; right:5px; top:50%; transform:translateY(-50%); }.home { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); }
            </style>`);
        card.insertAdjacentHTML('beforeend', `
            <div class="ptz">
                <div class="ptz-move ${joystickEnabled ? 'joystick' : ''}">${joystickEnabled ? '<div class="ptz-centre"></div><div class="ptz-stick"></div>' : '<ha-icon class="right" icon="mdi:arrow-right"></ha-icon><ha-icon class="left" icon="mdi:arrow-left"></ha-icon><ha-icon class="up" icon="mdi:arrow-up"></ha-icon><ha-icon class="down" icon="mdi:arrow-down"></ha-icon>'}</div>
                <div class="ptz-zoom"><ha-icon class="zoom_in" icon="mdi:plus"></ha-icon><ha-icon class="zoom_out" icon="mdi:minus"></ha-icon></div>
                <div class="ptz-zoom-slider ${zoomSliderOrientation === 'horizontal' ? 'horizontal' : 'vertical'}">
                    <ha-icon icon="mdi:magnify"></ha-icon>
                    <input class="ptz-zoom-range" type="range" min="0" max="100" step="1" value="0">
                    <span class="ptz-zoom-value">0%</span>
                </div>
                <div class="ptz-home"><ha-icon class="home" icon="mdi:home"></ha-icon></div>
            </div>
            <div class="ptz-dynamic"><div class="ptz-deadband"></div><div class="ptz-centre"></div><div class="ptz-stick"></div></div>`);

        const ptz = this.querySelector('.ptz');
        const fixedMove = this.querySelector('.ptz-move');
        const dynamicMove = this.querySelector('.ptz-dynamic');
        const isDigitallyZoomed = () => Boolean(this.digitalPTZ && this.digitalPTZ.transform && this.digitalPTZ.transform.scale > 1.001);

        let entityWheelZoom = null;
        let predictiveWheelZoom = null;
        if (showZoomSlider) {
            const range = this.querySelector('.ptz-zoom-range');
            const label = this.querySelector('.ptz-zoom-value');
            let sliderActive = false;
            let lastSent = null;
            let pendingTarget = null;
            let pendingUntil = 0;
            let lastWheelSend = 0;
            let sendTimer = null;
            let settleTimer = null;
            const wheelUpdateMs = Math.max(40, Number(this.config.ptz.wheel_zoom_update_ms ?? 100));
            const wheelSettleMs = Math.max(60, Number(this.config.ptz.wheel_zoom_settle_ms ?? 160));
            const syncTimeoutMs = Math.max(300, Number(this.config.ptz.wheel_zoom_sync_timeout_ms ?? 1500));
            const sendZoom = value => {
                const numeric = Number(value);
                if (!Number.isFinite(numeric) || numeric === lastSent) return Promise.resolve();
                lastSent = numeric;
                return this.hass.callService('number', 'set_value', {entity_id: zoomEntity, value: numeric})
                    .catch(err => console.error('WebRTC PTZ zoom service call failed', err));
            };
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
                if (pendingTarget !== null) {
                    const tolerance = Math.max(0.05, Math.abs(Number(range.step)) / 2);
                    if (Math.abs(value - pendingTarget) <= tolerance || Date.now() > pendingUntil) pendingTarget = null;
                }
                const shown = pendingTarget !== null ? pendingTarget : value;
                if (!sliderActive) range.value = String(shown);
                label.textContent = `${Math.round(shown)}%`;
            };
            this.onhass.push(updateZoomSlider);
            updateZoomSlider();
            range.addEventListener('pointerdown', ev => { sliderActive = true; pendingTarget = null; ev.stopPropagation(); });
            range.addEventListener('input', ev => { label.textContent = `${Math.round(Number(ev.target.value))}%`; });
            range.addEventListener('change', ev => sendZoom(ev.target.value));
            const finishSlider = ev => {
                if (!sliderActive) return;
                sliderActive = false;
                pendingTarget = Number(range.value);
                pendingUntil = Date.now() + syncTimeoutMs;
                sendZoom(range.value);
                ev?.stopPropagation?.();
            };
            range.addEventListener('pointerup', finishSlider);
            range.addEventListener('pointercancel', finishSlider);
            range.addEventListener('click', ev => ev.stopPropagation());

            entityWheelZoom = direction => {
                const state = this.hass?.states?.[zoomEntity];
                const reported = Number(state?.state);
                if (!Number.isFinite(reported)) return;
                const min = Number(state.attributes?.min ?? 0);
                const max = Number(state.attributes?.max ?? 100);
                const entityStep = Number(state.attributes?.step ?? 1);
                const configuredStep = Number(this.config.ptz.wheel_zoom_step ?? Math.max(2, entityStep || 1));
                const step = Number.isFinite(configuredStep) && configuredStep > 0 ? configuredStep : 2;
                const base = pendingTarget !== null ? pendingTarget : reported;
                pendingTarget = Math.max(min, Math.min(max, base + (direction === 'zoom_in' ? step : -step)));
                pendingUntil = Date.now() + syncTimeoutMs;
                range.value = String(pendingTarget);
                label.textContent = `${Math.round(pendingTarget)}%`;
                const now = performance.now();
                const transmit = () => {
                    sendTimer = null;
                    lastWheelSend = performance.now();
                    sendZoom(pendingTarget);
                };
                if (now - lastWheelSend >= wheelUpdateMs) transmit();
                else if (!sendTimer) sendTimer = setTimeout(transmit, wheelUpdateMs - (now - lastWheelSend));
                if (settleTimer) clearTimeout(settleTimer);
                settleTimer = setTimeout(() => {
                    if (sendTimer) { clearTimeout(sendTimer); sendTimer = null; }
                    lastWheelSend = performance.now();
                    sendZoom(pendingTarget);
                }, wheelSettleMs);
            };

            predictiveWheelZoom = {
                getPosition: () => {
                    const state = this.hass?.states?.[zoomEntity];
                    const reported = Number(state?.state);
                    if (!Number.isFinite(reported)) return null;
                    const min = Number(state.attributes?.min ?? 0);
                    const max = Number(state.attributes?.max ?? 100);
                    return {
                        value: pendingTarget !== null ? pendingTarget : reported,
                        reported,
                        min: Number.isFinite(min) ? min : 0,
                        max: Number.isFinite(max) ? max : 100,
                    };
                },
                showTarget: value => {
                    const numeric = Number(value);
                    if (!Number.isFinite(numeric)) return;
                    pendingTarget = numeric;
                    pendingUntil = Date.now() + syncTimeoutMs;
                    range.value = String(numeric);
                    label.textContent = `${Math.round(numeric)}%`;
                },
                sendTarget: value => sendZoom(value),
            };
        }

        if (joystickEnabled) {
            const surface = dynamicJoystick ? player : fixedMove;
            let activePointer = null, originX = 0, originY = 0, moving = false;
            let claimed = false, activePointerType = '', touchBlocked = false;
            const physicalPointers = new Set();
            let lastPan = 0, lastTilt = 0, lastSpeed = 0, lastSend = 0, heartbeat = null;
            let radius = fixedRadius, deadbandPx = 14;
            const updateMs = Math.max(40, parseInt(this.config.ptz.joystick_update_ms) || 100);
            const heartbeatMs = Math.max(250, parseInt(this.config.ptz.joystick_heartbeat_ms) || 600);
            const configuredMinSpeed = Number(this.config.ptz.joystick_min_speed ?? 0.03);
            const configuredMaxSpeed = Number(this.config.ptz.joystick_max_speed ?? 1.0);
            const minSpeed = Math.max(0, Math.min(1, Number.isFinite(configuredMinSpeed) ? configuredMinSpeed : 0.03));
            const maxSpeed = Math.max(minSpeed, Math.min(1, Number.isFinite(configuredMaxSpeed) ? configuredMaxSpeed : 1.0));
            const curve = Math.max(0.2, Number(this.config.ptz.joystick_curve ?? 1.9));

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
            const showDynamic = () => {
                if (!dynamicJoystick) return;
                const rect = player.getBoundingClientRect();
                dynamicMove.style.width = `${radius*2}px`; dynamicMove.style.height = `${radius*2}px`;
                dynamicMove.style.left = `${originX - rect.left}px`; dynamicMove.style.top = `${originY - rect.top}px`;
                dynamicMove.style.transform = 'translate(-50%,-50%)'; dynamicMove.style.display = 'block';
                const db = dynamicMove.querySelector('.ptz-deadband'); db.style.width = `${deadbandPx*2}px`; db.style.height = `${deadbandPx*2}px`;
            };
            const claimPointer = ev => {
                if (claimed) return;
                claimed = true;
                showDynamic();
                player.focus({preventScroll:true});
                surface.setPointerCapture?.(ev.pointerId);
            };
            const begin = ev => {
                if (ev.pointerType === 'mouse' && ev.button !== 0) return;
                if (dynamicJoystick && isDigitallyZoomed()) return;
                physicalPointers.add(ev.pointerId);
                if (ev.pointerType === 'touch' && physicalPointers.size > 1) {
                    touchBlocked = true;
                    if (activePointer !== null) {
                        activePointer = null;
                        claimed = false;
                        stopMove();
                    }
                    return;
                }
                if (activePointer !== null) return;
                activePointer = ev.pointerId;
                activePointerType = ev.pointerType || '';
                originX = ev.clientX; originY = ev.clientY;
                radius = Math.max(40, Number(ev.pointerType === 'touch' ? (this.config.ptz.joystick_radius_touch || 150) : (this.config.ptz.joystick_radius || 115)));
                deadbandPx = Math.max(4, Number(ev.pointerType === 'touch' ? (this.config.ptz.joystick_deadband_touch || 34) : (this.config.ptz.joystick_deadband || 22)));
                claimed = ev.pointerType !== 'touch';
                if (claimed) {
                    claimPointer(ev);
                    showDynamic();
                    player.focus({preventScroll:true});
                    surface.setPointerCapture?.(ev.pointerId);
                    ev.preventDefault(); ev.stopPropagation();
                }
            };
            const move = ev => {
                if (activePointer !== ev.pointerId || touchBlocked) return;
                const dx = ev.clientX-originX, dy = ev.clientY-originY, dist = Math.hypot(dx,dy);
                if (!claimed) {
                    if (activePointerType === 'touch' && physicalPointers.size > 1) return;
                    if (dist <= deadbandPx) return;
                    claimPointer(ev);
                }
                const ctl = dynamicJoystick ? dynamicMove : fixedMove;
                const stick = ctl.querySelector('.ptz-stick');
                const visual = Math.min(radius, dist);
                if (stick) stick.style.transform = dist ? `translate(${(dx/dist*visual).toFixed(1)}px,${(dy/dist*visual).toFixed(1)}px)` : 'translate(0,0)';
                if (dist <= deadbandPx) {
                    if (moving) { handle('joystick_stop'); moving=false; if (heartbeat) clearInterval(heartbeat); heartbeat=null; }
                    ev.preventDefault(); ev.stopPropagation(); return;
                }
                const norm = Math.min(1, (dist-deadbandPx)/Math.max(1,radius-deadbandPx));
                const magnitude = minSpeed + (maxSpeed-minSpeed)*Math.pow(norm,curve);
                const pan = dx/dist*magnitude, tilt = -dy/dist*magnitude;
                const now=performance.now(), changed=Math.hypot(pan-lastPan,tilt-lastTilt)>=0.03;
                if (!moving || (changed && now-lastSend>=updateMs)) {
                    handle('joystick',{pan,tilt,zoom:0,speed:magnitude});
                    lastPan=pan; lastTilt=tilt; lastSpeed=magnitude; lastSend=now; moving=true; startHeartbeat();
                }
                ev.preventDefault(); ev.stopPropagation();
            };
            const end = ev => {
                physicalPointers.delete(ev.pointerId);
                if (ev.pointerId === activePointer) {
                    const owned = claimed;
                    activePointer = null;
                    claimed = false;
                    stopMove();
                    if (owned) { ev.preventDefault(); ev.stopPropagation(); }
                }
                if (!physicalPointers.size) touchBlocked = false;
            };
            surface.addEventListener('pointerdown', begin, true);
            surface.addEventListener('pointermove', move, true);
            surface.addEventListener('pointerup', end, true);
            surface.addEventListener('pointercancel', end, true);
            surface.addEventListener('lostpointercapture', ev => {
                physicalPointers.delete(ev.pointerId);
                if (activePointer===ev.pointerId) { activePointer=null; claimed=false; stopMove(); }
                if (!physicalPointers.size) touchBlocked=false;
            });

            if (keyboardEnabled) {
                if (!player.hasAttribute('tabindex')) player.tabIndex = 0;
                const held = new Set();
                let keyTimer = null, keyStarted = 0, keyLastSend = 0, keyPan = 0, keyTilt = 0;
                const initial = Math.max(0, Math.min(1, Number(this.config.ptz.keyboard_initial_speed ?? 0.04)));
                const maximum = Math.max(initial, Math.min(1, Number(this.config.ptz.keyboard_max_speed || 0.45)));
                const rampMs = Math.max(0, Number(this.config.ptz.keyboard_ramp_ms || 2500));
                const keyboardUpdateMs = Math.max(150, Number(this.config.ptz.keyboard_update_ms || 300));
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
                    if (ev.repeat) { ev.preventDefault(); ev.stopPropagation(); return; }
                    if (!held.size) keyStarted=performance.now();
                    held.add(ev.key);
                    tick(true);
                    if (!keyTimer) keyTimer=setInterval(()=>tick(false), keyboardUpdateMs);
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

        // Desktop wheel arbitration: physical optical zoom while unzoomed;
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

        for (const [startEvent, endEvent] of [['touchstart','touchend'],['mousedown','mouseup']]) {
            ptz.addEventListener(startEvent, startEvt => {
                if (startEvt.target.closest?.('.ptz-zoom-slider')) return;
                if (joystickEnabled && startEvt.target.closest?.('.ptz-move')) return;
                const {className}=startEvt.target; startEvt.preventDefault(); handle('start_'+className);
                window.addEventListener(endEvent, endEvt => { endEvt.preventDefault(); handle('end_'+className); if(endEvt.timeStamp-startEvt.timeStamp>400)handle('long_'+className); else handle(className); }, {once:true});
            });
        }
    }

    saveScreenshot() {
        const a = document.createElement('a');

        if (this.video.videoWidth && this.video.videoHeight) {
            const canvas = document.createElement('canvas');
            canvas.width = this.video.videoWidth;
            canvas.height = this.video.videoHeight;
            canvas.getContext('2d').drawImage(this.video, 0, 0, canvas.width, canvas.height);
            a.href = canvas.toDataURL('image/jpeg');
        } else if (this.video.poster && this.video.poster.startsWith('data:image/jpeg')) {
            a.href = this.video.poster;
        } else {
            return;
        }

        const ts = new Date().toISOString().substring(0, 19).replaceAll('-', '').replaceAll(':', '');
        a.download = `snapshot_${ts}.jpeg`;
        a.click();
    }

    renderCustomUI() {
        if (!this.config.ui) return;

        this.video.controls = false;
        this.video.style.pointerEvents = 'none';

        const card = this.querySelector('.card');
        card.insertAdjacentHTML('beforebegin', `
            <style>
                .spinner {
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                }
                .controls {
                    position: absolute;
                    left: 5px;
                    right: 5px;
                    bottom: 5px;
                    display: flex;
                }
                .space { width: 100%; }
                .volume { display: none; }
                .stream {
                    padding-top: 2px;
                    margin-left: 2px;
                    font-weight: 400;
                    font-size: 20px;
                    color: white;
                    display: none;
                    cursor: pointer;
                }
            </style>
        `);
        card.insertAdjacentHTML('beforeend', `
            <div class="ui">
                <ha-circular-progress class="spinner"></ha-circular-progress>
                <div class="controls">
                    <ha-icon class="fullscreen" icon="mdi:fullscreen"></ha-icon>
                    <ha-icon class="screenshot" icon="mdi:floppy"></ha-icon>
                    <ha-icon class="pictureinpicture" icon="mdi:picture-in-picture-bottom-right"></ha-icon>
                    <span class="stream">${this.streamName}</span>
                    <span class="space"></span>
                    <ha-icon class="play" icon="mdi:play"></ha-icon>
                    <ha-icon class="volume" icon="mdi:volume-high"></ha-icon>
                </div>
            </div>
        `);

        const video = this.video;

        const fullscreen = this.querySelector('.fullscreen');
        if (this.requestFullscreen) {
            this.addEventListener('fullscreenchange', () => {
                fullscreen.icon = document.fullscreenElement ? 'mdi:fullscreen-exit' : 'mdi:fullscreen';
            });
        } else if (video.webkitEnterFullscreen) {
            this.requestFullscreen = () => new Promise((resolve, reject) => {
                try {
                    video.webkitEnterFullscreen();
                } catch (e) {
                    reject(e);
                }
            });
            video.addEventListener('webkitendfullscreen', () => {
                setTimeout(() => this.play(), 1000);
            });
        } else {
            fullscreen.style.display = 'none';
        }

        const pip = this.querySelector('.pictureinpicture');
        if (video.requestPictureInPicture) {
            video.addEventListener('enterpictureinpicture', () => {
                pip.icon = 'mdi:rectangle';
                this.background = true;
            });
            video.addEventListener('leavepictureinpicture', () => {
                pip.icon = 'mdi:picture-in-picture-bottom-right';
                this.background = this.config.background;
                this.play();
            });
        } else {
            pip.style.display = 'none';
        }

        const ui = this.querySelector('.ui');
        ui.addEventListener('click', ev => {
            const icon = ev.target.icon;
            if (icon === 'mdi:play') {
                this.play();
            } else if (icon === 'mdi:volume-mute') {
                video.muted = false;
                // Retry from the explicit user gesture after autoplay may have muted playback.
                video.play().catch(console.warn);
            } else if (icon === 'mdi:volume-high') {
                video.muted = true;
            } else if (icon === 'mdi:fullscreen') {
                this.requestFullscreen().catch(console.warn);
            } else if (icon === 'mdi:fullscreen-exit') {
                document.exitFullscreen().catch(console.warn);
            } else if (icon === 'mdi:floppy') {
                this.saveScreenshot();
            } else if (icon === 'mdi:picture-in-picture-bottom-right') {
                video.requestPictureInPicture().catch(console.warn);
            } else if (icon === 'mdi:rectangle') {
                document.exitPictureInPicture().catch(console.warn);
            } else if (ev.target.className === 'stream') {
                this.nextStream(true);
                ev.target.innerText = this.streamName;
            }
        });

        const spinner = this.querySelector('.spinner');
        video.addEventListener('waiting', () => { spinner.style.display = 'block'; });
        video.addEventListener('playing', () => { spinner.style.display = 'none'; });

        const play = this.querySelector('.play');
        video.addEventListener('play', () => { play.style.display = 'none'; });
        video.addEventListener('pause', () => { play.style.display = 'block'; });

        const volume = this.querySelector('.volume');
        video.addEventListener('loadeddata', () => {
            volume.style.display = this.hasAudio ? 'block' : 'none';
        });
        video.addEventListener('volumechange', () => {
            volume.icon = video.muted ? 'mdi:volume-mute' : 'mdi:volume-high';
        });

        const stream = this.querySelector('.stream');
        stream.style.display = this.config.streams.length > 1 ? 'block' : 'none';
    }

    renderAudioControl() {
        if (!this.config.audio_control || this.config.ui) return;

        // A compact audio-only control for cards that hide the browser-native
        // media controls but still need an explicit user gesture to unmute.
        this.video.controls = false;

        const card = this.querySelector('.card');
        card.insertAdjacentHTML('beforebegin', `
            <style>
                .audio-control {
                    position: absolute;
                    right: 8px;
                    bottom: 8px;
                    z-index: 3;
                    color: white;
                    cursor: pointer;
                    padding: 6px;
                    border-radius: 50%;
                    background: rgba(0, 0, 0, 0.35);
                    display: none;
                }
            </style>
        `);
        card.insertAdjacentHTML('beforeend',
            '<ha-icon class="audio-control" icon="mdi:volume-high" title="Audio"></ha-icon>');

        const video = this.video;
        const control = this.querySelector('.audio-control');
        const update = () => {
            control.icon = video.muted ? 'mdi:volume-mute' : 'mdi:volume-high';
            control.style.display = this.hasAudio ? 'block' : 'none';
        };

        control.addEventListener('click', ev => {
            ev.preventDefault();
            ev.stopPropagation();
            if (video.muted) {
                video.muted = false;
                // The click is a user gesture, so retry audible playback after
                // the browser's autoplay policy may have forced muted playback.
                video.play().catch(console.warn);
            } else {
                video.muted = true;
            }
        });

        video.addEventListener('loadeddata', update);
        video.addEventListener('playing', update);
        video.addEventListener('volumechange', update);
        update();
    }

    renderShortcuts() {
        if (!this.config.shortcuts) return;

        const card = this.querySelector('.card');
        card.insertAdjacentHTML('beforebegin', `
            <style>
                .shortcuts {
                    position: absolute;
                    top: 5px;
                    left: 5px;
                }
            </style>
        `);
        card.insertAdjacentHTML('beforeend', '<div class="shortcuts"></div>');

        const shortcuts = this.querySelector('.shortcuts');
        shortcuts.addEventListener('click', ev => {
            const index = ev.target.dataset.index;
            if (index === undefined) return;
            const value = this.config.shortcuts[index];

            if (value.tap_action) {
                this.performAction(value.tap_action, ev.target).catch(err => console.error('WebRTC shortcut action failed', err));
                return;
            }

            if (value.more_info !== undefined) {
                const event = new Event('hass-more-info', {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                });
                event.detail = {entityId: value.more_info};
                ev.target.dispatchEvent(event);
            }
            if (value.service !== undefined) {
                const [domain, name] = value.service.split('.');
                this.hass.callService(domain, name, value.service_data || {});
            }
        });

        this.renderTemplate('shortcuts', () => {
            shortcuts.innerHTML = this.config.shortcuts.map((value, index) => `
                <ha-icon data-index="${index}" icon="${value.icon}" title="${value.name}"></ha-icon>
            `).join('');
        });
    }

    renderStyle() {
        if (!this.config.style) return;

        const style = document.createElement('style');
        const card = this.querySelector('.card');
        card.insertAdjacentElement('beforebegin', style);

        this.renderTemplate('style', () => {
            style.innerText = this.config.style;
        });
    }

    renderTemplate(name, renderHTML) {
        const config = this.config[name];
        const template = typeof config === 'string' ? config : JSON.stringify(config);
        if (template.indexOf('${') >= 0) {
            const render = () => {
                try {
                    const states = this.hass ? this.hass.states : undefined;
                    this.config[name] = JSON.parse(eval('`' + template + '`'));
                    renderHTML();
                } catch (e) {
                    console.debug(e);
                }
            };
            this.onhass.push(render);
            render();
        } else {
            renderHTML();
        }
    }

    get hasAudio() {
        return (
            (this.video.srcObject && this.video.srcObject.getAudioTracks && this.video.srcObject.getAudioTracks().length) ||
            (this.video.mozHasAudio || this.video.webkitAudioDecodedByteCount) ||
            (this.video.audioTracks && this.video.audioTracks.length)
        );
    }
}

customElements.define('webrtc-camera', WebRTCCamera);

const card = {
    type: 'webrtc-camera',
    name: 'WebRTC Camera',
    preview: false,
    description: 'WebRTC camera allows you to view the stream of almost any camera without delay',
};
if (window.customCards) window.customCards.push(card);
else window.customCards = [card];
