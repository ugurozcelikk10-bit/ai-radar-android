# AI Radar APK (Kivy)

Bu klasör, Android için Kivy tabanlı arayüzlü APK projesidir.

## 1) PC / Mac / Linux üzerinde APK build (önerilen: Linux)
Android APK üretmek için Buildozer kullanılır.

### Kurulum (Ubuntu örneği)
```bash
sudo apt update
sudo apt install -y python3 python3-pip git zip unzip openjdk-17-jdk \
  autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
  libtinfo5 cmake libffi-dev libssl-dev

pip install --user buildozer cython
```

### Build
Proje klasörüne gir:
```bash
cd ai_radar_android_kivy
buildozer -v android debug
```

APK şurada oluşur:
`bin/airadar-0.1.0-arm64-v8a-debug.apk` (cihazına atıp kurarsın)

## 2) Uygulama kullanımı
- Telegram Bot Token ve Chat ID gir
- Coin listesini (CSV) istersen değiştir
- Başlat / Durdur

## Notlar
- Uygulama internet izni ister (INTERNET)
- Arkaplanda kapanmasın diye WAKE_LOCK var
- Bu app trade açmaz, sinyal gönderir.
