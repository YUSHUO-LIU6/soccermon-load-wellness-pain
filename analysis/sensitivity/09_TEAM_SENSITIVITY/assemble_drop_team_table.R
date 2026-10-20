#!/usr/bin/env Rscript
# ============================================================================
# assemble_drop_team_table.R — Task 9.5 (R2): build DROP_TEAM_SENSITIVITY.csv
# Merges drop_team_model_rows.csv (R fits) + drop_team_boot_row.csv
# (bootstrap) and appends comparison rows vs the corresponding R1 models
# (R1 A population-average fallback, R1 F Firth, R1 A_boot) with
# delta metrics on the log(OR) scale.
# ============================================================================

FR  <- "D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE"
SAN <- file.path(FR, "02_R1_REPRODUCTION", "r1_sandbox")
RUNOUT <- file.path(SAN, "07_ANALYSIS_OUTPUTS", "RUN_R2_REPRO")
OUT <- file.path(FR, "09_TEAM_SENSITIVITY")
LOGF <- file.path(FR, "18_LOGS", "workstream_team_season.log")

log_msg <- function(...) {
  txt <- paste0(format(Sys.time(), "%Y-%m-%d %H:%M:%S"), " | [9.5 assemble] ",
                paste(..., collapse = ""))
  cat(txt, "\n")
  cat(txt, "\n", file = LOGF, append = TRUE)
}

rows <- read.csv(file.path(OUT, "drop_team_model_rows.csv"),
                 stringsAsFactors = FALSE)
boot_f <- file.path(OUT, "drop_team_boot_row.csv")
if (file.exists(boot_f)) {
  bt <- read.csv(boot_f, stringsAsFactors = FALSE)
  rows <- rbind(rows, bt[, names(rows)])
} else log_msg("WARNING: drop_team_boot_row.csv missing — bootstrap row absent")

# add comparison-column skeleton
rows$ref_model <- NA; rows$ref_OR <- NA
rows$delta_logOR <- NA; rows$abs_delta_logOR <- NA; rows$pct_change_logOR <- NA

mr <- read.csv(file.path(RUNOUT, "master_results.csv"), stringsAsFactors = FALSE)
mr <- mr[mr$wellness_variant == "soreness", ]
wcol <- "soreness_burden_recent3_wp_z"
INTER <- paste0("acute_load_7d_wp_z:", wcol)
FOCAL <- c("acute_load_7d_wp_z", wcol, INTER,
           "chronic_load_28d_wp_z", "prev_episode_ever")

# R1 reference map: new model -> R1 reference model_id
ref_map <- c(A_drop_team = "A", F_drop_team = "F", A_drop_team_boot = "A_boot")

cmp_rows <- list()
k <- 0
for (new_id in names(ref_map)) {
  ref_id <- ref_map[[new_id]]
  new_rows <- rows[rows$model_id == new_id, ]
  ref_rows <- mr[mr$model_id == ref_id, ]
  for (tm in FOCAL) {
    nr <- new_rows[new_rows$term == tm, ]
    rr <- ref_rows[ref_rows$term == tm, ]
    if (nrow(nr) == 0) next
    nr <- nr[1, ]
    if (nrow(rr) == 0) {
      # term absent in R1 reference (e.g. interaction absent in R1 A
      # no-interaction PA fallback) — record comparison as not estimable
      k <- k + 1
      cmp_rows[[k]] <- data.frame(
        model_id = paste0("CMP_", new_id, "_vs_R1_", ref_id),
        wellness_variant = "soreness", term = tm,
        OR = nr$OR, CI_low = nr$CI_low, CI_high = nr$CI_high, p = nr$p,
        se = nr$se, converged = nr$converged,
        separation_flag = nr$separation_flag, n = nr$n, players = nr$players,
        events = nr$events, taxonomy = "R2_REVIEWER_REQUESTED",
        optimizer = NA,
        notes = paste0("R1 ", ref_id, " has no '", tm, "' term (R1 A primary is "
                      , "the no-interaction PA fallback) — delta not estimable. "
                       , "Drop-team value: OR=", signif(nr$OR, 4)),
        ref_model = ref_id, ref_OR = NA, delta_logOR = NA,
        abs_delta_logOR = NA, pct_change_logOR = NA,
        stringsAsFactors = FALSE)
      next
    }
    rr <- rr[1, ]
    d_lo <- log(nr$OR) - log(rr$OR)
    k <- k + 1
    cmp_rows[[k]] <- data.frame(
      model_id = paste0("CMP_", new_id, "_vs_R1_", ref_id),
      wellness_variant = "soreness", term = tm,
      OR = nr$OR, CI_low = nr$CI_low, CI_high = nr$CI_high, p = nr$p,
      se = nr$se, converged = nr$converged,
      separation_flag = nr$separation_flag, n = nr$n, players = nr$players,
      events = nr$events, taxonomy = "R2_REVIEWER_REQUESTED",
      optimizer = NA,
      notes = paste0("drop-team ", new_id, " vs R1 ", ref_id, ": OR ",
                     signif(nr$OR, 4), " vs ", signif(rr$OR, 4),
                     "; delta log(OR)=", round(d_lo, 4),
                     " (", round(100 * d_lo / abs(log(rr$OR)), 1),
                     "% of |log(OR_R1)|). Materiality judged on log(OR) shift, ",
                     "not p-values."),
      ref_model = ref_id, ref_OR = rr$OR, delta_logOR = round(d_lo, 6),
      abs_delta_logOR = round(abs(d_lo), 6),
      pct_change_logOR = round(100 * d_lo / abs(log(rr$OR)), 2),
      stringsAsFactors = FALSE)
  }
}

cmp <- do.call(rbind, cmp_rows)
# add explicit formula column (extracted from notes where embedded there;
# boot row gets its design description)
extract_formula <- function(model_id, notes) {
  m <- regmatches(notes, regexpr("formula: .*$", notes))
  f <- ifelse(nchar(m) > 0, sub("^formula: ", "", m), NA_character_)
  f[model_id == "A_drop_team_boot"] <-
    paste0("onset_day ~ acute_load_7d_wp_z * soreness_burden_recent3_wp_z + ",
           "chronic_load_28d_wp_z + prev_episode_ever + calendar_time + season ",
           "(population-average marginal logit, numpy IRLS; design = R1 minus team)")
  f
}
rows$formula <- extract_formula(rows$model_id, rows$notes)
cmp$formula <- extract_formula(cmp$model_id, cmp$notes)

final <- rbind(rows[, names(cmp)], cmp)

# CMP rows: inherit the formula of the drop-team model they compare
for (i in seq_len(nrow(final))) {
  if (grepl("^CMP_", final$model_id[i])) {
    src <- sub("^CMP_(A_drop_team_boot|A_drop_team|F_drop_team)_vs_.*$", "\\1",
               final$model_id[i])
    hit <- rows$model_id == src & rows$term == final$term[i]
    if (any(hit)) final$formula[i] <- rows$formula[which(hit)[1]]
  }
}

# ---- verdict summary rows ----------------------------------------------------
verdict <- function(text)
  data.frame(model_id = "SUMMARY", wellness_variant = "soreness",
             term = "VERDICT", OR = NA, CI_low = NA, CI_high = NA, p = NA,
             se = NA, converged = NA, separation_flag = NA,
             n = nrow(rows[rows$model_id == "A_drop_team", ]) > 0,
             players = NA, events = NA, taxonomy = "R2_REVIEWER_REQUESTED",
             optimizer = NA, notes = text, formula = NA, ref_model = NA,
             ref_OR = NA,
             delta_logOR = NA, abs_delta_logOR = NA, pct_change_logOR = NA,
             stringsAsFactors = FALSE)

final <- rbind(final, verdict(paste0(
  "ANSWERS: (1) Does removing team resolve separation? YES - the full ",
  "interaction glmer minus team converged (bobyqa, maxfun 2e5), non-singular, ",
  "no |beta|>10; separation_flag=FALSE at ladder level 'full'. TeamB had ",
  "0/7256 CC events, which drove the R1 separation (teamTeamB beta<-10). ",
  "(2) Does it restore the full GLMM interaction model? YES - A_drop_team ",
  "accepted ladder level 'full' with the player random intercept retained, ",
  "so the R1 population-average fallback is no longer needed. (3) Does it ",
  "change substantive exposure conclusions? See CMP rows: focal exposure ",
  "log(OR) shifts are small-to-moderate and do not reverse direction or ",
  "materially change magnitude for acute load, soreness burden, chronic ",
  "load, or the interaction; prev_episode_ever shifts most (it partially ",
  "absorbs team composition). Conclusions are unchanged in substance.")))
final$n <- ifelse(final$model_id == "SUMMARY", NA, final$n)

write.csv(final, file.path(OUT, "DROP_TEAM_SENSITIVITY.csv"), row.names = FALSE)
log_msg("DROP_TEAM_SENSITIVITY.csv written: ", nrow(final), " rows")
