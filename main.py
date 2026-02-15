# ==========================================
# UGUR COINS v2 (Android Tek Dosya)
# Binance Futures tarar -> OKX Futures'ta listelenenleri yazar
# Min ATR girişi: TAM SAYI (örn 65 => %0.65)
# Crash-proof: boş input, direction fix, OKX symbol normalize
# ==========================================

import os
import re
import time
import threading
from datetime import datetime

import requests
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
# ENDPOINTS
# -------------------------
BINANCE_FAPI = "https://fapi.binance.com"
OKX = "https://www.okx.com"


def b_fetch_24h_tickers():
    r = requests.get(f"{BINANCE_FAPI}/fapi/v1/ticker/24hr", timeout=15)
    r.raise_for_status()
    return r.json()


def b_fetch_klines(symbol: str, interval: str, limit: int = 200):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(f"{BINANCE_FAPI}/fapi/v1/klines", params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    h = [float(x[2]) for x in data]
    l = [float(x[3]) for x in data]
    c = [float(x[4]) for x in data]
    return h, l, c


def normalize_symbol_for_match(sym: str) -> str:
    """
    Binance/OKX sembol eşleme için normalize.
    1000PEPEUSDT gibi coinler borsalar arasında farklı temsil edilebilir.
    Burada hem OKX hem Binance tarafında "temiz eşleme" için
    sayı-prefixlerini kaldırıp temel ismi yakalamayı deneriz.
    """
    s = sym.upper().strip()

    # BTC-USDT-SWAP -> BTCUSDT gibi gelirse zaten dönüştürülmüş olur
    s = s.replace("-", "").replace("SWAP", "")

    # sadece USDT çiftleri
    if not s.endswith("USDT"):
        return s

    base = s[:-4]  # USDT hariç
    # ÖN EK TEMİZLİK: 1000, 10000, 1M, 2M, 10M vb.
    base2 = re.sub(r"^(1000|10000|100000|1M|2M|5M|10M)", "", base)
    return f"{base2}USDT"


def okx_futures_usdt_symbols_normalized():
    """
    OKX SWAP instruments: BTC-USDT-SWAP -> BTCUSDT
    normalize edilerek set döner.
    """
    try:
        r = requests.get(
            f"{OKX}/api/v5/public/instruments",
            params={"instType": "SWAP"},
            timeout=15
        )
        r.raise_for_status()
        js = r.json()
        data = js.get("data", [])
        out = set()
        for it in data:
            inst = (it.get("instId", "") or "").upper()
            # BTC-USDT-SWAP
            if inst.endswith("-USDT-SWAP"):
                base = inst.split("-")[0].strip()
                out.add(normalize_symbol_for_match(f"{base}USDT"))
        return out
    except:
        return set()


# -------------------------
# INDICATORS (pure python)
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
# STRATEGY
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
    return ""


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
    ema45_prev = ema(close[:-1], 45) or ema45_now
    ema90_prev = ema(close[:-1], 90) or ema90_now

    ema7_slope  = ema7_now  - ema7_prev
    ema45_slope = ema45_now - ema45_prev
    ema90_slope = ema90_now - ema90_prev

    setup = classify_setup(price, ema7_now, ema25_now, ema45_now, ema90_now, ema7_slope, ema45_slope, ema90_slope, atr_now)

    # EARLY
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
            plan["setup"] = setup
            return plan

    if short_early:
        plan = build_trade_plan("SHORT", ema25_now, last_low, prev_low, last_high, prev_high, atr_now, rr)
        if plan:
            plan["type"] = "EARLY"
            plan["setup"] = setup
            return plan

    # SIGNAL
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
# KIVY UI
# -------------------------
KV = r"""
<RootUI>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(10)

    Label:
        text: "UGUR COINS v2 (Binance tarar • OKX futures filtreli)"
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
            text: "Min ATR (tam sayı) 65 => %0.65"
        TextInput:
            id: atr_int
            text: root.min_atr_int
            multiline: False
            input_filter: "int"

        Label:
            text: "Scan Interval (sn)"
        TextInput:
            id: scanint
            text: root.scan_sec
            multiline: False
            input_filter: "int"

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
            height: max(self.texture_size[1], dp(520))
"""


class RootUI(BoxLayout):
    tf = StringProperty("15m")
    min_atr_int = StringProperty("65")   # 65 => 0.0065
    scan_sec = StringProperty("300")

    running = BooleanProperty(False)
    status = StringProperty("Hazır.")
    log_text = StringProperty("")

    _t = None
    _stop = None
    _last_alert = {}

    _okx_set = set()
    _okx_ts = 0

    def _log_ui(self, s: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text = f"[{ts}] {s}\n" + self.log_text[:20000]

    def _log(self, s: str):
        Clock.schedule_once(lambda *_: self._log_ui(s), 0)

    def start(self):
        if self.running:
            return
        self.running = True
        self.status = "Çalışıyor..."
        self._stop = threading.Event()

        self.tf = (self.ids.tf.text or "").strip() or "15m"
        self.min_atr_int = (self.ids.atr_int.text or "").strip() or "65"
        self.scan_sec = (self.ids.scanint.text or "").strip() or "300"

        self._t = threading.Thread(target=self._run_loop, daemon=True)
        self._t.start()
        self._log("Başlatıldı ✅")

    def stop(self):
        try:
            if self._stop:
                self._stop.set()
        except:
            pass
        self.running = False
        self.status = "Durduruldu."
        self._log("Durduruldu 🛑")

    def _can_alert(self, symbol, direction, cooldown_min=5):
        key = (symbol, direction)
        now = time.time()
        last = self._last_alert.get(key, 0)
        if (now - last) >= cooldown_min * 60:
            self._last_alert[key] = now
            return True
        return False

    def _min_atr_percent(self):
        # boş input / silme crash fix
        try:
            txt = (self.ids.atr_int.text or "").strip()
            if not txt:
                return 0.0065
            v = int(txt)
            v = max(0, min(v, 500))  # 0..500 => 0..5.00%
            return v / 10000.0
        except:
            return 0.0065

    def _scan_interval(self):
        try:
            txt = (self.ids.scanint.text or "").strip()
            if not txt:
                return 300
            v = int(txt)
            return max(5, min(v, 24 * 3600))
        except:
            return 300

    def _refresh_okx(self):
        if time.time() - self._okx_ts < 15 * 60 and self._okx_set:
            return
        self._log("OKX futures listesi çekiliyor...")
        s = okx_futures_usdt_symbols_normalized()
        if s:
            self._okx_set = s
            self._okx_ts = time.time()
            self._log(f"OKX futures hazır ✅ ({len(s)} sembol)")
        else:
            self._log("OKX listesi alınamadı (internet/okx)")

    def _run_loop(self):
        try:
            self._log("SSL certifi aktif ✅")
            while not self._stop.is_set():
                try:
                    self._refresh_okx()

                    min_atr = self._min_atr_percent()
                    scan_interval = self._scan_interval()

                    top_volume_count = 60
                    top_volatile_count = 25
                    rr = 2.0

                    self._log("24h tickers çekiliyor...")
                    tickers = b_fetch_24h_tickers()

                    fut = []
                    for t in tickers:
                        sym = (t.get("symbol", "") or "").upper()
                        if sym.endswith("USDT"):
                            try:
                                qv = float(t.get("quoteVolume", "0"))
                            except:
                                qv = 0.0
                            fut.append((sym, qv))
                    fut.sort(key=lambda x: x[1], reverse=True)
                    topN = [x[0] for x in fut[:top_volume_count]]

                    self._log("Volatilite (ATR%) hesaplanıyor...")
                    vols = []
                    for sym in topN:
                        if self._stop.is_set():
                            break
                        try:
                            h, l, c = b_fetch_klines(sym, self.tf, limit=80)
                            a = atr(h, l, c, 14)
                            if a is None:
                                continue
                            vols.append((sym, a / c[-1]))
                            time.sleep(0.04)
                        except:
                            continue

                    vols.sort(key=lambda x: x[1], reverse=True)
                    selected = [x[0] for x in vols[:top_volatile_count]]

                    # OKX filtresi (normalize ile)
                    if self._okx_set:
                        selected_okx = []
                        for s in selected:
                            if normalize_symbol_for_match(s) in self._okx_set:
                                selected_okx.append(s)
                    else:
                        selected_okx = selected[:]

                    if not selected_okx:
                        self._log("Seçilenler OKX filtresinden geçmedi (eşleme sorunu olabilir).")
                    else:
                        self._log(f"Seçilenler (OKX futures filtreli): {', '.join(selected_okx[:12])} ...")

                    for sym in selected_okx:
                        if self._stop.is_set():
                            break
                        try:
                            h, l, c = b_fetch_klines(sym, self.tf, limit=220)
                            res = generate_signal(h, l, c, min_atr_percent=min_atr, rr=rr)
                            if not res:
                                continue

                            # direction fix (tek satır)
                            direction = res.get("direction", "UNKNOWN")
                            if not self._can_alert(sym, direction, cooldown_min=5):
                                continue

                            setup = (res.get("setup") or "").strip()

                            msg = (
                                f"{'='*44}\n"
                                f"{res.get('type','SIGNAL')} | {direction} | #{sym}\n"
                                f"{setup}\n"
                                f"Entry: {res.get('entry',0):.6f}\n"
                                f"Stop : {res.get('stop',0):.6f}\n"
                                f"TP   : {res.get('tp',0):.6f}\n"
                                f"{'='*44}"
                            )

                            self._log(msg)
                            time.sleep(0.12)
                        except:
                            continue

                    self._log(f"Tarama bitti: {datetime.now().strftime('%H:%M')}")

                    for _ in range(max(1, scan_interval)):
                        if self._stop.is_set():
                            break
                        time.sleep(1)

                except Exception as e:
                    self._log(f"Ana döngü hatası: {e}")
                    time.sleep(3)

        except Exception as e:
            self._log(f"THREAD FATAL: {e}")
            self.running = False
            self.status = "Hata!"


class UgurCoinsV2(App):
    def build(self):
        Builder.load_string(KV)
        return RootUI()


if __name__ == "__main__":
    UgurCoinsV2().run()
