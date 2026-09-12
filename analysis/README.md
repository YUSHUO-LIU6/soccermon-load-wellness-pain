# Analysis

This directory contains the analysis workflow for the SoccerMon load–wellness and lower-limb pain study.

The public GitHub-facing workflow is being organized from the frozen reproducibility package used for the revised manuscript. The original frozen archive is preserved separately; scripts placed here are intended to provide a clearer and more portable representation of the analytical workflow.

## Workflow overview

The analysis proceeds through the following stages:

### 1. Raw-data audit and player-day reconstruction

- verify the public SoccerMon source files
- reconstruct the complete player-day grid
- check dates, players, duplicates, and variable ranges

### 2. Episode reconstruction and analytical dataset

- reconstruct recurrent lower-limb pain episodes
- define onset days and the at-risk population
- derive lagged acute and chronic training-load exposures
- construct within-player wellness measures

### 3. Missing-data assessment

- quantify wellness-data missingness
- fit observation models
- construct inverse-probability-of-observation weights
- evaluate weight distributions and effective sample sizes

### 4. Primary statistical analysis

- fit the prespecified within-player models
- evaluate load, wellness, and load × wellness terms
- use sparse-data methods where conventional estimation is unstable

### 5. Uncertainty analysis

- perform whole-player bootstrap analyses
- retain athlete-level dependence during resampling
- quantify uncertainty around focal estimates

### 6. Sensitivity and robustness analyses

- sample and event audit
- sparse-data diagnostics
- acute–chronic load collinearity
- non-overlapping exposure windows
- team sensitivity
- season stability
- backward-looking within-player standardization
- inverse-probability weighting
- event-player influence analysis

### 7. Validation and final consistency checks

- reconcile raw and derived datasets
- compare reproduced and frozen results
- verify manuscript-facing numerical results
- freeze and hash the final analytical state

## Code organization

The final GitHub-facing analysis code will be organized into:

```text
analysis/
├── core/
│   ├── data reconstruction
│   ├── episode construction
│   ├── missingness
│   ├── primary modelling
│   └── bootstrap analysis
│
└── sensitivity/
    ├── sparse-data diagnostics
    ├── collinearity
    ├── non-overlap window
    ├── team and season sensitivity
    ├── backward standardization
    ├── IPW
    └── event influence
```

## Important note

The manuscript revision archive preserves the original scripts exactly as executed in the frozen analysis. Some frozen scripts contain workstation-specific absolute paths.

For the public repository, these paths will be replaced with project-relative paths without changing the underlying statistical specifications, transformations, or analytical logic.

The original frozen submission archive will remain available separately for provenance.
