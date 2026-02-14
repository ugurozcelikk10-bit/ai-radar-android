import threading
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout

from ai_radar_core import RadarConfig, RadarEngine

KV = r"""
#:import dp kivy.metrics.dp

<RootUI>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(10)

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        Label:
            text: "AI Radar v3 (Futures • AI≥65 • ATR • 3TP)"

    BoxLayout:
        size_hint_y: None
        height: dp(46)
        spacing: dp(8)
        TextInput:
            id: bot_token
            hint_text: "Telegram Bot Token"
            multiline: False
            password: True
            text: root.bot_token
        Button:
            text: "Yapıştır"
            size_hint_x: None
            width: dp(90)
            on_release:
                bot_token.text = root.paste()
        Button:
            text: "Kopyala"
            size_hint_x: None
            width: dp(90)
            on_release:
                root.copy(bot_token.text)

    BoxLayout:
        size_hint_y: None
        height: dp(46)
        spacing: dp(8)
        TextInput:
            id: chat_id
            hint_text: "Telegram Chat ID"
            multiline: False
            text: root.chat_id
        Button:
            text: "Yapıştır"
            size_hint_x: None
            width: dp(90)
            on_release:
                chat_id.text = root.paste()

    BoxLayout:
        size_hint_y: None
        height: dp(46)
        spacing: dp(8)
        TextInput:
            id: coins
            hint_text: "Sembol listesi (virgülle) örn: BTCUSDT,ETHUSDT,..."
            multiline: False
            text: root.symbols
        Button:
            text: "40 Varsayılan"
            size_hint_x: None
            width: dp(120)
            on_release:
                root.set_default_symbols()

    GridLayout:
        cols: 2
        size_hint_y: None
        height: self.minimum_height
        row_default_height: dp(44)
        row_force_default: True
        spacing: dp(8)

        Label:
            text: "AI Min Olasılık"
        TextInput:
            id: proba
            multiline: False
            text: root.min_ai_proba

        Label:
            text: "Tarama (sn)"
        TextInput:
            id: scan_sec
            multiline: False
            text: root.scan_interval

        Label:
            text: "Cooldown (dk)"
        TextInput:
            id: cooldown
            multiline: False
            text: root.cooldown_min

        Label:
            text: "Sadece yeni 5m mum"
        CheckBox:
            id: new_candle
            active: root.only_new_candle

    BoxLayout:
        size_hint_y: None
        height: dp(52)
        spacing: dp(10)
        Button:
            text: "Başlat"
            disabled: root.running
            on_release:
                root.start(bot_token.text, chat_id.text, coins.text, proba.text, scan_sec.text, cooldown.text, new_candle.active)
        Button:
            text: "Durdur"
            disabled: not root.running
            on_release:
                root.stop()

    Label:
        id: status
        text: root.status
        halign: "left"
        valign: "top"
        text_size: self.width, None

    ScrollView:
        Label:
            id: log
            text: root.log_text
            halign: "left"
            valign: "top"
            text_size: self.width, None
            size_hint_y: None
            height: max(self.texture_size[1], dp(200))
"""

class RootUI(BoxLayout):
    bot_token = StringProperty("")
    chat_id = StringProperty("")
    symbols = StringProperty("BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,AVAXUSDT,LINKUSDT,DOTUSDT,TRXUSDT,LTCUSDT,BCHUSDT,ETCUSDT,ATOMUSDT,OPUSDT,ARBUSDT,NEARUSDT,APTUSDT,FILUSDT,SUIUSDT,INJUSDT,TIAUSDT,RNDRUSDT,GRTUSDT,AAVEUSDT,RUNEUSDT,SNXUSDT,DYDXUSDT,UNIUSDT,PEPEUSDT,SHIBUSDT,ICPUSDT,SEIUSDT,LDOUSDT,FLOWUSDT,EGLDUSDT,THETAUSDT,MATICUSDT,WIFUSDT")
    min_ai_proba = StringProperty("0.65")
    scan_interval = StringProperty("60")
    cooldown_min = StringProperty("5")
    only_new_candle = BooleanProperty(True)

    running = BooleanProperty(False)
    status = StringProperty("Hazır. Token/ChatID girip Başlat'a bas.")
    log_text = StringProperty("")

    _engine = None
    _thread = None

    def set_default_symbols(self):
        self.symbols = self.symbols  # zaten dolu

    def copy(self, text):
        Clipboard.copy(text or "")

    def paste(self):
        try:
            return Clipboard.paste() or ""
        except Exception:
            return ""

    def _ui_log(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text = f"[{ts}] {line}\n" + self.log_text[:12000]

    def start(self, token, chat_id, symbols_csv, proba, scan_sec, cooldown_min, only_new_candle):
        token = (token or "").strip()
        chat_id = (chat_id or "").strip()
        if not token or not chat_id:
            self.status = "❌ Telegram token ve chat_id zorunlu."
            self._ui_log(self.status)
            return

        try:
            min_ai = float(proba)
            scan = int(float(scan_sec))
            cooldown = int(float(cooldown_min))
        except Exception:
            self.status = "❌ Ayar formatı yanlış (proba/scan/cooldown)."
            self._ui_log(self.status)
            return

        symbols = [s.strip().upper() for s in (symbols_csv or "").split(",") if s.strip()]
        if not symbols:
            self.status = "❌ Sembol listesi boş."
            self._ui_log(self.status)
            return

        cfg = RadarConfig(
            telegram_bot_token=token,
            telegram_chat_id=chat_id,
            symbols=symbols,
            min_ai_proba=min_ai,
            scan_interval_sec=max(30, scan),
            alert_cooldown_min=max(1, cooldown),
            only_on_new_5m_candle=bool(only_new_candle),
        )

        self._engine = RadarEngine(cfg, log_cb=lambda s: Clock.schedule_once(lambda *_: self._ui_log(s), 0))
        self.running = True
        self.status = "✅ Çalışıyor."
        self._ui_log("Bot başlatıldı.")

        self._thread = threading.Thread(target=self._engine.run_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._engine:
            self._engine.stop()
        self.running = False
        self.status = "⏹ Durduruldu."
        self._ui_log("Bot durduruldu.")

class AIRadarApp(App):
    def build(self):
        Builder.load_string(KV)
        return RootUI()

if __name__ == "__main__":
    AIRadarApp().run()
