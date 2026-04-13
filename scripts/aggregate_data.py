"""
Data Aggregation Script for Chapter 4.

Reads all raw CSV data from the experiment, computes summary statistics
across 5 runs per configuration, and outputs clean tables and charts.

Usage:
  cd /home/sanidhya/experiment
  source venv/bin/activate
  python scripts/aggregate_data.py

Output:
  results/summary_inference.csv
  results/summary_stream.csv
  results/summary_pipeline.csv
  results/summary_resources.csv
  results/summary_stream_custom.csv
  results/summary_pipeline_custom.csv
  results/charts/*.png
"""

import csv
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import matplotlib for charts
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("WARNING: matplotlib not installed. Skipping charts.")
    print("Install with: pip install matplotlib --break-system-packages")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
CHARTS_DIR = os.path.join(RESULTS_DIR, "charts")

FRAMEWORKS = ["flask", "django", "fastapi", "tornado"]
ENDPOINTS = ["inference", "stream", "pipeline"]
CONCURRENCY_LEVELS = [1, 5, 10, 25, 50, 100]
RUNS = 5

# Ensure output directories exist
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def safe_median(values):
    return round(statistics.median(values), 3) if values else None

def safe_mean(values):
    return round(statistics.mean(values), 3) if values else None

def safe_stdev(values):
    return round(statistics.stdev(values), 3) if len(values) >= 2 else None

def safe_percentile(values, p):
    if not values:
        return None
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * p / 100)
    idx = min(idx, len(sorted_v) - 1)
    return round(sorted_v[idx], 3)


def read_csv_rows(filepath):
    """Read a CSV file and return list of dicts."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ---------------------------------------------------------------------------
# 1. Locust Stats Aggregation (Metrics 3, 5, 6, 7)
# ---------------------------------------------------------------------------

def aggregate_locust_stats():
    """Aggregate Locust stats across 5 runs per configuration.

    Extracts: Total Response Time, Throughput, Tail Latency, Error Rate
    """
    print("=" * 60)
    print("AGGREGATING LOCUST STATS")
    print("=" * 60)

    results = []

    for framework in FRAMEWORKS:
        for endpoint in ENDPOINTS:
            for concurrency in CONCURRENCY_LEVELS:
                response_times_median = []
                response_times_avg = []
                response_times_min = []
                response_times_max = []
                throughputs = []
                error_rates = []
                request_counts = []
                p95_values = []
                p99_values = []

                for run in range(1, RUNS + 1):
                    stats_file = os.path.join(
                        DATA_DIR, framework, endpoint,
                        f"c{concurrency}_run{run}_stats.csv"
                    )
                    rows = read_csv_rows(stats_file)

                    # Find the Aggregated row (last row, or row with Name="Aggregated")
                    agg_row = None
                    for row in rows:
                        if row.get("Name", "").strip() == "Aggregated" or row.get("Name", "").strip() == "":
                            if row.get("Request Count", "0") != "0":
                                agg_row = row
                                break

                    if agg_row is None:
                        # Try second row (some CSVs have header + aggregated)
                        for row in rows:
                            if int(row.get("Request Count", "0")) > 0:
                                agg_row = row
                                break

                    if agg_row and int(agg_row.get("Request Count", "0")) > 0:
                        req_count = int(agg_row["Request Count"])
                        fail_count = int(agg_row["Failure Count"])

                        request_counts.append(req_count)
                        response_times_median.append(float(agg_row["Median Response Time"]))
                        response_times_avg.append(float(agg_row["Average Response Time"]))
                        response_times_min.append(float(agg_row["Min Response Time"]))
                        response_times_max.append(float(agg_row["Max Response Time"]))
                        throughputs.append(float(agg_row["Requests/s"]))
                        error_rates.append(
                            (fail_count / req_count * 100) if req_count > 0 else 0
                        )

                        # p95 and p99 from percentile columns
                        if "95%" in agg_row:
                            try:
                                p95_values.append(float(agg_row["95%"]))
                            except (ValueError, TypeError):
                                pass
                        if "99%" in agg_row:
                            try:
                                p99_values.append(float(agg_row["99%"]))
                            except (ValueError, TypeError):
                                pass

                if request_counts:
                    result = {
                        "framework": framework,
                        "endpoint": endpoint,
                        "concurrency": concurrency,
                        "runs_collected": len(request_counts),
                        "total_requests_median": safe_median(request_counts),
                        "response_time_median_ms": safe_median(response_times_median),
                        "response_time_avg_ms": safe_median(response_times_avg),
                        "response_time_min_ms": safe_median(response_times_min),
                        "response_time_max_ms": safe_median(response_times_max),
                        "throughput_median_rps": safe_median(throughputs),
                        "throughput_mean_rps": safe_mean(throughputs),
                        "throughput_stdev_rps": safe_stdev(throughputs),
                        "p95_median_ms": safe_median(p95_values),
                        "p99_median_ms": safe_median(p99_values),
                        "error_rate_median_pct": safe_median(error_rates),
                    }
                    results.append(result)
                    print(f"  {framework:8s} | {endpoint:10s} | c{concurrency:3d} | "
                          f"{len(request_counts)} runs | "
                          f"median={result['response_time_median_ms']}ms | "
                          f"throughput={result['throughput_median_rps']} req/s")
                else:
                    print(f"  {framework:8s} | {endpoint:10s} | c{concurrency:3d} | NO DATA")

    # Write to CSV
    if results:
        output_file = os.path.join(RESULTS_DIR, "summary_locust_stats.csv")
        fieldnames = list(results[0].keys())
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nSaved: {output_file}")

    return results


# ---------------------------------------------------------------------------
# 2. Resource Monitoring Aggregation (Metrics 8, 9, 10)
# ---------------------------------------------------------------------------

def aggregate_resources():
    """Aggregate psutil resource data across 5 runs per configuration.

    Extracts: Peak Memory RSS, Memory Growth, CPU Utilisation
    """
    print("\n" + "=" * 60)
    print("AGGREGATING RESOURCE DATA")
    print("=" * 60)

    results = []

    for framework in FRAMEWORKS:
        for endpoint in ENDPOINTS:
            for concurrency in CONCURRENCY_LEVELS:
                peak_rss_values = []
                idle_rss_values = []
                memory_growth_values = []
                avg_cpu_values = []
                max_cpu_values = []

                for run in range(1, RUNS + 1):
                    res_file = os.path.join(
                        DATA_DIR, framework, endpoint,
                        f"c{concurrency}_run{run}_resources.csv"
                    )
                    rows = read_csv_rows(res_file)

                    if not rows:
                        continue

                    rss_values = []
                    cpu_values = []
                    idle_rss = None

                    for row in rows:
                        try:
                            rss = float(row["rss_mb"])
                            cpu = float(row["cpu_percent"])
                            rss_values.append(rss)
                            cpu_values.append(cpu)
                            if idle_rss is None:
                                idle_rss = rss  # First sample is idle
                        except (ValueError, KeyError):
                            continue

                    if rss_values and idle_rss is not None:
                        peak_rss = max(rss_values)
                        peak_rss_values.append(peak_rss)
                        idle_rss_values.append(idle_rss)
                        memory_growth_values.append(peak_rss - idle_rss)
                        avg_cpu_values.append(statistics.mean(cpu_values))
                        max_cpu_values.append(max(cpu_values))

                if peak_rss_values:
                    result = {
                        "framework": framework,
                        "endpoint": endpoint,
                        "concurrency": concurrency,
                        "runs_collected": len(peak_rss_values),
                        "idle_rss_median_mb": safe_median(idle_rss_values),
                        "peak_rss_median_mb": safe_median(peak_rss_values),
                        "memory_growth_median_mb": safe_median(memory_growth_values),
                        "avg_cpu_median_pct": safe_median(avg_cpu_values),
                        "max_cpu_median_pct": safe_median(max_cpu_values),
                    }
                    results.append(result)
                    print(f"  {framework:8s} | {endpoint:10s} | c{concurrency:3d} | "
                          f"peak={result['peak_rss_median_mb']}MB | "
                          f"growth={result['memory_growth_median_mb']}MB | "
                          f"cpu={result['avg_cpu_median_pct']}%")

    # Write to CSV
    if results:
        output_file = os.path.join(RESULTS_DIR, "summary_resources.csv")
        fieldnames = list(results[0].keys())
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nSaved: {output_file}")

    return results


# ---------------------------------------------------------------------------
# 3. Stream Custom Metrics (Metrics 1, 2, 4)
# ---------------------------------------------------------------------------

def aggregate_stream_metrics():
    """Aggregate custom stream metrics (TTFT, TPOT, CSR).

    Extracts: TTFT, TPOT, Connection Success Rate
    """
    print("\n" + "=" * 60)
    print("AGGREGATING STREAM CUSTOM METRICS")
    print("=" * 60)

    results = []

    for framework in FRAMEWORKS:
        for concurrency in CONCURRENCY_LEVELS:
            ttft_all = []
            tpot_all = []
            success_counts = []
            total_counts = []

            for run in range(1, RUNS + 1):
                metrics_file = os.path.join(
                    DATA_DIR, framework, "stream",
                    f"c{concurrency}_run{run}_stream_metrics.csv"
                )
                rows = read_csv_rows(metrics_file)

                if not rows:
                    continue

                run_success = 0
                run_total = 0

                for row in rows:
                    run_total += 1
                    if row.get("success", "").lower() == "true":
                        run_success += 1
                        try:
                            if row["ttft_ms"] and row["ttft_ms"] != "None":
                                ttft_all.append(float(row["ttft_ms"]))
                        except (ValueError, KeyError):
                            pass
                        try:
                            if row["tpot_ms"] and row["tpot_ms"] != "None":
                                tpot_all.append(float(row["tpot_ms"]))
                        except (ValueError, KeyError):
                            pass

                if run_total > 0:
                    success_counts.append(run_success)
                    total_counts.append(run_total)

            if ttft_all:
                csr_values = [
                    (s / t * 100) if t > 0 else 0
                    for s, t in zip(success_counts, total_counts)
                ]

                result = {
                    "framework": framework,
                    "concurrency": concurrency,
                    "runs_collected": len(total_counts),
                    "ttft_median_ms": safe_median(ttft_all),
                    "ttft_mean_ms": safe_mean(ttft_all),
                    "ttft_p95_ms": safe_percentile(ttft_all, 95),
                    "ttft_p99_ms": safe_percentile(ttft_all, 99),
                    "tpot_median_ms": safe_median(tpot_all),
                    "tpot_mean_ms": safe_mean(tpot_all),
                    "tpot_p95_ms": safe_percentile(tpot_all, 95),
                    "csr_median_pct": safe_median(csr_values),
                }
                results.append(result)
                print(f"  {framework:8s} | c{concurrency:3d} | "
                      f"TTFT={result['ttft_median_ms']}ms | "
                      f"TPOT={result['tpot_median_ms']}ms | "
                      f"CSR={result['csr_median_pct']}%")

    # Write to CSV
    if results:
        output_file = os.path.join(RESULTS_DIR, "summary_stream_custom.csv")
        fieldnames = list(results[0].keys())
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nSaved: {output_file}")

    return results


# ---------------------------------------------------------------------------
# 4. Pipeline Custom Metrics (Metrics 11, 12, 13)
# ---------------------------------------------------------------------------

def aggregate_pipeline_metrics():
    """Aggregate custom pipeline metrics.

    Extracts: E2E Pipeline Latency, Stage Timings, Pipeline Completion Rate
    """
    print("\n" + "=" * 60)
    print("AGGREGATING PIPELINE CUSTOM METRICS")
    print("=" * 60)

    results = []

    for framework in FRAMEWORKS:
        for concurrency in CONCURRENCY_LEVELS:
            e2e_all = []
            stage1_all = []
            stage2_all = []
            stage3_all = []
            stage4_all = []
            completed_counts = []
            total_counts = []

            for run in range(1, RUNS + 1):
                metrics_file = os.path.join(
                    DATA_DIR, framework, "pipeline",
                    f"c{concurrency}_run{run}_pipeline_metrics.csv"
                )
                rows = read_csv_rows(metrics_file)

                if not rows:
                    continue

                run_completed = 0
                run_total = 0

                for row in rows:
                    run_total += 1
                    if row.get("completed", "").lower() == "true":
                        run_completed += 1
                        try:
                            if row["e2e_pipeline_ms"] and row["e2e_pipeline_ms"] != "None":
                                e2e_all.append(float(row["e2e_pipeline_ms"]))
                        except (ValueError, KeyError):
                            pass
                        try:
                            if row.get("stage1_ms") and row["stage1_ms"] != "None":
                                stage1_all.append(float(row["stage1_ms"]))
                            if row.get("stage2_ms") and row["stage2_ms"] != "None":
                                stage2_all.append(float(row["stage2_ms"]))
                            if row.get("stage3_ms") and row["stage3_ms"] != "None":
                                stage3_all.append(float(row["stage3_ms"]))
                            if row.get("stage4_ms") and row["stage4_ms"] != "None":
                                stage4_all.append(float(row["stage4_ms"]))
                        except (ValueError, KeyError):
                            pass

                if run_total > 0:
                    completed_counts.append(run_completed)
                    total_counts.append(run_total)

            if e2e_all:
                pcr_values = [
                    (c / t * 100) if t > 0 else 0
                    for c, t in zip(completed_counts, total_counts)
                ]

                result = {
                    "framework": framework,
                    "concurrency": concurrency,
                    "runs_collected": len(total_counts),
                    "e2e_median_ms": safe_median(e2e_all),
                    "e2e_mean_ms": safe_mean(e2e_all),
                    "e2e_p95_ms": safe_percentile(e2e_all, 95),
                    "stage1_median_ms": safe_median(stage1_all),
                    "stage2_median_ms": safe_median(stage2_all),
                    "stage3_median_ms": safe_median(stage3_all),
                    "stage4_median_ms": safe_median(stage4_all),
                    "pcr_median_pct": safe_median(pcr_values),
                }
                results.append(result)
                print(f"  {framework:8s} | c{concurrency:3d} | "
                      f"E2E={result['e2e_median_ms']}ms | "
                      f"S1={result['stage1_median_ms']} | "
                      f"S2={result['stage2_median_ms']} | "
                      f"S3={result['stage3_median_ms']} | "
                      f"PCR={result['pcr_median_pct']}%")

    # Write to CSV
    if results:
        output_file = os.path.join(RESULTS_DIR, "summary_pipeline_custom.csv")
        fieldnames = list(results[0].keys())
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nSaved: {output_file}")

    return results


# ---------------------------------------------------------------------------
# 5. Charts
# ---------------------------------------------------------------------------

def generate_charts(locust_data, resource_data, stream_data, pipeline_data):
    """Generate comparison charts for Chapter 4."""
    if not HAS_MATPLOTLIB:
        print("\nSkipping charts — install matplotlib first.")
        return

    print("\n" + "=" * 60)
    print("GENERATING CHARTS")
    print("=" * 60)

    # Colorblind-friendly palette with neutral gray for overlap-heavy series.
    colors = {
        "flask": "#6E6E6E",   # gray
        "django": "#0072B2",  # blue
        "fastapi": "#D55E00", # red-orange
        "tornado": "#009E73", # green
    }

    line_styles = {
        "flask": "-",
        "django": "-",
        "fastapi": "-",
        "tornado": "-",
    }
    line_offsets = {
        "flask": -0.06,
        "django": -0.02,
        "fastapi": 0.02,
        "tornado": 0.06,
    }
    framework_markers = {
        "flask": "o",
        "django": "s",
        "fastapi": "^",
        "tornado": "D",
    }
    framework_zorder = {
        "flask": 2,
        "django": 3,
        "fastapi": 4,
        "tornado": 5,
    }
    line_width = 2.8
    marker_size = 8.0
    marker_edge_width = 1.8

    def offset_concurrency_values(values, framework):
        offset = line_offsets[framework]
        return [round(value * (1 + offset), 6) for value in values]

    def style_framework_axes(ax, title, ylabel):
        ax.set_xlabel("Concurrency Level")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(ncol=2, frameon=True)
        ax.grid(True, which="both", alpha=0.25, linestyle="--")
        ax.set_xscale("log", base=2)
        ax.set_xticks(CONCURRENCY_LEVELS)
        ax.set_xticklabels(CONCURRENCY_LEVELS)
        ax.set_xlim(min(CONCURRENCY_LEVELS) * 0.85, max(CONCURRENCY_LEVELS) * 1.15)

    def plot_framework_lines(ax, records, endpoint, value_key):
        for fw in FRAMEWORKS:
            fw_data = sorted(
                [r for r in records if r["framework"] == fw and r["endpoint"] == endpoint],
                key=lambda row: row["concurrency"],
            )
            if fw_data:
                x = offset_concurrency_values([r["concurrency"] for r in fw_data], fw)
                y = [r[value_key] for r in fw_data]
                ax.plot(
                    x,
                    y,
                    marker=framework_markers[fw],
                    linestyle=line_styles[fw],
                    label=fw.capitalize(),
                    color=colors[fw],
                    linewidth=line_width,
                    markersize=marker_size,
                    markerfacecolor="white",
                    markeredgewidth=marker_edge_width,
                    markeredgecolor=colors[fw],
                    alpha=1.0,
                    zorder=framework_zorder[fw],
                )

    # --- Chart 1: Response Time vs Concurrency (Inference) ---
    fig, ax = plt.subplots(figsize=(11, 6.5), constrained_layout=True)
    plot_framework_lines(ax, locust_data, "inference", "response_time_median_ms")
    style_framework_axes(ax, "Inference: Response Time vs Concurrency", "Median Response Time (ms)")
    plt.savefig(os.path.join(CHARTS_DIR, "response_time_inference.png"), dpi=180, bbox_inches="tight")
    plt.close()
    print("  Saved: response_time_inference.png")

    # --- Chart 2: Throughput vs Concurrency (Inference) ---
    fig, ax = plt.subplots(figsize=(11, 6.5), constrained_layout=True)
    plot_framework_lines(ax, locust_data, "inference", "throughput_median_rps")
    style_framework_axes(ax, "Inference: Throughput vs Concurrency", "Throughput (req/s)")
    plt.savefig(os.path.join(CHARTS_DIR, "throughput_inference.png"), dpi=180, bbox_inches="tight")
    plt.close()
    print("  Saved: throughput_inference.png")

    # --- Chart 3: Response Time vs Concurrency (Stream) ---
    fig, ax = plt.subplots(figsize=(11, 6.5), constrained_layout=True)
    plot_framework_lines(ax, locust_data, "stream", "response_time_median_ms")
    style_framework_axes(ax, "Streaming: Response Time vs Concurrency", "Median Response Time (ms)")
    plt.savefig(os.path.join(CHARTS_DIR, "response_time_stream.png"), dpi=180, bbox_inches="tight")
    plt.close()
    print("  Saved: response_time_stream.png")

    # --- Chart 4: Throughput vs Concurrency (Stream) ---
    fig, ax = plt.subplots(figsize=(11, 6.5), constrained_layout=True)
    plot_framework_lines(ax, locust_data, "stream", "throughput_median_rps")
    style_framework_axes(ax, "Streaming: Throughput vs Concurrency", "Throughput (req/s)")
    plt.savefig(os.path.join(CHARTS_DIR, "throughput_stream.png"), dpi=180, bbox_inches="tight")
    plt.close()
    print("  Saved: throughput_stream.png")

    # --- Chart 5: Pipeline E2E Latency ---
    fig, ax = plt.subplots(figsize=(11, 6.5), constrained_layout=True)
    plot_framework_lines(ax, locust_data, "pipeline", "response_time_median_ms")
    style_framework_axes(ax, "Pipeline: Response Time vs Concurrency", "Median Response Time (ms)")
    plt.savefig(os.path.join(CHARTS_DIR, "response_time_pipeline.png"), dpi=180, bbox_inches="tight")
    plt.close()
    print("  Saved: response_time_pipeline.png")

    # --- Chart 6: Throughput vs Concurrency (Pipeline) ---
    fig, ax = plt.subplots(figsize=(11, 6.5), constrained_layout=True)
    plot_framework_lines(ax, locust_data, "pipeline", "throughput_median_rps")
    style_framework_axes(ax, "Pipeline: Throughput vs Concurrency", "Throughput (req/s)")
    plt.savefig(os.path.join(CHARTS_DIR, "throughput_pipeline.png"), dpi=180, bbox_inches="tight")
    plt.close()
    print("  Saved: throughput_pipeline.png")

    # --- Chart 7: Pipeline Stage 2 Inflation ---
    if pipeline_data:
        fig, ax = plt.subplots(figsize=(11, 6.5), constrained_layout=True)
        for fw in FRAMEWORKS:
            fw_data = sorted(
                [r for r in pipeline_data if r["framework"] == fw],
                key=lambda row: row["concurrency"],
            )
            if fw_data:
                x = offset_concurrency_values([r["concurrency"] for r in fw_data], fw)
                y = [r["stage2_median_ms"] for r in fw_data]
                ax.plot(
                    x,
                    y,
                    marker=framework_markers[fw],
                    linestyle=line_styles[fw],
                    label=fw.capitalize(),
                    color=colors[fw],
                    linewidth=line_width,
                    markersize=marker_size,
                    markerfacecolor="white",
                    markeredgewidth=marker_edge_width,
                    markeredgecolor=colors[fw],
                    alpha=1.0,
                    zorder=framework_zorder[fw],
                )
        style_framework_axes(
            ax,
            "Pipeline: Stage 2 Retrieval Delay vs Concurrency",
            "Stage 2 Median Duration (ms)",
        )
        plt.savefig(os.path.join(CHARTS_DIR, "stage2_inflation.png"), dpi=180, bbox_inches="tight")
        plt.close()
        print("  Saved: stage2_inflation.png")

    # --- Chart 8: Peak Memory RSS (Inference) ---
    fig, ax = plt.subplots(figsize=(11, 6.5), constrained_layout=True)
    for fw in FRAMEWORKS:
        fw_data = sorted(
            [r for r in resource_data if r["framework"] == fw and r["endpoint"] == "inference"],
            key=lambda row: row["concurrency"],
        )
        if fw_data:
            x = offset_concurrency_values([r["concurrency"] for r in fw_data], fw)
            y = [r["peak_rss_median_mb"] for r in fw_data]
            ax.plot(
                x,
                y,
                marker=framework_markers[fw],
                linestyle=line_styles[fw],
                label=fw.capitalize(),
                color=colors[fw],
                linewidth=line_width,
                markersize=marker_size,
                markerfacecolor="white",
                markeredgewidth=marker_edge_width,
                markeredgecolor=colors[fw],
                alpha=1.0,
                zorder=framework_zorder[fw],
            )
    style_framework_axes(ax, "Inference: Peak Memory vs Concurrency", "Peak Memory RSS (MB)")
    plt.savefig(os.path.join(CHARTS_DIR, "memory_inference.png"), dpi=180, bbox_inches="tight")
    plt.close()
    print("  Saved: memory_inference.png")

    # --- Chart 9: TTFT Comparison ---
    if stream_data:
        fig, ax = plt.subplots(figsize=(11, 6.5), constrained_layout=True)
        for fw in FRAMEWORKS:
            fw_data = sorted(
                [r for r in stream_data if r["framework"] == fw],
                key=lambda row: row["concurrency"],
            )
            if fw_data:
                x = offset_concurrency_values([r["concurrency"] for r in fw_data], fw)
                y = [r["ttft_median_ms"] for r in fw_data]
                ax.plot(
                    x,
                    y,
                    marker=framework_markers[fw],
                    linestyle=line_styles[fw],
                    label=fw.capitalize(),
                    color=colors[fw],
                    linewidth=line_width,
                    markersize=marker_size,
                    markerfacecolor="white",
                    markeredgewidth=marker_edge_width,
                    markeredgecolor=colors[fw],
                    alpha=1.0,
                    zorder=framework_zorder[fw],
                )
        style_framework_axes(ax, "Streaming: Time to First Token vs Concurrency", "TTFT Median (ms)")
        plt.savefig(os.path.join(CHARTS_DIR, "ttft_comparison.png"), dpi=180, bbox_inches="tight")
        plt.close()
        print("  Saved: ttft_comparison.png")

    # --- Chart 10: All frameworks throughput comparison (grouped bar) ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)
    for idx, endpoint in enumerate(ENDPOINTS):
        ax = axes[idx]
        bar_width = 0.2
        x_positions = range(len(CONCURRENCY_LEVELS))

        for fw_idx, fw in enumerate(FRAMEWORKS):
            fw_data = [r for r in locust_data if r["framework"] == fw and r["endpoint"] == endpoint]
            if fw_data:
                y = [r["throughput_median_rps"] for r in fw_data]
                positions = [x + fw_idx * bar_width for x in x_positions]
                ax.bar(positions, y, bar_width, label=fw.capitalize(), color=colors[fw])

        ax.set_xlabel("Concurrency Level")
        ax.set_ylabel("Throughput (req/s)")
        ax.set_title(f"{endpoint.capitalize()}")
        ax.set_xticks([x + 1.5 * bar_width for x in x_positions])
        ax.set_xticklabels(CONCURRENCY_LEVELS)
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

    plt.suptitle("Throughput Comparison Across All Endpoints", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, "throughput_all_endpoints.png"), dpi=150)
    plt.close()
    print("  Saved: throughput_all_endpoints.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("THESIS DATA AGGREGATION")
    print(f"Data directory: {DATA_DIR}")
    print(f"Output directory: {RESULTS_DIR}")
    print("=" * 60)
    print()

    # Check data exists
    for fw in FRAMEWORKS:
        fw_dir = os.path.join(DATA_DIR, fw)
        if os.path.exists(fw_dir):
            file_count = sum(len(files) for _, _, files in os.walk(fw_dir))
            print(f"  {fw}: {file_count} files")
        else:
            print(f"  {fw}: NO DATA DIRECTORY")

    print()

    # Run aggregations
    locust_data = aggregate_locust_stats()
    resource_data = aggregate_resources()
    stream_data = aggregate_stream_metrics()
    pipeline_data = aggregate_pipeline_metrics()

    # Generate charts
    generate_charts(locust_data, resource_data, stream_data, pipeline_data)

    print("\n" + "=" * 60)
    print("AGGREGATION COMPLETE")
    print("=" * 60)
    print(f"\nOutput files in: {RESULTS_DIR}/")
    for f in sorted(os.listdir(RESULTS_DIR)):
        if f.endswith(".csv"):
            print(f"  {f}")
    if os.path.exists(CHARTS_DIR):
        chart_count = len([f for f in os.listdir(CHARTS_DIR) if f.endswith(".png")])
        print(f"\n  {chart_count} charts in {CHARTS_DIR}/")


if __name__ == "__main__":
    main()