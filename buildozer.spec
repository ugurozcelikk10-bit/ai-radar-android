[app]

title = AI Radar
package.name = airadar
package.domain = com.ugur

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 0.1

requirements = python3,kivy

orientation = portrait

fullscreen = 0

android.permissions = INTERNET,WAKE_LOCK

android.api = 33
android.minapi = 21

android.arch = arm64-v8a

log_level = 2

[buildozer]
log_level = 2
warn_on_root = 1
