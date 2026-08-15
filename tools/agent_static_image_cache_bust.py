from pathlib import Path
import json

js_path = Path('custom_components/webrtc/www/webrtc-camera.js')
text = js_path.read_text()
old = '''    updateStaticImage() {
        if (!this.imageMode || !this.staticImage || !this.hass) return;
        let source = String(this.config.image || '').trim();
        const state = this.hass.states?.[source];
        if (state?.attributes?.entity_picture) source = state.attributes.entity_picture;
        if (!source) return;
        if (!/^https?:\\/\\//i.test(source)) source = this.hass.hassUrl(source);
        if (this.staticImage.src !== source) this.staticImage.src = source;
    }
'''
new = '''    updateStaticImage() {
        if (!this.imageMode || !this.staticImage || !this.hass) return;
        let source = String(this.config.image || '').trim();
        const state = this.hass.states?.[source];
        if (state?.attributes?.entity_picture) source = state.attributes.entity_picture;
        if (!source) return;
        if (!/^https?:\\/\\//i.test(source)) source = this.hass.hassUrl(source);

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
'''
if old not in text:
    raise SystemExit('updateStaticImage block not found')
js_path.write_text(text.replace(old, new, 1))

manifest_path = Path('custom_components/webrtc/manifest.json')
manifest = json.loads(manifest_path.read_text())
manifest['version'] = '3.6.6'
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
