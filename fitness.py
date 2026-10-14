"""
fitness.py
Mathematical Formulation, Objective Cost Function J(x), Selection Fitness F(x),
Traceability Table, and 5-Case Fitness Audit.

Complies strictly with Bio-Inspired Computing Week 9 Assignment:
- Minimizes J(x) >= 0 in seconds equivalent
- Selection fitness F(x) = 1 / (1 + J(x)) > 0
- Normalized onlooker probabilities p_i = F(x_i) / sum(F)
- Explicit handling of hard bounds and cycle constraints
- Pre-optimization 5-case fitness audit and ranking verification
"""

import math
from typing import Dict, List, Tuple
from headless_sim import FastIntersectionSimulator

# Bounds and Parameters (Standard MKJI / Dishub Urban Intersection)
G_MIN = 10.0   # minimum green duration per phase (seconds)
G_MAX = 60.0   # maximum green duration per phase (seconds)
YELLOW_TIME = 3.0  # transition yellow time per phase (seconds)
CYCLE_MIN = 60.0   # minimum cycle time C (seconds)
CYCLE_MAX = 180.0  # maximum cycle time C (seconds)

# Weights in J(x)
ALPHA_QUEUE = 2.0     # weight converting 1 vehicle queue to 2.0s equivalent waiting penalty
PENALTY_BOUND = 50.0  # penalty weight for out-of-bound green duration
PENALTY_CYCLE = 25.0  # penalty weight for cycle time violations


def calculate_cycle_time(x: List[float]) -> float:
    """Cycle time C = sum(g_i) + 4 * yellow_time"""
    return sum(x) + 4.0 * YELLOW_TIME


def check_feasibility(x: List[float]) -> Tuple[bool, List[str]]:
    """
    Checks whether candidate decision x satisfies all hard constraints.
    Returns (is_feasible, list_of_violations).
    """
    violations = []
    for i, (g, direction) in enumerate(zip(x, ["NORTH", "EAST", "SOUTH", "WEST"])):
        if g < G_MIN:
            violations.append(f"{direction} green {g:.1f}s < G_MIN ({G_MIN}s)")
        elif g > G_MAX:
            violations.append(f"{direction} green {g:.1f}s > G_MAX ({G_MAX}s)")

    c = calculate_cycle_time(x)
    if c < CYCLE_MIN:
        violations.append(f"Cycle time {c:.1f}s < CYCLE_MIN ({CYCLE_MIN}s)")
    elif c > CYCLE_MAX:
        violations.append(f"Cycle time {c:.1f}s > CYCLE_MAX ({CYCLE_MAX}s)")

    is_feasible = (len(violations) == 0)
    return is_feasible, violations


def compute_hard_penalty(x: List[float]) -> float:
    """Quadratic penalty for constraint violations."""
    pen = 0.0
    for g in x:
        if g < G_MIN:
            pen += PENALTY_BOUND * ((G_MIN - g) ** 2)
        elif g > G_MAX:
            pen += PENALTY_BOUND * ((g - G_MAX) ** 2)

    c = calculate_cycle_time(x)
    if c < CYCLE_MIN:
        pen += PENALTY_CYCLE * ((CYCLE_MIN - c) ** 2)
    elif c > CYCLE_MAX:
        pen += PENALTY_CYCLE * ((c - CYCLE_MAX) ** 2)

    return pen


class TrafficFitnessEvaluator:
    """
    Evaluator for traffic light timing x = [g_N, g_E, g_S, g_W].
    Computes objective cost J(x), components, selection fitness F(x), and selection probabilities.
    """

    def __init__(self, scenario_name: str = "padat", horizon_sec: float = 240.0, eval_seed: int = 42):
        self.scenario_name = scenario_name
        self.horizon_sec = horizon_sec
        self.eval_seed = eval_seed
        self.simulator = FastIntersectionSimulator(scenario_name, horizon_sec=horizon_sec)
        self.eval_count = 0

    def evaluate(self, x: List[float]) -> dict:
        """
        Evaluates solution x.
        Returns full breakdown of objective terms, constraint violations, and selection fitness.
        """
        self.eval_count += 1
        x_clean = [float(v) for v in x]
        is_feasible, violations = check_feasibility(x_clean)
        penalty = compute_hard_penalty(x_clean)

        # Run simulation
        sim_res = self.simulator.run_simulation(x_clean, seed=self.eval_seed)
        avg_wait = sim_res["avg_wait_time_sec"]
        avg_queue = sim_res["avg_queue_veh"]

        # Objective cost to minimize J(x)
        # J(x) = W_avg + alpha * Q_avg + Penalty
        j_cost = avg_wait + ALPHA_QUEUE * avg_queue + penalty

        # Selection fitness for ABC onlookers F(x) = 1 / (1 + J(x))
        f_fitness = 1.0 / (1.0 + max(0.0, j_cost))

        return {
            "x": x_clean,
            "cycle_time": sim_res["cycle_time"],
            "avg_wait_sec": avg_wait,
            "avg_queue_veh": avg_queue,
            "penalty": round(penalty, 2),
            "objective_cost_J": round(j_cost, 4),
            "selection_fitness_F": round(f_fitness, 6),
            "is_feasible": is_feasible,
            "violations": violations,
            "total_passed": sim_res["total_passed"],
            "total_arrivals": sim_res["total_arrivals"],
            "throughput_ratio": sim_res["throughput_ratio"]
        }


def compute_selection_probabilities(fitness_values: List[float]) -> List[float]:
    """
    Computes onlooker selection probabilities:
    p_i = F(x_i) / sum(F(x_k))
    Confirms probabilities are finite, nonnegative, and sum to 1.
    """
    total_f = sum(fitness_values)
    if total_f <= 0.0 or math.isnan(total_f):
        # Fallback uniform
        n = len(fitness_values)
        return [1.0 / n] * n

    probs = [f / total_f for f in fitness_values]
    # Small numerical normalization check
    s_probs = sum(probs)
    return [p / s_probs for p in probs]


# ─── Traceability Table ────────────────────────────────────────────────────────
TRACEABILITY_TABLE = [
    {
        "term": "g_i (g_N, g_E, g_S, g_W)",
        "definition": "Durasi sinyal lampu hijau per lengan (detik)",
        "unit": "detik (s)",
        "supporting_records": "REC-01 s/d REC-36 (catatan siklus eksisting)",
        "assumption": "Hanya 1 lengan hijau sekaligus (4-fase) untuk eliminasi total konflik persimpangan.",
        "justification": "Standar keselamatan MKJI (Manual Kapasitas Jalan Indonesia) 1997."
    },
    {
        "term": "W_avg (Average Delay)",
        "definition": "Rata-rata waktu tunggu terakumulasi per kendaraan di persimpangan",
        "unit": "detik/kendaraan",
        "supporting_records": "Kolom avg_wait_time_sec di observations.json",
        "assumption": "Kendaraan berhenti mengakumulasi 1 detik penundaan per detik berada di antrean.",
        "justification": "Indikator kinerja utama Level of Service (LOS) persimpangan menurut Transportation Research Board (HCM)."
    },
    {
        "term": "Q_avg (Average Queue)",
        "definition": "Rata-rata jumlah kendaraan yang terhenti di semua lajur pendekat",
        "unit": "kendaraan (veh)",
        "supporting_records": "Kolom queue_north, queue_east, queue_south, queue_west",
        "assumption": "Antrean terdistribusi di seluruh lajur masuk yang tersedia.",
        "justification": "Mencegah antrean panjang meluap (spillback) yang dapat memblokir akses ke pertokoan dan persimpangan sebelumnya."
    },
    {
        "term": "alpha (Bobot Antrean)",
        "definition": "Faktor konversi bobot antrean terhadap waktu tunggu",
        "unit": "detik/kendaraan (alpha = 2.0)",
        "supporting_records": "Analisis regresi empiris data observasi Sesi Padat",
        "assumption": "1 antrean kendaraan memberi dampak friksi sistemik setara 2 detik penundaan tambahan.",
        "justification": "Menyelaraskan satuan antrean ke dimensi biaya waktu tunggu (detik)."
    },
    {
        "term": "Penalty_hard",
        "definition": "Fungsi penalti kuadratik atas pelanggaran batas g_i dan siklus C",
        "unit": "skor penalti (dimensionless ekuivalen biaya)",
        "supporting_records": "Batas izin teknis Dishub & MKJI (10s <= g_i <= 60s, 60s <= C <= 180s)",
        "assumption": "Pelanggaran hard constraint tidak dapat diterima di lapangan.",
        "justification": "Memastikan lebah pengamat (onlookers) mengabaikan solusi non-feasible (F -> 0)."
    },
    {
        "term": "F(x) = 1 / (1 + J(x))",
        "definition": "Fitness seleksi positif untuk pemilihan sumber makanan oleh lebah Onlooker",
        "unit": "positif dimensionless (0, 1]",
        "supporting_records": "Formulasi kanonikal Karaboga (2005) untuk minimasi non-negatif",
        "assumption": "Biaya J(x) selalu non-negatif sehingga pembagi selalu >= 1.",
        "justification": "Membalikkan biaya menjadi fitness positif: biaya lebih kecil menghasilkan probabilitas seleksi lebih besar."
    }
]


# ─── Fitness Audit (5 Candidate Decisions) ────────────────────────────────────
FITNESS_AUDIT_CASES = [
    {
        "id": "CASE-1",
        "name": "Praktik Eksisting (Current Practice)",
        "x": [25.0, 25.0, 25.0, 25.0],
        "expected_trait": "Layak, biaya sedang (durasi seragam tidak adaptif terhadap arus arteri)",
        "expected_rank": 2
    },
    {
        "id": "CASE-2",
        "name": "Peningkatan Masuk Akal (Plausible Improvement)",
        "x": [36.0, 16.0, 34.0, 14.0],
        "expected_trait": "Layak, biaya terendah (hijau lebih panjang untuk arteri Utara & Selatan yang padat)",
        "expected_rank": 1
    },
    {
        "id": "CASE-3",
        "name": "Keputusan Sangat Buruk (Clearly Poor)",
        "x": [12.0, 48.0, 12.0, 48.0],
        "expected_trait": "Layak tapi biaya tinggi (terbalik: hijau panjang untuk jalan sepi, jalan padat tersumbat)",
        "expected_rank": 3
    },
    {
        "id": "CASE-4",
        "name": "Kasus Batas (Boundary Case)",
        "x": [10.0, 10.0, 10.0, 10.0],
        "expected_trait": "Batas minimum g_i, melanggar batas siklus minimum C=52s < 60s, mendapat penalti",
        "expected_rank": 4
    },
    {
        "id": "CASE-5",
        "name": "Kasus Tidak Layak (Infeasible Case)",
        "x": [5.0, 70.0, 5.0, 75.0],
        "expected_trait": "Melanggar batas bawah (5s < 10s) dan batas atas (70s, 75s > 60s), penalti sangat besar",
        "expected_rank": 5
    }
]


def run_fitness_audit(scenario_name: str = "padat") -> List[dict]:
    """
    Executes the 5 audit cases, calculates objective components and F(x),
    ranks them by objective cost J(x), and compares against expected ranking.
    """
    evaluator = TrafficFitnessEvaluator(scenario_name=scenario_name, horizon_sec=240.0, eval_seed=42)
    audit_results = []

    for c in FITNESS_AUDIT_CASES:
        res = evaluator.evaluate(c["x"])
        row = {
            "case_id": c["id"],
            "name": c["name"],
            "x": c["x"],
            "cycle_time": res["cycle_time"],
            "avg_wait_sec": res["avg_wait_sec"],
            "avg_queue_veh": res["avg_queue_veh"],
            "penalty": res["penalty"],
            "cost_J": res["objective_cost_J"],
            "fitness_F": res["selection_fitness_F"],
            "is_feasible": res["is_feasible"],
            "violations": res["violations"],
            "expected_rank": c["expected_rank"]
        }
        audit_results.append(row)

    # Sort by computed J cost ascending (Rank 1 = lowest cost / best)
    audit_results.sort(key=lambda r: r["cost_J"])
    for rank, r in enumerate(audit_results, start=1):
        r["computed_rank"] = rank
        r["rank_match"] = (r["computed_rank"] == r["expected_rank"])

    return audit_results


if __name__ == "__main__":
    print("=== RUNNING PRE-OPTIMIZATION FITNESS AUDIT (5 CASES) ===")
    results = run_fitness_audit(scenario_name="padat")
    print(f"{'Rank':<5} {'Case ID':<8} {'Name':<35} {'Cycle':<6} {'Wait(s)':<8} {'Queue':<7} {'Pen':<8} {'J(x)':<10} {'F(x)':<10} {'Feas':<5} {'Rank Match'}")
    print("-" * 120)
    for r in results:
        feas_str = "YES" if r["is_feasible"] else "NO"
        match_str = "OK" if r["rank_match"] else f"MISMATCH (Exp: {r['expected_rank']})"
        print(f"{r['computed_rank']:<5} {r['case_id']:<8} {r['name']:<35} {r['cycle_time']:<6.1f} {r['avg_wait_sec']:<8.2f} {r['avg_queue_veh']:<7.2f} {r['penalty']:<8.1f} {r['cost_J']:<10.4f} {r['fitness_F']:<10.6f} {feas_str:<5} {match_str}")
