# Pre-publication repository safety review

Audit date: 2026-11-23 (Asia/Shanghai). Baseline commit:
`3ddde51a62559787261accf4e20e143e616b0b73`.

This review concerns the local reachable Git history and the proposed working
tree. It does not authorize pushing, publishing a Release, changing repository
visibility, selecting a code license, or rewriting history.

## Inspected scope and method

The baseline contains 137 tracked paths. All 10 locally reachable commits were
enumerated with `git rev-list --all`; all 137 reachable unique file blobs were
read through `git cat-file`. The checkout is not shallow. Their total size is
2,646,004 bytes; the largest blob is 438,283 bytes. One PNG is binary; other
blob contents were inspected as text. Unreachable objects, remote-only refs,
GitHub issues, CI caches, and external download caches are outside this scope.

Pattern scans covered OpenAI-style keys, GitHub token formats, AWS access keys,
private-key markers and quoted assignments of passwords/API credentials. The
scan found **zero matching credential candidates**. This bounded scan is not a
proof that arbitrary secrets cannot exist. No sensitive correspondence filename,
raw ZIP/RDS/Parquet input, installed environment, tracked workspace, or object
larger than 5 MB was found. Public scientific notes mentioning reviewer requests
are present; no private response letter or editorial decision letter was found.

The evidence inventory and reproducible scan script are retained locally in
ignored `work/security_inventory.json` and `work/security_audit.py`. Candidate
values are redacted. The scientific source manifest remains unchanged.

## Player-level and fine-grained information

Raw player-day monitoring records are not tracked. However, the repository
already contains linkable anonymized player identifiers and health-event
summaries. Four tracked CSV tables have a `player_id` or `excluded_player` field:

| File under `reproducibility/frozen/` | Rows | Information |
|---|---:|---|
| `05_SAMPLE_EVENT_AUDIT/EVENTS_BY_PLAYER.csv` | 100 | Player-level event counts and team/season summaries |
| `14_EVENT_INFLUENCE/EVENT_CONCENTRATION.csv` | 24 | Event-player concentration and episode counts |
| `14_EVENT_INFLUENCE/LEAVE_ONE_EVENT_PLAYER_OUT_QA.csv` | 153 | Player-linked exclusion fits and retained sample/event counts |
| `14_EVENT_INFLUENCE/LOO_EXCLUSION_SUMMARY.csv` | 18 | Player-linked exclusion and event counts |

Thirteen reachable text blobs contain full source-style anonymized player UUIDs.
Some other tables, code comments, model registry labels and verification notes
also identify an excluded high contributor by a full or shortened identifier.
These are granular derived health summaries, not merely anonymous aggregate
regression coefficients. Their presence must be evaluated explicitly for the
public release; anonymization is not a redistribution license.

The public [Zenodo record](https://zenodo.org/records/10033832) was read on the
audit date. Its HTML view did not expose the license identifier and direct
Zenodo API connections failed. A subsequent successful retrieval from the
[DataCite DOI registry](https://api.datacite.org/dois/10.5281/zenodo.10033832)
explicitly records **CC BY 4.0**. This resolves the previously missing license
metadata; the audit does not infer rights merely from download availability.
`docs/DATA_REUSE.md` supplies creator attribution, the source DOI and license,
a description of transformations, and a disclosure that frozen event/influence
tables retain linkable anonymized source identifiers. Frozen files and history
were preserved. No reidentification was attempted.

## Third-party materials, software and license choice

No bundled installed Python/R libraries or cached third-party articles/screenshots
were found in the tracked baseline. The retained polarity notes cite external
evidence; the cached originals are not included. Analysis files are project
scripts with source hashes, but no rights-holder attestation or code license
has been supplied. The initial pass assigned no software license. The rights holders subsequently
authorized the MIT license for project-owned code; LICENSE now records the
approved attribution. Third-party source-data terms remain separate.

Code-license authority was confirmed by the author on 2026-11-23. Before assigning one, confirm ownership
of the project code and any contributions and identify applicable source-data
and reused-material terms. The paper citation, source-dataset attribution, code
license and data license are distinct records; one should not be substituted
for another.

## Local paths and identity metadata

One preserved historical source comment contains a Windows home-directory account
path: `analysis/sensitivity/20_FREEZE/build_freeze_outputs.py`, line 3. Generic
historical project roots also remain throughout frozen source scripts and are
relocated only in ignored execution copies. They are disclosed portability
artifacts; no current user's macOS home path was found in baseline blob text.
The account path was not edited because doing so would change an imported frozen
source hash. Its disclosure should be considered before a public release.

The 10 reachable commits contain three distinct author/committer email addresses,
including addresses outside GitHub's `users.noreply.github.com` domain. These
are ordinary Git identity metadata rather than credentials. Their values are
not repeated here. Review whether their public exposure is intended; deleting
a working-tree file would not remove metadata from existing commits.

## Ignore rules and checks

Existing rules exclude `workspace/`, `.venv/`, raw archives, Office/PDF inputs,
environment files and R state. The update also excludes `work/`, cache and
coverage folders, logs, common private-key containers, credential/service-account
JSON files, and local `renv` libraries. `git check-ignore` confirmed exclusion of
representative fresh datasets, private audit files, environment files, caches,
credentials and a private-key filename. Ignore patterns do not protect a file
already tracked in history.

The added data-free CI job checks source hashes, fingerprint inventory and
adversarial verifier cases (missingness, failed fits, row keys, counts, duplicate
bootstrap IDs, incomplete execution provenance and workspace escape/reuse).
It does not claim a model refit or a full bootstrap run.

## Release gate

The code-license and identity-disclosure decisions are now resolved by explicit
author authorization. Source-data CC BY 4.0 attribution is retained. The first
private audit commit used an automatic local-account identity; the author
confirmed it contains no credentials and may be public. Subsequent commits
use the verified GitHub identity; no history rewrite or force push occurred.
Statistical limits are documented in FOLLOW_UP_VERIFICATION.md. Remote CI and
the final release gate must pass before changing visibility or issuing a
formal Release.

## Final proposed-file scan

The final candidate contains 157 paths (20 new files plus the
137 baseline paths, including modified documents/tools). A second scan of
all proposed contents found zero token/private-key/current-account-path
candidates and no file larger than 5 MB. Fresh data and dependency environments
remain ignored. Discrepancy ledgers retain the public source identifiers under
the same data-attribution notice; they are not new raw monitoring releases.
