"""
╔══════════════════════════════════════════════════════════════════════════╗
║        LANE CALIBRATION TOOL v2 — Urban Intersection Simulator           ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Workflow per arah (tab atas):                                            ║
║                                                                           ║
║  STEP 1 — Driveable Area  : Klik vertices polygon jalan yang boleh       ║
║                              dilalui kendaraan. Enter = tutup polygon.   ║
║  STEP 2 — Jalur MASUK (IN): Klik waypoints jalur masuk (dari tepi        ║
║                              hingga mendekati stop line). Enter = selesai ║
║                              lane ini, mulai lane baru.                   ║
║  STEP 3 — Jalur KELUAR(OUT): Klik waypoints jalur keluar. Enter = next.  ║
║  STEP 4 — Garis Stop      : Klik 2 titik untuk definisi garis stop.      ║
║                              Kendaraan IN berhenti SEBELUM garis ini      ║
║                              ketika lampu merah.                          ║
║  STEP 5 — Simpan           : Preview & export calibration.json            ║
║                                                                           ║
║  Klik kanan = undo / hapus titik terakhir                                 ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import sys, os, json, math
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import STREET_IMAGES

DIRECTIONS = ["NORTH", "EAST", "WEST", "SOUTH"]
CALIB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration.json")

# ── Visual design constants ───────────────────────────────────────────────────
C_BG         = "#090912"
C_PANEL      = "#0e0e1c"
C_CARD       = "#14142a"
C_ACCENT     = "#00d4ff"
C_TEXT       = "#dde4ff"
C_SUBTEXT    = "#5a6880"
C_STEP_ACT   = "#1a1a38"
C_STEP_DONE  = "#0d2010"

# Road polygon
C_ROAD_FILL  = (60, 80, 255, 40)
C_ROAD_LINE  = (100, 140, 255, 200)

# Lanes
C_IN_COLORS  = ["#00ccff", "#44aaff", "#0088ff"]
C_OUT_COLORS = ["#44ff88", "#88ff44", "#00ee66"]

# Stop line
C_STOP       = "#ff2222"
C_STOP_FILL  = (255, 30, 30, 200)

# Dot sizes
R_WAYPOINT   = 6
R_FIRST      = 9
R_STOP       = 8

STEP_KEYS    = ["road", "in", "out", "stop", "done"]
STEP_LABELS  = [
    "① Driveable Area",
    "② Jalur MASUK",
    "③ Jalur KELUAR",
    "④ Garis Stop",
    "⑤ Selesai & Simpan",
]
STEP_HINTS = [
    ("Tandai AREA JALAN yang boleh dilalui kendaraan\n"
     "Klik = tambah vertex  •  Enter = tutup polygon\n"
     "Klik kanan = hapus terakhir  •  C = clear all"),
    ("Gambar jalur MASUK (dari tepi → menuju stop line)\n"
     "Klik = tambah waypoint  •  Enter = selesai lane ini\n"
     "Klik kanan = hapus terakhir  •  N = lane baru"),
    ("Gambar jalur KELUAR (dari stop line → menuju tepi)\n"
     "Klik = tambah waypoint  •  Enter = selesai lane ini\n"
     "Klik kanan = hapus terakhir  •  N = lane baru"),
    ("Klik 2 titik untuk GARIS STOP\n"
     "Kendaraan IN berhenti SEBELUM garis ini saat merah\n"
     "Klik kanan = reset garis stop"),
    ("Simpan kalibrasi ke calibration.json\n"
     "Config simulator akan otomatis terbaru\n"
     "Buka simulator.py untuk melihat hasilnya"),
]

# ─────────────────────────────────────────────────────────────────────────────

def load_calib():
    if os.path.exists(CALIB_FILE):
        try:
            with open(CALIB_FILE) as f:
                return json.load(f)
        except:
            pass
    # Build empty structure
    return {d: _empty_dir() for d in DIRECTIONS}

def _empty_dir():
    return {
        "road_polygon": [],
        "lanes_in":     [[]],   # start with one empty lane
        "lanes_out":    [[]],
        "stop_line":    [],     # will be [[x1,y1],[x2,y2]]
        "traffic_light": None,
    }

def save_calib(data):
    with open(CALIB_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────────────────────────────────────────

def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _draw_arrow(draw, p1, p2, color_rgb, alpha=220, size=10):
    """Draw an arrowhead at p2 pointing from p1→p2."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    ln = math.hypot(dx, dy)
    if ln < 1:
        return
    dx /= ln; dy /= ln
    left  = (p2[0] - size*dx + size*0.5*dy, p2[1] - size*dy - size*0.5*dx)
    right = (p2[0] - size*dx - size*0.5*dy, p2[1] - size*dy + size*0.5*dx)
    draw.polygon([p2, left, right], fill=(*color_rgb, alpha))

def _draw_dashed_line(draw, p1, p2, color, dash=12, gap=6, width=3):
    """Draw dashed line from p1 to p2."""
    dx, dy = p2[0]-p1[0], p2[1]-p1[1]
    total = math.hypot(dx, dy)
    if total < 1:
        return
    ux, uy = dx/total, dy/total
    pos = 0
    on = True
    while pos < total:
        seg = dash if on else gap
        end = min(pos + seg, total)
        if on:
            x0 = p1[0] + ux*pos;   y0 = p1[1] + uy*pos
            x1 = p1[0] + ux*end;   y1 = p1[1] + uy*end
            draw.line([(x0, y0), (x1, y1)], fill=color, width=width)
        pos += seg
        on = not on

# ═════════════════════════════════════════════════════════════════════════════
class CalibApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("🛣️  Lane Calibration Tool v2")
        self.configure(bg=C_BG)
        self.geometry("1280x780")
        self.minsize(900, 600)

        self.calib      = load_calib()
        self.cur_dir    = DIRECTIONS[0]
        self.cur_step   = 0            # index into STEP_KEYS
        self.cur_lane_in  = 0
        self.cur_lane_out = 0

        # canvas display metrics (set on resize / image load)
        self._disp_w  = 1
        self._disp_h  = 1
        self._off_x   = 0
        self._off_y   = 0

        # Cached images
        self._bg_orig : dict[str, Image.Image] = {}
        self._tk_img  = None

        # Cursor ghost (last mouse position in frac coords)
        self._mouse_frac = None

        self._build_ui()
        self._switch_dir(DIRECTIONS[0])

    # ── UI Layout ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Direction tabs (top) ──
        topbar = tk.Frame(self, bg="#0a0a18", pady=6)
        topbar.pack(fill="x")

        tk.Label(topbar, text="  🛣️  CALIBRATION TOOL v2",
                 font=("Segoe UI", 12, "bold"), fg=C_ACCENT, bg="#0a0a18").pack(side="left", padx=10)

        self._dir_btns = {}
        for d in DIRECTIONS:
            b = tk.Button(topbar, text=d, font=("Segoe UI", 10, "bold"),
                          fg=C_TEXT, bg="#1a1a30", relief="flat",
                          padx=16, pady=5, cursor="hand2",
                          command=lambda x=d: self._switch_dir(x))
            b.pack(side="left", padx=3)
            self._dir_btns[d] = b

        tk.Frame(self, bg=C_ACCENT, height=2).pack(fill="x")

        # ── Body ──
        body = tk.Frame(self, bg=C_BG)
        body.pack(fill="both", expand=True)

        self._build_left(body)
        self._build_canvas(body)

        # ── Status bar ──
        self._status = tk.StringVar(value="Klik pada gambar untuk mulai kalibrasi")
        tk.Label(self, textvariable=self._status, font=("Consolas", 9),
                 fg=C_SUBTEXT, bg="#08080f", anchor="w", padx=10, pady=3
                 ).pack(fill="x", side="bottom")

    def _build_left(self, parent):
        self._panel = tk.Frame(parent, bg=C_PANEL, width=240)
        self._panel.pack(side="left", fill="y")
        self._panel.pack_propagate(False)

        p = self._panel

        # Step list
        tk.Label(p, text="LANGKAH KALIBRASI", font=("Segoe UI", 8, "bold"),
                 fg=C_SUBTEXT, bg=C_PANEL).pack(pady=(14, 4), padx=10, anchor="w")

        self._step_btns = []
        for i, label in enumerate(STEP_LABELS):
            btn = tk.Button(p, text=label, font=("Segoe UI", 9, "bold"),
                            fg=C_TEXT, bg=C_CARD, relief="flat",
                            padx=10, pady=6, cursor="hand2", anchor="w",
                            command=lambda x=i: self._goto_step(x))
            btn.pack(fill="x", padx=8, pady=2)
            self._step_btns.append(btn)

        tk.Frame(p, bg="#2a2a44", height=1).pack(fill="x", padx=8, pady=8)

        # Hint box
        self._hint_var = tk.StringVar(value="")
        self._hint_lbl = tk.Label(p, textvariable=self._hint_var,
                                  font=("Segoe UI", 8), fg="#7090b0", bg=C_CARD,
                                  justify="left", wraplength=210, padx=10, pady=10)
        self._hint_lbl.pack(fill="x", padx=8)

        tk.Frame(p, bg="#2a2a44", height=1).pack(fill="x", padx=8, pady=8)

        # Lane selector (for step 2 & 3)
        self._lane_frame = tk.Frame(p, bg=C_PANEL)
        self._lane_frame.pack(fill="x", padx=8)
        self._lane_info = tk.Label(self._lane_frame, text="", font=("Consolas", 9),
                                   fg=C_ACCENT, bg=C_PANEL)
        self._lane_info.pack(anchor="w")
        lane_btns = tk.Frame(self._lane_frame, bg=C_PANEL)
        lane_btns.pack(fill="x", pady=2)
        tk.Button(lane_btns, text="+ Lane Baru", font=("Segoe UI", 8, "bold"),
                  fg=C_ACCENT, bg=C_CARD, relief="flat", padx=8, pady=4,
                  cursor="hand2", command=self._add_lane
                  ).pack(side="left", padx=2)
        tk.Button(lane_btns, text="Hapus Lane", font=("Segoe UI", 8),
                  fg="#ff6644", bg=C_CARD, relief="flat", padx=8, pady=4,
                  cursor="hand2", command=self._del_lane
                  ).pack(side="left", padx=2)

        tk.Frame(p, bg="#2a2a44", height=1).pack(fill="x", padx=8, pady=8)

        # Edit buttons
        btns = [
            ("↩  Undo titik terakhir", "#ffaa44", self._undo),
            ("🗑  Clear langkah ini",   "#ff5555", self._clear_step),
        ]
        for txt, col, cmd in btns:
            tk.Button(p, text=txt, font=("Segoe UI", 8, "bold"),
                      fg=col, bg=C_CARD, relief="flat", padx=8, pady=5,
                      cursor="hand2", command=cmd).pack(fill="x", padx=8, pady=2)

        tk.Frame(p, bg="#2a2a44", height=1).pack(fill="x", padx=8, pady=10)

        # Summary
        self._summary_var = tk.StringVar(value="")
        tk.Label(p, textvariable=self._summary_var, font=("Consolas", 8),
                 fg=C_SUBTEXT, bg=C_PANEL, justify="left").pack(padx=10, pady=2)

        tk.Frame(p, bg="#2a2a44", height=1).pack(fill="x", padx=8, pady=8)

        # Save button
        tk.Button(p, text="💾  SAVE CONFIG",
                  font=("Segoe UI", 11, "bold"),
                  fg="#000", bg=C_ACCENT,
                  activeforeground="#000", activebackground="#00a8cc",
                  relief="flat", padx=10, pady=10,
                  cursor="hand2", command=self._save
                  ).pack(fill="x", padx=8, pady=4)

    def _build_canvas(self, parent):
        frm = tk.Frame(parent, bg="#000")
        frm.pack(side="left", fill="both", expand=True)
        self._canvas = tk.Canvas(frm, bg="#0a0a0a", cursor="crosshair",
                                 highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Button-1>",  self._on_click)
        self._canvas.bind("<Button-3>",  self._on_right)
        self._canvas.bind("<Motion>",    self._on_motion)
        self._canvas.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Return>", self._on_enter)
        self.bind("<n>",      lambda e: self._add_lane())
        self.bind("<N>",      lambda e: self._add_lane())
        self.bind("<c>",      lambda e: self._clear_step())
        self.bind("<C>",      lambda e: self._clear_step())

    # ── Direction / Step switching ────────────────────────────────────────────

    def _switch_dir(self, d: str):
        self.cur_dir      = d
        self.cur_lane_in  = 0
        self.cur_lane_out = 0
        for k, b in self._dir_btns.items():
            b.config(bg=C_ACCENT if k == d else "#1a1a30",
                     fg="#000"   if k == d else C_TEXT)
        self._load_bg(d)
        self._goto_step(self.cur_step)

    def _goto_step(self, idx: int):
        self.cur_step = max(0, min(idx, len(STEP_KEYS) - 1))
        for i, b in enumerate(self._step_btns):
            is_done = i < self.cur_step
            is_act  = i == self.cur_step
            bg = C_STEP_DONE if is_done else (C_STEP_ACT if is_act else C_CARD)
            fg = "#44ff88"   if is_done else (C_ACCENT   if is_act else C_TEXT)
            b.config(bg=bg, fg=fg)

        self._hint_var.set(STEP_HINTS[self.cur_step])
        self._update_lane_info()
        self._redraw()

    def _update_lane_info(self):
        d   = self.cur_dir
        data = self.calib[d]
        step = STEP_KEYS[self.cur_step]

        if step == "in":
            n = len(data["lanes_in"])
            idx = self.cur_lane_in
            self._lane_info.config(
                text=f"Lane IN {idx+1}/{n}  ({len(data['lanes_in'][idx])} pts)")
        elif step == "out":
            n = len(data["lanes_out"])
            idx = self.cur_lane_out
            self._lane_info.config(
                text=f"Lane OUT {idx+1}/{n}  ({len(data['lanes_out'][idx])} pts)")
        else:
            self._lane_info.config(text="")

        # Summary
        ni  = sum(len(l) for l in data["lanes_in"])
        no  = sum(len(l) for l in data["lanes_out"])
        np_ = len(data.get("road_polygon", []))
        sl  = data.get("stop_line", [])
        lines = [
            f"Polygon : {np_} vertex",
            f"IN lanes: {len(data['lanes_in'])} ({ni} pts)",
            f"OUT lanes:{len(data['lanes_out'])} ({no} pts)",
            f"Stop line: {'✓ SET' if len(sl)==2 else '— belum'}",
        ]
        self._summary_var.set("\n".join(lines))

    # ── Lane management ───────────────────────────────────────────────────────

    def _add_lane(self):
        d = self.cur_dir
        step = STEP_KEYS[self.cur_step]
        if step == "in":
            self.calib[d]["lanes_in"].append([])
            self.cur_lane_in = len(self.calib[d]["lanes_in"]) - 1
        elif step == "out":
            self.calib[d]["lanes_out"].append([])
            self.cur_lane_out = len(self.calib[d]["lanes_out"]) - 1
        self._update_lane_info()
        self._redraw()

    def _del_lane(self):
        d = self.cur_dir
        step = STEP_KEYS[self.cur_step]
        if step == "in":
            lanes = self.calib[d]["lanes_in"]
            if len(lanes) > 1:
                lanes.pop(self.cur_lane_in)
                self.cur_lane_in = max(0, self.cur_lane_in - 1)
        elif step == "out":
            lanes = self.calib[d]["lanes_out"]
            if len(lanes) > 1:
                lanes.pop(self.cur_lane_out)
                self.cur_lane_out = max(0, self.cur_lane_out - 1)
        self._update_lane_info()
        self._redraw()

    # ── Click handlers ────────────────────────────────────────────────────────

    def _px_to_frac(self, ex, ey):
        fx = (ex - self._off_x) / self._disp_w
        fy = (ey - self._off_y) / self._disp_h
        return round(fx, 4), round(fy, 4)

    def _frac_to_px(self, fx, fy):
        return (int(fx * self._disp_w + self._off_x),
                int(fy * self._disp_h + self._off_y))

    def _on_click(self, event):
        fx, fy = self._px_to_frac(event.x, event.y)
        d    = self.cur_dir
        step = STEP_KEYS[self.cur_step]
        data = self.calib[d]

        if step == "road":
            data["road_polygon"].append([fx, fy])
        elif step == "in":
            while len(data["lanes_in"]) <= self.cur_lane_in:
                data["lanes_in"].append([])
            data["lanes_in"][self.cur_lane_in].append([fx, fy])
        elif step == "out":
            while len(data["lanes_out"]) <= self.cur_lane_out:
                data["lanes_out"].append([])
            data["lanes_out"][self.cur_lane_out].append([fx, fy])
        elif step == "stop":
            sl = data.get("stop_line", [])
            if len(sl) < 2:
                sl.append([fx, fy])
                data["stop_line"] = sl
            else:
                data["stop_line"] = [[fx, fy]]   # reset with new first point
        elif step == "done":
            return

        self._status.set(
            f"[{d}] {STEP_KEYS[self.cur_step].upper()}  →  x={fx:.4f}  y={fy:.4f}")
        self._update_lane_info()
        self._redraw()

    def _on_right(self, event):
        d    = self.cur_dir
        step = STEP_KEYS[self.cur_step]
        data = self.calib[d]

        if step == "road":
            if data["road_polygon"]:
                data["road_polygon"].pop()
        elif step == "in":
            lane = data["lanes_in"]
            if self.cur_lane_in < len(lane) and lane[self.cur_lane_in]:
                lane[self.cur_lane_in].pop()
        elif step == "out":
            lane = data["lanes_out"]
            if self.cur_lane_out < len(lane) and lane[self.cur_lane_out]:
                lane[self.cur_lane_out].pop()
        elif step == "stop":
            data["stop_line"] = []

        self._update_lane_info()
        self._redraw()

    def _on_motion(self, event):
        fx, fy = self._px_to_frac(event.x, event.y)
        self._mouse_frac = (fx, fy)
        step = STEP_KEYS[self.cur_step]
        self._status.set(
            f"[{self.cur_dir}] {step.upper()}  │  "
            f"x={fx:.4f}  y={fy:.4f}  │  "
            f"canvas=({event.x},{event.y})")
        # Light redraw for rubber-band
        self._redraw()

    def _on_enter(self, event):
        step = STEP_KEYS[self.cur_step]
        d = self.cur_dir
        if step == "road":
            # Close polygon — just advance step
            self._goto_step(1)
        elif step == "in":
            # Finalize current lane, move to next
            self._add_lane()
        elif step == "out":
            self._add_lane()
        elif step == "stop":
            # If stop line set, advance
            if len(self.calib[d].get("stop_line", [])) == 2:
                self._goto_step(4)

    def _undo(self):
        self._on_right(type("E", (), {"x": 0, "y": 0})())

    def _clear_step(self):
        d    = self.cur_dir
        step = STEP_KEYS[self.cur_step]
        data = self.calib[d]
        if step == "road":
            data["road_polygon"] = []
        elif step == "in":
            data["lanes_in"][self.cur_lane_in] = []
        elif step == "out":
            data["lanes_out"][self.cur_lane_out] = []
        elif step == "stop":
            data["stop_line"] = []
        self._update_lane_info()
        self._redraw()

    # ── Image loading ─────────────────────────────────────────────────────────

    def _load_bg(self, d: str):
        if d not in self._bg_orig:
            self._bg_orig[d] = Image.open(STREET_IMAGES[d]).convert("RGB")

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _redraw(self):
        if not hasattr(self, "_canvas"):
            return
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            return
        d = self.cur_dir
        if d not in self._bg_orig:
            return

        orig = self._bg_orig[d]
        ow, oh = orig.size
        scale  = min(cw / ow, ch / oh)
        dw, dh = int(ow * scale), int(oh * scale)
        ox, oy = (cw - dw) // 2, (ch - dh) // 2

        self._disp_w = dw
        self._disp_h = dh
        self._off_x  = ox
        self._off_y  = oy

        # Base image
        bg = orig.resize((dw, dh), Image.LANCZOS)
        canvas_img = Image.new("RGB", (cw, ch), (8, 8, 16))
        canvas_img.paste(bg, (ox, oy))

        # Overlay layer (RGBA)
        ov = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        draw = ImageDraw.Draw(ov)

        data  = self.calib[d]
        step  = STEP_KEYS[self.cur_step]
        mouse = self._mouse_frac

        # ── 1. Road polygon ────────────────────────────────────────────────
        poly = data.get("road_polygon", [])
        if poly:
            pts_px = [self._frac_to_px(p[0], p[1]) for p in poly]
            if len(pts_px) >= 3:
                draw.polygon(pts_px, fill=C_ROAD_FILL)
                draw.line(pts_px + [pts_px[0]], fill=C_ROAD_LINE, width=2)
            elif len(pts_px) >= 2:
                draw.line(pts_px, fill=C_ROAD_LINE, width=2)
            # Vertices
            for i, pt in enumerate(pts_px):
                r = R_WAYPOINT
                draw.ellipse([(pt[0]-r, pt[1]-r), (pt[0]+r, pt[1]+r)],
                             fill=(100, 140, 255, 220), outline=(200, 220, 255, 200), width=1)
            # Rubber-band last edge
            if step == "road" and mouse and pts_px:
                mpt = self._frac_to_px(mouse[0], mouse[1])
                draw.line([pts_px[-1], mpt], fill=(*_hex_rgb("#6090ff"), 140), width=2)

        # ── 2. Incoming lanes ──────────────────────────────────────────────
        for li, lane in enumerate(data.get("lanes_in", [])):
            is_active = (step == "in" and li == self.cur_lane_in)
            col_hex = C_IN_COLORS[li % len(C_IN_COLORS)]
            col_rgb = _hex_rgb(col_hex)
            alpha   = 255 if is_active else 160
            width   = 4   if is_active else 2

            pts_px = [self._frac_to_px(p[0], p[1]) for p in lane]
            if len(pts_px) >= 2:
                draw.line(pts_px, fill=(*col_rgb, alpha), width=width)
                # Direction arrows along lane
                for seg_i in range(len(pts_px) - 1):
                    mid = ((pts_px[seg_i][0]+pts_px[seg_i+1][0])//2,
                           (pts_px[seg_i][1]+pts_px[seg_i+1][1])//2)
                    _draw_arrow(draw, pts_px[seg_i], mid, col_rgb, alpha, size=10)

            for j, pt in enumerate(pts_px):
                r = R_FIRST if j == 0 else R_WAYPOINT
                draw.ellipse([(pt[0]-r, pt[1]-r), (pt[0]+r, pt[1]+r)],
                             fill=(*col_rgb, alpha),
                             outline=(255, 255, 255, 180), width=1)
                self._draw_label(draw, pt[0]+8, pt[1]-8,
                                 f"IN{li}.{j}", col_hex, alpha)

            # Lane start badge
            if pts_px:
                self._draw_badge(draw, pts_px[0][0], pts_px[0][1]+12,
                                 f" IN #{li+1} ", col_hex)

            # Rubber-band
            if is_active and mouse and pts_px:
                mpt = self._frac_to_px(mouse[0], mouse[1])
                draw.line([pts_px[-1], mpt], fill=(*col_rgb, 120), width=2)

        # ── 3. Outgoing lanes ─────────────────────────────────────────────
        for li, lane in enumerate(data.get("lanes_out", [])):
            is_active = (step == "out" and li == self.cur_lane_out)
            col_hex = C_OUT_COLORS[li % len(C_OUT_COLORS)]
            col_rgb = _hex_rgb(col_hex)
            alpha   = 255 if is_active else 160
            width   = 4   if is_active else 2

            pts_px = [self._frac_to_px(p[0], p[1]) for p in lane]
            if len(pts_px) >= 2:
                draw.line(pts_px, fill=(*col_rgb, alpha), width=width)
                for seg_i in range(len(pts_px) - 1):
                    mid = ((pts_px[seg_i][0]+pts_px[seg_i+1][0])//2,
                           (pts_px[seg_i][1]+pts_px[seg_i+1][1])//2)
                    _draw_arrow(draw, pts_px[seg_i], mid, col_rgb, alpha, size=10)

            for j, pt in enumerate(pts_px):
                r = R_FIRST if j == 0 else R_WAYPOINT
                draw.ellipse([(pt[0]-r, pt[1]-r), (pt[0]+r, pt[1]+r)],
                             fill=(*col_rgb, alpha),
                             outline=(255, 255, 255, 180), width=1)
                self._draw_label(draw, pt[0]+8, pt[1]-8,
                                 f"OUT{li}.{j}", col_hex, alpha)

            if pts_px:
                self._draw_badge(draw, pts_px[0][0], pts_px[0][1]+12,
                                 f" OUT #{li+1} ", col_hex)

            if is_active and mouse and pts_px:
                mpt = self._frac_to_px(mouse[0], mouse[1])
                draw.line([pts_px[-1], mpt], fill=(*col_rgb, 120), width=2)

        # ── 4. Stop line ───────────────────────────────────────────────────
        sl = data.get("stop_line", [])
        if len(sl) >= 1:
            p0 = self._frac_to_px(sl[0][0], sl[0][1])
            # First point dot
            r = R_STOP
            draw.ellipse([(p0[0]-r, p0[1]-r), (p0[0]+r, p0[1]+r)],
                         fill=C_STOP_FILL, outline=(255, 100, 100, 240), width=2)

            if len(sl) == 2:
                p1 = self._frac_to_px(sl[1][0], sl[1][1])
                # Thick dashed red stop line
                _draw_dashed_line(draw, p0, p1, C_STOP_FILL, dash=14, gap=6, width=5)
                # "STOP" label at midpoint
                mid = ((p0[0]+p1[0])//2, (p0[1]+p1[1])//2)
                self._draw_badge(draw, mid[0], mid[1]-20, " STOP LINE ", "#ff2222")
                # Second dot
                draw.ellipse([(p1[0]-r, p1[1]-r), (p1[0]+r, p1[1]+r)],
                             fill=C_STOP_FILL, outline=(255, 100, 100, 240), width=2)
            elif step == "stop" and mouse:
                mpt = self._frac_to_px(mouse[0], mouse[1])
                _draw_dashed_line(draw, p0, mpt, (255, 60, 60, 120), dash=14, gap=6, width=4)

        elif step == "stop" and mouse and not sl:
            # Ghost preview of first click
            mpt = self._frac_to_px(mouse[0], mouse[1])
            draw.ellipse([(mpt[0]-R_STOP, mpt[1]-R_STOP),
                          (mpt[0]+R_STOP, mpt[1]+R_STOP)],
                         fill=(255, 60, 60, 80), outline=(255, 100, 100, 120), width=1)

        # ── Composite & show ───────────────────────────────────────────────
        base_rgba = canvas_img.convert("RGBA")
        final     = Image.alpha_composite(base_rgba, ov).convert("RGB")
        self._tk_img = ImageTk.PhotoImage(final)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def _draw_label(self, draw, x, y, text, col_hex, alpha=220):
        try:
            font = ImageFont.truetype("arial.ttf", 10)
        except:
            font = ImageFont.load_default()
        rgb = _hex_rgb(col_hex)
        draw.text((x+1, y+1), text, fill=(0, 0, 0, 180), font=font)
        draw.text((x, y),   text, fill=(*rgb, alpha),   font=font)

    def _draw_badge(self, draw, x, y, text, col_hex):
        try:
            font = ImageFont.truetype("arialbd.ttf", 11)
        except:
            font = ImageFont.load_default()
        rgb = _hex_rgb(col_hex)
        tw  = int(draw.textlength(text, font=font))
        pad = 4
        draw.rectangle([(x-pad, y-pad), (x+tw+pad, y+14+pad)],
                       fill=(0, 0, 0, 180))
        draw.text((x, y), text, fill=(*rgb, 240), font=font)

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self):
        # Remove empty lanes
        for d in DIRECTIONS:
            data = self.calib[d]
            data["lanes_in"]  = [l for l in data["lanes_in"]  if len(l) >= 2]
            data["lanes_out"] = [l for l in data["lanes_out"] if len(l) >= 2]
            if not data["lanes_in"]:
                data["lanes_in"]  = [[[0.25,0.0],[0.30,0.5],[0.35,0.9]]]
            if not data["lanes_out"]:
                data["lanes_out"] = [[[0.65,0.9],[0.70,0.5],[0.75,0.0]]]

        save_calib(self.calib)
        self._print_config_snippet()
        messagebox.showinfo(
            "Saved ✓",
            f"calibration.json berhasil disimpan!\n\n"
            f"Path: {CALIB_FILE}\n\n"
            "Jalankan simulator.py untuk melihat hasilnya.\n"
            "Lihat terminal untuk output config snippet."
        )

    def _print_config_snippet(self):
        print("\n" + "="*70)
        print("# Snippet yang bisa di-paste ke config.py (referensi):")
        print("="*70)
        for d in DIRECTIONS:
            data = self.calib[d]
            print(f"\n# {d}")
            print(f"  lanes_in  ({len(data['lanes_in'])} lane):")
            for i, l in enumerate(data["lanes_in"]):
                print(f"    [{i}]: {len(l)} waypoints")
            print(f"  lanes_out ({len(data['lanes_out'])} lane):")
            for i, l in enumerate(data["lanes_out"]):
                print(f"    [{i}]: {len(l)} waypoints")
            sl = data.get("stop_line", [])
            print(f"  stop_line: {'SET (' + str(sl) + ')' if len(sl)==2 else 'NOT SET'}")
        print("="*70 + "\n")


# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = CalibApp()
    app.mainloop()
