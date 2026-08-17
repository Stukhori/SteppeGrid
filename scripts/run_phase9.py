"""Reproduce the controlled Rodina Phase 9 benchmark from the verified weather cache."""

from steppegrid.benchmarks.phase9 import run_phase9


if __name__ == "__main__":
    result = run_phase9()
    print(f"Phase 9 complete: {result.weather_integrity['records']} hours, "
          f"{len(result.wind) - 1} turbines, {len(result.pv)} PV pairings, "
          f"{len(result.storage)} storage cases")
