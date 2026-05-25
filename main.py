"""
PATSB Traffic Counter — Kivy landscape, rainbow arc clusters
"""
import json, os, math

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
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle, Rectangle
from kivy.clock import Clock

Window.clearcolor = (0.08, 0.09, 0.12, 1)
if platform != 'android':
    Window.size = (1280, 720)

SAVE_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic_save.json")
DEFAULT_TIMER = 15 * 60
SUMMARY_ORDER = ["CAR", "LRY", "LLRY", "BUS", "MOTO"]
VEHICLES = {
    "CAR":  ("C",  (0.85, 0.20, 0.20, 1)),
    "MOTO": ("M",  (0.20, 0.72, 0.35, 1)),
    "LRY":  ("L",  (0.20, 0.47, 0.87, 1)),
    "LLRY": ("LL", (0.93, 0.50, 0.15, 1)),
    "BUS":  ("B",  (0.85, 0.75, 0.10, 1)),
}

# Button order — positions computed mathematically for equal gaps
ARC_ORDER = ["BUS", "CAR", "LRY", "MOTO", "LLRY"]
TOP_H    = 84
TIMER_H  = 220


# ── Vehicle icon drawing ────────────────────────────────────────────────────
def draw_icon(c, key, cx, cy, sz):
    """White line-art vehicle icon, drawn onto canvas group c."""
    s  = sz / 200.0
    lw = max(2.0, 3.6 * s)
    wr = 12 * s

    with c:
        Color(1, 1, 1, 0.95)

        if key == 'CAR':
            bw, bh = 108*s, 26*s
            rw, rh = 66*s,  22*s
            # Body
            Line(rounded_rectangle=(cx-bw/2, cy-16*s, bw, bh, 5*s), width=lw)
            # Roof (shifted slightly right for sedan look)
            Line(rounded_rectangle=(cx-rw/2+8*s, cy+8*s, rw, rh, 5*s), width=lw)
            # Wheels
            Ellipse(pos=(cx-bw/2+16*s-wr, cy-30*s), size=(wr*2, wr*2))
            Ellipse(pos=(cx+bw/2-16*s-wr, cy-30*s), size=(wr*2, wr*2))

        elif key == 'MOTO':
            # True side-view motorcycle
            rwr = 20*s   # rear wheel
            fwr = 18*s   # front wheel
            rwx = cx - 40*s;  rwy = cy - 18*s   # rear wheel centre
            fwx = cx + 38*s;  fwy = cy - 14*s   # front wheel centre
            # Wheels
            Ellipse(pos=(rwx-rwr, rwy-rwr), size=(rwr*2, rwr*2))
            Ellipse(pos=(fwx-fwr, fwy-fwr), size=(fwr*2, fwr*2))
            # Seat position
            sx = cx - 4*s;  sy = rwy + 35*s
            # Main frame: rear axle → seat point → front fork top
            Line(points=[rwx, rwy, sx, sy, fwx-6*s, fwy+24*s], width=lw)
            # Tank (between rear wheel and seat)
            Line(rounded_rectangle=(rwx+12*s, rwy+10*s, 26*s, 15*s, 3*s), width=lw)
            # Front fork: front wheel → handlebar
            Line(points=[fwx, fwy, fwx-8*s, fwy+30*s], width=lw)
            # Handlebar (horizontal)
            Line(points=[fwx-16*s, fwy+28*s, fwx, fwy+20*s], width=lw)
            # Seat pad
            Line(rounded_rectangle=(sx-14*s, sy-4*s, 28*s, 10*s, 3*s), width=lw)

        elif key == 'BUS':
            bw, bh = 88*s, 56*s
            # Body
            Line(rounded_rectangle=(cx-bw/2, cy-bh/2, bw, bh, 4*s), width=lw)
            # 3 windows
            for i in range(3):
                Line(rectangle=(cx-bw/2+8*s+i*27*s, cy+6*s, 19*s, 15*s), width=lw*0.8)
            # Door
            Line(rectangle=(cx+bw/2-22*s, cy-bh/2+4*s, 13*s, 22*s), width=lw*0.8)
            # 2 wheels from side (front + rear axle)
            Ellipse(pos=(cx-bw/2+18*s-wr, cy-bh/2-wr*1.8), size=(wr*2, wr*2))
            Ellipse(pos=(cx+bw/2-18*s-wr, cy-bh/2-wr*1.8), size=(wr*2, wr*2))

        elif key == 'LRY':
            # 2-axle lorry: 1 front wheel + 1 rear wheel visible from side
            cab_w, cab_h = 30*s, 46*s
            bod_w, bod_h = 68*s, 32*s
            # Trailer body (left of cab)
            Line(rectangle=(cx-cab_w/2-bod_w, cy-bod_h/2, bod_w, bod_h), width=lw)
            # Cab (right)
            Line(rounded_rectangle=(cx-cab_w/2, cy-bod_h/2, cab_w, cab_h, 4*s), width=lw)
            # Cab window
            Line(rectangle=(cx-cab_w/2+4*s, cy+4*s, cab_w-8*s, 13*s), width=lw*0.8)
            # 2 axles: front (under cab) + rear (under trailer rear)
            Ellipse(pos=(cx-wr, cy-bod_h/2-wr*2), size=(wr*2, wr*2))                       # front
            Ellipse(pos=(cx-cab_w/2-bod_w+14*s-wr, cy-bod_h/2-wr*2), size=(wr*2, wr*2))   # rear

        elif key == 'LLRY':
            # 3-axle large lorry: front + mid + rear wheel visible from side
            cab_w, cab_h = 27*s, 50*s
            bod_w, bod_h = 92*s, 30*s
            # Long trailer
            Line(rectangle=(cx-cab_w/2-bod_w, cy-bod_h/2, bod_w, bod_h), width=lw)
            # Cab
            Line(rounded_rectangle=(cx-cab_w/2, cy-bod_h/2, cab_w, cab_h, 4*s), width=lw)
            # Cab window
            Line(rectangle=(cx-cab_w/2+4*s, cy+4*s, cab_w-8*s, 13*s), width=lw*0.8)
            # 3 axles: front + mid-trailer + rear-trailer
            front_x = cx - wr
            mid_x   = cx - cab_w/2 - bod_w/2 - wr
            rear_x  = cx - cab_w/2 - bod_w + 13*s - wr
            wheel_y = cy - bod_h/2 - wr*2
            Ellipse(pos=(front_x, wheel_y), size=(wr*2, wr*2))
            Ellipse(pos=(mid_x,   wheel_y), size=(wr*2, wr*2))
            Ellipse(pos=(rear_x,  wheel_y), size=(wr*2, wr*2))


# ── Circle button ────────────────────────────────────────────────────────────
class CircleButton(Button):
    """
    Circular button.
    Press feedback: instant color darken + white outer ring.
    Widget size NEVER changes — no stuck animation possible.
    """
    def __init__(self, key, circle_color, **kwargs):
        super().__init__(background_normal='', background_color=(0,0,0,0), **kwargs)
        self.key          = key
        self.circle_color = circle_color
        self._pressed     = False
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            if self._pressed:
                Color(1, 1, 1, 1)
                ring = 10
                Ellipse(pos=(self.x-ring, self.y-ring),
                        size=(self.width+ring*2, self.height+ring*2))
                r, g, b, a = self.circle_color
                Color(r*0.40, g*0.40, b*0.40, a)
            else:
                Color(*self.circle_color)
            Ellipse(pos=self.pos, size=self.size)

    def on_press(self):
        self._pressed = True
        self._redraw()

    def on_release(self):
        self._pressed = False
        self._redraw()


# ── Summary chip ─────────────────────────────────────────────────────────────
class SummaryChip(Button):
    def __init__(self, chip_color, **kwargs):
        self._chip_color = chip_color
        self._dim        = tuple(max(0,c*0.35) if i<3 else c
                                 for i,c in enumerate(chip_color))
        self._flash_ev   = None
        super().__init__(background_normal='', background_color=chip_color, **kwargs)

    def flash(self):
        if self._flash_ev: self._flash_ev.cancel()
        self.background_color = list(self._dim)
        self._flash_ev = Clock.schedule_once(
            lambda dt: setattr(self,'background_color',list(self._chip_color)), 0.22)


class JunctionSummary(BoxLayout):
    def __init__(self, on_minus, **kwargs):
        kwargs.setdefault('orientation','horizontal')
        kwargs.setdefault('spacing',6)
        kwargs.setdefault('padding',[8,6,8,6])
        super().__init__(**kwargs)
        self.on_minus = on_minus
        self.counts   = {k:0 for k in VEHICLES}
        self.chips    = {}
        for key in SUMMARY_ORDER:
            short, color = VEHICLES[key]
            btn = SummaryChip(chip_color=color, text=f"{short}: 0",
                              font_size=19, bold=True,
                              color=(1,1,1,1), size_hint=(1,1))
            btn.bind(on_release=lambda b,k=key: self._minus(k))
            self.chips[key] = (btn, short)
            self.add_widget(btn)

    def _minus(self, key):
        if self.counts[key] > 0:
            self.counts[key] -= 1
            self._refresh(key)
            self.chips[key][0].flash()
            self.on_minus()

    def _refresh(self, key):
        btn, short = self.chips[key]
        btn.text = f"{short}: {self.counts[key]}"

    def increment(self, key): self.counts[key]+=1; self._refresh(key)
    def get_counts(self):     return dict(self.counts)

    def set_counts(self, data):
        for k,v in data.items():
            if k in self.counts:
                self.counts[k]=max(0,int(v)); self._refresh(k)

    def reset(self):
        for k in self.counts: self.counts[k]=0; self._refresh(k)


# ── Rainbow cluster ──────────────────────────────────────────────────────────
class RainbowCluster(FloatLayout):
    def __init__(self, on_tap, corner, **kwargs):
        super().__init__(**kwargs)
        self.on_tap = on_tap
        self.corner = corner
        self._btns  = []
        self.bind(size=self._place, pos=self._place)
        for key in ARC_ORDER:
            short, color = VEHICLES[key]
            btn = CircleButton(key=key, circle_color=color,
                               text=short, font_size=28, bold=True, color=(1,1,1,1))
            btn.size_hint = (None, None)
            btn.size      = (10, 10)
            btn.bind(on_release=lambda b, k=key: self.on_tap(k))
            self._btns.append((key, btn))
            self.add_widget(btn)

    def _place(self, *a):
        w, h = self.size
        if w <= 0 or h <= 0: return
        ref = min(w, h)

        # Three ring radii
        r1 = ref * 0.300
        r2 = ref * 0.545
        r3 = ref * 0.790

        # Button size and equal target gap
        btn_size = max(50, int(ref * 0.265))
        gap      = max(10, int(ref * 0.024))
        D        = btn_size + gap   # same center-to-center for ALL adjacent pairs

        # Law of cosines: D² = ra² + rb² - 2·ra·rb·cos(θ)
        # → θ = arccos((ra²+rb²-D²)/(2·ra·rb))

        # Angular step ring1 → ring2
        v2 = (r1**2 + r2**2 - D**2) / (2 * r1 * r2)
        t2 = math.acos(max(-1.0, min(1.0, v2)))

        # Angular step ring2 → ring3 (same D guarantees equal gap)
        v3 = (r2**2 + r3**2 - D**2) / (2 * r2 * r3)
        t3 = t2 + math.acos(max(-1.0, min(1.0, v3)))

        # Centre angle α: balance LLRY (α-t3) above floor and MOTO (α+t3) below ceiling
        buf = btn_size / 2 + 8
        alpha_min = t3 + math.asin(min(1.0, buf / r3))          # LLRY clears bottom
        alpha_max = math.asin(min(1.0, (h - buf) / r3)) - t3    # MOTO clears top
        alpha = (alpha_min + alpha_max) / 2
        alpha = max(alpha_min, min(alpha_max if alpha_max > alpha_min else alpha_min, alpha))

        # Map each key to its (angle, radius)
        arc_pos = {
            'BUS':  (alpha,      r1),
            'CAR':  (alpha + t2, r2),
            'LRY':  (alpha - t2, r2),
            'MOTO': (alpha + t3, r3),
            'LLRY': (alpha - t3, r3),
        }

        for key, btn in self._btns:
            angle, r = arc_pos[key]
            dx = r * math.cos(angle)
            dy = r * math.sin(angle)

            if self.corner == 'left':
                bx = self.x + dx - btn_size / 2
                by = self.y + dy - btn_size / 2
            else:
                bx = self.x + w - dx - btn_size / 2
                by = self.y + dy - btn_size / 2

            # Hard clamp — never outside cluster frame
            bx = max(self.x + 2, min(self.x + w - btn_size - 2, bx))
            by = max(self.y + 2, min(self.y + h - btn_size - 2, by))

            btn.size = (btn_size, btn_size)
            btn.pos  = (bx, by)


# ── Timer widget ─────────────────────────────────────────────────────────────
BASE_FONT = 68

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
                         size_hint=(1,1), halign='center', valign='middle')
        self.lbl.bind(size=lambda i,v: setattr(i,'text_size',v))
        self.add_widget(self.lbl)

        row = BoxLayout(orientation='horizontal', size_hint=(1,None),
                        height=46, spacing=6, padding=[4,0,4,0])
        self.btn_ss = self._mk("START", (0.20,0.60,0.30,1))
        self.btn_ss.bind(on_release=self._toggle)
        btn_set = self._mk("SET",   (0.25,0.35,0.60,1))
        btn_set.bind(on_release=self._open_set)
        btn_rst = self._mk("RESET", (0.55,0.25,0.25,1))
        btn_rst.bind(on_release=self._reset_timer)
        for b in (self.btn_ss, btn_set, btn_rst): row.add_widget(b)
        self.add_widget(row)

    def _mk(self, t, bg):
        return Button(text=t, font_size=15, bold=True, color=(1,1,1,1),
                      background_normal='', background_color=bg, size_hint=(1,1))

    def _fmt(self, secs):
        m, s = divmod(max(0,int(secs)),60)
        return f"{m:02d}:{s:02d}"

    def _toggle(self, *a):
        self._pause() if self._running else self._start()

    def _start(self):
        if self._remaining <= 0: return
        self._running = True
        self.btn_ss.text = "PAUSE"
        self.btn_ss.background_color = (0.70,0.50,0.10,1)
        self._stop_alert()
        self.lbl.color     = (0.55,0.92,0.55,1)
        self.lbl.font_size = BASE_FONT
        self._tick_ev = Clock.schedule_interval(self._tick, 1)

    def _pause(self):
        self._running = False
        self.btn_ss.text = "START"
        self.btn_ss.background_color = (0.20,0.60,0.30,1)
        if self._tick_ev: self._tick_ev.cancel()

    def _tick(self, dt):
        self._remaining -= 1
        self.lbl.text = self._fmt(self._remaining)
        if self._remaining <= 0:
            self._pause()
            self._alert()

    def _alert(self):
        """Capture attention: pulse font size + flash red only — no text change."""
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
        self._remaining = self._duration
        self.lbl.text      = self._fmt(self._remaining)
        self.lbl.color     = (0.55,0.92,0.55,1)
        self.lbl.font_size = BASE_FONT

    def reset_to_default(self): self._reset_timer()
    def stop_alert(self):       self._stop_alert(); self.lbl.color=(0.55,0.92,0.55,1); self.lbl.font_size=BASE_FONT

    def _open_set(self, *a):
        self._pause()
        content = BoxLayout(orientation='vertical', spacing=12, padding=20)
        content.add_widget(Label(text="Set timer (MM:SS)", font_size=18,
                                 color=(1,1,1,1), size_hint=(1,None), height=34, halign='center'))
        inp = TextInput(text=self._fmt(self._duration), font_size=32,
                        foreground_color=(1,1,1,1), background_color=(0.15,0.17,0.21,1),
                        cursor_color=(1,1,1,1), size_hint=(1,None), height=60,
                        multiline=False, halign='center')
        content.add_widget(inp)
        btns = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1,None), height=56)
        cancel  = self._mk("Cancel", (0.30,0.32,0.38,1))
        confirm = self._mk("Set",    (0.20,0.55,0.30,1))
        btns.add_widget(cancel); btns.add_widget(confirm); content.add_widget(btns)
        popup = Popup(title='Set Timer', title_size=20, content=content,
                      size_hint=(0.55,0.58), background_color=(0.14,0.15,0.20,1),
                      title_color=(1,1,1,1), separator_color=(0.25,0.27,0.32,1))
        cancel.bind(on_release=popup.dismiss)
        def _apply(*a):
            try:
                p = inp.text.strip().split(':')
                total = int(p[0])*60+int(p[1]) if len(p)==2 else int(p[0])*60
                self._duration = max(1, total)
            except: self._duration = DEFAULT_TIMER
            self._remaining    = self._duration
            self.lbl.text      = self._fmt(self._remaining)
            self.lbl.color     = (0.55,0.92,0.55,1)
            self.lbl.font_size = BASE_FONT
            self._stop_alert(); popup.dismiss()
        confirm.bind(on_release=_apply)
        popup.open()


# ── Root layout ──────────────────────────────────────────────────────────────
class RootLayout(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ── Top bar ───────────────────────────────────────────
        top = BoxLayout(size_hint=(1,None), height=TOP_H,
                        pos_hint={'x':0,'top':1},
                        spacing=6, padding=[6,6,6,6])
        self.j1_summary = JunctionSummary(on_minus=self._save, size_hint=(0.42,1))
        reset_btn = Button(text="RESET ALL", font_size=16, bold=True,
                           color=(1,1,1,1), background_normal='',
                           background_color=(0.75,0.20,0.20,1), size_hint=(0.16,1))
        reset_btn.bind(on_release=self._confirm_reset)
        self.j2_summary = JunctionSummary(on_minus=self._save, size_hint=(0.42,1))
        top.add_widget(self.j1_summary)
        top.add_widget(reset_btn)
        top.add_widget(self.j2_summary)
        self.add_widget(top)

        # ── Clusters — shifted inward toward timer ────────────
        self.j1_cluster = RainbowCluster(on_tap=self._j1_tap, corner='left',
                                          size_hint=(0.56,None), pos_hint={'x':0.02,'y':0})
        self.j2_cluster = RainbowCluster(on_tap=self._j2_tap, corner='right',
                                          size_hint=(0.56,None), pos_hint={'right':0.98,'y':0})
        self.add_widget(self.j1_cluster)
        self.add_widget(self.j2_cluster)

        # ── Timer — top of gap between clusters ───────────────
        self.timer_box = BoxLayout(orientation='vertical',
                                   size_hint=(0.22,None), height=TIMER_H,
                                   pos_hint={'center_x':0.5})
        self.timer = TimerWidget(size_hint=(1,1))
        self.timer_box.add_widget(self.timer)
        self.add_widget(self.timer_box)

        self.bind(size=self._layout)
        self._load()

    def _layout(self, *a):
        cluster_h = self.height - TOP_H
        self.j1_cluster.height = cluster_h
        self.j2_cluster.height = cluster_h
        # Place timer at top of cluster zone (with small padding)
        self.timer_box.y = cluster_h - TIMER_H - 6

    def _j1_tap(self, key): self.j1_summary.increment(key); self._save()
    def _j2_tap(self, key): self.j2_summary.increment(key); self._save()

    def _save(self, *a):
        try:
            with open(SAVE_FILE,'w') as f:
                json.dump({'j1':self.j1_summary.get_counts(),
                           'j2':self.j2_summary.get_counts()}, f)
        except Exception as e: print("Save error:", e)

    def _load(self):
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE,'r') as f: d=json.load(f)
                self.j1_summary.set_counts(d.get('j1',{}))
                self.j2_summary.set_counts(d.get('j2',{}))
        except Exception as e: print("Load error:", e)

    def _confirm_reset(self, *a):
        content = BoxLayout(orientation='vertical', spacing=16, padding=24)
        content.add_widget(Label(text="Reset all counts?", halign='center',
                                 valign='middle', color=(1,1,1,1), font_size=22, size_hint=(1,1)))
        btns = BoxLayout(orientation='horizontal', spacing=12, size_hint=(1,None), height=70)
        def _mk(t,bg): return Button(text=t, font_size=18, bold=True, color=(1,1,1,1),
                                      background_normal='', background_color=bg, size_hint=(1,1))
        cancel  = _mk("Cancel",     (0.30,0.32,0.38,1))
        confirm = _mk("Yes, Reset", (0.75,0.20,0.20,1))
        btns.add_widget(cancel); btns.add_widget(confirm); content.add_widget(btns)
        popup = Popup(title='Confirm', title_size=20, content=content,
                      size_hint=(0.65,0.45), background_color=(0.14,0.15,0.20,1),
                      title_color=(1,1,1,1), separator_color=(0.25,0.27,0.32,1))
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
        if platform == 'android': Window.update_viewport()

if __name__ == '__main__':
    TrafficCounterApp().run()
