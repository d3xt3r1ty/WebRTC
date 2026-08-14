from pathlib import Path

p = Path('custom_components/webrtc/www/webrtc-camera.js')
s = p.read_text()

# Insert shared keep-alive registry and lifecycle methods immediately after class declaration.
needle = "class WebRTCCamera extends VideoRTC {\n"
insert = r'''class WebRTCCamera extends VideoRTC {
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
'''
assert needle in s
s = s.replace(needle, insert, 1)

# Document defaults by making setConfig normalize numeric options.
needle = "        this.config = Object.assign({\n            mode: config.mse === false ? 'webrtc' : config.webrtc === false ? 'mse' : this.mode,\n            media: this.media,\n            streams: [{url: config.url, entity: config.entity}],\n            poster_remote: config.poster && (config.poster.indexOf('://') > 0 || config.poster.charAt(0) === '/'),\n        }, config);\n"
replacement = "        this.config = Object.assign({\n            mode: config.mse === false ? 'webrtc' : config.webrtc === false ? 'mse' : this.mode,\n            media: this.media,\n            streams: [{url: config.url, entity: config.entity}],\n            poster_remote: config.poster && (config.poster.indexOf('://') > 0 || config.poster.charAt(0) === '/'),\n            keep_alive: 0,\n            keep_alive_streams_max: 0,\n        }, config);\n"
assert needle in s
s = s.replace(needle, replacement, 1)

p.write_text(s)

manifest = Path('custom_components/webrtc/manifest.json')
m = manifest.read_text()
m = m.replace('"version": "v3.6.2-nav.6"', '"version": "v3.6.2-nav.7"', 1)
manifest.write_text(m)
