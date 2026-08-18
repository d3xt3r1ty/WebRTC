from pathlib import Path

p = Path('custom_components/webrtc/www/webrtc-camera.js')
s = p.read_text()

old = """        WebRTCCamera.keepAliveRegistry = WebRTCCamera.keepAliveRegistry.filter(item => item.card !== this);
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
"""
new = """        WebRTCCamera.keepAliveRegistry = WebRTCCamera.keepAliveRegistry.filter(item => item.card !== this);
        const group = String(this.config?.keep_alive_group || 'default');
        WebRTCCamera.keepAliveRegistry.push({card: this, detachedAt, group});

        const max = Math.max(0, parseInt(this.config?.keep_alive_streams_max ?? 0));
        if (max > 0) {
            const groupItems = WebRTCCamera.keepAliveRegistry
                .filter(item => (item.group || 'default') === group)
                .sort((a, b) => a.detachedAt - b.detachedAt);
            while (groupItems.length > max) {
                const oldest = groupItems.shift();
                if (!oldest) continue;
                WebRTCCamera.keepAliveRegistry = WebRTCCamera.keepAliveRegistry.filter(item => item !== oldest);
                if (oldest.card.keepAliveTID) {
                    clearTimeout(oldest.card.keepAliveTID);
                    oldest.card.keepAliveTID = 0;
                }
                if (!oldest.card.isConnected) oldest.card.ondisconnect();
            }
        }
"""
if old not in s:
    raise SystemExit('keep-alive block not found')
s = s.replace(old, new, 1)

old = """            keep_alive: 0,
            keep_alive_streams_max: 0,
"""
new = """            keep_alive: 0,
            keep_alive_group: 'default',
            keep_alive_streams_max: 0,
"""
if old not in s:
    raise SystemExit('keep-alive defaults not found')
s = s.replace(old, new, 1)

old = """                        this._initialStreamReused = true;
                        this.initialStream.video.srcObject = reusableMedia;
                        this.initialStream.video.muted = true;
"""
new = """                        this._initialStreamReused = true;
                        const sourceStyle = getComputedStyle(reusable.video);
                        if (sourceStyle.aspectRatio && sourceStyle.aspectRatio !== 'auto') {
                            this.initialStream.video.style.aspectRatio = sourceStyle.aspectRatio;
                        }
                        if (sourceStyle.objectFit) this.initialStream.video.style.objectFit = sourceStyle.objectFit;
                        if (sourceStyle.objectPosition) this.initialStream.video.style.objectPosition = sourceStyle.objectPosition;
                        this.initialStream.video.srcObject = reusableMedia;
                        this.initialStream.video.muted = true;
"""
if old not in s:
    raise SystemExit('reused stream block not found')
s = s.replace(old, new, 1)

old = """                pointer-events: none;
            }
            .mode {
"""
new = """                pointer-events: none;
                z-index: 4;
            }
            .mode {
"""
if old not in s:
    raise SystemExit('header block not found')
s = s.replace(old, new, 1)

old = """                .shortcuts {
                    position: absolute;
                    top: 5px;
                    left: 5px;
                }
"""
new = """                .shortcuts {
                    position: absolute;
                    top: 5px;
                    left: 5px;
                    z-index: 4;
                }
"""
if old not in s:
    raise SystemExit('shortcuts block not found')
s = s.replace(old, new, 1)

p.write_text(s)

c = Path('CHANGELOG.md')
cs = c.read_text()
anchor = """## 3.6.16
- `initial_stream` now first reuses a matching kept-alive card's live browser `MediaStream`, avoiding a second WebRTC negotiation during dashboard-to-full-view navigation.
- If no reusable kept-alive stream exists, the existing initial-stream connection is still attempted in parallel and never delays the main stream.
- Main-stream handoff continues to wait for the first rendered main frame.
"""
replacement = anchor + """- Reused initial streams inherit the source video's computed aspect ratio, object-fit and object-position so dashboard presentation carries through during handoff.
- Card chrome now stays above the initial-stream overlay; shortcuts and header are explicitly layered with PTZ/audio controls.
- `keep_alive_group` provides independent keep-alive pools, so overview and main-stream limits no longer evict one another.
"""
if anchor not in cs:
    raise SystemExit('3.6.16 changelog anchor not found')
c.write_text(cs.replace(anchor, replacement, 1))

Path('.github/patch_3616_followup.py').unlink()
Path('.github/workflows/patch-3616-followup.yml').unlink()
