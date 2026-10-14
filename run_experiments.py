"""
run_experiments.py
Automated Runner for Bio-Inspired Computing Week 9 Experiment Matrix:
1. Parameter Study: SN in {10, 30} x limit in {5D, 15D} (4 configs x 10 seeds 0-9 = 40 runs)
2. Final ABC Evaluation: Selected best config on 10 new seeds (100-109 = 10 runs)
3. Random Search Baseline: 10 runs on final seeds (100-109 = 10 runs)
4. Current Practice & Webster Heuristic Evaluations
5. Scout Ablation: Best ABC with scouts disabled (10 runs on seeds 100-109)
6. Sensitivity Analysis: +30% traffic surge and stricter cycle limit (C <= 120s) (5 seeds each)
7. Held-Out Validation: Evaluation on reserved observation session
"""

import os
import csv
import json
import time
import numpy as np
from typing import Dict, List
from fitness import TrafficFitnessEvaluator, G_MIN, G_MAX
from abc_optimizer import ABCOptimizer, ABCConfig, run_random_search, run_webster_heuristic

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
EXPERIMENTS_CSV = os.path.join(RESULTS_DIR, "experiments.csv")
CONVERGENCE_JSON = os.path.join(RESULTS_DIR, "convergence_histories.json")


def run_all_experiments():
    print("================================================================")
    print("   STARTING BIO-INSPIRED COMPUTING WEEK 9 EXPERIMENT SUITE      ")
    print("================================================================")

    all_rows = []
    convergence_histories = {}
    run_counter = 1

    # Evaluation budget
    BUDGET = 2000
    TUNING_SEEDS = list(range(0, 10))       # Seeds 0-9
    FINAL_SEEDS = list(range(100, 110))     # Seeds 100-109
    SENSITIVITY_SEEDS = list(range(100, 105)) # Seeds 100-104

    # ─────────────────────────────────────────────────────────────
    # EXPERIMENT 1: PARAMETER STUDY (40 RUNS)
    # ─────────────────────────────────────────────────────────────
    print("\n[1/6] Running Parameter Study: SN in {10, 30} x limit in {20, 60}...")
    param_configs = [
        {"SN": 10, "limit": 20, "label": "SN10_lim20"},
        {"SN": 10, "limit": 60, "label": "SN10_lim60"},
        {"SN": 30, "limit": 20, "label": "SN30_lim20"},
        {"SN": 30, "limit": 60, "label": "SN30_lim60"},
    ]

    for pcfg in param_configs:
        sn = pcfg["SN"]
        lim = pcfg["limit"]
        lbl = pcfg["label"]
        print(f"  -> Testing {lbl} across 10 tuning seeds (0-9)...")

        for seed in TUNING_SEEDS:
            ev = TrafficFitnessEvaluator(scenario_name="padat", horizon_sec=240.0, eval_seed=seed)
            cfg = ABCConfig(SN=sn, limit=lim, max_evals=BUDGET, seed=seed)
            optimizer = ABCOptimizer(ev, cfg)
            res = optimizer.optimize()

            details = res["best_feasible_details"] or {}
            x_opt = res["best_feasible_x"] or [0, 0, 0, 0]

            row = {
                "run_id": f"RUN-{run_counter:03d}",
                "experiment_group": "Parameter_Study",
                "config_label": lbl,
                "method": "ABC",
                "SN": sn,
                "limit": lim,
                "enable_scouts": True,
                "seed": seed,
                "scenario": "padat",
                "evaluations": res["evaluations"],
                "runtime_sec": res["runtime_sec"],
                "is_feasible": res["is_feasible"],
                "best_feasible_cost": res["best_feasible_cost"],
                "g_north": x_opt[0],
                "g_east":  x_opt[1],
                "g_south": x_opt[2],
                "g_west":  x_opt[3],
                "cycle_time": details.get("cycle_time"),
                "avg_wait_sec": details.get("avg_wait_sec"),
                "avg_queue_veh": details.get("avg_queue_veh"),
                "penalty": details.get("penalty", 0.0),
                "scout_activations": res["scout_activations"]
            }
            all_rows.append(row)

            # Store sampled convergence history
            hist_key = f"Param_{lbl}_seed_{seed}"
            convergence_histories[hist_key] = {
                "evals": res["history_evals"][::20],  # downsample for compact JSON
                "costs": res["history_best_cost"][::20]
            }
            run_counter += 1

    # Determine best configuration from parameter study (based on median cost)
    costs_by_cfg = {}
    for r in all_rows:
        if r["experiment_group"] == "Parameter_Study":
            lbl = r["config_label"]
            costs_by_cfg.setdefault(lbl, []).append(r["best_feasible_cost"])

    median_costs = {k: np.median(v) for k, v in costs_by_cfg.items()}
    best_config_label = min(median_costs, key=median_costs.get)
    print(f"\n>> Parameter study completed. Medians: {median_costs}")
    print(f">> Selected Best Configuration: {best_config_label}")

    best_cfg_params = next(c for c in param_configs if c["label"] == best_config_label)
    best_sn = best_cfg_params["SN"]
    best_limit = best_cfg_params["limit"]

    # ─────────────────────────────────────────────────────────────
    # EXPERIMENT 2: FINAL ABC EVALUATION (10 RUNS, SEEDS 100-109)
    # ─────────────────────────────────────────────────────────────
    print(f"\n[2/6] Running Final ABC Evaluation ({best_config_label}) on 10 unseen seeds (100-109)...")
    for seed in FINAL_SEEDS:
        ev = TrafficFitnessEvaluator(scenario_name="padat", horizon_sec=240.0, eval_seed=seed)
        cfg = ABCConfig(SN=best_sn, limit=best_limit, max_evals=BUDGET, seed=seed)
        optimizer = ABCOptimizer(ev, cfg)
        res = optimizer.optimize()

        details = res["best_feasible_details"] or {}
        x_opt = res["best_feasible_x"] or [0, 0, 0, 0]

        row = {
            "run_id": f"RUN-{run_counter:03d}",
            "experiment_group": "Final_ABC",
            "config_label": best_config_label,
            "method": "ABC",
            "SN": best_sn,
            "limit": best_limit,
            "enable_scouts": True,
            "seed": seed,
            "scenario": "padat",
            "evaluations": res["evaluations"],
            "runtime_sec": res["runtime_sec"],
            "is_feasible": res["is_feasible"],
            "best_feasible_cost": res["best_feasible_cost"],
            "g_north": x_opt[0],
            "g_east":  x_opt[1],
            "g_south": x_opt[2],
            "g_west":  x_opt[3],
            "cycle_time": details.get("cycle_time"),
            "avg_wait_sec": details.get("avg_wait_sec"),
            "avg_queue_veh": details.get("avg_queue_veh"),
            "penalty": details.get("penalty", 0.0),
            "scout_activations": res["scout_activations"]
        }
        all_rows.append(row)

        hist_key = f"Final_ABC_seed_{seed}"
        convergence_histories[hist_key] = {
            "evals": res["history_evals"][::20],
            "costs": res["history_best_cost"][::20]
        }
        run_counter += 1

    # ─────────────────────────────────────────────────────────────
    # EXPERIMENT 3: RANDOM SEARCH BASELINE (10 RUNS, SEEDS 100-109)
    # ─────────────────────────────────────────────────────────────
    print("\n[3/6] Running Random Search Baseline (10 runs, seeds 100-109)...")
    for seed in FINAL_SEEDS:
        ev = TrafficFitnessEvaluator(scenario_name="padat", horizon_sec=240.0, eval_seed=seed)
        res = run_random_search(ev, max_evals=BUDGET, seed=seed)

        details = res["best_feasible_details"] or {}
        x_opt = res["best_feasible_x"] or [0, 0, 0, 0]

        row = {
            "run_id": f"RUN-{run_counter:03d}",
            "experiment_group": "Baseline_RandomSearch",
            "config_label": "RandomSearch",
            "method": "RandomSearch",
            "SN": 0,
            "limit": 0,
            "enable_scouts": False,
            "seed": seed,
            "scenario": "padat",
            "evaluations": res["evaluations"],
            "runtime_sec": res["runtime_sec"],
            "is_feasible": res["is_feasible"],
            "best_feasible_cost": res["best_feasible_cost"],
            "g_north": x_opt[0],
            "g_east":  x_opt[1],
            "g_south": x_opt[2],
            "g_west":  x_opt[3],
            "cycle_time": details.get("cycle_time"),
            "avg_wait_sec": details.get("avg_wait_sec"),
            "avg_queue_veh": details.get("avg_queue_veh"),
            "penalty": details.get("penalty", 0.0),
            "scout_activations": 0
        }
        all_rows.append(row)

        hist_key = f"RandomSearch_seed_{seed}"
        convergence_histories[hist_key] = {
            "evals": res["history_evals"][::20],
            "costs": res["history_best_cost"][::20]
        }
        run_counter += 1

    # ─────────────────────────────────────────────────────────────
    # EXPERIMENT 4: CURRENT PRACTICE & WEBSTER HEURISTIC
    # ─────────────────────────────────────────────────────────────
    print("\n[4/6] Evaluating Current Practice & Webster Volume-Proportional Heuristic...")
    ev_curr = TrafficFitnessEvaluator(scenario_name="padat", horizon_sec=240.0, eval_seed=42)
    res_curr = ev_curr.evaluate([25.0, 25.0, 25.0, 25.0])
    row_curr = {
        "run_id": f"RUN-{run_counter:03d}",
        "experiment_group": "Current_Practice",
        "config_label": "Current_Practice_Static",
        "method": "CurrentPractice",
        "SN": 0,
        "limit": 0,
        "enable_scouts": False,
        "seed": 42,
        "scenario": "padat",
        "evaluations": 1,
        "runtime_sec": 0.005,
        "is_feasible": res_curr["is_feasible"],
        "best_feasible_cost": res_curr["objective_cost_J"],
        "g_north": 25.0,
        "g_east":  25.0,
        "g_south": 25.0,
        "g_west":  25.0,
        "cycle_time": res_curr["cycle_time"],
        "avg_wait_sec": res_curr["avg_wait_sec"],
        "avg_queue_veh": res_curr["avg_queue_veh"],
        "penalty": res_curr["penalty"],
        "scout_activations": 0
    }
    all_rows.append(row_curr)
    run_counter += 1

    # Webster Heuristic
    res_webster = run_webster_heuristic(ev_curr, scenario_name="padat")
    row_webster = {
        "run_id": f"RUN-{run_counter:03d}",
        "experiment_group": "Webster_Heuristic",
        "config_label": "Webster_Heuristic",
        "method": "WebsterHeuristic",
        "SN": 0,
        "limit": 0,
        "enable_scouts": False,
        "seed": 42,
        "scenario": "padat",
        "evaluations": 1,
        "runtime_sec": res_webster["runtime_sec"],
        "is_feasible": res_webster["is_feasible"],
        "best_feasible_cost": res_webster["objective_cost_J"],
        "g_north": res_webster["x"][0],
        "g_east":  res_webster["x"][1],
        "g_south": res_webster["x"][2],
        "g_west":  res_webster["x"][3],
        "cycle_time": sum(res_webster["x"]) + 12.0,
        "avg_wait_sec": res_webster["avg_wait_sec"],
        "avg_queue_veh": res_webster["avg_queue_veh"],
        "penalty": 0.0,
        "scout_activations": 0
    }
    all_rows.append(row_webster)
    run_counter += 1

    # ─────────────────────────────────────────────────────────────
    # EXPERIMENT 5: SCOUT ABLATION (10 RUNS, SEEDS 100-109)
    # ─────────────────────────────────────────────────────────────
    print(f"\n[5/6] Running Scout Ablation (ABC without Scouts, seeds 100-109)...")
    for seed in FINAL_SEEDS:
        ev = TrafficFitnessEvaluator(scenario_name="padat", horizon_sec=240.0, eval_seed=seed)
        cfg = ABCConfig(SN=best_sn, limit=best_limit, max_evals=BUDGET, enable_scouts=False, seed=seed)
        optimizer = ABCOptimizer(ev, cfg)
        res = optimizer.optimize()

        details = res["best_feasible_details"] or {}
        x_opt = res["best_feasible_x"] or [0, 0, 0, 0]

        row = {
            "run_id": f"RUN-{run_counter:03d}",
            "experiment_group": "Scout_Ablation",
            "config_label": f"{best_config_label}_NoScout",
            "method": "ABC_NoScout",
            "SN": best_sn,
            "limit": best_limit,
            "enable_scouts": False,
            "seed": seed,
            "scenario": "padat",
            "evaluations": res["evaluations"],
            "runtime_sec": res["runtime_sec"],
            "is_feasible": res["is_feasible"],
            "best_feasible_cost": res["best_feasible_cost"],
            "g_north": x_opt[0],
            "g_east":  x_opt[1],
            "g_south": x_opt[2],
            "g_west":  x_opt[3],
            "cycle_time": details.get("cycle_time"),
            "avg_wait_sec": details.get("avg_wait_sec"),
            "avg_queue_veh": details.get("avg_queue_veh"),
            "penalty": details.get("penalty", 0.0),
            "scout_activations": 0
        }
        all_rows.append(row)

        hist_key = f"NoScout_seed_{seed}"
        convergence_histories[hist_key] = {
            "evals": res["history_evals"][::20],
            "costs": res["history_best_cost"][::20]
        }
        run_counter += 1

    # ─────────────────────────────────────────────────────────────
    # EXPERIMENT 6: SENSITIVITY & FAILURE ANALYSIS (10 RUNS)
    # ─────────────────────────────────────────────────────────────
    print("\n[6/6] Running Sensitivity Analysis (+30% traffic surge & stricter C <= 120s)...")
    # Sensitivity A: Traffic surge (+30% arrival volume, lower inter-arrival intervals)
    for seed in SENSITIVITY_SEEDS:
        ev = TrafficFitnessEvaluator(scenario_name="padat", horizon_sec=240.0, eval_seed=seed)
        # Shift arrival intervals by -23% (equivalent to +30% volume)
        for d in ev.simulator.arrival_intervals:
            ev.simulator.arrival_intervals[d] = round(ev.simulator.arrival_intervals[d] / 1.30, 2)

        cfg = ABCConfig(SN=best_sn, limit=best_limit, max_evals=BUDGET, seed=seed)
        optimizer = ABCOptimizer(ev, cfg)
        res = optimizer.optimize()

        details = res["best_feasible_details"] or {}
        x_opt = res["best_feasible_x"] or [0, 0, 0, 0]

        row = {
            "run_id": f"RUN-{run_counter:03d}",
            "experiment_group": "Sensitivity_TrafficSurge_Plus30",
            "config_label": f"{best_config_label}_Surge30",
            "method": "ABC",
            "SN": best_sn,
            "limit": best_limit,
            "enable_scouts": True,
            "seed": seed,
            "scenario": "padat_surge_30pct",
            "evaluations": res["evaluations"],
            "runtime_sec": res["runtime_sec"],
            "is_feasible": res["is_feasible"],
            "best_feasible_cost": res["best_feasible_cost"],
            "g_north": x_opt[0],
            "g_east":  x_opt[1],
            "g_south": x_opt[2],
            "g_west":  x_opt[3],
            "cycle_time": details.get("cycle_time"),
            "avg_wait_sec": details.get("avg_wait_sec"),
            "avg_queue_veh": details.get("avg_queue_veh"),
            "penalty": details.get("penalty", 0.0),
            "scout_activations": res["scout_activations"]
        }
        all_rows.append(row)
        run_counter += 1

    # Sensitivity B: Stricter cycle constraint (C <= 120s instead of 180s)
    # We enforce extra penalty if C > 120.0
    for seed in SENSITIVITY_SEEDS:
        ev = TrafficFitnessEvaluator(scenario_name="padat", horizon_sec=240.0, eval_seed=seed)
        
        # Monkey patch evaluate method to enforce stricter C <= 120
        orig_evaluate = ev.evaluate
        def strict_evaluate(x):
            out = orig_evaluate(x)
            c = sum(x) + 12.0
            if c > 120.0:
                strict_pen = 50.0 * ((c - 120.0) ** 2)
                out["penalty"] += strict_pen
                out["objective_cost_J"] += strict_pen
                out["is_feasible"] = False
                out["violations"].append(f"Cycle time {c:.1f}s > Stricter limit (120s)")
                out["selection_fitness_F"] = 1.0 / (1.0 + max(0.0, out["objective_cost_J"]))
            return out

        ev.evaluate = strict_evaluate

        cfg = ABCConfig(SN=best_sn, limit=best_limit, max_evals=BUDGET, seed=seed)
        optimizer = ABCOptimizer(ev, cfg)
        res = optimizer.optimize()

        details = res["best_feasible_details"] or {}
        x_opt = res["best_feasible_x"] or [0, 0, 0, 0]

        row = {
            "run_id": f"RUN-{run_counter:03d}",
            "experiment_group": "Sensitivity_StrictCycle_120s",
            "config_label": f"{best_config_label}_StrictCycle120",
            "method": "ABC",
            "SN": best_sn,
            "limit": best_limit,
            "enable_scouts": True,
            "seed": seed,
            "scenario": "padat_strict_120s",
            "evaluations": res["evaluations"],
            "runtime_sec": res["runtime_sec"],
            "is_feasible": res["is_feasible"],
            "best_feasible_cost": res["best_feasible_cost"],
            "g_north": x_opt[0],
            "g_east":  x_opt[1],
            "g_south": x_opt[2],
            "g_west":  x_opt[3],
            "cycle_time": details.get("cycle_time"),
            "avg_wait_sec": details.get("avg_wait_sec"),
            "avg_queue_veh": details.get("avg_queue_veh"),
            "penalty": details.get("penalty", 0.0),
            "scout_activations": res["scout_activations"]
        }
        all_rows.append(row)
        run_counter += 1

    # ─────────────────────────────────────────────────────────────
    # HELD-OUT VALIDATION
    # ─────────────────────────────────────────────────────────────
    print("\n[Held-Out Validation] Testing Final Recommended Solution on Reserved Data (Session 3 Held-Out)...")
    # Take median best solution from Final ABC
    final_abc_rows = [r for r in all_rows if r["experiment_group"] == "Final_ABC"]
    best_final_row = min(final_abc_rows, key=lambda r: r["best_feasible_cost"])
    rec_x = [best_final_row["g_north"], best_final_row["g_east"], best_final_row["g_south"], best_final_row["g_west"]]

    ev_val = TrafficFitnessEvaluator(scenario_name="validation", horizon_sec=240.0, eval_seed=999)
    val_curr = ev_val.evaluate([25.0, 25.0, 25.0, 25.0])
    val_opt = ev_val.evaluate(rec_x)

    print(f"  Recommended Timing x*: {rec_x} (Cycle: {sum(rec_x)+12:.1f}s)")
    print(f"  Current Practice on Held-Out Validation: Cost = {val_curr['objective_cost_J']:.2f}, Wait = {val_curr['avg_wait_sec']:.2f}s, Queue = {val_curr['avg_queue_veh']:.2f}")
    print(f"  ABC Optimal on Held-Out Validation:      Cost = {val_opt['objective_cost_J']:.2f}, Wait = {val_opt['avg_wait_sec']:.2f}s, Queue = {val_opt['avg_queue_veh']:.2f}")
    improvement_pct = ((val_curr['objective_cost_J'] - val_opt['objective_cost_J']) / val_curr['objective_cost_J']) * 100
    print(f"  Validation Improvement: {improvement_pct:.2f}% reduction in objective cost!")

    row_val = {
        "run_id": f"RUN-{run_counter:03d}",
        "experiment_group": "HeldOut_Validation",
        "config_label": "HeldOut_Validation",
        "method": "ABC_Optimal_vs_Current",
        "SN": best_sn,
        "limit": best_limit,
        "enable_scouts": True,
        "seed": 999,
        "scenario": "validation_heldout",
        "evaluations": 1,
        "runtime_sec": 0.005,
        "is_feasible": val_opt["is_feasible"],
        "best_feasible_cost": val_opt["objective_cost_J"],
        "g_north": rec_x[0],
        "g_east":  rec_x[1],
        "g_south": rec_x[2],
        "g_west":  rec_x[3],
        "cycle_time": val_opt["cycle_time"],
        "avg_wait_sec": val_opt["avg_wait_sec"],
        "avg_queue_veh": val_opt["avg_queue_veh"],
        "penalty": val_opt["penalty"],
        "scout_activations": 0
    }
    all_rows.append(row_val)

    # ─────────────────────────────────────────────────────────────
    # SAVE EXPERIMENTAL DATA TO CSV & JSON
    # ─────────────────────────────────────────────────────────────
    fieldnames = list(all_rows[0].keys())
    with open(EXPERIMENTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)

    with open(CONVERGENCE_JSON, "w", encoding="utf-8") as f:
        json.dump(convergence_histories, f, indent=2)

    print(f"\n================================================================")
    print(f"  ALL {len(all_rows)} EXPERIMENTAL RUNS COMPLETED SUCCESSFULLY! ")
    print(f"  CSV Saved:  {EXPERIMENTS_CSV}")
    print(f"  JSON Saved: {CONVERGENCE_JSON}")
    print(f"================================================================")


if __name__ == "__main__":
    run_all_experiments()
