"""
PATSB Traffic Counter — Kivy landscape, square grid clusters with haptic feedback
"""
import os
import sys
# FIX: KIVY_GL_BACKEND=angle_sdl2 forcing REMOVED from here. It was
# originally added to solve a build-time problem (GitHub's headless CI
# Windows runner has no real GPU, only software OpenGL 1.1), but it was
# wrongly left applying at RUNTIME too — meaning every actual end-user
# machine, including ones with perfectly good real GPUs, was being forced
# through the ANGLE→D3D12 translation layer instead of Kivy's normal
# default backend. That forcing turned out to be the actual cause of a
# silent crash a few hundred ms into startup on real hardware. The CI-only
# fix now lives solely in build-windows.yml's PyInstaller build step,
# where it can't affect the shipped exe's own runtime behavior at all.

# FIX (crash diagnostics): the console window can close within a fraction
# of a second of a crash — far too fast for anyone to read, let alone
# select and copy, live. Redirect stdout/stderr to a persistent file
# instead, so every print() and any uncaught-exception traceback survives
# regardless of how fast the process dies. Written before any other
# imports so absolutely nothing can be lost before this is in place.
if getattr(sys, 'frozen', False) and sys.platform == 'win32':
    try:
        _appdata = os.environ.get('APPDATA')
        if _appdata:
            _log_dir = os.path.join(_appdata, 'PATSB_Traffic_Counter')
            os.makedirs(_log_dir, exist_ok=True)
            _log_path = os.path.join(_log_dir, 'crash_log.txt')
            _log_f = open(_log_path, 'w', buffering=1,
                          encoding='utf-8', errors='replace')
            sys.stdout = _log_f
            sys.stderr = _log_f
            print('=== PATSB Traffic Counter crash_log.txt ===')

            import traceback as _tb

            def _log_uncaught(exc_type, exc_value, exc_traceback):
                print('UNCAUGHT EXCEPTION:')
                _tb.print_exception(exc_type, exc_value, exc_traceback)
                sys.stdout.flush()
            sys.excepthook = _log_uncaught
    except Exception:
        pass

from kivy.config import Config
import math
import json
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image as KivyImage
from kivy.core.audio import SoundLoader
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.utils import platform
from kivy.graphics import (Color, Ellipse, Line, RoundedRectangle,
                           Rectangle, Triangle, Bezier, InstructionGroup)
from kivy.clock import Clock
import time
# Must be set before ANY kivy import — forces zero-delay touch on APK
os.environ['KIVY_BCM_DISPMANX_ID'] = '0'
os.environ['KCFG_POSTPROC_DOUBLE_TAP_TIME'] = '0'
os.environ['KCFG_POSTPROC_DOUBLE_TAP_DISTANCE'] = '0'
os.environ['KCFG_POSTPROC_RETAIN_TIME'] = '0'
os.environ['KCFG_POSTPROC_RETAIN_DISTANCE'] = '0'
os.environ['KCFG_POSTPROC_JITTER_DISTANCE'] = '0'


if platform == 'android':
    Config.set('graphics', 'resizable', '0')
else:
    # FIX: desktop use should allow resizing and minimizing the window
    # (e.g. to work alongside video footage on the same screen) — only
    # mobile needs a fixed size.
    Config.set('graphics', 'resizable', '1')
Config.set('graphics', 'show_cursor', '1')
# FIX: Kivy's Window has its OWN built-in "Escape quits the app" behavior
# enabled by default, completely separate from our _on_keyboard handler.
# Even though our handler correctly opens Reset All on Escape, Kivy's
# internal default was ALSO independently closing the whole window on the
# same keypress some of the time. This disables that built-in behavior
# entirely, leaving Escape's meaning solely up to our own handler.
Config.set('kivy', 'exit_on_escape', '0')
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
    # FIX: stop the window from being resized smaller than everything can
    # still fit and stay usable/visible.
    Window.minimum_width = 960
    # FIX: lowered way down (from 560) so the window can be squeezed into
    # a thin horizontal strip — useful when pinned on top of a video
    # player. Everything still lays out proportionally at this height,
    # just smaller; below ~150 things start getting genuinely unusable.
    Window.minimum_height = 150

# FIX: tracks whether the app is currently in the foreground. Used by
# TimerWidget so the alarm sound is suppressed while the app is minimised
# and only plays once the user reopens it — see App.on_pause/on_resume.
_APP_FOREGROUND = True

# Tracks whether the app is currently in the foreground. Set by
# TrafficCounterApp.on_pause/on_resume. Used so the timer never plays its
# alert sound while the app is backgrounded — only once it's reopened.
_APP_FOREGROUND = True


def _config_dir():
    """Where user-editable/persistent files (save data, keymap) live.
    FIX: previously used the exe's own folder (via sys.executable) once
    frozen. That broke in practice — the exe can end up inside a
    OneDrive-synced folder (Desktop, Documents, etc.), where file writes
    can genuinely HANG while OneDrive's sync/lock mechanism intervenes,
    freezing the whole app with no error at all. %APPDATA% is the
    standard, always-local, never-cloud-synced-by-default location for
    exactly this kind of per-user app data."""
    if os.name == 'nt':
        appdata = os.environ.get('APPDATA')
        if appdata:
            d = os.path.join(appdata, 'PATSB_Traffic_Counter')
            try:
                os.makedirs(d, exist_ok=True)
                return d
            except Exception:
                pass
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


SAVE_FILE = os.path.join(_config_dir(), "traffic_save.json")
DEFAULT_TIMER = 15 * 60

# ── Keyboard shortcut customization ──────────────────────────────────────────
# FIX: some colleagues may prefer different keys than the default layout —
# this makes every shortcut configurable via a plain-text keymap.json file
# that sits next to the app, instead of being hardcoded. If the file
# doesn't exist yet, sensible defaults are written out automatically so
# there's something to find and edit.
DEFAULT_KEYMAP = {
    # Left junction (swapped with right — this side now uses what was
    # previously the right junction's keys)
    'j1_car': 's', 'j1_moto': 'a', 'j1_lorry': 'q', 'j1_bus': 'x', 'j1_llry': 'z',
    # Right junction (swapped with left)
    'j2_car': 'k', 'j2_moto': 'l', 'j2_lorry': 'p', 'j2_bus': 'm', 'j2_llry': ',',
    # Global controls
    'timer_pause': 'space',
    'timer_set':   't',
    'lock':        'g',
    'pin':         'b',
    'undo':        'z',   # used with Ctrl — Ctrl-combos are always checked
                          # before bare vehicle keys, so this is safe even
                          # though 'z' is also a vehicle key above.
    'redo':        'y',
    'reset':       'escape',
    'help':        'f1',
    'dock_top':    'up',
    'dock_bottom': 'down',
}

# Names the "keyboard" (global hotkey) library and our own key==NNN checks
# both understand for non-printable keys. Anything not in here is treated
# as a literal single printable character.
_SPECIAL_KEY_CODES = {
    'escape': 27, 'enter': 13, 'f1': 282, 'up': 273, 'down': 274,
    'space': 32, 'tab': 9, 'backspace': 8,
}
_CODE_TO_SPECIAL_NAME = {v: k for k, v in _SPECIAL_KEY_CODES.items()}


def _keypress_to_keyval(key, codepoint):
    """Inverse of the lookup above — converts an actual captured keypress
    (from the in-app rebind UI) back into a keymap.json-style value."""
    if key in _CODE_TO_SPECIAL_NAME:
        return _CODE_TO_SPECIAL_NAME[key]
    if codepoint:
        return codepoint.lower()
    return None


def _keymap_path():
    return os.path.join(_config_dir(), 'keymap.json')


def _load_keymap():
    km = dict(DEFAULT_KEYMAP)
    if platform == 'android':
        return km  # customization is a desktop-only concept
    path = _keymap_path()
    print('KEYMAP: config dir is', _config_dir())
    try:
        if os.path.exists(path):
            print('KEYMAP: reading', path)
            with open(path, 'r') as f:
                loaded = json.load(f)
            for k, v in loaded.items():
                if k in km and isinstance(v, str) and v.strip():
                    km[k] = v.strip().lower()
            print('KEYMAP: loaded custom bindings from', path)
        else:
            print('KEYMAP: writing new default file to', path)
            with open(path, 'w') as f:
                json.dump(DEFAULT_KEYMAP, f, indent=2)
            print('KEYMAP: wrote default keymap.json to', path,
                  '— edit this file to customize shortcuts')
    except Exception as e:
        print('KEYMAP: failed to load/write keymap.json (%s) — using '
              'built-in defaults' % e)
    return km


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


def _get_screen_size():
    """Physical screen resolution, used for docking the window to the top
    or bottom edge (Ctrl+Up/Ctrl+Down). Windows-only for now — that's the
    desktop platform this is actually built/used for; other desktop OSes
    just won't support docking (the shortcut becomes a no-op) rather than
    risk something unreliable."""
    if platform == 'win':
        try:
            import ctypes
            user32 = ctypes.windll.user32
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except Exception:
            return None
    return None


# ── Haptic feedback ──────────────────────────────────────────────────────────
_haptic_flash_ev = None
_vibrator = None
_VibrationEffect = None


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
    """Dark near-black button with custom touch handling that mirrors
    SquareVehicleButton — bypasses Kivy's standard Button dispatch which
    is unreliable on some Android drivers."""
    CORNER = 8
    BG = (0.10, 0.11, 0.15, 1)
    BG_PRESS = (0.18, 0.20, 0.26, 1)

    def __init__(self, **kwargs):
        # FIX: same texture-reload issue as SummaryChip/SafeButton — even
        # though background_color is fully transparent here, Kivy still
        # swaps the underlying background_down/disabled source on every
        # state change unless it's blanked too.
        super().__init__(background_normal='', background_down='',
                         background_disabled_normal='', background_disabled_down='',
                         background_color=(0, 0, 0, 0), **kwargs)
        self._pressed = False
        self._touch = None
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
        pass

    # FIX: replace on_press/on_release method overrides with explicit
    # on_touch_down/on_touch_up — the same pattern used by SquareVehicleButton
    # which works reliably on Android. Kivy's standard Button dispatch
    # (on_press/on_release events) silently fails on some Android configs.
    def on_touch_down(self, touch):
        if self.disabled:
            return False
        if self.collide_point(*touch.pos):
            # FIX: clear any stale grab before granting a new one. Android
            # sometimes delivers on_touch_down twice for one physical tap;
            # without this, Kivy's grab list gets two entries for the same
            # touch and on_touch_up dispatches on_release twice. Same
            # dedupe pattern as SquareVehicleButton/SummaryChip — a
            # same-frame check, not a timer, so it adds no delay.
            if getattr(self, '_touch', None) is not None:
                try:
                    self._touch.ungrab(self)
                except Exception:
                    pass
                self._touch = None
            touch.grab(self)
            self._touch = touch
            self._pressed = True
            self._redraw()
            return True
        return False

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._touch = None
            self._pressed = False
            self._redraw()
            if self.collide_point(*touch.pos):
                self.dispatch('on_release')
            return True
        return False


# ── Clickable label (used for the shortcuts bar → opens rebind UI) ───────────
class _ClickableLabel(Label):
    def __init__(self, on_press=None, **kwargs):
        super().__init__(**kwargs)
        self._on_press_cb = on_press

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            if self._on_press_cb:
                self._on_press_cb()
            return True
        return super().on_touch_up(touch)


# ── Safe plain-text button (Cancel/Confirm/Set/Reset etc.) ───────────────────
class SafeButton(Button):
    """Plain rectangular text button using the same explicit touch-grab
    handling as IconButton/SquareVehicleButton instead of Kivy's default
    ButtonBehavior dispatch, which is unreliable on some Android drivers
    and was causing popup buttons to need two taps (and occasionally
    double-fire, opening a second overlapping popup)."""

    def __init__(self, **kwargs):
        # FIX: same Android texture-reload issue as SummaryChip — Kivy
        # swaps in a real background_down/background_disabled texture
        # whenever self.state flips, which felt like tap lag. Blank them
        # by default here so every call site gets the fix even though only
        # background_normal was explicitly set at each call site.
        kwargs.setdefault('background_down', '')
        kwargs.setdefault('background_disabled_normal', '')
        kwargs.setdefault('background_disabled_down', '')
        super().__init__(**kwargs)
        self._touch = None

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        if self.collide_point(*touch.pos):
            # FIX: clear any stale grab before granting a new one — see
            # SummaryChip/IconButton for the full rationale. Prevents a
            # duplicate on_touch_down from causing two grab-list entries
            # and therefore two on_release dispatches for one tap, with no
            # added delay (same-frame check, not a timer).
            if self._touch is not None:
                try:
                    self._touch.ungrab(self)
                except Exception:
                    pass
                self._touch = None
            touch.grab(self)
            self._touch = touch
            self.state = 'down'
            return True
        return False

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._touch = None
            self.state = 'normal'
            if self.collide_point(*touch.pos):
                self.dispatch('on_release')
            return True
        return False


# ── START / PAUSE button ──────────────────────────────────────────────────────
class StartPauseButton(IconButton):
    """Dark icon button showing assets/play.png or assets/pause.png.
    Both images are pre-loaded and toggled by opacity — no runtime source
    swap — to avoid the Android texture-reload bug."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._playing = False
        self._img_play = None
        self._img_pause = None
        src_play = os.path.join(_asset_dir(), 'play.png')
        src_pause = os.path.join(_asset_dir(), 'pause.png')
        for path, label in ((src_play, 'play'), (src_pause, 'pause')):
            if not os.path.exists(path):
                print('ICON', label, path,
                      'MISSING — place a 256x256 RGBA PNG there')
        if os.path.exists(src_play):
            self._img_play = KivyImage(source=src_play, allow_stretch=True,
                                       keep_ratio=True, size_hint=(None, None),
                                       opacity=1.0)
            self.add_widget(self._img_play)
        if os.path.exists(src_pause):
            self._img_pause = KivyImage(source=src_pause, allow_stretch=True,
                                        keep_ratio=True, size_hint=(None, None),
                                        opacity=0)
            self.add_widget(self._img_pause)

    def set_playing(self, val):
        self._playing = val
        # Toggle opacity only — never swap .source at runtime (unreliable on Android)
        if self._img_play:
            self._img_play.opacity = 0 if val else 1.0
        if self._img_pause:
            self._img_pause.opacity = 1.0 if val else 0
        self._redraw()

    def _draw_icon(self):
        w, h = self.size
        sz = min(w, h) * 0.65
        pos = (self.x + (w - sz) / 2, self.y + (h - sz) / 2)
        if self._img_play:
            self._img_play.size = (sz, sz)
            self._img_play.pos = pos
        if self._img_pause:
            self._img_pause.size = (sz, sz)
            self._img_pause.pos = pos


# ── UNDO / REDO toggle button ─────────────────────────────────────────────────
class UndoRedoButton(IconButton):
    """Single slot that shows undo.png or redo.png via opacity toggle."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mode = None
        self._img_undo = None
        self._img_redo = None
        src_undo = os.path.join(_asset_dir(), 'undo.png')
        src_redo = os.path.join(_asset_dir(), 'redo.png')
        for path, label in ((src_undo, 'undo'), (src_redo, 'redo')):
            if not os.path.exists(path):
                print('ICON', label, path,
                      'MISSING — place a 256x256 RGBA PNG there')
        if os.path.exists(src_undo):
            self._img_undo = KivyImage(source=src_undo, allow_stretch=True,
                                       keep_ratio=True, size_hint=(None, None),
                                       opacity=0.25)
            self.add_widget(self._img_undo)
        if os.path.exists(src_redo):
            self._img_redo = KivyImage(source=src_redo, allow_stretch=True,
                                       keep_ratio=True, size_hint=(None, None),
                                       opacity=0)
            self.add_widget(self._img_redo)
        self._update_visual()

    def set_mode(self, mode):
        self._mode = mode
        self._update_visual()

    def _update_visual(self):
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
        # Fallback vector if both PNGs missing
        self.canvas.after.clear()
        if w < 4 or h < 4:
            return
        cx, cy = self.x + w / 2, self.y + h / 2
        r = min(w, h) * 0.22
        lw = max(2.0, min(w, h) * 0.05)
        alpha = 0.95 if self._mode else 0.25
        flip = -1 if self._mode == 'redo' else 1
        start_deg, tip_deg = 485, 215
        with self.canvas.after:
            Color(1, 1, 1, alpha)
            Line(circle=(cx, cy, r, tip_deg, start_deg), width=lw, cap='round')
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
    """Shows lock.png when unlocked, unlock.png when locked."""

    _COL_UNLOCKED = (0.20, 0.45, 0.65, 1)
    _COL_LOCKED = (0.65, 0.35, 0.10, 1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_locked = False
        self._img_lock = None
        self._img_unlock = None
        src_lock = os.path.join(_asset_dir(), 'lock.png')
        src_unlock = os.path.join(_asset_dir(), 'unlock.png')
        for path, label in ((src_lock, 'lock'), (src_unlock, 'unlock')):
            if not os.path.exists(path):
                print('ICON', label, path,
                      'MISSING — place a 256x256 RGBA PNG there')
        if os.path.exists(src_lock):
            self._img_lock = KivyImage(source=src_lock, allow_stretch=True,
                                       keep_ratio=True, size_hint=(None, None),
                                       opacity=1.0)
            self.add_widget(self._img_lock)
        if os.path.exists(src_unlock):
            self._img_unlock = KivyImage(source=src_unlock, allow_stretch=True,
                                         keep_ratio=True, size_hint=(None, None),
                                         opacity=0)
            self.add_widget(self._img_unlock)
        self._update_visual()

    def set_locked(self, locked):
        self._is_locked = locked
        self._update_visual()

    def _update_visual(self):
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
        # Fallback vector padlock
        self.canvas.after.clear()
        if w < 4 or h < 4:
            return
        cx, cy = self.x + w / 2, self.y + h / 2
        s = min(w, h) * 0.0032
        lw = max(1.8, min(w, h) * 0.045)
        bw, bh = 28*s, 22*s
        with self.canvas.after:
            Color(1, 1, 1, 0.95)
            if self._is_locked:
                Line(circle=(cx, cy + 10*s, 14*s, 0, 180), width=lw, cap='round')
            else:
                Line(circle=(cx + 14*s, cy + 10*s, 14 *
                     s, 60, 180), width=lw, cap='round')
            Line(rounded_rectangle=(cx - bw/2, cy - 18*s, bw, 26*s, 4*s), width=lw)
            Ellipse(pos=(cx - 5*s, cy - 5*s), size=(10*s, 10*s))
            Line(points=[cx, cy - 5*s, cx, cy - 14*s], width=lw*0.8)


# ── Asset paths ───────────────────────────────────────────────────────────────
_ICON_FILES = {
    'CAR':  'car.png',  'MOTO': 'moto.png',
    'LRY':  'lry.png',  'LLRY': 'llry.png',
    'BUS':  'bus.png',
}


def _asset_dir():
    candidates = []
    # FIX (desktop packaging): PyInstaller's --onefile mode extracts
    # bundled data (assets/) into a temporary folder at runtime, exposed
    # via sys._MEIPASS — without checking this first, a packaged .exe
    # would silently fall back to the vector-drawn icons instead of the
    # real PNGs, even though they were bundled correctly.
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(os.path.join(meipass, 'assets'))
    candidates += [
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
    PRESS_TIMEOUT = 1.0

    def __init__(self, key, circle_color, label_text, **kwargs):
        # FIX: same texture-reload issue as the other button classes.
        super().__init__(background_normal='', background_down='',
                         background_disabled_normal='', background_disabled_down='',
                         background_color=(0, 0, 0, 0), **kwargs)
        self.key = key
        self.circle_color = circle_color
        self.label_text = label_text
        self._pressed = False
        self._touch = None
        self._timeout_ev = None
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

        # FIX: letter label under the icon removed per request — icon now
        # fills the full button height instead of sharing space with it.
        self._redraw()

    def _redraw(self, *a):
        w, h = self.size
        pad = 8
        icon_zone_h = h - pad * 2
        icon_zone_y = self.y + pad
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
        cr = self.circle_color
        self._col_normal = (None, cr)
        self._col_press = ((1, 1, 1, 0.9),
                           (cr[0]*0.38, cr[1]*0.38, cr[2]*0.38, cr[3]))
        self._r = self.CORNER_RADIUS
        self._ring = 6
        self._redraw_bg()

    def _redraw_bg(self):
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

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        if self.collide_point(*touch.pos):
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
        pass

    def on_release(self):
        self._pressed = False
        self._redraw_bg()

    def flash_press(self, duration=0.12):
        """Briefly show the same darken/ring press feedback a real touch
        gives, without an actual touch — used for keyboard-triggered
        increments so they get the same visual feedback as tapping."""
        self._pressed = True
        self._redraw_bg()
        Clock.schedule_once(lambda dt: (
            setattr(self, '_pressed', False), self._redraw_bg()), duration)


# ── Grid cluster ──────────────────────────────────────────────────────────────
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

                        # FIX: the previous version had the
                        # "if ub._mode else None" clause outside the lambda's
                        # parentheses, so it was evaluated once at bind time
                        # (when ub._mode was still None) instead of on every
                        # tap — permanently binding on_release to None.
                        # Using a real function closed over `ub` re-checks
                        # ub._mode every time the button is released.
                        def _undo_redo_release(b, ub=ub):
                            if self._is_locked():
                                return
                            if ub._mode == 'undo':
                                haptic_tap()
                                play_startpause()
                                on_undo()
                            elif ub._mode == 'redo':
                                haptic_tap()
                                play_startpause()
                                on_redo()

                        ub.bind(on_release=_undo_redo_release)
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
        self.on_tap(key)
        if self._is_locked():
            return
        import threading
        threading.Thread(target=lambda: (
            haptic_tap(), play_tap()), daemon=True).start()


# ── Summary chip ──────────────────────────────────────────────────────────────
class SummaryChip(Button):
    """Top-bar decrement chip. Uses the same explicit touch-grab handling
    as SafeButton/IconButton — plain Kivy Button dispatch (on_press/
    on_release) is unreliable on some Android touch drivers and was making
    these feel delayed / require a firmer or repeated tap."""

    # FIX: a fast/hard physical tap can make the touchscreen itself
    # register two contact events a few milliseconds apart ("bounce") —
    # this is a hardware phenomenon, not a software double-dispatch bug,
    # so the earlier grab-clearing fix doesn't catch it (both events are
    # genuinely separate touches). 60ms is far shorter than any real human
    # double-tap (typically 150ms+), so this only filters bounce, not
    # legitimate fast repeated taps.
    BOUNCE_WINDOW = 0.06

    # FIX: same safety net SquareVehicleButton already has — if a touch's
    # up/cancel event is ever dropped by the platform (a real, occasional
    # Android touch-driver issue) after we've grabbed it, this widget would
    # otherwise stay stuck looking pressed forever with no way to recover.
    # Force-clear after 1s if no release arrives.
    PRESS_TIMEOUT = 1.0

    def __init__(self, chip_color, **kwargs):
        self._chip_color = chip_color
        self._dim = tuple(max(0, c*0.35) if i < 3 else c
                          for i, c in enumerate(chip_color))
        self._flash_ev = None
        self._touch = None
        self._last_up_t = 0.0
        self._timeout_ev = None
        # FIX: background_normal was blanked but background_down (and the
        # disabled variants) were left at Kivy's default atlas images.
        # Every tap flipped self.state to 'down', which made Kivy load and
        # swap in that real texture, then swap it back on release — a
        # runtime texture reload on every single press, on the exact same
        # Android-texture-reload issue already fixed for the icon buttons
        # (StartPauseButton/UndoRedoButton/LockButton) via pre-loaded
        # opacity-toggled images instead of swapping .source/background at
        # runtime. That reload is what read as "delay" here. Blanking all
        # four background properties means no texture is ever swapped.
        super().__init__(background_normal='', background_down='',
                         background_disabled_normal='', background_disabled_down='',
                         background_color=chip_color, **kwargs)

    def flash(self):
        if self._flash_ev:
            self._flash_ev.cancel()
        self.background_color = list(self._dim)
        self._flash_ev = Clock.schedule_once(
            lambda dt: setattr(self, 'background_color', list(self._chip_color)), 0.08)

    def _arm_timeout(self):
        self._cancel_timeout()
        self._timeout_ev = Clock.schedule_once(
            self._force_release, self.PRESS_TIMEOUT)

    def _cancel_timeout(self):
        if self._timeout_ev:
            self._timeout_ev.cancel()
            self._timeout_ev = None

    def _force_release(self, dt):
        # A grabbed touch never sent us a release within PRESS_TIMEOUT —
        # treat it as abandoned. Just clean up the visual/grab state,
        # don't dispatch on_release (we can't know if it was a genuine
        # completed tap, so don't risk a phantom decrement).
        if self._touch is not None:
            try:
                self._touch.ungrab(self)
            except Exception:
                pass
            self._touch = None
        self.state = 'normal'
        self._last_up_t = time.monotonic()
        self.background_color = list(self._chip_color)

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        if self.collide_point(*touch.pos):
            # FIX: ignore a new touch landing within the bounce window of
            # the last completed release — this is what actually catches
            # "press too fast = decrements by 2", since that's two
            # genuinely separate touch objects from one physical bounce,
            # not something the grab-clearing dedupe below can see.
            if time.monotonic() - self._last_up_t < self.BOUNCE_WINDOW:
                return True
            # FIX: Android sometimes delivers on_touch_down twice for a
            # single physical tap. If we're still holding a grab from an
            # earlier (possibly duplicate) down event, release it before
            # granting a new one — otherwise Kivy's grab list ends up with
            # two entries for the same touch, and on_touch_up dispatches
            # on_release twice, decrementing by 2. Same dedupe pattern as
            # SquareVehicleButton's _clear_press(). This adds no delay —
            # it's a same-frame check, not a timer.
            if self._touch is not None:
                try:
                    self._touch.ungrab(self)
                except Exception:
                    pass
                self._touch = None
            touch.grab(self)
            self._touch = touch
            self.state = 'down'
            self._arm_timeout()
            # FIX: give immediate visual feedback the instant the finger
            # touches down, same as SquareVehicleButton's press-darken —
            # previously nothing changed on screen until on_touch_up (and
            # only then if the debounce/count checks passed), which is
            # part of why this felt less responsive than the vehicle
            # increment buttons even after the texture-swap fix.
            if self._flash_ev:
                self._flash_ev.cancel()
                self._flash_ev = None
            self.background_color = list(self._dim)
            return True
        return False

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._cancel_timeout()
            self._touch = None
            self._last_up_t = time.monotonic()
            self.state = 'normal'
            # FIX: always revert the press-darken immediately on release,
            # regardless of whether a decrement actually happens. Before,
            # this only got reverted by flash() — which only runs when
            # count > 0 — so tapping a chip whose count was already 0 left
            # it permanently stuck looking "pressed" forever, since
            # nothing else ever reset the color. If a decrement does
            # happen, flash() still runs right after this and does its own
            # separate dim-then-fade pulse — this line and flash() don't
            # conflict, they're just two different visual moments.
            self.background_color = list(self._chip_color)
            if self.collide_point(*touch.pos):
                self.dispatch('on_release')
            return True
        return False


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
        # FIX: removed the 300ms per-key debounce that lived here. It
        # duplicated protection SummaryChip's touch grab/ungrab already
        # provides and, unlike the increment buttons (SquareVehicleButton,
        # which has no debounce at all), was silently swallowing quick
        # legitimate repeat taps — the actual cause of decrement feeling
        # less smooth than increment.
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
        # FIX: re-entrancy guard so a double-fired tap on SET can't stack a
        # second Set-Timer popup underneath the first one.
        self._set_popup_open = False
        self._active_cancel_fn = None

        # FIX (background timer): instead of only counting down via Clock
        # ticks (which Android suspends while the app is minimised), we
        # anchor the countdown to a wall-clock deadline. Whenever the app
        # resumes, the remaining time is recomputed from real elapsed time
        # rather than from however many ticks happened to fire.
        self._deadline = None   # time.time() value when countdown hits 0, while running
        self._pending_alarm = False  # timer expired while backgrounded; alarm not yet played

        self.lbl = Label(text=self._fmt(DEFAULT_TIMER), font_size=BASE_FONT,
                         bold=True, color=(0.55, 0.92, 0.55, 1),
                         size_hint=(1, 1), halign='center', valign='middle')
        self.lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self.add_widget(self.lbl)

        # FIX: timer's own RESET button removed — RESET ALL (top bar)
        # already resets the timer alongside the counts, so this was
        # redundant. Only SET remains, now spanning the full row.
        row = BoxLayout(orientation='horizontal', size_hint=(1, None),
                        height=46, spacing=6, padding=[4, 0, 4, 0])
        self._btn_set = self._mk("SET", (0.25, 0.35, 0.60, 1))
        self._btn_set.bind(on_release=self._open_set)
        row.add_widget(self._btn_set)
        self.add_widget(row)

    def set_locked(self, locked):
        alpha = 0.25 if locked else 1.0
        self._btn_set.opacity = alpha
        self._btn_set.disabled = locked
        if self._ext_btn_ss:
            self._ext_btn_ss.opacity = alpha
            self._ext_btn_ss.disabled = locked

    def _mk(self, t, bg):
        # FIX: SafeButton instead of plain Button — plain Kivy Button
        # dispatch was unreliable on Android, requiring double taps and
        # occasionally double-firing (which stacked a second popup).
        return SafeButton(text=t, font_size=15, bold=True, color=(1, 1, 1, 1),
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
        # FIX: anchor to a wall-clock deadline instead of just counting
        # ticks, so the countdown stays correct across a background/
        # foreground cycle even if Android suspends the Clock in between.
        self._deadline = time.time() + self._remaining
        self._tick_ev = Clock.schedule_interval(self._tick, 1)

    def _pause(self):
        self._running = False
        self._set_btn_state(False)
        if self._tick_ev:
            self._tick_ev.cancel()
        if self._deadline is not None:
            self._remaining = max(0, self._deadline - time.time())
            self._deadline = None

    def _tick(self, dt):
        if self._deadline is None:
            return
        remaining = self._deadline - time.time()
        if remaining <= 0:
            self._remaining = 0
            self.lbl.text = self._fmt(0)
            self._pause()
            self._expire()
        else:
            self._remaining = remaining
            self.lbl.text = self._fmt(remaining)

    def _expire(self):
        # FIX: don't blast the alarm sound while the app is minimised —
        # only actually play it once the user is back looking at the app.
        # If we're already in the foreground, that's immediately.
        global _APP_FOREGROUND
        if _APP_FOREGROUND:
            self._pending_alarm = False
            self._alert()
        else:
            self._pending_alarm = True

    def on_app_resume(self):
        """Called by the App on returning to the foreground. Recomputes
        the countdown from wall-clock time and fires the alarm now if it
        expired while the app was minimised."""
        if self._running and self._deadline is not None:
            remaining = self._deadline - time.time()
            if remaining <= 0:
                self._remaining = 0
                self.lbl.text = self._fmt(0)
                self._pause()
                self._pending_alarm = False
                self._alert()
                return
            self._remaining = remaining
            self.lbl.text = self._fmt(remaining)
        if self._pending_alarm:
            self._pending_alarm = False
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
        self._deadline = None
        self._pending_alarm = False
        self.lbl.text = self._fmt(self._remaining)
        self.lbl.color = (0.55, 0.92, 0.55, 1)
        self.lbl.font_size = BASE_FONT

    def reset_to_default(self): self._reset_timer()

    def stop_alert(self):
        self._stop_alert()
        self._pending_alarm = False
        self.lbl.color = (0.55, 0.92, 0.55, 1)
        self.lbl.font_size = BASE_FONT

    def _open_set(self, *a):
        # FIX: guard against a duplicate/double-fired tap opening a second
        # Set-Timer popup on top of the first (the root cause of "press Set
        # twice" and the minute value reverting to default).
        if self._set_popup_open:
            return
        self._set_popup_open = True

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

        # FIX: auto_dismiss=False — prevents the first tap from landing on
        # the semi-transparent overlay and dismissing the popup before the
        # button registers (which made it feel like two presses were needed).
        popup = Popup(title='Set Timer', title_size=20, content=content,
                      size_hint=(0.55, None), height=280,
                      pos_hint={'center_x': 0.5, 'top': 0.98},
                      background_color=(0.14, 0.15, 0.20, 1),
                      title_color=(1, 1, 1, 1),
                      separator_color=(0.25, 0.27, 0.32, 1),
                      auto_dismiss=False)

        def _cancel(*a):
            self._duration = prev_duration
            self._remaining = prev_duration
            self.lbl.text = self._fmt(prev_duration)
            popup.dismiss()

        # FIX: stored so toggle_set_popup() (used by the global-hotkey
        # path, which can't reach this local closure otherwise) can close
        # this popup the same way Escape/T does.
        self._active_cancel_fn = _cancel

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

        # FIX: keyboard navigation for this popup. Tab cycles focus
        # through MM -> SS -> Cancel -> Set -> back to MM; Enter activates
        # Set (from anywhere, matching normal form behaviour) or whichever
        # button is highlighted; Escape cancels (same as clicking Cancel).
        # Only Tab/Enter/Escape are consumed here — every other key
        # (digits, backspace while typing, etc.) returns False and falls
        # through untouched to the focused TextInput's own normal typing,
        # so MM/SS editing keeps working exactly as before.
        tab_order = [inp_m, inp_s, cancel, confirm]
        focus_idx = {'i': 0}

        def _set_focus(idx):
            focus_idx['i'] = idx % len(tab_order)
            for i, w in enumerate(tab_order):
                is_sel = (i == focus_idx['i'])
                if isinstance(w, TextInput):
                    w.focus = is_sel
                else:
                    w.opacity = 1.0 if is_sel else 0.55

        def _popup_keydown(window, key, scancode, codepoint, modifiers):
            if key == 9:  # Tab
                _set_focus(focus_idx['i'] + 1)
                return True
            if key in (13, 271):  # Enter / numpad Enter
                current = tab_order[focus_idx['i']]
                if isinstance(current, TextInput):
                    confirm.dispatch('on_release')
                else:
                    current.dispatch('on_release')
                return True
            if key == 27:  # Escape — cancels, same as clicking Cancel
                _cancel()
                return True
            if (codepoint or '').lower() == getattr(self, 'toggle_key', 't'):
                # FIX: whatever key opens this popup (see _on_keyboard,
                # default 't' but customizable via keymap.json) also
                # closes it if pressed again while it's open.
                _cancel()
                return True
            return False

        Window.bind(on_key_down=_popup_keydown)
        _set_focus(0)  # start on the MM field, ready to type immediately

        def _on_dismiss(*a):
            # FIX: clear the re-entrancy guard once the popup actually
            # closes, and unbind the popup-only keyboard handler.
            Window.unbind(on_key_down=_popup_keydown)
            self._set_popup_open = False
            self._active_cancel_fn = None

        popup.bind(on_dismiss=_on_dismiss)
        popup.open()

    def toggle_set_popup(self):
        """Open the Set Timer popup if closed, close it if open — used by
        both the T key and the global Ctrl+Alt+T hotkey."""
        if self._set_popup_open:
            if self._active_cancel_fn:
                self._active_cancel_fn()
        else:
            self._open_set()


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
        _verbose = getattr(self, '_anim_frame_count', 0) <= 3
        if _verbose:
            print('DRAWBAR: before clear')
        w.canvas.clear()
        if _verbose:
            print('DRAWBAR: after clear, before with-block')
        bw, bh = w.width, w.height
        if bw < 1:
            return
        with w.canvas:
            Color(0.20, 0.22, 0.28, 1)
            RoundedRectangle(pos=(w.x, w.y), size=(bw, bh), radius=[bh/2])
            Color(0.10, 0.45, 0.90, 1)
            fill_w = max(bh, bw*self._bar_progress)
            RoundedRectangle(pos=(w.x, w.y), size=(fill_w, bh), radius=[bh/2])
        if _verbose:
            print('DRAWBAR: with-block completed OK')

    def _animate(self, dt):
        self._anim_frame_count = getattr(self, '_anim_frame_count', 0) + 1
        if self._anim_frame_count <= 5 or self._anim_frame_count % 10 == 0:
            print('LOADINGSCREEN: animate frame', self._anim_frame_count)
        gap = self._target - self._bar_progress
        if gap > 0:
            self._bar_progress += max(0.002, gap*0.08)
        self._bar_progress = min(self._target, self._bar_progress)
        self._draw_bar()

    def _step1(self, dt):
        self._status.text = 'Loading sounds...'
        _init_sounds()
        print('LOADINGSCREEN: sound init returned, continuing to step2')
        self._target = 0.40
        Clock.schedule_once(self._step2, 0.5)

    def _step2(self, dt):
        print('LOADINGSCREEN: reached step2 (loading assets)')
        self._status.text = 'Loading assets...'
        self._target = 0.75
        Clock.schedule_once(self._step3, 0.5)

    def _step3(self, dt):
        print('LOADINGSCREEN: reached step3 (ready)')
        self._status.text = 'Ready!'
        self._target = 1.0
        Clock.schedule_interval(self._wait_full, 0.05)

    def _wait_full(self, dt):
        if self._bar_progress >= 0.995:
            Clock.unschedule(self._wait_full)
            Clock.schedule_once(self._finish, 0.18)
            return False

    def _finish(self, dt):
        print('LOADINGSCREEN: finished, launching RootLayout now')
        if self._bar_ev:
            self._bar_ev.cancel()
        self._on_done()


# ── Root layout ───────────────────────────────────────────────────────────────
class RootLayout(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # FIX: loaded first, before any widget construction, so the
        # vehicle button dicts, TimerWidget's toggle key, and the
        # shortcuts bar/help popup text can all reference it regardless
        # of construction order below.
        self.keymap = _load_keymap()
        self._KEYS_J1 = {
            self.keymap['j1_car']:  'CAR',
            self.keymap['j1_moto']: 'MOTO',
            self.keymap['j1_lorry']: 'LRY',
            self.keymap['j1_bus']:  'BUS',
            self.keymap['j1_llry']: 'LLRY',
        }
        self._KEYS_J2 = {
            self.keymap['j2_car']:  'CAR',
            self.keymap['j2_moto']: 'MOTO',
            self.keymap['j2_lorry']: 'LRY',
            self.keymap['j2_bus']:  'BUS',
            self.keymap['j2_llry']: 'LLRY',
        }
        self._undo_snapshot = None
        self._redo_snapshot = None
        self._locked = False
        # FIX: re-entrancy guard so a double-fired tap on RESET ALL can't
        # stack a second confirm-reset popup underneath the first.
        self._reset_popup_open = False
        # FIX: tracks whether the in-app keybindings editor is open.
        self._keybind_popup_open = False

        top = BoxLayout(size_hint=(1, None), height=TOP_H,
                        pos_hint={'x': 0, 'top': 1},
                        spacing=6, padding=[6, 6, 6, 6])
        # FIX: kept as a reference so _layout() can shrink its height at
        # small window sizes — previously fixed at TOP_H permanently,
        # which meant a thin window would be almost entirely consumed by
        # this bar alone.
        self.top_bar = top
        self.j1_summary = JunctionSummary(on_minus=self._on_minus,
                                          order=SUMMARY_ORDER_LEFT,
                                          is_locked=lambda: self._locked,
                                          size_hint=(0.42, 1))
        # FIX: SafeButton instead of plain Button for the same reason as
        # the timer's SET/RESET buttons — reliable single-tap dispatch.
        self.reset_btn = SafeButton(text="RESET ALL", font_size=16, bold=True,
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

        # FIX: always-visible keyboard shortcuts reference — desktop only
        # (no keyboard on Android, and mobile screen space is precious).
        # A thin strip pinned to the bottom, sized/font-scaled in
        # _layout() rather than shown only in a popup you have to open.
        if platform == 'android':
            self.shortcuts_bar = None
        else:
            self.shortcuts_bar = _ClickableLabel(
                on_press=self._show_keybindings_editor,
                text=self._build_shortcuts_bar_text(),
                font_size=11, color=(0.72, 0.75, 0.80, 0.95),
                halign='center', valign='middle',
                size_hint=(None, None))
            self.shortcuts_bar.bind(
                size=lambda i, v: setattr(i, 'text_size', v))
            with self.shortcuts_bar.canvas.before:
                Color(0, 0, 0, 0.4)
                self._shortcuts_bg_rect = Rectangle(
                    pos=self.shortcuts_bar.pos, size=self.shortcuts_bar.size)

            def _upd_shortcuts_bg(inst, *a):
                self._shortcuts_bg_rect.pos = inst.pos
                self._shortcuts_bg_rect.size = inst.size
            self.shortcuts_bar.bind(
                pos=_upd_shortcuts_bg, size=_upd_shortcuts_bg)
            self.add_widget(self.shortcuts_bar)

        self.bind(size=self._layout)
        self.reset_btn.bind(size=self._layout)
        self.j1_summary.chips['MOTO'][0].bind(
            pos=self._layout, size=self._layout)
        self.j2_summary.chips['CAR'][0].bind(
            pos=self._layout,  size=self._layout)
        self._load()

        # FIX (desktop keyboard support): lets the surveyor keep both
        # hands on the keyboard while watching video footage, instead of
        # needing the mouse.
        # FIX: so the Set Timer popup's own "press the same key again to
        # close" logic respects a customized timer_set key too, not just
        # the outer open/close toggle.
        self.timer.toggle_key = self.keymap['timer_set']
        Window.bind(on_key_down=self._on_keyboard)

    # ── Action methods ──────────────────────────────────────────────────
    # Kept as separate small methods (rather than inlined in
    # _on_keyboard) so each is independently easy to test/read.

    def _act_vehicle(self, junction, vehicle, decrement):
        if self._locked:
            return
        summary = self.j1_summary if junction == 'j1' else self.j2_summary
        cluster = self.j1_cluster if junction == 'j1' else self.j2_cluster
        tap_fn = self._j1_tap if junction == 'j1' else self._j2_tap
        if decrement:
            summary._minus(vehicle)
        else:
            tap_fn(vehicle)
            # FIX: a real touch on this button gets haptic + sound via
            # SquareGridCluster._tap — but keyboard shortcuts call the
            # tap method directly, bypassing that, so this matches it for
            # full parity with a real touch (and with decrement, whose
            # _minus already includes all of this).
            btn = cluster._buttons.get(vehicle)
            if btn:
                btn.flash_press()
            import threading
            threading.Thread(target=lambda: (
                haptic_tap(), play_tap()), daemon=True).start()

    def _act_timer_toggle(self):
        if self._locked:
            return
        play_startpause()
        self.timer._toggle()

    def _act_set_timer_toggle(self):
        if self._locked:
            return
        self.timer.toggle_set_popup()

    def _act_undo(self):
        if self._locked:
            return
        haptic_tap()
        play_startpause()
        self._do_undo()

    def _act_redo(self):
        if self._locked:
            return
        haptic_tap()
        play_startpause()
        self._do_redo()

    def _act_lock(self):
        self._toggle_lock()

    def _act_pin(self):
        if platform == 'android':
            return
        Window.always_on_top = not Window.always_on_top
        Window.set_title('PATSB Traffic Counter' +
                         (' (Pinned)' if Window.always_on_top else ''))

    def _act_dock(self, edge):
        if platform == 'android':
            return
        self._dock_window(edge)

    def _act_reset(self):
        if self._locked:
            return
        self._confirm_reset()

    def _act_help(self):
        self._show_keybindings_editor()

    def _keyval_to_code(self, val):
        """Resolve one keymap.json value (e.g. 'escape', 'up', or a plain
        letter) to the numeric keycode _on_keyboard's 'key' argument uses."""
        if val in _SPECIAL_KEY_CODES:
            return _SPECIAL_KEY_CODES[val]
        if len(val) == 1:
            return ord(val)
        return None

    def _action_key_matches(self, action_name, ch, key):
        """Whether the current keypress matches a given action's bound
        key — handles both plain single characters (compared against the
        codepoint) and special key names like 'space'/'escape' (compared
        against the numeric keycode, since those don't have a meaningful
        codepoint to compare directly)."""
        val = self.keymap.get(action_name, '')
        if val in _SPECIAL_KEY_CODES:
            return key == _SPECIAL_KEY_CODES[val]
        return ch == val

    def _on_keyboard(self, window, key, scancode, codepoint, modifiers):
        # FIX: while a popup is open (Set Timer's MM/SS text fields, the
        # Reset All confirmation, the help popup, or the keybindings
        # editor), these shortcuts must stand down — otherwise typing a
        # digit or pressing Backspace to edit the MM/SS fields would get
        # hijacked, and while rebinding a key, the OLD action for that key
        # would also fire alongside the rebind capture.
        if (self.timer._set_popup_open or self._reset_popup_open or
                getattr(self, '_keybind_popup_open', False)):
            return False

        ch = (codepoint or '').lower()
        ctrl = 'ctrl' in modifiers
        shift = 'shift' in modifiers

        # FIX: Ctrl-combo actions (undo/redo/dock) are checked BEFORE the
        # bare vehicle-key checks below. This matters now that vehicle
        # keys are customizable — e.g. the default keymap uses "z" for a
        # vehicle and Ctrl+Z for undo; checking Ctrl-combos first (by
        # keycode, not codepoint, which Ctrl can suppress/alter) means
        # holding Ctrl always means "undo", never "tap the z vehicle",
        # regardless of what letter either one happens to be bound to.
        if ctrl and key == self._keyval_to_code(self.keymap['undo']):
            self._act_undo()
            return True
        if ctrl and key == self._keyval_to_code(self.keymap['redo']):
            self._act_redo()
            return True
        if ctrl and key == self._keyval_to_code(self.keymap['dock_top']):
            self._act_dock('top')
            return True
        if ctrl and key == self._keyval_to_code(self.keymap['dock_bottom']):
            self._act_dock('bottom')
            return True

        # From here on, a Ctrl-held keypress is never treated as a bare
        # shortcut — it's either one of the combos above, or not ours.
        if ctrl:
            return False

        if ch == '?' or key == 282:  # '?' or F1
            self._act_help()
            return True

        if ch in self._KEYS_J1:
            self._act_vehicle('j1', self._KEYS_J1[ch], shift)
            return True

        if ch in self._KEYS_J2:
            self._act_vehicle('j2', self._KEYS_J2[ch], shift)
            return True

        if self._action_key_matches('timer_pause', ch, key):
            self._act_timer_toggle()
            return True

        if self._action_key_matches('timer_set', ch, key):
            self._act_set_timer_toggle()
            return True

        if self._action_key_matches('lock', ch, key):
            self._act_lock()
            return True

        if self._action_key_matches('pin', ch, key):
            self._act_pin()
            return True

        if key == self._keyval_to_code(self.keymap['reset']):
            self._act_reset()
            return True

        return False

    def _dock_window(self, edge):
        """Snap the window to the top or bottom screen edge, spanning
        full screen width, keeping the current window height."""
        screen = _get_screen_size()
        if screen:
            sw, sh = screen
            Window.size = (sw, Window.height)
            Window.left = 0
            Window.top = 0 if edge == 'top' else max(0, sh - Window.height)
        else:
            # No reliable screen-size query on this OS — just snap
            # vertically without resizing width, better than doing
            # nothing at all.
            Window.top = 0 if edge == 'top' else Window.top

    def _build_shortcuts_bar_text(self):
        km = self.keymap
        return (
            "{j1c} {j1m} {j1l} {j1b} {j1ll} = J1 Car/Moto/Lorry/Bus/LLorry   |   "
            "{j2c} {j2m} {j2l} {j2b} {j2ll} = J2 Car/Moto/Lorry/Bus/LLorry   |   "
            "Shift = Decrement   |   {pause} = Pause   |   {set} = Timer   |   "
            "{lock} = Lock   |   {pin} = Pin   |   Ctrl+{undo}/{redo} = Undo/Redo   |   "
            "Esc = Reset All   |   F1 = Help / Customize"
        ).format(
            j1c=km['j1_car'].upper(), j1m=km['j1_moto'].upper(),
            j1l=km['j1_lorry'].upper(), j1b=km['j1_bus'].upper(),
            j1ll=km['j1_llry'].upper(),
            j2c=km['j2_car'].upper(), j2m=km['j2_moto'].upper(),
            j2l=km['j2_lorry'].upper(), j2b=km['j2_bus'].upper(),
            j2ll=km['j2_llry'].upper(),
            pause=km['timer_pause'].upper(), set=km['timer_set'].upper(),
            lock=km['lock'].upper(), pin=km['pin'].upper(),
            undo=km['undo'].upper(), redo=km['redo'].upper(),
        )

    def _apply_keymap_change(self):
        """Called after ANY rebind — rebuilds everything that depends on
        the keymap and saves it to disk, so changes take effect
        immediately without needing to restart the app."""
        self._KEYS_J1 = {
            self.keymap['j1_car']:  'CAR',
            self.keymap['j1_moto']: 'MOTO',
            self.keymap['j1_lorry']: 'LRY',
            self.keymap['j1_bus']:  'BUS',
            self.keymap['j1_llry']: 'LLRY',
        }
        self._KEYS_J2 = {
            self.keymap['j2_car']:  'CAR',
            self.keymap['j2_moto']: 'MOTO',
            self.keymap['j2_lorry']: 'LRY',
            self.keymap['j2_bus']:  'BUS',
            self.keymap['j2_llry']: 'LLRY',
        }
        self.timer.toggle_key = self.keymap['timer_set']
        if self.shortcuts_bar is not None:
            self.shortcuts_bar.text = self._build_shortcuts_bar_text()
        try:
            with open(_keymap_path(), 'w') as f:
                json.dump(self.keymap, f, indent=2)
        except Exception as e:
            print('KEYMAP: failed to save keymap.json:', e)

    def _show_keybindings_editor(self):
        # FIX: in-app rebinding UI — the app is distributed as a single
        # .exe to multiple colleagues who may each want different keys,
        # and most won't want to hand-edit a JSON file. Click any action
        # here, then press the key you want; it's saved to keymap.json
        # and applied immediately, no restart needed.
        if getattr(self, '_keybind_popup_open', False):
            return
        self._keybind_popup_open = True

        ACTIONS = [
            ('j1_car', 'Left: Car'), ('j1_moto', 'Left: Motorcycle'),
            ('j1_lorry', 'Left: Lorry'), ('j1_bus', 'Left: Bus'),
            ('j1_llry', 'Left: Large Lorry'),
            ('j2_car', 'Right: Car'), ('j2_moto', 'Right: Motorcycle'),
            ('j2_lorry', 'Right: Lorry'), ('j2_bus', 'Right: Bus'),
            ('j2_llry', 'Right: Large Lorry'),
            ('timer_pause', 'Pause / Resume Timer'),
            ('timer_set', 'Open / Close Set Timer'),
            ('lock', 'Lock / Unlock'),
            ('pin', 'Pin Window on Top'),
            ('undo', 'Undo (used with Ctrl)'),
            ('redo', 'Redo (used with Ctrl)'),
            ('reset', 'Reset All'),
            ('help', 'Show Help'),
            ('dock_top', 'Dock to Top (used with Ctrl)'),
            ('dock_bottom', 'Dock to Bottom (used with Ctrl)'),
        ]

        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(text="Customize Keyboard Shortcuts",
                                 font_size=20, bold=True, color=(1, 1, 1, 1),
                                 size_hint=(1, None), height=28))
        hint = Label(text="Click a key, then press the new key you want.\n"
                     "Hold Shift + any vehicle key to decrement instead.",
                     font_size=13, color=(0.7, 0.73, 0.78, 1),
                     size_hint=(1, None), height=34)
        content.add_widget(hint)

        scroll = ScrollView(size_hint=(1, 1))
        rows = GridLayout(cols=1, spacing=6, size_hint=(1, None))
        rows.bind(minimum_height=rows.setter('height'))
        scroll.add_widget(rows)
        content.add_widget(scroll)

        status_lbl = Label(text="", font_size=12, color=(1, 0.6, 0.4, 1),
                           size_hint=(1, None), height=18)
        content.add_widget(status_lbl)

        key_buttons = {}   # action_name -> SafeButton showing its current key
        listening = {'action': None, 'handler': None}

        def _display(val):
            return val.upper() if val else '?'

        def _stop_listening():
            if listening['handler'] is not None:
                Window.unbind(on_key_down=listening['handler'])
            if listening['action'] is not None:
                # revert the button's text back to its actual current
                # binding — matters when this is an Escape-cancel rather
                # than a successful rebind (which already set the text
                # itself before calling this).
                key_buttons[listening['action']].text = \
                    _display(self.keymap.get(listening['action'], ''))
            listening['action'] = None
            listening['handler'] = None
            status_lbl.text = ""

        def _start_listening(action_name):
            _stop_listening()
            listening['action'] = action_name
            key_buttons[action_name].text = "Press a key..."
            status_lbl.text = "Listening for a new key for: " + \
                dict(ACTIONS)[action_name]

            def _capture(window, key, scancode, codepoint, modifiers):
                if key == 27:  # Escape cancels listening, doesn't bind it
                    _stop_listening()
                    return True
                if key in (304, 305, 306, 307, 308, 309):  # bare modifier keys
                    return True
                newval = _keypress_to_keyval(key, codepoint)
                if not newval:
                    status_lbl.text = "Didn't recognise that key — try another."
                    return True
                # FIX: block binding the same key to two different actions
                conflict = None
                for name, val in self.keymap.items():
                    if name != action_name and val == newval:
                        conflict = dict(ACTIONS).get(name, name)
                        break
                if conflict:
                    status_lbl.text = ('"%s" is already used by "%s" — '
                                       'pick a different key.' %
                                       (newval.upper(), conflict))
                    return True
                self.keymap[action_name] = newval
                key_buttons[action_name].text = _display(newval)
                self._apply_keymap_change()
                _stop_listening()
                return True

            listening['handler'] = _capture
            Window.bind(on_key_down=_capture)

        for name, label in ACTIONS:
            row = BoxLayout(orientation='horizontal', size_hint=(
                1, None), height=36, spacing=10)
            lbl = Label(text=label, font_size=14, color=(0.88, 0.90, 0.92, 1),
                        halign='left', valign='middle', size_hint=(0.62, 1))
            lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
            row.add_widget(lbl)
            btn = SafeButton(text=_display(self.keymap.get(name, '')),
                             font_size=14, bold=True, color=(1, 1, 1, 1),
                             background_normal='', background_color=(0.25, 0.35, 0.60, 1),
                             size_hint=(0.38, 1))
            btn.bind(on_release=lambda b, n=name: _start_listening(n))
            key_buttons[name] = btn
            row.add_widget(btn)
            rows.add_widget(row)

        btn_row = BoxLayout(orientation='horizontal', spacing=10,
                            size_hint=(1, None), height=48)
        reset_btn = SafeButton(text="Reset All to Defaults", font_size=14, bold=True,
                               color=(1, 1, 1, 1), background_normal='',
                               background_color=(0.55, 0.25, 0.25, 1))
        close_btn = SafeButton(text="Done", font_size=16, bold=True, color=(1, 1, 1, 1),
                               background_normal='', background_color=(0.20, 0.55, 0.30, 1))

        def _reset_defaults(*a):
            _stop_listening()
            self.keymap = dict(DEFAULT_KEYMAP)
            for name, _ in ACTIONS:
                key_buttons[name].text = _display(self.keymap.get(name, ''))
            self._apply_keymap_change()
            status_lbl.text = "Reset to defaults."

        reset_btn.bind(on_release=_reset_defaults)
        btn_row.add_widget(reset_btn)
        btn_row.add_widget(close_btn)
        content.add_widget(btn_row)

        # FIX: Tab/Shift+Tab cycles through every row plus the two bottom
        # buttons, Enter activates whichever is highlighted, Escape closes
        # the whole editor — same navigation pattern as the other popups,
        # scaled up to a scrollable list.
        tab_stops = [name for name, _ in ACTIONS] + ['__reset__', '__close__']
        selected = {'idx': 0}

        def _widget_for_stop(stop):
            if stop == '__reset__':
                return reset_btn
            if stop == '__close__':
                return close_btn
            return key_buttons[stop]

        def _highlight_editor():
            for i, stop in enumerate(tab_stops):
                _widget_for_stop(
                    stop).opacity = 1.0 if i == selected['idx'] else 0.55

        def _editor_keydown(window, key, scancode, codepoint, modifiers):
            # While actively capturing a new key for some action, defer
            # entirely to that capture handler (bound separately above) —
            # don't also treat Tab/Enter as navigation in the middle of
            # picking a key.
            if listening['action'] is not None:
                return False
            if key == 9:  # Tab (Shift+Tab goes backward)
                step = -1 if 'shift' in modifiers else 1
                selected['idx'] = (selected['idx'] + step) % len(tab_stops)
                _highlight_editor()
                try:
                    scroll.scroll_to(_widget_for_stop(
                        tab_stops[selected['idx']]))
                except Exception:
                    pass
                return True
            if key in (13, 271):  # Enter / numpad Enter
                _widget_for_stop(
                    tab_stops[selected['idx']]).dispatch('on_release')
                return True
            if key == 27:  # Escape closes the whole editor
                popup.dismiss()
                return True
            if key == 282:  # F1 also closes it — same key that opened it
                popup.dismiss()
                return True
            return True  # swallow anything else while this popup is open

        Window.bind(on_key_down=_editor_keydown)
        _highlight_editor()

        popup = Popup(title='Keybindings', title_size=20, content=content,
                      size_hint=(0.75, 0.9),
                      background_color=(0.14, 0.15, 0.20, 1),
                      title_color=(1, 1, 1, 1),
                      separator_color=(0.25, 0.27, 0.32, 1),
                      auto_dismiss=False)
        close_btn.bind(on_release=lambda *a: popup.dismiss())

        def _on_dismiss(*a):
            _stop_listening()
            Window.unbind(on_key_down=_editor_keydown)
            self._keybind_popup_open = False

        popup.bind(on_dismiss=_on_dismiss)
        popup.open()

    def _layout(self, *a):
        W, H = self.size
        # FIX: scale the top summary bar down at small window heights
        # instead of leaving it permanently fixed at TOP_H — otherwise a
        # thin pinned window would be mostly the summary bar with almost
        # no room left for the actual counting buttons.
        # FIX: lowered the top bar's share (was 0.35) — the vehicle icons
        # sit in a 3-row grid, so they were shrinking roughly 3x faster
        # than the summary text as the window got thinner, making icons
        # look disproportionately small next to it. This leaves clusters
        # relatively more room.
        top_h = min(TOP_H, max(40, H * 0.22))
        self.top_bar.height = top_h

        # FIX: reserve a thin strip at the very bottom for the always-
        # visible keyboard shortcuts reference (desktop only — pointless
        # on Android, which has no keyboard). Scales with window size
        # too, within a small legible-but-unobtrusive range.
        if self.shortcuts_bar is not None:
            bar_h = min(26, max(14, H * 0.035))
            self.shortcuts_bar.height = bar_h
            self.shortcuts_bar.font_size = max(9, min(12, bar_h * 0.5))
            self.shortcuts_bar.pos = (0, 0)
            self.shortcuts_bar.size = (W, bar_h)
        else:
            bar_h = 0

        cluster_h = H - top_h - bar_h

        moto_chip = self.j1_summary.chips['MOTO'][0]
        left_grid_w = moto_chip.right if moto_chip.width > 1 else W*0.42

        car_chip = self.j2_summary.chips['CAR'][0]
        right_grid_x = car_chip.x if car_chip.width > 1 else W*0.58
        right_grid_w = W - right_grid_x

        self.j1_cluster.size = (left_grid_w, cluster_h)
        self.j1_cluster.pos = (0, bar_h)
        self.j2_cluster.size = (right_grid_w, cluster_h)
        self.j2_cluster.pos = (right_grid_x, bar_h)

        timer_w = self.reset_btn.width if self.reset_btn.width > 1 else W*0.16
        total_box_h = min(TIMER_H + self._lock_btn_h + 6, cluster_h - 12)
        self.timer_box.size = (timer_w, total_box_h)
        self.timer_box.pos = (W/2 - timer_w/2, bar_h +
                              (cluster_h - total_box_h)/2)

    def _j1_tap(self, key):
        if self._locked:
            return
        self.j1_summary.increment(key)
        self._lock_undo_redo()
        self._save()

    def _j2_tap(self, key):
        if self._locked:
            return
        self.j2_summary.increment(key)
        self._lock_undo_redo()
        self._save()

    def _on_minus(self):
        self._lock_undo_redo()
        self._save()

    def _lock_undo_redo(self):
        # FIX: once counting resumes (a tap or a minus) after an undo/redo,
        # the undo/redo snapshot chain no longer reflects a safe state to
        # revert to, so lock the button (mode=None dims it and makes taps
        # a no-op — see UndoRedoButton / _undo_redo_release).
        if self._undo_snapshot is not None or self._redo_snapshot is not None:
            self._undo_snapshot = None
            self._redo_snapshot = None
            self._set_undo_redo_mode(None)

    def _toggle_lock(self, *a):
        self._locked = not self._locked
        self.lock_btn.set_locked(self._locked)
        if self._locked:
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
        # FIX: guard against a duplicate/double-fired tap on RESET ALL
        # opening a second confirm popup on top of the first.
        if self._reset_popup_open:
            return
        self._reset_popup_open = True

        content = BoxLayout(orientation='vertical', spacing=16, padding=24)
        content.add_widget(Label(text="Reset all counts?", halign='center',
                                 valign='middle', color=(1, 1, 1, 1),
                                 font_size=22, size_hint=(1, 1)))
        btns = BoxLayout(orientation='horizontal', spacing=12,
                         size_hint=(1, None), height=70)

        def _mk(t, bg):
            # FIX: SafeButton instead of plain Button (see SafeButton docstring).
            return SafeButton(text=t, font_size=18, bold=True, color=(1, 1, 1, 1),
                              background_normal='', background_color=bg, size_hint=(1, 1))
        cancel = _mk("Cancel", (0.30, 0.32, 0.38, 1))
        confirm = _mk("Reset",  (0.75, 0.20, 0.20, 1))
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)

        # FIX: auto_dismiss=False — same reason as the Set Timer popup.
        popup = Popup(title='Confirm', title_size=20, content=content,
                      size_hint=(0.65, 0.45),
                      background_color=(0.14, 0.15, 0.20, 1),
                      title_color=(1, 1, 1, 1),
                      separator_color=(0.25, 0.27, 0.32, 1),
                      auto_dismiss=False)
        cancel.bind(on_release=lambda *a: popup.dismiss())
        confirm.bind(on_release=lambda *a: (self._do_reset(), popup.dismiss()))

        # FIX: keyboard navigation while this popup is open — Tab moves
        # the highlight between Cancel/Reset, Enter activates whichever
        # is highlighted, Escape cancels. Starts on Cancel (the safe,
        # non-destructive default) so Enter alone never resets by
        # accident. Bound only for the popup's lifetime and unbound on
        # dismiss, so it can never interfere with anything else.
        choice_buttons = [cancel, confirm]
        selected = {'idx': 0}

        def _highlight():
            for i, b in enumerate(choice_buttons):
                b.opacity = 1.0 if i == selected['idx'] else 0.55

        def _popup_keydown(window, key, scancode, codepoint, modifiers):
            if key == 9:  # Tab
                selected['idx'] = 1 - selected['idx']
                _highlight()
                return True
            if key in (13, 271):  # Enter / numpad Enter
                choice_buttons[selected['idx']].dispatch('on_release')
                return True
            if key == 27:  # Escape — cancels, same as clicking Cancel
                popup.dismiss()
                return True
            return True  # swallow everything else while this popup is open

        Window.bind(on_key_down=_popup_keydown)
        _highlight()

        def _on_dismiss(*a):
            # FIX: clear the re-entrancy guard once the popup actually
            # closes, and unbind the popup-only keyboard handler.
            Window.unbind(on_key_down=_popup_keydown)
            self._reset_popup_open = False

        popup.bind(on_dismiss=_on_dismiss)
        popup.open()

    def _do_reset(self):
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
        # FIX: fullscreen and orientation-lock are mobile concepts —
        # forcing fullscreen on desktop would fight against being able to
        # resize/minimize the window (e.g. to sit alongside video
        # footage).
        if platform == 'android':
            Window.fullscreen = 'auto'
            Window.orientation = 'landscape'
        else:
            # FIX: start maximized (normal window with title bar/taskbar,
            # not borderless fullscreen) rather than the fixed 1280x720
            # default — a much more useful starting point on desktop.
            Window.maximize()
        self._root = FloatLayout()
        self._root.add_widget(LoadingScreen(on_done=self._launch))
        return self._root

    def _launch(self):
        print('APP: clearing loading screen, about to construct RootLayout')
        self._root.clear_widgets()
        rl = RootLayout()
        print('APP: RootLayout constructed OK, adding to screen')
        self._root.add_widget(rl)
        print('APP: RootLayout added, should be visible now')

    def on_start(self):
        if platform == 'android':
            _init_haptic()
            Window.update_viewport()
            try:
                from kivy.base import EventLoop
                from kivy.input.providers.androidjoystick import AndroidMotionEventProvider
                EventLoop.remove_input_provider_by_name('android')
                EventLoop.add_input_provider(
                    AndroidMotionEventProvider('android', ''))
            except Exception as e:
                print("Touch provider override failed:", e)

    def on_stop(self):
        root = self._root.children[0] if self._root.children else None
        if isinstance(root, RootLayout):
            root._save_bg()

    # FIX (background timer): Android calls on_pause when the app is
    # minimised/loses focus and on_resume when it's brought back. We use
    # these to flip _APP_FOREGROUND (which suppresses the alarm sound
    # while away) and to make the timer recompute against wall-clock time
    # once the user is looking at the screen again.
    def on_pause(self):
        global _APP_FOREGROUND
        _APP_FOREGROUND = False
        return True  # tells Android to keep the app alive in the background

    def on_resume(self):
        global _APP_FOREGROUND
        _APP_FOREGROUND = True
        root = self._root.children[0] if self._root.children else None
        if isinstance(root, RootLayout):
            root.timer.on_app_resume()


if __name__ == '__main__':
    TrafficCounterApp().run()
