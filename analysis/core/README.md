# Core Analysis

This directory contains the core analytical workflow used to reconstruct the SoccerMon player-day dataset and reproduce the primary statistical analyses.

The scripts are derived from the frozen manuscript-revision workflow. Public-facing versions are organized here with portable project-relative paths while preserving the original analytical definitions and statistical specifications.

## Core scripts

The workflow consists of five main stages:

### 1. Raw-data audit and reconstruction

`01_raw_audit_and_rebuild.py`

- audits the downloaded SoccerMon source files
- checks player and date coverage
- checks duplicate observations and variable ranges
- reconstructs the complete player-day dataset
- records data-integrity diagnostics

### 2. Episode and modelling-dataset construction

`02_episodes_and_modeling_data.py`

- reconstructs recurrent lower-limb pain episodes
- applies the prespecified washout rules
- identifies onset days
- defines the at-risk player-day population
- derives lagged training-load and wellness variables
- creates the modelling dataset

### 3. Missing-data assessment

`03_missingness_ipw.py`

- describes wellness-data missingness
- evaluates observation patterns
- fits observation models
- constructs inverse-probability-of-observation weights
- records weight diagnostics

### 4. Primary statistical modelling

`04_run_reanalysis.R`

- fits the prespecified primary and supporting models
- evaluates load, wellness, and load × wellness associations
- applies sparse-data methods where required
- records model, sample-size, and convergence diagnostics

### 5. Bootstrap and finalization

`05_bootstrap_and_ipw.py`

- constructs sensitivity datasets
- performs whole-player bootstrap analyses
- performs Firth bootstrap analyses
- integrates model outputs
- creates the locked final result set

## Execution order

The main workflow is run in the following order:

```text
01_raw_audit_and_rebuild.py
        ↓
02_episodes_and_modeling_data.py
        ↓
03_missingness_ipw.py
        ↓
05_bootstrap_and_ipw.py prep
        ↓
05_bootstrap_and_ipw.py ipw
        ↓
04_run_reanalysis.R
        ↓
05_bootstrap_and_ipw.py bootstrap
        ↓
05_bootstrap_and_ipw.py firth_boot
        ↓
05_bootstrap_and_ipw.py finalize
```

## Reproducibility note

The original frozen revision scripts are retained unchanged in the manuscript reproducibility archive.

The GitHub-facing copies are intended to remove workstation-specific absolute paths and use portable project-relative paths. These portability changes do not alter the study definitions, statistical models, transformations, fixed random seed, or analytical decision rules.
