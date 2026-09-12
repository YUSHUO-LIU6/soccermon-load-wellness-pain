# Portable core-analysis staging bundle

These five scripts are derived from the frozen PLOS ONE revision workflow.
Only path/bootstrap setup and optional frozen-reference checks were adapted for
GitHub portability. Statistical formulas, exposure definitions, seeds, and
model logic were not intentionally changed.

## Default workspace

When the scripts are stored in `analysis/core/`, they use:

`<repository>/workspace/`

as the default working directory. You can override this by setting the
`SOCCERMON_WORKSPACE` environment variable. The workspace is intentionally
separate from the tracked GitHub files and should not be committed.

Expected raw-data location after downloading and extracting the public
SoccerMon archive:

`workspace/02_RAW_DATA/subjective_readonly_work/subjective/`

## Optional provenance-only reference files

`01_raw_audit_and_rebuild.py` and `02_episodes_and_modeling_data.py` originally
compared rebuilt outputs against frozen historical reference files. Those files
are not needed to construct the revised analytical dataset. In these public-
facing copies, the comparisons are skipped cleanly if the references are not
supplied. Optional paths can be provided through:

- `SOCCERMON_OLD_DERIVED`
- `SOCCERMON_FROZEN_EPISODES`

## Run identifier

If `workspace/RUN_ID.txt` does not exist, the scripts use `RUN_PUBLIC` and
create the file automatically. Override with `SOCCERMON_RUN_ID`.

## Important

This is a GitHub-facing portability layer, not a replacement for the frozen
submission archive. Keep the frozen archive unchanged for provenance. Before
public release, the portable workflow should receive one final end-to-end
validation against the frozen outputs.
