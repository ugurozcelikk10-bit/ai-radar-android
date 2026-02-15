[app]
title = Ugur Coins v3
package.name = ugurcoinsv3
package.domain = com.ugur
version = 0.3

source.dir = .
entrypoint = main.py
source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json,csv
source.exclude_exts = spec

# Network + SSL (Binance/OKX + Telegram için)
requirements = python3,kivy,requests,openssl,certifi,urllib3,idna,charset-normalizer

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WAKE_LOCK

android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a

# Stabil build-tools (RC'ye kaçmayı keser)
android.sdk_build_tools = 33.0.2
android.accept_sdk_license = True

# Sadece APK üret
android.release_artifact = apk
android.package_format = apk

# python-for-android stabil
p4a.branch = stable

log_level = 2
warn_on_root = 0
