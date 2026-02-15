# ==========================================
# UGUR COINS (V2) - CLEAN FAST
# Binance USDT-M Futures tarar (PUBLIC)
# Sadece OKX SWAP'ta listeli coinleri yazar
# ATR girişi TAM SAYI: 65 => %0.65
# SL: ATR tabanlı, TP: 3 kademe
# Telegram opsiyonel
# ==========================================

import os
import time
import threading
from datetime import datetime

import requests
import certifi

# Android SSL fix
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout

# -------------------------
# Binance Futures endpoints
# -------------------------
BINANCE_BASE = "https://fapi.binance.com"

def fetch_24h_tickers():
    r = requests.get(f"{BINANCE_BASE}/fapi/v1/ticker/24hr", timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_klines(symbol: str, interval: str, limit: int = 200):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(f"{BINANCE_BASE}/fapi/v1/klines", params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    h = [float(x[2]) for x in data]
    l = [float(x[3]) for x in data]
    c = [float(x[4]) for x in data]
    return h, l, c

# -------------------------
# OKX SWAP instruments (Public)
# -------------------------
OKX_BASE = "https://www.okx.com"

def binance_to_okx_swap(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if not s.endswith("USDT"):
        return ""
    base = s[:-4]
    return f"{base}-USDT-SWAP"

def okx_fetch_swap_instruments_set():
    r = requests.get(
        f"{OKX_BASE}/api/v5/public/instruments",
        params={"instType": "SWAP"},
        timeout=20,
    )
    r.raise_for_status()
    j = r.json()
    data = j.get("data", [])
    return set(x.get("instId", "") for x in data if x.get("instId"))

# -------------------------
# Indicators (pure python)
# -------------------------
def ema(series, length):
    if len(series) < length:
        return None
    k = 2.0 / (length + 1.0)
    v = sum(series[:length]) / length
    for x in series[length:]:
        v = (x * k) + (v * (1 - k))
    return v

def atr(high, low, close, length=14):
    if len(close) < length + 1:
        return None
    trs = []
    for i in range(1, len(close)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
        trs.append(tr)
    if len(trs) < length:
        return None
    return sum(trs[-length:]) / length

# -------------------------
# Telegram (optional)
# -------------------------
def tg_send(token, chat_id, msg):
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": msg}, timeout=12)
    except:
        pass

# -------------------------
# Pattern + Risk (clean/fast)
# -------------------------
def detect_regime(price, ema45, ema90):
    if ema45 is None or ema90 is None:
        return "UNKNOWN"
    if ema45 > ema90 and price >= ema90:
        return "UP"
    if ema45 < ema90 and price <= ema90:
        return "DOWN"
    return "CHOP"

def detect_pattern(ema7, ema25, ema45, ema90, atrv):
    if None in (ema7, ema25, ema45, ema90) or atrv is None:
        return "UNKNOWN"
    spread = max(ema7, ema25, ema45, ema90) - min(ema7, ema25, ema45, ema90)
    if spread <= 0.25 * atrv:
        return "SQUEEZE"
    if spread <= 0.35 * atrv:
        return "EXPLOSION"
    return "TREND"

def build_levels(entry, atrv, direction):
    risk = 1.2 * atrv
    if direction == "LONG":
        sl = entry - risk
        tp1 = entry + risk * 1.0
        tp2 = entry + risk * 1.6
        tp3 = entry + risk * 2.3
    else:
        sl = entry + risk
        tp1 = entry - risk * 1.0
        tp2 = entry - risk * 1.6
        tp3 = entry - risk * 2.3
    return sl, tp1, tp2, tp3

def base_probability(pattern, regime, direction, atrp):
    p = 0.50
    if pattern == "SQUEEZE":   p += 0.06
    if pattern == "EXPLOSION": p += 0.08
    if pattern == "TREND":     p += 0.04

    if regime == "UP" and direction == "LONG":     p += 0.08
    if regime == "DOWN" and direction == "SHORT":  p += 0.08
    if regime == "CHOP":                            p -= 0.06

    if atrp < 0.0065: p -= 0.05
    elif atrp > 0.012: p += 0.03

    if p < 0.05: p = 0.05
    if p > 0.95: p = 0.95
    return p

# -------------------------
# Kivy UI
# -------------------------
KV = r"""
<RootUI>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(10)

    Label:
        text: "Ugur Coins (V2) • Binance tarar • OKX SWAP yazar"
        bold: True
        size_hint_y: None
        height: dp(36)

    GridLayout:
        cols: 2
        size_hint_y: None
        height: self.minimum_height
        row_default_height: dp(44)
        row_force_default: True
        spacing: dp(8)

        Label:
            text: "TF (5m/15m/1h)"
        TextInput:
            id: tf
            text: root.tf
            multiline: False

        Label:
            text: "Min ATR (tam sayı) 65=%0.65"
        TextInput:
            id: atrint
            text: root.min_atr_int
            multiline: False

        Label:
            text: "Min AI % (65= %65)"
        TextInput:
            id: minaiint
            text: root.min_ai_int
            multiline: False

        Label:
            text: "Scan Interval (sn)"
        TextInput:
            id: scanint
            text: root.scan_sec
            multiline: False

        Label:
            text: "Telegram Token (opsiyonel)"
        TextInput:
            id: tkn
            text: root.tg_token
            multiline: False
            password: True

        Label:
            text: "Telegram Chat ID (opsiyonel)"
        TextInput:
            id: cid
            text: root.tg_chat
            multiline: False

        Label:
            text: "Telegram Gönder"
        CheckBox:
            id: tgen
            active: root.tg_enabled

    BoxLayout:
        size_hint_y: None
        height: dp(52)
        spacing: dp(10)
        Button:
            text: "Başlat"
            disabled: root.running
            on_release: root.start()
        Button:
            text: "Durdur"
            disabled: not root.running
            on_release: root.stop()

    Label:
        text: root.status
        size_hint_y: None
        height: dp(30)

    ScrollView:
        Label:
            text: root.log_text
            halign: "left"
            valign: "top"
            text_size: self.width, None
            size_hint_y: None
            height: max(self.texture_size[1], dp(420))
"""

class RootUI(BoxLayout):
    tf = StringProperty("15m")
    min_atr_int = StringProperty("65")   # 65 => 0.0065
    min_ai_int = StringProperty("65")    # 65 => 0.65
    scan_sec = StringProperty("60")

    tg_token = StringProperty("")
    tg_chat = StringProperty("")
    tg_enabled = BooleanProperty(False)

    running = BooleanProperty(False)
    status = StringProperty("Hazır.")
    log_text = StringProperty("")

    _t = None
    _stop = None
    _last_alert = {}

    _okx_swap_set = None
    _okx_swap_ts = 0

    def _log_ui(self, s: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text = f"[{ts}] {s}\n" + self.log_text[:16000]

    def _log(self, s: str):
        Clock.schedule_once(lambda *_: self._log_ui(s), 0)

    def _okx_refresh_if_needed(self):
        now = time.time()
        if (self._okx_swap_set is None) or (now - self._okx_swap_ts > 3600):
            self._log("🧾 OKX SWAP listesi çekiliyor...")
            try:
                s = okx_fetch_swap_instruments_set()
                self._okx_swap_set = s if s else set()
            except:
                self._okx_swap_set = set()
            self._okx_swap_ts = now
            self._log(f"✅ OKX SWAP sayısı: {len(self._okx_swap_set)}")

    def _can_alert(self, symbol, direction, cooldown_min=5):
        key = (symbol, direction)
        now = time.time()
        last = self._last_alert.get(key, 0)
        if (now - last) >= cooldown_min * 60:
            self._last_alert[key] = now
            return True
        return False

    def start(self):
        if self.running:
            return

        self.tf = self.ids.tf.text.strip() or "15m"
        self.min_atr_int = (self.ids.atrint.text.strip() or "65")
        self.min_ai_int = (self.ids.minaiint.text.strip() or "65")
        self.scan_sec = (self.ids.scanint.text.strip() or "60")

        self.tg_token = self.ids.tkn.text.strip()
        self.tg_chat = self.ids.cid.text.strip()
        self.tg_enabled = bool(self.ids.tgen.active)

        self.running = True
        self.status = "Çalışıyor..."
        self._stop = threading.Event()

        self._t = threading.Thread(target=self._run_loop, daemon=True)
        self._t.start()

        self._log("SSL certifi aktif ✅")
        self._log("Bot başlatıldı ✅")

    def stop(self):
        try:
            if self._stop:
                self._stop.set()
        except:
            pass
        self.running = False
        self.status = "Durduruldu."
        self._log("Bot durduruldu.")

    def _run_loop(self):
        try:
            # ATR: integer => percent/10000
            try:
                atr_int = int(float(self.min_atr_int))
            except:
                atr_int = 65
            min_atr = max(1, atr_int) / 10000.0

            # AI: integer => /100
            try:
                ai_int = int(float(self.min_ai_int))
            except:
                ai_int = 65
            min_ai = max(1, ai_int) / 100.0

            try:
                scan_interval = int(float(self.scan_sec))
            except:
                scan_interval = 60

            cooldown_min = 5
            top_volume_count = 40
            top_volatile_count = 20

            while not self._stop.is_set():
                try:
                    self._okx_refresh_if_needed()
                    okx_swap_set = self._okx_swap_set or set()

                    self._log("📡 Binance 24h tickers...")
                    tickers = fetch_24h_tickers()

                    # Top 40 volume
                    fut = []
                    for t in tickers:
                        sym = t.get("symbol", "")
                        if sym.endswith("USDT"):
                            try:
                                qv = float(t.get("quoteVolume", "0"))
                            except:
                                qv = 0.0
                            fut.append((sym, qv))
                    fut.sort(key=lambda x: x[1], reverse=True)
                    top40 = [x[0] for x in fut[:top_volume_count]]

                    # Volatility pick (OKX filtered)
                    vols = []
                    for sym in top40:
                        if self._stop.is_set():
                            break
                        okx_inst = binance_to_okx_swap(sym)
                        if not okx_inst or (okx_inst not in okx_swap_set):
                            continue
                        try:
                            h, l, c = fetch_klines(sym, self.tf, limit=120)
                            a = atr(h, l, c, 14)
                            if a is None:
                                continue
                            atrp = a / c[-1]
                            vols.append((sym, atrp))
                            time.sleep(0.05)
                        except:
                            continue

                    vols.sort(key=lambda x: x[1], reverse=True)
                    symbols = [x[0] for x in vols[:top_volatile_count]]

                    okx_list = [binance_to_okx_swap(s) for s in symbols]
                    self._log("✅ Seçilenler (OKX SWAP): " + ", ".join(okx_list[:10]) + (" ..." if len(okx_list) > 10 else ""))

                    # Scan
                    for sym in symbols:
                        if self._stop.is_set():
                            break

                        okx_inst = binance_to_okx_swap(sym)
                        if not okx_inst:
                            continue

                        try:
                            h, l, c = fetch_klines(sym, self.tf, limit=240)
                            a = atr(h, l, c, 14)
                            if a is None:
                                continue
                            price = c[-1]
                            atrp = a / price
                            if atrp < min_atr:
                                continue

                            e7 = ema(c, 7)
                            e25 = ema(c, 25)
                            e45 = ema(c, 45)
                            e90 = ema(c, 90)
                            if None in (e7, e25, e45, e90):
                                continue

                            regime = detect_regime(price, e45, e90)
                            pattern = detect_pattern(e7, e25, e45, e90, a)

                            # direction
                            if regime == "UP":
                                direction = "LONG"
                            elif regime == "DOWN":
                                direction = "SHORT"
                            else:
                                if pattern in ("SQUEEZE", "EXPLOSION"):
                                    direction = "LONG" if e7 > e25 else "SHORT"
                                else:
                                    continue

                            if not self._can_alert(sym, direction, cooldown_min=cooldown_min):
                                continue

                            # base AI prob (clean/fast)
                            prob = base_probability(pattern, regime, direction, atrp)
                            if prob < min_ai:
                                continue

                            entry = e25
                            sl, tp1, tp2, tp3 = build_levels(entry, a, direction)

                            msg = (
                                f"━━━━━━━━━━\n"
                                f"📡 COIN: {okx_inst}\n"
                                f"🧠 Yön: {direction}\n"
                                f"🎯 Olasılık: %{int(prob*100)}\n"
                                f"🧩 Pattern: {pattern}\n"
                                f"🌊 Rejim: {regime}\n"
                                f"📍 Entry: {entry:.6f}\n"
                                f"🛑 SL: {sl:.6f}\n"
                                f"🎯 TP1: {tp1:.6f}\n"
                                f"🎯 TP2: {tp2:.6f}\n"
                                f"🎯 TP3: {tp3:.6f}\n"
                                f"⚡ ATR%: {atrp*100:.2f}\n"
                                f"━━━━━━━━━━"
                            )

                            self._log(msg)
                            if self.tg_enabled:
                                tg_send(self.tg_token, self.tg_chat, msg)

                            time.sleep(0.15)

                        except:
                            continue

                    self._log(f"✅ Tarama bitti: {datetime.now().strftime('%H:%M')}")
                    for _ in range(max(1, scan_interval)):
                        if self._stop.is_set():
                            break
                        time.sleep(1)

                except Exception as e:
                    self._log(f"Ana döngü hatası: {e}")
                    time.sleep(5)

        except Exception as e:
            self._log(f"THREAD FATAL: {e}")
            self.running = False
            self.status = "Hata!"

class UgurCoinsApp(App):
    def build(self):
        Builder.load_string(KV)
        return RootUI()

if __name__ == "__main__":
    UgurCoinsApp().run()
