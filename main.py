from kivy.app import App
from kivy.uix.label import Label

class AIRadar(App):
    def build(self):
        return Label(text="AI RADAR TEST CALISTI ✅", font_size="28sp")

if __name__ == "__main__":
    AIRadar().run()
