# RESULTS LOCK ¡ª RUN_R2_REPRO

Phase 10/11 formal re-analysis per FROZEN SAP v1.0 (05_REVISION_SAP, hash in SAP_FREEZE_HASH.txt). seed=20260722. Model set fixed by model_candidate_matrix.csv; no p-value-based selection.

Naming mapping (SAP-concordant): primary wellness exposure = most recent report within t-3..t-1 -> columns `*_recent3_wp_z`; strict day t-1 lag sensitivity -> columns `*_wp_z` (z of `*_burden_lag1`). SAP ¡ì5 formula label `soreness_burden_wp_z` is shorthand for the SAP ¡ì3 recent3 definition.

All numbers in downstream documents must come from `master_results.csv` / `master_results.json` only.

## Files (sha256 in RESULTS_LOCK_HASH.txt)

- bootstrap_primary_interaction.json
- bootstrap_replicates.csv
- diagnostic_inventory.csv
- event_count_inventory.csv
- firth_bootstrap_results.csv
- ipw_weight_diagnostics.csv
- ipw_weights_fatigue.csv
- ipw_weights_readiness.csv
- ipw_weights_soreness.csv
- master_results.csv
- master_results.json
- model_inventory.csv
- r_results.csv
- sample_size_inventory.csv
- sens_acwr.csv
- sens_washout14d.csv
- sens_washout3d.csv
- session_info_python.txt
- session_info_R.txt

Combined lock hash (sha256 of hash manifest): `e7e6d2c0a8104d2957550dbd331000e245eb21abb607a8d4c6578d79ebc7b1ee`
