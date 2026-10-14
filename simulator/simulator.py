"""
Urban Intersection Traffic Simulator
Main application — Tkinter GUI with real-time animation.
Mimics SUMO (Simulator of Urban Mobility) for a 4-way intersection.

Usage:
    python simulator.py

Controls:
    - Sliders on the right panel: adjust red/green duration per lane
    - Speed buttons: 0.5×, 1×, 2× simulation speed
    - Play/Pause button: pause the simulation
    - Reset button: restart all vehicles and timers
"""
import sys
import os
import time
import math
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import pygame

# Ensure imports from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    QUADRANT_W, QUADRANT_H, CONTROL_PANEL_W, STREET_IMAGES,
    COLOR_BG, COLOR_PANEL_BG, COLOR_PANEL_CARD, COLOR_ACCENT,
    COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_TEXT, COLOR_SUBTEXT,
    FPS, DEFAULT_RED_DURATION, DEFAULT_GREEN_DURATION
)
from traffic_engine import Intersection, DIRECTIONS
from renderer import QuadrantRenderer, IntersectionRenderer


# ─────────────────────────────────────────────────
#  Helper: themed label + spinbox row
# ─────────────────────────────────────────────────
def make_spin_row(parent, label: str, var: tk.DoubleVar,
                  from_: float, to_: float, on_change,
                  fg: str = COLOR_TEXT, accent: str = COLOR_ACCENT):
    frame = tk.Frame(parent, bg=COLOR_PANEL_CARD)
    frame.pack(fill="x", pady=2, padx=4)

    tk.Label(frame, text=label, font=("Segoe UI", 9), fg=fg,
             bg=COLOR_PANEL_CARD, width=14, anchor="w").pack(side="left", padx=4)

    spin = tk.Spinbox(
        frame, from_=from_, to=to_, increment=1,
        textvariable=var, width=5,
        command=on_change,
        font=("Consolas", 10), fg=accent, bg="#0d0d1c",
        buttonbackground="#1a1a2e", relief="flat",
        insertbackground=accent
    )
    spin.pack(side="left", padx=4)
    spin.bind("<Return>", lambda e: on_change())

    tk.Label(frame, text="sec", font=("Segoe UI", 8), fg=COLOR_SUBTEXT,
             bg=COLOR_PANEL_CARD).pack(side="left")
    return frame


# ─────────────────────────────────────────────────
#  Direction card in control panel
# ─────────────────────────────────────────────────
class DirectionCard(tk.Frame):
    STATE_COLORS = {"RED": COLOR_RED, "GREEN": COLOR_GREEN, "YELLOW": COLOR_YELLOW}

    def __init__(self, parent, direction: str, intersection: Intersection, **kw):
        super().__init__(parent, bg=COLOR_PANEL_CARD, padx=6, pady=6,
                         highlightthickness=1, highlightbackground="#2a2a4a", **kw)
        self.direction = direction
        self.intersection = intersection

        # Title row
        title_frame = tk.Frame(self, bg=COLOR_PANEL_CARD)
        title_frame.pack(fill="x")

        tk.Label(title_frame, text=f"▶  {direction}", font=("Segoe UI", 11, "bold"),
                 fg=COLOR_ACCENT, bg=COLOR_PANEL_CARD).pack(side="left")

        self.state_badge = tk.Label(title_frame, text="●", font=("Segoe UI", 14),
                                    fg=COLOR_RED, bg=COLOR_PANEL_CARD)
        self.state_badge.pack(side="right", padx=4)

        self.state_lbl = tk.Label(title_frame, text="RED", font=("Consolas", 9, "bold"),
                                  fg=COLOR_RED, bg=COLOR_PANEL_CARD, width=7, anchor="e")
        self.state_lbl.pack(side="right")

        # Countdown bar
        self.bar_frame = tk.Frame(self, bg="#1a1a2e", height=6)
        self.bar_frame.pack(fill="x", pady=3)
        self.bar_fill = tk.Frame(self.bar_frame, bg=COLOR_RED, height=6)
        self.bar_fill.place(x=0, y=0, relwidth=1.0, height=6)

        # Red / Green duration sliders
        self.var_red   = tk.DoubleVar(value=intersection.lights[direction].red_duration)
        self.var_green = tk.DoubleVar(value=intersection.lights[direction].green_duration)

        make_spin_row(self, "🔴  Red (sec):",   self.var_red,   5, 180,
                      self._on_red_change,   fg=COLOR_RED, accent=COLOR_RED)
        make_spin_row(self, "🟢  Green (sec):", self.var_green, 5, 180,
                      self._on_green_change, fg=COLOR_GREEN, accent=COLOR_GREEN)

        # Stats row
        stats_frame = tk.Frame(self, bg=COLOR_PANEL_CARD)
        stats_frame.pack(fill="x", pady=(4, 0))

        self.lbl_queue   = tk.Label(stats_frame, text="Queue: 0",
                                    font=("Segoe UI", 8), fg=COLOR_SUBTEXT, bg=COLOR_PANEL_CARD)
        self.lbl_queue.pack(side="left", padx=4)

        self.lbl_passed  = tk.Label(stats_frame, text="Passed: 0",
                                    font=("Segoe UI", 8), fg=COLOR_SUBTEXT, bg=COLOR_PANEL_CARD)
        self.lbl_passed.pack(side="right", padx=4)

    def _on_red_change(self):
        self.intersection.set_red_duration(self.direction, float(self.var_red.get()))

    def _on_green_change(self):
        self.intersection.set_green_duration(self.direction, float(self.var_green.get()))

    def update_stats(self, stats: dict):
        state = stats["state"]
        color = self.STATE_COLORS.get(state, "white")
        self.state_badge.config(fg=color)
        self.state_lbl.config(text=state, fg=color)
        self.bar_fill.config(bg=color)

        # Progress bar width
        light = self.intersection.lights[self.direction]
        duration = light.current_duration()
        remaining = stats["time_remaining"]
        frac = max(0.0, min(1.0, remaining / duration)) if duration > 0 else 0
        # Update bar width after geometry is known
        bw = self.bar_frame.winfo_width()
        if bw > 1:
            self.bar_fill.place(x=0, y=0, width=int(bw * frac), height=6)

        self.lbl_queue.config(text=f"Queue: {stats['queue']}")
        self.lbl_passed.config(text=f"Passed: {stats['total_passed']}")


# ─────────────────────────────────────────────────
#  Main Simulator Window
# ─────────────────────────────────────────────────
class SimulatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Urban Intersection Traffic Simulator")
        self.configure(bg=COLOR_BG)
        self.resizable(True, True)
        
        self.is_fullscreen = False
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)

        # State
        self.intersection = Intersection()
        self.paused = False
        self._last_time = time.perf_counter()
        self._photo = None  # keep reference

        # Build renderers
        self.quad_renderers = {}
        for d in DIRECTIONS:
            path = STREET_IMAGES[d]
            self.quad_renderers[d] = QuadrantRenderer(d, path)
        self.intersection_renderer = IntersectionRenderer(self.quad_renderers)

        # Initialize pygame mixer for audio
        self.noise_sound = None
        self.siren_sound = None
        self.siren_playing = False
        try:
            pygame.mixer.init()
            sim_dir = os.path.dirname(os.path.abspath(__file__))
            noise_path = os.path.join(sim_dir, "assets", "voice", "noise", "noise_freesound_community-city-traffic-noise2-16695_0015.wav")
            siren_path = os.path.join(sim_dir, "assets", "voice", "emergency", "sirine_scottishperson-sound-effect-uk-ambulance-siren-164354_0002.wav")
            
            if os.path.exists(noise_path):
                self.noise_sound = pygame.mixer.Sound(noise_path)
                self.noise_sound.play(loops=-1)
                print("[audio] Started playing background traffic noise")
            else:
                print(f"[audio] Noise file not found: {noise_path}")
                
            if os.path.exists(siren_path):
                self.siren_sound = pygame.mixer.Sound(siren_path)
            else:
                print(f"[audio] Siren file not found: {siren_path}")
        except Exception as e:
            print(f"[audio] Failed to initialize audio mixer: {e}")

        # Set window close handler to clean up audio mixer
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        self._build_ui()
        self._schedule_frame()

    # ── UI Layout ──────────────────────────────
    def _build_ui(self):
        # Left: simulation canvas
        canvas_w = QUADRANT_W * 2
        canvas_h = QUADRANT_H * 2

        self.canvas = tk.Canvas(self, width=canvas_w, height=canvas_h,
                                bg="black", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True, padx=0, pady=0)
        self._canvas_img = self.canvas.create_image(0, 0, anchor="nw")

        # Right: control panel
        panel = tk.Frame(self, bg=COLOR_PANEL_BG, width=CONTROL_PANEL_W)
        panel.pack(side="right", fill="y", padx=0, pady=0)
        panel.pack_propagate(False)
        self._build_panel(panel)

    def _build_panel(self, panel: tk.Frame):
        # Header
        header = tk.Frame(panel, bg="#0d0d1c", pady=12)
        header.pack(fill="x")

        tk.Label(header, text="🚦 Traffic Simulator",
                 font=("Segoe UI", 13, "bold"),
                 fg=COLOR_ACCENT, bg="#0d0d1c").pack()
        tk.Label(header, text="Urban Intersection Control",
                 font=("Segoe UI", 8), fg=COLOR_SUBTEXT, bg="#0d0d1c").pack()

        # Separator
        tk.Frame(panel, bg=COLOR_ACCENT, height=2).pack(fill="x")

        # Scrollable area for everything below the header
        canvas = tk.Canvas(panel, bg=COLOR_PANEL_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLOR_PANEL_BG)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=CONTROL_PANEL_W - 20)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, pady=4)
        scrollbar.pack(side="right", fill="y")
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        # Bind mousewheel to canvas and its children
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Direction cards
        self.direction_cards: dict[str, DirectionCard] = {}
        for d in DIRECTIONS:
            card = DirectionCard(scroll_frame, d, self.intersection)
            card.pack(fill="x", padx=8, pady=4)
            self.direction_cards[d] = card

        # Global controls
        ctrl_sep = tk.Frame(scroll_frame, bg="#2a2a4a", height=1)
        ctrl_sep.pack(fill="x", padx=8, pady=4)

        ctrl = tk.Frame(scroll_frame, bg=COLOR_PANEL_BG, pady=4)
        ctrl.pack(fill="x", padx=8)

        tk.Label(ctrl, text="SIMULATION SPEED", font=("Segoe UI", 8, "bold"),
                 fg=COLOR_SUBTEXT, bg=COLOR_PANEL_BG).pack()

        speed_row = tk.Frame(ctrl, bg=COLOR_PANEL_BG)
        speed_row.pack(pady=4)

        for label, speed in [("0.5×", 0.5), ("1×", 1.0), ("2×", 2.0), ("3×", 3.0)]:
            btn = tk.Button(speed_row, text=label,
                            font=("Segoe UI", 9, "bold"),
                            fg=COLOR_TEXT, bg=COLOR_PANEL_CARD,
                            activeforeground=COLOR_BG, activebackground=COLOR_ACCENT,
                            relief="flat", padx=8, pady=4,
                            cursor="hand2",
                            command=lambda s=speed: self._set_speed(s))
            btn.pack(side="left", padx=3)

        # Pause / Reset
        action_row = tk.Frame(ctrl, bg=COLOR_PANEL_BG)
        action_row.pack(pady=6)

        self.pause_btn = tk.Button(action_row, text="⏸  Pause",
                                   font=("Segoe UI", 9, "bold"),
                                   fg=COLOR_BG, bg=COLOR_ACCENT,
                                   activeforeground=COLOR_BG, activebackground="#00a8cc",
                                   relief="flat", padx=10, pady=5,
                                   cursor="hand2",
                                   command=self._toggle_pause)
        self.pause_btn.pack(side="left", padx=4)

        reset_btn = tk.Button(action_row, text="↺  Reset",
                               font=("Segoe UI", 9, "bold"),
                               fg=COLOR_TEXT, bg="#2a2a4a",
                               activeforeground=COLOR_TEXT, activebackground="#3a3a6a",
                               relief="flat", padx=10, pady=5,
                               cursor="hand2",
                               command=self._reset)
        reset_btn.pack(side="left", padx=4)

        # Emergency Dispatch
        em_sep = tk.Frame(scroll_frame, bg="#2a2a4a", height=1)
        em_sep.pack(fill="x", padx=8, pady=4)
        
        em_frame = tk.Frame(scroll_frame, bg=COLOR_PANEL_BG)
        em_frame.pack(fill="x", padx=8)
        
        tk.Label(em_frame, text="EMERGENCY DISPATCH", font=("Segoe UI", 8, "bold"),
                 fg=COLOR_RED, bg=COLOR_PANEL_BG).pack()
                 
        type_var = tk.StringVar(value="ambulance")
        src_var = tk.StringVar(value="NORTH")
        dst_var = tk.StringVar(value="EAST")
        
        row1 = tk.Frame(em_frame, bg=COLOR_PANEL_BG)
        row1.pack(fill="x", pady=2)
        tk.Label(row1, text="Type:", bg=COLOR_PANEL_BG, fg=COLOR_TEXT).pack(side="left")
        ttk.Combobox(row1, textvariable=type_var, values=["ambulance", "firefighter"], width=10, state="readonly").pack(side="right")
        
        row2 = tk.Frame(em_frame, bg=COLOR_PANEL_BG)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="From:", bg=COLOR_PANEL_BG, fg=COLOR_TEXT).pack(side="left")
        ttk.Combobox(row2, textvariable=src_var, values=["NORTH", "EAST", "SOUTH", "WEST"], width=10, state="readonly").pack(side="right")
        
        row3 = tk.Frame(em_frame, bg=COLOR_PANEL_BG)
        row3.pack(fill="x", pady=2)
        tk.Label(row3, text="To:", bg=COLOR_PANEL_BG, fg=COLOR_TEXT).pack(side="left")
        ttk.Combobox(row3, textvariable=dst_var, values=["NORTH", "EAST", "SOUTH", "WEST"], width=10, state="readonly").pack(side="right")
        
        def spawn_emergency():
            vtype = type_var.get()
            src = src_var.get()
            dst = dst_var.get()
            if src != dst:
                self.intersection.lanes[src].spawn_special_vehicle(vtype, dst)
                
        tk.Button(em_frame, text="🚨 Spawn", bg="#cc0000", fg="#ffffff", font=("Segoe UI", 8, "bold"),
                  relief="flat", cursor="hand2", command=spawn_emergency).pack(pady=4, fill="x")

        # Bottom stats
        stats_sep = tk.Frame(scroll_frame, bg="#2a2a4a", height=1)
        stats_sep.pack(fill="x", padx=8, pady=4)

        self.stats_frame = tk.Frame(scroll_frame, bg=COLOR_PANEL_BG, pady=4)
        self.stats_frame.pack(fill="x", padx=8)

        tk.Label(self.stats_frame, text="GLOBAL STATS",
                 font=("Segoe UI", 8, "bold"), fg=COLOR_SUBTEXT,
                 bg=COLOR_PANEL_BG).pack()

        self.lbl_sim_time = tk.Label(self.stats_frame, text="Sim Time: 0s",
                                     font=("Consolas", 9), fg=COLOR_ACCENT,
                                     bg=COLOR_PANEL_BG)
        self.lbl_sim_time.pack()

        self.lbl_total_vehicles = tk.Label(self.stats_frame, text="Total Vehicles: 0",
                                           font=("Consolas", 9), fg=COLOR_TEXT,
                                           bg=COLOR_PANEL_BG)
        self.lbl_total_vehicles.pack()

        self.lbl_fps = tk.Label(self.stats_frame, text="FPS: --",
                                font=("Consolas", 8), fg=COLOR_SUBTEXT,
                                bg=COLOR_PANEL_BG)
        self.lbl_fps.pack()

        # Speed indicator
        self.lbl_speed = tk.Label(panel, text="Speed: 1.0×",
                                  font=("Segoe UI", 9, "bold"),
                                  fg=COLOR_YELLOW, bg=COLOR_PANEL_BG)
        self.lbl_speed.pack(pady=(0, 8))

    # ── Simulation Loop ────────────────────────
    def _schedule_frame(self):
        self.after(1000 // FPS, self._frame)

    def _frame(self):
        now = time.perf_counter()
        dt = now - self._last_time
        self._last_time = now
        actual_fps = 1.0 / max(dt, 0.001)

        if not self.paused:
            self.intersection.update(dt)

        # Audio control: play/stop siren based on the presence of emergency vehicles
        if self.siren_sound is not None:
            has_special = False
            for lane in self.intersection.lanes.values():
                for v in lane.incoming + lane.outgoing:
                    if v.is_special:
                        has_special = True
                        break
                if has_special:
                    break

            if has_special and not self.siren_playing:
                self.siren_sound.play(loops=-1)
                self.siren_playing = True
            elif not has_special and self.siren_playing:
                self.siren_sound.stop()
                self.siren_playing = False

        # Render
        img = self.intersection_renderer.render(
            QUADRANT_W, QUADRANT_H,
            self.intersection.lanes,
            self.intersection.lights,
            self.intersection.elapsed
        )

        # Scale image if canvas is resized
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw > 10 and ch > 10 and (cw != img.width or ch != img.height):
            img = img.resize((cw, ch), Image.NEAREST)

        photo = ImageTk.PhotoImage(img)
        self.canvas.itemconfig(self._canvas_img, image=photo)
        self._photo = photo  # prevent GC

        # Update control panel stats
        total_v = 0
        total_passed = 0
        for d in DIRECTIONS:
            s = self.intersection.stats(d)
            self.direction_cards[d].update_stats(s)
            total_v += s["vehicles"]
            total_passed += s["total_passed"]

        self.lbl_sim_time.config(text=f"Sim Time: {int(self.intersection.elapsed)}s")
        self.lbl_total_vehicles.config(text=f"On Road: {total_v}  |  Total: {total_passed}")
        self.lbl_fps.config(text=f"FPS: {actual_fps:.1f}")

        self._schedule_frame()

    # ── Controls ───────────────────────────────
    def _set_speed(self, speed: float):
        self.intersection.sim_speed = speed
        self.lbl_speed.config(text=f"Speed: {speed}×")

    def _toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.config(text="▶  Resume", bg="#2a6a2a")
            self._last_time = time.perf_counter()  # reset timer to avoid dt spike
        else:
            self.pause_btn.config(text="⏸  Pause", bg=COLOR_ACCENT)
            self._last_time = time.perf_counter()

    def _toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def _exit_fullscreen(self, event=None):
        self.is_fullscreen = False
        self.attributes("-fullscreen", False)

    def _reset(self):
        # Preserve current durations
        red_durs   = {d: self.intersection.lights[d].red_duration   for d in DIRECTIONS}
        green_durs = {d: self.intersection.lights[d].green_duration for d in DIRECTIONS}
        speed = self.intersection.sim_speed

        self.intersection = Intersection()
        self.intersection.sim_speed = speed

        for d in DIRECTIONS:
            self.intersection.set_red_duration(d, red_durs[d])
            self.intersection.set_green_duration(d, green_durs[d])

        # Update card references
        for d, card in self.direction_cards.items():
            card.intersection = self.intersection

        # Update renderer references (they don't hold intersection ref)
        # Recreate intersection renderer with same quad renderers
        self.intersection_renderer = IntersectionRenderer(self.quad_renderers)

        self._last_time = time.perf_counter()

    def _on_closing(self):
        try:
            if pygame.mixer.get_init():
                pygame.mixer.stop()
                pygame.mixer.quit()
        except Exception:
            pass
        self.destroy()


# ─────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    app = SimulatorApp()
    app.mainloop()
