from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]

def sub(path, pattern, repl, count=1):
    p = root / path
    text = p.read_text()
    new, n = re.subn(pattern, repl, text, count=count, flags=re.S)
    if n != count:
        raise SystemExit(f"{path}: expected {count} replacement(s), got {n}: {pattern[:100]}")
    p.write_text(new)

camera = "custom_components/webrtc/www/webrtc-camera.js"
dptz = "custom_components/webrtc/www/digital-ptz.js"

sub(camera, r"import \{DigitalPTZ\} from './digital-ptz.js\?v=3\.3\.0';", "import {DigitalPTZ} from './digital-ptz.js?v=3.4.0';")

# Async action sequences, including lightweight delays.
sub(camera, r'    performAction\(action, source = this\) \{.*?\n    \}\n\n    renderActions\(\) \{', '''    async performAction(action, source = this) {
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

    renderActions() {''')

# Avoid unhandled rejections from gesture/shortcut action sequences.
text = (root / camera).read_text()
text = text.replace('this.performAction(holdAction, player);', "this.performAction(holdAction, player).catch(err => console.error('WebRTC hold action failed', err));")
text = text.replace('this.performAction(tapAction, player);', "this.performAction(tapAction, player).catch(err => console.error('WebRTC tap action failed', err));")
text = text.replace('this.performAction(value.tap_action, ev.target);', "this.performAction(value.tap_action, ev.target).catch(err => console.error('WebRTC shortcut action failed', err));")
(root / camera).write_text(text)

# Region overlay styling and SVG layer. It lives inside ptz-transform so the same
# transform applies to pristine image and boxes.
sub(camera, r'            \.static-image \{\n                width: 100%;.*?                -webkit-user-drag: none;\n            \}', '''            .static-image {
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
            }''')

sub(camera, r'            this.querySelector\(\'\.ptz-transform\'\)\.appendChild\(this.staticImage\);\n            this.updateStaticImage\(\);', '''            this.querySelector('.ptz-transform').appendChild(this.staticImage);
            this.regionOverlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            this.regionOverlay.classList.add('region-overlay');
            this.regionOverlay.setAttribute('viewBox', '0 0 1 1');
            this.regionOverlay.setAttribute('preserveAspectRatio', 'none');
            this.querySelector('.ptz-transform').appendChild(this.regionOverlay);
            this.updateStaticImage();''')

# Add region metadata/overlay/update methods before renderDigitalPTZ.
sub(camera, r'\n    renderDigitalPTZ\(\) \{', '''
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

    renderDigitalPTZ() {''')

# Hook region updates to image load and HA state updates.
sub(camera, r'        this.digitalPTZ = new DigitalPTZ\(\n            this.querySelector\(\'\.player\'\),\n            this.querySelector\(\'\.player \.ptz-transform\'\),\n            media,\n            digitalOptions\n        \);', '''        this.digitalPTZ = new DigitalPTZ(
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
        }''')

# Replace slider controller with optimistic wheel-aware controller.
sub(camera, r'        if \(showZoomSlider\) \{\n            const range = this.querySelector\(\'\.ptz-zoom-range\'\);.*?            range.addEventListener\(\'click\', ev => ev.stopPropagation\(\)\);\n        \}', '''        let entityWheelZoom = null;
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
        }''')

# Wheel now increments the optimistic target rather than repeatedly reading stale HA state.
sub(camera, r'                if \(showZoomSlider\) \{\n                    const state = this.hass\?\.states\?\.\[zoomEntity\];.*?                        this.hass.callService\(\'number\', \'set_value\', \{entity_id: zoomEntity, value: target\}\)\n                            \.catch\(err => console.error\(\'WebRTC PTZ wheel zoom service call failed\', err\)\);\n                    \}\n                \} else if \(wheelUsesJoystick\)', '''                if (showZoomSlider) {
                    entityWheelZoom?.(direction);
                } else if (wheelUsesJoystick)''')

# DigitalPTZ: public reset/fitRegions operations with aspect-aware fitting.
sub(dptz, r'    this.recomputeRects = \(\) => \{\n      this.transform.updateRects\(this.videoEl, this.containerEl\);\n      this.transform.zoomAtCoords\(1, 0, 0\); // clamp transform\n      this.render\(\);\n    \};', '''    this.recomputeRects = () => {
      this.transform.updateRects(this.videoEl, this.containerEl);
      this.transform.zoomAtCoords(1, 0, 0); // clamp transform
      this.render();
      if (this.onRectsChanged) this.onRectsChanged();
    };''')
sub(dptz, r'  destroy\(\) \{', '''  reset() {
    if (!this.transform.videoRect) return false;
    this.transform.setView(1, 0.5, 0.5);
    this.render(true);
    return true;
  }
  fitRegions(regions, options = {}) {
    if (!this.transform.videoRect || !this.transform.containerRect || !Array.isArray(regions) || !regions.length) return false;
    const boxes = regions.map(r => r && r.bbox).filter(b => Array.isArray(b) && b.length === 4);
    if (!boxes.length) return false;
    let x1 = Math.min(...boxes.map(b => Math.min(Number(b[0]), Number(b[2]))));
    let y1 = Math.min(...boxes.map(b => Math.min(Number(b[1]), Number(b[3]))));
    let x2 = Math.max(...boxes.map(b => Math.max(Number(b[0]), Number(b[2]))));
    let y2 = Math.max(...boxes.map(b => Math.max(Number(b[1]), Number(b[3]))));
    if (![x1,y1,x2,y2].every(Number.isFinite)) return false;
    const padding = Math.max(0, Number(options.padding ?? 0));
    const w = Math.max(0.0001, x2-x1), h = Math.max(0.0001, y2-y1);
    x1 = Math.max(0, x1-w*padding); x2 = Math.min(1, x2+w*padding);
    y1 = Math.max(0, y1-h*padding); y2 = Math.min(1, y2+h*padding);
    const rw = Math.max(0.0001, x2-x1), rh = Math.max(0.0001, y2-y1);
    const tr = this.transform;
    const scaleX = tr.containerRect.width / Math.max(1, tr.videoRect.width * rw);
    const scaleY = tr.containerRect.height / Math.max(1, tr.videoRect.height * rh);
    const minScale = Math.max(1, Number(options.minScale ?? 1));
    const maxScale = Math.max(minScale, Number(options.maxScale ?? MAX_ZOOM));
    const scale = clamp(Math.min(scaleX, scaleY), minScale, Math.min(MAX_ZOOM, maxScale));
    tr.setView(scale, (x1+x2)/2, (y1+y2)/2);
    this.render(true);
    return true;
  }
  destroy() {''')

sub(dptz, r'  // x,y are relative to viewport \(clientX, clientY\)\n  zoomAtCoords', '''  setView(scale, centerX = 0.5, centerY = 0.5) {
    if (!this.videoRect) return;
    this.scale = clamp(Number(scale) || 1, 1, MAX_ZOOM);
    const bound = (this.scale - 1) / 2;
    this.x = clamp(-(Number(centerX) - 0.5) * this.scale, -bound, bound);
    this.y = clamp(-(Number(centerY) - 0.5) * this.scale, -bound, bound);
    this.persistTransform();
  }
  // x,y are relative to viewport (clientX, clientY)
  zoomAtCoords''')

print('WebRTC ROI/action/wheel patch applied')
