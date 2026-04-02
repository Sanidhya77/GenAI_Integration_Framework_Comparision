"""
Resource monitoring script using psutil.

Samples CPU utilisation and memory RSS of a target process every 1 second.
Runs as a separate process alongside the framework server during each test run.

Metrics collected (Dimension 3):
  - Peak Memory RSS (MB) — Metric #8
  - Memory Growth Rate (MB) — Metric #9 (computed from RSS data)
  - CPU Utilisation (%) — Metric #10

Usage:
  python monitoring/resource_monitor.py --pid <SERVER_PID> --output <CSV_PATH>

  # Example:
  python monitoring/resource_monitor.py --pid 12345 --output data/flask/inference/run1_resources.csv

  # Stop with Ctrl+C — data is flushed on exit

Output CSV columns:
  timestamp, elapsed_s, rss_mb, cpu_percent
"""

import argparse
import csv
import os
import signal
import sys
import time

import psutil


def get_process(pid):
    """Get a psutil.Process object for the given PID.

    Exits with an error if the process does not exist.
    """
    try:
        proc = psutil.Process(pid)
        return proc
    except psutil.NoSuchProcess:
        print(f"Error: No process found with PID {pid}")
        sys.exit(1)


def monitor(pid, output_path, interval=1.0):
    """Monitor a process and write resource data to CSV.

    Samples RSS memory and CPU usage at the specified interval.
    Handles Ctrl+C gracefully to ensure data is flushed.
    """
    proc = get_process(pid)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Initial CPU percent call (first call always returns 0.0)
    proc.cpu_percent()

    # Record idle RSS before load starts
    try:
        idle_rss = proc.memory_info().rss / (1024 * 1024)  # Convert to MB
    except psutil.NoSuchProcess:
        print("Error: Process terminated before monitoring started")
        sys.exit(1)

    print(f"Monitoring PID {pid} (idle RSS: {idle_rss:.2f} MB)")
    print(f"Output: {output_path}")
    print(f"Sampling interval: {interval}s")
    print("Press Ctrl+C to stop...\n")

    start_time = time.time()
    running = True

    def handle_signal(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "elapsed_s", "rss_mb", "cpu_percent"])

        # Write idle baseline row
        writer.writerow([
            round(start_time, 3),
            0.0,
            round(idle_rss, 2),
            0.0,
        ])

        sample_count = 0
        peak_rss = idle_rss

        while running:
            time.sleep(interval)

            try:
                mem = proc.memory_info()
                cpu = proc.cpu_percent()
            except psutil.NoSuchProcess:
                print(f"\nProcess {pid} terminated. Stopping monitor.")
                break

            now = time.time()
            elapsed = round(now - start_time, 3)
            rss_mb = round(mem.rss / (1024 * 1024), 2)
            cpu_pct = round(cpu, 1)

            writer.writerow([round(now, 3), elapsed, rss_mb, cpu_pct])
            f.flush()  # Ensure data is written even if interrupted

            if rss_mb > peak_rss:
                peak_rss = rss_mb

            sample_count += 1

            # Print progress every 10 samples
            if sample_count % 10 == 0:
                print(f"  [{elapsed:.0f}s] RSS: {rss_mb:.1f} MB | CPU: {cpu_pct:.1f}%")

    # Summary
    memory_growth = round(peak_rss - idle_rss, 2)
    print(f"\n--- Monitoring Summary ---")
    print(f"Samples collected: {sample_count}")
    print(f"Duration: {elapsed:.1f}s")
    print(f"Idle RSS: {idle_rss:.2f} MB")
    print(f"Peak RSS: {peak_rss:.2f} MB")
    print(f"Memory growth: {memory_growth:.2f} MB")
    print(f"Data saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Monitor CPU and memory of a process during experiment runs"
    )
    parser.add_argument(
        "--pid",
        type=int,
        required=True,
        help="PID of the framework server process to monitor",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to output CSV file (e.g., data/flask/inference/run1_resources.csv)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Sampling interval in seconds (default: 1.0)",
    )

    args = parser.parse_args()
    monitor(args.pid, args.output, args.interval)