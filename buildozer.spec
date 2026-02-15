# buildozer.spec  (TAM HALİ - v3 PRO)

[app]
title = Ugur Coins v3 PRO
package.name = ugurcoinsv3
package.domain = com.ugur
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json,csv
entrypoint = main.py
version = 0.3
orientation = portrait
fullscreen = 0

requirements = python3,kivy,requests,openssl,certifi,urllib3,idna,charset-normalizer
android.permissions = INTERNET,WAKE_LOCK

android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

# ✅ AAB KAPALI / SADECE APK
android.package_format = apk
android.release_artifact = apk

# ✅ AAB hatasını kökten kesen stabil p4a
p4a.branch = stable

log_level = 2
warn_on_root = 0

[buildozer]
log_level = 2
