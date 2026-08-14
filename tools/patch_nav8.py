from pathlib import Path

root = Path('custom_components/webrtc')

# ---- webrtc-camera.js -------------------------------------------------------
p = root / 'www/webrtc-camera.js'
s = p.read_text()

s = s.replace(
"""        if (!config.url && !config.entity && !config.streams) throw new Error('Missing `url` or `entity` or `streams`');
""",
"""        if (!config.url && !config.entity && !config.streams && !config.image) throw new Error('Missing `url`, `entity`, `streams` or `image`');
        this.imageMode = Boolean(config.image);
""", 1)

s = s.replace(
"""        this.streamID = -1;
        this.nextStream(false);

        this.onhass = [];
""",
"""        this.streamID = -1;
        if (!this.imageMode) this.nextStream(false);

        this.onhass = [];
""", 1)

s = s.replace(
"""    set hass(hass) {
        this._hass = hass;
        this.onhass.forEach(fn => fn());
    }
""",
"""    set hass(hass) {
        this._hass = hass;
        if (this.imageMode) this.updateStaticImage();
        this.onhass.forEach(fn => fn());
    }
""", 1)

needle = """    getCardSize() {
        return 5;
    }
"""
insert = """    updateStaticImage() {
        if (!this.imageMode || !this.staticImage || !this.hass) return;
        let source = String(this.config.image || '').trim();
        const state = this.hass.states?.[source];
        if (state?.attributes?.entity_picture) source = state.attributes.entity_picture;
        if (!source) return;
        if (!/^https?:\\/\\//i.test(source)) source = this.hass.hassUrl(source);
        if (this.staticImage.src !== source) this.staticImage.src = source;
    }

""" + needle
assert needle in s
s = s.replace(needle, insert, 1)

s = s.replace(
"""    nextStream(reload) {
        this.streamID = (this.streamID + 1) % this.config.streams.length;
""",
"""    nextStream(reload) {
        if (this.imageMode) return;
        this.streamID = (this.streamID + 1) % this.config.streams.length;
""", 1)

s = s.replace(
"""    onconnect() {
        if (!this.config || !this.hass) return false;
""",
"""    onconnect() {
        if (!this.config || !this.hass) return false;
        if (this.imageMode) {
            this.updateStaticImage();
            this.setStatus('IMG', this.config.title || '');
            return false;
        }
""", 1)

s = s.replace(
"""            .player .ptz-transform {
                height: 100%;
            }
""",
"""            .player .ptz-transform {
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
""", 1)

s = s.replace(
"""        this.querySelector = selectors => this.shadowRoot.querySelector(selectors);
        this.querySelector('.ptz-transform').appendChild(this.video);

        const mode = this.querySelector('.mode');
""",
"""        this.querySelector = selectors => this.shadowRoot.querySelector(selectors);
        if (this.imageMode) {
            this.staticImage = document.createElement('img');
            this.staticImage.className = 'static-image';
            this.staticImage.alt = this.config.title || 'Camera snapshot';
            this.staticImage.draggable = false;
            this.querySelector('.ptz-transform').appendChild(this.staticImage);
            this.updateStaticImage();
        } else {
            this.querySelector('.ptz-transform').appendChild(this.video);
        }

        const mode = this.querySelector('.mode');
""", 1)

s = s.replace(
"""        if (this.config.muted !== undefined) this.video.muted = this.config.muted;
        if (this.config.poster_remote) this.video.poster = this.config.poster;
""",
"""        if (!this.imageMode) {
            if (this.config.muted !== undefined) this.video.muted = this.config.muted;
            if (this.config.poster_remote) this.video.poster = this.config.poster;
        }
""", 1)

s = s.replace(
"""        new DigitalPTZ(
            this.querySelector('.player'),
            this.querySelector('.player .ptz-transform'),
            this.video,
            Object.assign({}, this.config.digital_ptz, {persist_key: this.config.url})
        );
""",
"""        const media = this.imageMode ? this.staticImage : this.video;
        new DigitalPTZ(
            this.querySelector('.player'),
            this.querySelector('.player .ptz-transform'),
            media,
            Object.assign({}, this.config.digital_ptz, {persist_key: this.config.image || this.config.url})
        );
""", 1)

# Avoid touching native video controls in image mode.
s = s.replace(
"""        this.video.controls = false;

        const player = this.querySelector('.player');
""",
"""        if (!this.imageMode) this.video.controls = false;

        const player = this.querySelector('.player');
""", 1)

old_handle = """        const template = JSON.stringify(this.config.ptz);
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
"""
new_handle = """        const handle = (path, vars = {}) => {
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
            if (!domain || !service) {
                console.error('WebRTC PTZ: invalid service', this.config.ptz.service);
                return;
            }
            const data = substitute(dataTemplate);
            this.hass.callService(domain, service, data).catch(err =>
                console.error(`WebRTC PTZ ${path} service call failed`, err, data)
            );
        };
"""
assert old_handle in s
s = s.replace(old_handle, new_handle, 1)

# Add a heartbeat timer and retained vector for joystick safety watchdog refresh.
s = s.replace(
"""            let lastSend = 0;
            let lastPan = 0;
            let lastTilt = 0;
""",
"""            let lastSend = 0;
            let lastPan = 0;
            let lastTilt = 0;
            let lastSpeed = 0;
            let heartbeat = null;
""", 1)

s = s.replace(
"""            const stopMove = () => {
                if (moving) handle('joystick_stop');
                moving = false;
                lastPan = 0;
                lastTilt = 0;
                resetStick();
            };
""",
"""            const stopMove = () => {
                if (heartbeat) clearInterval(heartbeat);
                heartbeat = null;
                if (moving) handle('joystick_stop');
                moving = false;
                lastPan = 0;
                lastTilt = 0;
                lastSpeed = 0;
                resetStick();
            };

            const startHeartbeat = () => {
                if (heartbeat) return;
                heartbeat = setInterval(() => {
                    if (activePointer === null || !moving) return;
                    handle('joystick', {pan: lastPan, tilt: lastTilt, zoom: 0, speed: lastSpeed});
                    lastSend = performance.now();
                }, updateMs);
            };
""", 1)

s = s.replace(
"""                        moving = false;
                        lastPan = 0;
                        lastTilt = 0;
                    }
                    return;
""",
"""                        moving = false;
                        lastPan = 0;
                        lastTilt = 0;
                        lastSpeed = 0;
                        if (heartbeat) clearInterval(heartbeat);
                        heartbeat = null;
                    }
                    return;
""", 1)

s = s.replace(
"""                    lastPan = pan;
                    lastTilt = tilt;
                    moving = true;
                }
""",
"""                    lastPan = pan;
                    lastTilt = tilt;
                    lastSpeed = magnitude;
                    moving = true;
                    startHeartbeat();
                }
""", 1)

p.write_text(s)

# ---- digital-ptz.js ---------------------------------------------------------
p = root / 'www/digital-ptz.js'
s = p.read_text()

s = s.replace(
"""    this.videoEl.addEventListener("loadedmetadata", this.recomputeRects);
    this.resizeObserver = new ResizeObserver(this.recomputeRects);
""",
"""    this.videoEl.addEventListener("loadedmetadata", this.recomputeRects);
    this.videoEl.addEventListener("load", this.recomputeRects);
    this.resizeObserver = new ResizeObserver(this.recomputeRects);
""", 1)

s = s.replace(
"""    this.videoEl.removeEventListener("loadedmetadata", this.recomputeRects);
    this.resizeObserver.unobserve(this.containerEl);
""",
"""    this.videoEl.removeEventListener("loadedmetadata", this.recomputeRects);
    this.videoEl.removeEventListener("load", this.recomputeRects);
    this.resizeObserver.unobserve(this.containerEl);
""", 1)

old_dims = """function getTransformedDimensions(video) {
  const { videoWidth, videoHeight } = video;
  if (!videoHeight || !videoWidth) return undefined;
  var transform = window.getComputedStyle(video).getPropertyValue("transform");
  const match = transform.match(/matrix\\((.+)\\)/);
  if (!match || !match[1]) return { videoWidth, videoHeight }; // the video isn't transformed
  const matrix = new DOMMatrix(match[1].split(", ").map(Number));
  const points = [
    new DOMPoint(0, 0),
    new DOMPoint(videoWidth, 0),
    new DOMPoint(0, videoHeight),
    new DOMPoint(videoWidth, videoHeight),
  ].map((point) => point.matrixTransform(matrix));
"""
new_dims = """function getTransformedDimensions(video) {
  const videoWidth = video.videoWidth || video.naturalWidth || 0;
  const videoHeight = video.videoHeight || video.naturalHeight || 0;
  if (!videoHeight || !videoWidth) return undefined;
  var transform = window.getComputedStyle(video).getPropertyValue("transform");
  const match = transform.match(/matrix\\((.+)\\)/);
  if (!match || !match[1]) return { videoWidth, videoHeight }; // media isn't transformed
  const matrix = new DOMMatrix(match[1].split(", ").map(Number));
  const points = [
    new DOMPoint(0, 0),
    new DOMPoint(videoWidth, 0),
    new DOMPoint(0, videoHeight),
    new DOMPoint(videoWidth, videoHeight),
  ].map((point) => point.matrixTransform(matrix));
"""
assert old_dims in s
s = s.replace(old_dims, new_dims, 1)
p.write_text(s)

# ---- manifest ---------------------------------------------------------------
p = root / 'manifest.json'
s = p.read_text()
s = s.replace('"version": "v3.6.2-nav.7"', '"version": "v3.6.2-nav.8"')
p.write_text(s)
