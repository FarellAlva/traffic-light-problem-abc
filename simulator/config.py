"""
Configuration for Urban Intersection Traffic Simulator

LANE_PATHS and TRAFFIC_LIGHT_POS are loaded from calibration.json if it
exists (produced by calibrate.py). If not found, the hardcoded defaults below
are used as-is.
"""
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STREET_DIR = os.path.join(BASE_DIR, "street")
STREET_RAW_DIR = os.path.join(BASE_DIR, "street_raw")
CALIB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration.json")

# Street background images
STREET_IMAGES = {
    "NORTH": os.path.join(STREET_DIR, "north.png"),
    "EAST":  os.path.join(STREET_DIR, "east.png"),
    "SOUTH": os.path.join(STREET_DIR, "south.png"),
    "WEST":  os.path.join(STREET_DIR, "west.png"),
}

# Quadrant layout (row, col)
QUADRANT_POSITIONS = {
    "NORTH": (0, 0),
    "EAST":  (0, 1),
    "WEST":  (1, 0),
    "SOUTH": (1, 1),
}

# Display settings
QUADRANT_W = 560
QUADRANT_H = 420
CONTROL_PANEL_W = 320

# Simulator
FPS = 30
SIM_SPEED = 1.0

# Default traffic light durations (seconds)
DEFAULT_RED_DURATION    = {d: 30 for d in ["NORTH", "EAST", "SOUTH", "WEST"]}
DEFAULT_GREEN_DURATION  = {d: 25 for d in ["NORTH", "EAST", "SOUTH", "WEST"]}
DEFAULT_YELLOW_DURATION = 3

# Vehicle spawn
MAX_VEHICLES_PER_LANE = 14
SPAWN_INTERVAL_BASE   = 2.5   # seconds between spawns (base)
SPAWN_JITTER          = 1.5

# Vehicle types
VEHICLE_TYPES = {
    "sedan": {"w": 56, "h": 38, "colors": ["#e8e8e8","#222222","#3a6bc4","#c43a3a","#c4993a","#5a9c5a"]},
    "mpv":   {"w": 64, "h": 44, "colors": ["#b8b8b8","#111111","#d4d4d4","#8a5a2a","#2a4a8a"]},
    "truck": {"w": 72, "h": 52, "colors": ["#dddddd","#f0f0f0","#c0c0c0","#888888"]},
    "moto":  {"w": 24, "h": 36, "colors": ["#ff0000","#0000ff","#00aa00","#ff8800","#888888","#ffffff"]},
    "ambulance":   {"w": 80, "h": 58, "colors": ["#ffffff"]},
    "firefighter": {"w": 96, "h": 68, "colors": ["#ff0000"]},
}
VEHICLE_TYPE_WEIGHTS = {"sedan": 0.45, "mpv": 0.25, "truck": 0.10, "moto": 0.20}

# UI Colors
COLOR_BG         = "#0a0a12"
COLOR_PANEL_BG   = "#10101e"
COLOR_PANEL_CARD = "#1a1a2e"
COLOR_ACCENT     = "#00d4ff"
COLOR_RED        = "#ff4444"
COLOR_GREEN      = "#44ff88"
COLOR_YELLOW     = "#ffd044"
COLOR_TEXT       = "#e0e8ff"
COLOR_SUBTEXT    = "#7080a0"
COLOR_LABEL_BG   = "black"

# ─── Hardcoded defaults (used when calibration.json is absent) ─────────────────

_DEFAULT_TRAFFIC_LIGHT_POS = {
    "NORTH": (0.36, 0.62),
    "EAST":  (0.16, 0.48),
    "SOUTH": (0.60, 0.32),
    "WEST":  (0.82, 0.52),
}

_DEFAULT_LANE_PATHS = {
    "NORTH": {
        "lanes_in": [
            [(0.22, 0.02), (0.24, 0.50), (0.26, 0.75)],
            [(0.28, 0.02), (0.30, 0.50), (0.32, 0.75)],
            [(0.34, 0.02), (0.36, 0.50), (0.38, 0.75)],
        ],
        "lanes_out": [
            [(0.54, 0.75), (0.58, 0.50), (0.62, 0.02)],
            [(0.62, 0.75), (0.66, 0.50), (0.70, 0.02)],
        ],
        "stop_frac": 0.74,
        "stop_axis": "y",
    },
    "EAST": {
        "lanes_in": [
            [(1.00, 0.34), (0.60, 0.38), (0.18, 0.42)],
            [(1.00, 0.42), (0.60, 0.44), (0.18, 0.48)],
        ],
        "lanes_out": [
            [(0.18, 0.56), (0.60, 0.58), (1.00, 0.60)],
            [(0.18, 0.62), (0.60, 0.64), (1.00, 0.66)],
        ],
        "stop_frac": 0.80,
        "stop_axis": "x_east",
    },
    "WEST": {
        "lanes_in": [
            [(0.00, 0.44), (0.40, 0.48), (0.82, 0.52)],
            [(0.00, 0.52), (0.40, 0.54), (0.82, 0.56)],
        ],
        "lanes_out": [
            [(0.82, 0.34), (0.42, 0.36), (0.00, 0.38)],
            [(0.82, 0.40), (0.42, 0.40), (0.00, 0.40)],
        ],
        "stop_frac": 0.80,
        "stop_axis": "x_west",
    },
    "SOUTH": {
        "lanes_in": [
            [(0.60, 1.00), (0.57, 0.60), (0.55, 0.30)],
            [(0.68, 1.00), (0.65, 0.60), (0.63, 0.30)],
            [(0.76, 1.00), (0.72, 0.60), (0.70, 0.30)],
        ],
        "lanes_out": [
            [(0.38, 0.30), (0.35, 0.60), (0.32, 1.00)],
            [(0.30, 0.30), (0.27, 0.60), (0.24, 1.00)],
        ],
        "stop_frac": 0.70,
        "stop_axis": "y",
    },
}


# ─── Calibration loader ────────────────────────────────────────────────────────

def _seg_intersect_t(a1, a2, b1, b2):
    """
    Find t (0-1) along path segment a1→a2 where it crosses stop line b1→b2.
    Returns None if no intersection.
    """
    dx_a = a2[0] - a1[0];  dy_a = a2[1] - a1[1]
    dx_b = b2[0] - b1[0];  dy_b = b2[1] - b1[1]
    denom = dx_a * dy_b - dy_a * dx_b
    if abs(denom) < 1e-10:
        return None   # parallel
    t = ((b1[0]-a1[0])*dy_b - (b1[1]-a1[1])*dx_b) / denom
    s = ((b1[0]-a1[0])*dy_a - (b1[1]-a1[1])*dx_a) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= s <= 1.0:
        return t
    return None


def _compute_stop_frac(waypoints: list, stop_line: list, direction: str) -> float:
    """
    Find the t-value (0-1) along the waypoint path where it crosses stop_line.
    stop_line = [[x1,y1],[x2,y2]]  (two-point segment)
    Falls back to proximity search if no clean intersection is found.
    """
    n = len(waypoints)
    if n < 2:
        return 0.80

    # ── Prefer exact line-segment intersection ──
    if len(stop_line) == 2 and isinstance(stop_line[0], (list, tuple)):
        b1, b2 = stop_line[0], stop_line[1]
        seg_len = 1.0 / (n - 1)
        for i in range(n - 1):
            a1 = waypoints[i]
            a2 = waypoints[i + 1]
            local_t = _seg_intersect_t(a1, a2, b1, b2)
            if local_t is not None:
                global_t = (i + local_t) * seg_len
                return round(min(0.99, max(0.01, global_t)), 4)

    # ── Fallback: proximity to stop_line midpoint ──
    if len(stop_line) >= 1:
        if len(stop_line) == 2 and isinstance(stop_line[0], (list, tuple)):
            target_x = (stop_line[0][0] + stop_line[1][0]) / 2
            target_y = (stop_line[0][1] + stop_line[1][1]) / 2
        else:
            target_x, target_y = stop_line[0]

        use_y  = direction in ("NORTH", "SOUTH")
        target = target_y if use_y else target_x
        seg_len = 1.0 / (n - 1)
        best_t, best_err = 0.8, float("inf")
        for step in range(201):
            t   = step / 200
            idx = min(int(t / seg_len), n - 2)
            lt  = (t - idx * seg_len) / seg_len
            x0, y0 = waypoints[idx]
            x1, y1 = waypoints[idx + 1]
            val = (y0 + (y1 - y0) * lt) if use_y else (x0 + (x1 - x0) * lt)
            err = abs(val - target)
            if err < best_err:
                best_err, best_t = err, t
        return round(best_t, 4)

    return 0.80


def _load_from_calibration(calib: dict):
    """Convert calibration.json -> (LANE_PATHS, TRAFFIC_LIGHT_POS)."""
    lane_paths, tl_pos = {}, {}
    for d, data in calib.items():
        lanes_in  = [[(p[0], p[1]) for p in lane] for lane in data.get("lanes_in",  [])
                     if len(lane) >= 2]
        lanes_out = [[(p[0], p[1]) for p in lane] for lane in data.get("lanes_out", [])
                     if len(lane) >= 2]

        if not lanes_in:
            lanes_in  = _DEFAULT_LANE_PATHS[d]["lanes_in"]
        if not lanes_out:
            lanes_out = _DEFAULT_LANE_PATHS[d]["lanes_out"]

        # Stop line: support both old format [x,y] and new [[x1,y1],[x2,y2]]
        sl = data.get("stop_line", [])
        if sl and isinstance(sl[0], list):
            # New 2-point format
            stop_frac = _compute_stop_frac(list(lanes_in[0]), sl, d)
        elif sl:
            # Old single-point format
            stop_frac = _compute_stop_frac(list(lanes_in[0]), sl, d)
        else:
            stop_frac = _DEFAULT_LANE_PATHS[d]["stop_frac"]

        stop_axis = "x_east" if d == "EAST" else ("x_west" if d == "WEST" else "y")

        lane_paths[d] = {
            "lanes_in":   lanes_in,
            "lanes_out":  lanes_out,
            "stop_frac":  stop_frac,
            "stop_axis":  stop_axis,
        }
        tl = data.get("traffic_light")
        tl_pos[d] = tuple(tl) if tl else _DEFAULT_TRAFFIC_LIGHT_POS[d]

    return lane_paths, tl_pos


# ── Apply at import time ───────────────────────────────────────────────────────

if os.path.exists(CALIB_FILE):
    try:
        with open(CALIB_FILE) as _f:
            _calib_raw = json.load(_f)
        LANE_PATHS, TRAFFIC_LIGHT_POS = _load_from_calibration(_calib_raw)
        print(f"[config] Loaded calibration: {CALIB_FILE}")
    except Exception as _e:
        print(f"[config] calibration.json load failed ({_e}), using defaults")
        LANE_PATHS        = _DEFAULT_LANE_PATHS
        TRAFFIC_LIGHT_POS = _DEFAULT_TRAFFIC_LIGHT_POS
else:
    LANE_PATHS        = _DEFAULT_LANE_PATHS
    TRAFFIC_LIGHT_POS = _DEFAULT_TRAFFIC_LIGHT_POS
    print("[config] No calibration.json — using hardcoded defaults")
    print("         Run:  python calibrate.py  to calibrate lane positions")
