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
