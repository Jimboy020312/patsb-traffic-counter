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

Window.clearcolor = (0.10, 0.11, 0.14, 1)

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic_save.json")

VEHICLES = [
    ("CAR",   "Car",         (0.20, 0.47, 0.87, 1)),
    ("MOTO",  "Motorcycle",  (0.93, 0.50, 0.15, 1)),
    ("LRY",   "Lorry",       (0.22, 0.72, 0.45, 1)),
    ("LLRY",  "Large Lorry", (0.87, 0.27, 0.27, 1)),
    ("BUS",   "Bus",         (0.65, 0.32, 0.87, 1)),
]


def flat_btn(text, bg, color=(1, 1, 1, 1), font_size=16, bold=True):
    b = Button(
        text=text,
        font_size=font_size,
        bold=bold,
        color=color,
        background_normal='',
        background_color=bg,
    )
    return b


class VehicleRow(BoxLayout):
    def __init__(self, key, label, color, on_change, **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint=(1, None),
            height=52,
            spacing=4,
            padding=[2, 2, 2, 2],
            **kwargs
        )
        self.key = key
        self.on_change = on_change
        self._count = 0

        # Coloured label chip
        chip = flat_btn(key, color, font_size=12, bold=True)
        chip.size_hint = (None, 1)
        chip.width = 56

        # Full name
        name = Label(
            text=label,
            font_size=13,
            color=(0.85, 0.87, 0.90, 1),
            halign='left',
            valign='middle',
            size_hint=(1, 1),
        )
        name.bind(size=lambda i, v: setattr(i, 'text_size', v))

        # Minus button
        self.btn_minus = flat_btn("−", (0.25, 0.27, 0.32, 1), font_size=22)
        self.btn_minus.size_hint = (None, 1)
        self.btn_minus.width = 52
        self.btn_minus.bind(on_release=self._dec)

        # Count display
        self.lbl_count = Label(
            text="0",
            font_size=22,
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, 1),
            width=58,
        )

        # Plus button
        self.btn_plus = flat_btn("+", color, font_size=22)
        self.btn_plus.size_hint = (None, 1)
        self.btn_plus.width = 52
        self.btn_plus.bind(on_release=self._inc)

        self.add_widget(chip)
        self.add_widget(name)
        self.add_widget(self.btn_minus)
        self.add_widget(self.lbl_count)
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
            spacing=4,
            padding=[8, 8, 8, 8],
            **kwargs
        )
        self.on_change = on_change
        self.background_color = bg_color

        # We use a plain background button trick for color
        with self.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*bg_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

        # Junction name
        self.name_input = TextInput(
            text=default_name,
            font_size=16,
            bold=True,
            foreground_color=(1, 1, 1, 1),
            background_color=(0.15, 0.17, 0.21, 1),
            cursor_color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=38,
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

        self.add_widget(Label(size_hint=(1, 1)))  # spacer

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
        super().__init__(orientation='vertical', spacing=0, **kwargs)

        # Header
        header = BoxLayout(
            size_hint=(1, None), height=36,
            padding=[12, 4, 12, 4],
        )
        title = Label(
            text="PATSB TRAFFIC COUNTER",
            font_size=14,
            bold=True,
            color=(0.55, 0.60, 0.70, 1),
            halign='left',
            valign='middle',
        )
        title.bind(size=lambda i, v: setattr(i, 'text_size', v))
        header.add_widget(title)
        self.add_widget(header)

        # Two junction panels
        panels = BoxLayout(
            orientation='horizontal',
            spacing=8,
            padding=[8, 0, 8, 4],
            size_hint=(1, 1),
        )
        self.j1 = JunctionPanel("Junction 1", (0.08, 0.13, 0.22, 1), self._save)
        self.j2 = JunctionPanel("Junction 2", (0.08, 0.18, 0.15, 1), self._save)
        panels.add_widget(self.j1)
        panels.add_widget(self.j2)
        self.add_widget(panels)

        # Reset button
        bottom = BoxLayout(size_hint=(1, None), height=48, padding=[8, 4, 8, 6])
        reset_btn = flat_btn("⟳  RESET ALL", (0.75, 0.20, 0.20, 1), font_size=15)
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
        content = BoxLayout(orientation='vertical', spacing=10, padding=16)
        content.add_widget(Label(
            text="Reset ALL counts for both junctions?\nThis cannot be undone.",
            halign='center',
            color=(1, 1, 1, 1),
            font_size=14,
        ))
        btns = BoxLayout(orientation='horizontal', spacing=8,
                         size_hint=(1, None), height=44)
        cancel = flat_btn("Cancel", (0.30, 0.32, 0.38, 1), font_size=14)
        confirm = flat_btn("Yes, Reset", (0.75, 0.20, 0.20, 1), font_size=14)
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)

        popup = Popup(
            title='Confirm Reset',
            content=content,
            size_hint=(None, None),
            size=(360, 190),
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
