# Data

Source: SoccerMon, DOI [10.5281/zenodo.10033832](https://doi.org/10.5281/zenodo.10033832).
Only `subjective.zip` is required. The objective/GPS archives are not used.
Raw data are not committed to this repository.

Expected `subjective.zip` SHA-256:

```text
338e9878fbed1f941cfc37b3f012cb356f97cc0f726e80a79aa5c8e67cc2a87c
```

`scripts/pipeline.py rebuild` verifies the hash before extraction. Downloaded
and derived player-level data stay in the ignored `workspace/` directory.
Supply an existing copy with `--raw-zip /path/to/subjective.zip`.

`reproducibility/data_fingerprints.json` contains order-sensitive column
digests of six frozen derived files, not the player-level records themselves.
The source dataset's terms and attribution remain applicable.
