
# robot/face_display.py
\"\"\"Interactive eye display for Jarvis.
Features:
- Pupils follow pan/tilt angles provided by a PanTilt object (attributes angle_pan, angle_tilt).
- Blink animation and idle micro-movements when no external pan/tilt updates.
- Non-blocking via Tkinter 'after' callbacks.
\"\"\"
from typing import Optional, Tuple
import tkinter as tk
import math
import time
import random

class FaceDisplay:
    def __init__(self, parent, width: int = 640, height: int = 320, pan_tilt: Optional[object] = None):
        self.parent = parent
        self.width = width
        self.height = height
        self.pan_tilt = pan_tilt
        self.canvas = tk.Canvas(parent, width=width, height=height, bg='black', highlightthickness=0)
        # geometry
        self.eye_radius = min(width, height) * 0.18
        self.pupil_radius = max(6, int(self.eye_radius * 0.36))
        gap = int(self.eye_radius * 1.2)
        cx = width // 2
        cy = int(height * 0.44)
        self.left_center = (cx - gap//2, cy)
        self.right_center = (cx + gap//2, cy)
        # drawing
        self._create_graphics()
        # mapping ranges (match pan_tilt limits)
        self.pan_min = 0.0
        self.pan_max = 180.0
        self.tilt_min = 30.0
        self.tilt_max = 150.0
        # pupil travel
        self.pupil_travel = self.eye_radius - self.pupil_radius - 6
        # blink / idle parameters
        self.running = False
        self.blinking = False
        self.last_blink = time.time()
        self.next_blink_in = random.uniform(3.0, 10.0)
        self.idle_phase = 0.0
        self.last_pan = None
        self.last_tilt = None
        self.smooth_pan = 90.0
        self.smooth_tilt = 90.0
        self.smooth_factor = 0.18  # 0..1 smoothing (higher = faster)
        # start loop interval
        self.interval_ms = 60

    def _create_graphics(self):
        lwx, lwy = self.left_center
        rwx, rwy = self.right_center
        er = self.eye_radius
        pr = self.pupil_radius
        # eye whites
        self.left_white = self.canvas.create_oval(lwx-er, lwy-er, lwx+er, lwy+er, fill='white', outline='#ddd', width=2)
        self.right_white = self.canvas.create_oval(rwx-er, rwy-er, rwx+er, rwy+er, fill='white', outline='#ddd', width=2)
        # pupils
        self.left_pupil = self.canvas.create_oval(lwx-pr, lwy-pr, lwx+pr, lwy+pr, fill='black')
        self.right_pupil = self.canvas.create_oval(rwx-pr, rwy-pr, rwx+pr, rwy+pr, fill='black')
        # eyelids are arcs we manipulate by drawing rectangles over eyes during blink
        self.left_lid = self.canvas.create_rectangle(0,0,0,0, fill='black', outline='')
        self.right_lid = self.canvas.create_rectangle(0,0,0,0, fill='black', outline='')
        self.canvas.pack()

    def angle_to_offset(self, pan: float, tilt: float) -> Tuple[float, float]:
        pn = (pan - self.pan_min) / (self.pan_max - self.pan_min)
        tn = (tilt - self.tilt_min) / (self.tilt_max - self.tilt_min)
        px = (pn - 0.5) * 2.0
        py = (tn - 0.5) * 2.0
        py = -py
        px = max(-1.0, min(1.0, px))
        py = max(-1.0, min(1.0, py))
        return px * self.pupil_travel, py * (self.pupil_travel * 0.6)

    def _apply_offsets(self, dx, dy):
        lx, ly = self.left_center
        rx, ry = self.right_center
        pr = self.pupil_radius
        self.canvas.coords(self.left_pupil, lx+dx-pr, ly+dy-pr, lx+dx+pr, ly+dy+pr)
        self.canvas.coords(self.right_pupil, rx+dx-pr, ry+dy-pr, rx+dx+pr, ry+dy+pr)

    def _draw_blink(self, progress: float):
        # progress 0..1 where 0=open, 1=closed
        # compute lid rectangle height
        for center, lid in ((self.left_center, self.left_lid), (self.right_center, self.right_lid)):
            cx, cy = center
            er = self.eye_radius
            # top lid covers from top downwards
            lid_h = int(er * 2 * progress)
            x0 = cx - er
            y0 = cy - er
            x1 = cx + er
            y1 = cy - er + lid_h
            self.canvas.coords(lid, x0, y0, x1, y1)

    def _clear_blink(self):
        # hide lids by moving them off-canvas
        w = self.width
        self.canvas.coords(self.left_lid, 0,0,0,0)
        self.canvas.coords(self.right_lid, 0,0,0,0)

    def _idle_offsets(self, t):
        # small natural micro-movements when no pan/tilt change
        jitter_x = math.sin(t * 0.8) * 2.0 + math.sin(t*1.3)*1.0
        jitter_y = math.cos(t * 1.1) * 1.2
        return jitter_x, jitter_y * 0.6

    def update_from_angles(self, pan: float, tilt: float):
        # smooth toward desired angles to avoid jitter
        self.smooth_pan += (pan - self.smooth_pan) * self.smooth_factor
        self.smooth_tilt += (tilt - self.smooth_tilt) * self.smooth_factor
        dx, dy = self.angle_to_offset(self.smooth_pan, self.smooth_tilt)
        self._apply_offsets(dx, dy)

    def _loop(self):
        if not self.running:
            return
        now = time.time()
        # check blinking
        if now - self.last_blink > self.next_blink_in and not self.blinking:
            # start blink
            self.blinking = True
            self.blink_start = now
        if self.blinking:
            # 3-phase blink: close (0.0->1.0), hold, open (1.0->0.0)
            elapsed = now - self.blink_start
            if elapsed < 0.08:
                prog = min(1.0, elapsed / 0.08)
                self._draw_blink(prog)
            elif elapsed < 0.18:
                self._draw_blink(1.0)
            elif elapsed < 0.26:
                prog = max(0.0, 1.0 - (elapsed - 0.18)/0.08)
                self._draw_blink(prog)
            else:
                self.blinking = False
                self._clear_blink()
                self.last_blink = now
                self.next_blink_in = random.uniform(3.0, 12.0)
        # read pan_tilt angles if available
        pan = None; tilt = None
        if self.pan_tilt is not None:
            pan = getattr(self.pan_tilt, 'angle_pan', None)
            tilt = getattr(self.pan_tilt, 'angle_tilt', None)
        if pan is not None and tilt is not None:
            self.update_from_angles(pan, tilt)
        else:
            # idle motion
            t = now
            jitter_x, jitter_y = self._idle_offsets(t + self.idle_phase)
            dx = jitter_x
            dy = jitter_y
            self._apply_offsets(dx, dy)
        # schedule next tick
        self.parent.after(self.interval_ms, self._loop)

    def start(self, interval_ms: int = 60):
        if self.running:
            return
        self.interval_ms = interval_ms
        self.running = True
        self.parent.after(0, self._loop)

    def stop(self):
        self.running = False
