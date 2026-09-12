# SoccerMon Load–Wellness Monitoring and Lower-Limb Pain

Reproducible within-player analysis of training load, wellness, and next-day self-reported lower-limb pain in elite female football using the public SoccerMon dataset.

## Overview

This repository contains the reproducible analysis workflow for a longitudinal secondary analysis of the SoccerMon dataset.

The study examines whether within-player deviations in training load and wellness are associated with subsequent lower-limb pain onset in elite female football players.

Rather than treating athlete monitoring variables as fixed between-player characteristics, the analysis focuses on day-to-day changes within individual players.

## Study Design

The analysis is based on longitudinal player-day data from the publicly available SoccerMon dataset.

The workflow includes:

- reconstruction of player-day observations
- identification of recurrent lower-limb pain episodes
- acute and chronic training-load derivation
- within-player standardization of load and wellness variables
- mixed-effects and sparse-data modelling
- whole-player bootstrap analyses
- missing-data and weighting analyses
- sensitivity analyses using alternative exposure and standardization strategies

## Methodological Focus

A central aim of the study is to evaluate whether apparent load–wellness associations are robust to analytical choices.

Particular attention is given to:

**Within-player exposure definition**  
Training load and wellness are interpreted relative to each player's own longitudinal distribution.

**Sparse outcome data**  
The analysis includes diagnostics and modelling strategies designed for a small number of onset events.

**Standardization strategy**  
The robustness of focal estimates is examined under alternative within-player standardization approaches, including approaches restricted to information available before each observation.

**Reproducibility**  
The analysis package includes structured scripts, model registries, validation outputs, and numerical consistency checks.

## Data

The study uses the publicly available SoccerMon dataset.

Raw source data will not be redistributed in this repository. Data-access information and instructions for reproducing the analytical dataset will be documented separately.

## Repository Status

This repository is currently being prepared from the frozen reproducibility package associated with the revised manuscript.

The public release will include:

- analysis scripts
- reproducibility documentation
- figure-generation workflows
- key derived results
- validation records
- software environment information

## Citation

Citation information will be added when the associated article or preprint becomes publicly available.

## Contact

**Yushuo Liu**  
MSc researcher in Sport Training Science  
Yunnan Normal University

GitHub: [YUSHUO-LIU6](https://github.com/YUSHUO-LIU6)
