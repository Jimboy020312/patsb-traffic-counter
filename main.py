"""
PATSB Traffic Counter — Kivy landscape, square grid clusters with haptic feedback
"""
import json, os, math

from kivy.config import Config
Config.set('graphics', 'resizable', '0')
Config.set('graphics', 'show_cursor', '1')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image as KivyImage
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.utils import platform
from kivy.graphics import (Color, Ellipse, Line, RoundedRectangle,
                            Rectangle, Triangle, Bezier, InstructionGroup)
from kivy.clock import Clock

Window.clearcolor = (0.08, 0.09, 0.12, 1)
if platform != 'android':
    Window.size = (1280, 720)

SAVE_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic_save.json")
DEFAULT_TIMER = 15 * 60
SUMMARY_ORDER_LEFT  = ["CAR", "LRY", "LLRY", "BUS", "MOTO"]  # C L LL B M
SUMMARY_ORDER_RIGHT = ["CAR",  "LRY", "LLRY", "BUS", "MOTO"] # C L LL B M
SUMMARY_ORDER = SUMMARY_ORDER_LEFT  # fallback
VEHICLES = {
    "CAR":  ("C",  (0.85, 0.20, 0.20, 1)),
    "MOTO": ("M",  (0.20, 0.72, 0.35, 1)),
    "LRY":  ("L",  (0.20, 0.47, 0.87, 1)),
    "LLRY": ("LL", (0.93, 0.50, 0.15, 1)),
    "BUS":  ("B",  (0.85, 0.75, 0.10, 1)),
}

# Grid layout: 2×3 grid (or shaped), ordered by usage priority
# CAR (most used) → top-left large; MOTO, LRY, LLRY, BUS fill around
# We use a 2-column grid:
#  Row0: CAR    | MOTO
#  Row1: LRY    | BUS
#  Row2: LLRY   | (blank / total label)
# Actually for a tight 2-col 3-row grid both sides:
GRID_ORDER = ["CAR", "MOTO", "LRY", "BUS", "LLRY"]   # left col top→bottom, then right

TOP_H    = 120
TIMER_H  = 130   # compact — just digits + 3 small buttons

# ── Haptic feedback ──────────────────────────────────────────────────────────
_haptic_flash_ev = None
_vibrator        = None

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
        Context        = autoclass('android.content.Context')
        _vibrator = PythonActivity.mActivity.getSystemService(Context.VIBRATOR_SERVICE)
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


# ── Vehicle icon drawing ─────────────────────────────────────────────────────
def draw_icon(c, key, cx, cy, sz):
    """
    White line-art vehicle icon drawn onto canvas group c.
    sz is the reference size (button width/height).
    All coordinates are relative to (cx, cy) = button centre.
    """
    s  = sz / 200.0
    lw = max(1.8, 3.2 * s)
    wr = 11 * s          # standard wheel radius

    with c:
        Color(1, 1, 1, 0.95)

        if key == 'CAR':
            # Side-view sedan: long body + raised cabin + 2 wheels
            bw, bh = 110*s, 26*s
            rw, rh = 68*s,  22*s
            # Main body
            Line(rounded_rectangle=(cx - bw/2, cy - 14*s, bw, bh, 5*s), width=lw)
            # Roof cabin (slightly right of centre for realistic sedan look)
            Line(rounded_rectangle=(cx - rw/2 + 6*s, cy + 10*s, rw, rh, 6*s), width=lw)
            # Windscreen hint (diagonal line inside cabin)
            Line(points=[cx - rw/2 + 6*s + 6*s, cy + 10*s,
                          cx - rw/2 + 6*s + 18*s, cy + 10*s + rh], width=lw * 0.6)
            # Wheels
            Ellipse(pos=(cx - bw/2 + 18*s - wr, cy - 28*s), size=(wr*2, wr*2))
            Ellipse(pos=(cx + bw/2 - 18*s - wr, cy - 28*s), size=(wr*2, wr*2))
            # Wheel hub dots
            hub = wr * 0.38
            Ellipse(pos=(cx - bw/2 + 18*s - hub, cy - 28*s + wr - hub), size=(hub*2, hub*2))
            Ellipse(pos=(cx + bw/2 - 18*s - hub, cy - 28*s + wr - hub), size=(hub*2, hub*2))

        elif key == 'MOTO':
            # Detailed side-view motorcycle
            rwr = 21*s    # rear wheel radius
            fwr = 19*s    # front wheel radius
            rwx = cx - 42*s;  rwy = cy - 16*s
            fwx = cx + 40*s;  fwy = cy - 12*s
            # Wheels
            Ellipse(pos=(rwx - rwr, rwy - rwr), size=(rwr*2, rwr*2))
            Ellipse(pos=(fwx - fwr, fwy - fwr), size=(fwr*2, fwr*2))
            # Wheel hubs
            hub = rwr * 0.32
            Ellipse(pos=(rwx - hub, rwy - hub), size=(hub*2, hub*2))
            hub2 = fwr * 0.32
            Ellipse(pos=(fwx - hub2, fwy - hub2), size=(hub2*2, hub2*2))
            # Seat / rider position
            sx = cx - 6*s;  sy = rwy + 36*s
            # Main frame spine: rear axle → seat → neck
            neck_x = fwx - 10*s;  neck_y = fwy + 28*s
            Line(points=[rwx, rwy + rwr, sx, sy, neck_x, neck_y], width=lw)
            # Swing arm: rear axle → lower frame
            Line(points=[rwx, rwy, cx - 14*s, cy], width=lw * 0.9)
            # Engine/tank block
            Line(rounded_rectangle=(cx - 28*s, cy - 4*s, 30*s, 18*s, 3*s), width=lw * 0.85)
            # Front fork
            Line(points=[fwx, fwy + fwr, neck_x, neck_y], width=lw)
            # Handlebar
            hbx = neck_x - 4*s
            Line(points=[hbx - 12*s, neck_y + 8*s, hbx + 10*s, neck_y - 6*s], width=lw)
            # Seat pad
            Line(rounded_rectangle=(sx - 16*s, sy - 3*s, 30*s, 10*s, 3*s), width=lw * 0.8)
            # Exhaust pipe (low, toward rear)
            Line(points=[cx - 10*s, cy - 8*s, rwx + rwr, rwy - rwr * 0.3], width=lw * 0.7)

        elif key == 'BUS':
            # City bus: tall rectangular body, multiple windows, door
            bw, bh = 92*s, 56*s
            # Body
            Line(rounded_rectangle=(cx - bw/2, cy - bh/2, bw, bh, 3*s), width=lw)
            # Roof luggage rail (thin line on top)
            Line(points=[cx - bw/2 + 8*s, cy + bh/2 - 4*s,
                          cx + bw/2 - 8*s, cy + bh/2 - 4*s], width=lw * 0.55)
            # 3 passenger windows
            win_w, win_h = 18*s, 14*s
            win_y = cy + 8*s
            for i in range(3):
                wx = cx - bw/2 + 8*s + i * 26*s
                Line(rounded_rectangle=(wx, win_y, win_w, win_h, 2*s), width=lw * 0.75)
            # Windscreen (front left, from side view)
            Line(rounded_rectangle=(cx - bw/2 + 8*s, cy - 2*s, 20*s, 18*s, 2*s), width=lw * 0.75)
            # Door (right side near rear from viewer perspective)
            Line(rectangle=(cx + bw/2 - 22*s, cy - bh/2 + 4*s, 14*s, 22*s), width=lw * 0.8)
            # Door split line
            Line(points=[cx + bw/2 - 15*s, cy - bh/2 + 4*s,
                          cx + bw/2 - 15*s, cy - bh/2 + 26*s], width=lw * 0.55)
            # 2 wheels
            Ellipse(pos=(cx - bw/2 + 20*s - wr, cy - bh/2 - wr * 1.9), size=(wr*2, wr*2))
            Ellipse(pos=(cx + bw/2 - 20*s - wr, cy - bh/2 - wr * 1.9), size=(wr*2, wr*2))
            hub = wr * 0.35
            Ellipse(pos=(cx - bw/2 + 20*s - hub, cy - bh/2 - wr * 1.9 + wr - hub), size=(hub*2, hub*2))
            Ellipse(pos=(cx + bw/2 - 20*s - hub, cy - bh/2 - wr * 1.9 + wr - hub), size=(hub*2, hub*2))

        elif key == 'LRY':
            # 2-axle lorry (small truck): cab + short cargo body
            cab_w, cab_h = 32*s, 46*s
            bod_w, bod_h = 64*s, 30*s
            # Cargo body (left of cab from side view)
            Line(rectangle=(cx - cab_w/2 - bod_w, cy - bod_h/2, bod_w, bod_h), width=lw)
            # Cargo ribs (2 vertical lines on cargo body)
            for i in range(1, 3):
                rx = cx - cab_w/2 - bod_w + i * (bod_w / 3)
                Line(points=[rx, cy - bod_h/2 + 3*s, rx, cy + bod_h/2 - 3*s], width=lw * 0.55)
            # Cab
            Line(rounded_rectangle=(cx - cab_w/2, cy - bod_h/2, cab_w, cab_h, 4*s), width=lw)
            # Cab windscreen
            Line(rounded_rectangle=(cx - cab_w/2 + 4*s, cy + 4*s, cab_w - 8*s, 14*s, 2*s), width=lw * 0.75)
            # Cab door line
            Line(points=[cx - cab_w/2 + 4*s, cy - bod_h/2 + 3*s,
                          cx - cab_w/2 + 4*s, cy + 2*s], width=lw * 0.55)
            # Bumper / grille
            Line(rounded_rectangle=(cx + cab_w/2 - 5*s, cy - bod_h/2 + 2*s, 4*s, 12*s, 1*s), width=lw * 0.7)
            # 2 axles: front (under cab) + rear (under cargo)
            Ellipse(pos=(cx - wr, cy - bod_h/2 - wr * 2.1), size=(wr*2, wr*2))
            Ellipse(pos=(cx - cab_w/2 - bod_w + 16*s - wr, cy - bod_h/2 - wr * 2.1), size=(wr*2, wr*2))
            hub = wr * 0.35
            Ellipse(pos=(cx - hub, cy - bod_h/2 - wr * 2.1 + wr - hub), size=(hub*2, hub*2))
            Ellipse(pos=(cx - cab_w/2 - bod_w + 16*s - hub, cy - bod_h/2 - wr * 2.1 + wr - hub), size=(hub*2, hub*2))

        elif key == 'LLRY':
            # 3-axle large lorry / prime mover + long trailer
            cab_w, cab_h = 28*s, 52*s
            bod_w, bod_h = 96*s, 28*s
            # Long trailer
            Line(rectangle=(cx - cab_w/2 - bod_w, cy - bod_h/2, bod_w, bod_h), width=lw)
            # Trailer ribs (3 vertical lines)
            for i in range(1, 4):
                rx = cx - cab_w/2 - bod_w + i * (bod_w / 4)
                Line(points=[rx, cy - bod_h/2 + 3*s, rx, cy + bod_h/2 - 3*s], width=lw * 0.55)
            # 5th-wheel coupling hump
            Line(rounded_rectangle=(cx - cab_w/2 - 12*s, cy + bod_h/2 - 2*s, 14*s, 8*s, 2*s), width=lw * 0.7)
            # Cab
            Line(rounded_rectangle=(cx - cab_w/2, cy - bod_h/2, cab_w, cab_h, 4*s), width=lw)
            # Cab windscreen
            Line(rounded_rectangle=(cx - cab_w/2 + 4*s, cy + 5*s, cab_w - 8*s, 15*s, 2*s), width=lw * 0.75)
            # Cab door line
            Line(points=[cx - cab_w/2 + 4*s, cy - bod_h/2 + 3*s,
                          cx - cab_w/2 + 4*s, cy + 3*s], width=lw * 0.55)
            # Bumper / bull bar
            Line(rounded_rectangle=(cx + cab_w/2 - 5*s, cy - bod_h/2 + 2*s, 4*s, 14*s, 1*s), width=lw * 0.7)
            # 3 axles: front cab, mid trailer, rear trailer
            front_x  = cx - wr
            mid_x    = cx - cab_w/2 - bod_w * 0.45 - wr
            rear_x   = cx - cab_w/2 - bod_w + 14*s - wr
            wheel_y  = cy - bod_h/2 - wr * 2.1
            Ellipse(pos=(front_x, wheel_y), size=(wr*2, wr*2))
            Ellipse(pos=(mid_x,   wheel_y), size=(wr*2, wr*2))
            Ellipse(pos=(rear_x,  wheel_y), size=(wr*2, wr*2))
            hub = wr * 0.35
            for wx in (front_x + wr - hub, mid_x + wr - hub, rear_x + wr - hub):
                Ellipse(pos=(wx, wheel_y + wr - hub), size=(hub*2, hub*2))



# ── Asset paths ──────────────────────────────────────────────────────────────
_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
_ICON_FILES = {
    'CAR':  'car.png',
    'MOTO': 'moto.png',
    'LRY':  'lry.png',
    'LLRY': 'llry.png',
    'BUS':  'bus.png',
}

def _icon_path(key):
    path = os.path.join(_ASSET_DIR, _ICON_FILES[key])
    return path if os.path.exists(path) else None

# ── Square button with canvas icon ───────────────────────────────────────────
class SquareVehicleButton(Button):
    """
    Square button with:
    - Solid colour fill matching vehicle colour
    - PNG icon from assets/ (falls back to canvas line-art if missing)
    - Short vehicle code label at bottom
    - Press feedback: darkened fill + white border ring
    """
    CORNER_RADIUS = 8

    def __init__(self, key, circle_color, label_text, **kwargs):
        super().__init__(
            background_normal='',
            background_color=(0, 0, 0, 0),
            **kwargs
        )
        self.key          = key
        self.circle_color = circle_color
        self.label_text   = label_text
        self._pressed     = False
        self.bind(pos=self._redraw, size=self._redraw)

        # ── Image widget (PNG icon) ──
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

        # ── Label widget ──
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
        r    = self.CORNER_RADIUS
        cr   = self.circle_color

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
        pad   = 6

        # ── Label at bottom ──
        self._lbl.size      = (w, lbl_h)
        self._lbl.pos       = (self.x, self.y + pad)
        self._lbl.text_size = self._lbl.size

        # ── Icon: image or canvas fallback ──
        icon_zone_h = h - lbl_h - pad * 2
        icon_zone_y = self.y + lbl_h + pad

        if self._img:
            # Fit icon squarely in icon zone with small padding
            icon_sz = min(w, icon_zone_h) * 0.82
            self._img.size = (icon_sz, icon_sz)
            self._img.pos  = (
                self.x + (w - icon_sz) / 2,
                icon_zone_y + (icon_zone_h - icon_sz) / 2,
            )
        else:
            # Canvas fallback: line-art
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
# Layout philosophy: usage-priority placement
#   CAR (highest use)  → top row, spans larger / leftmost prominence
#   MOTO               → second
#   LRY                → third
#   BUS                → fourth
#   LLRY               → fifth (least common)
#
# Grid: 2 columns × 3 rows, tight (no gap).
# Left cluster  → anchor bottom-left, buttons fill inward (right/up)
# Right cluster → anchor bottom-right, mirror

# Left cluster  — col 0 is the outer (left) edge, col 1 is inner (toward timer)
GRID_KEYS_LEFT = [
    ["LRY",  None  ],   # row 0 top
    ["CAR",  "MOTO"],   # row 1  (C<->M swapped)
    ["BUS",  "LLRY"],   # row 2  (B<->LL swapped)
]

# Right cluster — horizontal mirror: col 0 is inner, col 1 is outer (right) edge
GRID_KEYS_RIGHT = [
    [None,   "LRY" ],   # row 0 top
    ["MOTO", "CAR" ],   # row 1  (mirrored)
    ["LLRY", "BUS" ],   # row 2  (mirrored)
]

class SquareGridCluster(GridLayout):
    """
    2-column × 3-row tight grid of square vehicle buttons.
    Anchored by `corner` ('left' or 'right').
    Buttons are square and flush — no spacing, thin separator lines only.
    """
    SEP = 3   # px between buttons (visual gap / dark separator)

    def __init__(self, on_tap, corner, **kwargs):
        super().__init__(cols=2, rows=3, spacing=self.SEP, padding=0, **kwargs)
        self.on_tap = on_tap
        self.corner = corner
        self._buttons = {}

        grid_keys = GRID_KEYS_LEFT if corner == 'left' else GRID_KEYS_RIGHT
        for row in grid_keys:
            for key in row:
                if key is None:
                    # Filler cell — dark panel with total label
                    filler = BoxLayout()
                    with filler.canvas.before:
                        Color(0.13, 0.14, 0.18, 1)
                        self._filler_rect = Rectangle(pos=filler.pos, size=filler.size)
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
        self._filler_rect.pos  = w.pos
        self._filler_rect.size = w.size

    def _tap(self, key):
        haptic_tap()
        self.on_tap(key)


# ── Summary chip ──────────────────────────────────────────────────────────────
class SummaryChip(Button):
    def __init__(self, chip_color, **kwargs):
        self._chip_color = chip_color
        self._dim        = tuple(max(0, c * 0.35) if i < 3 else c
                                 for i, c in enumerate(chip_color))
        self._flash_ev   = None
        super().__init__(background_normal='', background_color=chip_color, **kwargs)

    def flash(self):
        if self._flash_ev: self._flash_ev.cancel()
        self.background_color = list(self._dim)
        self._flash_ev = Clock.schedule_once(
            lambda dt: setattr(self, 'background_color', list(self._chip_color)), 0.22)


class JunctionSummary(BoxLayout):
    def __init__(self, on_minus, order=None, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('spacing', 6)
        kwargs.setdefault('padding', [8, 6, 8, 6])
        super().__init__(**kwargs)
        self.on_minus = on_minus
        self.counts   = {k: 0 for k in VEHICLES}
        self.chips    = {}
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
            self.on_minus()

    def _refresh(self, key):
        btn, short = self.chips[key]
        btn.text = f"{short}: {self.counts[key]}"

    def increment(self, key): self.counts[key] += 1; self._refresh(key)
    def get_counts(self):     return dict(self.counts)

    def set_counts(self, data):
        for k, v in data.items():
            if k in self.counts:
                self.counts[k] = max(0, int(v)); self._refresh(k)

    def reset(self):
        for k in self.counts: self.counts[k] = 0; self._refresh(k)


# ── Timer widget ──────────────────────────────────────────────────────────────
BASE_FONT = 48

class TimerWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', spacing=6, **kwargs)
        self._duration  = DEFAULT_TIMER
        self._remaining = DEFAULT_TIMER
        self._running   = False
        self._tick_ev   = None
        self._alert_ev  = None
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
        for b in (self.btn_ss, btn_set, btn_rst): row.add_widget(b)
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
        if self._remaining <= 0: return
        self._running = True
        self.btn_ss.text = "PAUSE"
        self.btn_ss.background_color = (0.70, 0.50, 0.10, 1)
        self._stop_alert()
        self.lbl.color     = (0.55, 0.92, 0.55, 1)
        self.lbl.font_size = BASE_FONT
        self._tick_ev = Clock.schedule_interval(self._tick, 1)

    def _pause(self):
        self._running = False
        self.btn_ss.text = "START"
        self.btn_ss.background_color = (0.20, 0.60, 0.30, 1)
        if self._tick_ev: self._tick_ev.cancel()

    def _tick(self, dt):
        self._remaining -= 1
        self.lbl.text = self._fmt(self._remaining)
        if self._remaining <= 0:
            self._pause()
            self._alert()

    def _alert(self):
        self._alert_idx = 0
        self._alert_ev  = Clock.schedule_interval(self._alert_step, 0.25)

    def _alert_step(self, dt):
        self._alert_idx += 1
        phase = self._alert_idx % 2
        if phase == 0:
            self.lbl.font_size = BASE_FONT * 1.35
            self.lbl.color     = (1, 0.08, 0.08, 1)
        else:
            self.lbl.font_size = BASE_FONT * 0.85
            self.lbl.color     = (0.75, 0.05, 0.05, 1)

    def _stop_alert(self):
        if self._alert_ev: self._alert_ev.cancel(); self._alert_ev = None

    def _reset_timer(self, *a):
        self._pause(); self._stop_alert()
        self._remaining    = self._duration
        self.lbl.text      = self._fmt(self._remaining)
        self.lbl.color     = (0.55, 0.92, 0.55, 1)
        self.lbl.font_size = BASE_FONT

    def reset_to_default(self): self._reset_timer()
    def stop_alert(self):
        self._stop_alert()
        self.lbl.color     = (0.55, 0.92, 0.55, 1)
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
        cancel  = self._mk("Cancel", (0.30, 0.32, 0.38, 1))
        confirm = self._mk("Set",    (0.20, 0.55, 0.30, 1))
        btns.add_widget(cancel); btns.add_widget(confirm); content.add_widget(btns)
        popup = Popup(title='Set Timer', title_size=20, content=content,
                      size_hint=(0.55, 0.58), background_color=(0.14, 0.15, 0.20, 1),
                      title_color=(1, 1, 1, 1),
                      separator_color=(0.25, 0.27, 0.32, 1))
        cancel.bind(on_release=popup.dismiss)
        def _apply(*a):
            try:
                p = inp.text.strip().split(':')
                total = int(p[0]) * 60 + int(p[1]) if len(p) == 2 else int(p[0]) * 60
                self._duration = max(1, total)
            except:
                self._duration = DEFAULT_TIMER
            self._remaining    = self._duration
            self.lbl.text      = self._fmt(self._remaining)
            self.lbl.color     = (0.55, 0.92, 0.55, 1)
            self.lbl.font_size = BASE_FONT
            self._stop_alert(); popup.dismiss()
        confirm.bind(on_release=_apply)
        popup.open()


# ── Root layout ───────────────────────────────────────────────────────────────
class RootLayout(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ── Top bar ───────────────────────────────────────────
        top = BoxLayout(size_hint=(1, None), height=TOP_H,
                        pos_hint={'x': 0, 'top': 1},
                        spacing=6, padding=[6, 6, 6, 6])
        self.j1_summary = JunctionSummary(on_minus=self._save, order=SUMMARY_ORDER_LEFT, size_hint=(0.42, 1))
        self.reset_btn = Button(text="RESET ALL", font_size=16, bold=True,
                           color=(1, 1, 1, 1), background_normal='',
                           background_color=(0.75, 0.20, 0.20, 1), size_hint=(0.16, 1))
        self.reset_btn.bind(on_release=self._confirm_reset)
        reset_btn = self.reset_btn
        self.j2_summary = JunctionSummary(on_minus=self._save, order=SUMMARY_ORDER_RIGHT, size_hint=(0.42, 1))
        top.add_widget(self.j1_summary)
        top.add_widget(reset_btn)
        top.add_widget(self.j2_summary)
        self.add_widget(top)

        # ── Square grid clusters ──────────────────────────────
        # Each cluster: 2-col × 3-row grid, positioned at left/right edges
        # We size them to fill the available height below the top bar
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

        # ── Timer — centred between clusters ─────────────────
        self.timer_box = BoxLayout(orientation='vertical',
                                   size_hint=(None, None),
                                   pos_hint={'center_x': 0.5})
        self.timer = TimerWidget(size_hint=(1, 1))
        self.timer_box.add_widget(self.timer)
        self.add_widget(self.timer_box)

        self.bind(size=self._layout)
        self.reset_btn.bind(size=self._layout)
        self.j1_summary.chips['MOTO'][0].bind(pos=self._layout, size=self._layout)
        self.j2_summary.chips['CAR'][0].bind(pos=self._layout, size=self._layout)
        self._load()

    def _layout(self, *a):
        W, H = self.size
        cluster_h = H - TOP_H

        # Left grid right edge = right edge of MOTO chip (rightmost) in j1_summary
        moto_chip_l = self.j1_summary.chips['MOTO'][0]
        left_grid_w = (moto_chip_l.right if moto_chip_l.width > 1 else W * 0.42)

        # Right grid left edge = left edge of CAR chip in j2_summary
        car_chip = self.j2_summary.chips['CAR'][0]
        right_grid_x = (car_chip.x if car_chip.width > 1 else W * 0.58)
        right_grid_w = W - right_grid_x

        grid_h = cluster_h

        # Left cluster: flush left, width up to MOTO chip right edge
        self.j1_cluster.size = (left_grid_w, grid_h)
        self.j1_cluster.pos  = (0, 0)

        # Right cluster: starts at CAR chip left edge, flush right
        self.j2_cluster.size = (right_grid_w, grid_h)
        self.j2_cluster.pos  = (right_grid_x, 0)

        # Timer: same width as RESET ALL, centred, vertically centred
        timer_w = self.reset_btn.width if self.reset_btn.width > 1 else W * 0.16
        timer_h = min(TIMER_H, cluster_h - 12)
        self.timer_box.size = (timer_w, timer_h)
        self.timer_box.pos  = (
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
        cancel  = _mk("Cancel",     (0.30, 0.32, 0.38, 1))
        confirm = _mk("Yes, Reset", (0.75, 0.20, 0.20, 1))
        btns.add_widget(cancel); btns.add_widget(confirm); content.add_widget(btns)
        popup = Popup(title='Confirm', title_size=20, content=content,
                      size_hint=(0.65, 0.45),
                      background_color=(0.14, 0.15, 0.20, 1),
                      title_color=(1, 1, 1, 1),
                      separator_color=(0.25, 0.27, 0.32, 1))
        cancel.bind(on_release=popup.dismiss)
        confirm.bind(on_release=lambda *a: (self._do_reset(), popup.dismiss()))
        popup.open()

    def _do_reset(self):
        self.j1_summary.reset(); self.j2_summary.reset()
        self.timer.stop_alert(); self.timer.reset_to_default()
        self._save()


class TrafficCounterApp(App):
    def build(self):
        Window.fullscreen = 'auto'
        Window.orientation = 'landscape'
        return RootLayout()

    def on_start(self):
        if platform == 'android':
            _init_haptic()
            Window.update_viewport()


if __name__ == '__main__':
    TrafficCounterApp().run()
