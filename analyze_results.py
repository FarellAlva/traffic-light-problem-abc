"""
analyze_results.py
Statistical Analysis and Publication-Quality Visualizations
Compliant with Bio-Inspired Computing Week 9 Assignment requirements:
- Reports Median, Interquartile Range (IQR), Best, Worst, Feasibility Rate, and Runtime
- Plots best feasible objective vs evaluation count with median curves and IQR shaded bands
- Final-run distribution comparisons (boxplots) across algorithms
- Sensitivity & failure analysis charts
- Before and after comparison on held-out validation session
"""

import os
import csv
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
FIGURES_DIR = os.path.join(RESULTS_DIR, "figures")
TABLES_DIR = os.path.join(RESULTS_DIR, "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

EXPERIMENTS_CSV = os.path.join(RESULTS_DIR, "experiments.csv")
CONVERGENCE_JSON = os.path.join(RESULTS_DIR, "convergence_histories.json")


def load_experiment_data():
    """Loads experiments.csv into list of dicts with appropriate data types."""
    rows = []
    with open(EXPERIMENTS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["evaluations"] = int(r["evaluations"])
            r["runtime_sec"] = float(r["runtime_sec"])
            r["is_feasible"] = (r["is_feasible"].lower() == "true")
            r["best_feasible_cost"] = float(r["best_feasible_cost"]) if r["best_feasible_cost"] else None
            r["g_north"] = float(r["g_north"])
            r["g_east"] = float(r["g_east"])
            r["g_south"] = float(r["g_south"])
            r["g_west"] = float(r["g_west"])
            r["cycle_time"] = float(r["cycle_time"]) if r["cycle_time"] else 0.0
            r["avg_wait_sec"] = float(r["avg_wait_sec"]) if r["avg_wait_sec"] else 0.0
            r["avg_queue_veh"] = float(r["avg_queue_veh"]) if r["avg_queue_veh"] else 0.0
            r["penalty"] = float(r["penalty"]) if r["penalty"] else 0.0
            r["scout_activations"] = int(r["scout_activations"]) if r["scout_activations"] else 0
            rows.append(r)
    return rows


def compute_group_statistics(rows: list, group_key: str = "config_label") -> dict:
    """Computes median, IQR, best, worst, feasibility rate, runtime for each group."""
    groups = {}
    for r in rows:
        lbl = r[group_key]
        groups.setdefault(lbl, []).append(r)

    stats = {}
    for lbl, items in groups.items():
        costs = [x["best_feasible_cost"] for x in items if x["is_feasible"] and x["best_feasible_cost"] is not None]
        feas_count = sum(1 for x in items if x["is_feasible"])
        n_total = len(items)
        runtimes = [x["runtime_sec"] for x in items]
        waits = [x["avg_wait_sec"] for x in items if x["avg_wait_sec"] > 0]
        queues = [x["avg_queue_veh"] for x in items if x["avg_queue_veh"] > 0]
        cycles = [x["cycle_time"] for x in items if x["cycle_time"] > 0]
        scouts = [x["scout_activations"] for x in items]

        if costs:
            q25, q50, q75 = np.percentile(costs, [25, 50, 75])
            iqr = q75 - q25
            best_val = min(costs)
            worst_val = max(costs)
        else:
            q25 = q50 = q75 = iqr = best_val = worst_val = None

        stats[lbl] = {
            "group_label": lbl,
            "sample_size": n_total,
            "feasibility_rate_pct": round((feas_count / n_total) * 100, 1),
            "infeasible_count": n_total - feas_count,
            "best_cost": round(best_val, 4) if best_val is not None else None,
            "median_cost": round(q50, 4) if q50 is not None else None,
            "q25_cost": round(q25, 4) if q25 is not None else None,
            "q75_cost": round(q75, 4) if q75 is not None else None,
            "iqr_cost": round(iqr, 4) if iqr is not None else None,
            "worst_cost": round(worst_val, 4) if worst_val is not None else None,
            "mean_runtime_sec": round(float(np.mean(runtimes)), 3),
            "mean_wait_sec": round(float(np.mean(waits)), 2) if waits else 0.0,
            "mean_queue_veh": round(float(np.mean(queues)), 2) if queues else 0.0,
            "mean_cycle_sec": round(float(np.mean(cycles)), 1) if cycles else 0.0,
            "mean_scout_activations": round(float(np.mean(scouts)), 1) if scouts else 0.0,
        }
    return stats


def plot_convergence_curves(convergence_data: dict, current_practice_cost: float, webster_cost: float):
    """
    Plots best feasible objective vs evaluation count with median curves and IQR shaded bands.
    Compares Final ABC, Random Search, and Scout Ablation.
    """
    plt.figure(figsize=(10, 6), dpi=300)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Categories to plot
    categories = [
        {"prefix": "Final_ABC_seed_", "label": "Final ABC (Employed + Onlooker + Scout)", "color": "#007acc", "linestyle": "-"},
        {"prefix": "NoScout_seed_", "label": "ABC without Scouts (Scout Ablation)", "color": "#ff7f0e", "linestyle": "--"},
        {"prefix": "RandomSearch_seed_", "label": "Random Search Baseline", "color": "#7f7f7f", "linestyle": ":"},
    ]

    for cat in categories:
        prefix = cat["prefix"]
        runs = [v for k, v in convergence_data.items() if k.startswith(prefix)]
        if not runs:
            continue

        # Find common evaluation points
        eval_points = runs[0]["evals"]
        # Matrix of costs: (num_runs, num_points)
        cost_matrix = []
        for r in runs:
            # Interpolate or slice to length of eval_points
            costs = r["costs"][:len(eval_points)]
            cost_matrix.append(costs)

        cost_matrix = np.array(cost_matrix)
        median_curve = np.median(cost_matrix, axis=0)
        q25_curve = np.percentile(cost_matrix, 25, axis=0)
        q75_curve = np.percentile(cost_matrix, 75, axis=0)

        plt.plot(eval_points, median_curve, label=cat["label"], color=cat["color"], linestyle=cat["linestyle"], linewidth=2.2)
        plt.fill_between(eval_points, q25_curve, q75_curve, color=cat["color"], alpha=0.18)

    # Reference lines
    plt.axhline(current_practice_cost, color="#d62728", linestyle="-.", linewidth=1.8, label=f"Praktik Eksisting (J = {current_practice_cost:.1f})")
    plt.axhline(webster_cost, color="#2ca02c", linestyle="--", linewidth=1.8, label=f"Heuristik Webster (J = {webster_cost:.1f})")

    plt.title("Kurva Konvergensi Nilai Objektif Terbaik vs Jumlah Evaluasi\n(Median dan Pita Antarkuartil / IQR 10 Seed)", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Jumlah Evaluasi Fungsi Objektif (Budget = 2.000)", fontsize=11)
    plt.ylabel("Biaya Objektif Terbaik Feasible J(x) [Detik Ekuivalen]", fontsize=11)
    plt.xlim(0, 2000)
    plt.legend(frameon=True, fontsize=10, loc="upper right")
    plt.tight_layout()

    out_path = os.path.join(FIGURES_DIR, "convergence_comparison.png")
    plt.savefig(out_path)
    plt.close()
    print(f"[analyze] Saved convergence plot: {out_path}")


def plot_boxplot_param_study(rows: list):
    """Boxplot comparing the 4 parameter configurations (SN x limit)."""
    param_rows = [r for r in rows if r["experiment_group"] == "Parameter_Study"]
    configs = ["SN10_lim20", "SN10_lim60", "SN30_lim20", "SN30_lim60"]
    data_by_cfg = [
        [r["best_feasible_cost"] for r in param_rows if r["config_label"] == c and r["is_feasible"]]
        for c in configs
    ]

    plt.figure(figsize=(9, 5.5), dpi=300)
    bplot = plt.boxplot(data_by_cfg, tick_labels=[
        "SN=10, limit=20\n(limit=5D)",
        "SN=10, limit=60\n(limit=15D)",
        "SN=30, limit=20\n(limit=5D)",
        "SN=30, limit=60\n(limit=15D)"
    ], patch_artist=True, medianprops=dict(color="#d62728", linewidth=2.0))

    colors = ["#cce5ff", "#99ccff", "#cce5ff", "#99ccff"]
    for patch, color in zip(bplot['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_edgecolor("#004085")

    plt.title("Studi Parameter ABC: Pengaruh Ukuran Populasi (SN) dan Batas Abandonment (limit)\n(10 Seed per Konfigurasi)", fontsize=12, fontweight="bold", pad=12)
    plt.ylabel("Biaya Objektif Terbaik J(x)", fontsize=11)
    plt.xlabel("Konfigurasi Parameter", fontsize=11)
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    out_path = os.path.join(FIGURES_DIR, "boxplot_param_study.png")
    plt.savefig(out_path)
    plt.close()
    print(f"[analyze] Saved parameter boxplot: {out_path}")


def plot_boxplot_final_vs_baselines(rows: list):
    """Boxplot comparing final ABC against baselines and ablation."""
    final_abc = [r["best_feasible_cost"] for r in rows if r["experiment_group"] == "Final_ABC" and r["is_feasible"]]
    no_scout = [r["best_feasible_cost"] for r in rows if r["experiment_group"] == "Scout_Ablation" and r["is_feasible"]]
    random_search = [r["best_feasible_cost"] for r in rows if r["experiment_group"] == "Baseline_RandomSearch" and r["is_feasible"]]

    curr_row = next(r for r in rows if r["experiment_group"] == "Current_Practice")
    webster_row = next(r for r in rows if r["experiment_group"] == "Webster_Heuristic")

    plt.figure(figsize=(9, 5.5), dpi=300)
    data = [final_abc, no_scout, random_search]
    labels = ["Final ABC\n(Lengkap)", "ABC No-Scout\n(Ablasi)", "Random Search\n(Baseline)"]

    bplot = plt.boxplot(data, tick_labels=labels, patch_artist=True, medianprops=dict(color="#d62728", linewidth=2.0))
    colors = ["#b8e994", "#ffd32a", "#d2dae2"]
    for patch, color in zip(bplot['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_edgecolor("#2f3542")

    # Add reference lines for fixed heuristics
    plt.axhline(curr_row["best_feasible_cost"], color="#eb2f06", linestyle="-.", linewidth=2.0, label=f"Praktik Eksisting ({curr_row['best_feasible_cost']:.1f})")
    plt.axhline(webster_row["best_feasible_cost"], color="#38ada9", linestyle="--", linewidth=2.0, label=f"Heuristik Webster ({webster_row['best_feasible_cost']:.1f})")

    plt.title("Perbandingan Distribusi Kualitas Solusi: Final ABC vs Baseline & Ablasi\n(10 Seed Unseen 100-109, Budget = 2.000 Evaluasi)", fontsize=12, fontweight="bold", pad=12)
    plt.ylabel("Biaya Objektif Terbaik J(x)", fontsize=11)
    plt.legend(loc="upper right", frameon=True, fontsize=10)
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    out_path = os.path.join(FIGURES_DIR, "boxplot_final_vs_baselines.png")
    plt.savefig(out_path)
    plt.close()
    print(f"[analyze] Saved final vs baselines boxplot: {out_path}")


def plot_sensitivity_analysis(rows: list):
    """Bar chart comparing baseline scenario vs +30% traffic surge vs stricter cycle constraint."""
    final_abc_costs = [r["best_feasible_cost"] for r in rows if r["experiment_group"] == "Final_ABC"]
    surge_costs = [r["best_feasible_cost"] for r in rows if r["experiment_group"] == "Sensitivity_TrafficSurge_Plus30"]
    strict_costs = [r["best_feasible_cost"] for r in rows if r["experiment_group"] == "Sensitivity_StrictCycle_120s"]

    labels = ["Baseline (Peak Normal)", "Lonjakan Arus (+30% Volume)", "Konstrain Ketat (C <= 120s)"]
    medians = [np.median(final_abc_costs), np.median(surge_costs), np.median(strict_costs)]
    q25s = [np.percentile(final_abc_costs, 25), np.percentile(surge_costs, 25), np.percentile(strict_costs, 25)]
    q75s = [np.percentile(final_abc_costs, 75), np.percentile(surge_costs, 75), np.percentile(strict_costs, 75)]
    yerr = [
        [medians[i] - q25s[i] for i in range(3)],
        [q75s[i] - medians[i] for i in range(3)]
    ]

    plt.figure(figsize=(8.5, 5.2), dpi=300)
    bars = plt.bar(labels, medians, yerr=yerr, capsize=6, color=["#4a69bd", "#e55039", "#fa983a"], edgecolor="#1e3799", width=0.55)

    for bar, med in zip(bars, medians):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2.5, f"Median: {med:.2f}",
                 ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.title("Analisis Sensitivitas & Kegagalan: Ketahanan Solusi ABC Terhadap Perubahan Kondisi\n(Error bar menunjukkan rentang IQR 25-75%)", fontsize=11, fontweight="bold", pad=12)
    plt.ylabel("Biaya Objektif Terbaik J(x)", fontsize=11)
    plt.ylim(0, max(medians) * 1.30)
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    out_path = os.path.join(FIGURES_DIR, "sensitivity_analysis.png")
    plt.savefig(out_path)
    plt.close()
    print(f"[analyze] Saved sensitivity chart: {out_path}")


def plot_validation_before_after(rows: list):
    """Bar chart showing Before (Current Practice) vs After (ABC Optimal) on Held-Out Validation session."""
    val_row = next(r for r in rows if r["experiment_group"] == "HeldOut_Validation")
    
    # We retrieve the current practice on validation from observation data
    # Current wait: 44.41s, queue: 12.00 veh, Cost = 44.41 + 2.0*12.0 = 68.41
    metrics = ["Waktu Tunggu (detik)", "Panjang Antrean (kendaraan)", "Biaya Total J(x)"]
    before_vals = [44.41, 12.00, 68.41]
    after_vals = [val_row["avg_wait_sec"], val_row["avg_queue_veh"], val_row["best_feasible_cost"]]

    x = np.arange(len(metrics))
    width = 0.35

    plt.figure(figsize=(9, 5.5), dpi=300)
    rects1 = plt.bar(x - width/2, before_vals, width, label="Praktik Eksisting (Sebelum)", color="#e74c3c", edgecolor="#c0392b")
    rects2 = plt.bar(x + width/2, after_vals, width, label="Rekomendasi Optimal ABC (Sesudah)", color="#2ecc71", edgecolor="#27ae60")

    for rect in rects1:
        h = rect.get_height()
        plt.text(rect.get_x() + rect.get_width()/2, h + 0.8, f"{h:.1f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    for rect in rects2:
        h = rect.get_height()
        plt.text(rect.get_x() + rect.get_width()/2, h + 0.8, f"{h:.1f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    plt.title("Validasi Independen pada Data Observasi Ditahan (Held-Out Session 3)\nPerbandingan Kinerja Sebelum vs Sesudah Optimasi ABC", fontsize=12, fontweight="bold", pad=12)
    plt.xticks(x, metrics, fontsize=11)
    plt.ylabel("Nilai Parameter", fontsize=11)
    plt.legend(fontsize=10, loc="upper right")
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    out_path = os.path.join(FIGURES_DIR, "validation_before_after.png")
    plt.savefig(out_path)
    plt.close()
    print(f"[analyze] Saved validation chart: {out_path}")


def generate_markdown_summary_tables(stats_dict: dict) -> str:
    """Generates formatted Markdown tables of statistical summaries."""
    md = []
    md.append("### Ringkasan Statistik Hasil Eksperimen Algoritma ABC\n")
    md.append("| Eksperimen / Konfigurasi | N | Feasibility | Median J(x) | IQR | Terbaik | Terburuk | Waktu Tunggu (s) | Antrean (veh) | Runtime (s) |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for lbl, s in stats_dict.items():
        feas = f"{s['feasibility_rate_pct']}%"
        med = f"{s['median_cost']:.2f}" if s['median_cost'] else "-"
        iqr = f"{s['iqr_cost']:.2f}" if s['iqr_cost'] else "-"
        best = f"{s['best_cost']:.2f}" if s['best_cost'] else "-"
        worst = f"{s['worst_cost']:.2f}" if s['worst_cost'] else "-"
        wait = f"{s['mean_wait_sec']:.2f}"
        q = f"{s['mean_queue_veh']:.2f}"
        rt = f"{s['mean_runtime_sec']:.2f}"
        md.append(f"| **{lbl}** | {s['sample_size']} | {feas} | **{med}** | {iqr} | {best} | {worst} | {wait} | {q} | {rt} |")

    table_text = "\n".join(md)
    table_file = os.path.join(TABLES_DIR, "statistical_summary.md")
    with open(table_file, "w", encoding="utf-8") as f:
        f.write(table_text)
    print(f"[analyze] Saved Markdown table: {table_file}")
    return table_text


def run_full_analysis():
    print("=== STARTING STATISTICAL ANALYSIS & PLOTTING ===")
    rows = load_experiment_data()
    print(f"Loaded {len(rows)} experiment rows from {EXPERIMENTS_CSV}")

    # Compute statistics
    stats = compute_group_statistics(rows, group_key="config_label")
    with open(os.path.join(TABLES_DIR, "stats_summary.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    table_md = generate_markdown_summary_tables(stats)
    print("\n" + table_md + "\n")

    # Load convergence histories
    with open(CONVERGENCE_JSON, "r", encoding="utf-8") as f:
        conv_data = json.load(f)

    curr_row = next(r for r in rows if r["experiment_group"] == "Current_Practice")
    webster_row = next(r for r in rows if r["experiment_group"] == "Webster_Heuristic")

    # Generate all publication-quality plots
    plot_convergence_curves(conv_data, curr_row["best_feasible_cost"], webster_row["best_feasible_cost"])
    plot_boxplot_param_study(rows)
    plot_boxplot_final_vs_baselines(rows)
    plot_sensitivity_analysis(rows)
    plot_validation_before_after(rows)

    print("=== ALL ANALYSIS CHARTS AND TABLES SUCCESSFULLY GENERATED ===")


if __name__ == "__main__":
    run_full_analysis()
