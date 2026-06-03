"""
PATSB Traffic Counter — Kivy landscape, square grid clusters with haptic feedback
"""
from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, Line, RoundedRectangle,
                           Rectangle, Triangle, Bezier, InstructionGroup)
from kivy.utils import platform
from kivy.core.window import Window
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.core.audio import SoundLoader
from kivy.uix.image import Image as KivyImage
from kivy.uix.boxlayout import BoxLayout
from kivy.app import App
import json
import os
import math

from kivy.config import Config
Config.set('graphics', 'resizable', '0')
Config.set('graphics', 'show_cursor', '1')


Window.clearcolor = (0.08, 0.09, 0.12, 1)
if platform != 'android':
    Window.size = (1280, 720)

SAVE_FILE = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "traffic_save.json")
DEFAULT_TIMER = 15 * 60
SUMMARY_ORDER_LEFT = ["CAR", "LRY", "LLRY", "BUS", "MOTO"]  # C L LL B M
SUMMARY_ORDER_RIGHT = ["CAR",  "LRY", "LLRY", "BUS", "MOTO"]  # C L LL B M
SUMMARY_ORDER = SUMMARY_ORDER_LEFT  # fallback
VEHICLES = {
    "CAR":  ("C",  (0.85, 0.20, 0.20, 1)),
    "MOTO": ("M",  (0.20, 0.72, 0.35, 1)),
    "LRY":  ("L",  (0.20, 0.47, 0.87, 1)),
    "LLRY": ("LL", (0.93, 0.50, 0.15, 1)),
    "BUS":  ("B",  (0.85, 0.75, 0.10, 1)),
}

GRID_ORDER = ["CAR", "MOTO", "LRY", "BUS", "LLRY"]

TOP_H = 120
TIMER_H = 130   # compact — just digits + 3 small buttons

# ── Haptic feedback ──────────────────────────────────────────────────────────
_haptic_flash_ev = None
_vibrator = None


def _pc_haptic_flash():
    global _haptic_flash_ev
    Window.clearcolor = (0.30, 0.20, 0.08, 1)
    if _haptic_flash_ev:
        _haptic_flash_ev.cancel()
    _haptic_flash_ev = Clock.schedule_once(
        lambda dt: setattr(Window, 'clearcolor', (0.08, 0.09, 0.12, 1)), 0.07)


def _init_haptic():
    """Cache the Android vibrator service once at startup."""
    global _vibrator
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        _vibrator = PythonActivity.mActivity.getSystemService(
            Context.VIBRATOR_SERVICE)
        print("HAPTIC: vibrator acquired:", _vibrator)
    except Exception as e:
        print("HAPTIC _init_haptic failed:", e)


def haptic_tap():
    """30 ms haptic on Android; amber flash on PC for testing."""
    if platform != 'android':
        _pc_haptic_flash()
        return
    global _vibrator
    if _vibrator is None:
        _init_haptic()
    if _vibrator is None:
        return
    try:
        from jnius import autoclass
        VibrationEffect = autoclass('android.os.VibrationEffect')
        _vibrator.vibrate(
            VibrationEffect.createOneShot(30, VibrationEffect.DEFAULT_AMPLITUDE))
    except Exception:
        try:
            _vibrator.vibrate(30)          # pre-API-26 fallback
        except Exception as e:
            print("HAPTIC vibrate failed:", e)


# ── Sound effects ─────────────────────────────────────────────────────────────
_snd_tap = None
_snd_alarm = None


def _init_sounds():
    global _snd_tap, _snd_alarm
    import struct
    import math as _math
    import base64
    import tempfile

    def _wav(samples, sr=22050):
        import struct as _s
        data = b''.join(_s.pack('<h', max(-32768, min(32767, int(v))))
                        for v in samples)
        hdr = _s.pack('<4sI4s4sIHHIIHH4sI',
                      b'RIFF', 36+len(data), b'WAVE', b'fmt ', 16,
                      1, 1, sr, sr*2, 2, 16, b'data', len(data))
        return hdr + data

    def _make_beep(sr=22050):
        import math as _m
        n = int(sr * 0.07)
        out = []
        for i in range(n):
            t = i / sr
            dec = _m.exp(-i / (sr * 0.018))
            hit = _m.exp(-i / (sr * 0.004))
            body = _m.sin(2*_m.pi * 300 * t) * 0.65 * dec
            transient = _m.sin(2*_m.pi * 2200 * t) * 0.45 * hit
            out.append(32767 * (body + transient))
        return _wav(out, sr)

    def _make_alarm(sr=22050):
        import math as _m

        def square(freq, t, n_harm=6):
            s = 0.0
            for k in range(1, n_harm*2, 2):
                s += _m.sin(2*_m.pi * freq * k * t) / k
            return s * (4/_m.pi)

        def beep(freq, dur, vol=0.72):
            n = int(sr * dur)
            seg = []
            att = int(sr * 0.006)
            rel = int(sr * 0.025)
            for i in range(n):
                t = i / sr
                if i < att:
                    env = i / att
                elif i > n - rel:
                    env = (n - i) / rel
                else:
                    env = 1.0
                seg.append(32767 * vol * env * square(freq, t) * 0.35)
            return seg

        out = []
        for _ in range(3):
            out.extend(beep(880, 0.18))
            out.extend([0] * int(sr * 0.10))
        return _wav(out, sr)

    try:
        import tempfile
        import os as _os
        td = tempfile.gettempdir()
        tap_path = _os.path.join(td, 'patsb_tap.wav')
        alarm_path = _os.path.join(td, 'patsb_alarm.wav')
        with open(tap_path,   'wb') as f:
            f.write(_make_beep())
        with open(alarm_path, 'wb') as f:
            f.write(_make_alarm())
        _snd_tap = SoundLoader.load(tap_path)
        _snd_alarm = SoundLoader.load(alarm_path)
        if _snd_tap:
            _snd_tap.volume = 0.5
        if _snd_alarm:
            _snd_alarm.volume = 0.8
        print("SOUND: tap=%s alarm=%s" % (_snd_tap, _snd_alarm))
    except Exception as e:
        print("SOUND init failed:", e)


def play_tap():
    if _snd_tap:
        _snd_tap.stop()
        _snd_tap.play()


def play_alarm():
    if _snd_alarm:
        _snd_alarm.stop()
        _snd_alarm.play()

# ── Vehicle icon drawing ─────────────────────────────────────────────────────


def draw_icon(c, key, cx, cy, sz):
    s = sz / 200.0
    lw = max(1.8, 3.2 * s)
    wr = 11 * s

    with c:
        Color(1, 1, 1, 0.95)

        if key == 'CAR':
            bw, bh = 110*s, 26*s
            rw, rh = 68*s,  22*s
            Line(rounded_rectangle=(cx - bw/2, cy - 14*s, bw, bh, 5*s), width=lw)
            Line(rounded_rectangle=(cx - rw/2 + 6*s,
                 cy + 10*s, rw, rh, 6*s), width=lw)
            Line(points=[cx - rw/2 + 6*s + 6*s, cy + 10*s,
                         cx - rw/2 + 6*s + 18*s, cy + 10*s + rh], width=lw * 0.6)
            Ellipse(pos=(cx - bw/2 + 18*s - wr, cy - 28*s), size=(wr*2, wr*2))
            Ellipse(pos=(cx + bw/2 - 18*s - wr, cy - 28*s), size=(wr*2, wr*2))
            hub = wr * 0.38
            Ellipse(pos=(cx - bw/2 + 18*s - hub, cy -
                    28*s + wr - hub), size=(hub*2, hub*2))
            Ellipse(pos=(cx + bw/2 - 18*s - hub, cy -
                    28*s + wr - hub), size=(hub*2, hub*2))

        elif key == 'MOTO':
            rwr = 21*s
            fwr = 19*s
            rwx = cx - 42*s
            rwy = cy - 16*s
            fwx = cx + 40*s
            fwy = cy - 12*s
            Ellipse(pos=(rwx - rwr, rwy - rwr), size=(rwr*2, rwr*2))
            Ellipse(pos=(fwx - fwr, fwy - fwr), size=(fwr*2, fwr*2))
            hub = rwr * 0.32
            Ellipse(pos=(rwx - hub, rwy - hub), size=(hub*2, hub*2))
            hub2 = fwr * 0.32
            Ellipse(pos=(fwx - hub2, fwy - hub2), size=(hub2*2, hub2*2))
            sx = cx - 6*s
            sy = rwy + 36*s
            neck_x = fwx - 10*s
            neck_y = fwy + 28*s
            Line(points=[rwx, rwy + rwr, sx, sy, neck_x, neck_y], width=lw)
            Line(points=[rwx, rwy, cx - 14*s, cy], width=lw * 0.9)
            Line(rounded_rectangle=(cx - 28*s, cy - 4 *
                 s, 30*s, 18*s, 3*s), width=lw * 0.85)
            Line(points=[fwx, fwy + fwr, neck_x, neck_y], width=lw)
            hbx = neck_x - 4*s
            Line(points=[hbx - 12*s, neck_y + 8*s,
                 hbx + 10*s, neck_y - 6*s], width=lw)
            Line(rounded_rectangle=(sx - 16*s, sy -
                 3*s, 30*s, 10*s, 3*s), width=lw * 0.8)
            Line(points=[cx - 10*s, cy - 8*s, rwx +
                 rwr, rwy - rwr * 0.3], width=lw * 0.7)

        elif key == 'BUS':
            bw, bh = 92*s, 56*s
            Line(rounded_rectangle=(cx - bw/2, cy - bh/2, bw, bh, 3*s), width=lw)
            Line(points=[cx - bw/2 + 8*s, cy + bh/2 - 4*s,
                         cx + bw/2 - 8*s, cy + bh/2 - 4*s], width=lw * 0.55)
            win_w, win_h = 18*s, 14*s
            win_y = cy + 8*s
            for i in range(3):
                wx = cx - bw/2 + 8*s + i * 26*s
                Line(rounded_rectangle=(
                    wx, win_y, win_w, win_h, 2*s), width=lw * 0.75)
            Line(rounded_rectangle=(cx - bw/2 + 8*s, cy -
                 2*s, 20*s, 18*s, 2*s), width=lw * 0.75)
            Line(rectangle=(cx + bw/2 - 22*s, cy - bh /
                 2 + 4*s, 14*s, 22*s), width=lw * 0.8)
            Line(points=[cx + bw/2 - 15*s, cy - bh/2 + 4*s,
                         cx + bw/2 - 15*s, cy - bh/2 + 26*s], width=lw * 0.55)
            Ellipse(pos=(cx - bw/2 + 20*s - wr, cy -
                    bh/2 - wr * 1.9), size=(wr*2, wr*2))
            Ellipse(pos=(cx + bw/2 - 20*s - wr, cy -
                    bh/2 - wr * 1.9), size=(wr*2, wr*2))
            hub = wr * 0.35
            Ellipse(pos=(cx - bw/2 + 20*s - hub, cy - bh/2 -
                    wr * 1.9 + wr - hub), size=(hub*2, hub*2))
            Ellipse(pos=(cx + bw/2 - 20*s - hub, cy - bh/2 -
                    wr * 1.9 + wr - hub), size=(hub*2, hub*2))

        elif key == 'LRY':
            cab_w, cab_h = 32*s, 46*s
            bod_w, bod_h = 64*s, 30*s
            Line(rectangle=(cx - cab_w/2 - bod_w,
                 cy - bod_h/2, bod_w, bod_h), width=lw)
            for i in range(1, 3):
                rx = cx - cab_w/2 - bod_w + i * (bod_w / 3)
                Line(points=[rx, cy - bod_h/2 + 3*s, rx,
                     cy + bod_h/2 - 3*s], width=lw * 0.55)
            Line(rounded_rectangle=(cx - cab_w/2, cy -
                 bod_h/2, cab_w, cab_h, 4*s), width=lw)
            Line(rounded_rectangle=(cx - cab_w/2 + 4*s, cy +
                 4*s, cab_w - 8*s, 14*s, 2*s), width=lw * 0.75)
            Line(points=[cx - cab_w/2 + 4*s, cy - bod_h/2 + 3*s,
                         cx - cab_w/2 + 4*s, cy + 2*s], width=lw * 0.55)
            Line(rounded_rectangle=(cx + cab_w/2 - 5*s, cy -
                 bod_h/2 + 2*s, 4*s, 12*s, 1*s), width=lw * 0.7)
            Ellipse(pos=(cx - wr, cy - bod_h/2 - wr * 2.1), size=(wr*2, wr*2))
            Ellipse(pos=(cx - cab_w/2 - bod_w + 16*s - wr,
                    cy - bod_h/2 - wr * 2.1), size=(wr*2, wr*2))
            hub = wr * 0.35
            Ellipse(pos=(cx - hub, cy - bod_h/2 - wr *
                    2.1 + wr - hub), size=(hub*2, hub*2))
            Ellipse(pos=(cx - cab_w/2 - bod_w + 16*s - hub, cy -
                    bod_h/2 - wr * 2.1 + wr - hub), size=(hub*2, hub*2))

        elif key == 'LLRY':
            cab_w, cab_h = 28*s, 52*s
            bod_w, bod_h = 96*s, 28*s
            Line(rectangle=(cx - cab_w/2 - bod_w,
                 cy - bod_h/2, bod_w, bod_h), width=lw)
            for i in range(1, 4):
                rx = cx - cab_w/2 - bod_w + i * (bod_w / 4)
                Line(points=[rx, cy - bod_h/2 + 3*s, rx,
                     cy + bod_h/2 - 3*s], width=lw * 0.55)
            Line(rounded_rectangle=(cx - cab_w/2 - 12*s, cy +
                 bod_h/2 - 2*s, 14*s, 8*s, 2*s), width=lw * 0.7)
            Line(rounded_rectangle=(cx - cab_w/2, cy -
                 bod_h/2, cab_w, cab_h, 4*s), width=lw)
            Line(rounded_rectangle=(cx - cab_w/2 + 4*s, cy +
                 5*s, cab_w - 8*s, 15*s, 2*s), width=lw * 0.75)
            Line(points=[cx - cab_w/2 + 4*s, cy - bod_h/2 + 3*s,
                         cx - cab_w/2 + 4*s, cy + 3*s], width=lw * 0.55)
            Line(rounded_rectangle=(cx + cab_w/2 - 5*s, cy -
                 bod_h/2 + 2*s, 4*s, 14*s, 1*s), width=lw * 0.7)
            front_x = cx - wr
            mid_x = cx - cab_w/2 - bod_w * 0.45 - wr
            rear_x = cx - cab_w/2 - bod_w + 14*s - wr
            wheel_y = cy - bod_h/2 - wr * 2.1
            Ellipse(pos=(front_x, wheel_y), size=(wr*2, wr*2))
            Ellipse(pos=(mid_x,   wheel_y), size=(wr*2, wr*2))
            Ellipse(pos=(rear_x,  wheel_y), size=(wr*2, wr*2))
            hub = wr * 0.35
            for wx in (front_x + wr - hub, mid_x + wr - hub, rear_x + wr - hub):
                Ellipse(pos=(wx, wheel_y + wr - hub), size=(hub*2, hub*2))


# ── Asset paths ──────────────────────────────────────────────────────────────
_ICON_FILES = {
    'CAR':  'car.png',
    'MOTO': 'moto.png',
    'LRY':  'lry.png',
    'LLRY': 'llry.png',
    'BUS':  'bus.png',
}


def _asset_dir():
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets'),
        os.path.join(os.getcwd(), 'assets'),
        os.path.join(os.path.expanduser('~'), 'assets'),
        'assets',
    ]
    for d in candidates:
        if os.path.isdir(d):
            print('ASSETS found at:', d)
            return d
    print('ASSETS dir not found, tried:', candidates)
    return candidates[0]


_ASSET_DIR = _asset_dir()


def _icon_path(key):
    path = os.path.join(_ASSET_DIR, _ICON_FILES[key])
    exists = os.path.exists(path)
    print('ICON', key, path, 'OK' if exists else 'MISSING')
    return path if exists else None

# ── Square button with canvas icon ───────────────────────────────────────────


class SquareVehicleButton(Button):
    CORNER_RADIUS = 8

    def __init__(self, key, circle_color, label_text, **kwargs):
        super().__init__(
            background_normal='',
            background_color=(0, 0, 0, 0),
            **kwargs
        )
        self.key = key
        self.circle_color = circle_color
        self.label_text = label_text
        self._pressed = False
        self.bind(pos=self._redraw, size=self._redraw)

        self._img = None
        icon_path = _icon_path(key)
        if icon_path:
            self._img = KivyImage(
                source=icon_path,
                allow_stretch=True,
                keep_ratio=True,
                size_hint=(None, None),
            )
            self.add_widget(self._img)

        self._lbl = Label(
            text=label_text,
            font_size=15,
            bold=True,
            color=(1, 1, 1, 0.90),
            halign='center',
            valign='middle',
            size_hint=(None, None),
        )
        self.add_widget(self._lbl)

        self._redraw()

    def _redraw(self, *a):
        self.canvas.before.clear()
        w, h = self.size
        r = self.CORNER_RADIUS
        cr = self.circle_color

        with self.canvas.before:
            if self._pressed:
                ring = 6
                Color(1, 1, 1, 0.9)
                RoundedRectangle(
                    pos=(self.x - ring, self.y - ring),
                    size=(w + ring*2, h + ring*2),
                    radius=[r + ring]
                )
                Color(cr[0]*0.38, cr[1]*0.38, cr[2]*0.38, cr[3])
            else:
                Color(*cr)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])

        lbl_h = 24
        pad = 6

        self._lbl.size = (w, lbl_h)
        self._lbl.pos = (self.x, self.y + pad)
        self._lbl.text_size = self._lbl.size

        icon_zone_h = h - lbl_h - pad * 2
        icon_zone_y = self.y + lbl_h + pad

        if self._img:
            icon_sz = min(w, icon_zone_h) * 0.82
            self._img.size = (icon_sz, icon_sz)
            self._img.pos = (
                self.x + (w - icon_sz) / 2,
                icon_zone_y + (icon_zone_h - icon_sz) / 2,
            )
        else:
            self.canvas.after.clear()
            cx = self.x + w / 2
            cy = icon_zone_y + icon_zone_h / 2
            sz = min(w, icon_zone_h) * 0.92
            with self.canvas.after:
                draw_icon(self.canvas.after, self.key, cx, cy, sz)

    def on_press(self):
        self._pressed = True
        self._redraw()

    def on_release(self):
        self._pressed = False
        self._redraw()


# ── Square grid cluster ───────────────────────────────────────────────────────
GRID_KEYS_LEFT = [
    ["LRY",  None],
    ["MOTO", "CAR"],
    ["LLRY", "BUS"],
]

GRID_KEYS_RIGHT = [
    [None,   "LRY"],
    ["CAR",  "MOTO"],
    ["BUS",  "LLRY"],
]


class SquareGridCluster(GridLayout):
    SEP = 3

    def __init__(self, on_tap, corner, **kwargs):
        super().__init__(cols=2, rows=3, spacing=self.SEP, padding=0, **kwargs)
        self.on_tap = on_tap
        self.corner = corner
        self._buttons = {}

        grid_keys = GRID_KEYS_LEFT if corner == 'left' else GRID_KEYS_RIGHT
        for row in grid_keys:
            for key in row:
                if key is None:
                    filler = BoxLayout()
                    with filler.canvas.before:
                        Color(0.13, 0.14, 0.18, 1)
                        self._filler_rect = Rectangle(
                            pos=filler.pos, size=filler.size)
                    filler.bind(pos=self._upd_filler, size=self._upd_filler)
                    self._filler_widget = filler
                    self.add_widget(filler)
                else:
                    short, color = VEHICLES[key]
                    btn = SquareVehicleButton(
                        key=key,
                        circle_color=color,
                        label_text=short,
                        size_hint=(1, 1),
                    )
                    btn.bind(on_release=lambda b, k=key: self._tap(k))
                    self._buttons[key] = btn
                    self.add_widget(btn)

    def _upd_filler(self, w, *a):
        self._filler_rect.pos = w.pos
        self._filler_rect.size = w.size

    def _tap(self, key):
        haptic_tap()
        play_tap()
        self.on_tap(key)


# ── Summary chip ──────────────────────────────────────────────────────────────
class SummaryChip(Button):
    def __init__(self, chip_color, **kwargs):
        self._chip_color = chip_color
        self._dim = tuple(max(0, c * 0.35) if i < 3 else c
                          for i, c in enumerate(chip_color))
        self._flash_ev = None
        super().__init__(background_normal='', background_color=chip_color, **kwargs)

    def flash(self):
        if self._flash_ev:
            self._flash_ev.cancel()
        self.background_color = list(self._dim)
        self._flash_ev = Clock.schedule_once(
            lambda dt: setattr(self, 'background_color', list(self._chip_color)), 0.08)


class JunctionSummary(BoxLayout):
    def __init__(self, on_minus, order=None, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('spacing', 6)
        kwargs.setdefault('padding', [8, 6, 8, 6])
        super().__init__(**kwargs)
        self.on_minus = on_minus
        self.counts = {k: 0 for k in VEHICLES}
        self.chips = {}
        for key in (order or SUMMARY_ORDER_LEFT):
            short, color = VEHICLES[key]
            btn = SummaryChip(chip_color=color, text=f"{short}: 0",
                              font_size=24, bold=True,
                              color=(1, 1, 1, 1), size_hint=(1, 1))
            btn.bind(on_release=lambda b, k=key: self._minus(k))
            self.chips[key] = (btn, short)
            self.add_widget(btn)

    def _minus(self, key):
        if self.counts[key] > 0:
            self.counts[key] -= 1
            self._refresh(key)
            self.chips[key][0].flash()
            haptic_tap()
            play_tap()
            self.on_minus()

    def _refresh(self, key):
        btn, short = self.chips[key]
        btn.text = f"{short}: {self.counts[key]}"

    def increment(self, key): self.counts[key] += 1; self._refresh(key)
    def get_counts(self): return dict(self.counts)

    def set_counts(self, data):
        for k, v in data.items():
            if k in self.counts:
                self.counts[k] = max(0, int(v))
                self._refresh(k)

    def reset(self):
        for k in self.counts:
            self.counts[k] = 0
            self._refresh(k)


# ── Timer widget ──────────────────────────────────────────────────────────────
BASE_FONT = 48


class TimerWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', spacing=6, **kwargs)
        self._duration = DEFAULT_TIMER
        self._remaining = DEFAULT_TIMER
        self._running = False
        self._tick_ev = None
        self._alert_ev = None
        self._alert_idx = 0

        self.lbl = Label(text=self._fmt(DEFAULT_TIMER),
                         font_size=BASE_FONT, bold=True,
                         color=(0.55, 0.92, 0.55, 1),
                         size_hint=(1, 1), halign='center', valign='middle')
        self.lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self.add_widget(self.lbl)

        row = BoxLayout(orientation='horizontal', size_hint=(1, None),
                        height=46, spacing=6, padding=[4, 0, 4, 0])
        self.btn_ss = self._mk("START", (0.20, 0.60, 0.30, 1))
        self.btn_ss.bind(on_release=self._toggle)
        btn_set = self._mk("SET",   (0.25, 0.35, 0.60, 1))
        btn_set.bind(on_release=self._open_set)
        btn_rst = self._mk("RESET", (0.55, 0.25, 0.25, 1))
        btn_rst.bind(on_release=self._reset_timer)
        for b in (self.btn_ss, btn_set, btn_rst):
            row.add_widget(b)
        self.add_widget(row)

    def _mk(self, t, bg):
        return Button(text=t, font_size=15, bold=True, color=(1, 1, 1, 1),
                      background_normal='', background_color=bg, size_hint=(1, 1))

    def _fmt(self, secs):
        m, s = divmod(max(0, int(secs)), 60)
        return f"{m:02d}:{s:02d}"

    def _toggle(self, *a):
        self._pause() if self._running else self._start()

    def _start(self):
        if self._remaining <= 0:
            return
        self._running = True
        self.btn_ss.text = "PAUSE"
        self.btn_ss.background_color = (0.70, 0.50, 0.10, 1)
        self._stop_alert()
        self.lbl.color = (0.55, 0.92, 0.55, 1)
        self.lbl.font_size = BASE_FONT
        self._tick_ev = Clock.schedule_interval(self._tick, 1)

    def _pause(self):
        self._running = False
        self.btn_ss.text = "START"
        self.btn_ss.background_color = (0.20, 0.60, 0.30, 1)
        if self._tick_ev:
            self._tick_ev.cancel()

    def _tick(self, dt):
        self._remaining -= 1
        self.lbl.text = self._fmt(self._remaining)
        if self._remaining <= 0:
            self._pause()
            self._alert()

    def _alert(self):
        play_alarm()
        self._alert_idx = 0
        self._alert_ev = Clock.schedule_interval(self._alert_step, 0.25)

    def _alert_step(self, dt):
        self._alert_idx += 1
        phase = self._alert_idx % 2
        if phase == 0:
            self.lbl.font_size = BASE_FONT * 1.35
            self.lbl.color = (1, 0.08, 0.08, 1)
        else:
            self.lbl.font_size = BASE_FONT * 0.85
            self.lbl.color = (0.75, 0.05, 0.05, 1)

    def _stop_alert(self):
        if self._alert_ev:
            self._alert_ev.cancel()
            self._alert_ev = None

    def _reset_timer(self, *a):
        self._pause()
        self._stop_alert()
        self._remaining = self._duration
        self.lbl.text = self._fmt(self._remaining)
        self.lbl.color = (0.55, 0.92, 0.55, 1)
        self.lbl.font_size = BASE_FONT

    def reset_to_default(self): self._reset_timer()

    def stop_alert(self):
        self._stop_alert()
        self.lbl.color = (0.55, 0.92, 0.55, 1)
        self.lbl.font_size = BASE_FONT

    def _open_set(self, *a):
        self._pause()
        content = BoxLayout(orientation='vertical', spacing=12, padding=20)
        content.add_widget(Label(text="Set timer (MM:SS)", font_size=18,
                                 color=(1, 1, 1, 1), size_hint=(1, None), height=34,
                                 halign='center'))
        inp = TextInput(text=self._fmt(self._duration), font_size=32,
                        foreground_color=(1, 1, 1, 1),
                        background_color=(0.15, 0.17, 0.21, 1),
                        cursor_color=(1, 1, 1, 1),
                        size_hint=(1, None), height=60,
                        multiline=False, halign='center')
        content.add_widget(inp)
        btns = BoxLayout(orientation='horizontal', spacing=10,
                         size_hint=(1, None), height=56)
        cancel = self._mk("Cancel", (0.30, 0.32, 0.38, 1))
        confirm = self._mk("Set",    (0.20, 0.55, 0.30, 1))
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)
        popup = Popup(title='Set Timer', title_size=20, content=content,
                      size_hint=(0.62, None), height=260,
                      # anchored near top — keyboard opens below
                      pos_hint={'center_x': 0.5, 'top': 0.98},
                      background_color=(0.14, 0.15, 0.20, 1),
                      title_color=(1, 1, 1, 1),
                      separator_color=(0.25, 0.27, 0.32, 1))
        cancel.bind(on_release=popup.dismiss)

        def _apply(*a):
            try:
                p = inp.text.strip().split(':')
                total = int(p[0]) * 60 + \
                    int(p[1]) if len(p) == 2 else int(p[0]) * 60
                self._duration = max(1, total)
            except:
                self._duration = DEFAULT_TIMER
            self._remaining = self._duration
            self.lbl.text = self._fmt(self._remaining)
            self.lbl.color = (0.55, 0.92, 0.55, 1)
            self.lbl.font_size = BASE_FONT
            self._stop_alert()
            popup.dismiss()
        confirm.bind(on_release=_apply)
        popup.open()


# ── Loading screen ────────────────────────────────────────────────────────────
class LoadingScreen(FloatLayout):
    def __init__(self, on_done, **kwargs):
        super().__init__(**kwargs)
        self._on_done = on_done

        with self.canvas.before:
            Color(0.08, 0.09, 0.12, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        title = Label(
            text='PATSB',
            font_size=72, bold=True,
            color=(0.10, 0.45, 0.90, 1),
            halign='center', valign='middle',
            pos_hint={'center_x': 0.5, 'center_y': 0.60},
            size_hint=(1, None), height=90,
        )
        self.add_widget(title)

        sub = Label(
            text='Traffic Counter',
            font_size=26, bold=False,
            color=(0.65, 0.70, 0.78, 1),
            halign='center', valign='middle',
            pos_hint={'center_x': 0.5, 'center_y': 0.46},
            size_hint=(1, None), height=36,
        )
        self.add_widget(sub)

        self._status = Label(
            text='Initialising...',
            font_size=18,
            color=(0.40, 0.45, 0.52, 1),
            halign='center', valign='middle',
            pos_hint={'center_x': 0.5, 'center_y': 0.28},
            size_hint=(1, None), height=28,
        )
        self.add_widget(self._status)

        self._bar_widget = FloatLayout(
            size_hint=(0.5, None), height=14,
            pos_hint={'center_x': 0.5, 'center_y': 0.16},
        )
        self.add_widget(self._bar_widget)
        self._bar_progress = 0.0
        self._target = 0.0
        self._bar_ev = Clock.schedule_interval(self._animate, 0.03)
        self._bar_widget.bind(pos=self._draw_bar, size=self._draw_bar)

        Clock.schedule_once(self._step1, 0.3)

    def _upd_bg(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _draw_bar(self, *a):
        w = self._bar_widget
        w.canvas.clear()
        bw, bh = w.width, w.height
        if bw < 1:
            return
        with w.canvas:
            Color(0.20, 0.22, 0.28, 1)
            RoundedRectangle(pos=(w.x, w.y), size=(bw, bh), radius=[bh/2])
            Color(0.10, 0.45, 0.90, 1)
            fill_w = max(bh, bw * self._bar_progress)
            RoundedRectangle(pos=(w.x, w.y), size=(fill_w, bh), radius=[bh/2])

    def _animate(self, dt):
        target = getattr(self, '_target', 0.38)
        gap = target - self._bar_progress
        if gap > 0:
            self._bar_progress += max(0.002, gap * 0.08)
        self._bar_progress = min(target, self._bar_progress)
        self._draw_bar()

    def _step1(self, dt):
        self._status.text = 'Loading sounds...'
        _init_sounds()
        self._target = 0.40
        Clock.schedule_once(self._step2, 0.5)

    def _step2(self, dt):
        self._status.text = 'Loading assets...'
        self._target = 0.75
        Clock.schedule_once(self._step3, 0.5)

    def _step3(self, dt):
        self._status.text = 'Ready!'
        self._target = 1.0
        Clock.schedule_interval(self._wait_full, 0.05)

    def _wait_full(self, dt):
        if self._bar_progress >= 0.995:
            Clock.unschedule(self._wait_full)
            Clock.schedule_once(self._finish, 0.18)
            return False

    def _finish(self, dt):
        if self._bar_ev:
            self._bar_ev.cancel()
        self._on_done()

# ── Root layout ───────────────────────────────────────────────────────────────


class RootLayout(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        top = BoxLayout(size_hint=(1, None), height=TOP_H,
                        pos_hint={'x': 0, 'top': 1},
                        spacing=6, padding=[6, 6, 6, 6])
        self.j1_summary = JunctionSummary(
            on_minus=self._save, order=SUMMARY_ORDER_LEFT, size_hint=(0.42, 1))
        self.reset_btn = Button(text="RESET ALL", font_size=16, bold=True,
                                color=(1, 1, 1, 1), background_normal='',
                                background_color=(0.75, 0.20, 0.20, 1), size_hint=(0.16, 1))
        self.reset_btn.bind(on_release=self._confirm_reset)
        reset_btn = self.reset_btn
        self.j2_summary = JunctionSummary(
            on_minus=self._save, order=SUMMARY_ORDER_RIGHT, size_hint=(0.42, 1))
        top.add_widget(self.j1_summary)
        top.add_widget(reset_btn)
        top.add_widget(self.j2_summary)
        self.add_widget(top)

        self.j1_cluster = SquareGridCluster(
            on_tap=self._j1_tap, corner='left',
            size_hint=(None, None),
            pos_hint={'x': 0, 'y': 0}
        )
        self.j2_cluster = SquareGridCluster(
            on_tap=self._j2_tap, corner='right',
            size_hint=(None, None),
            pos_hint={'right': 1, 'y': 0}
        )
        self.add_widget(self.j1_cluster)
        self.add_widget(self.j2_cluster)

        self.timer_box = BoxLayout(orientation='vertical',
                                   size_hint=(None, None),
                                   pos_hint={'center_x': 0.5})
        self.timer = TimerWidget(size_hint=(1, 1))
        self.timer_box.add_widget(self.timer)
        self.add_widget(self.timer_box)

        self.bind(size=self._layout)
        self.reset_btn.bind(size=self._layout)
        self.j1_summary.chips['MOTO'][0].bind(
            pos=self._layout, size=self._layout)
        self.j2_summary.chips['CAR'][0].bind(
            pos=self._layout, size=self._layout)
        self._load()

    def _layout(self, *a):
        W, H = self.size
        cluster_h = H - TOP_H

        moto_chip_l = self.j1_summary.chips['MOTO'][0]
        left_grid_w = (moto_chip_l.right if moto_chip_l.width >
                       1 else W * 0.42)

        car_chip = self.j2_summary.chips['CAR'][0]
        right_grid_x = (car_chip.x if car_chip.width > 1 else W * 0.58)
        right_grid_w = W - right_grid_x

        grid_h = cluster_h

        self.j1_cluster.size = (left_grid_w, grid_h)
        self.j1_cluster.pos = (0, 0)

        self.j2_cluster.size = (right_grid_w, grid_h)
        self.j2_cluster.pos = (right_grid_x, 0)

        timer_w = self.reset_btn.width if self.reset_btn.width > 1 else W * 0.16
        timer_h = min(TIMER_H, cluster_h - 12)
        self.timer_box.size = (timer_w, timer_h)
        self.timer_box.pos = (
            W / 2 - timer_w / 2,
            (cluster_h - timer_h) / 2
        )

    def _j1_tap(self, key): self.j1_summary.increment(key); self._save()
    def _j2_tap(self, key): self.j2_summary.increment(key); self._save()

    def _save(self, *a):
        try:
            with open(SAVE_FILE, 'w') as f:
                json.dump({'j1': self.j1_summary.get_counts(),
                           'j2': self.j2_summary.get_counts()}, f)
        except Exception as e:
            print("Save error:", e)

    def _load(self):
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE, 'r') as f:
                    d = json.load(f)
                self.j1_summary.set_counts(d.get('j1', {}))
                self.j2_summary.set_counts(d.get('j2', {}))
        except Exception as e:
            print("Load error:", e)

    def _confirm_reset(self, *a):
        content = BoxLayout(orientation='vertical', spacing=16, padding=24)
        content.add_widget(Label(text="Reset all counts?", halign='center',
                                 valign='middle', color=(1, 1, 1, 1),
                                 font_size=22, size_hint=(1, 1)))
        btns = BoxLayout(orientation='horizontal', spacing=12,
                         size_hint=(1, None), height=70)

        def _mk(t, bg):
            return Button(text=t, font_size=18, bold=True, color=(1, 1, 1, 1),
                          background_normal='', background_color=bg, size_hint=(1, 1))
        cancel = _mk("Cancel",     (0.30, 0.32, 0.38, 1))
        confirm = _mk("Yes, Reset", (0.75, 0.20, 0.20, 1))
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)
        popup = Popup(title='Confirm', title_size=20, content=content,
                      size_hint=(0.65, 0.45),
                      background_color=(0.14, 0.15, 0.20, 1),
                      title_color=(1, 1, 1, 1),
                      separator_color=(0.25, 0.27, 0.32, 1))
        cancel.bind(on_release=popup.dismiss)
        confirm.bind(on_release=lambda *a: (self._do_reset(), popup.dismiss()))
        popup.open()

    def _do_reset(self):
        self.j1_summary.reset()
        self.j2_summary.reset()
        self.timer.stop_alert()
        self.timer.reset_to_default()
        self._save()


class TrafficCounterApp(App):
    def build(self):
        Window.fullscreen = 'auto'
        Window.orientation = 'landscape'
        self._root = FloatLayout()
        loading = LoadingScreen(on_done=self._launch)
        self._root.add_widget(loading)
        return self._root

    def _launch(self):
        self._root.clear_widgets()
        self._root.add_widget(RootLayout())

    def on_start(self):
        if platform == 'android':
            _init_haptic()
            Window.update_viewport()


if __name__ == '__main__':
    TrafficCounterApp().run()
