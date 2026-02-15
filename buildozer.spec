[app]
title = AI Radar
package.name = airadar
package.domain = com.ugur
version = 0.1

source.dir = .
entrypoint = main.py

source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json,csv
source.exclude_exts = spec

# Python + Kivy + Network + SSL (Binance için zorunlu)
requirements = python3,kivy,requests,openssl,certifi,urllib3,idna,charset-normalizer

orientation = portrait
fullscreen = 0

# Android izinleri
android.permissions = INTERNET,WAKE_LOCK

# SDK / API ayarları
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a

# Stabil build-tools
android.sdk_build_tools = 33.0.2
android.accept_sdk_license = True

# APK üret (AAB kapalı)
android.release_artifact = apk
android.package_format = apk

# AAB / toolchain hatasını keser
p4a.branch = develop

# Stabilite
log_level = 2
warn_on_root = 0
