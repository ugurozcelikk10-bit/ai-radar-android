[app]

# (str) Uygulama başlığı
title = Ugur Coins

# (str) Paket adı
package.name = ugurcoinsv2

# (str) Paket domaini
package.domain = com.ugur

# (str) Kaynak kodların olduğu dizin
source.dir = .

# (list) Dahil edilecek dosya uzantıları
source.include_exts = py,kv,png,jpg,jpeg,gif,atlas,txt,json,csv

# (str) Giriş dosyası
entrypoint = main.py

# (list) Uygulamanın çalışması için gereken kütüphaneler
# ÖNEMLİ: requests için openssl, certifi vb. buraya eklenmiştir.
requirements = python3,kivy,requests,openssl,certifi,urllib3,idna,charset-normalizer

# (str) Uygulama versiyonu
version = 0.2

# (int) Ekran yönü (1=Portrait, 2=Landscape)
orientation = portrait

# (bool) Tam ekran modu
fullscreen = 0

# (list) Android izinleri
android.permissions = INTERNET,WAKE_LOCK

# (int) Hedef Android API (Android 13 = 33)
android.api = 33

# (int) Minimum Android API (Lollipop = 21)
android.minapi = 21

# (str) Android NDK sürümü (Boş bırakırsak buildozer en iyisini seçer)
android.ndk = 25b

# (bool) SDK lisanslarını otomatik kabul et
android.accept_sdk_license = True

# (list) Mimari (Modern cihazlar için arm64-v8a yeterlidir)
android.archs = arm64-v8a

# (str) Paket formatı (Google Play için aab, test için apk)
android.package_format = apk

# (str) p4a branşı (master en stabil olanıdır)
p4a.branch = master

# (int) Log seviyesi (2 = Her şeyi göster)
log_level = 2

# (bool) Root uyarısını kapat
warn_on_root = 0

[buildozer]
# (int) Build log seviyesi
log_level = 2
