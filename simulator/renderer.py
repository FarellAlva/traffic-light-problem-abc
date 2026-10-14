"""
Renderer: draws each quadrant with background, vehicles.
Uses PIL for compositing + real sprite photos from sprite_engine.
"""
import math
import time
from PIL import Image, ImageDraw, ImageFont
from config import (
    QUADRANT_W, QUADRANT_H, LANE_PATHS, VEHICLE_TYPES,
    TRAFFIC_LIGHT_POS,
)
from sprite_engine import blit_vehicle_sprite, SPRITE_BANK


# ─── Path utilities ────────────────────────────────────────────────────────────

def _lerp_path(path, t):
    """Interpolate along a list of (x,y) waypoints. t ∈ [0,1]."""
    if len(path) < 2:
        return path[0]
    n = len(path) - 1
    seg_len = 1.0 / n
    seg_idx = min(int(t / seg_len), n - 1)
    local_t = (t - seg_idx * seg_len) / seg_len
    x = path[seg_idx][0] + (path[seg_idx+1][0] - path[seg_idx][0]) * local_t
    y = path[seg_idx][1] + (path[seg_idx+1][1] - path[seg_idx][1]) * local_t
    return x, y


def _perspective_scale(t: float, is_outgoing: bool, direction: str) -> float:
    """
    Compute scale factor based on perceived proximity to viewer.
    Each direction has a different axis where proximity increases.
    """
    if direction == "NORTH":
        # incoming: t=0 far (top), t=1 close (bottom)
        proximity = t if not is_outgoing else (1.0 - t)
    elif direction == "EAST":
        # incoming: t=0 far (right), t=1 close (left)
        proximity = t if not is_outgoing else (1.0 - t)
    elif direction == "WEST":
        # incoming: t=0 far (left), t=1 close (right)
        proximity = t if not is_outgoing else (1.0 - t)
    else:  # SOUTH
        # incoming: t=0 far (bottom), t=1 close (top)
        proximity = t if not is_outgoing else (1.0 - t)

    # min scale 0.28 (far), max 1.0 (near)
    return 0.28 + proximity * 0.72


# ─── Color utilities ────────────────────────────────────────────────────────────

def hex_to_rgb(hex_color: str):
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    h = h.ljust(6, '0')[:6]
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _darken(color_hex, factor=0.55):
    r, g, b = hex_to_rgb(color_hex)
    return (int(r*factor), int(g*factor), int(b*factor))


def _lighten(color_hex, factor=1.5):
    r, g, b = hex_to_rgb(color_hex)
    return (min(255, int(r*factor)), min(255, int(g*factor)), min(255, int(b*factor)))


# ─── Vehicle drawing ────────────────────────────────────────────────────────────

def _draw_vehicle(draw: ImageDraw.Draw, cx: int, cy: int, w: int, h: int,
                  color_hex: str, vtype: str, alpha: int = 255):
    """
    Draw a top-down perspective vehicle sprite at (cx, cy).
    Width is lateral, height is along direction of travel.
    """
    body  = hex_to_rgb(color_hex)
    dark  = _darken(color_hex, 0.45)
    light = _lighten(color_hex, 1.6)

    hw = max(2, w // 2)
    hh = max(2, h // 2)

    if vtype == "moto":
        # Slim oval for motorcycle
        bw = max(2, w // 2)
        bh = max(3, h)
        draw.ellipse([(cx - bw, cy - bh), (cx + bw, cy + bh)],
                     fill=(*body, alpha), outline=(*dark, alpha), width=1)
        # Helmet (small circle on top half)
        hr = max(2, w // 2)
        draw.ellipse([(cx - hr, cy - hh - hr), (cx + hr, cy - hh + hr)],
                     fill=(60, 50, 40, alpha))
        return

    def safe_rect(x0, y0, x1, y1, **kw):
        """Draw rectangle only if coordinates are valid."""
        if x1 > x0 and y1 > y0:
            draw.rectangle([(x0, y0), (x1, y1)], **kw)

    # ── Main body rectangle
    safe_rect(cx - hw, cy - hh, cx + hw, cy + hh,
              fill=(*body, alpha), outline=(*dark, alpha), width=1)

    if vtype == "truck":
        # Truck: flat top, cargo area
        cargo_h = max(1, hh // 2)
        safe_rect(cx - hw + 2, cy - hh + 2, cx + hw - 2, cy - hh + cargo_h,
                  fill=(*dark, alpha))
        # Cab section
        cab_y0 = cy - hh + cargo_h + 1
        cab_y1 = cy + hh - 2
        safe_rect(cx - hw + 2, cab_y0, cx + hw - 2, cab_y1,
                  fill=(*light, alpha))
        return

    # ── Roof (sedan/mpv) — darker, inset
    rm_w = max(1, w // 5)
    rm_h = max(1, h // 5)
    roof_top = cy - hh + rm_h
    roof_bot = cy + hh // 4
    if roof_bot > roof_top:
        safe_rect(cx - hw + rm_w, roof_top, cx + hw - rm_w, roof_bot,
                  fill=(*dark, alpha))

    # ── Windshield (light blue glass)
    ws_top = cy - hh + 1
    ws_bot = roof_top + 1
    ws_lft = cx - hw + rm_w + 1
    ws_rgt = cx + hw - rm_w - 1
    if ws_rgt > ws_lft and ws_bot > ws_top:
        safe_rect(ws_lft, ws_top, ws_rgt, ws_bot,
                  fill=(140, 200, 230, min(alpha, 200)))

    # ── Headlights (front = top in our top-down view)
    ll = max(2, w // 7)
    # Front (top of car)
    safe_rect(cx - hw, cy - hh, cx - hw + ll, cy - hh + ll,
              fill=(255, 255, 200, alpha))
    safe_rect(cx + hw - ll, cy - hh, cx + hw, cy - hh + ll,
              fill=(255, 255, 200, alpha))
    # Rear lights (bottom of car)
    safe_rect(cx - hw, cy + hh - ll, cx - hw + ll, cy + hh,
              fill=(200, 30, 30, alpha))
    safe_rect(cx + hw - ll, cy + hh - ll, cx + hw, cy + hh,
              fill=(200, 30, 30, alpha))

    # ── Wheels (4 corners)
    ww = max(2, w // 6)
    wh = max(2, h // 5)
    for wx, wy in [(cx - hw, cy - hh), (cx + hw - ww, cy - hh),
                   (cx - hw, cy + hh - wh), (cx + hw - ww, cy + hh - wh)]:
        safe_rect(wx, wy, wx + ww, wy + wh, fill=(15, 15, 15, alpha))


# ─── Traffic light drawing ────────────────────────────────────────────────────

def _draw_traffic_light(draw: ImageDraw.Draw, cx: int, cy: int,
                        state: str, remaining: float):
    """Draw a compact traffic light pole with countdown."""
    hw, hh = 14, 42
    # Housing
    draw.rounded_rectangle([(cx - hw, cy - hh), (cx + hw, cy + hh)],
                            radius=4, fill=(25, 25, 25, 235), outline=(70, 70, 70), width=1)

    r = 6
    centers_y = [cy - hh + 8 + r, cy, cy + hh - 8 - r]
    colors_off = [(70, 15, 15), (70, 55, 10), (10, 55, 20)]
    colors_on  = {
        "RED":    [(230, 40, 40), None,          None],
        "GREEN":  [None,          None,          (40, 210, 90)],
        "YELLOW": [None,          (220, 175, 30), None],
    }
    on_set = colors_on.get(state, [None, None, None])

    for i, (light_cy, off_c) in enumerate(zip(centers_y, colors_off)):
        fill = on_set[i] if on_set[i] else off_c
        draw.ellipse([(cx - r, light_cy - r), (cx + r, light_cy + r)], fill=(*fill, 255))
        if on_set[i]:
            # Glow ring
            draw.ellipse([(cx - r - 2, light_cy - r - 2), (cx + r + 2, light_cy + r + 2)],
                         outline=(*fill, 120), width=1)

    # Pole
    draw.line([(cx, cy + hh), (cx, cy + hh + 12)], fill=(50, 50, 50), width=3)

    # Countdown text
    txt = f"{int(remaining)}s"
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except:
        font = ImageFont.load_default()

    tw = draw.textlength(txt, font=font)
    tx = int(cx - tw / 2)
    ty = cy + hh + 14

    state_rgb = {"RED": (255, 70, 70), "GREEN": (70, 255, 110), "YELLOW": (255, 215, 50)}
    c = state_rgb.get(state, (200, 200, 200))
    # Shadow
    draw.text((tx + 1, ty + 1), txt, fill=(0, 0, 0, 180), font=font)
    draw.text((tx, ty), txt, fill=(*c, 230), font=font)


# ─── Quadrant Renderer ────────────────────────────────────────────────────────

class QuadrantRenderer:
    """Renders one quadrant: real street background + animated vehicles + light."""

    def __init__(self, direction: str, bg_image_path: str):
        self.direction = direction
        self._bg_orig  = Image.open(bg_image_path).convert("RGBA")
        self._bg_cache = None
        self._bg_size  = None

        # Pre-load fonts
        self._font_label = None
        self._font_small = None

    def _get_bg(self, w: int, h: int) -> Image.Image:
        if self._bg_size != (w, h):
            self._bg_cache = self._bg_orig.resize((w, h), Image.LANCZOS)
            self._bg_size  = (w, h)
        return self._bg_cache.copy()

    def _get_fonts(self):
        if self._font_label is None:
            try:
                self._font_label = ImageFont.truetype("arialbd.ttf", 15)
                self._font_small = ImageFont.truetype("arial.ttf", 10)
            except:
                self._font_label = ImageFont.load_default()
                self._font_small = ImageFont.load_default()
        return self._font_label, self._font_small

    def render(self, w: int, h: int, vehicles: list) -> Image.Image:
        frame   = self._get_bg(w, h)           # RGBA
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)

        lp = LANE_PATHS[self.direction]
        paths_in  = lp["lanes_in"]
        paths_out = lp["lanes_out"]

        # Painter's algorithm: draw vehicles further away (smaller y) first
        def depth_key(v):
            t = min(v.t, 0.999)
            tracks = paths_out if v.is_outgoing else paths_in
            path   = tracks[v.lane_idx % len(tracks)]
            _, fy = _lerp_path(path, t)
            return fy

        sorted_v = sorted(vehicles, key=depth_key)

        for v in sorted_v:
            t = min(v.t, 0.999)
            tracks = paths_out if v.is_outgoing else paths_in
            path   = tracks[v.lane_idx % len(tracks)]
            fx, fy = _lerp_path(path, t)

            px = int(fx * w)
            py = int(fy * h)

            scale = _perspective_scale(t, v.is_outgoing, self.direction)
            vw = max(5, int(v.base_w * scale))
            vh = max(4, int(v.base_h * scale))
            alpha_f = v.alpha   # 0.0 – 1.0

            if alpha_f < 0.04:
                continue

            # ── Try real sprite first ───────────────────────────────────────
            # Since we now have front/rear sprites, we pass v.is_outgoing
            # We still flip if needed (though the user might have provided correctly oriented ones, let's keep flip_h for now, or maybe flip=False since front/rear is correct?)
            # Usually front/rear sprites don't need horizontal flipping unless they are asymmetric or we want variety. I'll keep flip_h=False for now since the custom sprites might just work.
            used_sprite = blit_vehicle_sprite(
                frame, px, py, vw, vh,
                v.vtype, v.sprite_idx,
                is_outgoing=v.is_outgoing,
                alpha_factor=alpha_f,
                flip_h=False,
            )

            # ── Fallback: draw with PIL if no sprite available ──────────────
            if not used_sprite:
                alpha_i = int(255 * alpha_f)
                _draw_vehicle(draw, px, py, vw, vh, v.color, v.vtype, alpha_i)

            # ── Draw Strobe Lights for special vehicles ─────────────────────
            if v.vtype in ("ambulance", "firefighter"):
                t_sec = time.time()
                is_red_on = (int(t_sec * 6) % 2) == 0
                is_blue_on = not is_red_on
                
                strobe_r = max(2, int(vw * 0.08))
                
                # Top roof coordinates
                rx = px - vw * 0.15
                bx = px + vw * 0.15
                ry = py - vh * 0.35
                
                if is_red_on:
                    draw.ellipse([rx-strobe_r, ry-strobe_r, rx+strobe_r, ry+strobe_r], fill=(255, 50, 50, int(255 * alpha_f)))
                    # optional glow
                    draw.ellipse([rx-strobe_r*2, ry-strobe_r*2, rx+strobe_r*2, ry+strobe_r*2], fill=(255, 50, 50, int(100 * alpha_f)))
                
                if is_blue_on:
                    draw.ellipse([bx-strobe_r, ry-strobe_r, bx+strobe_r, ry+strobe_r], fill=(50, 50, 255, int(255 * alpha_f)))
                    # optional glow
                    draw.ellipse([bx-strobe_r*2, ry-strobe_r*2, bx+strobe_r*2, ry+strobe_r*2], fill=(50, 50, 255, int(100 * alpha_f)))

        # Composite PIL fallback overlay onto background
        frame = Image.alpha_composite(frame, overlay)

        # Direction label (top-left corner)
        tl_draw = ImageDraw.Draw(frame)
        font_label, _ = self._get_fonts()
        label = self.direction
        lw = int(tl_draw.textlength(label, font=font_label))
        pad = 5
        lx, ly = 8, 8
        tl_draw.rectangle([(lx - pad, ly - pad), (lx + lw + pad, ly + 16 + pad)],
                          fill=(0, 0, 0, 195))
        tl_draw.text((lx, ly), label, fill=(255, 255, 255), font=font_label)

        return frame.convert("RGB")



# ─── Intersection 4-quadrant Renderer ────────────────────────────────────────

class IntersectionRenderer:
    """Assembles the full 4-quadrant view like architecture/image.png."""

    POSITIONS = {
        "NORTH": (0, 0),
        "EAST":  (1, 0),
        "WEST":  (0, 1),
        "SOUTH": (1, 1),
    }

    def __init__(self, renderers: dict):
        self.renderers = renderers
        self._font_compass  = None
        self._font_ts       = None

    def _get_fonts(self):
        if self._font_compass is None:
            try:
                self._font_compass = ImageFont.truetype("arialbd.ttf", 20)
                self._font_ts      = ImageFont.truetype("arial.ttf", 12)
            except:
                self._font_compass = ImageFont.load_default()
                self._font_ts      = ImageFont.load_default()
        return self._font_compass, self._font_ts

    def render(self, qw: int, qh: int, lanes: dict, lights: dict,
               sim_time: float) -> Image.Image:
        canvas = Image.new("RGB", (qw * 2, qh * 2), (0, 0, 0))

        for direction, renderer in self.renderers.items():
            col, row = self.POSITIONS[direction]
            lane   = lanes[direction]
            light  = lights[direction]
            vehicles = lane.incoming + lane.outgoing
            frame  = renderer.render(qw, qh, vehicles)
            canvas.paste(frame, (col * qw, row * qh))

        return canvas
