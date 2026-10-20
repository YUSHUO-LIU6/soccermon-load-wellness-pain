#!/usr/bin/env Rscript
# ============================================================================
# run_ipw_final.R — IPW workstream, PLOS ONE R2 reproducibility freeze (9.9)
# PONE-D-26-31950 (SoccerMon). Weighted outcome models for the two
# observation-model variants:
#   onset     : weights = existing R1 run files RUN_R2_REPRO/ipw_weights_<v>.csv
#               (taxonomy R1_REVISION_SAP; refit here is a verification of the
#               frozen master_results.csv IPW rows)
#   nooutcome : weights = FR/13_IPW_FINAL/ipw_weights_nooutcome_<v>.csv
#               (taxonomy R2_REVIEWER_REQUESTED; NEW sensitivity, observation
#               model refit without onset_day — no R1 counterpart exists)
# Machinery mirrors 06_ANALYSIS_CODE/04_run_reanalysis.R IPW block exactly:
#   cc_sample() complete-case definition, key-based weight merge, NA drop,
#   glm(binomial, weights) + clubSandwich::vcovCR(type="CR2", cluster=player_id)
#   + lmtest::coeftest.
# Output: FR/13_IPW_FINAL/ipw_final_r_results.csv
# Writes ONLY under FR/13_IPW_FINAL/. Seed 20260722 (no randomness; recorded).
# ============================================================================

suppressPackageStartupMessages({
  library(clubSandwich)
  library(sandwich)
  library(lmtest)
})

SEED <- 20260722
set.seed(SEED)

FR  <- "D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE"
SB  <- file.path(FR, "02_R1_REPRODUCTION", "r1_sandbox")
RUN <- file.path(SB, "07_ANALYSIS_OUTPUTS", "RUN_R2_REPRO")
OUTDIR <- file.path(FR, "13_IPW_FINAL")

log_msg <- function(...) cat(paste0(format(Sys.time(), "%H:%M:%S"), " | ",
                                    paste(..., collapse = ""), "\n"))

md <- read.csv(file.path(SB, "07_ANALYSIS_OUTPUTS", "modeling_dataset.csv"),
               stringsAsFactors = FALSE)
md$date <- as.Date(md$date)
md$team <- factor(md$team)
md$season <- factor(md$season)
md$player_id <- factor(md$player_id)
log_msg("modeling_dataset: ", nrow(md), " rows; onset_day positives = ",
        sum(md$onset_day), "; players = ", length(unique(md$player_id)))

WELL <- c(soreness  = "soreness_burden_recent3_wp_z",
          fatigue   = "fatigue_burden_recent3_wp_z",
          readiness = "readiness_deficit_recent3_wp_z")

mk_formula <- function(wcol) {
  as.formula(paste0("onset_day ~ acute_load_7d_wp_z * ", wcol,
                    " + chronic_load_28d_wp_z + prev_episode_ever",
                    " + calendar_time + team + season"))
}

cc_sample <- function(d, wcol) {
  # identical to 04_run_reanalysis.R cc_sample(): days_since_last_episode
  # excluded by design (NA when no previous episode; not a model covariate)
  vars <- c("onset_day", "acute_load_7d_wp_z", wcol, "chronic_load_28d_wp_z",
            "prev_episode_ever", "calendar_time", "team", "season",
            "player_id", "date", "prev_episode_count")
  d[complete.cases(d[, vars]), ]
}

res_rows <- list()
k <- 0
for (variant in c("onset", "nooutcome")) {
  wdir <- if (variant == "onset") RUN else OUTDIR
  wpat <- if (variant == "onset") "ipw_weights_%s.csv" else
    "ipw_weights_nooutcome_%s.csv"
  for (v in names(WELL)) {
    wf <- file.path(wdir, sprintf(wpat, v))
    if (!file.exists(wf)) { log_msg("MISSING weights: ", wf); next }
    w <- read.csv(wf, stringsAsFactors = FALSE)
    d <- cc_sample(md, WELL[[v]])
    n_pre <- nrow(d)
    key <- paste(d$player_id, d$date)
    wkey <- paste(w$player_id, w$date)
    stopifnot(!anyDuplicated(wkey))
    d$ipw <- w$w_stab_trunc[match(key, wkey)]
    n_na_w <- sum(is.na(d$ipw))
    d <- d[!is.na(d$ipw), ]
    f <- mk_formula(WELL[[v]])
    g <- glm(f, data = d, family = binomial, weights = ipw)
    V <- vcovCR(g, cluster = d$player_id, type = "CR2")
    ct <- coeftest(g, vcov. = V)
    ess <- sum(d$ipw)^2 / sum(d$ipw^2)
    log_msg(variant, " / ", v, ": n=", nrow(d), " (CC pre weight drop=",
            n_pre, ", dropped no weight=", n_na_w, "), players=",
            length(unique(d$player_id)), ", events=", sum(d$onset_day),
            ", ESS=", round(ess, 1), " (ESS/n=", round(ess / nrow(d), 3),
            "), max w=", round(max(d$ipw), 3))
    for (tm in rownames(ct)) {
      k <- k + 1
      res_rows[[k]] <- data.frame(
        obs_model_variant = variant, wellness_variant = v, term = tm,
        OR = exp(ct[tm, 1]),
        CI_low = exp(ct[tm, 1] - 1.96 * ct[tm, 2]),
        CI_high = exp(ct[tm, 1] + 1.96 * ct[tm, 2]),
        p = ct[tm, 4], se = ct[tm, 2], converged = TRUE,
        optimizer = "glm binomial weighted + clubSandwich CR2 cluster(player)",
        n = nrow(d), players = length(unique(d$player_id)),
        events = sum(d$onset_day),
        event_players = length(unique(d$player_id[d$onset_day == 1])),
        n_cc_pre_weight_drop = n_pre, n_cc_dropped_no_weight = n_na_w,
        ess_trunc_cc_sample = ess, ess_over_n_cc_sample = ess / nrow(d),
        max_w_trunc_cc = max(d$ipw),
        stringsAsFactors = FALSE)
    }
  }
}

res <- do.call(rbind, res_rows)
write.csv(res, file.path(OUTDIR, "ipw_final_r_results.csv"),
          row.names = FALSE)
log_msg("wrote ipw_final_r_results.csv (", nrow(res), " term rows)")
