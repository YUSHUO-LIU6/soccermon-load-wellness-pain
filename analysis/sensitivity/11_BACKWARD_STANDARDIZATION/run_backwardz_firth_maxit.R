#!/usr/bin/env Rscript
# ============================================================================
# run_backwardz_firth_maxit.R — Task 9.7 follow-up: three logistf fits in
# run_backwardz_models.R emitted "Maximum number of iterations for full model
# exceeded" (default maxit=25): F_hist (soreness, with team), F_hist_r90 and
# F_hist_dropteam_r90 (soreness, _r90 QA). Refit with maxit=200 and compare
# coefficients; if a focal coefficient moved materially the RESULTS rows are
# replaced (with notes) and CMP/SUMMARY recomputed; otherwise a confirmation
# diagnostic is appended and the original rows stand.
#
# Outputs: appends to FR/11_BACKWARD_STANDARDIZATION/backwardz_diagnostics.csv
#          (and repairs BACKWARD_STANDARDIZATION_RESULTS.csv only if needed)
# Log    : FR/18_LOGS/workstream_newmodels.log
# ============================================================================

suppressPackageStartupMessages(library(logistf))

FR   <- "D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE"
OUT  <- file.path(FR, "11_BACKWARD_STANDARDIZATION")
LOGF <- file.path(FR, "18_LOGS", "workstream_newmodels.log")

log_msg <- function(...) {
  txt <- paste0(format(Sys.time(), "%Y-%m-%d %H:%M:%S"), " | [9.7 firth_maxit] ",
                paste(..., collapse = ""))
  cat(txt, "\n")
  cat(txt, "\n", file = LOGF, append = TRUE)
}

res_file  <- file.path(OUT, "BACKWARD_STANDARDIZATION_RESULTS.csv")
diag_file <- file.path(OUT, "backwardz_diagnostics.csv")

append_csv <- function(df, path)
  write.table(df, path, sep = ",", row.names = FALSE, quote = TRUE,
              append = file.exists(path), col.names = !file.exists(path))
add_diag <- function(model_id, diagnostic, value)
  append_csv(data.frame(model_id = model_id, wellness_variant = "soreness",
                        diagnostic = diagnostic, value = as.character(value),
                        stringsAsFactors = FALSE), diag_file)

md <- read.csv(file.path(OUT, "modeling_dataset_backwardz.csv"),
               stringsAsFactors = FALSE)
md$date <- as.Date(md$date)
md$team      <- factor(md$team)
md$season    <- factor(md$season)
md$player_id <- factor(md$player_id)

mk_cc <- function(acute_col, wcol, chron_col) {
  vars <- c("onset_day", acute_col, wcol, chron_col, "prev_episode_ever",
            "calendar_time", "team", "season", "player_id", "date",
            "prev_episode_count")
  md[complete.cases(md[, vars]), ]
}
mkf <- function(acute_col, wcol, chron_col, team = TRUE)
  as.formula(paste0("onset_day ~ ", acute_col, " * ", wcol, " + ", chron_col,
                    " + prev_episode_ever + calendar_time + ",
                    if (team) "team + season" else "season"))

jobs <- list(
  list(model_id = "F_hist", taxonomy = "R2_REVIEWER_REQUESTED",
       acute = "acute_load_7d_wp_z_hist",
       wcol  = "soreness_burden_recent3_wp_z_hist",
       chron = "chronic_load_28d_wp_z_hist", team = TRUE),
  list(model_id = "F_hist_r90", taxonomy = "R2_INTERNAL_QA_ONLY",
       acute = "acute_load_7d_wp_z_r90",
       wcol  = "soreness_burden_recent3_wp_z_r90",
       chron = "chronic_load_28d_wp_z_r90", team = TRUE),
  list(model_id = "F_hist_dropteam_r90", taxonomy = "R2_INTERNAL_QA_ONLY",
       acute = "acute_load_7d_wp_z_r90",
       wcol  = "soreness_burden_recent3_wp_z_r90",
       chron = "chronic_load_28d_wp_z_r90", team = FALSE))

res_df <- read.csv(res_file, stringsAsFactors = FALSE)
repair_needed <- FALSE
refits <- list()

for (j in jobs) {
  d <- mk_cc(j$acute, j$wcol, j$chron)
  f <- mkf(j$acute, j$wcol, j$chron, j$team)
  ctl <- logistf.control(maxit = 200, maxstep = 5)
  warns <- character(0)
  ff <- withCallingHandlers(
    logistf(f, data = d, control = ctl),
    warning = function(w) { warns <<- c(warns, conditionMessage(w))
                            invokeRestart("muffleWarning") })
  old <- res_df[res_df$model_id == j$model_id & res_df$wellness_variant == "soreness", ]
  old_beta <- log(old$OR); names(old_beta) <- old$term
  new_beta <- ff$coefficients
  common <- intersect(names(old_beta), names(new_beta))
  dmax <- max(abs(new_beta[common] - old_beta[common]))
  inter <- paste0(j$acute, ":", j$wcol)
  log_msg(j$model_id, ": refit maxit=200; max|delta log(OR)|=", signif(dmax, 4),
          "; interaction OR ", round(exp(old_beta[inter]), 4), " -> ",
          round(exp(new_beta[inter]), 4),
          "; warnings: ", if (length(warns)) paste(unique(warns), collapse=" || ") else "none")
  add_diag(j$model_id, "logistf_maxit25_warning_refit",
           paste0("original fit warned 'maxit exceeded'; refit maxit=200 maxstep=5: ",
                  "max|delta log(OR)|=", signif(dmax, 6),
                  "; interaction OR ", round(exp(old_beta[inter]), 6), " -> ",
                  round(exp(new_beta[inter]), 6),
                  if (length(warns)) paste0("; refit warnings: ", paste(unique(warns), collapse=" || ")) else "; refit clean"))
  refits[[j$model_id]] <- list(fit = ff, d = d, j = j, dmax = dmax)
  if (dmax > 0.01) repair_needed <- TRUE
}

if (!repair_needed) {
  log_msg("All three refits match original coefficients (max|delta log(OR)| <= 0.01); ",
          "original rows kept, maxit warning benign (iteration limit hit at/near optimum).")
  add_diag("F_hist_maxit_check", "verdict",
           "maxit=25 warnings benign: maxit=200 refits reproduce coefficients within 0.01 log-OR on all terms; RESULTS rows unchanged")
} else {
  log_msg("MATERIAL coefficient shift detected — replacing rows and recomputing CMP/SUMMARY")
  for (mid in names(refits)) {
    r <- refits[[mid]]; ff <- r$fit; j <- r$j; d <- r$d
    keep <- !(res_df$model_id == mid & res_df$wellness_variant == "soreness")
    res_df <- res_df[keep, ]
    ci_lo <- if (is.null(ff$ci.lower)) rep(NA_real_, length(ff$coefficients)) else ff$ci.lower
    ci_hi <- if (is.null(ff$ci.upper)) rep(NA_real_, length(ff$coefficients)) else ff$ci.upper
    f_str <- paste(deparse(mkf(j$acute, j$wcol, j$chron, j$team)), collapse = " ")
    new_rows <- data.frame(
      model_id = mid, wellness_variant = "soreness",
      term = names(ff$coefficients), OR = exp(ff$coefficients),
      CI_low = exp(ci_lo), CI_high = exp(ci_hi), p = ff$prob, se = NA,
      converged = TRUE,
      separation_flag = any(abs(ff$coefficients) > 10),
      n = nrow(d), players = length(unique(d$player_id)),
      events = sum(d$onset_day), formula = f_str, taxonomy = j$taxonomy,
      notes = paste0("Firth penalised logistic (logistf)", if (!j$team) " minus team" else "",
                     "; profile-likelihood CI; REFIT with control maxit=200 maxstep=5 ",
                     "after maxit-exceeded warning on initial fit (max|delta log(OR)|=",
                     signif(r$dmax, 4), " vs initial; initial values in backwardz_diagnostics.csv)"),
      stringsAsFactors = FALSE)
    res_df <- rbind(res_df, new_rows)
  }
  write.csv(res_df, res_file, row.names = FALSE, quote = TRUE)
  log_msg("Rows replaced; NOTE: CMP_*/SUMMARY rows must be regenerated — ",
          "rerun run_backwardz_models.R (resume mode keeps all fit rows and ",
          "recomputes CMP/SUMMARY; Firth models flagged converged will be skipped ",
          "only if rows exist, which they now do with corrected values).")
}
log_msg("run_backwardz_firth_maxit.R finished")
