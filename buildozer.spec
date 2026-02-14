[app]
title = AI Radar
package.name = airadar
package.domain = org.ugur
source.dir = .
source.include_exts = py,kv,png,jpg,ttf
version = 0.1.0

requirements = python3,kivy,requests,numpy,pandas,scikit-learn,ta

orientation = portrait
fullscreen = 0

# Permissions
android.permissions = INTERNET,WAKE_LOCK

# Keep screen optional; Termux-like behavior
android.wakelock = True

# (Optional) enable logs
log_level = 2

[buildozer]
warn_on_root = 1
