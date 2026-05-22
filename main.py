"""
PATSB Traffic Counter
Kivy — rainbow arc clusters, circular buttons, ML-style spacing
"""

from kivy.graphics import Color, Ellipse, PushMatrix, PopMatrix
from kivy.utils import platform
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.app import App
import json
import os
import math

from kivy.config import Config
Config.set('graphics', 'resizable', '0')
Config.set('graphics', 'show_cursor', '0')


Window.clearcolor = (0.08, 0.09, 0.12, 1)
if platform != 'android':
    Window.size = (1280, 720)

SAVE_FILE = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "traffic_save.json")

VEHICLES = [
    ("CAR",  "C",  (0.85, 0.20, 0.20, 1)),
    ("MOTO", "M",  (0.20, 0.72, 0.35, 1)),
    ("LRY",  "L",  (0.20, 0.47, 0.87, 1)),
    ("LLRY", "LL", (0.93, 0.50, 0.15, 1)),
    ("BUS",  "B",  (0.85, 0.75, 0.10, 1)),
]
VEHICLE_MAP = {v[0]: v for v in VEHICLES}


class CircleButton(Button):
    """A button that draws as a filled circle."""

    def __init__(self, circle_color, **kwargs):
        super().__init__(
            background_normal='',
            background_color=(0, 0, 0, 0),  # transparent — we draw our own
            **kwargs
        )
        self.circle_color = circle_color
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.circle_color)
            Ellipse(pos=self.pos, size=self.size)


def flat_btn(text, bg, color=(1, 1, 1, 1), font_size=22, bold=True):
    return Button(
        text=text, font_size=font_size, bold=bold,
        color=color, background_normal='', background_color=bg,
    )


class JunctionSummary(BoxLayout):
    def __init__(self, on_minus, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('spacing', 6)
        kwargs.setdefault('padding', [8, 4, 8, 4])
        super().__init__(**kwargs)
        self.on_minus = on_minus
        self.counts = {k: 0 for k, *_ in VEHICLES}
        self.chips = {}
        for key, short, color in VEHICLES:
            btn = Button(
                text=f"{short}:0", font_size=18, bold=True,
                color=(1, 1, 1, 1), background_normal='',
                background_color=color, size_hint=(1, 1),
            )
            btn.bind(on_release=lambda b, k=key: self._minus(k))
            self.chips[key] = (btn, short)
            self.add_widget(btn)

    def _minus(self, key):
        if self.counts[key] > 0:
            self.counts[key] -= 1
            self._refresh(key)
            self.on_minus()

    def _refresh(self, key):
        btn, short = self.chips[key]
        btn.text = f"{short}:{self.counts[key]}"

    def increment(self, key):
        self.counts[key] += 1
        self._refresh(key)

    def get_counts(self): return dict(self.counts)

    def set_counts(self, data):
        for k, v in data.items():
            if k in self.counts:
                self.counts[k] = max(0, int(v))
                self._refresh(k)

    def reset(self):
        for key in self.counts:
            self.counts[key] = 0
            self._refresh(key)


class RainbowCluster(FloatLayout):
    """
    3 rainbow rings from bottom corner, ML-style circular buttons.

    Ring 1: CAR   — closest, 45 deg
    Ring 2: MOTO (65 deg), LRY (25 deg)
    Ring 3: BUS  (78 deg), LLRY (12 deg)

    Radii chosen so buttons almost touch (gap ~ 6px).
    """
    BTN_SIZE = 108  # diameter

    LEFT_POSITIONS = [
        ("CAR",  45, 0.26),   # (key, angle, radius_fraction)
        ("MOTO", 65, 0.48),
        ("LRY",  25, 0.48),
        ("BUS",  78, 0.70),
        ("LLRY", 12, 0.70),
    ]

    def __init__(self, on_tap, corner, **kwargs):
        super().__init__(**kwargs)
        self.on_tap = on_tap
        self.corner = corner
        self._btns = []
        self.bind(size=self._place, pos=self._place)

        for key, angle, radius in self.LEFT_POSITIONS:
            _, short, color = VEHICLE_MAP[key]
            btn = CircleButton(
                circle_color=color,
                text=short,
                font_size=28,
                bold=True,
                color=(1, 1, 1, 1),
            )
            btn.size_hint = (None, None)
            btn.size = (self.BTN_SIZE, self.BTN_SIZE)
            btn.bind(on_release=lambda b, k=key: self.on_tap(k))
            self._btns.append((key, angle, radius, btn))
            self.add_widget(btn)

    def _place(self, *a):
        w, h = self.size
        ref = min(w, h)

        for key, angle_deg, radius_frac, btn in self._btns:
            r = radius_frac * ref
            rad = math.radians(angle_deg)
            dx = r * math.cos(rad)
            dy = r * math.sin(rad)

            if self.corner == 'left':
                bx = self.x + dx - self.BTN_SIZE / 2
                by = self.y + dy - self.BTN_SIZE / 2
            else:
                bx = self.x + w - dx - self.BTN_SIZE / 2
                by = self.y + dy - self.BTN_SIZE / 2

            btn.pos = (bx, by)


class RootLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation='vertical', spacing=0, padding=[0, 0, 0, 0], **kwargs
        )

        # ── Top bar ────────────────────────────────────────────
        top = BoxLayout(size_hint=(1, None), height=62,
                        spacing=6, padding=[6, 4, 6, 4])
        self.j1_summary = JunctionSummary(
            on_minus=self._save, size_hint=(0.42, 1))
        reset_btn = flat_btn("RESET ALL", (0.75, 0.20, 0.20, 1), font_size=15)
        reset_btn.size_hint = (0.16, 1)
        reset_btn.bind(on_release=self._confirm_reset)
        self.j2_summary = JunctionSummary(
            on_minus=self._save, size_hint=(0.42, 1))
        top.add_widget(self.j1_summary)
        top.add_widget(reset_btn)
        top.add_widget(self.j2_summary)
        self.add_widget(top)

        # ── Main ───────────────────────────────────────────────
        main = FloatLayout(size_hint=(1, 1))
        self.j1_cluster = RainbowCluster(
            on_tap=self._j1_tap, corner='left',
            size_hint=(0.48, 1), pos_hint={'x': 0, 'y': 0},
        )
        self.j2_cluster = RainbowCluster(
            on_tap=self._j2_tap, corner='right',
            size_hint=(0.48, 1), pos_hint={'right': 1, 'y': 0},
        )
        main.add_widget(self.j1_cluster)
        main.add_widget(self.j2_cluster)
        self.add_widget(main)

        self._load()

    def _j1_tap(self, key):
        self.j1_summary.increment(key)
        self._save()

    def _j2_tap(self, key):
        self.j2_summary.increment(key)
        self._save()

    def _save(self, *a):
        try:
            with open(SAVE_FILE, 'w') as f:
                json.dump({
                    'j1': self.j1_summary.get_counts(),
                    'j2': self.j2_summary.get_counts(),
                }, f)
        except Exception as e:
            print("Save error:", e)

    def _load(self):
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE, 'r') as f:
                    data = json.load(f)
                self.j1_summary.set_counts(data.get('j1', {}))
                self.j2_summary.set_counts(data.get('j2', {}))
        except Exception as e:
            print("Load error:", e)

    def _confirm_reset(self, *a):
        content = BoxLayout(orientation='vertical', spacing=16, padding=24)
        content.add_widget(Label(
            text="Reset ALL counts for both junctions?\nThis cannot be undone.",
            halign='center', valign='middle', color=(1, 1, 1, 1),
            font_size=18, size_hint=(1, 1),
        ))
        btns = BoxLayout(orientation='horizontal', spacing=12,
                         size_hint=(1, None), height=70)
        cancel = flat_btn("Cancel",     (0.30, 0.32, 0.38, 1), font_size=18)
        confirm = flat_btn("Yes, Reset", (0.75, 0.20, 0.20, 1), font_size=18)
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)
        popup = Popup(
            title='Confirm Reset', title_size=20, content=content,
            size_hint=(0.85, 0.55), background_color=(0.14, 0.15, 0.20, 1),
            title_color=(1, 1, 1, 1), separator_color=(0.25, 0.27, 0.32, 1),
        )
        cancel.bind(on_release=popup.dismiss)
        confirm.bind(on_release=lambda *a: (self._do_reset(), popup.dismiss()))
        popup.open()

    def _do_reset(self):
        self.j1_summary.reset()
        self.j2_summary.reset()
        self._save()


class TrafficCounterApp(App):
    def build(self):
        Window.fullscreen = 'auto'
        Window.orientation = 'landscape'
        return RootLayout()

    def on_start(self):
        if platform == 'android':
            Window.update_viewport()


if __name__ == '__main__':
    TrafficCounterApp().run()
