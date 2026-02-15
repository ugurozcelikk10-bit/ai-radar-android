# ==========================================
# AI RADAR ANDROID (TEK DOSYA) - FINAL
# Binance Futures PUBLIC (API key yok)
# Saf Python: EMA + ATR (pandas yok)
# Telegram opsiyonel
# Android crash-proof: SSL fix + thread safe UI log
# ==========================================

import os
import time
import threading
from datetime import datetime

import requests

# SSL / CA Fix (Android'de en çok çökerten yer burası)
import certifi
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
BASE = "https://fapi.binance.com"

def fetch_24h_tickers():
    r = requests.get(f"{BASE}/fapi/v1/ticker/24hr", timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_klines(symbol: str, interval: str, limit: int = 200):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(f"{BASE}/fapi/v1/klines", params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    # kline format: [openTime, open, high, low, close, volume, ...]
    h = [float(x[2]) for x in data]
    l = [float(x[3]) for x in data]
    c = [float(x[4]) for x in data]
    return h, l, c

# -------------------------
# Indicators (saf python)
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
# Telegram (opsiyonel)
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
# Strategy
# -------------------------
def classify_setup(price, ema7, ema25, ema45, ema90, ema7_slope, ema45_slope, ema90_slope, atrv):
    try:
        spread = max(ema7, ema25, ema45, ema90) - min(ema7, ema25, ema45, ema90)
        if spread <= (0.35 * atrv):
            return "🧨 EXPLOSION SETUP"

        if (ema45 > ema90) and (price >= ema25):
            if (ema7 > ema25) and (ema7_slope > 0) and (ema45_slope > 0) and (ema90_slope > 0):
                return "🔥 HIGH PROB LONG"
            if (ema7 > ema25) and (ema7_slope <= 0):
                return "⚠️ WEAK LONG"

        if (ema45 < ema90) and (price <= ema25):
            if (ema7 < ema25) and (ema7_slope < 0) and (ema45_slope < 0) and (ema90_slope < 0):
                return "🔥 HIGH PROB SHORT"
            if (ema7 < ema25) and (ema7_slope >= 0):
                return "⚠️ WEAK SHORT"

        if (abs(ema7 - ema25) <= (0.25 * atrv)) and (
            (ema7_slope < 0 and ema7 > ema25) or (ema7_slope > 0 and ema7 < ema25)
        ):
            return "🧊 TREND COOLING"

        if (ema7 > ema25) and (ema45 < ema90):
            return "❌ FAKE BREAK (LONG tuzağı)"
        if (ema7 < ema25) and (ema45 > ema90):
            return "❌ FAKE BREAK (SHORT tuzağı)"
    except:
        pass
    return None

def build_trade_plan(direction, entry_hint, last_low, prev_low, last_high, prev_high, atrv, rr=2.0):
    if direction == "LONG":
        stop = min(last_low, prev_low) - (0.20 * atrv)
        entry = entry_hint
        risk = entry - stop
        if risk <= 0:
            return None
        tp = entry + (risk * rr)
        return {"direction": "LONG", "entry": entry, "stop": stop, "tp": tp}

    if direction == "SHORT":
        stop = max(last_high, prev_high) + (0.20 * atrv)
        entry = entry_hint
        risk = stop - entry
        if risk <= 0:
            return None
        tp = entry - (risk * rr)
        return {"direction": "SHORT", "entry": entry, "stop": stop, "tp": tp}

    return None

def generate_signal(high, low, close, min_atr_percent=0.0065, rr=2.0, min_risk_percent=0.0015, prox_atr_mult=0.30):
    ema7_now  = ema(close, 7)
    ema25_now = ema(close, 25)
    ema45_now = ema(close, 45)
    ema90_now = ema(close, 90)
    if None in (ema7_now, ema25_now, ema45_now, ema90_now):
        return None

    atr_now = atr(high, low, close, 14)
    if atr_now is None:
        return None

    price = close[-1]
    atr_percent = atr_now / price
    if atr_percent < min_atr_percent:
        return None

    ema7_prev  = ema(close[:-1], 7)  or ema7_now
    ema25_prev = ema(close[:-1], 25) or ema25_now
    ema45_prev = ema(close[:-1], 45) or ema45_now
    ema90_prev = ema(close[:-1], 90) or ema90_now

    ema7_slope  = ema7_now  - ema7_prev
    ema45_slope = ema45_now - ema45_prev
    ema90_slope = ema90_now - ema90_prev

    setup = classify_setup(price, ema7_now, ema25_now, ema45_now, ema90_now, ema7_slope, ema45_slope, ema90_slope, atr_now)

    near_7_25  = abs(ema7_now - ema25_now) <= (prox_atr_mult * atr_now)
    near_7_45  = abs(ema7_now - ema45_now) <= (prox_atr_mult * atr_now)
    near_25_45 = abs(ema25_now - ema45_now) <= (prox_atr_mult * atr_now)
    near_45_90 = abs(ema45_now - ema90_now) <= (prox_atr_mult * atr_now)

    bend_down_to_25 = (ema7_now > ema25_now) and (ema7_slope < 0) and near_7_25
    bend_up_to_25   = (ema7_now < ema25_now) and (ema7_slope > 0) and near_7_25
    squeeze_to_45   = near_7_45 and near_25_45

    prev_gap_45_90 = abs(ema45_prev - ema90_prev)
    gap_45_90 = abs(ema45_now - ema90_now)
    closing_45_90 = gap_45_90 < prev_gap_45_90
    approaching_45_90 = near_45_90 and closing_45_90

    long_early = (
        ema90_slope > 0 and ema45_slope > 0 and
        (bend_down_to_25 or (near_7_25 and ema7_slope >= 0)) and
        (squeeze_to_45 or approaching_45_90)
    )
    short_early = (
        ema90_slope < 0 and ema45_slope < 0 and
        (bend_up_to_25 or (near_7_25 and ema7_slope <= 0)) and
        (squeeze_to_45 or approaching_45_90)
    )

    last_low, prev_low = low[-1], low[-2]
    last_high, prev_high = high[-1], high[-2]

    if long_early:
        plan = build_trade_plan("LONG", ema25_now, last_low, prev_low, last_high, prev_high, atr_now, rr)
        if plan:
            plan["type"] = "EARLY"
            plan["note"] = "EMA'lar sıkışıyor / kesişime yaklaşıyor (LONG adayı)."
            plan["setup"] = setup
            plan["levels"] = {"price": price, "EMA7": ema7_now, "EMA25": ema25_now, "EMA45": ema45_now, "EMA90": ema90_now}
            return plan

    if short_early:
        plan = build_trade_plan("SHORT", ema25_now, last_low, prev_low, last_high, prev_high, atr_now, rr)
        if plan:
            plan["type"] = "EARLY"
            plan["note"] = "EMA'lar sıkışıyor / kesişime yaklaşıyor (SHORT adayı)."
            plan["setup"] = setup
            plan["levels"] = {"price": price, "EMA7": ema7_now, "EMA25": ema25_now, "EMA45": ema45_now, "EMA90": ema90_now}
            return plan

    if (price > ema90_now and ema90_slope > 0 and ema45_slope > 0 and ema7_slope > 0 and ema7_now > ema25_now):
        stop = min(last_low, prev_low)
        risk = price - stop
        if risk <= 0 or (risk / price) < min_risk_percent:
            return None
        tp = price + (risk * rr)
        return {"type": "SIGNAL", "direction": "LONG", "entry": price, "stop": stop, "tp": tp, "setup": setup}

    if (price < ema90_now and ema90_slope < 0 and ema45_slope < 0 and ema7_slope < 0 and ema7_now < ema25_now):
        stop = max(last_high, prev_high)
        risk = stop - price
        if risk <= 0 or (risk / price) < min_risk_percent:
            return None
        tp = price - (risk * rr)
        return {"type": "SIGNAL", "direction": "SHORT", "entry": price, "stop": stop, "tp": tp, "setup": setup}

    return None

# -------------------------
# Kivy UI
# -------------------------
KV = r"""
<RootUI>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(10)

    Label:
        text: "AI RADAR (Futures Public • EMA/ATR • High Prob)"
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
            text: "Timeframe"
        TextInput:
            id: tf
            text: root.tf
            multiline: False

        Label:
            text: "Min ATR % (0.0065=0.65%)"
        TextInput:
            id: atrp
            text: root.min_atr
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
            height: max(self.texture_size[1], dp(400))
"""

class RootUI(BoxLayout):
    tf = StringProperty("15m")
    min_atr = StringProperty("0.0065")
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

    def _log_ui(self, s: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text = f"[{ts}] {s}\n" + self.log_text[:14000]

    def _log(self, s: str):
        Clock.schedule_once(lambda *_: self._log_ui(s), 0)

    def start(self):
        if self.running:
            return
        self.running = True
        self.status = "Çalışıyor..."
        self._stop = threading.Event()

        self.tf = self.ids.tf.text.strip() or "15m"
        self.min_atr = self.ids.atrp.text.strip() or "0.0065"
        self.scan_sec = self.ids.scanint.text.strip() or "60"
        self.tg_token = self.ids.tkn.text.strip()
        self.tg_chat = self.ids.cid.text.strip()
        self.tg_enabled = bool(self.ids.tgen.active)

        self._t = threading.Thread(target=self._run_loop, daemon=True)
        self._t.start()
        self._log("Bot başlatıldı.")

    def stop(self):
        try:
            if self._stop:
                self._stop.set()
        except:
            pass
        self.running = False
        self.status = "Durduruldu."
        self._log("Bot durduruldu.")

    def _can_alert(self, symbol, alert_type, direction, cooldown_min=5):
        key = (symbol, alert_type, direction)
        now = time.time()
        last = self._last_alert.get(key, 0)
        if (now - last) >= cooldown_min * 60:
            self._last_alert[key] = now
            return True
        return False

    def _run_loop(self):
        # Thread içi: asla crash ettirmeyeceğiz
        try:
            try:
                min_atr = float(self.min_atr)
            except:
                min_atr = 0.0065
            try:
                scan_interval = int(float(self.scan_sec))
            except:
                scan_interval = 60

            cooldown_min = 5
            top_volume_count = 40
            top_volatile_count = 20
            rr = 2.0

            self._log("SSL certifi aktif ✅ (Android güvenli)")

            while not self._stop.is_set():
                try:
                    self._log("📡 24h tickers çekiliyor...")
                    tickers = fetch_24h_tickers()

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

                    self._log("🔎 Volatilite hesaplanıyor...")

                    vols = []
                    for sym in top40:
                        if self._stop.is_set():
                            break
                        try:
                            h, l, c = fetch_klines(sym, self.tf, limit=60)
                            a = atr(h, l, c, 14)
                            if a is None:
                                continue
                            vols.append((sym, a / c[-1]))
                            time.sleep(0.05)
                        except Exception as e:
                            # fazla log şişirmeyelim
                            continue

                    vols.sort(key=lambda x: x[1], reverse=True)
                    symbols = [x[0] for x in vols[:top_volatile_count]]
                    self._log(f"🔥 En volatil {top_volatile_count} seçildi: {', '.join(symbols[:8])} ...")

                    # Scan
                    for sym in symbols:
                        if self._stop.is_set():
                            break
                        try:
                            h, l, c = fetch_klines(sym, self.tf, limit=220)
                            res = generate_signal(h, l, c, min_atr_percent=min_atr, rr=rr)
                            if not res:
                                continue

                            alert_type = res.get("type", "SIGNAL")
                            direction = res.get("direction", "?")

                            if not self._can_alert(sym, alert_type, direction, cooldown_min=cooldown_min):
                                continue

                            setup = (res.get("setup") or "").strip()

                            if alert_type == "EARLY":
                                lv = res.get("levels", {})
                                msg = (
                                    f"{'='*46}\n"
                                    f"⚠️ EARLY WARNING | {direction} | #{sym}\n"
                                    f"{setup}\n"
                                    f"{res.get('note','')}\n"
                                    f"Price : {lv.get('price',0):.6f}\n"
                                    f"EMA7  : {lv.get('EMA7',0):.6f}\n"
                                    f"EMA25 : {lv.get('EMA25',0):.6f}\n"
                                    f"EMA45 : {lv.get('EMA45',0):.6f}\n"
                                    f"EMA90 : {lv.get('EMA90',0):.6f}\n"
                                    f"Entry : {res['entry']:.6f}\n"
                                    f"Stop  : {res['stop']:.6f}\n"
                                    f"TP    : {res['tp']:.6f}\n"
                                    f"{'='*46}"
                                )
                            else:
                                msg = (
                                    f"{'='*46}\n"
                                    f"📊 SIGNAL | {direction} | #{sym}\n"
                                    f"{setup}\n"
                                    f"Entry : {res['entry']:.6f}\n"
                                    f"Stop  : {res['stop']:.6f}\n"
                                    f"TP    : {res['tp']:.6f}\n"
                                    f"{'='*46}"
                                )

                            self._log(msg)

                            if self.tg_enabled:
                                tg_send(self.tg_token, self.tg_chat, msg)

                            time.sleep(0.15)

                        except:
                            continue

                    self._log(f"✅ Tarama bitti: {datetime.now().strftime('%H:%M')}")

                    # scan interval
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

class AIRadarApp(App):
    def build(self):
        Builder.load_string(KV)
        return RootUI()

if __name__ == "__main__":
    AIRadarApp().run()1
