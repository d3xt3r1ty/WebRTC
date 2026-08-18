from pathlib import Path
p=Path('custom_components/webrtc/www/webrtc-camera.js')
s=p.read_text()
s=s.replace("""            .player .ptz-transform {\n                height: 100%;\n                position: relative;\n                z-index: 1;\n            }\n            .initial-stream {\n                position: absolute;\n                inset: 0;\n                z-index: 2;\n""","""            .player .ptz-transform {\n                height: 100%;\n                position: relative;\n                z-index: 1;\n            }\n            .initial-stream {\n                position: absolute;\n                inset: 0;\n                z-index: 1;\n""",1)
# explicitly put interaction/UI overlays above startup video
for cls in ['.header {','.shortcuts {','.ptz {','.custom-ui {','.actions {']:
    if cls in s:
        s=s.replace(cls, cls+"\n                z-index: 3;",1)
p.write_text(s)
Path('.github/patch_3616_fixui.py').unlink()
