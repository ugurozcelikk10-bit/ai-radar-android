[app]

title = UGUR COINS v3 PRO
package.name = ugurcoinsv3
package.domain = com.ugur

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json

version = 3.0

orientation = portrait
fullscreen = 0

requirements = python3,kivy,requests,certifi,urllib3,idna,charset-normalizer,openssl

android.permissions = INTERNET,WAKE_LOCK

android.api = 33
android.minapi = 21

android.ndk = 25b
android.accept_sdk_license = True

android.archs = arm64-v8a

# SADECE APK üret (AAB yok)
android.release_artifact = apk
android.package_format = apk

p4a.branch = master

log_level = 2
warn_on_root = 0


[buildozer]
log_level = 2
