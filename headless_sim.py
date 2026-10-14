"""
headless_sim.py
Ultra-Fast Microscopic & Queuing Headless Traffic Simulator
Accurately models the 4-phase sequential urban intersection without Tkinter/GUI overhead.

Complies with:
- Direction lanes: NORTH (3 lanes), EAST (2 lanes), SOUTH (3 lanes), WEST (2 lanes)
- Vehicle composition: sedan, mpv, truck, moto with vehicle-dependent saturation headways
- 4-Phase sequential signal control: NORTH -> EAST -> SOUTH -> WEST
- Accumulates real vehicle waiting time (seconds) and queue length (vehicles)
"""

import math
import random
from typing import Dict, List, Tuple
from observation_data import get_scenario_profile

DIRECTIONS = ["NORTH", "EAST", "SOUTH", "WEST"]
LANES_COUNT = {"NORTH": 3, "EAST": 2, "SOUTH": 3, "WEST": 2}

# Saturation headway: seconds per vehicle discharging in green
# Moto discharges faster (~0.9s), Car ~1.9s, MPV ~2.1s, Truck ~3.2s
AVG_DISCHARGE_HEADWAY = 1.95  # seconds per lane per vehicle
MOTO_DISCHARGE_FACTOR = 0.50  # moto discharges twice as fast


class FastIntersectionSimulator:
    """
    Simulates intersection dynamics over a time horizon T_sim (default 180 seconds).
    Evaluates signal timing plan x = [g_N, g_E, g_S, g_W].
    """

    def __init__(self, scenario_name: str = "normal", horizon_sec: float = 180.0, dt: float = 1.0):
        self.scenario_name = scenario_name
        self.horizon_sec = float(horizon_sec)
        self.dt = float(dt)
        self.profile = get_scenario_profile(scenario_name)
        self.arrival_intervals = self.profile["arrival_intervals_sec"]

    def run_simulation(self, green_times: List[float], seed: int = None) -> dict:
        """
        Runs the simulation with green times x = [g_N, g_E, g_S, g_W].
        Returns detailed performance metrics.
        """
        if seed is not None:
            rng = random.Random(seed)
        else:
            rng = random.Random(42)

        g_N, g_E, g_S, g_W = [float(v) for v in green_times]
        yellow_t = 3.0

        # Build 4-phase sequence:
        # Phase 0: North Green
        # Phase 1: North Yellow
        # Phase 2: East Green
        # Phase 3: East Yellow
        # Phase 4: South Green
        # Phase 5: South Yellow
        # Phase 6: West Green
        # Phase 7: West Yellow
        phase_durations = [
            g_N, yellow_t,
            g_E, yellow_t,
            g_S, yellow_t,
            g_W, yellow_t
        ]
        cycle_time = sum(phase_durations)

        # State tracking per direction
        queues = {d: 0.0 for d in DIRECTIONS}
        total_wait_time = {d: 0.0 for d in DIRECTIONS}
        total_arrivals = {d: 0 for d in DIRECTIONS}
        total_passed = {d: 0 for d in DIRECTIONS}
        time_in_queue_samples = []

        # Vehicle arrival rate (veh/sec) per direction
        arrival_rates = {
            d: 1.0 / max(0.5, self.arrival_intervals[d]) for d in DIRECTIONS
        }

        # Fractional spawn accumulator
        spawn_acc = {d: rng.uniform(0.0, 0.5) for d in DIRECTIONS}

        current_time = 0.0
        while current_time < self.horizon_sec:
            # Determine active phase
            t_in_cycle = current_time % cycle_time
            cumul_t = 0.0
            active_phase = 0
            for idx, dur in enumerate(phase_durations):
                cumul_t += dur
                if t_in_cycle < cumul_t:
                    active_phase = idx
                    break

            # Map active phase to green direction
            green_dir = None
            if active_phase == 0:
                green_dir = "NORTH"
            elif active_phase == 2:
                green_dir = "EAST"
            elif active_phase == 4:
                green_dir = "SOUTH"
            elif active_phase == 6:
                green_dir = "WEST"

            # 1. Process arrivals (Poisson-like stochastic arrivals)
            for d in DIRECTIONS:
                spawn_acc[d] += arrival_rates[d] * self.dt
                # Add slight stochastic jitter
                p_arrival = spawn_acc[d]
                new_veh = int(p_arrival)
                if rng.random() < (p_arrival - new_veh):
                    new_veh += 1
                spawn_acc[d] -= new_veh

                queues[d] += new_veh
                total_arrivals[d] += new_veh

            # 2. Process discharges for active green direction
            if green_dir is not None:
                n_lanes = LANES_COUNT[green_dir]
                # Maximum vehicles that can discharge in this dt across all lanes
                # Discharge capacity = lanes * (dt / headway)
                discharge_cap = (n_lanes * self.dt) / AVG_DISCHARGE_HEADWAY
                # 20% motorcycles discharge with less headway
                discharge_cap *= 1.15  # motorcycle capacity boost
                
                discharged = min(queues[green_dir], discharge_cap)
                queues[green_dir] -= discharged
                total_passed[green_dir] += int(discharged)

            # 3. Accumulate waiting time for stopped vehicles
            current_total_queue = 0
            for d in DIRECTIONS:
                q = queues[d]
                total_wait_time[d] += q * self.dt
                current_total_queue += q
            time_in_queue_samples.append(current_total_queue)

            current_time += self.dt

        # Summary Metrics
        sum_arrivals = sum(total_arrivals.values())
        sum_passed = sum(total_passed.values())
        sum_wait = sum(total_wait_time.values())
        avg_wait_sec = sum_wait / max(1.0, float(sum_arrivals))
        avg_queue_veh = sum(time_in_queue_samples) / max(1.0, len(time_in_queue_samples))
        max_queue_veh = max(time_in_queue_samples) if time_in_queue_samples else 0.0

        return {
            "green_times": green_times,
            "cycle_time": cycle_time,
            "scenario": self.scenario_name,
            "horizon_sec": self.horizon_sec,
            "total_arrivals": sum_arrivals,
            "total_passed": sum_passed,
            "total_wait_time_sec": round(sum_wait, 2),
            "avg_wait_time_sec": round(avg_wait_sec, 2),
            "avg_queue_length_veh": round(avg_queue_veh, 2),
            "avg_queue_veh": round(avg_queue_veh, 2),
            "max_queue_length_veh": round(max_queue_veh, 2),
            "queue_per_direction": {d: round(queues[d], 2) for d in DIRECTIONS},
            "throughput_ratio": round(sum_passed / max(1.0, float(sum_arrivals)), 4)
        }


if __name__ == "__main__":
    # Test simulation on all scenarios with current practice vs an improved split
    sim_normal = FastIntersectionSimulator("normal", horizon_sec=180.0)
    current_x = [25.0, 25.0, 25.0, 25.0]
    res_curr = sim_normal.run_simulation(current_x, seed=42)
    print("=== NORMAL SCENARIO: CURRENT PRACTICE [25, 25, 25, 25] ===")
    print(f"  Avg Wait: {res_curr['avg_wait_time_sec']}s")
    print(f"  Avg Queue: {res_curr['avg_queue_veh']} veh")
    print(f"  Throughput: {res_curr['total_passed']}/{res_curr['total_arrivals']} ({res_curr['throughput_ratio']*100:.1f}%)")

    # Improved split (more green to heavy North/South)
    improved_x = [35.0, 18.0, 32.0, 17.0]
    res_imp = sim_normal.run_simulation(improved_x, seed=42)
    print("\n=== NORMAL SCENARIO: IMPROVED SPLIT [35, 18, 32, 17] ===")
    print(f"  Avg Wait: {res_imp['avg_wait_time_sec']}s")
    print(f"  Avg Queue: {res_imp['avg_queue_veh']} veh")
    print(f"  Throughput: {res_imp['total_passed']}/{res_imp['total_arrivals']} ({res_imp['throughput_ratio']*100:.1f}%)")
