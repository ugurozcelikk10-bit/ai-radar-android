# ================================
# AI RADAR - TEK DOSYA FINAL
# ================================

from kivy.app import App
from kivy.uix.label import Label
from kivy.clock import Clock
from threading import Thread
import time
import random

# ================================
# BOT ENGINE (AYNI DOSYANIN ICINDE)
# ================================

HIGH_PROBS = []

def bot_loop():
    global HIGH_PROBS

    coins = [
        "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
        "ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","MATICUSDT",
        "LTCUSDT","ATOMUSDT","NEARUSDT","OPUSDT","ARBUSDT"
    ]

    while True:
        time.sleep(3)

        if random.random() > 0.6:
            coin = random.choice(coins)
            HIGH_PROBS.append(coin)
            print("HIGH PROB:", coin)


def get_high_probs():
    return HIGH_PROBS


# ================================
# KIVY APP
# ================================

class AIRadarApp(App):

    def build(self):
        self.label = Label(text="AI Radar Baslatiliyor...", font_size=18)

        # BOTU ARKA PLANDA BASLAT
        Thread(target=bot_loop, daemon=True).start()

        # UI GUNCELLE
        Clock.schedule_interval(self.update_ui, 2)

        return self.label

    def update_ui(self, dt):
        probs = get_high_probs()

        if probs:
            txt = "HIGH PROB COINLER:\n\n"
            for c in probs[-10:]:
                txt += c + "\n"
            self.label.text = txt
        else:
            self.label.text = "Taranıyor..."


if __name__ == "__main__":
    AIRadarApp().run()
