"""
sprite_engine.py — Manages real vehicle sprites extracted from street_raw photos.
Loads PNG sprites from simulator/sprites/ and provides a blitting interface
that replaces the old PIL draw_vehicle() rectangles in renderer.py.
"""

import os
import random
from PIL import Image, ImageEnhance

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "vehicles_processed")

CAR_FRONT_DIR = os.path.join(ASSETS_DIR, "car_front")
CAR_REAR_DIR = os.path.join(ASSETS_DIR, "car_rear")
MOTO_FRONT_DIR = os.path.join(ASSETS_DIR, "motorbike_front")
MOTO_REAR_DIR = os.path.join(ASSETS_DIR, "motorbike_rear")
AMBULANCE_FRONT_DIR = os.path.join(ASSETS_DIR, "ambulance_front")
AMBULANCE_REAR_DIR = os.path.join(ASSETS_DIR, "ambulance_rear")
FIREFIGHTER_FRONT_DIR = os.path.join(ASSETS_DIR, "firefighter_front")
FIREFIGHTER_REAR_DIR = os.path.join(ASSETS_DIR, "firefighter_rear")

# Map from vehicle type name to category
VTYPE_TO_CAT = {
    "sedan": "car",
    "car":   "car",
    "mpv":   "car",    # mapping all to car since we only have car and motorbike
    "truck": "car",
    "moto":  "moto",
    "ambulance": "ambulance",
    "firefighter": "firefighter",
}


class SpriteBank:
    """Loads and caches all sprite images on first access."""

    def __init__(self):
        self._sprites_front: dict[str, list[Image.Image]] = {}
        self._sprites_rear: dict[str, list[Image.Image]] = {}
        self._loaded = False

    def _load_dir(self, folder_path: str) -> list[Image.Image]:
        images = []
        if os.path.isdir(folder_path):
            for fname in sorted(os.listdir(folder_path)):
                if fname.lower().endswith(".png"):
                    try:
                        img = Image.open(os.path.join(folder_path, fname)).convert("RGBA")
                        images.append(img)
                    except Exception as e:
                        print(f"[sprites] Failed to load {fname}: {e}")
        return images

    def _load(self):
        if self._loaded:
            return
        self._loaded = True

        # Load user's custom sprites
        car_front = self._load_dir(CAR_FRONT_DIR)
        car_rear = self._load_dir(CAR_REAR_DIR)
        moto_front = self._load_dir(MOTO_FRONT_DIR)
        moto_rear = self._load_dir(MOTO_REAR_DIR)
        amb_front = self._load_dir(AMBULANCE_FRONT_DIR)
        amb_rear = self._load_dir(AMBULANCE_REAR_DIR)
        fire_front = self._load_dir(FIREFIGHTER_FRONT_DIR)
        fire_rear = self._load_dir(FIREFIGHTER_REAR_DIR)
        
        for vtype, cat in VTYPE_TO_CAT.items():
            if cat == "car":
                self._sprites_front[vtype] = car_front
                self._sprites_rear[vtype] = car_rear
            elif cat == "moto":
                self._sprites_front[vtype] = moto_front
                self._sprites_rear[vtype] = moto_rear
            elif cat == "ambulance":
                self._sprites_front[vtype] = amb_front
                self._sprites_rear[vtype] = amb_rear
            elif cat == "firefighter":
                self._sprites_front[vtype] = fire_front
                self._sprites_rear[vtype] = fire_rear
                
        print(f"[sprites] Car       : {len(car_front)} front, {len(car_rear)} rear sprites loaded")
        print(f"[sprites] Motorbike : {len(moto_front)} front, {len(moto_rear)} rear sprites loaded")
        print(f"[sprites] Ambulance : {len(amb_front)} front, {len(amb_rear)} rear sprites loaded")
        print(f"[sprites] Firefighter: {len(fire_front)} front, {len(fire_rear)} rear sprites loaded")

    def get(self, vtype: str, sprite_idx: int, is_outgoing: bool) -> Image.Image | None:
        """Return sprite for vtype at index (wraps around). Returns None if unavailable."""
        self._load()
        pool = self._sprites_rear.get(vtype) if is_outgoing else self._sprites_front.get(vtype)
        if not pool:
            return None
        return pool[sprite_idx % len(pool)]


# Global singleton
SPRITE_BANK = SpriteBank()


def blit_vehicle_sprite(
    frame: Image.Image,
    cx: int, cy: int,
    target_w: int, target_h: int,
    vtype: str,
    sprite_idx: int,
    is_outgoing: bool,
    alpha_factor: float = 1.0,
    flip_h: bool = False,
) -> bool:
    """
    Composite a real vehicle sprite onto frame at (cx, cy).
    Sprite is scaled to fit within (target_w × target_h) maintaining aspect ratio.

    Returns True if sprite was used, False if fallback drawing is needed.
    """
    sprite = SPRITE_BANK.get(vtype, sprite_idx, is_outgoing)
    if sprite is None:
        return False

    sw, sh = sprite.size
    # Scale sprite to fit target dimensions, maintain aspect ratio
    scale = min(target_w / sw, target_h / sh)
    scale = max(scale, 0.05)   # never scale to nothing
    new_w = max(2, int(sw * scale))
    new_h = max(2, int(sh * scale))

    if new_w < 2 or new_h < 2:
        return False

    scaled = sprite.resize((new_w, new_h), Image.LANCZOS)

    # Horizontal flip for opposite-direction lanes
    if flip_h:
        scaled = scaled.transpose(Image.FLIP_LEFT_RIGHT)

    # Apply alpha factor
    if alpha_factor < 0.99:
        r, g, b, a = scaled.split()
        a = a.point(lambda v: int(v * alpha_factor))
        scaled = Image.merge("RGBA", (r, g, b, a))

    # Position: centered on (cx, cy)
    px = cx - new_w // 2
    py = cy - new_h // 2

    # Clip to frame bounds
    fw, fh = frame.size
    if px + new_w <= 0 or py + new_h <= 0 or px >= fw or py >= fh:
        return True  # off-screen but sprite was valid

    frame.paste(scaled, (px, py), scaled)
    return True
