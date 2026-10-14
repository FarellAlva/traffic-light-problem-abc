"""
abc_optimizer.py
Artificial Bee Colony (ABC) Algorithm for Urban Traffic Signal Optimization.
Compliant with Bio-Inspired Computing Week 9 Assignment requirements:
- Explicit Employed, Onlooker, and Scout phases from scratch (no black-box optimizer)
- Objective cost minimization J(x) >= 0 and positive selection fitness F(x) = 1 / (1 + J(x))
- Roulette wheel onlooker selection probabilities p_i
- Abandonment limit handling (failed search attempts convention)
- Preservation of best feasible solution across whole run
- Strict evaluation budget tracking (2,000 evaluations)
- Scout ablation mode (scouts disabled)
- Baseline solvers: Random Search and Webster Volume Heuristic
- Manual Trace demonstration (SN=3, 1 complete cycle + controlled scout activation)
"""

import math
import random
import time
from typing import Dict, List, Tuple, Optional
from fitness import (
    TrafficFitnessEvaluator, G_MIN, G_MAX, YELLOW_TIME,
    CYCLE_MIN, CYCLE_MAX, compute_selection_probabilities,
    check_feasibility, calculate_cycle_time
)


class ABCConfig:
    def __init__(self,
                 SN: int = 10,
                 limit: Optional[int] = None,
                 max_evals: int = 2000,
                 dimension: int = 4,
                 enable_scouts: bool = True,
                 seed: int = 42):
        self.SN = SN  # Number of food sources
        self.dimension = dimension  # D = 4 [g_N, g_E, g_S, g_W]
        # Default limit = 5 * D or 15 * D
        self.limit = limit if limit is not None else 5 * dimension
        self.max_evals = max_evals
        self.enable_scouts = enable_scouts
        self.seed = seed


class ABCOptimizer:
    def __init__(self, evaluator: TrafficFitnessEvaluator, config: ABCConfig):
        self.evaluator = evaluator
        self.config = config
        self.rng = random.Random(config.seed)

        # State arrays
        self.population: List[List[float]] = []  # SN food sources
        self.costs: List[float] = []             # J(x) values
        self.fitness: List[float] = []           # F(x) values
        self.trial_counters: List[int] = []      # Failed attempt counters
        self.is_feasible_list: List[bool] = []   # Feasibility flags
        
        # Best feasible solution tracking
        self.best_feasible_x: Optional[List[float]] = None
        self.best_feasible_cost: float = float("inf")
        self.best_feasible_details: Optional[dict] = None
        
        # Best overall solution (fallback if no feasible found)
        self.best_overall_x: Optional[List[float]] = None
        self.best_overall_cost: float = float("inf")

        # History for convergence plotting
        self.history_evals: List[int] = []
        self.history_best_cost: List[float] = []
        
        # Scout metrics
        self.scout_activations = 0

    def _sample_random_solution(self) -> List[float]:
        """Samples a uniform random candidate in [G_MIN, G_MAX]^D."""
        return [round(self.rng.uniform(G_MIN, G_MAX), 1) for _ in range(self.config.dimension)]

    def _update_best(self, x: List[float], res: dict):
        """Updates best feasible and best overall solutions."""
        cost = res["objective_cost_J"]
        if cost < self.best_overall_cost:
            self.best_overall_cost = cost
            self.best_overall_x = list(x)

        if res["is_feasible"] and cost < self.best_feasible_cost:
            self.best_feasible_cost = cost
            self.best_feasible_x = list(x)
            self.best_feasible_details = dict(res)

    def initialize_population(self):
        """Phase 0: Population Initialization and Evaluation."""
        self.population = []
        self.costs = []
        self.fitness = []
        self.trial_counters = [0] * self.config.SN
        self.is_feasible_list = []

        for _ in range(self.config.SN):
            x = self._sample_random_solution()
            res = self.evaluator.evaluate(x)
            self.population.append(x)
            self.costs.append(res["objective_cost_J"])
            self.fitness.append(res["selection_fitness_F"])
            self.is_feasible_list.append(res["is_feasible"])
            self._update_best(x, res)

            self.history_evals.append(self.evaluator.eval_count)
            self.history_best_cost.append(self.best_feasible_cost)

    def _generate_neighbor(self, i: int) -> Tuple[List[float], int, int, float]:
        """
        Generates neighbor v_i using partner k != i and random dimension j:
        v_ij = x_ij + phi_ij * (x_ij - x_kj)
        """
        D = self.config.dimension
        # Select partner k != i
        candidates = [idx for idx in range(self.config.SN) if idx != i]
        k = self.rng.choice(candidates)
        # Select dimension j
        j = self.rng.randint(0, D - 1)
        # phi in [-1, 1]
        phi = self.rng.uniform(-1.0, 1.0)

        v = list(self.population[i])
        v[j] = round(v[j] + phi * (v[j] - self.population[k][j]), 1)
        # Bounds handling
        v[j] = max(G_MIN, min(G_MAX, v[j]))

        return v, k, j, phi

    def employed_phase(self):
        """Phase 1: Employed Bee Phase."""
        for i in range(self.config.SN):
            if self.evaluator.eval_count >= self.config.max_evals:
                break

            v, k, j, phi = self._generate_neighbor(i)
            res_v = self.evaluator.evaluate(v)
            v_cost = res_v["objective_cost_J"]

            # Greedy acceptance
            if v_cost <= self.costs[i]:
                self.population[i] = v
                self.costs[i] = v_cost
                self.fitness[i] = res_v["selection_fitness_F"]
                self.is_feasible_list[i] = res_v["is_feasible"]
                self.trial_counters[i] = 0
                self._update_best(v, res_v)
            else:
                self.trial_counters[i] += 1

            self.history_evals.append(self.evaluator.eval_count)
            self.history_best_cost.append(self.best_feasible_cost)

    def onlooker_phase(self):
        """Phase 2: Onlooker Bee Phase."""
        if self.evaluator.eval_count >= self.config.max_evals:
            return

        # Compute selection probabilities refreshed at start of onlooker phase
        probs = compute_selection_probabilities(self.fitness)

        # SN onlooker attempts
        for _ in range(self.config.SN):
            if self.evaluator.eval_count >= self.config.max_evals:
                break

            # Roulette wheel selection based on p_i
            r = self.rng.random()
            cumul = 0.0
            chosen_i = 0
            for idx, p in enumerate(probs):
                cumul += p
                if r <= cumul:
                    chosen_i = idx
                    break

            v, k, j, phi = self._generate_neighbor(chosen_i)
            res_v = self.evaluator.evaluate(v)
            v_cost = res_v["objective_cost_J"]

            # Greedy acceptance
            if v_cost <= self.costs[chosen_i]:
                self.population[chosen_i] = v
                self.costs[chosen_i] = v_cost
                self.fitness[chosen_i] = res_v["selection_fitness_F"]
                self.is_feasible_list[chosen_i] = res_v["is_feasible"]
                self.trial_counters[chosen_i] = 0
                self._update_best(v, res_v)
            else:
                self.trial_counters[chosen_i] += 1

            self.history_evals.append(self.evaluator.eval_count)
            self.history_best_cost.append(self.best_feasible_cost)

    def scout_phase(self):
        """Phase 3: Scout Bee Phase."""
        if not self.config.enable_scouts:
            return

        if self.evaluator.eval_count >= self.config.max_evals:
            return

        # Find food source with highest trial counter exceeding limit
        max_trial = max(self.trial_counters)
        if max_trial >= self.config.limit:
            idx = self.trial_counters.index(max_trial)

            # Preserve best feasible before scout replacement (already tracked)
            # Replace with random candidate
            new_x = self._sample_random_solution()
            res_new = self.evaluator.evaluate(new_x)
            
            self.population[idx] = new_x
            self.costs[idx] = res_new["objective_cost_J"]
            self.fitness[idx] = res_new["selection_fitness_F"]
            self.is_feasible_list[idx] = res_new["is_feasible"]
            self.trial_counters[idx] = 0
            self.scout_activations += 1
            
            self._update_best(new_x, res_new)
            self.history_evals.append(self.evaluator.eval_count)
            self.history_best_cost.append(self.best_feasible_cost)

    def optimize(self) -> dict:
        """Runs complete ABC search until evaluation budget is exhausted."""
        start_t = time.perf_counter()
        self.initialize_population()

        cycle = 0
        while self.evaluator.eval_count < self.config.max_evals:
            cycle += 1
            self.employed_phase()
            self.onlooker_phase()
            self.scout_phase()

        runtime = round(time.perf_counter() - start_t, 3)

        return {
            "method": "ABC" if self.config.enable_scouts else "ABC_NoScout",
            "SN": self.config.SN,
            "limit": self.config.limit,
            "seed": self.config.seed,
            "evaluations": self.evaluator.eval_count,
            "cycles_completed": cycle,
            "runtime_sec": runtime,
            "best_feasible_cost": self.best_feasible_cost if self.best_feasible_x else None,
            "best_feasible_x": self.best_feasible_x,
            "best_feasible_details": self.best_feasible_details,
            "scout_activations": self.scout_activations,
            "is_feasible": self.best_feasible_x is not None,
            "history_evals": self.history_evals,
            "history_best_cost": self.history_best_cost
        }


# ─── Baseline: Random Search ─────────────────────────────────────────────────
def run_random_search(evaluator: TrafficFitnessEvaluator, max_evals: int = 2000, seed: int = 42) -> dict:
    """Random search baseline operating under the exact same evaluation budget."""
    rng = random.Random(seed)
    start_t = time.perf_counter()
    best_cost = float("inf")
    best_x = None
    best_details = None

    history_evals = []
    history_best_cost = []

    for _ in range(max_evals):
        x = [round(rng.uniform(G_MIN, G_MAX), 1) for _ in range(4)]
        res = evaluator.evaluate(x)
        cost = res["objective_cost_J"]

        if res["is_feasible"] and cost < best_cost:
            best_cost = cost
            best_x = list(x)
            best_details = dict(res)

        history_evals.append(evaluator.eval_count)
        history_best_cost.append(best_cost)

    runtime = round(time.perf_counter() - start_t, 3)
    return {
        "method": "RandomSearch",
        "seed": seed,
        "evaluations": evaluator.eval_count,
        "runtime_sec": runtime,
        "best_feasible_cost": best_cost if best_x else None,
        "best_feasible_x": best_x,
        "best_feasible_details": best_details,
        "is_feasible": best_x is not None,
        "history_evals": history_evals,
        "history_best_cost": history_best_cost
    }


# ─── Baseline: Webster Volume-Proportional Heuristic ─────────────────────────
def run_webster_heuristic(evaluator: TrafficFitnessEvaluator, scenario_name: str = "padat") -> dict:
    """
    Standard traffic engineering heuristic (Webster 1958 / MKJI 1997):
    Allocates green time proportional to arrival flow rates:
    g_i = (y_i / Y) * (C_target - 4 * yellow_time)
    """
    profile = evaluator.simulator.profile
    intervals = profile["arrival_intervals_sec"]
    # Flow rates q_i = 1 / interval
    flows = [1.0 / max(0.5, intervals[d]) for d in ["NORTH", "EAST", "SOUTH", "WEST"]]
    total_flow = sum(flows)

    # Standard urban target cycle = 110s
    c_target = 110.0
    total_yellow = 4.0 * YELLOW_TIME
    effective_green = c_target - total_yellow

    # Proportional green allocation
    x_heur = [round(max(G_MIN, min(G_MAX, (f / total_flow) * effective_green)), 1) for f in flows]
    start_t = time.perf_counter()
    res = evaluator.evaluate(x_heur)
    runtime = round(time.perf_counter() - start_t, 3)

    return {
        "method": "Webster_Heuristic",
        "x": x_heur,
        "evaluations": 1,
        "runtime_sec": runtime,
        "objective_cost_J": res["objective_cost_J"],
        "selection_fitness_F": res["selection_fitness_F"],
        "avg_wait_sec": res["avg_wait_sec"],
        "avg_queue_veh": res["avg_queue_veh"],
        "is_feasible": res["is_feasible"]
    }


# ─── Controlled Manual Trace Demonstration (SN=3, 1 Complete Cycle) ───────────
def run_manual_trace_demonstration(seed: int = 123) -> dict:
    """
    Generates a step-by-step numerical trace of 1 full cycle with 3 food sources (SN=3):
    1. Initialization of 3 food sources
    2. Employed bee phase (3 attempts, partner k, dim j, phi, before/after J, greedy acceptance)
    3. Onlooker bee phase (probabilities p_i, roulette wheel sample, neighbor search, acceptance)
    4. Counters tracking and best feasible preservation
    5. Controlled Scout demonstration (deliberately setting a counter to limit to show replacement)
    """
    trace_log = []
    evaluator = TrafficFitnessEvaluator("padat", horizon_sec=240.0, eval_seed=seed)
    rng = random.Random(seed)

    SN = 3
    D = 4
    limit = 3  # low limit for clear demonstration

    # Step 1: Initialization
    pop = [
        [30.0, 20.0, 30.0, 20.0],
        [25.0, 25.0, 25.0, 25.0],
        [40.0, 15.0, 35.0, 15.0]
    ]
    costs = []
    fitness = []
    counters = [0] * SN

    best_feasible_x = None
    best_feasible_cost = float("inf")

    init_records = []
    for i, x in enumerate(pop):
        res = evaluator.evaluate(x)
        costs.append(res["objective_cost_J"])
        fitness.append(res["selection_fitness_F"])
        if res["is_feasible"] and res["objective_cost_J"] < best_feasible_cost:
            best_feasible_cost = res["objective_cost_J"]
            best_feasible_x = list(x)
        init_records.append({
            "source_idx": i,
            "x": list(x),
            "cost_J": res["objective_cost_J"],
            "fitness_F": res["selection_fitness_F"],
            "counter": counters[i]
        })

    trace_log.append({"step": "INITIALIZATION", "records": init_records, "best_cost": best_feasible_cost})

    # Step 2: Employed Phase (3 attempts)
    employed_records = []
    for i in range(SN):
        # Choose partner k != i
        other_candidates = [idx for idx in range(SN) if idx != i]
        k = rng.choice(other_candidates)
        j = rng.randint(0, D - 1)
        phi = round(rng.uniform(-1.0, 1.0), 3)

        v = list(pop[i])
        v[j] = round(max(G_MIN, min(G_MAX, v[j] + phi * (v[j] - pop[k][j]))), 1)

        res_v = evaluator.evaluate(v)
        v_cost = res_v["objective_cost_J"]
        accepted = (v_cost <= costs[i])

        old_cost = costs[i]
        if accepted:
            pop[i] = v
            costs[i] = v_cost
            fitness[i] = res_v["selection_fitness_F"]
            counters[i] = 0
            if res_v["is_feasible"] and v_cost < best_feasible_cost:
                best_feasible_cost = v_cost
                best_feasible_x = list(v)
        else:
            counters[i] += 1

        employed_records.append({
            "source_idx": i,
            "partner_k": k,
            "dimension_j": j,
            "phi": phi,
            "candidate_v": v,
            "old_cost_J": old_cost,
            "new_cost_J": v_cost,
            "accepted": accepted,
            "new_counter": counters[i]
        })

    trace_log.append({"step": "EMPLOYED_PHASE", "records": employed_records, "best_cost": best_feasible_cost})

    # Step 3: Compute Probabilities
    probs = compute_selection_probabilities(fitness)
    prob_records = [{"source_idx": i, "fitness_F": fitness[i], "probability_p": round(probs[i], 4)} for i in range(SN)]
    trace_log.append({"step": "PROBABILITY_UPDATE", "records": prob_records})

    # Step 4: Onlooker Phase (3 attempts)
    onlooker_records = []
    for att in range(SN):
        # Roulette wheel pick
        r = rng.random()
        cumul = 0.0
        chosen_i = 0
        for idx, p in enumerate(probs):
            cumul += p
            if r <= cumul:
                chosen_i = idx
                break

        other_candidates = [idx for idx in range(SN) if idx != chosen_i]
        k = rng.choice(other_candidates)
        j = rng.randint(0, D - 1)
        phi = round(rng.uniform(-1.0, 1.0), 3)

        v = list(pop[chosen_i])
        v[j] = round(max(G_MIN, min(G_MAX, v[j] + phi * (v[j] - pop[k][j]))), 1)

        res_v = evaluator.evaluate(v)
        v_cost = res_v["objective_cost_J"]
        accepted = (v_cost <= costs[chosen_i])
        old_cost = costs[chosen_i]

        if accepted:
            pop[chosen_i] = v
            costs[chosen_i] = v_cost
            fitness[chosen_i] = res_v["selection_fitness_F"]
            counters[chosen_i] = 0
            if res_v["is_feasible"] and v_cost < best_feasible_cost:
                best_feasible_cost = v_cost
                best_feasible_x = list(v)
        else:
            counters[chosen_i] += 1

        onlooker_records.append({
            "attempt": att + 1,
            "chosen_source": chosen_i,
            "random_r": round(r, 4),
            "partner_k": k,
            "dimension_j": j,
            "phi": phi,
            "candidate_v": v,
            "old_cost_J": old_cost,
            "new_cost_J": v_cost,
            "accepted": accepted,
            "new_counter": counters[chosen_i]
        })

    trace_log.append({"step": "ONLOOKER_PHASE", "records": onlooker_records, "best_cost": best_feasible_cost})

    # Step 5: Controlled Demonstration of Scout Replacement
    # Deliberately set counter for source 0 to limit=3 to demonstrate scout replacement
    counters[0] = limit
    scout_records = []
    for i in range(SN):
        if counters[i] >= limit:
            new_x = [round(rng.uniform(G_MIN, G_MAX), 1) for _ in range(D)]
            res_new = evaluator.evaluate(new_x)
            old_x = list(pop[i])
            old_c = costs[i]
            
            pop[i] = new_x
            costs[i] = res_new["objective_cost_J"]
            fitness[i] = res_new["selection_fitness_F"]
            counters[i] = 0
            if res_new["is_feasible"] and res_new["objective_cost_J"] < best_feasible_cost:
                best_feasible_cost = res_new["objective_cost_J"]
                best_feasible_x = list(new_x)

            scout_records.append({
                "source_idx": i,
                "reason": f"Trial counter reached threshold limit={limit}",
                "abandoned_x": old_x,
                "abandoned_cost_J": old_c,
                "scout_new_x": new_x,
                "scout_new_cost_J": res_new["objective_cost_J"],
                "counter_reset": 0
            })

    trace_log.append({"step": "CONTROLLED_SCOUT_DEMO", "records": scout_records, "best_cost": best_feasible_cost})

    return {
        "trace_log": trace_log,
        "final_best_feasible_x": best_feasible_x,
        "final_best_feasible_cost": best_feasible_cost
    }


if __name__ == "__main__":
    print("=== TESTING MANUAL TRACE DEMONSTRATION ===")
    trace_res = run_manual_trace_demonstration(seed=42)
    for entry in trace_res["trace_log"]:
        print(f"\n--- {entry['step']} ---")
        for rec in entry["records"]:
            print(" ", rec)
        if "best_cost" in entry:
            print(f"  Best Feasible Cost so far: {entry['best_cost']}")

    print("\n=== TESTING SINGLE ABC RUN (2000 EVALS) ===")
    ev = TrafficFitnessEvaluator("padat", horizon_sec=240.0, eval_seed=100)
    cfg = ABCConfig(SN=10, limit=20, max_evals=2000, seed=100)
    optimizer = ABCOptimizer(ev, cfg)
    res = optimizer.optimize()
    print(f"Method: {res['method']}")
    print(f"Evals completed: {res['evaluations']}")
    print(f"Runtime: {res['runtime_sec']}s")
    print(f"Best feasible cost: {res['best_feasible_cost']}")
    print(f"Best feasible x: {res['best_feasible_x']}")
    print(f"Scout activations: {res['scout_activations']}")
