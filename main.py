# ==========================================
# UGUR COINS v3 PRO (TEK DOSYA) - ANDROID
# Binance tarar ✅  OKX'te listelenenleri gösterir ✅
# Trap + Squeeze + Strong/Weak + Early + AI Öğrenme + Telegram ✅
# EMA/ATR saf python ✅  (pandas/numpy yok)
# ==========================================

import os
import time
import json
import threading
from datetime import datetime

import requests
import certifi

# Android SSL / CA Fix (kritik)
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout

# -------------------------
# API ENDPOINTS
# -------------------------
BINANCE_FAPI = "https://fapi.binance.com"
OKX_PUBLIC = "https://www.okx.com"

# -------------------------
# AI / Öğrenme ayarları
# -------------------------
EDGE_HORIZON = 10      # sinyalden kaç mum sonra "başarılı" sayalım?
EDGE_DECAY = 0.95      # hafıza eskimesi (0.95 = yavaş unutma)
MEM_FILE = "ugurcoins_v3_pro_mem.json"

# -------------------------
# Tarama ayarları (default)
# -------------------------
TOP_VOLUME_N = 40      # hacimden seç
TOP_VOLATILE_N = 20    # volatiliteden seç

# -------------------------
# YARDIMCI: Kayıt yolu
# -------------------------
def _get_save_path():
    try:
        # bazı cihazlarda android.storage olabilir
        from android.storage import app_storage_path
        d = app_storage_path()
        return os.path.join(d, MEM_FILE)
    except:
        try:
            # Kivy'nin kendi güvenli dizini (Android'de sorunsuz)
            d = App.get_running_app().user_data_dir
            return os.path.join(d, MEM_FILE)
        except:
            return MEM_FILE

# -------------------------
# Binance/OKX fetch
# -------------------------
def fetch_24h_tickers():
    r = requests.get(f"{BINANCE_FAPI}/fapi/v1/ticker/24hr", timeout=15, verify=certifi.where())
    r.raise_for_status()
    return r.json()

def fetch_klines(symbol: str, interval: str, limit: int = 220):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(f"{BINANCE_FAPI}/fapi/v1/klines", params=params, timeout=15, verify=certifi.where())
    r.raise_for_status()
    data = r.json()
    # [openTime, open, high, low, close, volume, ...]
    h = [float(x[2]) for x in data]
    l = [float(x[3]) for x in data]
    c = [float(x[4]) for x in data]
    return h, l, c

def okx_usdt_swap_bases():
    """
    OKX USDT-SWAP'te listelenen base'leri döndürür.
    Örn: BTC-USDT-SWAP -> BTC
    """
    try:
        r = requests.get(
            f"{OKX_PUBLIC}/api/v5/public/instruments",
            params={"instType": "SWAP"},
            timeout=15,
            verify=certifi.where()
        ).json()
        bases = set()
        for it in r.get("data", []):
            inst = it.get("instId", "")
            if inst.endswith("-USDT-SWAP"):
                base = inst.split("-")[0].strip()
                if base:
                    bases.add(base)
        return bases
    except:
        return set()

# -------------------------
# İNDİKATÖRLER (saf python)
# -------------------------
def ema_value(series, length):
    if len(series) < length:
        return None
    k = 2.0 / (length + 1.0)
    v = sum(series[:length]) / length
    for x in series[length:]:
        v = (x * k) + (v * (1 - k))
    return v

def atr_value(high, low, close, length=14):
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
# PRO SINIFLANDIRMA (Trap + Squeeze + Strong/Weak + Early)
# -------------------------
def classify_setup(price, atrv, ema7, ema25, ema45, ema90, ema7_slope, ema45_slope, ema90_slope):
    """
    Türkçe etiketler:
    - PATLAMA SETUP (Squeeze)
    - GÜÇLÜ LONG / GÜÇLÜ SHORT
    - ZAYIF LONG / ZAYIF SHORT
    - LONG TUZAĞI / SHORT TUZAĞI (Fake breakout)
    - TREND SOĞUMA
    """
    try:
        # SQUEEZE (Patlama setup): EMA'lar birbirine çok yakınsa
        spread = max(ema7, ema25, ema45, ema90) - min(ema7, ema25, ema45, ema90)
        if spread <= (0.35 * atrv):
            return "💥 PATLAMA SETUP (Sıkışma → Patlama)"

        # Tuzağı (Fake breakout)
        # Kısa vadede EMA7/25 ters ama büyük trend zıt = tuzak
        if (ema7 > ema25) and (ema45 < ema90):
            return "🪤 LONG TUZAĞI (Fake breakout)"
        if (ema7 < ema25) and (ema45 > ema90):
            return "🪤 SHORT TUZAĞI (Fake breakout)"

        # GÜÇLÜ / ZAYIF trend
        # LONG rejimi
        if (ema45 > ema90) and (price >= ema25):
            if (ema7 > ema25) and (ema7_slope > 0) and (ema45_slope > 0) and (ema90_slope > 0):
                return "🟢 GÜÇLÜ LONG"
            if (ema7 > ema25) and (ema7_slope <= 0):
                return "🟡 ZAYIF LONG"

        # SHORT rejimi
        if (ema45 < ema90) and (price <= ema25):
            if (ema7 < ema25) and (ema7_slope < 0) and (ema45_slope < 0) and (ema90_slope < 0):
                return "🔴 GÜÇLÜ SHORT"
            if (ema7 < ema25) and (ema7_slope >= 0):
                return "🟠 ZAYIF SHORT"

        # Trend soğuma (EMA7-25 yakın + ters bükülme)
        if abs(ema7 - ema25) <= (0.25 * atrv):
            if (ema7 > ema25 and ema7_slope < 0) or (ema7 < ema25 and ema7_slope > 0):
                return "🧊 TREND SOĞUMA (Kesişime yaklaşım)"

    except:
        pass

    return None

def build_tp_plan(direction, entry, atrv):
    """
    TP1/TP2/TP3 ve SL üretir.
    SL = 1.5*ATR
    TP1 = 1R, TP2 = 2R, TP3 = 3R
    """
    if direction == "LONG":
        stop = entry - (1.5 * atrv)
        risk = entry - stop
        return {
            "entry": entry,
            "stop": stop,
            "tp1": entry + (risk * 1.0),
            "tp2": entry + (risk * 2.0),
            "tp3": entry + (risk * 3.0),
        }
    if direction == "SHORT":
        stop = entry + (1.5 * atrv)
        risk = stop - entry
        return {
            "entry": entry,
            "stop": stop,
            "tp1": entry - (risk * 1.0),
            "tp2": entry - (risk * 2.0),
            "tp3": entry - (risk * 3.0),
        }
    return None

def generate_signal(high, low, close, min_atr_percent=0.0065):
    """
    Sinyal üretir:
    - setup etiketi (Türkçe)
    - direction
    - plan (entry/sl/tp1/tp2/tp3)
    - EMA seviyeleri
    """
    ema7  = ema_value(close, 7)
    ema25 = ema_value(close, 25)
    ema45 = ema_value(close, 45)
    ema90 = ema_value(close, 90)
    if None in (ema7, ema25, ema45, ema90):
        return None

    atrv = atr_value(high, low, close, 14)
    if atrv is None:
        return None

    price = close[-1]
    if price <= 0:
        return None

    # Min ATR% filtresi
    if (atrv / price) < min_atr_percent:
        return None

    # slope (son 1 mum çıkarıp yeniden hesap)
    ema7_prev  = ema_value(close[:-1], 7)  or ema7
    ema45_prev = ema_value(close[:-1], 45) or ema45
    ema90_prev = ema_value(close[:-1], 90) or ema90

    ema7_slope  = ema7  - ema7_prev
    ema45_slope = ema45 - ema45_prev
    ema90_slope = ema90 - ema90_prev

    setup = classify_setup(price, atrv, ema7, ema25, ema45, ema90, ema7_slope, ema45_slope, ema90_slope)
    if not setup:
        return None

    # direction çıkar (tuzağa göre de karar)
    direction = None
    if "LONG" in setup and "TUZAĞI" not in setup:
        direction = "LONG"
    elif "SHORT" in setup and "TUZAĞI" not in setup:
        direction = "SHORT"
    elif "LONG TUZAĞI" in setup:
        # longlar tuzakta -> yön SHORT
        direction = "SHORT"
    elif "SHORT TUZAĞI" in setup:
        # shortlar tuzakta -> yön LONG
        direction = "LONG"
    elif "PATLAMA SETUP" in setup or "TREND SOĞUMA" in setup:
        # early warning: büyük trend yönüne göre
        direction = "LONG" if (ema45 > ema90) else "SHORT"

    if not direction:
        return None

    plan = build_tp_plan(direction, price, atrv)
    if not plan:
        return None

    return {
        "setup": setup,
        "direction": direction,
        "atr": atrv,
        "price": price,
        "levels": {"EMA7": ema7, "EMA25": ema25, "EMA45": ema45, "EMA90": ema90},
        "plan": plan
    }

# -------------------------
# Telegram (opsiyonel)
# -------------------------
def tg_send(token, chat_id, msg):
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": msg}, timeout=12, verify=certifi.where())
    except:
        pass

# -------------------------
# KIVY UI
# -------------------------
KV = r"""
<RootUI>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(10)

    canvas.before:
        Color:
            rgba: 0.02, 0.02, 0.05, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: "UGUR COINS v3 PRO (Trap + Squeeze + AI)"
        bold: True
        size_hint_y: None
        height: dp(42)
        font_size: dp(18)

    GridLayout:
        cols: 2
        size_hint_y: None
        height: self.minimum_height
        row_default_height: dp(44)
        row_force_default: True
        spacing: dp(8)

        Label:
            text: "Timeframe (15m/1h/4h)"
        TextInput:
            id: tf
            text: root.tf
            multiline: False

        Label:
            text: "Min ATR (tam sayı) 65 = 0.65%"
        TextInput:
            id: atr_int
            text: root.atr_int
            multiline: False
            input_filter: "int"

        Label:
            text: "Tarama aralığı (saniye)"
        TextInput:
            id: scan_sec
            text: root.scan_sec
            multiline: False
            input_filter: "int"

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
        height: dp(28)

    ScrollView:
        do_scroll_x: False
        Label:
            text: root.log_text
            halign: "left"
            valign: "top"
            text_size: self.width, None
            size_hint_y: None
            height: max(self.texture_size[1], dp(420))
            font_size: dp(13)
"""

class RootUI(BoxLayout):
    tf = StringProperty("15m")
    atr_int = StringProperty("65")     # 65 => 0.65%
    scan_sec = StringProperty("60")    # saniye

    tg_token = StringProperty("")
    tg_chat = StringProperty("")
    tg_enabled = BooleanProperty(False)

    running = BooleanProperty(False)
    status = StringProperty("Hazır.")
    log_text = StringProperty("")

    _t = None
    _stop = None
    _okx_bases = set()

    # AI memory: key -> {"wins": float, "total": float}
    _mem = {}

    # pending: sinyal sonrası değerlendirme
    _pending = []  # [{"sym","tf","dir","entry","idx"}]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_mem()

    # ---------- UI log ----------
    def _log_ui(self, s: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text = f"[{ts}] {s}\n\n" + self.log_text[:26000]

    def _log(self, s: str):
        Clock.schedule_once(lambda *_: self._log_ui(s), 0)

    # ---------- memory ----------
    def _load_mem(self):
        try:
            p = _get_save_path()
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._mem = data.get("mem", {})
                    self._pending = data.get("pending", [])
        except:
            self._mem = {}
            self._pending = []

    def _save_mem(self):
        try:
            p = _get_save_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"mem": self._mem, "pending": self._pending}, f, ensure_ascii=False)
        except:
            pass

    def _mem_key(self, sym, tf, dkey, setup_key):
        # setup_key: TRAP / SQUEEZE / STRONG / WEAK / COOLING
        return f"{sym}|{tf}|{dkey}|{setup_key}"

    def _setup_key(self, setup_text: str):
        if "TUZAĞI" in setup_text:
            return "TRAP"
        if "PATLAMA SETUP" in setup_text:
            return "SQUEEZE"
        if "GÜÇLÜ" in setup_text:
            return "STRONG"
        if "ZAYIF" in setup_text:
            return "WEAK"
        if "SOĞUMA" in setup_text:
            return "COOLING"
        return "OTHER"

    def _update_learning(self, sym, tf, direction, setup_key, entry_price, closes, entry_idx):
        """
        EDGE_HORIZON mum sonra fiyat hedef yönde gitti mi?
        """
        try:
            now_idx = len(closes) - 1
            if now_idx < entry_idx + EDGE_HORIZON:
                return False  # daha zamanı gelmedi

            future_price = closes[entry_idx + EDGE_HORIZON]
            win = (future_price > entry_price) if direction == "LONG" else (future_price < entry_price)

            dkey = "L" if direction == "LONG" else "S"
            k = self._mem_key(sym, tf, dkey, setup_key)
            cur = self._mem.get(k, {"wins": 0.0, "total": 0.0})

            cur["wins"] = cur["wins"] * EDGE_DECAY + (1.0 if win else 0.0)
            cur["total"] = cur["total"] * EDGE_DECAY + 1.0
            self._mem[k] = cur
            return True
        except:
            return False

    def _ai_prob(self, sym, tf, direction, setup_key):
        dkey = "L" if direction == "LONG" else "S"
        k = self._mem_key(sym, tf, dkey, setup_key)
        cur = self._mem.get(k, {"wins": 0.0, "total": 0.0})
        if cur["total"] <= 0:
            return 0, 0
        prob = (cur["wins"] / cur["total"]) * 100.0
        return prob, int(cur["total"])

    # ---------- start/stop ----------
    def start(self):
        if self.running:
            return
        self.running = True
        self.status = "Çalışıyor..."
        self._stop = threading.Event()

        # UI değerlerini al (boş kalırsa default)
        self.tf = (self.ids.tf.text.strip() or "15m")
        self.atr_int = (self.ids.atr_int.text.strip() or "65")
        self.scan_sec = (self.ids.scan_sec.text.strip() or "60")
        self.tg_token = self.ids.tkn.text.strip()
        self.tg_chat = self.ids.cid.text.strip()
        self.tg_enabled = bool(self.ids.tgen.active)

        self._t = threading.Thread(target=self._run_loop, daemon=True)
        self._t.start()
        self._log("✅ Başlatıldı. Binance taranıyor → OKX listedekiler gösterilecek.")

    def stop(self):
        try:
            if self._stop:
                self._stop.set()
        except:
            pass
        self.running = False
        self.status = "Durduruldu."
        self._save_mem()
        self._log("⛔ Durduruldu. Hafıza kaydedildi.")

    # ---------- core scan ----------
    def _safe_int(self, s, default):
        try:
            s = (s or "").strip()
            if s == "":
                return default
            return int(s)
        except:
            return default

    def _run_loop(self):
        # ayar parse
        tf = self.tf.strip()
        atr_i = self._safe_int(self.atr_int, 65)
        min_atr = max(1, atr_i) / 10000.0  # 65 => 0.0065
        scan_interval = max(10, self._safe_int(self.scan_sec, 60))

        # OKX list
        self._log("📌 OKX futures listesi çekiliyor...")
        self._okx_bases = okx_usdt_swap_bases()
        if self._okx_bases:
            self._log(f"✅ OKX filtresi aktif. ({len(self._okx_bases)} coin)")
        else:
            self._log("⚠️ OKX listesi alınamadı. Filtre kapalı gibi davranacağım (her şeyi tarar).")

        while not self._stop.is_set():
            try:
                self._log("📡 24h verileri çekiliyor (Binance Futures)...")
                tickers = fetch_24h_tickers()

                # Top volume seç
                fut = []
                for t in tickers:
                    sym = t.get("symbol", "")
                    if not sym.endswith("USDT"):
                        continue
                    try:
                        qv = float(t.get("quoteVolume", 0) or 0)
                    except:
                        qv = 0.0
                    fut.append((sym, qv))

                fut.sort(key=lambda x: x[1], reverse=True)
                top_symbols = [x[0] for x in fut[:TOP_VOLUME_N]]

                # OKX filtresi uygula (base = BTCUSDT -> BTC)
                filtered = []
                for sym in top_symbols:
                    base = sym[:-4]
                    if self._okx_bases and (base not in self._okx_bases):
                        continue
                    filtered.append(sym)

                if not filtered:
                    self._log("⚠️ OKX filtresi sonrası liste boş. (Eşleşme toleransı yüzünden olabilir)")
                    filtered = top_symbols[:15]

                self._log("🔥 Volatilite (ATR%) ile en hareketliler seçiliyor...")

                # Volatilite seç
                vols = []
                for sym in filtered:
                    if self._stop.is_set():
                        break
                    try:
                        h, l, c = fetch_klines(sym, tf, limit=60)
                        a = atr_value(h, l, c, 14)
                        if a is None or c[-1] <= 0:
                            continue
                        vols.append((sym, a / c[-1]))
                        time.sleep(0.05)
                    except:
                        continue

                vols.sort(key=lambda x: x[1], reverse=True)
                scan_list = [x[0] for x in vols[:TOP_VOLATILE_N]] if vols else filtered[:TOP_VOLATILE_N]

                self._log(f"✅ Seçilenler ({len(scan_list)}): {', '.join(scan_list[:8])} ...")

                # asıl tarama
                for sym in scan_list:
                    if self._stop.is_set():
                        break
                    try:
                        h, l, c = fetch_klines(sym, tf, limit=220)

                        # öğrenme: pending işleri güncelle
                        if self._pending:
                            keep = []
                            for p in self._pending:
                                if p["sym"] == sym and p["tf"] == tf:
                                    done = self._update_learning(
                                        sym=p["sym"],
                                        tf=p["tf"],
                                        direction=p["dir"],
                                        setup_key=p["setup_key"],
                                        entry_price=p["entry"],
                                        closes=c,
                                        entry_idx=p["idx"]
                                    )
                                    if not done:
                                        keep.append(p)
                                else:
                                    keep.append(p)
                            self._pending = keep

                        # sinyal üret
                        res = generate_signal(h, l, c, min_atr_percent=min_atr)
                        if not res:
                            time.sleep(0.10)
                            continue

                        setup = res["setup"]
                        direction = res["direction"]
                        plan = res["plan"]
                        price = res["price"]
                        atrv = res["atr"]
                        setup_key = self._setup_key(setup)

                        # AI olasılık
                        prob, sample = self._ai_prob(sym, tf, direction, setup_key)

                        # mesaj (Türkçe + TP1/TP2/TP3)
                        msg = (
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📌 {sym}  |  {tf}\n"
                            f"🧠 Kurulum: {setup}\n"
                            f"➡️ Yön: {direction}\n"
                            f"📍 Entry: {plan['entry']:.6f}\n"
                            f"🛑 SL:   {plan['stop']:.6f}\n"
                            f"🎯 TP1:  {plan['tp1']:.6f}\n"
                            f"🎯 TP2:  {plan['tp2']:.6f}\n"
                            f"🎯 TP3:  {plan['tp3']:.6f}\n"
                            f"📏 ATR:  {atrv:.6f}  |  ATR%: {(atrv/price*100):.2f}%\n"
                            f"🤖 AI ONAYI: %{prob:.0f}  (tecrübe: {sample})\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━"
                        )

                        self._log(msg)

                        # telegram (opsiyonel)
                        if self.tg_enabled:
                            tg_send(self.tg_token, self.tg_chat, msg)

                        # pending'e ekle (learning)
                        # entry_idx = son kapanış indexi
                        self._pending.append({
                            "sym": sym,
                            "tf": tf,
                            "dir": direction,
                            "setup_key": setup_key,
                            "entry": plan["entry"],
                            "idx": len(c) - 1
                        })

                        time.sleep(0.15)

                    except:
                        continue

                self._save_mem()
                self._log(f"✅ Tarama bitti. {scan_interval}s bekleyeceğim...")

                for _ in range(scan_interval):
                    if self._stop.is_set():
                        break
                    time.sleep(1)

            except Exception as e:
                self._log(f"🔴 Ana döngü hatası: {str(e)[:80]}")
                time.sleep(5)

class UgurCoinsV3(App):
    def build(self):
        Builder.load_string(KV)
        return RootUI()

if __name__ == "__main__":
    UgurCoinsV3().run()
