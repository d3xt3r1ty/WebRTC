from pathlib import Path

p = Path('custom_components/webrtc/www/webrtc-camera.js')
s = p.read_text()
old = '''        const template = JSON.stringify(this.config.ptz);\n        const handle = (path, vars = {}) => {\n            if (!this.config.ptz['data_' + path]) return;\n            const pan = Number(vars.pan || 0);\n            const tilt = Number(vars.tilt || 0);\n            const zoom = Number(vars.zoom || 0);\n            const speed = Number(vars.speed || Math.hypot(pan, tilt));\n            const config = template.indexOf('${') < 0 ? this.config.ptz : JSON.parse(eval('`' + template + '`'));\n            const [domain, service] = config.service.split('.', 2);\n            const data = config['data_' + path];\n            this.hass.callService(domain, service, data);\n        };\n'''
new = '''        const resolveVars = (value, vars) => {\n            if (typeof value === 'string') {\n                return value.replace(/\\$\\{(pan|tilt|zoom|speed)\\}/g, (_match, key) => String(vars[key] ?? 0));\n            }\n            if (Array.isArray(value)) return value.map(item => resolveVars(item, vars));\n            if (value && typeof value === 'object') {\n                return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, resolveVars(item, vars)]));\n            }\n            return value;\n        };\n        const handle = (path, vars = {}) => {\n            const dataTemplate = this.config.ptz['data_' + path];\n            if (!dataTemplate) return;\n            const pan = Number(vars.pan || 0);\n            const tilt = Number(vars.tilt || 0);\n            const zoom = Number(vars.zoom || 0);\n            const speed = Number(vars.speed || Math.hypot(pan, tilt));\n            const resolved = {pan, tilt, zoom, speed};\n            const [domain, service] = this.config.ptz.service.split('.', 2);\n            const data = resolveVars(dataTemplate, resolved);\n            const result = this.hass.callService(domain, service, data);\n            if (result && typeof result.catch === 'function') {\n                result.catch(er => console.warn(`WebRTC PTZ ${path} service call failed`, er, data));\n            }\n        };\n'''
assert old in s
s = s.replace(old, new, 1)
old = '''            let lastSend = 0;\n            let lastPan = 0;\n            let lastTilt = 0;\n\n            const resetStick = () => {\n'''
new = '''            let lastSend = 0;\n            let lastPan = 0;\n            let lastTilt = 0;\n            let lastSpeed = 0;\n            let heartbeatTID = 0;\n\n            const resetStick = () => {\n'''
assert old in s
s = s.replace(old, new, 1)
old = '''            const stopMove = () => {\n                if (moving) handle('joystick_stop');\n                moving = false;\n                lastPan = 0;\n                lastTilt = 0;\n                resetStick();\n            };\n'''
new = '''            const stopHeartbeat = () => {\n                if (heartbeatTID) {\n                    clearInterval(heartbeatTID);\n                    heartbeatTID = 0;\n                }\n            };\n            const startHeartbeat = () => {\n                stopHeartbeat();\n                heartbeatTID = setInterval(() => {\n                    if (moving && activePointer !== null) {\n                        handle('joystick', {pan: lastPan, tilt: lastTilt, zoom: 0, speed: lastSpeed});\n                        lastSend = performance.now();\n                    }\n                }, updateMs);\n            };\n            const stopMove = () => {\n                stopHeartbeat();\n                if (moving) handle('joystick_stop');\n                moving = false;\n                lastPan = 0;\n                lastTilt = 0;\n                lastSpeed = 0;\n                resetStick();\n            };\n'''
assert old in s
s = s.replace(old, new, 1)
old = '''                    if (moving) {\n                        handle('joystick_stop');\n                        moving = false;\n                        lastPan = 0;\n                        lastTilt = 0;\n                    }\n                    return;\n'''
new = '''                    if (moving) {\n                        handle('joystick_stop');\n                        moving = false;\n                        lastPan = 0;\n                        lastTilt = 0;\n                        lastSpeed = 0;\n                    }\n                    return;\n'''
assert old in s
s = s.replace(old, new, 1)
old = '''                    lastPan = pan;\n                    lastTilt = tilt;\n                    moving = true;\n                }\n'''
new = '''                    lastPan = pan;\n                    lastTilt = tilt;\n                    lastSpeed = magnitude;\n                    moving = true;\n                } else {\n                    lastPan = pan;\n                    lastTilt = tilt;\n                    lastSpeed = magnitude;\n                }\n'''
assert old in s
s = s.replace(old, new, 1)
old = '''                move.setPointerCapture(ev.pointerId);\n                updateJoystick(ev, true);\n            });\n'''
new = '''                move.setPointerCapture(ev.pointerId);\n                updateJoystick(ev, true);\n                startHeartbeat();\n            });\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s)

manifest = Path('custom_components/webrtc/manifest.json')
m = manifest.read_text().replace('"version": "v3.6.2-nav.7"', '"version": "v3.6.2-nav.8"', 1)
manifest.write_text(m)
