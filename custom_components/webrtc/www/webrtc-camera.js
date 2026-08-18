// WebRTC Camera 3.6.18 compatibility layer.
// Keep the 3.6.17 implementation intact in the core module and patch only the
// runtime behaviours needed for initial-stream presentation and mobile PTZ.
import './webrtc-camera-core.js?v=3.6.18';

const WebRTCCamera = customElements.get('webrtc-camera');

if (WebRTCCamera && !WebRTCCamera.__v3618Patched) {
    WebRTCCamera.__v3618Patched = true;

    // Remember the source video's actual on-screen presentation while the card
    // is connected. A kept-alive card is detached by the time another card asks
    // to reuse it, so getBoundingClientRect() at reuse time can already be 0x0.
    const connectedCallback = WebRTCCamera.prototype.connectedCallback;
    WebRTCCamera.prototype.connectedCallback = function(...args) {
        const result = connectedCallback.apply(this, args);

        if (this.video && !this._presentationObserver) {
            const capturePresentation = () => {
                if (!this.video) return;
                const rect = this.video.getBoundingClientRect();
                if (!(rect.width > 0 && rect.height > 0)) return;
                const style = getComputedStyle(this.video);
                this._lastVideoPresentation = {
                    ratio: rect.width / rect.height,
                    aspectRatio: style.aspectRatio,
                    objectFit: style.objectFit,
                    objectPosition: style.objectPosition,
                };
            };

            this._presentationObserver = new ResizeObserver(capturePresentation);
            this._presentationObserver.observe(this.video);
            requestAnimationFrame(capturePresentation);
        }

        return result;
    };

    // Apply the source card's last real rendered box to the temporary reused
    // video. Merely copying CSS aspect-ratio is ineffective when VideoRTC has
    // already given the child both width:100% and height:100%.
    const reusableInitialStream = WebRTCCamera.reusableInitialStream;
    WebRTCCamera.reusableInitialStream = function(stream, exclude) {
        const reusable = reusableInitialStream.call(this, stream, exclude);
        const target = exclude?.initialStream?.video;
        if (!reusable?.video || !target) return reusable;

        const fallbackStyle = getComputedStyle(reusable.video);
        const presentation = reusable._lastVideoPresentation || {};
        const ratio = Number(presentation.ratio);
        const aspectRatio = Number.isFinite(ratio) && ratio > 0
            ? `${ratio}`
            : presentation.aspectRatio || fallbackStyle.aspectRatio;

        if (aspectRatio && aspectRatio !== 'auto') {
            exclude.initialStream.style.display = 'flex';
            exclude.initialStream.style.alignItems = 'center';
            exclude.initialStream.style.justifyContent = 'center';
            target.style.aspectRatio = aspectRatio;
            target.style.width = '100%';
            target.style.height = 'auto';
            target.style.maxWidth = '100%';
            target.style.maxHeight = '100%';
        }

        const objectFit = presentation.objectFit || fallbackStyle.objectFit;
        const objectPosition = presentation.objectPosition || fallbackStyle.objectPosition;
        if (objectFit) target.style.objectFit = objectFit;
        if (objectPosition) target.style.objectPosition = objectPosition;

        return reusable;
    };

    // Draw detection regions after DigitalPTZ has scaled/panned the image.
    // The core overlay lives inside .ptz-transform, so it is itself transformed.
    // Move it to the player and project normalized source boxes into final
    // screen-space coordinates instead. This keeps boxes aligned and line width
    // constant regardless of digital zoom or source/card aspect-ratio scaling.
    WebRTCCamera.prototype.updateRegionOverlay = function() {
        if (!this.regionOverlay || !this.digitalPTZ) return;
        const cfg = this.config.digital_ptz?.region_overlay || {};
        const {regions, primary} = this.getDigitalRegions();
        this.regionOverlay.innerHTML = '';
        this.regionOverlay.style.display = cfg.show === false || !regions.length ? 'none' : 'block';
        if (this.regionOverlay.style.display === 'none') return;

        const tr = this.digitalPTZ.transform;
        if (!tr.videoRect || !tr.containerRect) return;

        const containerWidth = tr.containerRect.width;
        const containerHeight = tr.containerRect.height;
        if (!(containerWidth > 0 && containerHeight > 0)) return;

        // CSS transform is translate(...) scale(...) around the transform
        // element's centre. Project the untransformed rendered-video rectangle
        // through that same transform, then place normalized detections inside it.
        const scale = Number(tr.scale) || 1;
        const tx = (Number(tr.x) || 0) * tr.videoRect.width;
        const ty = (Number(tr.y) || 0) * tr.videoRect.height;
        const centreX = containerWidth / 2;
        const centreY = containerHeight / 2;
        const baseLeft = tr.videoRect.x - tr.containerRect.x;
        const baseTop = tr.videoRect.y - tr.containerRect.y;
        const left = centreX + (baseLeft - centreX) * scale + tx;
        const top = centreY + (baseTop - centreY) * scale + ty;
        const width = tr.videoRect.width * scale;
        const height = tr.videoRect.height * scale;

        this.regionOverlay.style.left = '0px';
        this.regionOverlay.style.top = '0px';
        this.regionOverlay.style.width = '100%';
        this.regionOverlay.style.height = '100%';
        this.regionOverlay.style.overflow = 'hidden';
        this.regionOverlay.setAttribute('viewBox', `0 0 ${containerWidth} ${containerHeight}`);
        this.regionOverlay.setAttribute('preserveAspectRatio', 'none');

        const selection = String(cfg.selection ?? 'all').toLowerCase();
        const selected = selection === 'primary' && primary !== null
            ? [regions[primary]].filter(Boolean)
            : regions;
        const lineWidth = Math.max(0.5, Number(cfg.line_width ?? 2));

        selected.forEach(region => {
            const [rx1, ry1, rx2, ry2] = region.bbox.map(Number);
            if (![rx1, ry1, rx2, ry2].every(Number.isFinite)) return;
            const rawX1 = left + Math.min(rx1, rx2) * width;
            const rawY1 = top + Math.min(ry1, ry2) * height;
            const rawX2 = left + Math.max(rx1, rx2) * width;
            const rawY2 = top + Math.max(ry1, ry2) * height;
            const x1 = Math.max(0, Math.min(containerWidth, rawX1));
            const y1 = Math.max(0, Math.min(containerHeight, rawY1));
            const x2 = Math.max(0, Math.min(containerWidth, rawX2));
            const y2 = Math.max(0, Math.min(containerHeight, rawY2));
            if (x2 <= x1 || y2 <= y1) return;
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', String(x1));
            rect.setAttribute('y', String(y1));
            rect.setAttribute('width', String(x2 - x1));
            rect.setAttribute('height', String(y2 - y1));
            rect.setAttribute('stroke-width', String(lineWidth));
            this.regionOverlay.appendChild(rect);
        });
    };

    const renderDigitalPTZ = WebRTCCamera.prototype.renderDigitalPTZ;
    WebRTCCamera.prototype.renderDigitalPTZ = function(...args) {
        const result = renderDigitalPTZ.apply(this, args);

        if (this.imageMode && this.regionOverlay && this.digitalPTZ) {
            const player = this.querySelector?.('.player');
            if (player && this.regionOverlay.parentElement !== player) {
                player.appendChild(this.regionOverlay);
            }
            this.regionOverlay.style.zIndex = '3';

            if (!this.digitalPTZ.__webrtcScreenOverlayPatched) {
                this.digitalPTZ.__webrtcScreenOverlayPatched = true;
                const render = this.digitalPTZ.render;
                this.digitalPTZ.render = (...renderArgs) => {
                    const renderResult = render(...renderArgs);
                    requestAnimationFrame(() => this.updateRegionOverlay());
                    return renderResult;
                };
                const onRectsChanged = this.digitalPTZ.onRectsChanged;
                this.digitalPTZ.onRectsChanged = (...rectArgs) => {
                    if (onRectsChanged) onRectsChanged(...rectArgs);
                    this.updateRegionOverlay();
                };
            }

            requestAnimationFrame(() => this.updateRegionOverlay());
        }

        return result;
    };

    // The core deliberately waits until a touch leaves the joystick deadband
    // before claiming it. On mobile that leaves enough time for the browser or
    // another gesture recogniser to steal/cancel the pointer. Capture the first
    // touch immediately, without changing logical joystick ownership. When a
    // second touch arrives, release the first capture so DigitalPTZ pinch can
    // take over exactly as before.
    const renderPTZ = WebRTCCamera.prototype.renderPTZ;
    WebRTCCamera.prototype.renderPTZ = function(...args) {
        const result = renderPTZ.apply(this, args);
        const ptz = this.config?.ptz;
        const joystickEnabled = Boolean(
            ptz?.service && ptz?.joystick && ptz?.data_joystick && ptz?.data_joystick_stop
        );
        if (!joystickEnabled || ptz.physical_drag === false) return result;

        const joystickMode = String(ptz.joystick_mode || 'dynamic').toLowerCase();
        const surface = joystickMode === 'dynamic'
            ? this.querySelector?.('.player')
            : this.querySelector?.('.ptz-move');
        if (!surface || surface.__webrtcImmediateTouchCapture) return result;
        surface.__webrtcImmediateTouchCapture = true;

        let capturedTouch = null;
        surface.addEventListener('pointerdown', ev => {
            if (ev.pointerType !== 'touch') return;

            if (capturedTouch === null) {
                capturedTouch = ev.pointerId;
                try {
                    surface.setPointerCapture?.(ev.pointerId);
                } catch (err) {
                    console.debug('WebRTC PTZ: immediate touch capture unavailable', err);
                }
                return;
            }

            if (ev.pointerId !== capturedTouch) {
                try {
                    if (surface.hasPointerCapture?.(capturedTouch)) {
                        surface.releasePointerCapture?.(capturedTouch);
                    }
                } catch (err) {
                    console.debug('WebRTC PTZ: touch capture release unavailable', err);
                }
                capturedTouch = null;
            }
        }, true);

        const clearTouch = ev => {
            if (ev.pointerId === capturedTouch) capturedTouch = null;
        };
        surface.addEventListener('pointerup', clearTouch, true);
        surface.addEventListener('pointercancel', clearTouch, true);
        surface.addEventListener('lostpointercapture', clearTouch);

        return result;
    };
}
