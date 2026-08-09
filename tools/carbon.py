#!/usr/bin/env python3
"""Turn measured CPU time into energy and CO2e - with the assumptions visible.

    python3 tools/carbon.py                      # from results.json
    python3 tools/carbon.py --region eu-north-1  # a cleaner grid
    python3 tools/carbon.py --requests 50e6      # scale to a real workload

WHY THIS SCRIPT IS DELIBERATELY SIMPLE
--------------------------------------
You cannot measure joules from userspace without RAPL/perf privileges, which
you will not have on a cloud VM or a locked-down laptop. So this uses the
standard published model instead:

    energy (Wh) = CPU-seconds x (TDP / cores) x utilisation-factor / 3600
    energy_with_overhead = energy x PUE
    CO2e (g) = energy_with_overhead (kWh) x grid carbon intensity (gCO2e/kWh)

This is the same shape as the Cloud Carbon Footprint and Green Software
Foundation SCI methodologies. Every constant is on screen and adjustable,
which is the point: the class should leave knowing that carbon numbers are
ESTIMATES built on assumptions, and that the honest way to present one is
with its assumptions attached.

The ranking it produces is robust even though the absolute values are soft:
if language A burns 40x the CPU-seconds of language B on the same task, it
burns roughly 40x the energy, whatever you assume about the hardware.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Assumptions, all adjustable -------------------------------------------

# A representative server CPU. Cloud vCPUs are usually shares of something in
# this class. Divide TDP by physical cores to get a per-core figure.
DEFAULT_TDP_W = 205.0        # AMD EPYC 7763 class, 280 W part derated
DEFAULT_CORES = 64

# Power Usage Effectiveness: total facility power / IT power. 1.0 would be a
# datacentre that spends nothing on cooling, which does not exist.
# Hyperscalers publish 1.1-1.2; enterprise rooms are commonly 1.5-2.0.
DEFAULT_PUE = 1.12

# Embodied carbon: manufacturing the server, amortised over its life. Real SCI
# calculations include this; it is often 20-50% of lifetime emissions for
# compute that is not heavily utilised. We expose it as a multiplier so the
# class can see how much it moves the answer.
DEFAULT_EMBODIED_FACTOR = 1.0   # set to e.g. 1.3 to add 30% embodied

# Grid carbon intensity, gCO2e per kWh. These are order-of-magnitude figures
# for teaching, not for reporting - published values move year to year and
# vary by source. The SPREAD is the lesson, not the digits.
GRID_INTENSITY = {
    "eu-north-1":     20,    # Sweden: hydro + nuclear
    "eu-west-1":     250,    # Ireland
    "eu-central-1":  350,    # Germany
    "us-west-2":      95,    # Oregon: heavily hydro
    "us-east-1":     350,    # N. Virginia
    "ap-south-1":    630,    # India: coal-heavy
    "ap-southeast-2":600,    # Australia
    "world-average": 480,
}


def estimate(cpu_seconds: float, args: argparse.Namespace) -> tuple[float, float]:
    """Return (watt_hours, grams_co2e) for a given amount of CPU time."""
    watts_per_core = args.tdp / args.cores
    wh = cpu_seconds * watts_per_core * args.utilisation / 3600.0
    wh *= args.pue
    wh *= args.embodied
    grams = (wh / 1000.0) * GRID_INTENSITY[args.region]
    return wh, grams


def human_grams(g: float) -> str:
    if g < 1.0:
        return f"{g * 1000:.1f} mg"
    if g < 1000.0:
        return f"{g:.1f} g"
    return f"{g / 1000:.2f} kg"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default=os.path.join(ROOT, "results.json"))
    ap.add_argument("--workload", default="wordfreq",
                    help="which workload to scale up (default: wordfreq)")
    ap.add_argument("--requests", type=float, default=1e6,
                    help="how many times per month this runs (default: 1,000,000)")
    ap.add_argument("--region", default="eu-central-1", choices=sorted(GRID_INTENSITY))
    ap.add_argument("--tdp", type=float, default=DEFAULT_TDP_W)
    ap.add_argument("--cores", type=int, default=DEFAULT_CORES)
    ap.add_argument("--pue", type=float, default=DEFAULT_PUE)
    ap.add_argument("--utilisation", type=float, default=1.0,
                    help="fraction of a core actually used (1.0 = saturated)")
    ap.add_argument("--embodied", type=float, default=DEFAULT_EMBODIED_FACTOR,
                    help="multiplier for embodied/manufacturing carbon (e.g. 1.3)")
    args = ap.parse_args()

    if not os.path.exists(args.results):
        print(f"No results at {args.results}.")
        print("Run:  python3 tools/bench.py --reps 5 --json results.json")
        sys.exit(1)

    with open(args.results) as fh:
        data = json.load(fh)

    if args.workload not in data["workloads"]:
        print(f"workload {args.workload!r} not in results; have: {list(data['workloads'])}")
        sys.exit(1)

    wl = data["workloads"][args.workload]
    cells = {l: c for l, c in wl["langs"].items() if "error" not in c}
    if not cells:
        print("no successful measurements to work from")
        sys.exit(1)

    print("=" * 78)
    print(f"ENERGY AND CARBON ESTIMATE - workload '{args.workload}'")
    print("=" * 78)
    print()
    print("Assumptions (change any of them with a flag; the ranking will not move):")
    print(f"  CPU                {args.tdp:.0f} W TDP / {args.cores} cores"
          f" = {args.tdp / args.cores:.2f} W per core")
    print(f"  PUE                {args.pue}  (datacentre overhead)")
    print(f"  Embodied factor    {args.embodied}  (manufacturing, amortised)")
    print(f"  Utilisation        {args.utilisation}")
    print(f"  Region             {args.region} @ {GRID_INTENSITY[args.region]} gCO2e/kWh")
    print(f"  Volume             {args.requests:,.0f} executions/month")
    print()

    baseline = min(c["cpu_median"] for c in cells.values())

    header = (f"{'Language':<12} {'CPU/run':>10} {'Wh/month':>12} "
              f"{'CO2e/month':>12} {'vs best':>9}")
    print(header)
    print("-" * len(header))

    rows = sorted(cells.items(), key=lambda kv: kv[1]["cpu_median"])
    for lang, cell in rows:
        cpu = cell["cpu_median"]
        wh, grams = estimate(cpu * args.requests, args)
        print(f"{lang:<12} {cpu * 1000:>8.1f} ms {wh:>11.1f}  "
              f"{human_grams(grams):>12} {cpu / baseline:>8.1f}x")

    print()
    best_lang, best_cell = rows[0]
    worst_lang, worst_cell = rows[-1]
    _, best_g = estimate(best_cell["cpu_median"] * args.requests, args)
    _, worst_g = estimate(worst_cell["cpu_median"] * args.requests, args)
    delta_kg = (worst_g - best_g) / 1000.0

    print(f"Switching from {worst_lang} to {best_lang} for this workload saves about")
    print(f"{delta_kg:.1f} kg CO2e per month at {args.requests:,.0f} executions.")
    print()

    print("PUT THAT NUMBER IN CONTEXT BEFORE ANYONE ACTS ON IT")
    print("-" * 78)
    print(f"""
  {delta_kg:.1f} kg CO2e/month is roughly {delta_kg * 12 / 1000:.2f} tonnes/year.
  For comparison, one economy passenger on a London-New York return flight is
  about 0.6-1.0 tonnes. A single developer's annual laptop+commute footprint
  dwarfs most of these numbers.

  So the honest engineering conclusions are:

  1. At LOW volume, language choice is climate noise. Rewriting a cron job
     that runs 100 times a month from Python to Rust saves milligrams. Do not
     let anyone justify a rewrite on carbon grounds at that scale.

  2. At HIGH volume it becomes real, but it is still usually second-order
     compared to: not running the job at all, caching the result, picking a
     better algorithm, right-sizing the instance, and choosing a clean region.
     Moving this workload from ap-south-1 to eu-north-1 cuts emissions ~30x
     with no code change at all. Try: --region eu-north-1

  3. The strongest carbon argument for an efficient language is not CPU, it is
     DENSITY: if the service needs 1/10th the memory, you fit it on 1/10th the
     machines, and you avoid the embodied carbon of the hardware you did not
     buy. That is why the peak-RSS column matters more than it looks.

  4. Always show your assumptions. A carbon number without its PUE, grid
     intensity and utilisation is not a measurement, it is a vibe.
""".rstrip())


if __name__ == "__main__":
    main()
