# Reproducing the frozen Rodina results

## Requirements

Use Python 3.12 or newer with the project development and visualization dependencies. The Rodina
ERA5 cache must be present under `data/weather/cache/open_meteo/era5/`; ordinary reproduction does
not require a network request.

## Lightweight validation

```powershell
.\.venv\Scripts\python.exe scripts\run_phase12.py --mode verify
```

This validates local inputs, hashes and provenance, cross-file consistency, Phase 11 semantics,
and final artifact generation. It does not treat saved result CSVs alone as physical reproduction.

## Controlled physical reproduction

```powershell
.\.venv\Scripts\python.exe scripts\run_phase12.py --mode reproduce
```

This reruns the frozen Phase 9 physical model and independently evaluates the saved final 95% and
99% Phase 10 designs. It does not run the Phase 10 optimizer. Runtime depends on hardware; Phase 9
trace generation is the main cost.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_phase12.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_phase9.py tests\test_phase10.py tests\test_phase11.py tests\test_phase12.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

## Historical commands

`scripts/run_phase9.py`, `scripts/run_phase10.py`, and `scripts/run_phase11.py` remain available,
but a normal final audit should not rerun the expensive Phase 10 candidate search. Use them only
when intentionally reconstructing historical phase artifacts.

Final outputs are under `outputs/benchmarks/rodina/phase12/`. A successful frozen benchmark audit
has zero `BLOCKER` entries. Known limitations may appear as `WARNING`.
