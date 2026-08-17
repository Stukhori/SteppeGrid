import argparse

from steppegrid.benchmarks.phase12 import run_phase12

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Validate or reproduce the frozen Rodina benchmark")
    parser.add_argument("--mode",choices=("verify","reproduce"),default="verify")
    args=parser.parse_args();result=run_phase12(mode=args.mode)
    print(f"Phase 12 {args.mode}: {len(result['audit'])} checks, {result['warnings']} warnings, {result['blockers']} blockers, {result['runtime_seconds']:.2f}s")
