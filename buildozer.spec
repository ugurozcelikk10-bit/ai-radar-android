[app]
title = AI Radar
package.name = airadar
package.domain = com.ugur
version = 0.1

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json,csv
source.exclude_exts = spec

entrypoint = main.py

# requests + SSL için şart paketler
requirements = python3,kivy,requests,openssl,certifi,urllib3,idna,charset-normalizer

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WAKE_LOCK
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a

# build-tools kilit
android.sdk_build_tools = 33.0.2
android.accept_sdk_license = True

# (opsiyonel ama stabil)
p4a.branch = stable

log_level = 2
warn_on_root = 0
