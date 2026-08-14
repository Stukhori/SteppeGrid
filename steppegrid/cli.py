"""Command-line demonstration for a synthetic 24-hour scenario."""

from steppegrid.examples.synthetic import synthetic_24_hour_scenario
from steppegrid.simulation.simulator import simulate


def main() -> None:
    result = simulate(synthetic_24_hour_scenario())
    print("SteppeGrid synthetic 24-hour scenario (not representative field data)")
    for name, value in result.metrics.model_dump().items():
        rendered = f"{value:.3f}" if isinstance(value, float) else str(value)
        print(f"{name}: {rendered}")


if __name__ == "__main__":
    main()
