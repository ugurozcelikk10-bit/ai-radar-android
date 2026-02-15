[app]
title = Ugur Coins

package.domain = com.ugur
package.name = ugurcoinsv2
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
android.ndk = 25b
android.archs = arm64-v8a

android.sdk_build_tools = 33.0.2
android.accept_sdk_license = True

android.release_artifact = apk
android.package_format = apk

log_level = 2
warn_on_root = 0
