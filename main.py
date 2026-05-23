"""
PATSB Traffic Counter
Kivy — rainbow arc, circular buttons, countdown timer
"""

import json
import os
import math

from kivy.config import Config
Config.set('graphics', 'resizable', '0')
Config.set('graphics', 'show_cursor', '1')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.utils import platform
from kivy.graphics import Color, Ellipse
from kivy.animation import Animation
from kivy.clock import Clock

Window.clearcolor = (0.08, 0.09, 0.12, 1)
if platform != 'android':
    Window.size = (1280, 720)

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic_save.json")
DEFAULT_TIMER = 15 * 60

SUMMARY_ORDER = ["CAR", "LRY", "LLRY", "BUS", "MOTO"]

VEHICLES = {
    "CAR":  ("🚗", "C",  (0.85, 0.20, 0.20, 1)),
    "MOTO": ("🏍", "M",  (0.20, 0.72, 0.35, 1)),
    "LRY":  ("🚛", "L",  (0.20, 0.47, 0.87, 1)),
    "LLRY": ("🚚", "LL", (0.93, 0.50, 0.15, 1)),
    "BUS":  ("🚌", "B",  (0.85, 0.75, 0.10, 1)),
}

# Ring 1 (closest) : LRY  at 42°
# Ring 2 (middle)  : MOTO at 55°, CAR at 25°   ← swapped vs before
# Ring 3 (outer)   : BUS  at 65°, LLRY at 18°
LEFT_ARC = [
    ("LRY",  42, 0.30),
    ("MOTO", 55, 0.54),
    ("CAR",  25, 0.54),
    ("BUS",  65, 0.78),
    ("LLRY", 18, 0.78),
]

BTN_SIZE = 155


def flat_btn(text, bg, color=(1, 1, 1, 1), font_size=22, bold=True):
    return Button(
        text=text, font_size=font_size, bold=bold,
        color=color, background_normal='', background_color=bg,
    )


class CircleButton(Button):
    """Circular button — shrinks on press, always bounces back."""

    def __init__(self, circle_color, **kwargs):
        super().__init__(
            background_normal='',
            background_color=(0, 0, 0, 0),
            **kwargs
        )
        self.circle_color = circle_color
        self._full_size = (BTN_SIZE, BTN_SIZE)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.circle_color)
            Ellipse(pos=self.pos, size=self.size)

    def on_press(self):
        # Instant shrink — no animation so it can't get stuck mid-shrink
        Animation.cancel_all(self)
        s = BTN_SIZE * 0.80
        self.size = (s, s)
        self._redraw()

    def on_release(self):
        # Always restore to full size, with bounce
        Animation.cancel_all(self)
        anim = Animation(
            size=self._full_size,
            duration=0.18,
            t='out_back',
        )
        anim.bind(on_progress=lambda *a: self._redraw())
        anim.bind(on_complete=lambda *a: self._force_restore())
        anim.start(self)

    def _force_restore(self, *a):
        # Hard guarantee — always full size after release
        self.size = self._full_size
        self._redraw()


class SummaryChip(Button):
    def __init__(self, chip_color, **kwargs):
        self._chip_color = chip_color
        self._dim = tuple(max(0, c * 0.45) if i < 3 else c
                          for i, c in enumerate(chip_color))
        super().__init__(background_normal='', background_color=chip_color, **kwargs)

    def flash(self):
        Animation.cancel_all(self)
        anim = (Animation(background_color=self._dim, duration=0.08) +
                Animation(background_color=self._chip_color, duration=0.18))
        anim.start(self)


class JunctionSummary(BoxLayout):
    def __init__(self, on_minus, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('spacing', 6)
        kwargs.setdefault('padding', [8, 4, 8, 4])
        super().__init__(**kwargs)
        self.on_minus = on_minus
        self.counts = {k: 0 for k in VEHICLES}
        self.chips = {}
        for key in SUMMARY_ORDER:
            icon, short, color = VEHICLES[key]
            btn = SummaryChip(
                chip_color=color,
                text=f"{short}: 0",
                font_size=20, bold=True,
                color=(1, 1, 1, 1), size_hint=(1, 1),
            )
            btn.bind(on_release=lambda b, k=key: self._minus(k))
            self.chips[key] = (btn, short)
            self.add_widget(btn)

    def _minus(self, key):
        if self.counts[key] > 0:
            self.counts[key] -= 1
            self._refresh(key)
            btn, _ = self.chips[key]
            btn.flash()
            self.on_minus()

    def _refresh(self, key):
        btn, short = self.chips[key]
        btn.text = f"{short}: {self.counts[key]}"

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
    def __init__(self, on_tap, corner, **kwargs):
        super().__init__(**kwargs)
        self.on_tap = on_tap
        self.corner = corner
        self._btns = []
        self.bind(size=self._place, pos=self._place)

        for key, angle, radius in LEFT_ARC:
            icon, short, color = VEHICLES[key]
            btn = CircleButton(
                circle_color=color,
                text=icon, font_size=38, bold=True, color=(1, 1, 1, 1),
            )
            btn.size_hint = (None, None)
            btn.size = (BTN_SIZE, BTN_SIZE)
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
                bx = self.x + dx - BTN_SIZE / 2
                by = self.y + dy - BTN_SIZE / 2
            else:
                bx = self.x + w - dx - BTN_SIZE / 2
                by = self.y + dy - BTN_SIZE / 2
            btn.pos = (bx, by)


class TimerWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', spacing=4, **kwargs)
        self._duration = DEFAULT_TIMER
        self._remaining = DEFAULT_TIMER
        self._running = False
        self._tick_event = None
        self._flash_event = None
        self._flash_state = False

        self.lbl = Label(
            text=self._fmt(self._remaining),
            font_size=52, bold=True,
            color=(0.60, 0.90, 0.60, 1),
            size_hint=(1, 1),
            halign='center', valign='middle',
        )
        self.lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self.add_widget(self.lbl)

        controls = BoxLayout(orientation='horizontal', size_hint=(1, None),
                             height=40, spacing=6, padding=[4, 0, 4, 0])
        self.btn_startstop = flat_btn("START", (0.20, 0.60, 0.30, 1), font_size=13)
        self.btn_startstop.size_hint = (1, 1)
        self.btn_startstop.bind(on_release=self._toggle)
        btn_set = flat_btn("SET", (0.25, 0.35, 0.60, 1), font_size=13)
        btn_set.size_hint = (1, 1)
        btn_set.bind(on_release=self._open_set)
        btn_reset = flat_btn("RESET", (0.55, 0.25, 0.25, 1), font_size=13)
        btn_reset.size_hint = (1, 1)
        btn_reset.bind(on_release=self._reset_timer)
        controls.add_widget(self.btn_startstop)
        controls.add_widget(btn_set)
        controls.add_widget(btn_reset)
        self.add_widget(controls)

    def _fmt(self, secs):
        m, s = divmod(max(0, int(secs)), 60)
        return f"{m:02d}:{s:02d}"

    def _toggle(self, *a):
        self._pause() if self._running else self._start()

    def _start(self):
        if self._remaining <= 0:
            return
        self._running = True
        self.btn_startstop.text = "PAUSE"
        self.btn_startstop.background_color = (0.70, 0.50, 0.10, 1)
        self._stop_flash()
        self.lbl.color = (0.60, 0.90, 0.60, 1)
        self._tick_event = Clock.schedule_interval(self._tick, 1)

    def _pause(self):
        self._running = False
        self.btn_startstop.text = "START"
        self.btn_startstop.background_color = (0.20, 0.60, 0.30, 1)
        if self._tick_event:
            self._tick_event.cancel()

    def _tick(self, dt):
        self._remaining -= 1
        self.lbl.text = self._fmt(self._remaining)
        if self._remaining <= 0:
            self._pause()
            self._alert()

    def _alert(self):
        self._flash_event = Clock.schedule_interval(self._do_flash, 0.4)

    def _do_flash(self, dt):
        self._flash_state = not self._flash_state
        self.lbl.color = (1, 0.2, 0.2, 1) if self._flash_state else (1, 1, 1, 1)

    def _stop_flash(self):
        if self._flash_event:
            self._flash_event.cancel()
            self._flash_event = None

    def _reset_timer(self, *a):
        self._pause()
        self._stop_flash()
        self._remaining = self._duration
        self.lbl.text = self._fmt(self._remaining)
        self.lbl.color = (0.60, 0.90, 0.60, 1)

    def reset_to_default(self):
        self._reset_timer()

    def _open_set(self, *a):
        self._pause()
        content = BoxLayout(orientation='vertical', spacing=12, padding=20)
        content.add_widget(Label(
            text="Set timer (MM:SS)",
            font_size=16, color=(1, 1, 1, 1),
            size_hint=(1, None), height=30, halign='center',
        ))
        inp = TextInput(
            text=self._fmt(self._duration),
            font_size=28, foreground_color=(1, 1, 1, 1),
            background_color=(0.15, 0.17, 0.21, 1),
            cursor_color=(1, 1, 1, 1),
            size_hint=(1, None), height=54,
            multiline=False, halign='center',
        )
        content.add_widget(inp)
        btns = BoxLayout(orientation='horizontal', spacing=10,
                         size_hint=(1, None), height=52)
        cancel  = flat_btn("Cancel", (0.30, 0.32, 0.38, 1), font_size=16)
        confirm = flat_btn("Set",    (0.20, 0.55, 0.30, 1), font_size=16)
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)
        popup = Popup(
            title='Set Timer', title_size=18, content=content,
            size_hint=(0.55, 0.55),
            background_color=(0.14, 0.15, 0.20, 1),
            title_color=(1, 1, 1, 1),
            separator_color=(0.25, 0.27, 0.32, 1),
        )
        cancel.bind(on_release=popup.dismiss)

        def _apply(*a):
            try:
                text = inp.text.strip()
                parts = text.split(':')
                if len(parts) == 2:
                    total = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 1:
                    total = int(parts[0]) * 60
                else:
                    total = DEFAULT_TIMER
                self._duration = max(1, total)
            except Exception:
                self._duration = DEFAULT_TIMER
            self._remaining = self._duration
            self._stop_flash()
            self.lbl.color = (0.60, 0.90, 0.60, 1)
            self.lbl.text = self._fmt(self._remaining)
            popup.dismiss()

        confirm.bind(on_release=_apply)
        popup.open()


class RootLayout(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ── Top bar: J1 summary | RESET ALL | J2 summary ───────
        top = BoxLayout(
            size_hint=(1, None), height=72,
            pos_hint={'x': 0, 'top': 1},
            spacing=6, padding=[6, 4, 6, 4],
        )
        self.j1_summary = JunctionSummary(on_minus=self._save, size_hint=(0.42, 1))
        reset_btn = flat_btn("RESET ALL", (0.75, 0.20, 0.20, 1), font_size=15)
        reset_btn.size_hint = (0.16, 1)
        reset_btn.bind(on_release=self._confirm_reset)
        self.j2_summary = JunctionSummary(on_minus=self._save, size_hint=(0.42, 1))
        top.add_widget(self.j1_summary)
        top.add_widget(reset_btn)
        top.add_widget(self.j2_summary)
        self.add_widget(top)

        # ── Rainbow clusters — bottom corners ──────────────────
        self.j1_cluster = RainbowCluster(
            on_tap=self._j1_tap, corner='left',
            size_hint=(0.48, None),
            pos_hint={'x': 0, 'y': 0},
        )
        self.j2_cluster = RainbowCluster(
            on_tap=self._j2_tap, corner='right',
            size_hint=(0.48, None),
            pos_hint={'right': 1, 'y': 0},
        )
        # Cluster height = screen minus top bar
        self.bind(size=self._resize_clusters)

        self.add_widget(self.j1_cluster)
        self.add_widget(self.j2_cluster)

        # ── Timer — centred in the gap between clusters ────────
        # Horizontal: middle 24% between clusters
        # Vertical:   centred within the cluster zone (below top bar)
        self.timer_box = BoxLayout(
            orientation='vertical',
            size_hint=(0.22, None), height=170,
            pos_hint={'center_x': 0.5},
        )
        self.timer = TimerWidget(size_hint=(1, 1))
        self.timer_box.add_widget(self.timer)
        self.add_widget(self.timer_box)
        self.bind(size=self._reposition_timer)

        self._load()

    def _resize_clusters(self, *a):
        cluster_h = self.height - 72  # subtract top bar
        self.j1_cluster.height = cluster_h
        self.j2_cluster.height = cluster_h
        self._reposition_timer()

    def _reposition_timer(self, *a):
        # Centre timer vertically within the cluster zone
        cluster_h = self.height - 72
        timer_h = self.timer_box.height
        # y position: centre of cluster zone
        centre_y = (cluster_h - timer_h) / 2
        self.timer_box.y = centre_y

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
            text="Reset all counts?",
            halign='center', valign='middle',
            color=(1, 1, 1, 1), font_size=20, size_hint=(1, 1),
        ))
        btns = BoxLayout(orientation='horizontal', spacing=12,
                         size_hint=(1, None), height=70)
        cancel  = flat_btn("Cancel",     (0.30, 0.32, 0.38, 1), font_size=18)
        confirm = flat_btn("Yes, Reset", (0.75, 0.20, 0.20, 1), font_size=18)
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)
        popup = Popup(
            title='Confirm', title_size=20, content=content,
            size_hint=(0.70, 0.45),
            background_color=(0.14, 0.15, 0.20, 1),
            title_color=(1, 1, 1, 1),
            separator_color=(0.25, 0.27, 0.32, 1),
        )
        cancel.bind(on_release=popup.dismiss)
        confirm.bind(on_release=lambda *a: (self._do_reset(), popup.dismiss()))
        popup.open()

    def _do_reset(self):
        self.j1_summary.reset()
        self.j2_summary.reset()
        self.timer.reset_to_default()
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
