# Reproducibility records

- `source_archives.json`: SHA-256 identities of supplied source archives.
- `source_manifest.csv`: hashes of imported code, protocol and frozen results.
  For portable core scripts the original source hash is also retained.
- `data_fingerprints.json`: six frozen derived-file fingerprints, including
  column order, row order, missingness and eight-decimal numerical values.
- `frozen/`: reference results, not fresh calculations.
- `SOURCE_FREEZE_HASH.txt`: original complete research-freeze identity.

The three CSVs originally at this directory's root are retained as historical
validation records. The earlier portability pass is preserved in
[`reports/VALIDATION.md`](../reports/VALIDATION.md). Current post-publication
execution scope, result gates and limitations are in
[`reports/REPRODUCIBILITY_AUDIT.md`](../reports/REPRODUCIBILITY_AUDIT.md),
[`RESULT_COMPARISON.csv`](../reports/RESULT_COMPARISON.csv) and
[`EXECUTION_MANIFEST.json`](../reports/EXECUTION_MANIFEST.json).

`verify-frozen` checks imported-file/SAP hashes and reexecutes 54 frozen
numeric-consistency checks. `rebuild` and `refit-focus` verify fresh data
and models separately. A historical PASS record alone is not evidence that a
model has been rerun.
