from pathlib import Path

p = Path('custom_components/webrtc/www/webrtc-camera.js')
s = p.read_text()

# Add helper methods after streamName getter.
needle = """    get streamName() {\n        return this.config.streams[this.streamID].name || `S${this.streamID}`;\n    }\n\n"""
insert = """    get streamName() {\n        return this.config.streams[this.streamID].name || `S${this.streamID}`;\n    }\n\n    static streamMatches(card, stream) {\n        if (!card?.config || !stream) return false;\n        if (stream.entity) return card.config.entity === stream.entity;\n        if (stream.url) return card.config.url === stream.url;\n        return false;\n    }\n\n    static reusableInitialStream(stream, exclude) {\n        const now = Date.now();\n        for (let i = WebRTCCamera.keepAliveRegistry.length - 1; i >= 0; i--) {\n            const item = WebRTCCamera.keepAliveRegistry[i];\n            const card = item?.card;\n            if (!card || card === exclude || !WebRTCCamera.streamMatches(card, stream)) continue;\n            const media = card.video?.srcObject;\n            const videoTrack = media?.getVideoTracks?.().find(track => track.readyState === 'live');\n            if (!videoTrack) continue;\n            const seconds = Math.max(0, Number(card.config?.keep_alive || 0));\n            if (seconds && now - item.detachedAt > seconds * 1000) continue;\n            return card;\n        }\n        return null;\n    }\n\n"""
if needle not in s:
    raise SystemExit('streamName insertion point not found')
s = s.replace(needle, insert, 1)

# Replace initial-stream setup in onconnect with reuse-first logic while preserving parallel fallback.
old = """            if (this.initialStream && this.config.initial_stream) {\n                const initial = typeof this.config.initial_stream === 'string'\n                    ? {url: this.config.initial_stream}\n                    : this.config.initial_stream;\n                const initialURL = buildStreamURL(initial);\n                if (initialURL) {\n                    this._mainStreamReady = false;\n                    this.initialStream.style.display = 'block';\n                    this.initialStream.style.opacity = '1';\n                    this.initialStream.ondisconnect();\n                    this.initialStream.wsURL = initialURL;\n                    this.initialStream.onconnect();\n                }\n            }\n"""
new = """            if (this.initialStream && this.config.initial_stream) {\n                const initial = typeof this.config.initial_stream === 'string'\n                    ? {url: this.config.initial_stream}\n                    : this.config.initial_stream;\n                const initialURL = buildStreamURL(initial);\n                if (initialURL) {\n                    this._mainStreamReady = false;\n                    this.initialStream.style.display = 'block';\n                    this.initialStream.style.opacity = '1';\n                    this.initialStream.ondisconnect();\n\n                    const reusable = WebRTCCamera.reusableInitialStream(initial, this);\n                    const reusableMedia = reusable?.video?.srcObject;\n                    if (reusableMedia) {\n                        // Fast path: reuse the already-live browser MediaStream from a\n                        // kept-alive source card. This creates no second WebRTC session.\n                        this._initialStreamReused = true;\n                        this.initialStream.video.srcObject = reusableMedia;\n                        this.initialStream.video.muted = true;\n                        this.initialStream.video.play().catch(() => {});\n                        console.debug('WebRTC initial_stream: reused kept-alive stream', initial.entity || initial.url);\n                    } else {\n                        // Fallback for direct navigation/no kept-alive source. Start a\n                        // normal initial-stream consumer in parallel; never delay main.\n                        this._initialStreamReused = false;\n                        this.initialStream.wsURL = initialURL;\n                        this.initialStream.onconnect();\n                        console.debug('WebRTC initial_stream: no reusable stream; opening fallback', initial.entity || initial.url);\n                    }\n                }\n            }\n"""
if old not in s:
    raise SystemExit('onconnect initial_stream block not found')
s = s.replace(old, new, 1)

p.write_text(s)

m = Path('custom_components/webrtc/manifest.json')
ms = m.read_text()
if '"version": "3.6.15"' not in ms:
    raise SystemExit('expected 3.6.15 manifest')
m.write_text(ms.replace('"version": "3.6.15"', '"version": "3.6.16"', 1))

c = Path('CHANGELOG.md')
cs = c.read_text()
if not cs.startswith('# Changelog\n\n'):
    raise SystemExit('unexpected changelog format')
entry = """# Changelog\n\n## 3.6.16\n- `initial_stream` now first reuses a matching kept-alive card's live browser `MediaStream`, avoiding a second WebRTC negotiation during dashboard-to-full-view navigation.\n- If no reusable kept-alive stream exists, the existing initial-stream connection is still attempted in parallel and never delays the main stream.\n- Main-stream handoff continues to wait for the first rendered main frame.\n\n"""
c.write_text(entry + cs[len('# Changelog\n\n'):])

# Restore the normal validation workflow and remove this helper from final tree.
Path('.github/workflows/hacs.yml').write_text('''name: HACS validation\n\non:\n  push:\n  pull_request:\n\njobs:\n  hacs:\n    runs-on: "ubuntu-latest"\n    steps:\n      - uses: "actions/checkout@v2"\n      - uses: "hacs/action@main"\n        with: { category: "integration" }\n  hassfest:\n    runs-on: "ubuntu-latest"\n    steps:\n      - uses: "actions/checkout@v3"\n      - uses: "home-assistant/actions/hassfest@master"\n''')
Path('.github/patch_3616.py').unlink()
