# """
# PATSB Traffic Counter — Kivy landscape, square grid clusters with haptic feedback
# """
# from kivy.config import Config
# import math
# import json
# from kivy.app import App
# from kivy.uix.boxlayout import BoxLayout
# from kivy.uix.image import Image as KivyImage
# from kivy.core.audio import SoundLoader
# from kivy.uix.floatlayout import FloatLayout
# from kivy.uix.gridlayout import GridLayout
# from kivy.uix.button import Button
# from kivy.uix.label import Label
# from kivy.uix.popup import Popup
# from kivy.uix.textinput import TextInput
# from kivy.core.window import Window
# from kivy.utils import platform
# from kivy.graphics import (Color, Ellipse, Line, RoundedRectangle,
#                            Rectangle, Triangle, Bezier, InstructionGroup)
# from kivy.clock import Clock
# import time
# import os
# # Must be set before ANY kivy import — forces zero-delay touch on APK
# os.environ['KIVY_BCM_DISPMANX_ID'] = '0'
# os.environ['KCFG_POSTPROC_DOUBLE_TAP_TIME'] = '0'
# os.environ['KCFG_POSTPROC_DOUBLE_TAP_DISTANCE'] = '0'
# os.environ['KCFG_POSTPROC_RETAIN_TIME'] = '0'
# os.environ['KCFG_POSTPROC_RETAIN_DISTANCE'] = '0'
# os.environ['KCFG_POSTPROC_JITTER_DISTANCE'] = '0'


# Config.set('graphics', 'resizable', '0')
# Config.set('graphics', 'show_cursor', '1')
# Config.set('input', 'mouse', 'mouse,disable_multitouch')
# Config.set('postproc', 'double_tap_time', '0')
# Config.set('postproc', 'double_tap_distance', '0')
# Config.set('postproc', 'retain_time', '0')
# Config.set('postproc', 'retain_distance', '0')
# Config.set('postproc', 'jitter_distance', '0')
# Config.set('postproc', 'jitter_ignore_devices', 'mouse,mactouch,')


# Window.clearcolor = (0.08, 0.09, 0.12, 1)
# if platform != 'android':
#     Window.size = (1280, 720)

# # FIX: tracks whether the app is currently in the foreground. Used by
# # TimerWidget so the alarm sound is suppressed while the app is minimised
# # and only plays once the user reopens it — see App.on_pause/on_resume.
# _APP_FOREGROUND = True

# # Tracks whether the app is currently in the foreground. Set by
# # TrafficCounterApp.on_pause/on_resume. Used so the timer never plays its
# # alert sound while the app is backgrounded — only once it's reopened.
# _APP_FOREGROUND = True

# SAVE_FILE = os.path.join(os.path.dirname(
#     os.path.abspath(__file__)), "traffic_save.json")
# DEFAULT_TIMER = 15 * 60
# SUMMARY_ORDER_LEFT = ["CAR", "LRY", "LLRY", "BUS", "MOTO"]
# SUMMARY_ORDER_RIGHT = ["CAR", "LRY", "LLRY", "BUS", "MOTO"]
# SUMMARY_ORDER = SUMMARY_ORDER_LEFT
# VEHICLES = {
#     "CAR":  ("C",  (0.85, 0.20, 0.20, 1)),
#     "MOTO": ("M",  (0.20, 0.72, 0.35, 1)),
#     "LRY":  ("L",  (0.20, 0.47, 0.87, 1)),
#     "LLRY": ("LL", (0.93, 0.50, 0.15, 1)),
#     "BUS":  ("B",  (0.85, 0.75, 0.10, 1)),
# }

# TOP_H = 120
# TIMER_H = 130

# # ── Haptic feedback ──────────────────────────────────────────────────────────
# _haptic_flash_ev = None
# _vibrator = None
# _VibrationEffect = None


# def _pc_haptic_flash():
#     global _haptic_flash_ev
#     Window.clearcolor = (0.30, 0.20, 0.08, 1)
#     if _haptic_flash_ev:
#         _haptic_flash_ev.cancel()
#     _haptic_flash_ev = Clock.schedule_once(
#         lambda dt: setattr(Window, 'clearcolor', (0.08, 0.09, 0.12, 1)), 0.07)


# def _init_haptic():
#     global _vibrator, _VibrationEffect
#     try:
#         from jnius import autoclass
#         PythonActivity = autoclass('org.kivy.android.PythonActivity')
#         Context = autoclass('android.content.Context')
#         _vibrator = PythonActivity.mActivity.getSystemService(
#             Context.VIBRATOR_SERVICE)
#         try:
#             _VibrationEffect = autoclass('android.os.VibrationEffect')
#         except Exception:
#             _VibrationEffect = None
#         print("HAPTIC init OK, VibrationEffect=%s" % _VibrationEffect)
#     except Exception as e:
#         print("HAPTIC _init_haptic failed:", e)


# def _do_haptic():
#     if _vibrator is None:
#         return
#     try:
#         if _VibrationEffect is not None:
#             _vibrator.vibrate(
#                 _VibrationEffect.createOneShot(
#                     30, _VibrationEffect.DEFAULT_AMPLITUDE))
#         else:
#             _vibrator.vibrate(30)
#     except Exception as e:
#         print("HAPTIC vibrate failed:", e)


# def haptic_tap():
#     if platform != 'android':
#         _pc_haptic_flash()
#         return
#     if _vibrator is None:
#         return
#     import threading
#     threading.Thread(target=_do_haptic, daemon=True).start()


# # ── Sound effects ─────────────────────────────────────────────────────────────
# _POOL_SIZE = 3
# _pool_tap = []
# _pool_click = []
# _pool_alarm = []
# _pool_idx = {'tap': 0, 'click': 0, 'alarm': 0}


# def _init_sounds():
#     global _pool_tap, _pool_click, _pool_alarm

#     def _wav(samples, sr=22050):
#         import struct as _s
#         data = b''.join(_s.pack('<h', max(-32768, min(32767, int(v))))
#                         for v in samples)
#         hdr = _s.pack('<4sI4s4sIHHIIHH4sI',
#                       b'RIFF', 36+len(data), b'WAVE', b'fmt ', 16,
#                       1, 1, sr, sr*2, 2, 16, b'data', len(data))
#         return hdr + data

#     def _make_beep(sr=22050):
#         import math as _m
#         n = int(sr * 0.07)
#         out = []
#         for i in range(n):
#             t = i / sr
#             dec = _m.exp(-i / (sr * 0.018))
#             hit = _m.exp(-i / (sr * 0.004))
#             body = _m.sin(2*_m.pi * 300 * t) * 0.65 * dec
#             transient = _m.sin(2*_m.pi * 2200 * t) * 0.45 * hit
#             out.append(32767 * (body + transient))
#         return _wav(out, sr)

#     def _make_soft_click(sr=22050):
#         import math as _m
#         n = int(sr * 0.055)
#         out = []
#         for i in range(n):
#             t = i / sr
#             dec = _m.exp(-i / (sr * 0.012))
#             body = _m.sin(2*_m.pi * 180 * t) * 0.55 * dec
#             sub = _m.sin(2*_m.pi * 80 * t) * 0.30 * dec
#             out.append(32767 * (body + sub))
#         return _wav(out, sr)

#     def _make_alarm(sr=22050):
#         import math as _m

#         def square(freq, t, n_harm=6):
#             s = 0.0
#             for k in range(1, n_harm*2, 2):
#                 s += _m.sin(2*_m.pi * freq * k * t) / k
#             return s * (4/_m.pi)

#         def beep(freq, dur, vol=0.72):
#             n = int(sr * dur)
#             seg = []
#             att = int(sr * 0.006)
#             rel = int(sr * 0.025)
#             for i in range(n):
#                 t = i / sr
#                 if i < att:
#                     env = i / att
#                 elif i > n - rel:
#                     env = (n - i) / rel
#                 else:
#                     env = 1.0
#                 seg.append(32767 * vol * env * square(freq, t) * 0.35)
#             return seg

#         out = []
#         for _ in range(3):
#             out.extend(beep(880, 0.18))
#             out.extend([0] * int(sr * 0.10))
#         return _wav(out, sr)

#     def _make_pool(path, vol, size):
#         pool = []
#         for _ in range(size):
#             s = SoundLoader.load(path)
#             if s:
#                 s.volume = vol
#                 pool.append(s)
#         return pool

#     try:
#         import tempfile
#         import os as _os
#         td = tempfile.gettempdir()
#         paths = {
#             'tap':   (_os.path.join(td, 'patsb_tap.wav'),   _make_beep()),
#             'click': (_os.path.join(td, 'patsb_click.wav'), _make_soft_click()),
#             'alarm': (_os.path.join(td, 'patsb_alarm.wav'), _make_alarm()),
#         }
#         for key, (path, data) in paths.items():
#             with open(path, 'wb') as f:
#                 f.write(data)
#         _pool_tap = _make_pool(paths['tap'][0],   0.5,  _POOL_SIZE)
#         _pool_click = _make_pool(paths['click'][0], 0.45, _POOL_SIZE)
#         _pool_alarm = _make_pool(paths['alarm'][0], 0.8,  1)
#         print("SOUND pools: tap=%d click=%d alarm=%d" %
#               (len(_pool_tap), len(_pool_click), len(_pool_alarm)))
#     except Exception as e:
#         print("SOUND init failed:", e)


# def _pool_play(pool, key):
#     if not pool:
#         return
#     idx = _pool_idx[key] % len(pool)
#     _pool_idx[key] = idx + 1
#     snd = pool[idx]
#     try:
#         snd.play()
#     except Exception:
#         pass


# def play_tap():        _pool_play(_pool_tap,   'tap')
# def play_startpause(): _pool_play(_pool_click, 'click')


# def play_alarm():
#     if _pool_alarm:
#         try:
#             _pool_alarm[0].stop()
#             _pool_alarm[0].play()
#         except Exception:
#             pass


# # ── Vehicle icon drawing ─────────────────────────────────────────────────────
# def draw_icon(c, key, cx, cy, sz):
#     s = sz / 200.0
#     lw = max(1.8, 3.2 * s)
#     wr = 11 * s

#     with c:
#         Color(1, 1, 1, 0.95)

#         if key == 'CAR':
#             bw, bh = 110*s, 26*s
#             rw, rh = 68*s,  22*s
#             Line(rounded_rectangle=(cx-bw/2, cy-14*s, bw, bh, 5*s), width=lw)
#             Line(rounded_rectangle=(cx-rw/2+6*s, cy+10*s, rw, rh, 6*s), width=lw)
#             Line(points=[cx-rw/2+12*s, cy+10*s, cx -
#                  rw/2+24*s, cy+10*s+rh], width=lw*0.6)
#             Ellipse(pos=(cx-bw/2+18*s-wr, cy-28*s), size=(wr*2, wr*2))
#             Ellipse(pos=(cx+bw/2-18*s-wr, cy-28*s), size=(wr*2, wr*2))
#             hub = wr*0.38
#             Ellipse(pos=(cx-bw/2+18*s-hub, cy-28*s+wr-hub), size=(hub*2, hub*2))
#             Ellipse(pos=(cx+bw/2-18*s-hub, cy-28*s+wr-hub), size=(hub*2, hub*2))

#         elif key == 'MOTO':
#             rwr = 21*s
#             fwr = 19*s
#             rwx = cx-42*s
#             rwy = cy-16*s
#             fwx = cx+40*s
#             fwy = cy-12*s
#             Ellipse(pos=(rwx-rwr, rwy-rwr), size=(rwr*2, rwr*2))
#             Ellipse(pos=(fwx-fwr, fwy-fwr), size=(fwr*2, fwr*2))
#             hub = rwr*0.32
#             Ellipse(pos=(rwx-hub, rwy-hub), size=(hub*2, hub*2))
#             hub2 = fwr*0.32
#             Ellipse(pos=(fwx-hub2, fwy-hub2), size=(hub2*2, hub2*2))
#             sx = cx-6*s
#             sy = rwy+36*s
#             neck_x = fwx-10*s
#             neck_y = fwy+28*s
#             Line(points=[rwx, rwy+rwr, sx, sy, neck_x, neck_y], width=lw)
#             Line(points=[rwx, rwy, cx-14*s, cy], width=lw*0.9)
#             Line(rounded_rectangle=(cx-28*s, cy-4 *
#                  s, 30*s, 18*s, 3*s), width=lw*0.85)
#             Line(points=[fwx, fwy+fwr, neck_x, neck_y], width=lw)
#             hbx = neck_x-4*s
#             Line(points=[hbx-12*s, neck_y+8*s, hbx+10*s, neck_y-6*s], width=lw)
#             Line(rounded_rectangle=(sx-16*s, sy-3*s, 30*s, 10*s, 3*s), width=lw*0.8)
#             Line(points=[cx-10*s, cy-8*s, rwx+rwr, rwy-rwr*0.3], width=lw*0.7)

#         elif key == 'BUS':
#             bw, bh = 92*s, 56*s
#             Line(rounded_rectangle=(cx-bw/2, cy-bh/2, bw, bh, 3*s), width=lw)
#             Line(points=[cx-bw/2+8*s, cy+bh/2-4*s, cx +
#                  bw/2-8*s, cy+bh/2-4*s], width=lw*0.55)
#             win_w, win_h = 18*s, 14*s
#             win_y = cy+8*s
#             for i in range(3):
#                 wx = cx-bw/2+8*s+i*26*s
#                 Line(rounded_rectangle=(wx, win_y, win_w, win_h, 2*s), width=lw*0.75)
#             Line(rounded_rectangle=(cx-bw/2+8*s, cy -
#                  2*s, 20*s, 18*s, 2*s), width=lw*0.75)
#             Line(rectangle=(cx+bw/2-22*s, cy-bh/2+4*s, 14*s, 22*s), width=lw*0.8)
#             Line(points=[cx+bw/2-15*s, cy-bh/2+4*s, cx +
#                  bw/2-15*s, cy-bh/2+26*s], width=lw*0.55)
#             Ellipse(pos=(cx-bw/2+20*s-wr, cy-bh/2-wr*1.9), size=(wr*2, wr*2))
#             Ellipse(pos=(cx+bw/2-20*s-wr, cy-bh/2-wr*1.9), size=(wr*2, wr*2))
#             hub = wr*0.35
#             Ellipse(pos=(cx-bw/2+20*s-hub, cy-bh/2 -
#                     wr*1.9+wr-hub), size=(hub*2, hub*2))
#             Ellipse(pos=(cx+bw/2-20*s-hub, cy-bh/2 -
#                     wr*1.9+wr-hub), size=(hub*2, hub*2))

#         elif key == 'LRY':
#             cab_w, cab_h = 32*s, 46*s
#             bod_w, bod_h = 64*s, 30*s
#             Line(rectangle=(cx-cab_w/2-bod_w, cy-bod_h/2, bod_w, bod_h), width=lw)
#             for i in range(1, 3):
#                 rx = cx-cab_w/2-bod_w+i*(bod_w/3)
#                 Line(points=[rx, cy-bod_h/2+3*s, rx,
#                      cy+bod_h/2-3*s], width=lw*0.55)
#             Line(rounded_rectangle=(cx-cab_w/2, cy -
#                  bod_h/2, cab_w, cab_h, 4*s), width=lw)
#             Line(rounded_rectangle=(cx-cab_w/2+4*s, cy +
#                  4*s, cab_w-8*s, 14*s, 2*s), width=lw*0.75)
#             Line(points=[cx-cab_w/2+4*s, cy-bod_h/2+3*s,
#                  cx-cab_w/2+4*s, cy+2*s], width=lw*0.55)
#             Line(rounded_rectangle=(cx+cab_w/2-5*s, cy -
#                  bod_h/2+2*s, 4*s, 12*s, 1*s), width=lw*0.7)
#             Ellipse(pos=(cx-wr, cy-bod_h/2-wr*2.1), size=(wr*2, wr*2))
#             Ellipse(pos=(cx-cab_w/2-bod_w+16*s-wr, cy -
#                     bod_h/2-wr*2.1), size=(wr*2, wr*2))
#             hub = wr*0.35
#             Ellipse(pos=(cx-hub, cy-bod_h/2-wr*2.1+wr-hub), size=(hub*2, hub*2))
#             Ellipse(pos=(cx-cab_w/2-bod_w+16*s-hub, cy-bod_h /
#                     2-wr*2.1+wr-hub), size=(hub*2, hub*2))

#         elif key == 'LLRY':
#             cab_w, cab_h = 28*s, 52*s
#             bod_w, bod_h = 96*s, 28*s
#             Line(rectangle=(cx-cab_w/2-bod_w, cy-bod_h/2, bod_w, bod_h), width=lw)
#             for i in range(1, 4):
#                 rx = cx-cab_w/2-bod_w+i*(bod_w/4)
#                 Line(points=[rx, cy-bod_h/2+3*s, rx,
#                      cy+bod_h/2-3*s], width=lw*0.55)
#             Line(rounded_rectangle=(cx-cab_w/2-12*s, cy +
#                  bod_h/2-2*s, 14*s, 8*s, 2*s), width=lw*0.7)
#             Line(rounded_rectangle=(cx-cab_w/2, cy -
#                  bod_h/2, cab_w, cab_h, 4*s), width=lw)
#             Line(rounded_rectangle=(cx-cab_w/2+4*s, cy +
#                  5*s, cab_w-8*s, 15*s, 2*s), width=lw*0.75)
#             Line(points=[cx-cab_w/2+4*s, cy-bod_h/2+3*s,
#                  cx-cab_w/2+4*s, cy+3*s], width=lw*0.55)
#             Line(rounded_rectangle=(cx+cab_w/2-5*s, cy -
#                  bod_h/2+2*s, 4*s, 14*s, 1*s), width=lw*0.7)
#             front_x = cx-wr
#             mid_x = cx-cab_w/2-bod_w*0.45-wr
#             rear_x = cx-cab_w/2-bod_w+14*s-wr
#             wheel_y = cy-bod_h/2-wr*2.1
#             Ellipse(pos=(front_x, wheel_y), size=(wr*2, wr*2))
#             Ellipse(pos=(mid_x,   wheel_y), size=(wr*2, wr*2))
#             Ellipse(pos=(rear_x,  wheel_y), size=(wr*2, wr*2))
#             hub = wr*0.35
#             for wx in (front_x+wr-hub, mid_x+wr-hub, rear_x+wr-hub):
#                 Ellipse(pos=(wx, wheel_y+wr-hub), size=(hub*2, hub*2))


# # ── Canvas-icon button base ───────────────────────────────────────────────────
# class IconButton(Button):
#     """Dark near-black button with custom touch handling that mirrors
#     SquareVehicleButton — bypasses Kivy's standard Button dispatch which
#     is unreliable on some Android drivers."""
#     CORNER = 8
#     BG = (0.10, 0.11, 0.15, 1)
#     BG_PRESS = (0.18, 0.20, 0.26, 1)
#     MIN_INTERVAL = 0.3

#     def __init__(self, **kwargs):
#         super().__init__(background_normal='', background_color=(0, 0, 0, 0), **kwargs)
#         self._pressed = False
#         self._last_release_t = 0.0
#         self.bind(pos=self._redraw, size=self._redraw)

#     def _redraw(self, *a):
#         self.canvas.before.clear()
#         self.canvas.after.clear()
#         bg = self.BG_PRESS if self._pressed else self.BG
#         with self.canvas.before:
#             Color(*bg)
#             RoundedRectangle(pos=self.pos, size=self.size,
#                              radius=[self.CORNER])
#         self._draw_icon()

#     def _draw_icon(self):
#         pass

#     # FIX: replace on_press/on_release method overrides with explicit
#     # on_touch_down/on_touch_up — the same pattern used by SquareVehicleButton
#     # which works reliably on Android. Kivy's standard Button dispatch
#     # (on_press/on_release events) silently fails on some Android configs.
#     def on_touch_down(self, touch):
#         if self.disabled:
#             return False
#         if self.collide_point(*touch.pos):
#             touch.grab(self)
#             self._pressed = True
#             self._redraw()
#             return True
#         return False

#     def on_touch_up(self, touch):
#         if touch.grab_current is self:
#             touch.ungrab(self)
#             self._pressed = False
#             self._redraw()
#             if self.collide_point(*touch.pos):
#                 # Debounce: swallow a duplicate release event that Android
#                 # sometimes double-fires for the same physical tap.
#                 now = time.monotonic()
#                 if now - self._last_release_t < self.MIN_INTERVAL:
#                     print('ICONBTN', self.__class__.__name__,
#                           'duplicate release swallowed')
#                     return True
#                 self._last_release_t = now
#                 print('ICONBTN', self.__class__.__name__, 'on_release firing')
#                 self.dispatch('on_release')
#             return True
#         return False


# # ── Safe plain-text button (Cancel/Confirm/Set/Reset etc.) ───────────────────
# class SafeButton(Button):
#     """Plain rectangular text button using the same explicit touch-grab
#     handling as IconButton/SquareVehicleButton instead of Kivy's default
#     ButtonBehavior dispatch, which is unreliable on some Android drivers
#     and was causing popup buttons to need two taps (and occasionally
#     double-fire, opening a second overlapping popup)."""
#     MIN_INTERVAL = 0.3

#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self._touch = None
#         self._last_release_t = 0.0

#     def on_touch_down(self, touch):
#         if self.disabled:
#             return False
#         if self.collide_point(*touch.pos):
#             touch.grab(self)
#             self._touch = touch
#             self.state = 'down'
#             return True
#         return False

#     def on_touch_up(self, touch):
#         if touch.grab_current is self:
#             touch.ungrab(self)
#             self._touch = None
#             self.state = 'normal'
#             if self.collide_point(*touch.pos):
#                 now = time.monotonic()
#                 if now - self._last_release_t < self.MIN_INTERVAL:
#                     return True
#                 self._last_release_t = now
#                 self.dispatch('on_release')
#             return True
#         return False


# # ── START / PAUSE button ──────────────────────────────────────────────────────
# class StartPauseButton(IconButton):
#     """Dark icon button showing assets/play.png or assets/pause.png.
#     Both images are pre-loaded and toggled by opacity — no runtime source
#     swap — to avoid the Android texture-reload bug."""

#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self._playing = False
#         self._img_play = None
#         self._img_pause = None
#         src_play = os.path.join(_asset_dir(), 'play.png')
#         src_pause = os.path.join(_asset_dir(), 'pause.png')
#         for path, label in ((src_play, 'play'), (src_pause, 'pause')):
#             if not os.path.exists(path):
#                 print('ICON', label, path,
#                       'MISSING — place a 256x256 RGBA PNG there')
#         if os.path.exists(src_play):
#             self._img_play = KivyImage(source=src_play, allow_stretch=True,
#                                        keep_ratio=True, size_hint=(None, None),
#                                        opacity=1.0)
#             self.add_widget(self._img_play)
#         if os.path.exists(src_pause):
#             self._img_pause = KivyImage(source=src_pause, allow_stretch=True,
#                                         keep_ratio=True, size_hint=(None, None),
#                                         opacity=0)
#             self.add_widget(self._img_pause)

#     def set_playing(self, val):
#         self._playing = val
#         # Toggle opacity only — never swap .source at runtime (unreliable on Android)
#         if self._img_play:
#             self._img_play.opacity = 0 if val else 1.0
#         if self._img_pause:
#             self._img_pause.opacity = 1.0 if val else 0
#         self._redraw()

#     def _draw_icon(self):
#         w, h = self.size
#         sz = min(w, h) * 0.65
#         pos = (self.x + (w - sz) / 2, self.y + (h - sz) / 2)
#         if self._img_play:
#             self._img_play.size = (sz, sz)
#             self._img_play.pos = pos
#         if self._img_pause:
#             self._img_pause.size = (sz, sz)
#             self._img_pause.pos = pos


# # ── UNDO / REDO toggle button ─────────────────────────────────────────────────
# class UndoRedoButton(IconButton):
#     """Single slot that shows undo.png or redo.png via opacity toggle."""

#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self._mode = None
#         self._img_undo = None
#         self._img_redo = None
#         src_undo = os.path.join(_asset_dir(), 'undo.png')
#         src_redo = os.path.join(_asset_dir(), 'redo.png')
#         for path, label in ((src_undo, 'undo'), (src_redo, 'redo')):
#             if not os.path.exists(path):
#                 print('ICON', label, path,
#                       'MISSING — place a 256x256 RGBA PNG there')
#         if os.path.exists(src_undo):
#             self._img_undo = KivyImage(source=src_undo, allow_stretch=True,
#                                        keep_ratio=True, size_hint=(None, None),
#                                        opacity=0.25)
#             self.add_widget(self._img_undo)
#         if os.path.exists(src_redo):
#             self._img_redo = KivyImage(source=src_redo, allow_stretch=True,
#                                        keep_ratio=True, size_hint=(None, None),
#                                        opacity=0)
#             self.add_widget(self._img_redo)
#         self._update_visual()

#     def set_mode(self, mode):
#         self._mode = mode
#         self._update_visual()

#     def _update_visual(self):
#         if self._img_undo is not None:
#             self._img_undo.opacity = (
#                 0 if self._mode == 'redo' else (1.0 if self._mode else 0.25))
#         if self._img_redo is not None:
#             self._img_redo.opacity = 1.0 if self._mode == 'redo' else 0
#         self._redraw()

#     def _draw_icon(self):
#         w, h = self.size
#         sz = min(w, h) * 0.65
#         pos = (self.x + (w - sz) / 2, self.y + (h - sz) / 2)
#         if self._img_undo is not None:
#             self._img_undo.size = (sz, sz)
#             self._img_undo.pos = pos
#         if self._img_redo is not None:
#             self._img_redo.size = (sz, sz)
#             self._img_redo.pos = pos
#         if self._img_undo is not None or self._img_redo is not None:
#             return
#         # Fallback vector if both PNGs missing
#         self.canvas.after.clear()
#         if w < 4 or h < 4:
#             return
#         cx, cy = self.x + w / 2, self.y + h / 2
#         r = min(w, h) * 0.22
#         lw = max(2.0, min(w, h) * 0.05)
#         alpha = 0.95 if self._mode else 0.25
#         flip = -1 if self._mode == 'redo' else 1
#         start_deg, tip_deg = 485, 215
#         with self.canvas.after:
#             Color(1, 1, 1, alpha)
#             Line(circle=(cx, cy, r, tip_deg, start_deg), width=lw, cap='round')
#             ang = math.radians(tip_deg)
#             tipx = cx + flip * r * math.cos(ang)
#             tipy = cy + r * math.sin(ang)
#             head = r * 0.95
#             Triangle(points=[
#                 tipx - flip*head*0.55, tipy + head*0.35,
#                 tipx - flip*head*0.05, tipy - head*0.55,
#                 tipx + flip*head*0.55, tipy + head*0.15,
#             ])


# # ── LOCK / UNLOCK toggle button ───────────────────────────────────────────────
# class LockButton(IconButton):
#     """Shows lock.png when unlocked, unlock.png when locked."""

#     _COL_UNLOCKED = (0.20, 0.45, 0.65, 1)
#     _COL_LOCKED = (0.65, 0.35, 0.10, 1)

#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self._is_locked = False
#         self._img_lock = None
#         self._img_unlock = None
#         src_lock = os.path.join(_asset_dir(), 'lock.png')
#         src_unlock = os.path.join(_asset_dir(), 'unlock.png')
#         for path, label in ((src_lock, 'lock'), (src_unlock, 'unlock')):
#             if not os.path.exists(path):
#                 print('ICON', label, path,
#                       'MISSING — place a 256x256 RGBA PNG there')
#         if os.path.exists(src_lock):
#             self._img_lock = KivyImage(source=src_lock, allow_stretch=True,
#                                        keep_ratio=True, size_hint=(None, None),
#                                        opacity=1.0)
#             self.add_widget(self._img_lock)
#         if os.path.exists(src_unlock):
#             self._img_unlock = KivyImage(source=src_unlock, allow_stretch=True,
#                                          keep_ratio=True, size_hint=(None, None),
#                                          opacity=0)
#             self.add_widget(self._img_unlock)
#         self._update_visual()

#     def set_locked(self, locked):
#         self._is_locked = locked
#         self._update_visual()

#     def _update_visual(self):
#         if self._img_lock:
#             self._img_lock.opacity = 0 if self._is_locked else 1.0
#         if self._img_unlock:
#             self._img_unlock.opacity = 1.0 if self._is_locked else 0
#         self.BG = self._COL_LOCKED if self._is_locked else self._COL_UNLOCKED
#         self._redraw()

#     def _draw_icon(self):
#         w, h = self.size
#         sz = min(w, h) * 0.60
#         pos = (self.x + (w - sz) / 2, self.y + (h - sz) / 2)
#         if self._img_lock:
#             self._img_lock.size = (sz, sz)
#             self._img_lock.pos = pos
#         if self._img_unlock:
#             self._img_unlock.size = (sz, sz)
#             self._img_unlock.pos = pos
#         if self._img_lock is not None or self._img_unlock is not None:
#             return
#         # Fallback vector padlock
#         self.canvas.after.clear()
#         if w < 4 or h < 4:
#             return
#         cx, cy = self.x + w / 2, self.y + h / 2
#         s = min(w, h) * 0.0032
#         lw = max(1.8, min(w, h) * 0.045)
#         bw, bh = 28*s, 22*s
#         with self.canvas.after:
#             Color(1, 1, 1, 0.95)
#             if self._is_locked:
#                 Line(circle=(cx, cy + 10*s, 14*s, 0, 180), width=lw, cap='round')
#             else:
#                 Line(circle=(cx + 14*s, cy + 10*s, 14 *
#                      s, 60, 180), width=lw, cap='round')
#             Line(rounded_rectangle=(cx - bw/2, cy - 18*s, bw, 26*s, 4*s), width=lw)
#             Ellipse(pos=(cx - 5*s, cy - 5*s), size=(10*s, 10*s))
#             Line(points=[cx, cy - 5*s, cx, cy - 14*s], width=lw*0.8)


# # ── Asset paths ───────────────────────────────────────────────────────────────
# _ICON_FILES = {
#     'CAR':  'car.png',  'MOTO': 'moto.png',
#     'LRY':  'lry.png',  'LLRY': 'llry.png',
#     'BUS':  'bus.png',
# }


# def _asset_dir():
#     candidates = [
#         os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets'),
#         os.path.join(os.getcwd(), 'assets'),
#         os.path.join(os.path.expanduser('~'), 'assets'),
#         'assets',
#     ]
#     print("ASSET_DIR candidates:")
#     for d in candidates:
#         exists = os.path.isdir(d)
#         print(f"  {'OK' if exists else '--'} {d}")
#         if exists:
#             print(f"     contents: {os.listdir(d)}")
#             return d
#     print(f"  none found, defaulting to: {candidates[0]}")
#     return candidates[0]


# _ASSET_DIR = _asset_dir()
# print("ASSET_DIR resolved to:", _ASSET_DIR)


# def _icon_path(key):
#     path = os.path.join(_ASSET_DIR, _ICON_FILES[key])
#     exists = os.path.exists(path)
#     print('ICON', key, path, 'OK' if exists else 'MISSING')
#     return path if exists else None


# # ── Square vehicle button ─────────────────────────────────────────────────────
# class SquareVehicleButton(Button):
#     CORNER_RADIUS = 8
#     PRESS_TIMEOUT = 1.0

#     def __init__(self, key, circle_color, label_text, **kwargs):
#         super().__init__(background_normal='', background_color=(0, 0, 0, 0), **kwargs)
#         self.key = key
#         self.circle_color = circle_color
#         self.label_text = label_text
#         self._pressed = False
#         self._touch = None
#         self._timeout_ev = None
#         cr = circle_color
#         self._col_normal = (None, cr)
#         self._col_press = ((1, 1, 1, 0.9),
#                            (cr[0]*0.38, cr[1]*0.38, cr[2]*0.38, cr[3]))
#         self._r = self.CORNER_RADIUS
#         self._ring = 6
#         self.bind(pos=self._redraw, size=self._redraw)

#         self._img = None
#         icon_path = _icon_path(key)
#         if icon_path:
#             self._img = KivyImage(source=icon_path, allow_stretch=True,
#                                   keep_ratio=True, size_hint=(None, None))
#             self.add_widget(self._img)

#         # FIX: letter label under the icon removed per request — icon now
#         # fills the full button height instead of sharing space with it.
#         self._redraw()

#     def _redraw(self, *a):
#         w, h = self.size
#         pad = 8
#         icon_zone_h = h - pad * 2
#         icon_zone_y = self.y + pad
#         if self._img:
#             icon_sz = min(w, icon_zone_h) * 0.82
#             self._img.size = (icon_sz, icon_sz)
#             self._img.pos = (self.x + (w - icon_sz) / 2,
#                              icon_zone_y + (icon_zone_h - icon_sz) / 2)
#         else:
#             self.canvas.after.clear()
#             cx = self.x + w / 2
#             cy = icon_zone_y + icon_zone_h / 2
#             sz = min(w, icon_zone_h) * 0.92
#             with self.canvas.after:
#                 draw_icon(self.canvas.after, self.key, cx, cy, sz)
#         cr = self.circle_color
#         self._col_normal = (None, cr)
#         self._col_press = ((1, 1, 1, 0.9),
#                            (cr[0]*0.38, cr[1]*0.38, cr[2]*0.38, cr[3]))
#         self._r = self.CORNER_RADIUS
#         self._ring = 6
#         self._redraw_bg()

#     def _redraw_bg(self):
#         self.canvas.before.clear()
#         w, h = self.size
#         with self.canvas.before:
#             if self._pressed:
#                 Color(*self._col_press[0])
#                 RoundedRectangle(pos=(self.x - self._ring, self.y - self._ring),
#                                  size=(w + self._ring*2, h + self._ring*2),
#                                  radius=[self._r + self._ring])
#                 Color(*self._col_press[1])
#             else:
#                 Color(*self._col_normal[1])
#             RoundedRectangle(pos=self.pos, size=self.size, radius=[self._r])

#     def on_touch_down(self, touch):
#         if self.disabled:
#             return False
#         if self.collide_point(*touch.pos):
#             if self._pressed:
#                 self._clear_press()
#             touch.grab(self)
#             self._touch = touch
#             self._pressed = True
#             self._redraw_bg()
#             self._arm_timeout()
#             return True
#         return super().on_touch_down(touch)

#     def on_touch_up(self, touch):
#         if touch.grab_current is self:
#             touch.ungrab(self)
#             self._cancel_timeout()
#             self._touch = None
#             self._pressed = False
#             self._redraw_bg()
#             if self.collide_point(*touch.pos):
#                 self.dispatch('on_release')
#             return True
#         return super().on_touch_up(touch)

#     def _arm_timeout(self):
#         self._cancel_timeout()
#         self._timeout_ev = Clock.schedule_once(
#             self._force_release, self.PRESS_TIMEOUT)

#     def _cancel_timeout(self):
#         if getattr(self, '_timeout_ev', None):
#             self._timeout_ev.cancel()
#             self._timeout_ev = None

#     def _force_release(self, dt):
#         self._clear_press()

#     def _clear_press(self):
#         self._cancel_timeout()
#         if self._touch is not None:
#             try:
#                 self._touch.ungrab(self)
#             except Exception:
#                 pass
#         self._touch = None
#         self._pressed = False
#         self._redraw_bg()

#     def on_press(self):
#         pass

#     def on_release(self):
#         self._pressed = False
#         self._redraw_bg()


# # ── Grid cluster ──────────────────────────────────────────────────────────────
# GRID_KEYS_LEFT = [
#     ["LRY",  None],
#     ["MOTO", "CAR"],
#     ["LLRY", "BUS"],
# ]
# GRID_KEYS_RIGHT = [
#     [None,   "LRY"],
#     ["CAR",  "MOTO"],
#     ["BUS",  "LLRY"],
# ]


# class SquareGridCluster(GridLayout):
#     SEP = 3

#     def __init__(self, on_tap, corner, timer_widget=None, on_undo=None,
#                  on_redo=None, is_locked=None, **kwargs):
#         grid_keys = GRID_KEYS_LEFT if corner == 'left' else GRID_KEYS_RIGHT
#         super().__init__(cols=len(grid_keys[0]), rows=len(grid_keys),
#                          spacing=self.SEP, padding=0, **kwargs)
#         self.on_tap = on_tap
#         self.corner = corner
#         self._buttons = {}
#         self._is_locked = is_locked or (lambda: False)

#         for row in grid_keys:
#             for key in row:
#                 if key is None:
#                     if corner == 'right' and timer_widget is not None:
#                         sp = StartPauseButton(size_hint=(1, 1))
#                         sp.bind(on_release=lambda b: (
#                             None if self._is_locked() else (
#                                 play_startpause(), timer_widget._toggle())))
#                         timer_widget._ext_btn_ss = sp
#                         self.add_widget(sp)
#                     elif corner == 'left' and (on_undo is not None or on_redo is not None):
#                         ub = UndoRedoButton(size_hint=(1, 1))

#                         # FIX: the previous version had the
#                         # "if ub._mode else None" clause outside the lambda's
#                         # parentheses, so it was evaluated once at bind time
#                         # (when ub._mode was still None) instead of on every
#                         # tap — permanently binding on_release to None.
#                         # Using a real function closed over `ub` re-checks
#                         # ub._mode every time the button is released.
#                         def _undo_redo_release(b, ub=ub):
#                             if self._is_locked():
#                                 return
#                             if ub._mode == 'undo':
#                                 haptic_tap()
#                                 play_startpause()
#                                 on_undo()
#                             elif ub._mode == 'redo':
#                                 haptic_tap()
#                                 play_startpause()
#                                 on_redo()

#                         ub.bind(on_release=_undo_redo_release)
#                         self._undo_redo_btn = ub
#                         self.add_widget(ub)
#                     else:
#                         self.add_widget(self._make_filler())
#                 else:
#                     short, color = VEHICLES[key]
#                     btn = SquareVehicleButton(key=key, circle_color=color,
#                                               label_text=short, size_hint=(1, 1))
#                     btn.bind(on_release=lambda b, k=key: self._tap(k))
#                     self._buttons[key] = btn
#                     self.add_widget(btn)

#     def _make_filler(self):
#         filler = BoxLayout()
#         with filler.canvas.before:
#             Color(0.13, 0.14, 0.18, 1)
#             rect = Rectangle(pos=filler.pos, size=filler.size)
#         filler._rect = rect

#         def _upd(w, *a):
#             w._rect.pos = w.pos
#             w._rect.size = w.size
#         filler.bind(pos=_upd, size=_upd)
#         return filler

#     def _tap(self, key):
#         self.on_tap(key)
#         if self._is_locked():
#             return
#         import threading
#         threading.Thread(target=lambda: (
#             haptic_tap(), play_tap()), daemon=True).start()


# # ── Summary chip ──────────────────────────────────────────────────────────────
# class SummaryChip(Button):
#     def __init__(self, chip_color, **kwargs):
#         self._chip_color = chip_color
#         self._dim = tuple(max(0, c*0.35) if i < 3 else c
#                           for i, c in enumerate(chip_color))
#         self._flash_ev = None
#         super().__init__(background_normal='', background_color=chip_color, **kwargs)

#     def flash(self):
#         if self._flash_ev:
#             self._flash_ev.cancel()
#         self.background_color = list(self._dim)
#         self._flash_ev = Clock.schedule_once(
#             lambda dt: setattr(self, 'background_color', list(self._chip_color)), 0.08)


# class JunctionSummary(BoxLayout):
#     def __init__(self, on_minus, order=None, is_locked=None, **kwargs):
#         kwargs.setdefault('orientation', 'horizontal')
#         kwargs.setdefault('spacing', 6)
#         kwargs.setdefault('padding', [8, 6, 8, 6])
#         super().__init__(**kwargs)
#         self.on_minus = on_minus
#         self.is_locked = is_locked or (lambda: False)
#         self.counts = {k: 0 for k in VEHICLES}
#         # FIX: per-key debounce timestamps — prevents Android double-release
#         # from decrementing by 2 on a single tap.
#         self._last_minus_t = {}
#         self.chips = {}
#         for key in (order or SUMMARY_ORDER_LEFT):
#             short, color = VEHICLES[key]
#             btn = SummaryChip(chip_color=color, text=f"{short}: 0",
#                               font_size=24, bold=True, color=(1, 1, 1, 1),
#                               size_hint=(1, 1))
#             btn.bind(on_release=lambda b, k=key: self._minus(k))
#             self.chips[key] = (btn, short)
#             self.add_widget(btn)

#     def _minus(self, key):
#         if self.is_locked():
#             return
#         # Debounce: ignore a second call within 300 ms of the first.
#         now = time.monotonic()
#         if now - self._last_minus_t.get(key, 0) < 0.30:
#             return
#         self._last_minus_t[key] = now
#         if self.counts[key] > 0:
#             self.counts[key] -= 1
#             self._refresh(key)
#             self.chips[key][0].flash()
#             self.on_minus()
#             import threading
#             threading.Thread(target=lambda: (
#                 haptic_tap(), play_tap()), daemon=True).start()

#     def _refresh(self, key):
#         btn, short = self.chips[key]
#         btn.text = f"{short}: {self.counts[key]}"

#     def increment(self, key): self.counts[key] += 1; self._refresh(key)
#     def get_counts(self): return dict(self.counts)

#     def set_counts(self, data):
#         for k, v in data.items():
#             if k in self.counts:
#                 self.counts[k] = max(0, int(v))
#                 self._refresh(k)

#     def reset(self):
#         for k in self.counts:
#             self.counts[k] = 0
#             self._refresh(k)


# # ── Timer widget ──────────────────────────────────────────────────────────────
# BASE_FONT = 48


# class TimerWidget(BoxLayout):
#     def __init__(self, **kwargs):
#         super().__init__(orientation='vertical', spacing=6, **kwargs)
#         self._duration = DEFAULT_TIMER
#         self._remaining = DEFAULT_TIMER
#         self._running = False
#         self._tick_ev = None
#         self._alert_ev = None
#         self._alert_idx = 0
#         self._ext_btn_ss = None
#         # FIX: re-entrancy guard so a double-fired tap on SET can't stack a
#         # second Set-Timer popup underneath the first one.
#         self._set_popup_open = False

#         # FIX (background timer): instead of only counting down via Clock
#         # ticks (which Android suspends while the app is minimised), we
#         # anchor the countdown to a wall-clock deadline. Whenever the app
#         # resumes, the remaining time is recomputed from real elapsed time
#         # rather than from however many ticks happened to fire.
#         self._deadline = None   # time.time() value when countdown hits 0, while running
#         self._pending_alarm = False  # timer expired while backgrounded; alarm not yet played

#         self.lbl = Label(text=self._fmt(DEFAULT_TIMER), font_size=BASE_FONT,
#                          bold=True, color=(0.55, 0.92, 0.55, 1),
#                          size_hint=(1, 1), halign='center', valign='middle')
#         self.lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
#         self.add_widget(self.lbl)

#         # FIX: timer's own RESET button removed — RESET ALL (top bar)
#         # already resets the timer alongside the counts, so this was
#         # redundant. Only SET remains, now spanning the full row.
#         row = BoxLayout(orientation='horizontal', size_hint=(1, None),
#                         height=46, spacing=6, padding=[4, 0, 4, 0])
#         self._btn_set = self._mk("SET", (0.25, 0.35, 0.60, 1))
#         self._btn_set.bind(on_release=self._open_set)
#         row.add_widget(self._btn_set)
#         self.add_widget(row)

#     def set_locked(self, locked):
#         alpha = 0.25 if locked else 1.0
#         self._btn_set.opacity = alpha
#         self._btn_set.disabled = locked
#         if self._ext_btn_ss:
#             self._ext_btn_ss.opacity = alpha
#             self._ext_btn_ss.disabled = locked

#     def _mk(self, t, bg):
#         # FIX: SafeButton instead of plain Button — plain Kivy Button
#         # dispatch was unreliable on Android, requiring double taps and
#         # occasionally double-firing (which stacked a second popup).
#         return SafeButton(text=t, font_size=15, bold=True, color=(1, 1, 1, 1),
#                           background_normal='', background_color=bg, size_hint=(1, 1))

#     def _fmt(self, secs):
#         m, s = divmod(max(0, int(secs)), 60)
#         return f"{m:02d}:{s:02d}"

#     def _toggle(self, *a):
#         self._pause() if self._running else self._start()

#     def _set_btn_state(self, running):
#         if self._ext_btn_ss:
#             self._ext_btn_ss.set_playing(running)

#     def _start(self):
#         if self._remaining <= 0:
#             return
#         self._running = True
#         self._set_btn_state(True)
#         self._stop_alert()
#         self.lbl.color = (0.55, 0.92, 0.55, 1)
#         self.lbl.font_size = BASE_FONT
#         # FIX: anchor to a wall-clock deadline instead of just counting
#         # ticks, so the countdown stays correct across a background/
#         # foreground cycle even if Android suspends the Clock in between.
#         self._deadline = time.time() + self._remaining
#         self._tick_ev = Clock.schedule_interval(self._tick, 1)

#     def _pause(self):
#         self._running = False
#         self._set_btn_state(False)
#         if self._tick_ev:
#             self._tick_ev.cancel()
#         if self._deadline is not None:
#             self._remaining = max(0, self._deadline - time.time())
#             self._deadline = None

#     def _tick(self, dt):
#         if self._deadline is None:
#             return
#         remaining = self._deadline - time.time()
#         if remaining <= 0:
#             self._remaining = 0
#             self.lbl.text = self._fmt(0)
#             self._pause()
#             self._expire()
#         else:
#             self._remaining = remaining
#             self.lbl.text = self._fmt(remaining)

#     def _expire(self):
#         # FIX: don't blast the alarm sound while the app is minimised —
#         # only actually play it once the user is back looking at the app.
#         # If we're already in the foreground, that's immediately.
#         global _APP_FOREGROUND
#         if _APP_FOREGROUND:
#             self._pending_alarm = False
#             self._alert()
#         else:
#             self._pending_alarm = True

#     def on_app_resume(self):
#         """Called by the App on returning to the foreground. Recomputes
#         the countdown from wall-clock time and fires the alarm now if it
#         expired while the app was minimised."""
#         if self._running and self._deadline is not None:
#             remaining = self._deadline - time.time()
#             if remaining <= 0:
#                 self._remaining = 0
#                 self.lbl.text = self._fmt(0)
#                 self._pause()
#                 self._pending_alarm = False
#                 self._alert()
#                 return
#             self._remaining = remaining
#             self.lbl.text = self._fmt(remaining)
#         if self._pending_alarm:
#             self._pending_alarm = False
#             self._alert()

#     def _alert(self):
#         play_alarm()
#         self._alert_idx = 0
#         self._alert_ev = Clock.schedule_interval(self._alert_step, 0.25)

#     def _alert_step(self, dt):
#         self._alert_idx += 1
#         if self._alert_idx % 2 == 0:
#             self.lbl.font_size = BASE_FONT * 1.35
#             self.lbl.color = (1, 0.08, 0.08, 1)
#         else:
#             self.lbl.font_size = BASE_FONT * 0.85
#             self.lbl.color = (0.75, 0.05, 0.05, 1)

#     def _stop_alert(self):
#         if self._alert_ev:
#             self._alert_ev.cancel()
#             self._alert_ev = None

#     def _reset_timer(self, *a):
#         self._pause()
#         self._stop_alert()
#         self._remaining = self._duration
#         self._deadline = None
#         self._pending_alarm = False
#         self.lbl.text = self._fmt(self._remaining)
#         self.lbl.color = (0.55, 0.92, 0.55, 1)
#         self.lbl.font_size = BASE_FONT

#     def reset_to_default(self): self._reset_timer()

#     def stop_alert(self):
#         self._stop_alert()
#         self._pending_alarm = False
#         self.lbl.color = (0.55, 0.92, 0.55, 1)
#         self.lbl.font_size = BASE_FONT

#     def _open_set(self, *a):
#         # FIX: guard against a duplicate/double-fired tap opening a second
#         # Set-Timer popup on top of the first (the root cause of "press Set
#         # twice" and the minute value reverting to default).
#         if self._set_popup_open:
#             return
#         self._set_popup_open = True

#         self._pause()
#         prev_duration = self._duration
#         prev_m, prev_s = divmod(prev_duration, 60)

#         content = BoxLayout(orientation='vertical', spacing=12, padding=20)
#         content.add_widget(Label(text="Set Timer", font_size=20, bold=True,
#                                  color=(1, 1, 1, 1), size_hint=(1, None), height=34,
#                                  halign='center'))
#         time_row = BoxLayout(orientation='horizontal', size_hint=(1, None),
#                              height=70, spacing=0)

#         def _inp(hint):
#             return TextInput(hint_text=hint, text="", font_size=36,
#                              foreground_color=(1, 1, 1, 1),
#                              hint_text_color=(0.5, 0.5, 0.5, 1),
#                              background_color=(0.15, 0.17, 0.21, 1),
#                              cursor_color=(1, 1, 1, 1), size_hint=(1, 1),
#                              multiline=False, halign='center', input_filter='int')
#         inp_m = _inp("MM")
#         inp_s = _inp("SS")
#         colon = Label(text=":", font_size=36, bold=True, color=(1, 1, 1, 1),
#                       size_hint=(None, 1), width=28)
#         time_row.add_widget(inp_m)
#         time_row.add_widget(colon)
#         time_row.add_widget(inp_s)
#         content.add_widget(time_row)

#         btns = BoxLayout(orientation='horizontal', spacing=10,
#                          size_hint=(1, None), height=56)
#         cancel = self._mk("Cancel", (0.30, 0.32, 0.38, 1))
#         confirm = self._mk("Set",    (0.20, 0.55, 0.30, 1))
#         btns.add_widget(cancel)
#         btns.add_widget(confirm)
#         content.add_widget(btns)

#         # FIX: auto_dismiss=False — prevents the first tap from landing on
#         # the semi-transparent overlay and dismissing the popup before the
#         # button registers (which made it feel like two presses were needed).
#         popup = Popup(title='Set Timer', title_size=20, content=content,
#                       size_hint=(0.55, None), height=280,
#                       pos_hint={'center_x': 0.5, 'top': 0.98},
#                       background_color=(0.14, 0.15, 0.20, 1),
#                       title_color=(1, 1, 1, 1),
#                       separator_color=(0.25, 0.27, 0.32, 1),
#                       auto_dismiss=False)

#         def _cancel(*a):
#             self._duration = prev_duration
#             self._remaining = prev_duration
#             self.lbl.text = self._fmt(prev_duration)
#             popup.dismiss()

#         def _apply(*a):
#             try:
#                 m_val = int(inp_m.text.strip()
#                             ) if inp_m.text.strip() else prev_m
#                 s_val = int(inp_s.text.strip()
#                             ) if inp_s.text.strip() else prev_s
#                 s_val = max(0, min(59, s_val))
#                 self._duration = max(1, m_val*60 + s_val)
#             except Exception:
#                 self._duration = prev_duration
#             self._remaining = self._duration
#             self.lbl.text = self._fmt(self._remaining)
#             self.lbl.color = (0.55, 0.92, 0.55, 1)
#             self.lbl.font_size = BASE_FONT
#             self._stop_alert()
#             popup.dismiss()

#         cancel.bind(on_release=_cancel)
#         confirm.bind(on_release=_apply)
#         # FIX: clear the re-entrancy guard once the popup actually closes,
#         # whichever button (or code path) triggered the dismiss.
#         popup.bind(on_dismiss=lambda *a: setattr(self,
#                    '_set_popup_open', False))
#         popup.open()


# # ── Loading screen ────────────────────────────────────────────────────────────
# class LoadingScreen(FloatLayout):
#     def __init__(self, on_done, **kwargs):
#         super().__init__(**kwargs)
#         self._on_done = on_done
#         with self.canvas.before:
#             Color(0.08, 0.09, 0.12, 1)
#             self._bg = Rectangle(pos=self.pos, size=self.size)
#         self.bind(pos=self._upd_bg, size=self._upd_bg)

#         for text, hint, cy in [
#             ('PATSB',           72, 0.60),
#             ('Traffic Counter', 26, 0.46),
#         ]:
#             self.add_widget(Label(text=text, font_size=hint,
#                                   bold=(hint == 72),
#                                   color=(0.10, 0.45, 0.90, 1) if hint == 72 else (
#                                       0.65, 0.70, 0.78, 1),
#                                   halign='center', valign='middle',
#                                   pos_hint={'center_x': 0.5, 'center_y': cy},
#                                   size_hint=(1, None), height=hint+18))

#         self._status = Label(text='Initialising...', font_size=18,
#                              color=(0.40, 0.45, 0.52, 1), halign='center', valign='middle',
#                              pos_hint={'center_x': 0.5, 'center_y': 0.28},
#                              size_hint=(1, None), height=28)
#         self.add_widget(self._status)

#         self._bar_widget = FloatLayout(size_hint=(0.5, None), height=14,
#                                        pos_hint={'center_x': 0.5, 'center_y': 0.16})
#         self.add_widget(self._bar_widget)
#         self._bar_progress = 0.0
#         self._target = 0.0
#         self._bar_ev = Clock.schedule_interval(self._animate, 0.03)
#         self._bar_widget.bind(pos=self._draw_bar, size=self._draw_bar)
#         Clock.schedule_once(self._step1, 0.3)

#     def _upd_bg(self, *a):
#         self._bg.pos = self.pos
#         self._bg.size = self.size

#     def _draw_bar(self, *a):
#         w = self._bar_widget
#         w.canvas.clear()
#         bw, bh = w.width, w.height
#         if bw < 1:
#             return
#         with w.canvas:
#             Color(0.20, 0.22, 0.28, 1)
#             RoundedRectangle(pos=(w.x, w.y), size=(bw, bh), radius=[bh/2])
#             Color(0.10, 0.45, 0.90, 1)
#             fill_w = max(bh, bw*self._bar_progress)
#             RoundedRectangle(pos=(w.x, w.y), size=(fill_w, bh), radius=[bh/2])

#     def _animate(self, dt):
#         gap = self._target - self._bar_progress
#         if gap > 0:
#             self._bar_progress += max(0.002, gap*0.08)
#         self._bar_progress = min(self._target, self._bar_progress)
#         self._draw_bar()

#     def _step1(self, dt):
#         self._status.text = 'Loading sounds...'
#         _init_sounds()
#         self._target = 0.40
#         Clock.schedule_once(self._step2, 0.5)

#     def _step2(self, dt):
#         self._status.text = 'Loading assets...'
#         self._target = 0.75
#         Clock.schedule_once(self._step3, 0.5)

#     def _step3(self, dt):
#         self._status.text = 'Ready!'
#         self._target = 1.0
#         Clock.schedule_interval(self._wait_full, 0.05)

#     def _wait_full(self, dt):
#         if self._bar_progress >= 0.995:
#             Clock.unschedule(self._wait_full)
#             Clock.schedule_once(self._finish, 0.18)
#             return False

#     def _finish(self, dt):
#         if self._bar_ev:
#             self._bar_ev.cancel()
#         self._on_done()


# # ── Root layout ───────────────────────────────────────────────────────────────
# class RootLayout(FloatLayout):
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self._undo_snapshot = None
#         self._redo_snapshot = None
#         self._locked = False
#         # FIX: re-entrancy guard so a double-fired tap on RESET ALL can't
#         # stack a second confirm-reset popup underneath the first.
#         self._reset_popup_open = False

#         top = BoxLayout(size_hint=(1, None), height=TOP_H,
#                         pos_hint={'x': 0, 'top': 1},
#                         spacing=6, padding=[6, 6, 6, 6])
#         self.j1_summary = JunctionSummary(on_minus=self._on_minus,
#                                           order=SUMMARY_ORDER_LEFT,
#                                           is_locked=lambda: self._locked,
#                                           size_hint=(0.42, 1))
#         # FIX: SafeButton instead of plain Button for the same reason as
#         # the timer's SET/RESET buttons — reliable single-tap dispatch.
#         self.reset_btn = SafeButton(text="RESET ALL", font_size=16, bold=True,
#                                     color=(1, 1, 1, 1), background_normal='',
#                                     background_color=(0.75, 0.20, 0.20, 1),
#                                     size_hint=(0.16, 1))
#         self.reset_btn.bind(on_release=self._confirm_reset)
#         self.j2_summary = JunctionSummary(on_minus=self._on_minus,
#                                           order=SUMMARY_ORDER_RIGHT,
#                                           is_locked=lambda: self._locked,
#                                           size_hint=(0.42, 1))
#         top.add_widget(self.j1_summary)
#         top.add_widget(self.reset_btn)
#         top.add_widget(self.j2_summary)
#         self.add_widget(top)

#         self.timer = TimerWidget(size_hint=(1, 1))

#         LOCK_BTN_H = 48
#         self.lock_btn = LockButton(size_hint=(1, None), height=LOCK_BTN_H)
#         self.lock_btn.bind(on_release=self._toggle_lock)
#         self._lock_btn_h = LOCK_BTN_H

#         self.j1_cluster = SquareGridCluster(
#             on_tap=self._j1_tap, corner='left',
#             on_undo=self._do_undo, on_redo=self._do_redo,
#             is_locked=lambda: self._locked,
#             size_hint=(None, None), pos_hint={'x': 0, 'y': 0})

#         self.j2_cluster = SquareGridCluster(
#             on_tap=self._j2_tap, corner='right',
#             timer_widget=self.timer,
#             is_locked=lambda: self._locked,
#             size_hint=(None, None), pos_hint={'right': 1, 'y': 0})

#         self.add_widget(self.j1_cluster)
#         self.add_widget(self.j2_cluster)

#         self.timer_box = BoxLayout(orientation='vertical', spacing=6,
#                                    size_hint=(None, None),
#                                    pos_hint={'center_x': 0.5})
#         self.timer_box.add_widget(self.timer)
#         self.timer_box.add_widget(self.lock_btn)
#         self.add_widget(self.timer_box)

#         self.bind(size=self._layout)
#         self.reset_btn.bind(size=self._layout)
#         self.j1_summary.chips['MOTO'][0].bind(
#             pos=self._layout, size=self._layout)
#         self.j2_summary.chips['CAR'][0].bind(
#             pos=self._layout,  size=self._layout)
#         self._load()

#     def _layout(self, *a):
#         W, H = self.size
#         cluster_h = H - TOP_H

#         moto_chip = self.j1_summary.chips['MOTO'][0]
#         left_grid_w = moto_chip.right if moto_chip.width > 1 else W*0.42

#         car_chip = self.j2_summary.chips['CAR'][0]
#         right_grid_x = car_chip.x if car_chip.width > 1 else W*0.58
#         right_grid_w = W - right_grid_x

#         self.j1_cluster.size = (left_grid_w, cluster_h)
#         self.j1_cluster.pos = (0, 0)
#         self.j2_cluster.size = (right_grid_w, cluster_h)
#         self.j2_cluster.pos = (right_grid_x, 0)

#         timer_w = self.reset_btn.width if self.reset_btn.width > 1 else W*0.16
#         total_box_h = min(TIMER_H + self._lock_btn_h + 6, cluster_h - 12)
#         self.timer_box.size = (timer_w, total_box_h)
#         self.timer_box.pos = (W/2 - timer_w/2, (cluster_h - total_box_h)/2)

#     def _j1_tap(self, key):
#         if self._locked:
#             return
#         self.j1_summary.increment(key)
#         self._lock_undo_redo()
#         self._save()

#     def _j2_tap(self, key):
#         if self._locked:
#             return
#         self.j2_summary.increment(key)
#         self._lock_undo_redo()
#         self._save()

#     def _on_minus(self):
#         self._lock_undo_redo()
#         self._save()

#     def _lock_undo_redo(self):
#         # FIX: once counting resumes (a tap or a minus) after an undo/redo,
#         # the undo/redo snapshot chain no longer reflects a safe state to
#         # revert to, so lock the button (mode=None dims it and makes taps
#         # a no-op — see UndoRedoButton / _undo_redo_release).
#         if self._undo_snapshot is not None or self._redo_snapshot is not None:
#             self._undo_snapshot = None
#             self._redo_snapshot = None
#             self._set_undo_redo_mode(None)

#     def _toggle_lock(self, *a):
#         self._locked = not self._locked
#         self.lock_btn.set_locked(self._locked)
#         if self._locked:
#             self.timer._pause()
#             self.reset_btn.disabled = True
#             self.reset_btn.opacity = 0.25
#             self.timer.set_locked(True)
#             if hasattr(self.j1_cluster, '_undo_redo_btn'):
#                 self.j1_cluster._undo_redo_btn.disabled = True
#                 self.j1_cluster._undo_redo_btn.opacity = 0.25
#             for summary in (self.j1_summary, self.j2_summary):
#                 for btn, _ in summary.chips.values():
#                     btn.disabled = True
#                     btn.opacity = 0.35
#             for cluster in (self.j1_cluster, self.j2_cluster):
#                 for btn in cluster._buttons.values():
#                     btn.disabled = True
#                     btn.opacity = 0.35
#         else:
#             self.reset_btn.disabled = False
#             self.reset_btn.opacity = 1.0
#             self.timer.set_locked(False)
#             if hasattr(self.j1_cluster, '_undo_redo_btn'):
#                 self.j1_cluster._undo_redo_btn.disabled = False
#                 self.j1_cluster._undo_redo_btn.opacity = 1.0
#             for summary in (self.j1_summary, self.j2_summary):
#                 for btn, _ in summary.chips.values():
#                     btn.disabled = False
#                     btn.opacity = 1.0
#             for cluster in (self.j1_cluster, self.j2_cluster):
#                 for btn in cluster._buttons.values():
#                     btn.disabled = False
#                     btn.opacity = 1.0

#     def _save(self, *a):
#         if hasattr(self, '_save_ev') and self._save_ev:
#             self._save_ev.cancel()
#         self._save_ev = Clock.schedule_once(self._save_bg, 0.5)

#     def _save_bg(self, dt=None):
#         import threading
#         data = {'j1': self.j1_summary.get_counts(),
#                 'j2': self.j2_summary.get_counts()}

#         def _write():
#             try:
#                 with open(SAVE_FILE, 'w') as f:
#                     json.dump(data, f)
#             except Exception as e:
#                 print("Save error:", e)
#         threading.Thread(target=_write, daemon=True).start()

#     def _load(self):
#         try:
#             if os.path.exists(SAVE_FILE):
#                 with open(SAVE_FILE, 'r') as f:
#                     d = json.load(f)
#                 self.j1_summary.set_counts(d.get('j1', {}))
#                 self.j2_summary.set_counts(d.get('j2', {}))
#         except Exception as e:
#             print("Load error:", e)

#     def _confirm_reset(self, *a):
#         # FIX: guard against a duplicate/double-fired tap on RESET ALL
#         # opening a second confirm popup on top of the first.
#         if self._reset_popup_open:
#             return
#         self._reset_popup_open = True

#         content = BoxLayout(orientation='vertical', spacing=16, padding=24)
#         content.add_widget(Label(text="Reset all counts?", halign='center',
#                                  valign='middle', color=(1, 1, 1, 1),
#                                  font_size=22, size_hint=(1, 1)))
#         btns = BoxLayout(orientation='horizontal', spacing=12,
#                          size_hint=(1, None), height=70)

#         def _mk(t, bg):
#             # FIX: SafeButton instead of plain Button (see SafeButton docstring).
#             return SafeButton(text=t, font_size=18, bold=True, color=(1, 1, 1, 1),
#                               background_normal='', background_color=bg, size_hint=(1, 1))
#         cancel = _mk("Cancel", (0.30, 0.32, 0.38, 1))
#         confirm = _mk("Reset",  (0.75, 0.20, 0.20, 1))
#         btns.add_widget(cancel)
#         btns.add_widget(confirm)
#         content.add_widget(btns)

#         # FIX: auto_dismiss=False — same reason as the Set Timer popup.
#         popup = Popup(title='Confirm', title_size=20, content=content,
#                       size_hint=(0.65, 0.45),
#                       background_color=(0.14, 0.15, 0.20, 1),
#                       title_color=(1, 1, 1, 1),
#                       separator_color=(0.25, 0.27, 0.32, 1),
#                       auto_dismiss=False)
#         cancel.bind(on_release=lambda *a: popup.dismiss())
#         confirm.bind(on_release=lambda *a: (self._do_reset(), popup.dismiss()))
#         # FIX: clear the re-entrancy guard once the popup actually closes.
#         popup.bind(on_dismiss=lambda *a: setattr(self,
#                    '_reset_popup_open', False))
#         popup.open()

#     def _do_reset(self):
#         self._undo_snapshot = (
#             self.j1_summary.get_counts(),
#             self.j2_summary.get_counts(),
#         )
#         self._redo_snapshot = None
#         self.j1_summary.reset()
#         self.j2_summary.reset()
#         self.timer.stop_alert()
#         self.timer.reset_to_default()
#         self._save()
#         self._set_undo_redo_mode('undo')

#     def _do_undo(self):
#         if self._undo_snapshot is None:
#             return
#         self._redo_snapshot = (
#             self.j1_summary.get_counts(),
#             self.j2_summary.get_counts(),
#         )
#         j1_snap, j2_snap = self._undo_snapshot
#         self.j1_summary.set_counts(j1_snap)
#         self.j2_summary.set_counts(j2_snap)
#         self._undo_snapshot = None
#         self._save()
#         self._set_undo_redo_mode('redo')

#     def _do_redo(self):
#         if self._redo_snapshot is None:
#             return
#         self._undo_snapshot = (
#             self.j1_summary.get_counts(),
#             self.j2_summary.get_counts(),
#         )
#         j1_snap, j2_snap = self._redo_snapshot
#         self.j1_summary.set_counts(j1_snap)
#         self.j2_summary.set_counts(j2_snap)
#         self._redo_snapshot = None
#         self._save()
#         self._set_undo_redo_mode('undo')

#     def _set_undo_redo_mode(self, mode):
#         if hasattr(self.j1_cluster, '_undo_redo_btn'):
#             self.j1_cluster._undo_redo_btn.set_mode(mode)


# class TrafficCounterApp(App):
#     def build(self):
#         Window.fullscreen = 'auto'
#         Window.orientation = 'landscape'
#         self._root = FloatLayout()
#         self._root.add_widget(LoadingScreen(on_done=self._launch))
#         return self._root

#     def _launch(self):
#         self._root.clear_widgets()
#         self._root.add_widget(RootLayout())

#     def on_start(self):
#         if platform == 'android':
#             _init_haptic()
#             Window.update_viewport()
#             try:
#                 from kivy.base import EventLoop
#                 from kivy.input.providers.androidjoystick import AndroidMotionEventProvider
#                 EventLoop.remove_input_provider_by_name('android')
#                 EventLoop.add_input_provider(
#                     AndroidMotionEventProvider('android', ''))
#             except Exception as e:
#                 print("Touch provider override failed:", e)

#     def on_stop(self):
#         root = self._root.children[0] if self._root.children else None
#         if isinstance(root, RootLayout):
#             root._save_bg()

#     # FIX (background timer): Android calls on_pause when the app is
#     # minimised/loses focus and on_resume when it's brought back. We use
#     # these to flip _APP_FOREGROUND (which suppresses the alarm sound
#     # while away) and to make the timer recompute against wall-clock time
#     # once the user is looking at the screen again.
#     def on_pause(self):
#         global _APP_FOREGROUND
#         _APP_FOREGROUND = False
#         return True  # tells Android to keep the app alive in the background

#     def on_resume(self):
#         global _APP_FOREGROUND
#         _APP_FOREGROUND = True
#         root = self._root.children[0] if self._root.children else None
#         if isinstance(root, RootLayout):
#             root.timer.on_app_resume()


# if __name__ == '__main__':
#     TrafficCounterApp().run()
