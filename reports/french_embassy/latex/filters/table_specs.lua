-- How each table in table_manifest.csv is typeset in Appendix H.
--
-- This file decides PRESENTATION ONLY: which CSV columns are shown, their headers, number
-- of decimals, alignment and relative width. Every value is read from the CSV at build
-- time; nothing here is a result. Columns that are not shown are listed automatically in
-- each table's note, so omissions are visible to the reader.
--
-- Column fields:
--   field   CSV column name (the build fails if it does not exist)
--   head    header text (LaTeX)
--   align   'l', 'r' or 'c'
--   width   fraction of the line width; the widths of one table must sum to 1
--   fmt     'text' | 'break' (long identifiers) | 'int' | 'num:N' (N decimals) |
--           'bool' (True/False shown as yes/no) | 'doi' | 'code'
--   repeat  false hides a value identical to the one in the row above (grouped rows)
-- Table fields:
--   size       font size command; landscape  true rotates the page
--   constants  columns whose single value is stated once in the note (checked)
--   keep       optional row filter; row_note explains it (%d = number of rows omitted)
--   rule_when  insert a rule when this column's value changes between rows
--   space_when insert a small gap when this column's value changes between rows

local function col(field, head, align, width, fmt, extra)
  local c = { field = field, head = head, align = align, width = width, fmt = fmt or 'text' }
  for k, v in pairs(extra or {}) do c[k] = v end
  return c
end

local specs = {}

specs.table_1 = {
  caption_key = 'Table 1', size = '\\small', rule_when = 'is_total',
  columns = {
    col('tissue', 'Tissue (OncotreeLineage)', 'l', 0.30),
    col('records', 'Records', 'r', 0.11, 'int'),
    col('independent_components', 'Independent components', 'r', 0.14, 'int'),
    col('multi_record_components', 'Components with more than one record', 'r', 0.17, 'int'),
    col('stranded_rna_profiles', 'Stranded RNA profiles', 'r', 0.12, 'int'),
    col('stratification', 'Stratification', 'l', 0.16),
  },
  derived = { is_total = function(row) return row.tissue == 'All' and 'total' or 'tissue' end },
}

specs.table_2 = {
  caption_key = 'Table 2', size = '\\footnotesize', landscape = true,
  constants = { { 'inference_status', 'Inference status (all models)' } },
  columns = {
    col('model_id', 'Model', 'l', 0.05),
    col('mae', 'MAE (mSF2)', 'r', 0.085, 'num:6'),
    col('rmse', 'RMSE (mSF2)', 'r', 0.085, 'num:6'),
    col('r2_oos', 'Out-of-sample R²', 'r', 0.085, 'num:6'),
    col('calibration_slope', 'Calibration slope', 'r', 0.065, 'num:2'),
    col('calibration_intercept', 'Calibration intercept', 'r', 0.075, 'num:2'),
    col('mae_change_vs_M1', 'MAE change vs M1', 'r', 0.085, 'num:6'),
    col('relative_mae_change_vs_M1', 'Relative change vs M1', 'r', 0.07, 'num:4'),
    col('mae_change_vs_M0', 'MAE change vs M0', 'r', 0.085, 'num:6'),
    col('relative_mae_change_vs_M0', 'Relative change vs M0', 'r', 0.07, 'num:4'),
    col('paired_delta_mae', 'Paired ΔMAE', 'r', 0.085, 'num:6'),
    col('paired_comparator', 'Comparator', 'l', 0.065),
    col('repeats_favouring_model', 'Repeats favouring model', 'l', 0.095),
  },
}

specs.table_3 = {
  caption_key = 'Table 3', size = '\\footnotesize', rule_when = 'support',
  columns = {
    col('tissue', 'Tissue', 'l', 0.22),
    col('independent_components', 'Components', 'r', 0.10, 'int'),
    col('mae_M0', 'MAE M0', 'r', 0.085, 'num:4'),
    col('mae_M1', 'MAE M1', 'r', 0.085, 'num:4'),
    col('mae_M2', 'MAE M2', 'r', 0.085, 'num:4'),
    col('delta_mae_m1_minus_m2', 'ΔMAE (M1 − M2)', 'r', 0.105, 'num:4'),
    col('direction', 'Direction', 'l', 0.11),
    col('support', 'Support', 'l', 0.21),
  },
}

specs.table_s1 = {
  caption_key = 'Table S1', size = '\\small', rule_when = 'is_summary',
  columns = {
    col('cv_repeat', 'Cross-validation repeat', 'l', 0.30),
    col('primary: tissue+expression vs tissue', 'ΔMAE, M2 vs M1 (primary)', 'r', 0.35,
      'num:6'),
    col('S1: beyond tissue+proliferation', 'ΔMAE, M2P vs M1P (beyond tissue and proliferation)',
      'r', 0.35, 'num:6'),
  },
  derived = {
    is_summary = function(row)
      return row.cv_repeat:match('^%d+$') and 'repeat' or 'summary'
    end,
  },
}

specs.table_s2 = {
  caption_key = 'Table S2', size = '\\footnotesize', landscape = true, rule_when = 'tier',
  constants = {
    { 'null_control_evidence', 'Negative-control evidence (all gene sets)' },
    { 'interpretation_limit', 'Interpretation limit (all gene sets)' },
  },
  columns = {
    col('rank', 'Rank', 'r', 0.04, 'int'),
    col('gene_set', 'Hallmark gene set', 'l', 0.22, 'break'),
    col('mean_importance', 'Mean importance (mSF2)', 'r', 0.08, 'num:6'),
    col('sd_importance', 'SD of importance', 'r', 0.08, 'num:6'),
    col('positive_importance_share', 'Share of fits with importance > 0', 'r', 0.075, 'num:2'),
    col('sign_consistency', 'Sign consistency', 'r', 0.07, 'num:2'),
    col('dominant_sign', 'Dominant sign', 'l', 0.065),
    col('share_zero_coefficient', 'Share of fits with zero coefficient', 'r', 0.075, 'num:2'),
    col('tier', 'Tier', 'l', 0.04),
    col('shared_signal_caveat', 'Shared-signal caveat', 'l', 0.255),
  },
}

specs.table_s3 = {
  caption_key = 'Table S3', size = '\\scriptsize', landscape = true, rule_when = 'tier',
  keep = function(row)
    return row.tier == 'A' or row.tier == 'B' or row.tier == 'C' or row.context_line ~= ''
  end,
  row_note = 'Rows shown: every line in discrepancy tiers A, B and C, plus the Moringa '
    .. 'context lines whatever their tier; the remaining %d lines (not prioritised) are in '
    .. 'the source file.',
  columns = {
    col('rank', 'Rank', 'r', 0.035, 'int'),
    col('depmap_id', 'DepMap ID', 'l', 0.07),
    col('cell_line_name', 'Cell line', 'l', 0.08),
    col('lineage', 'Tissue', 'l', 0.10),
    col('observed_msf2', 'Observed mSF2', 'r', 0.055, 'num:3'),
    col('pred_m1', 'Predicted, M1', 'r', 0.055, 'num:3'),
    col('pred_m2', 'Predicted, M2', 'r', 0.055, 'num:3'),
    col('abs_error_m1', 'Absolute error, M1', 'r', 0.055, 'num:3'),
    col('abs_error_m2', 'Absolute error, M2', 'r', 0.055, 'num:3'),
    col('model_disagreement', 'Model disagreement', 'r', 0.06, 'num:3'),
    col('pred_m2_repeat_sd', 'SD across repeats, M2', 'r', 0.06, 'num:3'),
    col('tier', 'Tier', 'l', 0.035),
    col('triage_category', 'Triage category', 'l', 0.115),
    col('technical_flags', 'Technical flags', 'l', 0.12),
    col('context_line', 'Context line', 'l', 0.05),
  },
}

specs.within_tissue_spearman_v2 = {
  caption_key = 'within_tissue_spearman_v2', size = '\\small',
  pivot = {
    row_field = 'lineage', col_field = 'model_id', value_field = 'spearman_rho',
    status_field = 'status', n_field = 'n_components', caveat_field = 'caveat',
    models = { 'M0', 'M1', 'M1P', 'M2', 'M2P' }, fmt = 'num:3',
    omit_status_prefix = 'not reported', undefined_status_prefix = 'undefined',
    undefined_text = '\\textit{undefined}',
  },
  columns = {
    col('lineage', 'Tissue', 'l', 0.29),
    col('n_components', 'Components', 'r', 0.13, 'int'),
    col('M0', 'M0', 'r', 0.116, 'raw'), col('M1', 'M1', 'r', 0.116, 'raw'),
    col('M1P', 'M1P', 'r', 0.116, 'raw'), col('M2', 'M2', 'r', 0.116, 'raw'),
    col('M2P', 'M2P', 'r', 0.116, 'raw'),
  },
}

specs.table_c1 = {
  size = '\\scriptsize', landscape = true, space_when = 'preferred_name',
  columns = {
    col('preferred_name', 'Compound', 'l', 0.13, 'text', { ['repeat'] = false }),
    col('report_number', 'Report', 'r', 0.04, 'int'),
    col('report_plant_part', 'Plant part', 'l', 0.05),
    col('solvent_or_fraction', 'Solvent or fraction', 'l', 0.17),
    col('is_dichloromethane', 'DCM', 'l', 0.035, 'bool'),
    col('identification_method', 'Identification method', 'l', 0.20),
    col('identification_strength', 'Identification strength', 'l', 0.085, 'break'),
    col('reading_depth', 'Reading depth', 'l', 0.06, 'break'),
    col('research_group', 'Research group', 'l', 0.11),
    col('doi', 'DOI', 'l', 0.12, 'doi'),
  },
}

specs.table_c2 = {
  size = '\\scriptsize', landscape = true, space_when = 'preferred_name',
  columns = {
    col('evidence_id', 'ID', 'l', 0.045),
    col('preferred_name', 'Compound', 'l', 0.075),
    col('evidence_level', 'Evidence level', 'l', 0.07, 'break'),
    col('process_category', 'Process', 'l', 0.07, 'break'),
    col('model_system', 'Model system', 'l', 0.15),
    col('radiation_type', 'Radiation', 'l', 0.08),
    col('radiation_dose_gy', 'Dose (Gy)', 'l', 0.08),
    col('concentration', 'Concentration', 'l', 0.13),
    col('direction', 'Reported direction', 'l', 0.09, 'break'),
    col('is_liability', 'Liability', 'l', 0.045, 'bool'),
    col('counts_for_score', 'Scored', 'l', 0.04, 'bool'),
    col('doi', 'DOI', 'l', 0.125, 'doi'),
  },
}

specs.table_c3 = {
  panels = {
    {
      size = '\\footnotesize', landscape = true,
      columns = {
        col('rank', 'Rank', 'r', 0.04, 'int'),
        col('preferred_name', 'Compound', 'l', 0.16),
        col('chemical_class', 'Chemical class', 'l', 0.13),
        col('plant_part', 'Plant part', 'l', 0.05),
        col('extraction_category', 'Extraction category', 'l', 0.12, 'break'),
        col('dcm_reports', 'DCM reports', 'r', 0.05, 'int'),
        col('d1_moringa_identity', 'D1 identity (0–2)', 'r', 0.05, 'int'),
        col('d2_radiation_biology', 'D2 radiation biology (0–3)', 'r', 0.06, 'int'),
        col('d3_independent_sources', 'D3 sources (0–2)', 'r', 0.05, 'int'),
        col('d4_feasibility', 'D4 feasibility (0–1)', 'r', 0.055, 'int'),
        col('total_score', 'Total (0–8)', 'r', 0.045, 'int'),
        col('tier', 'Tier', 'l', 0.075, 'break'),
        col('liability_flags', 'Liability flags', 'l', 0.115),
      },
    },
    {
      size = '\\scriptsize', landscape = true,
      continuation = 'written justification of every point and of the tier',
      columns = {
        col('preferred_name', 'Compound', 'l', 0.11),
        col('reason_d1_moringa_identity', 'D1 Moringa identity', 'l', 0.16),
        col('reason_d2_radiation_biology', 'D2 radiation biology', 'l', 0.19),
        col('reason_d3_independent_sources', 'D3 independent sources', 'l', 0.27),
        col('reason_d4_feasibility', 'D4 feasibility', 'l', 0.12),
        col('tier_reason', 'Tier reason', 'l', 0.15),
      },
    },
  },
}

specs.table_c4 = {
  size = '\\footnotesize', space_when = 'preferred_name',
  constants = { { 'interpretation_limit', 'Interpretation limit (all rows)' } },
  columns = {
    col('preferred_name', 'Compound', 'l', 0.15, 'text', { ['repeat'] = false }),
    col('gene_set', 'Hallmark gene set', 'l', 0.29, 'break'),
    col('n_overlapping_genes', 'Overlapping genes (n)', 'r', 0.10, 'int'),
    col('n_genes_measured', 'Genes measured (n)', 'r', 0.09, 'int'),
    col('n_genes_in_set', 'Genes in set (n)', 'r', 0.09, 'int'),
    col('overlapping_genes', 'Overlapping genes', 'l', 0.16),
    col('evidence_ids', 'Evidence IDs', 'l', 0.12),
  },
}

specs.table_r1 = {
  size = '\\small',
  columns = {
    col('model_id', 'Model', 'l', 0.09),
    col('scale', 'Scale', 'l', 0.09),
    col('mae', 'MAE (mSF2)', 'r', 0.15, 'num:6'),
    col('rmse', 'RMSE (mSF2)', 'r', 0.15, 'num:6'),
    col('r2_oos', 'Out-of-sample R²', 'r', 0.16, 'num:6'),
    col('calibration_slope', 'Calibration slope', 'r', 0.18, 'num:2'),
    col('calibration_intercept', 'Calibration intercept', 'r', 0.18, 'num:2'),
  },
}

specs.table_r2 = {
  size = '\\small',
  columns = {
    col('held_out_lineage', 'Held-out tissue', 'l', 0.29),
    col('n_components', 'Components', 'r', 0.13, 'int'),
    col('delta_mae_vs_global_mean', 'ΔMAE vs global mean (mSF2)', 'r', 0.19, 'num:4'),
    col('mean_prediction_shift', 'Mean prediction shift (mSF2)', 'r', 0.20, 'num:4'),
    col('within_lineage_spearman', 'Within-tissue Spearman ρ', 'r', 0.19, 'num:3'),
  },
}

specs.table_r3 = {
  size = '\\footnotesize',
  constants = {
    { 'comparison', 'Comparison' }, { 'model', 'Model' }, { 'comparator', 'Comparator' },
  },
  columns = {
    col('scale', 'Scale', 'l', 0.08),
    col('delta_mae', 'ΔMAE', 'r', 0.10, 'num:5'),
    col('record_weighted_delta_mae', 'Record-weighted ΔMAE', 'r', 0.13, 'num:5'),
    col('n_components', 'Components', 'r', 0.11, 'int'),
    col('n_records', 'Records', 'r', 0.08, 'int'),
    col('repeats', 'Repeats', 'r', 0.08, 'int'),
    col('adopted_method', 'Adopted method', 'l', 0.14, 'break'),
    col('verdict', 'Verdict', 'l', 0.28),
  },
}

return specs
