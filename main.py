"""
PATSB Traffic Counter — Kivy landscape, square grid clusters with haptic feedback
"""
from kivy.config import Config
import math
import json
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image as KivyImage
from kivy.core.audio import SoundLoader
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
import os
# Must be set before ANY kivy import — forces zero-delay touch on APK
os.environ['KIVY_BCM_DISPMANX_ID'] = '0'
os.environ['KCFG_POSTPROC_DOUBLE_TAP_TIME'] = '0'
os.environ['KCFG_POSTPROC_DOUBLE_TAP_DISTANCE'] = '0'
os.environ['KCFG_POSTPROC_RETAIN_TIME'] = '0'
os.environ['KCFG_POSTPROC_RETAIN_DISTANCE'] = '0'
os.environ['KCFG_POSTPROC_JITTER_DISTANCE'] = '0'


Config.set('graphics', 'resizable', '0')
Config.set('graphics', 'show_cursor', '1')
# Disable the 200ms tap-vs-scroll detection delay that Kivy adds on Android APKs.
# Without this, every touch is held for up to 200ms before being dispatched.
Config.set('input', 'mouse', 'mouse,disable_multitouch')
Config.set('postproc', 'double_tap_time', '0')
Config.set('postproc', 'double_tap_distance', '0')
Config.set('postproc', 'retain_time', '0')
Config.set('postproc', 'retain_distance', '0')
Config.set('postproc', 'jitter_distance', '0')
Config.set('postproc', 'jitter_ignore_devices', 'mouse,mactouch,')


Window.clearcolor = (0.08, 0.09, 0.12, 1)
if platform != 'android':
    Window.size = (1280, 720)

SAVE_FILE = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "traffic_save.json")
DEFAULT_TIMER = 15 * 60
SUMMARY_ORDER_LEFT = ["CAR", "LRY", "LLRY", "BUS", "MOTO"]
SUMMARY_ORDER_RIGHT = ["CAR", "LRY", "LLRY", "BUS", "MOTO"]
SUMMARY_ORDER = SUMMARY_ORDER_LEFT
VEHICLES = {
    "CAR":  ("C",  (0.85, 0.20, 0.20, 1)),
    "MOTO": ("M",  (0.20, 0.72, 0.35, 1)),
    "LRY":  ("L",  (0.20, 0.47, 0.87, 1)),
    "LLRY": ("LL", (0.93, 0.50, 0.15, 1)),
    "BUS":  ("B",  (0.85, 0.75, 0.10, 1)),
}

TOP_H = 120
TIMER_H = 130

# ── Haptic feedback ──────────────────────────────────────────────────────────
_haptic_flash_ev = None
_vibrator = None
_VibrationEffect = None   # cached JNI class — looked up once at init


def _pc_haptic_flash():
    global _haptic_flash_ev
    Window.clearcolor = (0.30, 0.20, 0.08, 1)
    if _haptic_flash_ev:
        _haptic_flash_ev.cancel()
    _haptic_flash_ev = Clock.schedule_once(
        lambda dt: setattr(Window, 'clearcolor', (0.08, 0.09, 0.12, 1)), 0.07)


def _init_haptic():
    global _vibrator, _VibrationEffect
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        _vibrator = PythonActivity.mActivity.getSystemService(
            Context.VIBRATOR_SERVICE)
        try:
            _VibrationEffect = autoclass('android.os.VibrationEffect')
        except Exception:
            _VibrationEffect = None
        print("HAPTIC init OK, VibrationEffect=%s" % _VibrationEffect)
    except Exception as e:
        print("HAPTIC _init_haptic failed:", e)


def _do_haptic():
    """Run on background thread — no JNI class lookups, just the vibrate call."""
    if _vibrator is None:
        return
    try:
        if _VibrationEffect is not None:
            _vibrator.vibrate(
                _VibrationEffect.createOneShot(
                    30, _VibrationEffect.DEFAULT_AMPLITUDE))
        else:
            _vibrator.vibrate(30)
    except Exception as e:
        print("HAPTIC vibrate failed:", e)


def haptic_tap():
    if platform != 'android':
        _pc_haptic_flash()
        return
    if _vibrator is None:
        return
    import threading
    threading.Thread(target=_do_haptic, daemon=True).start()


# ── Sound effects ─────────────────────────────────────────────────────────────
# Each short sound keeps a pool of POOL_SIZE pre-loaded instances so rapid
# taps never have to wait for a previous play() to finish — no stop() stall.
_POOL_SIZE = 3
_pool_tap = []
_pool_click = []
_pool_alarm = []
_pool_idx = {'tap': 0, 'click': 0, 'alarm': 0}


def _init_sounds():
    global _pool_tap, _pool_click, _pool_alarm

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

    def _make_soft_click(sr=22050):
        import math as _m
        n = int(sr * 0.055)
        out = []
        for i in range(n):
            t = i / sr
            dec = _m.exp(-i / (sr * 0.012))
            body = _m.sin(2*_m.pi * 180 * t) * 0.55 * dec
            sub = _m.sin(2*_m.pi * 80 * t) * 0.30 * dec
            out.append(32767 * (body + sub))
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

    def _make_pool(path, vol, size):
        pool = []
        for _ in range(size):
            s = SoundLoader.load(path)
            if s:
                s.volume = vol
                pool.append(s)
        return pool

    try:
        import tempfile
        import os as _os
        td = tempfile.gettempdir()
        paths = {
            'tap':   (_os.path.join(td, 'patsb_tap.wav'),   _make_beep()),
            'click': (_os.path.join(td, 'patsb_click.wav'), _make_soft_click()),
            'alarm': (_os.path.join(td, 'patsb_alarm.wav'), _make_alarm()),
        }
        for key, (path, data) in paths.items():
            with open(path, 'wb') as f:
                f.write(data)
        _pool_tap = _make_pool(paths['tap'][0],   0.5,  _POOL_SIZE)
        _pool_click = _make_pool(paths['click'][0], 0.45, _POOL_SIZE)
        _pool_alarm = _make_pool(paths['alarm'][0], 0.8,  1)
        print("SOUND pools: tap=%d click=%d alarm=%d" %
              (len(_pool_tap), len(_pool_click), len(_pool_alarm)))
    except Exception as e:
        print("SOUND init failed:", e)


def _pool_play(pool, key):
    if not pool:
        return
    idx = _pool_idx[key] % len(pool)
    _pool_idx[key] = idx + 1
    snd = pool[idx]
    # Do NOT call stop() — just play() on the next idle instance in the pool.
    # This avoids the Android stop() latency that causes the UI stall.
    try:
        snd.play()
    except Exception:
        pass


def play_tap():        _pool_play(_pool_tap,   'tap')
def play_startpause(): _pool_play(_pool_click, 'click')


def play_alarm():
    if _pool_alarm:
        try:
            _pool_alarm[0].stop()
            _pool_alarm[0].play()
        except Exception:
            pass


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
            Line(rounded_rectangle=(cx-bw/2, cy-14*s, bw, bh, 5*s), width=lw)
            Line(rounded_rectangle=(cx-rw/2+6*s, cy+10*s, rw, rh, 6*s), width=lw)
            Line(points=[cx-rw/2+12*s, cy+10*s, cx -
                 rw/2+24*s, cy+10*s+rh], width=lw*0.6)
            Ellipse(pos=(cx-bw/2+18*s-wr, cy-28*s), size=(wr*2, wr*2))
            Ellipse(pos=(cx+bw/2-18*s-wr, cy-28*s), size=(wr*2, wr*2))
            hub = wr*0.38
            Ellipse(pos=(cx-bw/2+18*s-hub, cy-28*s+wr-hub), size=(hub*2, hub*2))
            Ellipse(pos=(cx+bw/2-18*s-hub, cy-28*s+wr-hub), size=(hub*2, hub*2))

        elif key == 'MOTO':
            rwr = 21*s
            fwr = 19*s
            rwx = cx-42*s
            rwy = cy-16*s
            fwx = cx+40*s
            fwy = cy-12*s
            Ellipse(pos=(rwx-rwr, rwy-rwr), size=(rwr*2, rwr*2))
            Ellipse(pos=(fwx-fwr, fwy-fwr), size=(fwr*2, fwr*2))
            hub = rwr*0.32
            Ellipse(pos=(rwx-hub, rwy-hub), size=(hub*2, hub*2))
            hub2 = fwr*0.32
            Ellipse(pos=(fwx-hub2, fwy-hub2), size=(hub2*2, hub2*2))
            sx = cx-6*s
            sy = rwy+36*s
            neck_x = fwx-10*s
            neck_y = fwy+28*s
            Line(points=[rwx, rwy+rwr, sx, sy, neck_x, neck_y], width=lw)
            Line(points=[rwx, rwy, cx-14*s, cy], width=lw*0.9)
            Line(rounded_rectangle=(cx-28*s, cy-4 *
                 s, 30*s, 18*s, 3*s), width=lw*0.85)
            Line(points=[fwx, fwy+fwr, neck_x, neck_y], width=lw)
            hbx = neck_x-4*s
            Line(points=[hbx-12*s, neck_y+8*s, hbx+10*s, neck_y-6*s], width=lw)
            Line(rounded_rectangle=(sx-16*s, sy-3*s, 30*s, 10*s, 3*s), width=lw*0.8)
            Line(points=[cx-10*s, cy-8*s, rwx+rwr, rwy-rwr*0.3], width=lw*0.7)

        elif key == 'BUS':
            bw, bh = 92*s, 56*s
            Line(rounded_rectangle=(cx-bw/2, cy-bh/2, bw, bh, 3*s), width=lw)
            Line(points=[cx-bw/2+8*s, cy+bh/2-4*s, cx +
                 bw/2-8*s, cy+bh/2-4*s], width=lw*0.55)
            win_w, win_h = 18*s, 14*s
            win_y = cy+8*s
            for i in range(3):
                wx = cx-bw/2+8*s+i*26*s
                Line(rounded_rectangle=(wx, win_y, win_w, win_h, 2*s), width=lw*0.75)
            Line(rounded_rectangle=(cx-bw/2+8*s, cy -
                 2*s, 20*s, 18*s, 2*s), width=lw*0.75)
            Line(rectangle=(cx+bw/2-22*s, cy-bh/2+4*s, 14*s, 22*s), width=lw*0.8)
            Line(points=[cx+bw/2-15*s, cy-bh/2+4*s, cx +
                 bw/2-15*s, cy-bh/2+26*s], width=lw*0.55)
            Ellipse(pos=(cx-bw/2+20*s-wr, cy-bh/2-wr*1.9), size=(wr*2, wr*2))
            Ellipse(pos=(cx+bw/2-20*s-wr, cy-bh/2-wr*1.9), size=(wr*2, wr*2))
            hub = wr*0.35
            Ellipse(pos=(cx-bw/2+20*s-hub, cy-bh/2 -
                    wr*1.9+wr-hub), size=(hub*2, hub*2))
            Ellipse(pos=(cx+bw/2-20*s-hub, cy-bh/2 -
                    wr*1.9+wr-hub), size=(hub*2, hub*2))

        elif key == 'LRY':
            cab_w, cab_h = 32*s, 46*s
            bod_w, bod_h = 64*s, 30*s
            Line(rectangle=(cx-cab_w/2-bod_w, cy-bod_h/2, bod_w, bod_h), width=lw)
            for i in range(1, 3):
                rx = cx-cab_w/2-bod_w+i*(bod_w/3)
                Line(points=[rx, cy-bod_h/2+3*s, rx,
                     cy+bod_h/2-3*s], width=lw*0.55)
            Line(rounded_rectangle=(cx-cab_w/2, cy -
                 bod_h/2, cab_w, cab_h, 4*s), width=lw)
            Line(rounded_rectangle=(cx-cab_w/2+4*s, cy +
                 4*s, cab_w-8*s, 14*s, 2*s), width=lw*0.75)
            Line(points=[cx-cab_w/2+4*s, cy-bod_h/2+3*s,
                 cx-cab_w/2+4*s, cy+2*s], width=lw*0.55)
            Line(rounded_rectangle=(cx+cab_w/2-5*s, cy -
                 bod_h/2+2*s, 4*s, 12*s, 1*s), width=lw*0.7)
            Ellipse(pos=(cx-wr, cy-bod_h/2-wr*2.1), size=(wr*2, wr*2))
            Ellipse(pos=(cx-cab_w/2-bod_w+16*s-wr, cy -
                    bod_h/2-wr*2.1), size=(wr*2, wr*2))
            hub = wr*0.35
            Ellipse(pos=(cx-hub, cy-bod_h/2-wr*2.1+wr-hub), size=(hub*2, hub*2))
            Ellipse(pos=(cx-cab_w/2-bod_w+16*s-hub, cy-bod_h /
                    2-wr*2.1+wr-hub), size=(hub*2, hub*2))

        elif key == 'LLRY':
            cab_w, cab_h = 28*s, 52*s
            bod_w, bod_h = 96*s, 28*s
            Line(rectangle=(cx-cab_w/2-bod_w, cy-bod_h/2, bod_w, bod_h), width=lw)
            for i in range(1, 4):
                rx = cx-cab_w/2-bod_w+i*(bod_w/4)
                Line(points=[rx, cy-bod_h/2+3*s, rx,
                     cy+bod_h/2-3*s], width=lw*0.55)
            Line(rounded_rectangle=(cx-cab_w/2-12*s, cy +
                 bod_h/2-2*s, 14*s, 8*s, 2*s), width=lw*0.7)
            Line(rounded_rectangle=(cx-cab_w/2, cy -
                 bod_h/2, cab_w, cab_h, 4*s), width=lw)
            Line(rounded_rectangle=(cx-cab_w/2+4*s, cy +
                 5*s, cab_w-8*s, 15*s, 2*s), width=lw*0.75)
            Line(points=[cx-cab_w/2+4*s, cy-bod_h/2+3*s,
                 cx-cab_w/2+4*s, cy+3*s], width=lw*0.55)
            Line(rounded_rectangle=(cx+cab_w/2-5*s, cy -
                 bod_h/2+2*s, 4*s, 14*s, 1*s), width=lw*0.7)
            front_x = cx-wr
            mid_x = cx-cab_w/2-bod_w*0.45-wr
            rear_x = cx-cab_w/2-bod_w+14*s-wr
            wheel_y = cy-bod_h/2-wr*2.1
            Ellipse(pos=(front_x, wheel_y), size=(wr*2, wr*2))
            Ellipse(pos=(mid_x,   wheel_y), size=(wr*2, wr*2))
            Ellipse(pos=(rear_x,  wheel_y), size=(wr*2, wr*2))
            hub = wr*0.35
            for wx in (front_x+wr-hub, mid_x+wr-hub, rear_x+wr-hub):
                Ellipse(pos=(wx, wheel_y+wr-hub), size=(hub*2, hub*2))


# ── Canvas-icon button base ───────────────────────────────────────────────────
class IconButton(Button):
    """Dark near-black button that draws its icon via _draw_icon() override."""
    CORNER = 8
    BG = (0.10, 0.11, 0.15, 1)
    BG_PRESS = (0.18, 0.20, 0.26, 1)

    def __init__(self, **kwargs):
        super().__init__(background_normal='', background_color=(0, 0, 0, 0), **kwargs)
        self._pressed = False
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *a):
        self.canvas.before.clear()
        self.canvas.after.clear()
        bg = self.BG_PRESS if self._pressed else self.BG
        with self.canvas.before:
            Color(*bg)
            RoundedRectangle(pos=self.pos, size=self.size,
                             radius=[self.CORNER])
        self._draw_icon()

    def _draw_icon(self):
        pass   # override in subclass

    def on_press(self):
        self._pressed = True
        self._redraw()

    def on_release(self):
        self._pressed = False
        self._redraw()


# ── START / PAUSE button ──────────────────────────────────────────────────────
class StartPauseButton(IconButton):
    """Dark icon button showing assets/play.png or assets/pause.png."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._playing = False
        self._img = None
        self._src_play = os.path.join(_asset_dir(), 'play.png')
        self._src_pause = os.path.join(_asset_dir(), 'pause.png')
        for path, label in ((self._src_play, 'play'), (self._src_pause, 'pause')):
            if not os.path.exists(path):
                print('ICON', label, path,
                      'MISSING — place a 256x256 RGBA PNG there')
        src = self._src_play if os.path.exists(self._src_play) else None
        if src:
            self._img = KivyImage(source=src, allow_stretch=True,
                                  keep_ratio=True, size_hint=(None, None))
            self.add_widget(self._img)

    def set_playing(self, val):
        self._playing = val
        if self._img is not None:
            new_src = self._src_pause if val else self._src_play
            if os.path.exists(new_src):
                self._img.source = new_src
        self._redraw()

    def _draw_icon(self):
        if self._img is None:
            return
        w, h = self.size
        sz = min(w, h) * 0.65
        self._img.size = (sz, sz)
        self._img.pos = (self.x + (w - sz) / 2, self.y + (h - sz) / 2)


# ── UNDO / REDO toggle button ─────────────────────────────────────────────────
class UndoRedoButton(IconButton):
    """Single dark icon button that shows assets/undo.png or assets/redo.png
    depending on which action currently makes sense.
    Call set_mode('undo' | 'redo' | None) — None disables/dims the button."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mode = None   # 'undo' | 'redo' | None (disabled)
        self._src_undo = os.path.join(_asset_dir(), 'undo.png')
        self._src_redo = os.path.join(_asset_dir(), 'redo.png')
        for path, label in ((self._src_undo, 'undo'), (self._src_redo, 'redo')):
            if not os.path.exists(path):
                print('ICON', label, path,
                      'MISSING — place a 256x256 RGBA PNG there')
        # Pre-load BOTH icons once at construction time and just toggle which
        # one is visible. Swapping an Image widget's `source` at runtime
        # (e.g. undo.png -> redo.png) is reliable on desktop GL but has
        # been flaky on some Android GPU/driver combos — the texture
        # reload silently fails to show. Loading both up front and only
        # changing opacity avoids that runtime-reload path entirely.
        self._img_undo = None
        self._img_redo = None
        if os.path.exists(self._src_undo):
            self._img_undo = KivyImage(source=self._src_undo, allow_stretch=True,
                                       keep_ratio=True, size_hint=(None, None),
                                       opacity=0.25)
            self.add_widget(self._img_undo)
        if os.path.exists(self._src_redo):
            self._img_redo = KivyImage(source=self._src_redo, allow_stretch=True,
                                       keep_ratio=True, size_hint=(None, None),
                                       opacity=0)
            self.add_widget(self._img_redo)
        self._update_visual()

    def set_mode(self, mode):
        """mode: 'undo' to show/enable the undo icon, 'redo' to show/enable
        the redo icon, or None to disable and dim the button."""
        self._mode = mode
        self._update_visual()

    def _update_visual(self):
        # Toggle opacity on the two pre-loaded images — never touch .source
        if self._img_undo is not None:
            self._img_undo.opacity = (
                0 if self._mode == 'redo' else (1.0 if self._mode else 0.25))
        if self._img_redo is not None:
            self._img_redo.opacity = 1.0 if self._mode == 'redo' else 0
        self._redraw()

    def _draw_icon(self):
        w, h = self.size
        sz = min(w, h) * 0.65
        pos = (self.x + (w - sz) / 2, self.y + (h - sz) / 2)
        if self._img_undo is not None:
            self._img_undo.size = (sz, sz)
            self._img_undo.pos = pos
        if self._img_redo is not None:
            self._img_redo.size = (sz, sz)
            self._img_redo.pos = pos
        if self._img_undo is not None or self._img_redo is not None:
            return
        # Fallback vector icon — used only if undo.png/redo.png can't be
        # found (e.g. present on the dev machine but not yet bundled into
        # an Android build). Keeps the button from rendering blank.
        self.canvas.after.clear()
        if w < 4 or h < 4:
            return
        cx, cy = self.x + w / 2, self.y + h / 2
        r = min(w, h) * 0.22
        lw = max(2.0, min(w, h) * 0.05)
        alpha = 0.95 if self._mode else 0.25
        # redo mirrors undo horizontally so the two are visually distinct
        flip = -1 if self._mode == 'redo' else 1
        start_deg, tip_deg = 485, 215   # ~270° sweep, arrowhead at tip_deg
        with self.canvas.after:
            Color(1, 1, 1, alpha)
            Line(circle=(cx, cy, r, tip_deg, start_deg),
                 width=lw, cap='round')
            ang = math.radians(tip_deg)
            tipx = cx + flip * r * math.cos(ang)
            tipy = cy + r * math.sin(ang)
            head = r * 0.95
            Triangle(points=[
                tipx - flip*head*0.55, tipy + head*0.35,
                tipx - flip*head*0.05, tipy - head*0.55,
                tipx + flip*head*0.55, tipy + head*0.15,
            ])


# ── LOCK / UNLOCK toggle button ───────────────────────────────────────────────
class LockButton(IconButton):
    """Icon button below the timer that shows assets/lock.png when unlocked
    and assets/unlock.png when locked. Pre-loads both textures at startup so
    there is never a runtime texture-reload (the same fix applied to Undo/Redo).
    Call set_locked(True/False) to switch state."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_locked = False
        self._src_lock = os.path.join(_asset_dir(), 'lock.png')
        self._src_unlock = os.path.join(_asset_dir(), 'unlock.png')
        for path, label in ((self._src_lock, 'lock'), (self._src_unlock, 'unlock')):
            if not os.path.exists(path):
                print('ICON', label, path,
                      'MISSING — place a 256x256 RGBA PNG there')
        self._img_lock = None
        self._img_unlock = None
        if os.path.exists(self._src_lock):
            self._img_lock = KivyImage(source=self._src_lock,
                                       allow_stretch=True, keep_ratio=True,
                                       size_hint=(None, None), opacity=1.0)
            self.add_widget(self._img_lock)
        if os.path.exists(self._src_unlock):
            self._img_unlock = KivyImage(source=self._src_unlock,
                                         allow_stretch=True, keep_ratio=True,
                                         size_hint=(None, None), opacity=0)
            self.add_widget(self._img_unlock)
        self._update_visual()

    def set_locked(self, locked):
        self._is_locked = locked
        self._update_visual()

    # Accent colours: blue when unlocked (tap to lock), amber when locked
    _COL_UNLOCKED = (0.20, 0.45, 0.65, 1)
    _COL_LOCKED = (0.65, 0.35, 0.10, 1)

    def _update_visual(self):
        # Show lock icon when unlocked, unlock icon when locked
        if self._img_lock:
            self._img_lock.opacity = 0 if self._is_locked else 1.0
        if self._img_unlock:
            self._img_unlock.opacity = 1.0 if self._is_locked else 0
        self.BG = self._COL_LOCKED if self._is_locked else self._COL_UNLOCKED
        self._redraw()

    def _draw_icon(self):
        w, h = self.size
        sz = min(w, h) * 0.60
        pos = (self.x + (w - sz) / 2, self.y + (h - sz) / 2)
        if self._img_lock:
            self._img_lock.size = (sz, sz)
            self._img_lock.pos = pos
        if self._img_unlock:
            self._img_unlock.size = (sz, sz)
            self._img_unlock.pos = pos
        if self._img_lock is not None or self._img_unlock is not None:
            return
        # Fallback: draw a simple padlock in canvas if both PNGs are missing
        self.canvas.after.clear()
        if w < 4 or h < 4:
            return
        cx, cy = self.x + w / 2, self.y + h / 2
        s = min(w, h) * 0.0032
        lw = max(1.8, min(w, h) * 0.045)
        with self.canvas.after:
            Color(1, 1, 1, 0.95)
            # shackle arc (open when unlocked, closed when locked)
            bw, bh = 28*s, 22*s
            if self._is_locked:
                Line(circle=(cx, cy + 10*s, 14*s, 0, 180), width=lw, cap='round')
            else:
                Line(circle=(cx + 14*s, cy + 10*s, 14*s, 60, 180),
                     width=lw, cap='round')
            # body
            Line(rounded_rectangle=(cx - bw/2, cy - 18*s, bw, 26*s, 4*s),
                 width=lw)
            # keyhole
            Ellipse(pos=(cx - 5*s, cy - 5*s), size=(10*s, 10*s))
            Line(points=[cx, cy - 5*s, cx, cy - 14*s], width=lw*0.8)


_ICON_FILES = {
    'CAR':  'car.png',  'MOTO': 'moto.png',
    'LRY':  'lry.png',  'LLRY': 'llry.png',
    'BUS':  'bus.png',
}


def _asset_dir():
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets'),
        os.path.join(os.getcwd(), 'assets'),
        os.path.join(os.path.expanduser('~'), 'assets'),
        'assets',
    ]
    print("ASSET_DIR candidates:")
    for d in candidates:
        exists = os.path.isdir(d)
        print(f"  {'OK' if exists else '--'} {d}")
        if exists:
            print(f"     contents: {os.listdir(d)}")
            return d
    print(f"  none found, defaulting to: {candidates[0]}")
    return candidates[0]


_ASSET_DIR = _asset_dir()
print("ASSET_DIR resolved to:", _ASSET_DIR)


def _icon_path(key):
    path = os.path.join(_ASSET_DIR, _ICON_FILES[key])
    exists = os.path.exists(path)
    print('ICON', key, path, 'OK' if exists else 'MISSING')
    return path if exists else None


# ── Square vehicle button ─────────────────────────────────────────────────────
class SquareVehicleButton(Button):
    CORNER_RADIUS = 8

    def __init__(self, key, circle_color, label_text, **kwargs):
        super().__init__(background_normal='', background_color=(0, 0, 0, 0), **kwargs)
        self.key = key
        self.circle_color = circle_color
        self.label_text = label_text
        self._pressed = False
        self._touch = None
        self._timeout_ev = None
        # cached bg colors — populated by first _redraw()
        cr = circle_color
        self._col_normal = (None, cr)
        self._col_press = ((1, 1, 1, 0.9),
                           (cr[0]*0.38, cr[1]*0.38, cr[2]*0.38, cr[3]))
        self._r = self.CORNER_RADIUS
        self._ring = 6
        self.bind(pos=self._redraw, size=self._redraw)

        self._img = None
        icon_path = _icon_path(key)
        if icon_path:
            self._img = KivyImage(source=icon_path, allow_stretch=True,
                                  keep_ratio=True, size_hint=(None, None))
            self.add_widget(self._img)

        self._lbl = Label(text=label_text, font_size=15, bold=True,
                          color=(1, 1, 1, 0.90), halign='center', valign='middle',
                          size_hint=(None, None))
        self.add_widget(self._lbl)
        self._redraw()

    def _redraw(self, *a):
        """Full redraw — called on layout changes only."""
        w, h = self.size
        r = self.CORNER_RADIUS
        cr = self.circle_color
        lbl_h = 24
        pad = 6
        # layout children
        self._lbl.size = (w, lbl_h)
        self._lbl.pos = (self.x, self.y + pad)
        self._lbl.text_size = self._lbl.size
        icon_zone_h = h - lbl_h - pad * 2
        icon_zone_y = self.y + lbl_h + pad
        if self._img:
            icon_sz = min(w, icon_zone_h) * 0.82
            self._img.size = (icon_sz, icon_sz)
            self._img.pos = (self.x + (w - icon_sz) / 2,
                             icon_zone_y + (icon_zone_h - icon_sz) / 2)
        else:
            self.canvas.after.clear()
            cx = self.x + w / 2
            cy = icon_zone_y + icon_zone_h / 2
            sz = min(w, icon_zone_h) * 0.92
            with self.canvas.after:
                draw_icon(self.canvas.after, self.key, cx, cy, sz)
        # store normal/dim colors for fast press recolor
        self._col_normal = (None, cr)
        self._col_press = ((1, 1, 1, 0.9),
                           (cr[0]*0.38, cr[1]*0.38, cr[2]*0.38, cr[3]))
        self._r = r
        self._ring = 6
        self._redraw_bg()

    def _redraw_bg(self):
        """Cheap background-only redraw — called on press/release."""
        self.canvas.before.clear()
        w, h = self.size
        with self.canvas.before:
            if self._pressed:
                Color(*self._col_press[0])
                RoundedRectangle(pos=(self.x - self._ring, self.y - self._ring),
                                 size=(w + self._ring*2, h + self._ring*2),
                                 radius=[self._r + self._ring])
                Color(*self._col_press[1])
            else:
                Color(*self._col_normal[1])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self._r])

    # Safety net: occasionally a touch is cancelled by the OS (e.g. a brief
    # accidental graze, or Android intercepting it for a system gesture)
    # and Kivy never delivers a matching on_touch_up. Without a timeout the
    # button would stay rendered as "pressed" forever, only clearing on the
    # next unrelated tap. This auto-releases the look (without counting a
    # tap) if no touch_up arrives within PRESS_TIMEOUT seconds.
    PRESS_TIMEOUT = 1.0

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        if self.collide_point(*touch.pos):
            # Defensive: if a previous touch was somehow never released
            # (the exact stuck-press scenario this fixes), clear it first
            # so this fresh press starts from a clean state.
            if self._pressed:
                self._clear_press()
            touch.grab(self)
            self._touch = touch
            self._pressed = True
            self._redraw_bg()
            self._arm_timeout()
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._cancel_timeout()
            self._touch = None
            self._pressed = False
            self._redraw_bg()
            if self.collide_point(*touch.pos):
                self.dispatch('on_release')
            return True
        return super().on_touch_up(touch)

    def _arm_timeout(self):
        self._cancel_timeout()
        self._timeout_ev = Clock.schedule_once(
            self._force_release, self.PRESS_TIMEOUT)

    def _cancel_timeout(self):
        if getattr(self, '_timeout_ev', None):
            self._timeout_ev.cancel()
            self._timeout_ev = None

    def _force_release(self, dt):
        # The grabbed touch never sent on_touch_up — release it ourselves.
        # This does NOT count as a tap, it only clears the stuck visual.
        self._clear_press()

    def _clear_press(self):
        self._cancel_timeout()
        if self._touch is not None:
            try:
                self._touch.ungrab(self)
            except Exception:
                pass
        self._touch = None
        self._pressed = False
        self._redraw_bg()

    def on_press(self):
        pass  # handled by on_touch_down

    def on_release(self):
        self._pressed = False
        self._redraw_bg()


# ── Grid cluster ──────────────────────────────────────────────────────────────
GRID_KEYS_LEFT = [
    ["LRY",  None],      # None → UNDO/REDO toggle button
    ["MOTO", "CAR"],
    ["LLRY", "BUS"],
]
GRID_KEYS_RIGHT = [
    [None,   "LRY"],     # None → START/PAUSE button
    ["CAR",  "MOTO"],
    ["BUS",  "LLRY"],
]


class SquareGridCluster(GridLayout):
    SEP = 3

    def __init__(self, on_tap, corner, timer_widget=None, on_undo=None,
                 on_redo=None, is_locked=None, **kwargs):
        grid_keys = GRID_KEYS_LEFT if corner == 'left' else GRID_KEYS_RIGHT
        super().__init__(cols=len(grid_keys[0]), rows=len(grid_keys),
                         spacing=self.SEP, padding=0, **kwargs)
        self.on_tap = on_tap
        self.corner = corner
        self._buttons = {}
        self._is_locked = is_locked or (lambda: False)

        for row in grid_keys:
            for key in row:
                if key is None:
                    if corner == 'right' and timer_widget is not None:
                        sp = StartPauseButton(size_hint=(1, 1))
                        sp.bind(on_release=lambda b: (
                            None if self._is_locked() else (
                                play_startpause(), timer_widget._toggle())))
                        timer_widget._ext_btn_ss = sp
                        self.add_widget(sp)
                    elif corner == 'left' and (on_undo is not None or on_redo is not None):
                        ub = UndoRedoButton(size_hint=(1, 1))
                        ub.bind(on_release=lambda b: (
                            None if self._is_locked() else (
                                haptic_tap(), play_startpause(),
                                on_undo() if ub._mode == 'undo'
                                else (on_redo() if ub._mode == 'redo' else None)))
                                if ub._mode else None)
                        self._undo_redo_btn = ub
                        self.add_widget(ub)
                    else:
                        self.add_widget(self._make_filler())
                else:
                    short, color = VEHICLES[key]
                    btn = SquareVehicleButton(key=key, circle_color=color,
                                              label_text=short, size_hint=(1, 1))
                    btn.bind(on_release=lambda b, k=key: self._tap(k))
                    self._buttons[key] = btn
                    self.add_widget(btn)

    def _make_filler(self):
        filler = BoxLayout()
        with filler.canvas.before:
            Color(0.13, 0.14, 0.18, 1)
            rect = Rectangle(pos=filler.pos, size=filler.size)
        filler._rect = rect

        def _upd(w, *a):
            w._rect.pos = w.pos
            w._rect.size = w.size
        filler.bind(pos=_upd, size=_upd)
        return filler

    def _tap(self, key):
        # Increment counter immediately so the UI feels instant,
        # then fire sound + haptic on a background thread so the main
        # thread / redraw is never blocked.
        # Both are suppressed when locked.
        self.on_tap(key)
        if self._is_locked():
            return
        import threading
        threading.Thread(target=lambda: (
            haptic_tap(), play_tap()), daemon=True).start()


# ── Summary chip ──────────────────────────────────────────────────────────────
class SummaryChip(Button):
    def __init__(self, chip_color, **kwargs):
        self._chip_color = chip_color
        self._dim = tuple(max(0, c*0.35) if i < 3 else c
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
    def __init__(self, on_minus, order=None, is_locked=None, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('spacing', 6)
        kwargs.setdefault('padding', [8, 6, 8, 6])
        super().__init__(**kwargs)
        self.on_minus = on_minus
        self.is_locked = is_locked or (lambda: False)
        self.counts = {k: 0 for k in VEHICLES}
        self.chips = {}
        for key in (order or SUMMARY_ORDER_LEFT):
            short, color = VEHICLES[key]
            btn = SummaryChip(chip_color=color, text=f"{short}: 0",
                              font_size=24, bold=True, color=(1, 1, 1, 1),
                              size_hint=(1, 1))
            btn.bind(on_release=lambda b, k=key: self._minus(k))
            self.chips[key] = (btn, short)
            self.add_widget(btn)

    def _minus(self, key):
        if self.is_locked():
            return
        if self.counts[key] > 0:
            self.counts[key] -= 1
            self._refresh(key)
            self.chips[key][0].flash()
            self.on_minus()
            import threading
            threading.Thread(target=lambda: (
                haptic_tap(), play_tap()), daemon=True).start()

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
        self._ext_btn_ss = None

        self.lbl = Label(text=self._fmt(DEFAULT_TIMER), font_size=BASE_FONT,
                         bold=True, color=(0.55, 0.92, 0.55, 1),
                         size_hint=(1, 1), halign='center', valign='middle')
        self.lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self.add_widget(self.lbl)

        row = BoxLayout(orientation='horizontal', size_hint=(1, None),
                        height=46, spacing=6, padding=[4, 0, 4, 0])
        self._btn_set = self._mk("SET",   (0.25, 0.35, 0.60, 1))
        self._btn_rst = self._mk("RESET", (0.55, 0.25, 0.25, 1))
        self._btn_set.bind(on_release=self._open_set)
        self._btn_rst.bind(on_release=self._reset_timer)
        row.add_widget(self._btn_set)
        row.add_widget(self._btn_rst)
        self.add_widget(row)

    def set_locked(self, locked):
        """Dim and disable the SET/RESET buttons and the play/pause button."""
        alpha = 0.25 if locked else 1.0
        self._btn_set.opacity = alpha
        self._btn_rst.opacity = alpha
        self._btn_set.disabled = locked
        self._btn_rst.disabled = locked
        if self._ext_btn_ss:
            self._ext_btn_ss.opacity = alpha
            self._ext_btn_ss.disabled = locked

    def _mk(self, t, bg):
        return Button(text=t, font_size=15, bold=True, color=(1, 1, 1, 1),
                      background_normal='', background_color=bg, size_hint=(1, 1))

    def _fmt(self, secs):
        m, s = divmod(max(0, int(secs)), 60)
        return f"{m:02d}:{s:02d}"

    def _toggle(self, *a):
        self._pause() if self._running else self._start()

    def _set_btn_state(self, running):
        if self._ext_btn_ss:
            self._ext_btn_ss.set_playing(running)

    def _start(self):
        if self._remaining <= 0:
            return
        self._running = True
        self._set_btn_state(True)
        self._stop_alert()
        self.lbl.color = (0.55, 0.92, 0.55, 1)
        self.lbl.font_size = BASE_FONT
        self._tick_ev = Clock.schedule_interval(self._tick, 1)

    def _pause(self):
        self._running = False
        self._set_btn_state(False)
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
        if self._alert_idx % 2 == 0:
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
        prev_duration = self._duration
        prev_m, prev_s = divmod(prev_duration, 60)

        content = BoxLayout(orientation='vertical', spacing=12, padding=20)
        content.add_widget(Label(text="Set Timer", font_size=20, bold=True,
                                 color=(1, 1, 1, 1), size_hint=(1, None), height=34,
                                 halign='center'))
        time_row = BoxLayout(orientation='horizontal', size_hint=(1, None),
                             height=70, spacing=0)

        def _inp(hint):
            return TextInput(hint_text=hint, text="", font_size=36,
                             foreground_color=(1, 1, 1, 1),
                             hint_text_color=(0.5, 0.5, 0.5, 1),
                             background_color=(0.15, 0.17, 0.21, 1),
                             cursor_color=(1, 1, 1, 1), size_hint=(1, 1),
                             multiline=False, halign='center', input_filter='int')
        inp_m = _inp("MM")
        inp_s = _inp("SS")
        colon = Label(text=":", font_size=36, bold=True, color=(1, 1, 1, 1),
                      size_hint=(None, 1), width=28)
        time_row.add_widget(inp_m)
        time_row.add_widget(colon)
        time_row.add_widget(inp_s)
        content.add_widget(time_row)

        btns = BoxLayout(orientation='horizontal', spacing=10,
                         size_hint=(1, None), height=56)
        cancel = self._mk("Cancel", (0.30, 0.32, 0.38, 1))
        confirm = self._mk("Set",    (0.20, 0.55, 0.30, 1))
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)

        popup = Popup(title='Set Timer', title_size=20, content=content,
                      size_hint=(0.55, None), height=280,
                      pos_hint={'center_x': 0.5, 'top': 0.98},
                      background_color=(0.14, 0.15, 0.20, 1),
                      title_color=(1, 1, 1, 1),
                      separator_color=(0.25, 0.27, 0.32, 1))

        def _cancel(*a):
            self._duration = prev_duration
            self._remaining = prev_duration
            self.lbl.text = self._fmt(prev_duration)
            popup.dismiss()

        def _apply(*a):
            try:
                m_val = int(inp_m.text.strip()
                            ) if inp_m.text.strip() else prev_m
                s_val = int(inp_s.text.strip()
                            ) if inp_s.text.strip() else prev_s
                s_val = max(0, min(59, s_val))
                self._duration = max(1, m_val*60 + s_val)
            except Exception:
                self._duration = prev_duration
            self._remaining = self._duration
            self.lbl.text = self._fmt(self._remaining)
            self.lbl.color = (0.55, 0.92, 0.55, 1)
            self.lbl.font_size = BASE_FONT
            self._stop_alert()
            popup.dismiss()

        cancel.bind(on_release=_cancel)
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

        for text, hint, cy in [
            ('PATSB',           72, 0.60),
            ('Traffic Counter', 26, 0.46),
        ]:
            self.add_widget(Label(text=text, font_size=hint,
                                  bold=(hint == 72),
                                  color=(0.10, 0.45, 0.90, 1) if hint == 72 else (
                                      0.65, 0.70, 0.78, 1),
                                  halign='center', valign='middle',
                                  pos_hint={'center_x': 0.5, 'center_y': cy},
                                  size_hint=(1, None), height=hint+18))

        self._status = Label(text='Initialising...', font_size=18,
                             color=(0.40, 0.45, 0.52, 1), halign='center', valign='middle',
                             pos_hint={'center_x': 0.5, 'center_y': 0.28},
                             size_hint=(1, None), height=28)
        self.add_widget(self._status)

        self._bar_widget = FloatLayout(size_hint=(0.5, None), height=14,
                                       pos_hint={'center_x': 0.5, 'center_y': 0.16})
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
            fill_w = max(bh, bw*self._bar_progress)
            RoundedRectangle(pos=(w.x, w.y), size=(fill_w, bh), radius=[bh/2])

    def _animate(self, dt):
        gap = self._target - self._bar_progress
        if gap > 0:
            self._bar_progress += max(0.002, gap*0.08)
        self._bar_progress = min(self._target, self._bar_progress)
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
        self._undo_snapshot = None
        self._redo_snapshot = None
        self._locked = False

        top = BoxLayout(size_hint=(1, None), height=TOP_H,
                        pos_hint={'x': 0, 'top': 1},
                        spacing=6, padding=[6, 6, 6, 6])
        self.j1_summary = JunctionSummary(on_minus=self._on_minus,
                                          order=SUMMARY_ORDER_LEFT,
                                          is_locked=lambda: self._locked,
                                          size_hint=(0.42, 1))
        self.reset_btn = Button(text="RESET ALL", font_size=16, bold=True,
                                color=(1, 1, 1, 1), background_normal='',
                                background_color=(0.75, 0.20, 0.20, 1),
                                size_hint=(0.16, 1))
        self.reset_btn.bind(on_release=self._confirm_reset)
        self.j2_summary = JunctionSummary(on_minus=self._on_minus,
                                          order=SUMMARY_ORDER_RIGHT,
                                          is_locked=lambda: self._locked,
                                          size_hint=(0.42, 1))
        top.add_widget(self.j1_summary)
        top.add_widget(self.reset_btn)
        top.add_widget(self.j2_summary)
        self.add_widget(top)

        self.timer = TimerWidget(size_hint=(1, 1))

        # Lock button lives below the timer in the centre column.
        # It is the ONLY thing that stays tappable when locked.
        LOCK_BTN_H = 48
        self.lock_btn = LockButton(size_hint=(1, None), height=LOCK_BTN_H)
        self.lock_btn.bind(on_release=self._toggle_lock)
        self._lock_btn_h = LOCK_BTN_H

        self.j1_cluster = SquareGridCluster(
            on_tap=self._j1_tap, corner='left',
            on_undo=self._do_undo, on_redo=self._do_redo,
            is_locked=lambda: self._locked,
            size_hint=(None, None), pos_hint={'x': 0, 'y': 0})

        self.j2_cluster = SquareGridCluster(
            on_tap=self._j2_tap, corner='right',
            timer_widget=self.timer,
            is_locked=lambda: self._locked,
            size_hint=(None, None), pos_hint={'right': 1, 'y': 0})

        self.add_widget(self.j1_cluster)
        self.add_widget(self.j2_cluster)

        self.timer_box = BoxLayout(orientation='vertical', spacing=6,
                                   size_hint=(None, None),
                                   pos_hint={'center_x': 0.5})
        self.timer_box.add_widget(self.timer)
        self.timer_box.add_widget(self.lock_btn)
        self.add_widget(self.timer_box)

        self.bind(size=self._layout)
        self.reset_btn.bind(size=self._layout)
        self.j1_summary.chips['MOTO'][0].bind(
            pos=self._layout, size=self._layout)
        self.j2_summary.chips['CAR'][0].bind(
            pos=self._layout,  size=self._layout)
        self._load()

    def _layout(self, *a):
        W, H = self.size
        cluster_h = H - TOP_H

        moto_chip = self.j1_summary.chips['MOTO'][0]
        left_grid_w = moto_chip.right if moto_chip.width > 1 else W*0.42

        car_chip = self.j2_summary.chips['CAR'][0]
        right_grid_x = car_chip.x if car_chip.width > 1 else W*0.58
        right_grid_w = W - right_grid_x

        self.j1_cluster.size = (left_grid_w, cluster_h)
        self.j1_cluster.pos = (0, 0)
        self.j2_cluster.size = (right_grid_w, cluster_h)
        self.j2_cluster.pos = (right_grid_x, 0)

        timer_w = self.reset_btn.width if self.reset_btn.width > 1 else W*0.16
        total_box_h = min(TIMER_H + self._lock_btn_h + 6, cluster_h - 12)
        timer_h = total_box_h - self._lock_btn_h - 6
        self.timer_box.size = (timer_w, total_box_h)
        self.timer_box.pos = (W/2 - timer_w/2, (cluster_h - total_box_h)/2)

    def _j1_tap(self, key):
        if self._locked:
            return
        self.j1_summary.increment(key)
        self._save()

    def _j2_tap(self, key):
        if self._locked:
            return
        self.j2_summary.increment(key)
        self._save()

    def _on_minus(self):
        """Proxy passed to JunctionSummary — honours the lock state.
        JunctionSummary calls this after it has already decremented, so if
        locked we put the count back and skip the save."""
        # The actual guard lives in JunctionSummary._minus which checks
        # _locked via the on_minus gate below — see _toggle_lock.
        self._save()

    def _toggle_lock(self, *a):
        self._locked = not self._locked
        self.lock_btn.set_locked(self._locked)
        if self._locked:
            # Auto-pause the timer — must be manually resumed after unlock
            self.timer._pause()
            self.reset_btn.disabled = True
            self.reset_btn.opacity = 0.25
            self.timer.set_locked(True)
            if hasattr(self.j1_cluster, '_undo_redo_btn'):
                self.j1_cluster._undo_redo_btn.disabled = True
                self.j1_cluster._undo_redo_btn.opacity = 0.25
            for summary in (self.j1_summary, self.j2_summary):
                for btn, _ in summary.chips.values():
                    btn.disabled = True
                    btn.opacity = 0.35
            for cluster in (self.j1_cluster, self.j2_cluster):
                for btn in cluster._buttons.values():
                    btn.disabled = True
                    btn.opacity = 0.35
        else:
            # Unlock — timer stays paused, user must press play to resume
            self.reset_btn.disabled = False
            self.reset_btn.opacity = 1.0
            self.timer.set_locked(False)
            if hasattr(self.j1_cluster, '_undo_redo_btn'):
                self.j1_cluster._undo_redo_btn.disabled = False
                self.j1_cluster._undo_redo_btn.opacity = 1.0
            for summary in (self.j1_summary, self.j2_summary):
                for btn, _ in summary.chips.values():
                    btn.disabled = False
                    btn.opacity = 1.0
            for cluster in (self.j1_cluster, self.j2_cluster):
                for btn in cluster._buttons.values():
                    btn.disabled = False
                    btn.opacity = 1.0

    def _save(self, *a):
        # Debounce: cancel any pending save and reschedule.
        # The actual write is deferred 0.5 s and runs on a background thread
        # so the main/UI thread is never blocked by file I/O.
        if hasattr(self, '_save_ev') and self._save_ev:
            self._save_ev.cancel()
        self._save_ev = Clock.schedule_once(self._save_bg, 0.5)

    def _save_bg(self, dt=None):
        import threading
        data = {'j1': self.j1_summary.get_counts(),
                'j2': self.j2_summary.get_counts()}

        def _write():
            try:
                with open(SAVE_FILE, 'w') as f:
                    json.dump(data, f)
            except Exception as e:
                print("Save error:", e)
        threading.Thread(target=_write, daemon=True).start()

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
        cancel = _mk("Cancel", (0.30, 0.32, 0.38, 1))
        confirm = _mk("Reset",  (0.75, 0.20, 0.20, 1))
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
        # Starting a brand-new action clears any pending redo history.
        self._undo_snapshot = (
            self.j1_summary.get_counts(),
            self.j2_summary.get_counts(),
        )
        self._redo_snapshot = None
        self.j1_summary.reset()
        self.j2_summary.reset()
        self.timer.stop_alert()
        self.timer.reset_to_default()
        self._save()
        self._set_undo_redo_mode('undo')

    def _do_undo(self):
        if self._undo_snapshot is None:
            return
        # Stash the current (post-reset) state so Redo can re-apply it.
        self._redo_snapshot = (
            self.j1_summary.get_counts(),
            self.j2_summary.get_counts(),
        )
        j1_snap, j2_snap = self._undo_snapshot
        self.j1_summary.set_counts(j1_snap)
        self.j2_summary.set_counts(j2_snap)
        self._undo_snapshot = None
        self._save()
        self._set_undo_redo_mode('redo')

    def _do_redo(self):
        if self._redo_snapshot is None:
            return
        # Stash the current (undone) state so Undo can restore it again.
        self._undo_snapshot = (
            self.j1_summary.get_counts(),
            self.j2_summary.get_counts(),
        )
        j1_snap, j2_snap = self._redo_snapshot
        self.j1_summary.set_counts(j1_snap)
        self.j2_summary.set_counts(j2_snap)
        self._redo_snapshot = None
        self._save()
        self._set_undo_redo_mode('undo')

    def _set_undo_redo_mode(self, mode):
        if hasattr(self.j1_cluster, '_undo_redo_btn'):
            self.j1_cluster._undo_redo_btn.set_mode(mode)


class TrafficCounterApp(App):
    def build(self):
        Window.fullscreen = 'auto'
        Window.orientation = 'landscape'
        self._root = FloatLayout()
        self._root.add_widget(LoadingScreen(on_done=self._launch))
        return self._root

    def _launch(self):
        self._root.clear_widgets()
        self._root.add_widget(RootLayout())

    def on_start(self):
        if platform == 'android':
            _init_haptic()
            Window.update_viewport()
            # Replace the default android touch provider with one that has
            # zero postprocessing — this is the only reliable way on a
            # packaged APK since the config file may already be baked in.
            try:
                from kivy.base import EventLoop
                from kivy.input.providers.androidjoystick import AndroidMotionEventProvider
                # Remove existing providers and re-add without postproc
                EventLoop.remove_input_provider_by_name('android')
                EventLoop.add_input_provider(
                    AndroidMotionEventProvider('android', ''))
            except Exception as e:
                print("Touch provider override failed:", e)

    def on_stop(self):
        # Flush any pending debounced save immediately on app exit.
        root = self._root.children[0] if self._root.children else None
        if isinstance(root, RootLayout):
            root._save_bg()


if __name__ == '__main__':
    TrafficCounterApp().run()
