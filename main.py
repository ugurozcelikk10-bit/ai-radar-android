from kivy.app import App
from kivy.uix.label import Label

class AppTest(App):
    def build(self):
        return Label(text="AI Radar OK")

AppTest().run()
