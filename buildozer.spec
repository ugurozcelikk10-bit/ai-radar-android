[app]
title = AI Radar
package.name = airadar
package.domain = com.ugur
version = 0.1

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json,csv
entrypoint = main.py

requirements = python3,kivy

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WAKE_LOCK

[buildozer]
log_level = 2
warn_on_root = 0

[android]
android.minapi = 21
android.api = 33
android.ndk = 25b
android.archs = arm64-v8a

# APK’de python 3.11 var → bunu sabitle
p4a.python_version = 3.11
