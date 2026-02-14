[app]

title = AI Radar
package.name = airadar
package.domain = org.airadar

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 0.1

requirements = python3,kivy,requests,numpy

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 25b

android.gradle_dependencies =

android.accept_sdk_license = True

android.arch = arm64-v8a

android.permissions = INTERNET,WAKE_LOCK

android.allow_backup = True

[buildozer]

log_level = 2
warn_on_root = 1
