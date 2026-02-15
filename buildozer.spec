name: Build Android APK (Ugur Coins v3 AI)

on:
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-22.04

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python 3.10
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Set up Java 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"

      - name: Install System Dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y \
            git zip unzip curl autoconf automake libtool pkg-config \
            build-essential cmake zlib1g-dev libffi-dev libssl-dev \
            libncurses5-dev libncursesw5-dev libtinfo6 libatlas-base-dev \
            gfortran libsqlite3-dev

      - name: Install Buildozer and Cython
        run: |
          python -m pip install --upgrade pip setuptools wheel
          python -m pip install "Cython==0.29.36" "buildozer==1.5.0"

      - name: Build APK with Buildozer
        run: |
          yes | buildozer -v android debug 2>&1 | tee build_log.txt

      - name: Collect APK
        if: always()
        run: |
          mkdir -p output
          # Klasördeki her şeyi tara, en güncel APK'yı bul ve adını v3 yap
          find bin/ -name "*.apk" -exec cp {} output/UgurCoins-V3-AI.apk \; || true

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: UgurCoins-V3-AI-Pack
          path: output/*.apk
          if-no-files-found: error

      - name: Upload Build Log
        uses: actions/upload-artifact@v4
        with:
          name: build-log-v3
          path: build_log.txt

