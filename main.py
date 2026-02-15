# ==========================================
# UGUR COINS v3 (Android Tek Dosya)
# AI Learning & Edge Memory Edition
# ==========================================

import os
import re
import time
import json
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
# AI CONSTANTS
# -------------------------
EDGE_HORIZON_BARS = 10     # 15m TF için 150 dk sonra ölçer
EDGE_MIN_SAMPLES  = 15     # Confidence MED olması için gereken min örnek
EDGE_FILE_NAME    = "edge_memory.json"

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

# -------------------------
# AI CORE FUNCTIONS
# -------------------------
def _edge_path():
    try: d = App.get_running_app().user_data_dir
    except: d = "."
    return os.path.join(d, EDGE_FILE_NAME)

def edge_load():
    p = _edge_path()
    try:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return {"patterns": {}, "pending": []}

def edge_save(db):
    p = _edge_path()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False)
    except: pass

def _pattern_key(setup, direction, tf, feat):
    def b(x, step):
        try: return int(x / step) * step
        except: return 0
    atrp = b(feat.get("atrp", 0), 0.001)
    return f"{tf}|{setup}|{direction}|atrp:{atrp:.3f}"

def edge_prob(db, setup, direction, tf, feat):
    key = _pattern_key(setup, direction, tf, feat)
    pat = db["patterns"].get(key)
    if not pat: return None
    w, l, n = pat.get("w", 0), pat.get("l", 0), pat.get("n", 0)
    p = (w + 2) / (w + l + 4) if (w + l) > 0 else 0.5
    conf = "HIGH" if n >= 50 else ("MED" if n >= EDGE_MIN_SAMPLES else "LOW")
    return p, conf, n, w, l

def edge_register_pending(db, symbol, tf, setup, direction, entry, stop, feat, close_len):
    key = _pattern_key(setup or "NONE", direction, tf, feat)
    db["pending"].append({
        "symbol": symbol, "tf": tf, "key": key, "direction": direction,
        "entry": float(entry), "stop": float(stop) if stop else None,
        "created_at": time.time(), "bars_at_create": int(close_len)
    })

def edge_update_logic(db, symbol, tf, close_prices):
    if not db["pending"]: return 0
    updated, keep, cur_price, cur_len = 0, [], close_prices[-1], len(close_prices)
    for it in db["pending"]:
        if it["symbol"] != symbol or it["tf"] != tf:
            keep.append(it); continue
        if cur_len < it["bars_at_create"] + EDGE_HORIZON_BARS:
            keep.append(it); continue
        
        key, direction, entry, stop = it["key"], it["direction"], it["entry"], it["stop"]
        win, lose = False, False
        if direction == "LONG":
            lose = (cur_price <= stop) if stop else (cur_price < entry)
            win = (cur_price >= entry + (entry - (stop or entry*0.99)) * 0.5)
        else:
            lose = (cur_price >= stop) if stop else (cur_price > entry)
            win = (cur_price <= entry - ((stop or entry*1.01) - entry) * 0.5)

        pat = db["patterns"].setdefault(key, {"w": 0, "l": 0, "nr": 0, "n": 0})
        if win and not lose: pat["w"] += 1
        elif lose and not win: pat["l"] += 1
        else: pat["nr"] += 1
        pat["n"] = pat["w"] + pat["l"] + pat["nr"]
        updated += 1
    db["pending"] = keep
    return updated

# -------------------------
# UTILS & INDICATORS
# -------------------------
def normalize_symbol_for_match(sym: str) -> str:
    s = sym.upper().replace("-", "").replace("SWAP", "").strip()
    if not s.endswith("USDT"): return s
    base = s[:-4]
    base2 = re.sub(r"^(1000|10000|1M|2M|10M)", "", base)
    return f"{base2}USDT"

def okx_futures_usdt_symbols_normalized():
    try:
        r = requests.get(f"{OKX}/api/v5/public/instruments", params={"instType": "SWAP"}, timeout=15)
        data = r.json().get("data", [])
        return {normalize_symbol_for_match(f"{it['instId'].split('-')[0]}USDT") for it in data if "-USDT-SWAP" in it.get("instId", "")}
    except: return set()

def ema(series, length):
    if len(series) < length: return None
    k, v = 2.0 / (length + 1.0), sum(series[:length]) / length
    for x in series[length:]: v = (x * k) + (v * (1 - k))
    return v

def atr(high, low, close, length=14):
    if len(close) < length + 1: return None
    trs = [max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])) for i in range(1, len(close))]
    return sum(trs[-length:]) / length

# -------------------------
# STRATEGY & SIGNAL
# -------------------------
def classify_setup(price, ema7, ema25, ema45, ema90, ema7_slope, ema45_slope, ema90_slope, atrv):
    try:
        spread = max(ema7, ema25, ema45, ema90) - min(ema7, ema25, ema45, ema90)
        if spread <= (0.35 * atrv): return "🧨 EXPLOSION SETUP"
        if (ema45 > ema90) and (price >= ema25):
            return "🔥 HIGH PROB LONG" if (ema7_slope > 0 and ema45_slope > 0) else "⚠️ WEAK LONG"
        if (ema45 < ema90) and (price <= ema25):
            return "🔥 HIGH PROB SHORT" if (ema7_slope < 0 and ema45_slope < 0) else "⚠️ WEAK SHORT"
    except: pass
    return ""

def generate_signal(high, low, close, min_atr_percent=0.0065):
    e7, e25, e45, e90 = ema(close,7), ema(close,25), ema(close,45), ema(close,90)
    if None in (e7, e25, e45, e90): return None
    atrv = atr(high, low, close, 14)
    if not atrv or (atrv/close[-1]) < min_atr_percent: return None
    
    price, e7_p, e45_p, e90_p = close[-1], ema(close[:-1],7), ema(close[:-1],45), ema(close[:-1],90)
    s7, s45, s90 = e7-(e7_p or e7), e45-(e45_p or e45), e90-(e90_p or e90)
    setup = classify_setup(price, e7, e25, e45, e90, s7, s45, s90, atrv)
    
    if price > e90 and s90 > 0 and s7 > 0 and e7 > e25:
        stop = min(low[-2:])
        return {"type": "SIGNAL", "direction": "LONG", "entry": price, "stop": stop, "tp": price+(price-stop)*2, "setup": setup}
    if price < e90 and s90 < 0 and s7 < 0 and e7 < e25:
        stop = max(high[-2:])
        return {"type": "SIGNAL", "direction": "SHORT", "entry": price, "stop": stop, "tp": price-(stop-price)*2, "setup": setup}
    return None

# -------------------------
# KIVY UI
# -------------------------
KV = r"""
<RootUI>:
    orientation: "vertical"
    padding: dp(10)
    Label:
        text: "UGUR COINS v3 [AI EDGE]"
        bold: True
        size_hint_y: None
        height: dp(30)
    GridLayout:
        cols: 2
        size_hint_y: None
        height: dp(100)
        Label: text: "TF (15m/1h):"
        TextInput:
            id: tf
            text: "15m"
        Label: text: "Min ATR (65=%0.65):"
        TextInput:
            id: atr_int
            text: "65"
    BoxLayout:
        size_hint_y: None
        height: dp(45)
        Button:
            text: "BAŞLAT"
            on_release: root.start()
        Button:
            text: "DURDUR"
            on_release: root.stop()
    Label:
        text: root.status
        size_hint_y: None
        height: dp(25)
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
    status = StringProperty("Hazır.")
    log_text = StringProperty("")
    running = BooleanProperty(False)
    _edge_db = {}

    def _log(self, s):
        Clock.schedule_once(lambda *_: setattr(self, 'log_text', f"[{datetime.now().strftime('%H:%M:%S')}] {s}\n" + self.log_text[:10000]), 0)

    def start(self):
        if self.running: return
        self._edge_db = edge_load()
        self.running = True
        self._stop = threading.Event()
        threading.Thread(target=self._run_loop, daemon=True).start()
        self._log("AI Memory Yüklendi & Başlatıldı ✅")

    def stop(self):
        if hasattr(self, '_stop'): self._stop.set()
        self.running = False
        self._log("Durduruldu 🛑")

    def _run_loop(self):
        okx_set = set()
        while not self._stop.is_set():
            try:
                if not okx_set: okx_set = okx_futures_usdt_symbols_normalized()
                min_atr = int(self.ids.atr_int.text or 65) / 10000.0
                tf = self.ids.tf.text or "15m"

                self._log("Tarama başlıyor...")
                tickers = b_fetch_24h_tickers()
                # Hacim sıralı ilk 50
                syms = sorted([(t['symbol'], float(t['quoteVolume'])) for t in tickers if t['symbol'].endswith('USDT')], key=lambda x: x[1], reverse=True)[:50]
                
                for sym, vol in syms:
                    if self._stop.is_set(): break
                    if normalize_symbol_for_match(sym) not in okx_set: continue
                    
                    h, l, c = b_fetch_klines(sym, tf, limit=100)
                    
                    # AI UPDATE
                    u = edge_update_logic(self._edge_db, sym, tf, c)
                    if u > 0: edge_save(self._edge_db)

                    res = generate_signal(h, l, c, min_atr)
                    if res:
                        setup, dir = res['setup'], res['direction']
                        feat = {"atrp": atr(h,l,c,14)/c[-1]}
                        
                        # AI PROBABILITY
                        prob_info = edge_prob(self._edge_db, setup, dir, tf, feat)
                        ai_msg = ""
                        if prob_info:
                            p, conf, n, w, lo = prob_info
                            ai_msg = f"\n🧠 AI Win%: {p*100:.0f} | Conf: {conf} (n={n})"
                        
                        msg = f"#{sym} {res['type']} {dir}\n{setup}{ai_msg}\nEntry: {res['entry']:.5f}"
                        self._log(msg)
                        
                        edge_register_pending(self._edge_db, sym, tf, setup, dir, res['entry'], res['stop'], feat, len(c))
                        edge_save(self._edge_db)
                    
                    time.sleep(0.1)
                
                self._log("Tarama bitti, uykuya geçiliyor...")
                for _ in range(300):
                    if self._stop.is_set(): break
                    time.sleep(1)
            except Exception as e:
                self._log(f"Hata: {e}")
                time.sleep(10)

class UgurCoinsV2(App):
    def build(self):
        Builder.load_string(KV)
        return RootUI()

if __name__ == "__main__":
    UgurCoinsV2().run()

