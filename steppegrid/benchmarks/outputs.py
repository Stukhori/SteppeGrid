"""Machine-readable and human-readable literature benchmark artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from steppegrid.benchmarks.models import ReconstructionResult, SourceIntegrityReport


def _comparison_lines(label: str, comparison) -> list[str]:
    return [
        f"## {label}",
        "",
        f"- Published annual total: {comparison.published_annual_kwh:,} kWh",
        f"- Calculated monthly-row sum: {comparison.calculated_monthly_sum_kwh:,} kWh",
        f"- Difference (calculated - published): {comparison.difference_kwh:+,} kWh",
        f"- Relative difference: {comparison.relative_difference:.6%}",
        f"- Equal: {'yes' if comparison.matches else 'no'}",
        "",
    ]


def write_source_integrity(report: SourceIntegrityReport, output_directory: str | Path) -> Path:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    (output / "source_integrity.json").write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Rodina Source-Integrity Report",
        "",
        "Printed annual totals and sums calculated from the transcribed monthly rows are "
        "kept separate. A mismatch is source evidence and is not corrected silently.",
        "",
    ]
    for label, comparison in (
        ("Load", report.load),
        ("PV generation", report.pv),
        ("Wind generation", report.wind),
        ("Total renewable generation", report.generation),
    ):
        lines.extend(_comparison_lines(label, comparison))
    lines.extend(
        [
            "## Conclusion",
            "",
            f"Known source inconsistency detected: {'yes' if report.known_source_inconsistency else 'no'}.",
            "",
        ]
    )
    (output / "source_integrity.md").write_text("\n".join(lines), encoding="utf-8")
    return output


def write_reconstruction(result: ReconstructionResult, output_directory: str | Path) -> Path:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "hourly_load.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("timestamp", "total_load_kwh"))
        writer.writerows(
            (timestamp.isoformat(), value)
            for timestamp, value in zip(
                result.dataset.timestamps, result.dataset.total_load_kwh, strict=True
            )
        )
    (output / "load_summary.json").write_text(
        result.summary.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (output / "provenance.json").write_text(
        json.dumps(
            result.dataset.provenance.model_dump(mode="json"),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    with (output / "monthly_validation.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fieldnames = list(result.validation[0].model_dump())
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in result.validation:
            writer.writerow(row.model_dump())
    return output
