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

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic_save.json")

VEHICLES = [
    ("CAR",   "Car",         (0.20, 0.47, 0.87, 1)),
    ("MOTO",  "Motorcycle",  (0.93, 0.50, 0.15, 1)),
    ("LRY",   "Lorry",       (0.22, 0.72, 0.45, 1)),
    ("LLRY",  "Large Lorry", (0.87, 0.27, 0.27, 1)),
    ("BUS",   "Bus",         (0.65, 0.32, 0.87, 1)),
]


def flat_btn(text, bg, color=(1, 1, 1, 1), font_size=18, bold=True):
    return Button(
        text=text,
        font_size=font_size,
        bold=bold,
        color=color,
        background_normal='',
        background_color=bg,
    )


class VehicleRow(BoxLayout):
    def __init__(self, key, label, color, on_change, **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint=(1, 1),
            spacing=4,
            padding=[0, 2, 0, 2],
            **kwargs
        )
        self.key = key
        self.on_change = on_change
        self._count = 0

        # Minus — left edge, fills 25% width
        self.btn_minus = flat_btn("−", (0.22, 0.24, 0.30, 1), font_size=32)
        self.btn_minus.size_hint = (0.25, 1)
        self.btn_minus.bind(on_release=self._dec)

        # Middle section: chip + name + count
        middle = BoxLayout(orientation='horizontal', size_hint=(0.5, 1), spacing=4)

        chip = flat_btn(key, color, font_size=13, bold=True)
        chip.size_hint = (None, 1)
        chip.width = 64

        name = Label(
            text=label,
            font_size=15,
            color=(0.85, 0.87, 0.90, 1),
            halign='center',
            valign='middle',
            size_hint=(1, 1),
        )
        name.bind(size=lambda i, v: setattr(i, 'text_size', v))

        self.lbl_count = Label(
            text="0",
            font_size=32,
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, 1),
            width=72,
        )

        middle.add_widget(chip)
        middle.add_widget(name)
        middle.add_widget(self.lbl_count)

        # Plus — right edge, fills 25% width
        self.btn_plus = flat_btn("+", color, font_size=32)
        self.btn_plus.size_hint = (0.25, 1)
        self.btn_plus.bind(on_release=self._inc)

        self.add_widget(self.btn_minus)
        self.add_widget(middle)
        self.add_widget(self.btn_plus)

    def _inc(self, *a):
        self._count += 1
        self.lbl_count.text = str(self._count)
        self.on_change()

    def _dec(self, *a):
        if self._count > 0:
            self._count -= 1
            self.lbl_count.text = str(self._count)
            self.on_change()

    @property
    def count(self):
        return self._count

    @count.setter
    def count(self, v):
        self._count = max(0, int(v))
        self.lbl_count.text = str(self._count)

    def reset(self):
        self.count = 0


class JunctionPanel(BoxLayout):
    def __init__(self, default_name, bg_color, on_change, **kwargs):
        super().__init__(
            orientation='vertical',
            spacing=0,
            padding=[0, 0, 0, 0],
            **kwargs
        )
        self.on_change = on_change

        with self.canvas.before:
            Color(*bg_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

        # Junction name
        self.name_input = TextInput(
            text=default_name,
            font_size=20,
            foreground_color=(1, 1, 1, 1),
            background_color=(0.12, 0.14, 0.18, 1),
            cursor_color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=48,
            multiline=False,
            halign='center',
        )
        self.name_input.bind(text=lambda *a: self.on_change())
        self.add_widget(self.name_input)

        # Vehicle rows
        self.rows = {}
        for key, label, color in VEHICLES:
            row = VehicleRow(key, label, color, on_change=self.on_change)
            self.rows[key] = row
            self.add_widget(row)

    def _upd(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def get_state(self):
        return {
            'name': self.name_input.text,
            'counts': {k: r.count for k, r in self.rows.items()},
        }

    def set_state(self, state):
        if 'name' in state:
            self.name_input.text = state['name']
        for k, v in state.get('counts', {}).items():
            if k in self.rows:
                self.rows[k].count = v

    def reset(self):
        for row in self.rows.values():
            row.reset()
        self.on_change()


class RootLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', spacing=0, padding=[0, 0, 0, 0], **kwargs)

        # Header
        header = BoxLayout(size_hint=(1, None), height=44)
        with header.canvas.before:
            Color(0.07, 0.08, 0.11, 1)
            self._hdr_rect = Rectangle(pos=header.pos, size=header.size)
        header.bind(
            pos=lambda i, v: setattr(self._hdr_rect, 'pos', v),
            size=lambda i, v: setattr(self._hdr_rect, 'size', v),
        )
        title = Label(
            text="PATSB Traffic Counter",
            font_size=18,
            bold=True,
            color=(0.70, 0.75, 0.85, 1),
            halign='center',
            valign='middle',
        )
        title.bind(size=lambda i, v: setattr(i, 'text_size', v))
        header.add_widget(title)
        self.add_widget(header)

        # Two junction panels
        panels = BoxLayout(
            orientation='horizontal',
            spacing=4,
            padding=[4, 4, 4, 0],
            size_hint=(1, 1),
        )
        self.j1 = JunctionPanel("Junction 1", (0.08, 0.13, 0.22, 1), self._save)
        self.j2 = JunctionPanel("Junction 2", (0.08, 0.18, 0.15, 1), self._save)
        panels.add_widget(self.j1)
        panels.add_widget(self.j2)
        self.add_widget(panels)

        # Reset bar
        bottom = BoxLayout(size_hint=(1, None), height=56, padding=[8, 4, 8, 6])
        reset_btn = flat_btn("⟳   RESET ALL", (0.75, 0.20, 0.20, 1), font_size=18)
        reset_btn.bind(on_release=self._confirm_reset)
        bottom.add_widget(reset_btn)
        self.add_widget(bottom)

        self._load()

    def _save(self, *a):
        try:
            with open(SAVE_FILE, 'w') as f:
                json.dump({'j1': self.j1.get_state(), 'j2': self.j2.get_state()}, f)
        except Exception as e:
            print("Save error:", e)

    def _load(self):
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE, 'r') as f:
                    data = json.load(f)
                self.j1.set_state(data.get('j1', {}))
                self.j2.set_state(data.get('j2', {}))
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
        btns = BoxLayout(
            orientation='horizontal',
            spacing=12,
            size_hint=(1, None),
            height=70,
        )
        cancel = flat_btn("Cancel", (0.30, 0.32, 0.38, 1), font_size=18)
        confirm = flat_btn("Yes, Reset", (0.75, 0.20, 0.20, 1), font_size=18)
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)

        # Use size_hint so popup fills screen on any phone size
        popup = Popup(
            title='Confirm Reset',
            title_size=20,
            content=content,
            size_hint=(0.85, 0.5),
            background_color=(0.14, 0.15, 0.20, 1),
            title_color=(1, 1, 1, 1),
            separator_color=(0.25, 0.27, 0.32, 1),
        )
        cancel.bind(on_release=popup.dismiss)
        confirm.bind(on_release=lambda *a: (self._do_reset(), popup.dismiss()))
        popup.open()

    def _do_reset(self):
        self.j1.reset()
        self.j2.reset()
        self._save()


class TrafficCounterApp(App):
    def build(self):
        Window.orientation = 'landscape'
        return RootLayout()


if __name__ == '__main__':
    TrafficCounterApp().run()
