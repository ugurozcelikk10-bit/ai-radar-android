[app]
title = AI Radar
package.name = airadar
package.domain = com.ugur
version = 0.1

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json,csv
source.exclude_exts = spec
entrypoint = main.py

requirements = python3,kivy

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WAKE_LOCK
android.api = 33
android.minapi = 21
android.archs = arm64-v8a

# Build-tools ve lisans KİLİTLE (RC 37-rc1'e saplamasın)
android.sdk_build_tools = 34.0.0
android.accept_sdk_license = True

# log
log_level = 2
warn_on_root = 0
