[app]
title = AI Radar
package.name = airadar
package.domain = com.ugur

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json,csv
source.exclude_exts = spec

# Giriş dosyan
entrypoint = main.py

# Kivy
requirements = python3,kivy

# Ekran
orientation = portrait
fullscreen = 0

# İnternet + uyanık kalsın
android.permissions = INTERNET,WAKE_LOCK


[buildozer]
log_level = 2
warn_on_root = 0


[android]
# Stabil çalışan set
android.api = 33
android.minapi = 21
android.sdk = 33
android.build_tools_version = 33.0.2

# Telefonlar için
android.archs = arm64-v8a

# Gradle ayarı
android.gradle_dependencies =

# İmzalama yok (debug)
android.debug_keystore =
