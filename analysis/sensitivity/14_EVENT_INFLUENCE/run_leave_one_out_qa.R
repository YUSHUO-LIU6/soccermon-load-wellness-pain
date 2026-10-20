#!/usr/bin/env Rscript
# ============================================================================
# run_leave_one_out_qa.R — R2 freeze plan section 9.10
# PONE-D-26-31950 (SoccerMon) R2 reproducibility freeze.
#
# Symmetric leave-one-event-player-out QA on the PRIMARY soreness
# complete-case sample (n=19,758; 28 onset-days; 9 event players).
# For each of the 9 event players, refit on the remaining CC rows:
#   (a) population-average logistic — SAME no-interaction fallback formula as
#       the R1 primary Model A PA fallback:
#         onset_day ~ acute_load_7d_wp_z + soreness_burden_recent3_wp_z
#                     + chronic_load_28d_wp_z + prev_episode_ever
#                     + calendar_time + team + season
#       with clubSandwich CR2 cluster(player_id) SEs;
#   (b) full-interaction Firth (logistf) — same full formula as R1 Model F:
#         onset_day ~ acute_load_7d_wp_z * soreness_burden_recent3_wp_z + ...
# All fits recorded; failures/separation are recorded, never omitted.
#
# Taxonomy: R2_INTERNAL_QA_ONLY. Seed 20260722 (fixed; no stochastic steps).
# Output: LEAVE_ONE_EVENT_PLAYER_OUT_QA.csv (one row per
#         excluded_player x model x term), plus EXCLUSION_SUMMARY.csv
#         (one row per excluded_player x model).
# ============================================================================

suppressPackageStartupMessages({
  library(clubSandwich)
  library(sandwich)
  library(lmtest)
  library(logistf)
})

SEED <- 20260722
set.seed(SEED)
TAXONOMY <- "R2_INTERNAL_QA_ONLY"

FR  <- "D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE"
SB  <- file.path(FR, "02_R1_REPRODUCTION", "r1_sandbox")
OUT <- file.path(FR, "14_EVENT_INFLUENCE")
dir.create(OUT, recursive = TRUE, showWarnings = FALSE)

SAFEGUARD <- paste(
  "28 CC onset-days / 9 event players = severe information limit;",
  "leave-one-out fits share almost all of the same 28 events;",
  "TeamB contributes 0 CC events so the team coefficient is degenerate",
  "(separation); nominal p<0.05 must never be called robust.")

md <- read.csv(file.path(SB, "07_ANALYSIS_OUTPUTS", "modeling_dataset.csv"),
               stringsAsFactors = FALSE)
md$date <- as.Date(md$date)
md$team <- factor(md$team); md$season <- factor(md$season)
md$player_id <- factor(md$player_id)

wcol <- "soreness_burden_recent3_wp_z"
cc_vars <- c("onset_day", "acute_load_7d_wp_z", wcol, "chronic_load_28d_wp_z",
             "prev_episode_ever", "calendar_time", "team", "season",
             "player_id", "date", "prev_episode_count")
cc <- md[complete.cases(md[, cc_vars]), ]
stopifnot(nrow(cc) == 19758, sum(cc$onset_day) == 28)

event_players <- sort(unique(as.character(cc$player_id[cc$onset_day == 1])))
stopifnot(length(event_players) == 9)

f_pa <- as.formula(paste0("onset_day ~ acute_load_7d_wp_z + ", wcol,
                          " + chronic_load_28d_wp_z + prev_episode_ever",
                          " + calendar_time + team + season"))
f_full <- as.formula(paste0("onset_day ~ acute_load_7d_wp_z * ", wcol,
                            " + chronic_load_28d_wp_z + prev_episode_ever",
                            " + calendar_time + team + season"))

# ---- full-sample reference estimates (from locked R1 reproduction) ---------
mr <- read.csv(file.path(SB, "07_ANALYSIS_OUTPUTS", "RUN_R2_REPRO",
                         "master_results.csv"), stringsAsFactors = FALSE)
ref_pa <- mr[mr$model_id == "A" & mr$wellness_variant == "soreness", ]
ref_f  <- mr[mr$model_id == "F" & mr$wellness_variant == "soreness", ]
ref_or <- function(ref, term) {
  r <- ref[ref$term == term, "OR"]
  if (length(r) == 0) NA_real_ else r[1]
}

res_rows <- list()
sum_rows <- list()
k <- 0

for (xp in event_players) {
  d <- cc[as.character(cc$player_id) != xp, ]
  d$player_id <- factor(as.character(d$player_id))
  n_ev  <- sum(d$onset_day)
  n_evp <- length(unique(d$player_id[d$onset_day == 1]))
  xp_ev <- sum(cc$onset_day[as.character(cc$player_id) == xp])

  # ---------------- (a) population-average glm + CR2 ------------------------
  g <- tryCatch(glm(f_pa, data = d, family = binomial), error = function(e) e)
  if (inherits(g, "error")) {
    k <- k + 1
    res_rows[[k]] <- data.frame(
      taxonomy = TAXONOMY, excluded_player = xp, model = "PA_CR2",
      term = NA_character_, OR = NA, CI_low = NA, CI_high = NA, p = NA,
      se = NA, n = nrow(d), players = length(unique(d$player_id)),
      events = n_ev, event_players = n_evp, converged = FALSE,
      separation_flag = NA, separated_terms = NA,
      full_sample_OR = NA, delta_logOR = NA, pct_change_OR = NA,
      notes = paste("FIT FAILED:", conditionMessage(g), "--", SAFEGUARD),
      stringsAsFactors = FALSE)
  } else {
    V <- tryCatch(vcovCR(g, cluster = d$player_id, type = "CR2"),
                  error = function(e) e)
    if (inherits(V, "error")) {
      ct <- summary(g)$coefficients
      se_col <- ct[, 2]; p_col <- ct[, 4]
      se_note <- paste("CR2 vcov FAILED (", conditionMessage(V),
                       ") — model-based SEs reported instead;")
    } else {
      ct <- coeftest(g, vcov. = V)
      se_col <- ct[, 2]; p_col <- ct[, 4]
      se_note <- ""
    }
    b <- ct[, 1]
    sep <- any(abs(b) > 10)
    sep_terms <- if (sep) paste(rownames(ct)[abs(b) > 10], collapse = " || ") else ""
    for (tm in rownames(ct)) {
      r0 <- ref_or(ref_pa, tm)
      k <- k + 1
      res_rows[[k]] <- data.frame(
        taxonomy = TAXONOMY, excluded_player = xp, model = "PA_CR2",
        term = tm, OR = exp(b[tm]),
        CI_low = exp(b[tm] - 1.96 * se_col[tm]),
        CI_high = exp(b[tm] + 1.96 * se_col[tm]),
        p = p_col[tm], se = se_col[tm],
        n = nrow(d), players = length(unique(d$player_id)),
        events = n_ev, event_players = n_evp, converged = TRUE,
        separation_flag = sep, separated_terms = sep_terms,
        full_sample_OR = r0,
        delta_logOR = if (is.na(r0)) NA_real_ else b[tm] - log(r0),
        pct_change_OR = if (is.na(r0)) NA_real_ else (exp(b[tm]) / r0 - 1) * 100,
        notes = paste(trimws(paste(se_note, "PA fallback formula (no",
                                   "interaction); player CR2 SEs.")), SAFEGUARD,
                      sep = " -- "),
        stringsAsFactors = FALSE)
    }
    sum_rows[[paste0(xp, "_PA")]] <- data.frame(
      taxonomy = TAXONOMY, excluded_player = xp,
      excluded_player_cc_events = xp_ev, model = "PA_CR2",
      n = nrow(d), players = length(unique(d$player_id)), events = n_ev,
      event_players = n_evp, converged = TRUE, separation_flag = sep,
      separated_terms = sep_terms,
      focal_acute_OR = exp(b["acute_load_7d_wp_z"]),
      focal_soreness_OR = exp(b[wcol]),
      interaction_OR = NA_real_,
      notes = SAFEGUARD, stringsAsFactors = FALSE)
  }

  # ---------------- (b) full-interaction Firth ------------------------------
  ff <- tryCatch(logistf(f_full, data = d), error = function(e) e)
  if (inherits(ff, "error")) {
    k <- k + 1
    res_rows[[k]] <- data.frame(
      taxonomy = TAXONOMY, excluded_player = xp, model = "firth_full",
      term = NA_character_, OR = NA, CI_low = NA, CI_high = NA, p = NA,
      se = NA, n = nrow(d), players = length(unique(d$player_id)),
      events = n_ev, event_players = n_evp, converged = FALSE,
      separation_flag = NA, separated_terms = NA,
      full_sample_OR = NA, delta_logOR = NA, pct_change_OR = NA,
      notes = paste("FIT FAILED:", conditionMessage(ff), "--", SAFEGUARD),
      stringsAsFactors = FALSE)
  } else {
    b <- ff$coefficients
    conv <- !any(is.na(b))
    for (tm in names(b)) {
      r0 <- ref_or(ref_f, tm)
      k <- k + 1
      res_rows[[k]] <- data.frame(
        taxonomy = TAXONOMY, excluded_player = xp, model = "firth_full",
        term = tm, OR = exp(b[tm]),
        CI_low = exp(ff$ci.lower[tm]), CI_high = exp(ff$ci.upper[tm]),
        p = ff$prob[tm], se = NA_real_,
        n = nrow(d), players = length(unique(d$player_id)),
        events = n_ev, event_players = n_evp, converged = conv,
        separation_flag = FALSE,
        separated_terms = "",
        full_sample_OR = r0,
        delta_logOR = if (is.na(r0)) NA_real_ else b[tm] - log(r0),
        pct_change_OR = if (is.na(r0)) NA_real_ else (exp(b[tm]) / r0 - 1) * 100,
        notes = paste("Firth penalised full-interaction; profile-likelihood",
                      "CIs; finite by construction under separation --",
                      SAFEGUARD),
        stringsAsFactors = FALSE)
    }
    iterm <- paste0("acute_load_7d_wp_z:", wcol)
    sum_rows[[paste0(xp, "_F")]] <- data.frame(
      taxonomy = TAXONOMY, excluded_player = xp,
      excluded_player_cc_events = xp_ev, model = "firth_full",
      n = nrow(d), players = length(unique(d$player_id)), events = n_ev,
      event_players = n_evp, converged = conv, separation_flag = FALSE,
      separated_terms = "",
      focal_acute_OR = exp(b["acute_load_7d_wp_z"]),
      focal_soreness_OR = exp(b[wcol]),
      interaction_OR = exp(b[iterm]),
      notes = SAFEGUARD, stringsAsFactors = FALSE)
  }
  cat(sprintf("[%s] excluded=%s (cc_events=%d) -> n=%d events=%d evp=%d\n",
              format(Sys.time(), "%H:%M:%S"), xp, xp_ev, nrow(d), n_ev, n_evp))
}

res <- do.call(rbind, res_rows)
summ <- do.call(rbind, sum_rows)
rownames(res) <- NULL; rownames(summ) <- NULL
write.csv(res, file.path(OUT, "LEAVE_ONE_EVENT_PLAYER_OUT_QA.csv"),
          row.names = FALSE)
write.csv(summ, file.path(OUT, "LOO_EXCLUSION_SUMMARY.csv"), row.names = FALSE)

# ---- console digest ----------------------------------------------------------
cat("\n=== LOO digest (firth_full interaction OR) ===\n")
ix <- res[res$model == "firth_full" &
          res$term == paste0("acute_load_7d_wp_z:", wcol), ]
print(ix[, c("excluded_player", "OR", "CI_low", "CI_high", "p",
             "pct_change_OR")], row.names = FALSE)
cat("\n=== LOO digest (PA_CR2 focal ORs) ===\n")
pa <- res[res$model == "PA_CR2" &
          res$term %in% c("acute_load_7d_wp_z", wcol), ]
print(pa[, c("excluded_player", "term", "OR", "CI_low", "CI_high", "p",
             "pct_change_OR")], row.names = FALSE)
cat("\nDONE. rows:", nrow(res), "\n")
