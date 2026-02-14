# ai_radar_core.py
# Core engine extracted for Kivy app. No API key. Binance Futures public endpoints.

import os
import time
import math
import requests
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from ta.trend import EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.momentum import RSIIndicator
from sklearn.ensemble import RandomForestClassifier

BINANCE_FAPI = "https://fapi.binance.com"
TR_TZ = timezone(timedelta(hours=3))

@dataclass
class RadarConfig:
    telegram_bot_token: str
    telegram_chat_id: str
    symbols: list[str]

    scan_interval_sec: int = 60
    min_ai_proba: float = 0.65

    alert_cooldown_min: int = 5
    only_on_new_5m_candle: bool = True

    atr_mult_sl: float = 2.0
    atr_mult_tp1: float = 1.5
    atr_mult_tp2: float = 3.0
    atr_mult_tp3: float = 5.0

    eval_horizon_candles: int = 48
    results_csv: str = "signals_results.csv"

@dataclass
class RadarEngine:
    cfg: RadarConfig
    log_cb: callable | None = None

    _stop: bool = False
    _last_alert: dict = field(default_factory=dict)      # (symbol, pattern, direction) -> ts
    _last_5m_candle: dict = field(default_factory=dict)  # symbol -> candle time
    pending: dict = field(default_factory=dict)          # signal_id -> dict
    _last_daily_report_date: str | None = None

    PRIORITY_PATTERNS: list[str] = field(default_factory=lambda: ["SQUEEZE_BREAKOUT", "LIQUIDITY_SWEEP_REVERSAL", "TREND_PULLBACK"])

    def log(self, s: str):
        if self.log_cb:
            try:
                self.log_cb(s)
            except Exception:
                pass

    # ---------- Telegram ----------
    def tg_send(self, text: str):
        url = f"https://api.telegram.org/bot{self.cfg.telegram_bot_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": self.cfg.telegram_chat_id, "text": text}, timeout=10)
        except Exception as e:
            self.log(f"Telegram error: {str(e)[:80]}")

    # ---------- Binance public ----------
    def fetch_klines(self, symbol: str, interval: str, limit: int = 320) -> pd.DataFrame:
        url = f"{BINANCE_FAPI}/fapi/v1/klines"
        r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data, columns=[
            "t","o","h","l","c","v","ct","qav","n","tbbav","tbqav","ig"
        ])
        df = df[["t","o","h","l","c","v"]].copy()
        df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert(TR_TZ)
        for col in ["o","h","l","c","v"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.dropna()

    def fetch_funding_and_mark(self, symbol: str):
        url = f"{BINANCE_FAPI}/fapi/v1/premiumIndex"
        r = requests.get(url, params={"symbol": symbol}, timeout=10)
        r.raise_for_status()
        j = r.json()
        return float(j.get("markPrice", "nan")), float(j.get("lastFundingRate", "nan"))

    def fetch_open_interest(self, symbol: str):
        url = f"{BINANCE_FAPI}/futures/data/openInterestHist"
        try:
            r = requests.get(url, params={"symbol": symbol, "period": "5m", "limit": 2}, timeout=10)
            r.raise_for_status()
            j = r.json()
            if isinstance(j, list) and len(j) >= 1:
                return float(j[-1].get("sumOpenInterest", "nan"))
        except Exception:
            pass
        return float("nan")

    # ---------- Indicators ----------
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        d["ema7"]  = EMAIndicator(d["c"], 7).ema_indicator()
        d["ema25"] = EMAIndicator(d["c"], 25).ema_indicator()
        d["ema50"] = EMAIndicator(d["c"], 50).ema_indicator()
        d["rsi14"] = RSIIndicator(d["c"], 14).rsi()

        bb = BollingerBands(d["c"], window=20, window_dev=2)
        d["bb_m"] = bb.bollinger_mavg()
        d["bb_h"] = bb.bollinger_hband()
        d["bb_l"] = bb.bollinger_lband()
        d["bb_width"] = (d["bb_h"] - d["bb_l"]) / d["bb_m"]

        atr = AverageTrueRange(d["h"], d["l"], d["c"], window=14)
        d["atr14"] = atr.average_true_range()

        d["ret1"] = d["c"].pct_change(1)
        d["ret3"] = d["c"].pct_change(3)
        d["ret6"] = d["c"].pct_change(6)
        d["v_chg"] = d["v"].pct_change(5)
        return d.dropna()

    def regime_1h(self, df1h: pd.DataFrame) -> str:
        last = df1h.iloc[-1]
        up = last["ema7"] > last["ema25"] > last["ema50"]
        dn = last["ema7"] < last["ema25"] < last["ema50"]
        if up: return "UP"
        if dn: return "DOWN"
        return "RANGE"

    # ---------- Patterns ----------
    def detect_squeeze_breakout(self, df5: pd.DataFrame):
        last = df5.iloc[-1]
        w = float(last["bb_width"])
        w_min = float(df5["bb_width"].rolling(80).min().iloc[-1])
        is_squeeze = w <= (w_min * 1.25)
        up_break = last["c"] > last["bb_h"]
        dn_break = last["c"] < last["bb_l"]
        vol_ok = float(last["v_chg"]) > 0.2
        if is_squeeze and vol_ok and (up_break or dn_break):
            direction = "LONG" if up_break else "SHORT"
            return {"pattern":"SQUEEZE_BREAKOUT","direction":direction,"detail":"Squeeze → Expansion + BB Breakout"}
        return None

    def detect_liquidity_sweep_reversal(self, df5: pd.DataFrame):
        prev = df5.iloc[-21:-1]
        last = df5.iloc[-1]
        swing_high = prev["h"].max()
        swing_low = prev["l"].min()
        swept_high = last["h"] > swing_high and last["c"] < swing_high
        swept_low  = last["l"] < swing_low  and last["c"] > swing_low
        if swept_low and last["rsi14"] < 50:
            return {"pattern":"LIQUIDITY_SWEEP_REVERSAL","direction":"LONG","detail":"Stop hunt (low) → close back"}
        if swept_high and last["rsi14"] > 50:
            return {"pattern":"LIQUIDITY_SWEEP_REVERSAL","direction":"SHORT","detail":"Stop hunt (high) → close back"}
        return None

    def detect_trend_pullback(self, df5: pd.DataFrame, reg: str):
        last = df5.iloc[-1]
        prev = df5.iloc[-2]
        if reg == "UP":
            near = abs(last["c"] - last["ema25"]) <= last["atr14"] * 0.25
            bounce = last["c"] > prev["c"] and last["rsi14"] > 50
            if near and bounce:
                return {"pattern":"TREND_PULLBACK","direction":"LONG","detail":"UP regime → EMA25 pullback bounce"}
        if reg == "DOWN":
            near = abs(last["c"] - last["ema25"]) <= last["atr14"] * 0.25
            reject = last["c"] < prev["c"] and last["rsi14"] < 50
            if near and reject:
                return {"pattern":"TREND_PULLBACK","direction":"SHORT","detail":"DOWN regime → EMA25 pullback reject"}
        return None

    def pick_best_pattern(self, df5: pd.DataFrame, reg: str):
        checks = [self.detect_squeeze_breakout(df5), self.detect_liquidity_sweep_reversal(df5), self.detect_trend_pullback(df5, reg)]
        for p in self.PRIORITY_PATTERNS:
            for c in checks:
                if c and c["pattern"] == p:
                    return c
        return None

    # ---------- AI Probability ----------
    def build_ai_dataset(self, df5: pd.DataFrame) -> pd.DataFrame:
        d = df5.copy()
        horizon = 6
        d["fret"] = d["c"].shift(-horizon) / d["c"] - 1.0
        d["y_up"] = (d["fret"] > 0).astype(int)
        feats = ["ret1","ret3","ret6","v_chg","ema7","ema25","ema50","rsi14","bb_width","atr14"]
        out = d.dropna().copy()
        return out[feats + ["y_up"]]

    def ai_probability(self, df5: pd.DataFrame, direction: str) -> float:
        ds = self.build_ai_dataset(df5)
        if len(ds) < 180:
            return 0.0
        feats = ds.columns[:-1]
        X = ds[feats].values
        y = ds["y_up"].values
        X_train, y_train = X[:-1], y[:-1]
        x_last = X[-1:].copy()
        clf = RandomForestClassifier(n_estimators=140, max_depth=6, random_state=42, n_jobs=-1)
        clf.fit(X_train, y_train)
        p_up = float(clf.predict_proba(x_last)[0][1])
        return p_up if direction == "LONG" else (1.0 - p_up)

    # ---------- Levels ----------
    def levels(self, df5: pd.DataFrame, direction: str):
        last = df5.iloc[-1]
        atr = float(last["atr14"])
        price = float(last["c"])
        zone_low, zone_high = (price - 0.3*atr, price + 0.3*atr)
        if direction == "LONG":
            sl  = price - self.cfg.atr_mult_sl * atr
            tp1 = price + self.cfg.atr_mult_tp1 * atr
            tp2 = price + self.cfg.atr_mult_tp2 * atr
            tp3 = price + self.cfg.atr_mult_tp3 * atr
        else:
            sl  = price + self.cfg.atr_mult_sl * atr
            tp1 = price - self.cfg.atr_mult_tp1 * atr
            tp2 = price - self.cfg.atr_mult_tp2 * atr
            tp3 = price - self.cfg.atr_mult_tp3 * atr
        return zone_low, zone_high, sl, tp1, tp2, tp3, atr, price

    def fmt_price(self, x: float):
        if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
            return "-"
        if x >= 1000:
            return f"{x:,.1f}"
        if x >= 1:
            return f"{x:,.4f}"
        return f"{x:.8f}"

    # ---------- Anti-spam ----------
    def can_alert(self, symbol: str, pattern: str, direction: str, last_candle_time) -> bool:
        if self.cfg.only_on_new_5m_candle:
            prev_t = self._last_5m_candle.get(symbol)
            if prev_t is not None and prev_t == last_candle_time:
                return False
            self._last_5m_candle[symbol] = last_candle_time

        key = (symbol, pattern, direction)
        now = time.time()
        last_ts = self._last_alert.get(key, 0)
        if (now - last_ts) >= (self.cfg.alert_cooldown_min * 60):
            self._last_alert[key] = now
            return True
        return False

    # ---------- Winrate ----------
    def ensure_csv(self):
        if not os.path.exists(self.cfg.results_csv):
            pd.DataFrame(columns=[
                "time_tr","symbol","pattern","direction","ai_proba","entry","sl","tp1","tp2","tp3",
                "result","max_tp","bars_to_close"
            ]).to_csv(self.cfg.results_csv, index=False)

    def new_signal_id(self, symbol: str, t_tr: datetime) -> str:
        return f"{symbol}-{t_tr.strftime('%Y%m%d-%H%M')}-{int(time.time()*1000)%100000}"

    def add_pending(self, symbol, t_tr, pattern, direction, ai_p, entry, sl, tp1, tp2, tp3):
        sid = self.new_signal_id(symbol, t_tr)
        self.pending[sid] = {
            "id": sid,
            "time_tr": t_tr,
            "symbol": symbol,
            "pattern": pattern,
            "direction": direction,
            "ai_proba": ai_p,
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "start_candle_time": t_tr,
            "status": "OPEN"
        }

    def evaluate_one_signal(self, sig: dict, df5: pd.DataFrame):
        direction = sig["direction"]
        sl, tp1, tp2, tp3 = sig["sl"], sig["tp1"], sig["tp2"], sig["tp3"]
        after = df5[df5["t"] > sig["start_candle_time"]].copy()
        if after.empty:
            return None

        max_tp = 0
        bars = 0
        for _, row in after.iterrows():
            bars += 1
            high = float(row["h"]); low = float(row["l"])
            if direction == "LONG":
                if low <= sl:
                    return ("LOSS_SL", max_tp, bars)
                if high >= tp3:
                    return ("WIN_TP3", 3, bars)
                if high >= tp2:
                    max_tp = max(max_tp, 2)
                elif high >= tp1:
                    max_tp = max(max_tp, 1)
            else:
                if high >= sl:
                    return ("LOSS_SL", max_tp, bars)
                if low <= tp3:
                    return ("WIN_TP3", 3, bars)
                if low <= tp2:
                    max_tp = max(max_tp, 2)
                elif low <= tp1:
                    max_tp = max(max_tp, 1)
            if bars >= self.cfg.eval_horizon_candles:
                return ("TIMEOUT", max_tp, bars)
        return None

    def close_signal(self, sig_id: str, result: str, max_tp: int, bars: int):
        sig = self.pending.get(sig_id)
        if not sig:
            return
        self.ensure_csv()
        df = pd.read_csv(self.cfg.results_csv)
        df.loc[len(df)] = [
            sig["time_tr"].strftime("%Y-%m-%d %H:%M"),
            sig["symbol"], sig["pattern"], sig["direction"], round(sig["ai_proba"], 4),
            sig["entry"], sig["sl"], sig["tp1"], sig["tp2"], sig["tp3"],
            result, max_tp, bars
        ]
        df.to_csv(self.cfg.results_csv, index=False)
        del self.pending[sig_id]

    def winrate_summary(self, day_str: str):
        if not os.path.exists(self.cfg.results_csv):
            return None
        df = pd.read_csv(self.cfg.results_csv)
        d = df[df["time_tr"].str.startswith(day_str)]
        if d.empty:
            return None
        total = len(d)
        wins = (d["result"] == "WIN_TP3").sum()
        losses = (d["result"] == "LOSS_SL").sum()
        timeouts = (d["result"] == "TIMEOUT").sum()
        tp1plus = (d["max_tp"] >= 1).sum()
        tp2plus = (d["max_tp"] >= 2).sum()
        return {"total": int(total), "wins": int(wins), "losses": int(losses), "timeouts": int(timeouts),
                "winrate": float(wins/total) if total else 0.0, "tp1plus": int(tp1plus), "tp2plus": int(tp2plus)}

    def maybe_send_daily_report(self):
        now = datetime.now(TR_TZ)
        day_str = now.strftime("%Y-%m-%d")
        if now.hour == 23 and now.minute >= 55:
            if self._last_daily_report_date == day_str:
                return
            self._last_daily_report_date = day_str
            s = self.winrate_summary(day_str)
            if not s:
                self.tg_send(f"📒 Günlük Rapor ({day_str})\nBugün kapanmış sinyal yok.")
                return
            msg = (
                f"📒 Günlük Rapor ({day_str})\n"
                f"Toplam: {s['total']}\n"
                f"✅ Win(TP3): {s['wins']}\n"
                f"❌ Loss(SL): {s['losses']}\n"
                f"⏳ Timeout: {s['timeouts']}\n"
                f"🎯 Winrate: {int(s['winrate']*100)}%\n"
                f"📌 TP1+ görmüş: {s['tp1plus']} | TP2+ görmüş: {s['tp2plus']}"
            )
            self.tg_send(msg)

    # ---------- Message ----------
    def make_message(self, symbol: str, reg: str, pat: dict, proba: float,
                     zone_low, zone_high, sl, tp1, tp2, tp3, atr,
                     mark, funding, oi, t_tr: datetime):
        return (
            f"📡 COIN: {symbol}\n"
            f"🧠 Yön: {pat['direction']}\n"
            f"🎯 Olasılık: {int(proba*100)}% (AI)\n"
            f"🕒 Zaman: {t_tr.strftime('%Y-%m-%d %H:%M')} (TR)\n\n"
            f"━━━━━━━━━━\n"
            f"📍 Entry Zone: {self.fmt_price(zone_low)} – {self.fmt_price(zone_high)}\n"
            f"🛑 Stop Loss (ATR): {self.fmt_price(sl)}\n"
            f"🎯 TP1: {self.fmt_price(tp1)}\n"
            f"🎯 TP2: {self.fmt_price(tp2)}\n"
            f"🎯 TP3: {self.fmt_price(tp3)}\n\n"
            f"━━━━━━━━━━\n"
            f"📊 Pattern: {pat['pattern']}\n"
            f"🧩 Detay: {pat['detail']}\n"
            f"🌊 Trend(1h): {reg}\n"
            f"⏱ TF: 5m / 15m / 1h\n"
            f"📏 ATR(5m): {self.fmt_price(atr)}\n\n"
            f"━━━━━━━━━━\n"
            f"💹 Mark: {self.fmt_price(mark)} | Funding: {funding:+.4%}\n"
            f"📌 OI(5m): {self.fmt_price(oi)}\n"
            f"🛡 Risk: Orta"
        )

    # ---------- Lifecycle ----------
    def stop(self):
        self._stop = True

    def run_forever(self):
        self.ensure_csv()
        self.log("✅ Engine başladı.")
        while not self._stop:
            # evaluate pending
            for sid, sig in list(self.pending.items()):
                try:
                    df5 = self.add_indicators(self.fetch_klines(sig["symbol"], "5m", 320))
                    out = self.evaluate_one_signal(sig, df5)
                    if out:
                        result, max_tp, bars = out
                        self.close_signal(sid, result, max_tp, bars)
                        self.tg_send(f"📌 Kapanış | {sig['symbol']} {sig['direction']}\nSonuç: {result} | MaxTP: {max_tp} | Bar: {bars}")
                except Exception:
                    pass

            # scan
            for sym in self.cfg.symbols:
                if self._stop:
                    break
                try:
                    df5_raw = self.fetch_klines(sym, "5m", 320)
                    df1h_raw = self.fetch_klines(sym, "1h", 260)
                    df5 = self.add_indicators(df5_raw)
                    df1h = self.add_indicators(df1h_raw)

                    reg = self.regime_1h(df1h)
                    pat = self.pick_best_pattern(df5, reg)
                    if not pat:
                        continue

                    last_candle_time = df5_raw.iloc[-1]["t"]
                    if not self.can_alert(sym, pat["pattern"], pat["direction"], last_candle_time):
                        continue

                    proba = self.ai_probability(df5, pat["direction"])
                    if proba < self.cfg.min_ai_proba:
                        continue

                    zone_low, zone_high, sl, tp1, tp2, tp3, atr, entry = self.levels(df5, pat["direction"])
                    mark, funding = self.fetch_funding_and_mark(sym)
                    oi = self.fetch_open_interest(sym)
                    t_tr = datetime.now(TR_TZ)

                    msg = self.make_message(sym, reg, pat, proba, zone_low, zone_high, sl, tp1, tp2, tp3, atr, mark, funding, oi, t_tr)
                    self.tg_send(msg)
                    self.log(f"SENT {sym} {pat['pattern']} {int(proba*100)}%")
                    self.add_pending(sym, t_tr, pat["pattern"], pat["direction"], proba, entry, sl, tp1, tp2, tp3)

                    time.sleep(0.25)
                except Exception as e:
                    s = str(e)
                    if "429" in s or "Too Many Requests" in s:
                        time.sleep(2.0)
                    else:
                        self.log(f"ERR {sym}: {s[:80]}")
                        continue

            self.maybe_send_daily_report()
            time.sleep(self.cfg.scan_interval_sec)

        self.log("⏹ Engine durdu.")
