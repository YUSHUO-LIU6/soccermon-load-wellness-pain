# Computational environment and portability

The original frozen environment and the current execution environment are
separate records. Do not edit the original session files to make them match.

| Component | Original freeze | Post-publication execution |
|---|---|---|
| OS / architecture | Windows 11, x86_64 | macOS 15.7.9 (24G830), arm64 |
| Python | 3.11.9 | 3.11.15 |
| R | 4.6.1 | 4.5.2 |
| Python resolution | Historical freeze record | Unchanged `uv.lock`, `uv sync --frozen` |
| R dependencies | Recorded versions, no portable lockfile | Missing packages only installed locally; existing packages reused with origin recorded |
| lme4 | 2.0-6 | 2.0.1 |
| clubSandwich | 0.7.0 | 0.7.0 |
| sandwich | 3.1-3 | 3.1.1 |
| logistf | 1.26.1 | 1.26.1 |
| coxme | 2.2-22 | 2.2.22 |
| survival | 3.8-6 | 3.8.3 |
| Matrix | 1.7-5 | 1.7.4 |

R's package version string formatting may display hyphens as dots. The
installed origins and complete session, rather than this compact table, are
the authority for which packages were used. The current R setup does not
recreate all original versions. Optimizers and failed/separated models may
behave differently across versions/platforms; they must pass the recorded
result gates or remain documented discrepancies.

The project library is `workspace/R/library`; `SOCCERMON_R_LIBRARY` and
`R_LIBS_USER` both identify it. The runner explicitly prepends it before
sourcing R analysis files. No system-library package was installed or upgraded.
Package versions/origins and input/source hashes appear in
`reports/EXECUTION_MANIFEST.json`; complete sessions remain in ignored runtime
evidence. The portable Python versions are numpy 2.4.6, pandas 3.0.6,
scipy 1.17.1, statsmodels 0.14.6, scikit-learn 1.9.1 and matplotlib 3.11.2.

Base seed: 20260722. R1 Firth bootstrap: 20260723, one stream across wellness
variants. Internal QA sampler: 20260902. The historical IRLS convergence and
per-replicate recording limitations are explained in the audit. Scientific
analysis settings and fallback logic were not retuned to match a platform.

A separate post-publication Model E/readiness probe installed the exact archived
survival 3.8-6 into `workspace/R/frozen-survival`. It did not replace the full
run's library. Both survival versions returned the same warning-bearing fit
on this machine; the original Windows failure was not reproduced by changing
survival alone. See `reports/FRAILTY_VERSION_PROBE.json`.

The optional post-publication stationarity check uses numDeriv 2016.8-1.1
(reported by R as 2016.8.1.1). It is included in the missing-only local-library
setup. It does not alter the original model-fitting algorithms.
