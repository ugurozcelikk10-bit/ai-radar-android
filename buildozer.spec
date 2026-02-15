[app]
title = Ugur Coins
package.name = ugurcoinsv2
package.domain = com.ugur
version = 0.2

source.dir = .
entrypoint = main.py

source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json,csv
source.exclude_exts = spec

requirements = python3,kivy,requests,openssl,certifi,urllib3,idna,charset-normalizer

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WAKE_LOCK

android.api = 33
android.minapi = 21
android.archs = arm64-v8a

android.release_artifact = apk
android.package_format = apk

p4a.branch = master

log_level = 2
warn_on_root = 0
