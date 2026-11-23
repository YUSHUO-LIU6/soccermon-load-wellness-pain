# Published-source and preregistration reconciliation

Audit date: 2026-11-23, Asia/Shanghai. This is a source comparison; it is not
proof of a new model run. The original records were preserved unchanged.

## Publication and downloaded evidence

Liu Y, Li H (2026). *Within-player load-wellness monitoring and lower-limb pain
in elite female football: A reproducible secondary analysis of the SoccerMon
dataset*. PLOS ONE 21(11): e0362663. Published 2026-11-13.
[Article](https://doi.org/10.1371/journal.pone.0362663).
The publisher HTML/XML, supporting tables and S2/S3 were retrieved. Citation
metadata in CITATION.cff follows the publisher record.

[S2 archive](https://doi.org/10.1371/journal.pone.0362663.s014): 8,300,907
bytes, 181 file members, SHA-256
`d9c9d3cbfa31bd56717ff5c3c925ebe8f74c14062498f0f4ab0bda9d65594577`.
ZIP CRC testing passed. Against the 101 rows of the repository source manifest,
91 files are byte-identical to S2, five core files differ through documented
portability edits and match the manifest's original hashes, and five entries
are not present in S2: four frozen revision-SAP files and the repository's
wellness-polarity evidence note. A first automatic path mapping missed the
figure script; direct member inspection confirmed its exact byte identity.
The corrected mapping is archived in the source-comparison evidence.

The repository is a subset of S2, not a mirror. S2 additionally contains derived
player-day inputs, IPW working files, historical raw-rebuild diagnostics/logs,
archive integrity files, reporting/assembly scripts and manuscript-production
utilities. The omission of local datasets is intentional. Missing reporting
utilities limit automatic recreation of the final submitted layout; they do
not imply that all scientific model source is absent. Unimported files were
not silently copied into the release candidate. Six core datasets and two
sensitivity datasets have independent frozen reconstruction fingerprints.

## Published numerical displays

A selected 623 field comparisons of Table 2, Table 3 and numerical sections of
S5–S9 against frozen structured outputs passed at the precision printed in the
published displays. Comparisons use half a last printed decimal unit, or the
printed inequality for threshold p values. These checks include Firth,
recurrent-event, washout, risk-set, ACWR, strict-lag, high-contributor, team,
season/backward-looking, bootstrap and IPW displays where mapped. They do not
constitute an exhaustive check of every sentence, every cell or publisher
figure layout. Table 1/main-text counts were separately checked against the
raw rebuild; selected graphic data are checked during fresh figure execution.
`PUBLISHED_FROZEN_COMPARISON.csv` preserves the 623 comparisons. All of these
are publication-versus-frozen checks; fresh-versus-frozen acceptance is in
`RESULT_COMPARISON.csv`.

## OSF registry, registered attachment and published protocol

The [OSF registration API](https://api.osf.io/v2/registrations/uafwq/) was
retrieved successfully. It reports a public, unwithdrawn preregistration dated
2026-05-29T13:38:23.822848, with identical original/latest schema-response IDs.
The archived attachment was listed and downloaded through the registration's
file API. Its SHA-256, independently matching the OSF file metadata, is
`52fecc26880fce09c5b798bb04cb9f8614fb21126c95e3f61e4701e2e19483b2`.
The [published S3 protocol](https://doi.org/10.1371/journal.pone.0362663.s015)
is **byte-identical to this registered attachment**. The attachment is a
five-page scanned protocol; its model, lag and simplification sections were
visually inspected. There is no evidence here that the published attachment
was substituted after registration.

However, the registry's structured answers and its attached protocol are not
identical specifications. The structured statistical-model/inference answers
(344-71, 344-77, 344-83) describe interaction analyses as secondary/exploratory
unless event information permits stable estimation; the attached protocol
section 8 prespecifies an acute-load × soreness interaction model but retains
main effects as primary if the interaction is unstable. The attachment also
specifies more precise lag windows, a more detailed fallback sequence, and a
conservative unreported-load sensitivity not fully repeated in the structured
missingness answer (344-81). Both records must be cited when discussing what
was registered. The published S10 reconciliation is primarily aligned with
the attachment, and should not erase these structured-form qualifications.

The frozen 2026-07-22 revision SAP, R1 implementation, later R2 analyses and
post-publication software checks remain separate. Final Firth emphasis is not
the original primary mixed-model estimator. The observed calendar grid,
separate wellness families, model-dependent fallback, missing-load limitation
and later exposure sensitivities are documented deviations/choices; none was
retroactively inserted into the original protocol. Full-period scaling is
retrospective, the outcome is self-reported and the findings are associational.

## GitHub baseline coverage before delivery

The local baseline has 137 tracked paths at commit
`3ddde51a62559787261accf4e20e143e616b0b73`. Connected GitHub metadata/file
APIs returned 404 and unauthenticated Git inspection failed. The authenticated
local `gh` CLI subsequently succeeded: at that baseline check the repository
was **private**, default
branch `main`, with the same commit SHA as the local baseline. All 137 remote
file-blob SHAs match `git ls-tree -r HEAD`; the recursive tree is not truncated.
This resolves the connector-access limitation. The remote/local baseline and
S2 comparison therefore concerns the same observed main-branch contents.
Branch/tag inventories were recorded in local evidence before delivery.
Subsequent verified work is delivered through PR #1 and the release profile;
this baseline/S2 comparison is not a claim that the delivered main branch
remains at 3ddde51.
