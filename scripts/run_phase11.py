import argparse

from steppegrid.benchmarks.phase11 import run_phase11, update_combined_scenarios

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--combined-only",action="store_true",
        help="incrementally recompute only the two combined Phase 11 scenarios")
    args=parser.parse_args()
    result=update_combined_scenarios() if args.combined_only else run_phase11()
    print(f"Phase 11 complete: {result['summary']['statistics']}")
