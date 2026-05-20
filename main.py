"""
Traffic Counter — 2 Junction Landscape App
Works on Pydroid 3 (Android). Requires Kivy installed in Pydroid 3.
Install Kivy in Pydroid 3: pip install kivy
"""

import json
import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock

# Force landscape
Window.orientation = 'landscape'

# ── Colours ──────────────────────────────────────────────────────────────────
BG         = (0.10, 0.11, 0.14, 1)   # near-black background
COL_LEFT   = (0.08, 0.13, 0.22, 1)   # junction left panel
COL_RIGHT  = (0.08, 0.18, 0.15, 1)   # junction right panel
DIVIDER    = (0.20, 0.22, 0.26, 1)

VEHICLE_COLORS = {
    "CAR":   (0.20, 0.47, 0.87, 1),   # blue
    "MOTO":  (0.93, 0.50, 0.15, 1),   # orange
    "LRY":   (0.22, 0.72, 0.45, 1),   # green
    "L-LRY": (0.87, 0.27, 0.27, 1),   # red
    "BUS":   (0.65, 0.32, 0.87, 1),   # purple
}

VEHICLE_LABELS = {
    "CAR":   "Car",
    "MOTO":  "Motorcycle",
    "LRY":   "Lorry",
    "L-LRY": "Large Lorry",
    "BUS":   "Bus",
}

VEHICLE_ORDER = ["CAR", "MOTO", "LRY", "L-LRY", "BUS"]

SAVE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "traffic_save.json"
)

# ── Helpers ───────────────────────────────────────────────────────────────────
def rgba_to_hex(r, g, b, a=1):
    return "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))

def make_color_btn(text, bg_rgba, text_color=(1,1,1,1), font_size=18, bold=True):
    btn = Button(
        text=text,
        font_size=font_size,
        bold=bold,
        background_normal='',
        background_color=bg_rgba,
        color=text_color,
    )
    return btn

# ── Vehicle Row ───────────────────────────────────────────────────────────────
class VehicleRow(BoxLayout):
    def __init__(self, key, on_change, **kwargs):
        super().__init__(orientation='horizontal', spacing=4,
                         size_hint=(1, None), height=54, **kwargs)
        self.key = key
        self.on_change = on_change
        self._count = 0
        color = VEHICLE_COLORS[key]

        # Label chip
        lbl = Label(
            text=key,
            font_size=13,
            bold=True,
            size_hint=(None, 1),
            width=58,
            color=(1,1,1,1),
        )
        with lbl.canvas.before:
            Color(*color)
            self._chip_rect = RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[6])
        lbl.bind(pos=self._update_chip, size=self._update_chip)

        # Full name
        name_lbl = Label(
            text=VEHICLE_LABELS[key],
            font_size=13,
            size_hint=(1, 1),
            color=(0.80, 0.83, 0.88, 1),
            halign='left',
            valign='middle',
        )
        name_lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))

        # Minus
        self.btn_minus = make_color_btn("−", (0.25, 0.27, 0.32, 1),
                                        font_size=22, bold=True)
        self.btn_minus.size_hint = (None, 1)
        self.btn_minus.width = 52
        self.btn_minus.bind(on_release=self._decrement)

        # Count
        self.count_lbl = Label(
            text="0",
            font_size=22,
            bold=True,
            size_hint=(None, 1),
            width=58,
            color=(1,1,1,1),
        )

        # Plus
        self.btn_plus = make_color_btn("+", color, font_size=22, bold=True)
        self.btn_plus.size_hint = (None, 1)
        self.btn_plus.width = 52
        self.btn_plus.bind(on_release=self._increment)

        self.add_widget(lbl)
        self.add_widget(name_lbl)
        self.add_widget(self.btn_minus)
        self.add_widget(self.count_lbl)
        self.add_widget(self.btn_plus)

    def _update_chip(self, inst, val):
        self._chip_rect.pos  = inst.pos
        self._chip_rect.size = inst.size

    def _increment(self, *a):
        self._count += 1
        self._refresh()
        self.on_change()

    def _decrement(self, *a):
        if self._count > 0:
            self._count -= 1
            self._refresh()
            self.on_change()

    def _refresh(self):
        self.count_lbl.text = str(self._count)

    @property
    def count(self):
        return self._count

    @count.setter
    def count(self, val):
        self._count = max(0, int(val))
        self._refresh()

    def reset(self):
        self._count = 0
        self._refresh()

# ── Junction Panel ────────────────────────────────────────────────────────────
class JunctionPanel(BoxLayout):
    def __init__(self, default_name, panel_color, on_change, **kwargs):
        super().__init__(orientation='vertical', spacing=6, padding=[10,10,10,10], **kwargs)
        self.on_change = on_change

        with self.canvas.before:
            Color(*panel_color)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        # Editable junction name
        self.name_input = TextInput(
            text=default_name,
            font_size=18,
            bold=True,
            foreground_color=(1,1,1,1),
            background_color=(0,0,0,0),
            cursor_color=(1,1,1,1),
            size_hint=(1, None),
            height=40,
            multiline=False,
            halign='center',
        )
        self.name_input.bind(text=lambda *a: self.on_change())
        self.add_widget(self.name_input)

        # Divider
        div = Label(size_hint=(1, None), height=1)
        with div.canvas:
            Color(*DIVIDER)
            RoundedRectangle(pos=div.pos, size=div.size)
        div.bind(pos=lambda i,v: setattr(i,'canvas', i.canvas),
                 size=lambda i,v: setattr(i,'canvas', i.canvas))
        self.add_widget(div)

        # Vehicle rows
        self.rows = {}
        for key in VEHICLE_ORDER:
            row = VehicleRow(key, on_change=self.on_change)
            self.rows[key] = row
            self.add_widget(row)

        self.add_widget(Label(size_hint=(1,1)))  # spacer

    def _upd_bg(self, *a):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def get_state(self):
        return {
            'name':   self.name_input.text,
            'counts': {k: r.count for k, r in self.rows.items()}
        }

    def set_state(self, state):
        self.name_input.text = state.get('name', self.name_input.text)
        for k, v in state.get('counts', {}).items():
            if k in self.rows:
                self.rows[k].count = v

    def reset(self):
        for row in self.rows.values():
            row.reset()
        self.on_change()

# ── Root Layout ───────────────────────────────────────────────────────────────
class TrafficRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', spacing=0, **kwargs)

        with self.canvas.before:
            Color(*BG)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self._bg, 'pos', self.pos),
                  size=lambda *a: setattr(self._bg, 'size', self.size))

        # Header bar
        header = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=38,
            padding=[12, 4, 12, 4],
        )
        title = Label(
            text="TRAFFIC COUNTER",
            font_size=15,
            bold=True,
            color=(0.60, 0.65, 0.75, 1),
            halign='left',
        )
        title.bind(size=lambda i, v: setattr(i, 'text_size', v))
        header.add_widget(title)
        self.add_widget(header)

        # Two junction panels
        panels_row = BoxLayout(
            orientation='horizontal',
            spacing=10,
            padding=[10, 0, 10, 6],
            size_hint=(1, 1),
        )

        self.j1 = JunctionPanel(
            default_name="Junction 1",
            panel_color=COL_LEFT,
            on_change=self._save,
        )
        self.j2 = JunctionPanel(
            default_name="Junction 2",
            panel_color=COL_RIGHT,
            on_change=self._save,
        )
        panels_row.add_widget(self.j1)
        panels_row.add_widget(self.j2)
        self.add_widget(panels_row)

        # Bottom bar — Reset
        bottom = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=46,
            padding=[10, 4, 10, 6],
            spacing=10,
        )

        reset_btn = make_color_btn(
            "⟳  RESET ALL",
            (0.75, 0.22, 0.22, 1),
            font_size=15,
            bold=True,
        )
        reset_btn.bind(on_release=self._confirm_reset)
        bottom.add_widget(reset_btn)
        self.add_widget(bottom)

        # Load saved state
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────
    def _save(self, *a):
        try:
            data = {
                'j1': self.j1.get_state(),
                'j2': self.j2.get_state(),
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
                self.j1.set_state(data.get('j1', {}))
                self.j2.set_state(data.get('j2', {}))
        except Exception as e:
            print("Load error:", e)

    # ── Reset with confirmation ───────────────────────────────────────────────
    def _confirm_reset(self, *a):
        content = BoxLayout(orientation='vertical', spacing=12, padding=16)
        content.add_widget(Label(
            text="Reset ALL counts for both junctions?\nThis cannot be undone.",
            halign='center',
            color=(1,1,1,1),
            font_size=15,
        ))
        btn_row = BoxLayout(orientation='horizontal', spacing=10,
                            size_hint=(1, None), height=44)

        cancel_btn = make_color_btn("Cancel", (0.30, 0.32, 0.38, 1), font_size=14)
        confirm_btn = make_color_btn("Yes, Reset", (0.75, 0.22, 0.22, 1), font_size=14)

        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)
        content.add_widget(btn_row)

        popup = Popup(
            title='Confirm Reset',
            content=content,
            size_hint=(None, None),
            size=(380, 200),
            background_color=(0.14, 0.15, 0.19, 1),
            title_color=(1,1,1,1),
            separator_color=(0.25, 0.27, 0.32, 1),
        )
        cancel_btn.bind(on_release=popup.dismiss)
        confirm_btn.bind(on_release=lambda *a: (self._do_reset(), popup.dismiss()))
        popup.open()

    def _do_reset(self):
        self.j1.reset()
        self.j2.reset()
        self._save()

# ── App ───────────────────────────────────────────────────────────────────────
class TrafficCounterApp(App):
    def build(self):
        Window.clearcolor = BG
        return TrafficRoot()

if __name__ == '__main__':
    TrafficCounterApp().run()
