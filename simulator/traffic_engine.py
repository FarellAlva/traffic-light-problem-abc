"""
Traffic Engine: TrafficLight, Vehicle, Lane, Intersection logic
Supports multi-lane paths per direction.
"""
import time
import random
import math
from config import (
    DEFAULT_RED_DURATION, DEFAULT_GREEN_DURATION, DEFAULT_YELLOW_DURATION,
    MAX_VEHICLES_PER_LANE, SPAWN_INTERVAL_BASE, SPAWN_JITTER,
    VEHICLE_TYPES, VEHICLE_TYPE_WEIGHTS, LANE_PATHS
)

DIRECTIONS = ["NORTH", "EAST", "SOUTH", "WEST"]


def _lerp_path(path, t):
    """Interpolate along a path of (x,y) tuples. t in [0,1]."""
    if len(path) < 2:
        return path[0]
    seg_len = 1.0 / (len(path) - 1)
    seg_idx = min(int(t / seg_len), len(path) - 2)
    local_t = (t - seg_idx * seg_len) / seg_len
    x = path[seg_idx][0] + (path[seg_idx+1][0] - path[seg_idx][0]) * local_t
    y = path[seg_idx][1] + (path[seg_idx+1][1] - path[seg_idx][1]) * local_t
    return x, y


class TrafficLight:
    """State machine: RED → GREEN → YELLOW → RED"""
    STATES = ["RED", "GREEN", "YELLOW"]

    def __init__(self, direction: str, offset: float = 0.0):
        self.direction = direction
        self.red_duration    = DEFAULT_RED_DURATION[direction]
        self.green_duration  = DEFAULT_GREEN_DURATION[direction]
        self.yellow_duration = DEFAULT_YELLOW_DURATION

        self._state_idx = 0   # start RED
        self._timer = offset  # pre-offset so lanes stagger

    @property
    def state(self) -> str:
        return self.STATES[self._state_idx]

    @property
    def is_green(self) -> bool:
        return self._state_idx == 1

    @property
    def is_yellow(self) -> bool:
        return self._state_idx == 2

    @property
    def is_red(self) -> bool:
        return self._state_idx == 0

    def current_duration(self) -> float:
        return [self.red_duration, self.green_duration, self.yellow_duration][self._state_idx]

    def time_remaining(self) -> float:
        return max(0.0, self.current_duration() - self._timer)

    def update(self, dt: float):
        self._timer += dt
        while self._timer >= self.current_duration():
            self._timer -= self.current_duration()
            self._state_idx = (self._state_idx + 1) % 3


def _weighted_choice(weights: dict) -> str:
    keys = list(weights.keys())
    vals = [weights[k] for k in keys]
    total = sum(vals)
    r = random.random() * total
    cumul = 0
    for k, v in zip(keys, vals):
        cumul += v
        if r <= cumul:
            return k
    return keys[-1]


class Vehicle:
    """
    A single vehicle traveling along one specific lane track.
    lane_idx: which track in lanes_in / lanes_out
    is_outgoing: True if on outgoing track
    """
    def __init__(self, direction: str, is_outgoing: bool, lane_idx: int, vtype: str = None, dest_dir: str = None):
        self.direction   = direction
        self.is_outgoing = is_outgoing
        self.lane_idx    = lane_idx
        self.dest_dir    = dest_dir
        self.is_special  = dest_dir is not None

        if vtype is not None:
            self.vtype = vtype
        else:
            self.vtype = _weighted_choice(VEHICLE_TYPE_WEIGHTS)
            
        self.color = random.choice(VEHICLE_TYPES[self.vtype]["colors"])
        self.base_w = VEHICLE_TYPES[self.vtype]["w"]
        self.base_h = VEHICLE_TYPES[self.vtype]["h"]

        speed_base = {"sedan": 0.13, "mpv": 0.11, "truck": 0.085, "moto": 0.16, "ambulance": 0.15, "firefighter": 0.14}
        jitter = random.uniform(-0.015, 0.015)
        self.speed = speed_base[self.vtype] + jitter

        self.t = 0.0
        self.stopped = False
        self.alpha = 1.0
        self.id = id(self)

        # Assign a random sprite index at spawn — stays fixed for vehicle lifetime
        self.sprite_idx = random.randint(0, 127)

    def get_path(self):
        lp = LANE_PATHS[self.direction]
        key = "lanes_out" if self.is_outgoing else "lanes_in"
        tracks = lp[key]
        idx = self.lane_idx % len(tracks)
        return tracks[idx]

    def _stop_threshold(self):
        """Return t-value where this vehicle should stop at red."""
        lp = LANE_PATHS[self.direction]
        return lp["stop_frac"]

    def update(self, dt: float, light_green: bool, same_lane_vehicles: list):
        stop_thresh = self._stop_threshold()
        # Increased gap to prevent overlap
        min_gap = 0.085

        if self.is_outgoing:
            self.t += self.speed * dt
            if self.t > 0.88:
                self.alpha = max(0.0, 1.0 - (self.t - 0.88) / 0.12)
            return

        # Check gap to vehicle ahead in same lane
        blocked = False
        for other in same_lane_vehicles:
            if (other.id != self.id and not other.is_outgoing
                    and other.lane_idx == self.lane_idx
                    and other.t > self.t):
                
                # Dynamic gap based on the vehicle ahead
                gap = 0.080  # Default car gap
                if other.vtype == "moto":
                    gap = 0.045
                elif other.vtype == "truck":
                    gap = 0.105
                elif other.vtype == "mpv":
                    gap = 0.090
                    
                # If we are a moto, we can squeeze a bit closer
                if self.vtype == "moto":
                    gap *= 0.75
                    
                if (other.t - self.t) < gap:
                    blocked = True
                    break

        # If vehicle is already well past the stop line, it shouldn't stop for red light
        passed_stop_line = (self.t > stop_thresh)
        
        # We only apply red light stopping if it's approaching or exactly at the stop line
        at_stop = (self.t >= stop_thresh - 0.01) and not passed_stop_line

        if at_stop and not light_green and not blocked:
            self.stopped = True
            self.t = min(self.t, stop_thresh - 0.005)
        elif blocked:
            self.stopped = True
        else:
            self.stopped = False
            self.t += self.speed * dt

        if self.t > 0.88:
            self.alpha = max(0.0, 1.0 - (self.t - 0.88) / 0.12)

    @property
    def is_done(self):
        return self.t >= 1.0


class Lane:
    """Manages all vehicles for one direction (incoming + outgoing)."""

    def __init__(self, direction: str, light: TrafficLight):
        self.direction = direction
        self.light     = light
        self.incoming: list[Vehicle] = []
        self.outgoing: list[Vehicle] = []

        self._spawn_timer_in  = {i: random.uniform(0, SPAWN_INTERVAL_BASE * 0.8)
                                  for i in range(len(LANE_PATHS[direction]["lanes_in"]))}
        self._spawn_timer_out = {i: random.uniform(0, SPAWN_INTERVAL_BASE)
                                  for i in range(len(LANE_PATHS[direction]["lanes_out"]))}
        self.total_passed = 0
        self.total_wait   = 0.0
        self._n_lanes_in  = len(LANE_PATHS[direction]["lanes_in"])
        self._n_lanes_out = len(LANE_PATHS[direction]["lanes_out"])

    @property
    def vehicles(self):
        return self.incoming + self.outgoing

    def _spawn_interval(self, base_extra=0.0):
        return max(1.2, SPAWN_INTERVAL_BASE + base_extra + random.uniform(-SPAWN_JITTER, SPAWN_JITTER))

    def spawn_special_vehicle(self, vtype: str, dest_dir: str):
        """Manually spawns an emergency vehicle at a random lane."""
        lane_idx = random.randint(0, self._n_lanes_in - 1)
        v = Vehicle(self.direction, is_outgoing=False, lane_idx=lane_idx, vtype=vtype, dest_dir=dest_dir)
        self.incoming.append(v)

    def update(self, dt: float, sim_speed: float):
        rdt = dt * sim_speed

        # Update light
        self.light.update(rdt)

        # Spawn incoming vehicles per lane track
        for lane_idx in range(self._n_lanes_in):
            self._spawn_timer_in[lane_idx] += rdt
            interval = self._spawn_interval(lane_idx * 0.3)
            in_lane = [v for v in self.incoming if v.lane_idx == lane_idx]
            if (self._spawn_timer_in[lane_idx] >= interval
                    and len(self.incoming) < MAX_VEHICLES_PER_LANE):
                self._spawn_timer_in[lane_idx] = 0.0
                v = Vehicle(self.direction, False, lane_idx)
                self.incoming.append(v)

        # Spawn outgoing vehicles
        for lane_idx in range(self._n_lanes_out):
            self._spawn_timer_out[lane_idx] += rdt
            interval = self._spawn_interval(0.6 + lane_idx * 0.3)
            if (self._spawn_timer_out[lane_idx] >= interval
                    and len(self.outgoing) < MAX_VEHICLES_PER_LANE):
                self._spawn_timer_out[lane_idx] = 0.0
                v = Vehicle(self.direction, True, lane_idx)
                self.outgoing.append(v)

        can_go = self.light.is_green or self.light.is_yellow

        # Update vehicles
        for v in self.incoming:
            if v.stopped:
                self.total_wait += rdt
            v.update(rdt, can_go, self.incoming)
        for v in self.outgoing:
            v.update(rdt, True, self.outgoing)

        # Remove done
        done_in = [v for v in self.incoming if v.is_done]
        self.total_passed += len(done_in)
        self.incoming = [v for v in self.incoming if not v.is_done]
        self.outgoing = [v for v in self.outgoing if not v.is_done]
        
        return done_in

    @property
    def queue_length(self):
        return sum(1 for v in self.incoming if v.stopped)


class Intersection:
    """Top-level coordinator for all 4 lanes."""

    def __init__(self):
        offsets = {"NORTH": 0, "EAST": 28, "SOUTH": 14, "WEST": 42}
        self.lights = {d: TrafficLight(d, offset=offsets[d]) for d in DIRECTIONS}
        self.lanes  = {d: Lane(d, self.lights[d]) for d in DIRECTIONS}
        self.elapsed  = 0.0
        self.sim_speed = 1.0

    def update(self, dt: float):
        self.elapsed += dt
        for lane in self.lanes.values():
            done_in = lane.update(dt, self.sim_speed)
            # Transfer special vehicles to their destination's outgoing lane
            for v in done_in:
                if v.is_special and v.dest_dir in self.lanes:
                    dest_lane = self.lanes[v.dest_dir]
                    v.direction = v.dest_dir
                    v.is_outgoing = True
                    v.t = 0.0
                    v.alpha = 1.0
                    v.lane_idx = random.randint(0, dest_lane._n_lanes_out - 1)
                    dest_lane.outgoing.append(v)

    def set_red_duration(self, direction: str, secs: float):
        self.lights[direction].red_duration = max(3.0, float(secs))

    def set_green_duration(self, direction: str, secs: float):
        self.lights[direction].green_duration = max(3.0, float(secs))

    def stats(self, direction: str) -> dict:
        lane  = self.lanes[direction]
        light = self.lights[direction]
        return {
            "state":         light.state,
            "time_remaining": light.time_remaining(),
            "queue":         lane.queue_length,
            "total_passed":  lane.total_passed,
            "vehicles":      len(lane.vehicles),
        }
