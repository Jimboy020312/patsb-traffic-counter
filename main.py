"""
PATSB Traffic Counter
Kivy app — landscape, 2 junctions, crash recovery
"""

import json
import os

# Fix DPI scaling BEFORE importing anything else from kivy
from kivy.config import Config
Config.set('graphics', 'resizable', '0')
Config.set('graphics', 'show_cursor', '0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.utils import platform

Window.clearcolor = (0.10, 0.11, 0.14, 1)

if platform != 'android':
    Window.size = (1280, 720)  # PC preview only

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic_save.json")

VEHICLES = [
    ("CAR",  "CAR",     (0.85, 0.20, 0.20, 1)),
    ("MOTO", "MOTO",    (0.20, 0.72, 0.35, 1)),
    ("LRY",  "LORRY",   (0.20, 0.47, 0.87, 1)),
    ("LLRY", "L.LORRY", (0.93, 0.50, 0.15, 1)),
    ("BUS",  "BUS",     (0.85, 0.75, 0.10, 1)),
]

BTN_MINUS = (0.30, 0.32, 0.36, 1)


def flat_btn(text, bg, color=(1, 1, 1, 1), font_size=22, bold=True):
    return Button(
        text=text,
        font_size=font_size,
        bold=bold,
        color=color,
        background_normal='',
        background_color=bg,
    )


class VehicleRow(BoxLayout):
    def __init__(self, key, label, plus_color, j1_change, j2_change, **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint=(1, 1),
            spacing=2,
            padding=[0, 1, 0, 1],
            **kwargs
        )
        self.key = key
        self._j1 = 0
        self._j2 = 0
        self.j1_change = j1_change
        self.j2_change = j2_change

        self.j1_plus = flat_btn(label, plus_color, font_size=18)
        self.j1_plus.size_hint = (0.14, 1)
        self.j1_plus.bind(on_release=self._j1_inc)

        self.j1_count = Label(
            text="0", font_size=34, bold=True,
            color=(1, 1, 1, 1), size_hint=(0.10, 1),
            halign='center', valign='middle',
        )
        self.j1_count.bind(size=lambda i, v: setattr(i, 'text_size', v))

        self.j1_minus = flat_btn("-", BTN_MINUS, font_size=34)
        self.j1_minus.size_hint = (0.14, 1)
        self.j1_minus.bind(on_release=self._j1_dec)

        divider = Button(
            text='',
            background_normal='',
            background_color=(0.18, 0.20, 0.25, 1),
            size_hint=(0.04, 1),
        )

        self.j2_minus = flat_btn("-", BTN_MINUS, font_size=34)
        self.j2_minus.size_hint = (0.14, 1)
        self.j2_minus.bind(on_release=self._j2_dec)

        self.j2_count = Label(
            text="0", font_size=34, bold=True,
            color=(1, 1, 1, 1), size_hint=(0.10, 1),
            halign='center', valign='middle',
        )
        self.j2_count.bind(size=lambda i, v: setattr(i, 'text_size', v))

        self.j2_plus = flat_btn(label, plus_color, font_size=18)
        self.j2_plus.size_hint = (0.14, 1)
        self.j2_plus.bind(on_release=self._j2_inc)

        for w in [self.j1_plus, self.j1_count, self.j1_minus,
                  divider,
                  self.j2_minus, self.j2_count, self.j2_plus]:
            self.add_widget(w)

    def _j1_inc(self, *a):
        self._j1 += 1
        self.j1_count.text = str(self._j1)
        self.j1_change()

    def _j1_dec(self, *a):
        if self._j1 > 0:
            self._j1 -= 1
            self.j1_count.text = str(self._j1)
            self.j1_change()

    def _j2_inc(self, *a):
        self._j2 += 1
        self.j2_count.text = str(self._j2)
        self.j2_change()

    def _j2_dec(self, *a):
        if self._j2 > 0:
            self._j2 -= 1
            self.j2_count.text = str(self._j2)
            self.j2_change()

    def get_j1(self): return self._j1
    def get_j2(self): return self._j2

    def set_j1(self, v):
        self._j1 = max(0, int(v))
        self.j1_count.text = str(self._j1)

    def set_j2(self, v):
        self._j2 = max(0, int(v))
        self.j2_count.text = str(self._j2)

    def reset_j1(self):
        self._j1 = 0
        self.j1_count.text = "0"

    def reset_j2(self):
        self._j2 = 0
        self.j2_count.text = "0"


class RootLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation='vertical',
            spacing=2,
            padding=[0, 0, 0, 0],
            **kwargs
        )

        header = BoxLayout(size_hint=(1, None), height=46, spacing=2)

        self.j1_name = TextInput(
            text="Junction 1",
            font_size=17,
            foreground_color=(1, 1, 1, 1),
            background_color=(0.10, 0.13, 0.20, 1),
            cursor_color=(1, 1, 1, 1),
            size_hint=(0.35, 1),
            multiline=False,
            halign='center',
        )
        self.j1_name.bind(text=lambda *a: self._save())

        title_btn = Button(
            text="PATSB Traffic Counter",
            font_size=16,
            bold=True,
            color=(0.70, 0.75, 0.85, 1),
            background_normal='',
            background_color=(0.07, 0.08, 0.11, 1),
            size_hint=(0.30, 1),
        )

        self.j2_name = TextInput(
            text="Junction 2",
            font_size=17,
            foreground_color=(1, 1, 1, 1),
            background_color=(0.08, 0.16, 0.13, 1),
            cursor_color=(1, 1, 1, 1),
            size_hint=(0.35, 1),
            multiline=False,
            halign='center',
        )
        self.j2_name.bind(text=lambda *a: self._save())

        header.add_widget(self.j1_name)
        header.add_widget(title_btn)
        header.add_widget(self.j2_name)
        self.add_widget(header)

        self.rows = {}
        for key, label, color in VEHICLES:
            row = VehicleRow(key, label, color, self._save, self._save)
            self.rows[key] = row
            self.add_widget(row)

        reset_btn = flat_btn("RESET ALL", (0.75, 0.20, 0.20, 1), font_size=18)
        reset_btn.size_hint = (1, None)
        reset_btn.height = 54
        reset_btn.bind(on_release=self._confirm_reset)
        self.add_widget(reset_btn)

        self._load()

    def _save(self, *a):
        try:
            data = {
                'j1_name': self.j1_name.text,
                'j2_name': self.j2_name.text,
                'counts': {k: {'j1': r.get_j1(), 'j2': r.get_j2()}
                           for k, r in self.rows.items()}
            }
            with open(SAVE_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print("Save error:", e)

    def _load(self):
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE, 'r') as f:
                    data = json.load(f)
                self.j1_name.text = data.get('j1_name', 'Junction 1')
                self.j2_name.text = data.get('j2_name', 'Junction 2')
                for k, v in data.get('counts', {}).items():
                    if k in self.rows:
                        self.rows[k].set_j1(v.get('j1', 0))
                        self.rows[k].set_j2(v.get('j2', 0))
        except Exception as e:
            print("Load error:", e)

    def _confirm_reset(self, *a):
        content = BoxLayout(orientation='vertical', spacing=16, padding=24)
        content.add_widget(Label(
            text="Reset ALL counts for both junctions?\nThis cannot be undone.",
            halign='center', valign='middle',
            color=(1, 1, 1, 1), font_size=18,
            size_hint=(1, 1),
        ))
        btns = BoxLayout(orientation='horizontal', spacing=12,
                         size_hint=(1, None), height=70)
        cancel  = flat_btn("Cancel",     (0.30, 0.32, 0.38, 1), font_size=18)
        confirm = flat_btn("Yes, Reset", (0.75, 0.20, 0.20, 1), font_size=18)
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)

        popup = Popup(
            title='Confirm Reset',
            title_size=20,
            content=content,
            size_hint=(0.85, 0.55),
            background_color=(0.14, 0.15, 0.20, 1),
            title_color=(1, 1, 1, 1),
            separator_color=(0.25, 0.27, 0.32, 1),
        )
        cancel.bind(on_release=popup.dismiss)
        confirm.bind(on_release=lambda *a: (self._do_reset(), popup.dismiss()))
        popup.open()

    def _do_reset(self):
        for row in self.rows.values():
            row.reset_j1()
            row.reset_j2()
        self._save()


class TrafficCounterApp(App):
    def build(self):
        Window.fullscreen = 'auto'
        Window.orientation = 'landscape'
        return RootLayout()

    def on_start(self):
        # Force window to match actual screen size on Android
        if platform == 'android':
            from android.runnable import run_on_ui_thread  # noqa
            Window.update_viewport()


if __name__ == '__main__':
    TrafficCounterApp().run()
