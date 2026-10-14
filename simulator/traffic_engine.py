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
    """
    Light display model for a single direction.
    State, durations, and remaining countdown are managed centrally by Intersection
    to strictly guarantee that exactly one approach has green/yellow at any time.
    """
    def __init__(self, direction: str, offset: float = 0.0):
        self.direction = direction
        self.state = "RED"  # "RED", "GREEN", "YELLOW"
        self._time_remaining = 0.0
        self.green_duration = DEFAULT_GREEN_DURATION.get(direction, 25.0)
        self.red_duration = DEFAULT_RED_DURATION.get(direction, 84.0)
        self.yellow_duration = DEFAULT_YELLOW_DURATION

    @property
    def is_green(self) -> bool:
        return self.state == "GREEN"

    @property
    def is_yellow(self) -> bool:
        return self.state == "YELLOW"

    @property
    def is_red(self) -> bool:
        return self.state == "RED"

    def current_duration(self) -> float:
        if self.state == "GREEN":
            return self.green_duration
        elif self.state == "YELLOW":
            return self.yellow_duration
        return self.red_duration

    def time_remaining(self) -> float:
        return max(0.0, self._time_remaining)

    def update(self, dt: float):
        # Controlled centrally by Intersection master phase sequencer
        pass


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


PHASE_ORDER = ["NORTH", "EAST", "SOUTH", "WEST"]


class Lane:
    """Manages all vehicles for one direction (incoming + outgoing)."""

    def __init__(self, direction: str, light: TrafficLight):
        self.direction = direction
        self.light     = light
        self.incoming: list[Vehicle] = []
        self.outgoing: list[Vehicle] = []

        self._spawn_timer_in  = {i: random.uniform(0.0, 1.5)
                                  for i in range(len(LANE_PATHS[direction]["lanes_in"]))}
        self._spawn_timer_out = {i: random.uniform(0.0, 2.5)
                                  for i in range(len(LANE_PATHS[direction]["lanes_out"]))}
        self.total_passed = 0
        self.total_wait   = 0.0
        self._n_lanes_in  = len(LANE_PATHS[direction]["lanes_in"])
        self._n_lanes_out = len(LANE_PATHS[direction]["lanes_out"])
        self.spawn_interval_base = SPAWN_INTERVAL_BASE
        self.spawn_jitter = SPAWN_JITTER
        self.max_incoming = MAX_VEHICLES_PER_LANE
        self.max_outgoing = 6

    @property
    def vehicles(self):
        return self.incoming + self.outgoing

    def _spawn_interval(self, base_extra=0.0):
        base = getattr(self, "spawn_interval_base", SPAWN_INTERVAL_BASE)
        jitter = getattr(self, "spawn_jitter", SPAWN_JITTER)
        return max(0.8, base + base_extra + random.uniform(-jitter, jitter))

    def spawn_special_vehicle(self, vtype: str, dest_dir: str):
        """Manually spawns an emergency vehicle at a random lane."""
        lane_idx = random.randint(0, self._n_lanes_in - 1)
        v = Vehicle(self.direction, is_outgoing=False, lane_idx=lane_idx, vtype=vtype, dest_dir=dest_dir)
        self.incoming.append(v)

    def update(self, dt: float, sim_speed: float):
        rdt = dt * sim_speed

        # Spawn incoming vehicles per lane track
        for lane_idx in range(self._n_lanes_in):
            self._spawn_timer_in[lane_idx] += rdt
            interval = self._spawn_interval(lane_idx * 0.35)
            if (self._spawn_timer_in[lane_idx] >= interval
                    and len(self.incoming) < self.max_incoming):
                self._spawn_timer_in[lane_idx] = 0.0
                v = Vehicle(self.direction, False, lane_idx)
                self.incoming.append(v)

        # Spawn outgoing vehicles
        for lane_idx in range(self._n_lanes_out):
            self._spawn_timer_out[lane_idx] += rdt
            interval = self._spawn_interval(1.2 + lane_idx * 0.5)
            if (self._spawn_timer_out[lane_idx] >= interval
                    and len(self.outgoing) < self.max_outgoing):
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
    """
    Central Master Intersection Phase Coordinator.
    Enforces a strict 4-phase sequential cyclic schedule:
      Stage 0: North Green
      Stage 1: North Yellow (3s)
      Stage 2: East Green
      Stage 3: East Yellow (3s)
      Stage 4: South Green
      Stage 5: South Yellow (3s)
      Stage 6: West Green
      Stage 7: West Yellow (3s)
    Mathematically guarantees that exactly ONE approach has Green or Yellow at any moment.
    All other approaches are strictly and unconditionally RED.
    """

    def __init__(self):
        self.green_times = {"NORTH": 25.0, "EAST": 25.0, "SOUTH": 25.0, "WEST": 25.0}
        self.yellow_time = 3.0

        self.stage_idx = 0      # 0 to 7
        self.stage_timer = 0.0  # seconds elapsed in active stage

        self.lights = {d: TrafficLight(d) for d in DIRECTIONS}
        self.lanes  = {d: Lane(d, self.lights[d]) for d in DIRECTIONS}
        self.elapsed  = 0.0
        self.sim_speed = 1.0
        self.current_scenario = "padat"

        self._update_all_lights()
        self.set_scenario("padat", flush_excess=True)

    def _stage_duration(self, stage: int) -> float:
        if stage % 2 == 0:
            d = PHASE_ORDER[stage // 2]
            return max(5.0, float(self.green_times[d]))
        else:
            return self.yellow_time

    def _update_all_lights(self):
        active_dir = PHASE_ORDER[self.stage_idx // 2]
        is_green = (self.stage_idx % 2 == 0)
        curr_dur = self._stage_duration(self.stage_idx)
        rem_in_stage = max(0.0, curr_dur - self.stage_timer)

        c_tot = sum(self.green_times.values()) + 4.0 * self.yellow_time

        for d in DIRECTIONS:
            light = self.lights[d]
            light.green_duration = self.green_times[d]
            light.yellow_duration = self.yellow_time
            light.red_duration = max(3.0, c_tot - self.green_times[d] - self.yellow_time)

            if d == active_dir:
                light.state = "GREEN" if is_green else "YELLOW"
                light._time_remaining = rem_in_stage
            else:
                light.state = "RED"
                # Compute countdown until this direction's turn to get Green
                target_stage = 2 * PHASE_ORDER.index(d)
                t_wait = rem_in_stage
                s = (self.stage_idx + 1) % 8
                while s != target_stage:
                    t_wait += self._stage_duration(s)
                    s = (s + 1) % 8
                light._time_remaining = t_wait

    def update(self, dt: float):
        rdt = dt * self.sim_speed
        self.elapsed += rdt

        # Advance stage timer
        self.stage_timer += rdt
        dur = self._stage_duration(self.stage_idx)
        while self.stage_timer >= dur:
            self.stage_timer -= dur
            self.stage_idx = (self.stage_idx + 1) % 8
            dur = self._stage_duration(self.stage_idx)

        self._update_all_lights()

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
        # Durations are governed by green_times and cycle length
        pass

    def set_green_duration(self, direction: str, secs: float):
        self.green_times[direction] = max(5.0, float(secs))
        self._update_all_lights()

    def set_scenario(self, scenario_name: str, flush_excess: bool = True):
        """
        Dynamically adjusts arrival patterns for all approaches with distinct visual profiles:
        - 'sepi': Sesi 1 Off-Peak (sparse, quiet road, max 3 vehicles, calm flow)
        - 'normal': Sesi 2 Normal (regular moderate urban flow, max 7 vehicles)
        - 'padat': Sesi 3 Peak (dense arterial rush hour, max 16 vehicles, heavy queuing)
        """
        self.current_scenario = scenario_name
        scen_lower = scenario_name.lower()

        if "sepi" in scen_lower or "low" in scen_lower:
            intervals = {"NORTH": 8.5, "EAST": 18.0, "SOUTH": 9.0, "WEST": 20.0}
            jitters   = {"NORTH": 1.5, "EAST": 3.0,  "SOUTH": 1.5, "WEST": 3.0}
            max_in = 3
            max_out = 2
        elif "normal" in scen_lower or "medium" in scen_lower:
            intervals = {"NORTH": 3.5, "EAST": 7.5,  "SOUTH": 3.6, "WEST": 8.0}
            jitters   = {"NORTH": 0.8, "EAST": 1.5,  "SOUTH": 0.8, "WEST": 1.5}
            max_in = 7
            max_out = 4
        else: # padat / peak
            intervals = {"NORTH": 1.25, "EAST": 3.2,  "SOUTH": 1.30, "WEST": 3.5}
            jitters   = {"NORTH": 0.3,  "EAST": 0.6,  "SOUTH": 0.3,  "WEST": 0.6}
            max_in = 16
            max_out = 8

        for d, lane in self.lanes.items():
            lane.spawn_interval_base = intervals.get(d, 3.5)
            lane.spawn_jitter = jitters.get(d, 0.8)
            lane.max_incoming = max_in
            lane.max_outgoing = max_out

            if flush_excess:
                if "sepi" in scen_lower or "low" in scen_lower:
                    # Clear excess queues so off-peak looks sparse and quiet immediately
                    lane.incoming = lane.incoming[:1]
                    lane.outgoing = lane.outgoing[:1]
                    for i in lane._spawn_timer_in:
                        lane._spawn_timer_in[i] = 0.0
                elif "normal" in scen_lower or "medium" in scen_lower:
                    if len(lane.incoming) > 4:
                        lane.incoming = lane.incoming[:4]
                else: # padat
                    # Inject initial rush-hour queue if lane is empty so the peak hour is immediately visible
                    if len(lane.incoming) < 3:
                        for l_idx in range(lane._n_lanes_in):
                            for step in range(2):
                                v = Vehicle(d, is_outgoing=False, lane_idx=l_idx)
                                v.t = 0.62 - step * 0.10
                                v.stopped = True
                                lane.incoming.append(v)

    def apply_4phase_timings(self, green_times: list, sync_phase: bool = False):
        """
        Applies sequential 4-phase coordination (North -> East -> South -> West):
        green_times = [g_N, g_E, g_S, g_W]
        yellow = 3.0s
        If sync_phase is True, resets cycle to start with North Green.
        If sync_phase is False, smoothly updates durations without interrupting current active phase!
        """
        g_N, g_E, g_S, g_W = [max(10.0, float(v)) for v in green_times]
        self.green_times = {"NORTH": g_N, "EAST": g_E, "SOUTH": g_S, "WEST": g_W}

        if sync_phase:
            self.stage_idx = 0
            self.stage_timer = 0.0

        self._update_all_lights()

    def stats(self, direction: str) -> dict:
        lane  = self.lanes[direction]
        light = self.lights[direction]
        return {
            "state":          light.state,
            "time_remaining": light.time_remaining(),
            "queue":          lane.queue_length,
            "total_passed":   lane.total_passed,
            "vehicles":       len(lane.vehicles),
        }
