from steppegrid.benchmarks.phase10 import run_phase10
if __name__=="__main__":
 result=run_phase10();s=result["statistics"]
 print(f"Phase 10: {s['physical_feasible_candidates']} candidates, {s['battery_simulations']} battery simulations, {s['total_seconds']:.1f}s")
