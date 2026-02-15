from kivy.app import App
from kivy.uix.label import Label

class AppTest(App):
    def build(self):
        return Label(
            text="AI RADAR TEST OK ✅",
            font_size="32sp"
        )

if __name__ == "__main__":
    AppTest().run()
