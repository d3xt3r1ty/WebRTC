from pathlib import Path

root = Path('custom_components/webrtc')

# DigitalPTZ: eliminate image-load race by using a stable ready handler and
# scheduling a recompute for already-loaded/cached media.
p = root / 'www/digital-ptz.js'
s = p.read_text()
s = s.replace(
'''    this.videoEl.addEventListener("loadedmetadata", this.recomputeRects);\n    this.videoEl.addEventListener("load", this.recomputeRects);\n    this.resizeObserver = new ResizeObserver(this.recomputeRects);\n    this.resizeObserver.observe(this.containerEl);\n    this.recomputeRects();\n''',
'''    this.mediaReadyHandler = () => requestAnimationFrame(this.recomputeRects);\n    this.videoEl.addEventListener("loadedmetadata", this.mediaReadyHandler);\n    this.videoEl.addEventListener("load", this.mediaReadyHandler);\n    this.resizeObserver = new ResizeObserver(this.recomputeRects);\n    this.resizeObserver.observe(this.containerEl);\n    this.recomputeRects();\n    if ((this.videoEl.tagName === "IMG" && this.videoEl.complete && this.videoEl.naturalWidth) ||\n        (this.videoEl.tagName === "VIDEO" && this.videoEl.readyState >= 1)) {\n      this.mediaReadyHandler();\n    }\n''', 1)
s = s.replace(
'''    this.videoEl.removeEventListener("loadedmetadata", this.recomputeRects);\n    this.videoEl.removeEventListener("load", this.recomputeRects);\n''',
'''    this.videoEl.removeEventListener("loadedmetadata", this.mediaReadyHandler);\n    this.videoEl.removeEventListener("load", this.mediaReadyHandler);\n''', 1)
p.write_text(s)

# Bump fork patch version.
p = root / 'manifest.json'
s = p.read_text().replace('"version": "v3.6.2-nav.8"', '"version": "v3.6.2-nav.9"')
p.write_text(s)
