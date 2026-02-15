# ==========================================
# UGUR COINS v2+v3 FINAL (PURE EMA/ATR + AI MEMORY)
# Binance Futures tarar -> OKX USDT-SWAP listesinde olanları raporlar
# v2 setup etiketleri + detaylı rapor + AI öğrenme (decay memory)
# RSI YOK
# Android SSL fix + verify=certifi.where()
# ==========================================

import os, time, threading, json
from datetime import datetime

import requests, certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout

# --- AYARLAR ---
BINANCE_FAPI = "https://fapi.binance.com"
OKX_PUBLIC = "https://www.okx.com"

TOP_N = 45
EDGE_HORIZON = 10
EDGE_DECAY = 0.95
MEM_FILE = "ugur_v2v3_edge.json"

def _get_save_path():
    try:
        d = App.get_running_app().user_data_dir
        if d:
            return os.path.join(d, MEM_FILE)
    except:
        pass
    try:
        from android.storage import app_storage_path
        d = app_storage_path()
        return os.path.join(d, MEM_FILE)
    except:
        return MEM_FILE

def get_lookback_limit(tf):
    if tf == "15m": return 672
    if tf == "1h":  return 168
    return 500

# --- TEKNİK HESAPLAR (EMA + ATR) ---
def ema(series, length):
    if len(series) < length:
        return None
    k = 2.0 / (length + 1.0)
    v = sum(series[:length]) / length
    for x in series[length:]:
        v = (x * k) + (v * (1 - k))
    return v

def ema_list(series, length):
    if len(series) < length:
        return [0.0] * len(series)
    k = 2.0 / (length + 1.0)
    v = sum(series[:length]) / length
    res = [0.0] * (length - 1) + [v]
    for x in series[length:]:
        v = (x * k) + (v * (1 - k))
        res.append(v)
    return res

def atr_list(high, low, close, length=14):
    n = len(close)
    if n < length + 2:
        return [0.0] * n
    trs = [
        max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        for i in range(1, n)
    ]
    res = [0.0] * length
    for i in range(len(trs) - length + 1):
        res.append(sum(trs[i:i + length]) / length)
    if len(res) < n:
        res += [res[-1]] * (n - len(res))
    return res[:n]

# --- v2 SETUP ETİKETLERİ ---
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
    return ""

# --- OKX FİLTRESİ ---
def okx_usdt_swap_bases():
    try:
        r = requests.get(
            f"{OKX_PUBLIC}/api/v5/public/instruments",
            params={"instType": "SWAP"},
            timeout=15,
            verify=certifi.where()
        ).json()
        return {
            it["instId"].split("-")[0]
            for it in r.get("data", [])
            if it.get("instId", "").endswith("-USDT-SWAP")
        }
    except:
        return set()

# --- UI ---
KV = r"""
<RootUI>:
    orientation: "vertical"
    padding: dp(10)
    canvas.before:
        Color:
            rgba: 0.02, 0.02, 0.04, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: "UGUR COINS v2+v3 FINAL"
        bold: True
        color: (0, 1, 0.8, 1)
        size_hint_y: None
        height: dp(50)

    GridLayout:
        cols: 2
        size_hint_y: None
        height: dp(90)
        spacing: dp(10)

        Label:
            text: "Zaman Dilimi (15m/1h):"
        TextInput:
            id: tf
            text: "15m"
            halign: "center"
            multiline: False

        Label:
            text: "Min ATR% (65=0.65):"
        TextInput:
            id: atr_int
            text: "65"
            halign: "center"
            multiline: False
            input_filter: "int"

    BoxLayout:
        size_hint_y: None
        height: dp(60)
        padding: [0, dp(10)]
        spacing: dp(15)

        Button:
            text: "BAŞLAT"
            background_color: (0, 0.8, 0.4, 1)
            on_release: root.start()

        Button:
            text: "DURDUR"
            background_color: (0.8, 0.2, 0.2, 1)
            on_release: root.stop()

    Label:
        text: root.status
        size_hint_y: None
        height: dp(30)
        font_size: dp(12)
        color: (0.6, 0.6, 0.6, 1)

    ScrollView:
        Label:
            text: root.log_text
            halign: "left"
            valign: "top"
            text_size: self.width, None
            size_hint_y: None
            height: max(self.texture_size[1], dp(500))
            font_size: dp(13)
            color: (0.9, 0.9, 0.9, 1)
"""

class RootUI(BoxLayout):
    status = StringProperty("Sistem Hazır.")
    log_text = StringProperty("")
    running = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._edge_mem = {}
        self._stop = None
        self._load_mem()

    def _log(self, s):
        ts = datetime.now().strftime("%H:%M:%S")
        Clock.schedule_once(
            lambda *_: setattr(self, "log_text", f"[{ts}] {s}\n\n" + self.log_text[:22000]),
            0
        )

    def _safe_min_atr(self):
        try:
            raw = (self.ids.atr_int.text or "").strip()
            if not raw:
                return 0.0065
            return int(raw) / 10000.0
        except:
            return 0.0065

    def _load_mem(self):
        try:
            p = _get_save_path()
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    self._edge_mem = json.load(f)
        except:
            self._edge_mem = {}

    def _save_mem(self):
        try:
            p = _get_save_path()
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self._edge_mem, f)
        except:
            pass

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop = threading.Event()
        threading.Thread(target=self._run_loop, daemon=True).start()
        self.status = "Çalışıyor..."

    def stop(self):
        if self._stop:
            self._stop.set()
        self.running = False
        self._save_mem()
        self.status = "Durduruldu."

    def _run_loop(self):
        while not self._stop.is_set():
            try:
                tf = (self.ids.tf.text or "15m").strip()
                min_atr = self._safe_min_atr()
                lookback = get_lookback_limit(tf)

                okx_list = okx_usdt_swap_bases()
                if okx_list:
                    self._log(f"OKX filtresi aktif ✅ ({len(okx_list)} coin)")
                else:
                    self._log("⚠️ OKX listesi alınamadı (filtre kapalı).")

                tickers = requests.get(
                    f"{BINANCE_FAPI}/fapi/v1/ticker/24hr",
                    timeout=15,
                    verify=certifi.where()
                ).json()

                pairs = sorted(
                    [(t.get("symbol", ""), float(t.get("quoteVolume", 0) or 0)) for t in tickers if t.get("symbol", "").endswith("USDT")],
                    key=lambda x: x[1],
                    reverse=True
                )[:TOP_N]

                for sym, _ in pairs:
                    if self._stop.is_set():
                        break

                    if okx_list:
                        if sym[:-4] not in okx_list:
                            continue

                    try:
                        rk = requests.get(
                            f"{BINANCE_FAPI}/fapi/v1/klines",
                            params={"symbol": sym, "interval": tf, "limit": lookback + 120},
                            timeout=15,
                            verify=certifi.where()
                        ).json()

                        h = [float(x[2]) for x in rk]
                        l = [float(x[3]) for x in rk]
                        c = [float(x[4]) for x in rk]

                        self._backtest_update_memory(sym, tf, h, l, c, min_atr, lookback)
                        self._report_now(sym, tf, h, l, c, min_atr)

                    except:
                        continue

                    time.sleep(0.1)

                self._save_mem()
                self._log("✅ Tarama bitti. 5 dk mola...")
                for _ in range(300):
                    if self._stop.is_set():
                        break
                    time.sleep(1)

            except Exception as e:
                self._log(f"🔴 Ana Döngü Hatası: {str(e)[:80]}")
                time.sleep(10)

    def _backtest_update_memory(self, sym, tf, h, l, c, min_atr, lookback):
        e25 = ema_list(c, 25)
        e45 = ema_list(c, 45)
        e90 = ema_list(c, 90)
        atrs = atr_list(h, l, c, 14)

        res = {"L": {"w": 0, "t": 0}, "S": {"w": 0, "t": 0}}

        start = max(90, len(c) - lookback)
        end = len(c) - EDGE_HORIZON
        if end <= start:
            self._log(f"⚠️ {sym} veri yetersiz (len={len(c)})")
            return

        for i in range(start, end):
            if c[i] <= 0:
                continue
            if (atrs[i] / c[i]) < min_atr:
                continue

            # PURE TREND ADAYLARI
            if (e45[i] > e90[i]) and (c[i] >= e25[i]):  # LONG
                res["L"]["t"] += 1
                if c[i + EDGE_HORIZON] > c[i]:
                    res["L"]["w"] += 1
            elif (e45[i] < e90[i]) and (c[i] <= e25[i]):  # SHORT
                res["S"]["t"] += 1
                if c[i + EDGE_HORIZON] < c[i]:
                    res["S"]["w"] += 1

        # decay memory update
        for d in ("L", "S"):
            k = f"{sym}|{tf}|{d}"
            cur = self._edge_mem.get(k, {"wins": 0.0, "total": 0.0})
            cur["wins"] = cur["wins"] * EDGE_DECAY + float(res[d]["w"])
            cur["total"] = cur["total"] * EDGE_DECAY + float(res[d]["t"])
            self._edge_mem[k] = cur

    def _report_now(self, sym, tf, h, l, c, min_atr):
        price = c[-1]
        if price <= 0:
            return

        e7_now = ema(c, 7) or 0.0
        e25_now = ema(c, 25) or 0.0
        e45_now = ema(c, 45) or 0.0
        e90_now = ema(c, 90) or 0.0

        atrv = atr_list(h, l, c, 14)[-1]
        atrp = (atrv / price) if price else 0.0
        if atrp < min_atr:
            return

        # slope (son 1 mum kırpıp tekrar EMA)
        e7_prev  = ema(c[:-1], 7)  or e7_now
        e45_prev = ema(c[:-1], 45) or e45_now
        e90_prev = ema(c[:-1], 90) or e90_now

        e7_slope  = e7_now  - e7_prev
        e45_slope = e45_now - e45_prev
        e90_slope = e90_now - e90_prev

        setup = classify_setup(price, e7_now, e25_now, e45_now, e90_now, e7_slope, e45_slope, e90_slope, atrv) or "—"

        direction = ""
        dkey = ""
        if (e45_now > e90_now) and (price >= e25_now):
            direction, dkey = "LONG", "L"
        elif (e45_now < e90_now) and (price <= e25_now):
            direction, dkey = "SHORT", "S"
        else:
            return

        mem = self._edge_mem.get(f"{sym}|{tf}|{dkey}", {"wins": 0.0, "total": 0.0})
        prob = (mem["wins"] / mem["total"] * 100.0) if mem["total"] > 0 else 0.0

        stop = price - (atrv * 1.5) if direction == "LONG" else price + (atrv * 1.5)

        msg = (
            f"⭐ #{sym} {direction}!\n"
            f"Setup: {setup}\n"
            f"TF: {tf} | ATR%: {(atrp*100):.2f}\n"
            f"Entry: {price:.6f} | Stop: {stop:.6f}\n"
            f"EMA7 : {e7_now:.6f}\n"
            f"EMA25: {e25_now:.6f}\n"
            f"EMA45: {e45_now:.6f}\n"
            f"EMA90: {e90_now:.6f}\n"
            f"----------------------------------\n"
            f"🧠 AI ONAYI: %{prob:.0f} ({int(mem['total'])} tecrübe)"
        )
        self._log(msg)

class UgurCoinsApp(App):
    def build(self):
        Builder.load_string(KV)
        return RootUI()

if __name__ == "__main__":
    UgurCoinsApp().run()
