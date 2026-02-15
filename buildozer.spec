[app]
title = AI Radar
package.name = airadar
package.domain = com.ugur
version = 0.1

# main.py proje kökünde
source.dir = .
entrypoint = main.py

# Dahil edilecek dosya tipleri
source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json,csv
source.exclude_exts = spec

# Gerekli paketler (tek dosya main için minimal)
requirements = python3,kivy

# Ekran
orientation = portrait
fullscreen = 0

# İzinler
android.permissions = INTERNET,WAKE_LOCK

# Android hedefleri (stabil kilit)
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.sdk_build_tools = 33.0.2
android.accept_sdk_license = True

# Log
log_level = 2
warn_on_root = 0
