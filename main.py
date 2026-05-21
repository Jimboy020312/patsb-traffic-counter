"""
PATSB Traffic Counter
Kivy app — landscape, 2 junctions, crash recovery
"""

import json
import os

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle

Window.clearcolor = (0.10, 0.11, 0.14, 1)
Window.size = (1280, 720)  # PC preview only — ignored on Android

SAVE_FILE = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "traffic_save.json")

# (key, emoji icon, + button color)
VEHICLES = [
    ("CAR",  "🚗", (0.85, 0.20, 0.20, 1)),   # red
    ("MOTO", "🏍", (0.20, 0.72, 0.35, 1)),   # green
    ("LRY",  "🚛", (0.20, 0.47, 0.87, 1)),   # blue
    ("LLRY", "🚚", (0.93, 0.50, 0.15, 1)),   # orange
    ("BUS",  "🚌", (0.85, 0.75, 0.10, 1)),   # yellow
]

BTN_MINUS = (0.30, 0.32, 0.36, 1)  # grey — all minus buttons


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
    """
    Full-width row for one vehicle type across both junctions:
    [J1 +] [J1 count] [J1 -]  |gap|  [J2 -] [J2 count] [J2 +]
    """

    def __init__(self, key, icon, plus_color, j1_change, j2_change, **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint=(1, 1),
            spacing=0,
            padding=[0, 2, 0, 2],
            **kwargs
        )
        self.key = key
        self._j1 = 0
        self._j2 = 0
        self.j1_change = j1_change
        self.j2_change = j2_change

        # ── Junction 1 (left side) ──────────────────────────────
        # + far left edge
        self.j1_plus = flat_btn(icon, plus_color, font_size=30)
        self.j1_plus.size_hint = (0.14, 1)
        self.j1_plus.bind(on_release=self._j1_inc)

        # count
        self.j1_count = Label(
            text="0",
            font_size=34,
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(0.10, 1),
            halign='center',
            valign='middle',
        )
        self.j1_count.bind(size=lambda i, v: setattr(i, 'text_size', v))

        # - button
        self.j1_minus = flat_btn("−", BTN_MINUS, font_size=34)
        self.j1_minus.size_hint = (0.14, 1)
        self.j1_minus.bind(on_release=self._j1_dec)

        # ── Centre divider ──────────────────────────────────────
        divider = Label(text="", size_hint=(0.04, 1))
        with divider.canvas.before:
            Color(0.18, 0.20, 0.25, 1)
            self._div_rect = Rectangle(pos=divider.pos, size=divider.size)
        divider.bind(
            pos=lambda i, v: setattr(self._div_rect, 'pos', v),
            size=lambda i, v: setattr(self._div_rect, 'size', v),
        )

        # ── Junction 2 (right side, mirrored) ──────────────────
        # - button
        self.j2_minus = flat_btn("−", BTN_MINUS, font_size=34)
        self.j2_minus.size_hint = (0.14, 1)
        self.j2_minus.bind(on_release=self._j2_dec)

        # count
        self.j2_count = Label(
            text="0",
            font_size=34,
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(0.10, 1),
            halign='center',
            valign='middle',
        )
        self.j2_count.bind(size=lambda i, v: setattr(i, 'text_size', v))

        # + far right edge
        self.j2_plus = flat_btn(icon, plus_color, font_size=30)
        self.j2_plus.size_hint = (0.14, 1)
        self.j2_plus.bind(on_release=self._j2_inc)

        for w in [self.j1_plus, self.j1_count, self.j1_minus,
                  divider,
                  self.j2_minus, self.j2_count, self.j2_plus]:
            self.add_widget(w)

    # J1
    def _j1_inc(self, *a):
        self._j1 += 1
        self.j1_count.text = str(self._j1)
        self.j1_change()

    def _j1_dec(self, *a):
        if self._j1 > 0:
            self._j1 -= 1
            self.j1_count.text = str(self._j1)
            self.j1_change()

    # J2
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
            spacing=0,
            padding=[0, 0, 0, 0],
            **kwargs
        )

        # ── Header ─────────────────────────────────────────────
        header = BoxLayout(size_hint=(1, None), height=46)
        with header.canvas.before:
            Color(0.07, 0.08, 0.11, 1)
            self._hdr_rect = Rectangle(pos=header.pos, size=header.size)
        header.bind(
            pos=lambda i, v: setattr(self._hdr_rect, 'pos', v),
            size=lambda i, v: setattr(self._hdr_rect, 'size', v),
        )

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

        title = Label(
            text="PATSB Traffic Counter",
            font_size=17,
            bold=True,
            color=(0.70, 0.75, 0.85, 1),
            halign='center',
            valign='middle',
            size_hint=(0.30, 1),
        )
        title.bind(size=lambda i, v: setattr(i, 'text_size', v))

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
        header.add_widget(title)
        header.add_widget(self.j2_name)
        self.add_widget(header)

        # ── Vehicle rows ────────────────────────────────────────
        self.rows = {}
        for key, icon, color in VEHICLES:
            row = VehicleRow(key, icon, color, self._save, self._save)
            self.rows[key] = row
            self.add_widget(row)

        # ── Reset bar ───────────────────────────────────────────
        bottom = BoxLayout(size_hint=(1, None), height=54,
                           padding=[8, 4, 8, 6])
        reset_btn = flat_btn(
            "⟳   RESET ALL", (0.75, 0.20, 0.20, 1), font_size=18)
        reset_btn.bind(on_release=self._confirm_reset)
        bottom.add_widget(reset_btn)
        self.add_widget(bottom)

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
            halign='center',
            valign='middle',
            color=(1, 1, 1, 1),
            font_size=18,
            size_hint=(1, 1),
        ))
        btns = BoxLayout(orientation='horizontal', spacing=12,
                         size_hint=(1, None), height=70)
        cancel = flat_btn("Cancel",     (0.30, 0.32, 0.38, 1), font_size=18)
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
        Window.orientation = 'landscape'
        return RootLayout()


if __name__ == '__main__':
    TrafficCounterApp().run()
