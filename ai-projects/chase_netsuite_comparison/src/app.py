# ============================================================
#  app.py
#  BU–CG Reconciliation Engine — Version 3.9.8
#
#  Entry point. Run with: streamlit run app.py
#
#  This file contains ONLY Streamlit UI code.
#  All business logic lives in separate modules:
#    config.py     — constants, MONTHS, YEARS
#    loaders.py    — file reading, normalization, caching, validation
#    reconcile.py  — reconciliation logic + MoM trend analysis
#
#  v3.9.0 Phase-1 upgrades (code review of Sonnet v3.7.1):
#    1. JPMC BU-scoping restored (the 8237-row bug)
#    2. Materiality ORIG CO NAME filter added
#    3. Version headers consistent at 3.9.0
#    4. Fragment/rerun cleanup
#    5. Diagnostic reorder: NS → JPMC → Deposits → success
#    6. Sidebar write-failure → st.info not st.success
#    7. hide_index on BU conflicts table
#    8. Deposits column validation added
# ============================================================

import io
import json
import os
import zipfile
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st

from config    import APP_VERSION, MONTHS, YEARS, DEFAULT_COLUMN_CFG
from loaders   import (
    load_config, load_netsuite, load_bu_mapping, load_jpmc,
    validate_columns_config,
    load_top18_mapping, Top18MappingError, normalize_for_match,
    load_deposits,
)
from reconcile import (
    reconcile, reconcile_three_way,
    analyze_mom_trend, find_round_amounts, analyze_bu_materiality,
    ReconciliationEmpty, TrendInsufficientData,
    trend_empty_schema,
)

# ── Option A: auto-load columns.json from project folder on startup ───────────
# If columns.json exists alongside app.py, load it once into session_state.
# This means column letters are always correct on every run — no manual Save.
_COLUMNS_JSON_PATH = os.path.join(os.path.dirname(__file__), "columns.json")
if "cfg" not in st.session_state:
    if os.path.exists(_COLUMNS_JSON_PATH):
        with open(_COLUMNS_JSON_PATH, "r") as _f:
            st.session_state["cfg"]         = json.load(_f)
            st.session_state["sidebar_cfg"] = dict(st.session_state["cfg"])
    else:
        st.session_state["cfg"]         = dict(DEFAULT_COLUMN_CFG)
        st.session_state["sidebar_cfg"] = dict(DEFAULT_COLUMN_CFG)

# ─────────────────────────────────────────
# Page config — must be first Streamlit call
# ─────────────────────────────────────────
st.set_page_config(page_title="Chase & NetSuite Comparison", layout="wide",
                   initial_sidebar_state="expanded")

# Only hide the per-dataframe toolbar icons (download/search/fullscreen)
# — all other Streamlit UI chrome (spinner, settings ⋮, sidebar toggle)
# must remain visible.
st.markdown("""
<style>
  [data-testid="stElementToolbar"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# Display helper — adds a 1-based "#" column
# ─────────────────────────────────────────
def with_serial_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of df with a leading 1-based '#' column, ready for
    display via st.dataframe(..., hide_index=True).

    The pandas index carries no business meaning and confuses users
    (e.g. shows '12, 20, 45' after filtering). A 1-based '#' that
    resets on every render is what readers expect ("look at row 7").

    Display-only — does NOT mutate the DataFrame in session state.
    """
    if df is None or df.empty:
        return df
    out = df.reset_index(drop=True).copy()
    out.insert(0, "#", range(1, len(out) + 1))
    return out

# ─────────────────────────────────────────
# Fix01 — reconciliation KPI semantics
# ─────────────────────────────────────────
def calculate_reconciliation_kpis(summary_df: pd.DataFrame, three_way: bool) -> dict:
    """
    Calculate user-facing reconciliation quality metrics.

    Semantics:
      • 3-way Match Rate = Matched eligible groups ÷ Eligible reconciliation groups.
      • Eligible group = any BU + Remarks group with non-zero activity in at
        least one source. Defensive all-zero rows are excluded.
      • Matched group = eligible group where Result == 'Match'.
      • 2-way Variance Rate = Variance groups ÷ Eligible reconciliation groups.

    This avoids presenting the KPI as a generic dataframe row percentage and
    keeps the metric tied to the business grain of the reconciliation: one
    BU + ORIG CO NAME / Remarks group.
    """
    if summary_df is None or summary_df.empty:
        return {
            "eligible_groups": 0,
            "matched_groups": 0,
            "mismatched_groups": 0,
            "match_rate": 0.0,
            "variance_groups": 0,
            "variance_rate": 0.0,
        }

    df = summary_df.copy()

    amount_cols = [c for c in ["NetSuite_Total", "Chase_Total", "JPMC_Total", "Deposits_Total"] if c in df.columns]
    if amount_cols:
        eligible_mask = df[amount_cols].fillna(0).abs().sum(axis=1).round(2) != 0
    else:
        eligible_mask = pd.Series(True, index=df.index)

    eligible_groups = int(eligible_mask.sum())

    if eligible_groups == 0:
        return {
            "eligible_groups": 0,
            "matched_groups": 0,
            "mismatched_groups": 0,
            "match_rate": 0.0,
            "variance_groups": 0,
            "variance_rate": 0.0,
        }

    if three_way and "Result" in df.columns:
        matched_groups = int(((df["Result"] == "Match") & eligible_mask).sum())
        mismatched_groups = int(((df["Result"] == "Mismatch") & eligible_mask).sum())
        match_rate = matched_groups / eligible_groups * 100
        return {
            "eligible_groups": eligible_groups,
            "matched_groups": matched_groups,
            "mismatched_groups": mismatched_groups,
            "match_rate": match_rate,
            "variance_groups": mismatched_groups,
            "variance_rate": 100 - match_rate,
        }

    if "Variance" in df.columns:
        variance_groups = int(((df["Variance"].fillna(0).round(2) != 0) & eligible_mask).sum())
    else:
        variance_groups = 0
    variance_rate = variance_groups / eligible_groups * 100

    return {
        "eligible_groups": eligible_groups,
        "matched_groups": eligible_groups - variance_groups,
        "mismatched_groups": variance_groups,
        "match_rate": 100 - variance_rate,
        "variance_groups": variance_groups,
        "variance_rate": variance_rate,
    }


# ─────────────────────────────────────────
# Diagnostic export helper (Test08)
# ─────────────────────────────────────────
def _safe_stem(filename: str) -> str:
    """
    Sanitize an uploaded filename into something safe to use as a
    filesystem stem. Drops the extension, replaces unsafe characters
    with underscore. Defensive against unusual filenames.
    """
    import re as _re
    # Strip extension
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    # Replace anything that isn't alphanumeric, dash, underscore, dot, or space
    stem = _re.sub(r"[^A-Za-z0-9._\- ]+", "_", stem)
    # Collapse runs of whitespace + trim
    stem = _re.sub(r"\s+", " ", stem).strip()
    return stem or "file"


def export_diagnostic(df: pd.DataFrame, source_filename: str, suffix: str) -> str | None:
    """
    Prepare a diagnostic frame for ZIP export instead of rendering it in the UI.
    Returns the prepared file path or None if the frame was empty / nothing written.

    Filenames pattern:  <source_stem>_<suffix>.csv
    e.g. 'Consolidated Chase 2026_Daily_dropped_zero_credit.csv'

    Patch02 stores these files in an OS temp cache used only to assemble the
    ZIP diagnostics folder, avoiding duplicate visible CSVs in the app folder.

    The file is overwritten on each pre-process — so re-running with a fresh
    upload of the same source file replaces the previous diagnostic cache.
    """
    if df is None or len(df) == 0:
        return None
    stem  = _safe_stem(source_filename)
    fname = f"{stem}_{suffix}.csv"
    # Patch02: keep diagnostics available for ZIP export without cluttering
    # the app launch directory with duplicate local CSVs.
    diag_dir = os.path.join(tempfile.gettempdir(), "bucg_recon_diagnostics")
    os.makedirs(diag_dir, exist_ok=True)
    fpath = os.path.join(diag_dir, fname)
    try:
        df.to_csv(fpath, index=False)
        return fpath
    except OSError as e:
        # Surface the failure to the caller — UI message decides what to show
        st.error(f"Could not prepare diagnostic file '{fname}': {e}")
        return None


def _remember_diagnostic_export(registry: list[dict], source: str, category: str, filename: str | None, rows: int) -> None:
    """Register a diagnostic CSV for the download bundle manifest."""
    if filename:
        registry.append({
            "source": source,
            "category": category,
            "filename": filename,
            "rows": int(rows or 0),
        })


def _safe_zip_name(name: str) -> str:
    """Return a safe ZIP member name without path traversal risk."""
    return os.path.basename(str(name)).replace('\\', '_').replace('/', '_')


# ─────────────────────────────────────────
# Section 0 — Header
# ─────────────────────────────────────────
title_col, btn_col = st.columns([5, 1])
with title_col:
    st.title("Chase & NetSuite Comparison")
with btn_col:
    # Theme switching is handled by Streamlit's built-in ⋮ menu →
    # Settings → Theme. No need for a duplicate button here.
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Restart", use_container_width=True):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()

st.markdown("---")


# ─────────────────────────────────────────
# Sidebar — Column Configuration
# ─────────────────────────────────────────

# Single source of truth for default column config — imported from config.py
_DEFAULT_CFG = DEFAULT_COLUMN_CFG

with st.sidebar:
    st.markdown("## ⚙️ Column Configuration")

    # Excel / Snowflake mode toggle
    col_mode = st.radio(
        "Source mode",
        options=["Excel (A/B/C…)", "Snowflake (column names)"],
        index=0,
        horizontal=True,
        key="col_mode",
        help=(
            "Excel mode: enter the column letter (A, B, C…) for each field.\n"
            "Snowflake mode: enter the exact column name from the table."
        ),
    )
    is_excel_mode = (col_mode == "Excel (A/B/C…)")
    placeholder   = "e.g. B" if is_excel_mode else "e.g. SUBSIDIARY"

    # Load current cfg from session or use defaults
    if "sidebar_cfg" not in st.session_state:
        st.session_state["sidebar_cfg"] = {
            src: dict(fields)
            for src, fields in _DEFAULT_CFG.items()
        }
    _scfg = st.session_state["sidebar_cfg"]

    def _cfg_section(title: str, src_key: str, fields: list[str]):
        """Render one collapsible config section for a source file."""
        with st.expander(title, expanded=False):
            updated = {}
            for field in fields:
                updated[field] = st.text_input(
                    field,
                    value=_scfg[src_key].get(field, ""),
                    key=f"cfg_{src_key}_{field}",
                    placeholder=placeholder,
                )
            _scfg[src_key] = updated

    _cfg_section("NetSuite",   "netsuite",   ["BU", "DATE", "ENTITY", "REMARKS", "CREDIT"])
    _cfg_section("JPMC/Chase", "jpmc",       ["BU_FULL", "DATE", "CREDIT", "REMARKS"])
    _cfg_section("BU Mapping", "bu_mapping", ["BU", "BU_FULL"])
    _cfg_section("Deposits",   "deposits",   ["BU", "DATE", "AMOUNT", "REMARKS"])

    st.markdown("---")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("💾 Save", use_container_width=True, key="cfg_save"):
            st.session_state["cfg"] = dict(_scfg)
            # Write to columns.json in project folder so it persists across restarts
            try:
                with open(_COLUMNS_JSON_PATH, "w") as _wf:
                    json.dump(dict(_scfg), _wf, indent=2)
                st.success("Saved to columns.json ✅")
            except Exception as _e:
                st.info("Saved to session (file write unavailable).")
                st.warning(f"Could not write columns.json: {_e}")
    with col_s2:
        if st.button("↺ Reset", use_container_width=True, key="cfg_reset"):
            st.session_state["sidebar_cfg"] = {
                src: dict(fields) for src, fields in _DEFAULT_CFG.items()
            }
            st.session_state["cfg"] = dict(_DEFAULT_CFG)
            try:
                with open(_COLUMNS_JSON_PATH, "w") as _wf:
                    json.dump(dict(_DEFAULT_CFG), _wf, indent=2)
            except Exception:
                pass
            st.rerun()

    st.caption(
        "Changes take effect on the next Pre-process run. "
        "Snowflake mode: enter exact column names from the table."
    )


# ─────────────────────────────────────────
# Section 1 — File uploads
# ─────────────────────────────────────────

@st.fragment
def section_uploads():
    st.subheader("1. File uploads")

    st.caption(
        "Upload all files at once — select multiple in the file dialog (Ctrl+A or Shift+click). "
        "Select the correct role for each file from the dropdown, then click Pre-process."
    )

    uploaded_files = st.file_uploader(
        "Drop all files here (NetSuite · JPMC · BU Mapping · Deposits · Top18 JSON)",
        type=["xlsx", "xls", "csv", "json"],
        accept_multiple_files=True,
        key="all_files",
    )

    ROLE_OPTIONS = ["— select role —", "netsuite", "jpmc", "bu_mapping", "deposits", "top18", "ignore"]

    # Manual role assignment — no auto-detection, no file reads at this stage
    assigned_roles: dict[str, str] = {}
    missing_roles: set[str] = {"netsuite", "jpmc", "bu_mapping"}

    if uploaded_files:
        st.markdown("**Assign a role to each file:**")

        for uf in uploaded_files:
            col_name, col_role = st.columns([3, 2])
            with col_name:
                st.markdown(f"📄 `{uf.name}`")
            with col_role:
                chosen = st.selectbox(
                    "Role",
                    options=ROLE_OPTIONS,
                    index=0,
                    key=f"role_{uf.name}",
                    label_visibility="collapsed",
                )
            if chosen not in ("— select role —", "ignore"):
                assigned_roles[uf.name] = chosen

        # Validation
        role_counts     = {}
        for r in assigned_roles.values():
            role_counts[r] = role_counts.get(r, 0) + 1
        duplicate_roles = [r for r, c in role_counts.items() if c > 1]
        mandatory       = {"netsuite", "jpmc", "bu_mapping"}
        missing_roles   = mandatory - set(assigned_roles.values())

        if duplicate_roles:
            st.warning(f"⚠️ Duplicate role(s): {', '.join(duplicate_roles)} — each role must be assigned once.")
        if missing_roles:
            st.info(f"Still needed: {', '.join(sorted(missing_roles))}")

    # Build role → file lookup (no file reads here — reads happen in preprocess)
    _role_to_file: dict[str, any] = {}
    if uploaded_files:
        for uf in uploaded_files:
            role = assigned_roles.get(uf.name)
            if role:
                uf.seek(0)
                _role_to_file[role] = uf

    preprocess_clicked = st.button(
        "Pre-process files",
        type="primary",
        disabled=bool(missing_roles) if uploaded_files else False,
    )


    if preprocess_clicked:
        if not uploaded_files:
            st.error("Please upload files first.")
        elif missing_roles:
            st.error(f"Please assign these roles before pre-processing: {', '.join(sorted(missing_roles))}")
        else:
            ns_file    = _role_to_file.get("netsuite")
            jp_file    = _role_to_file.get("jpmc")
            bu_file    = _role_to_file.get("bu_mapping")
            top18_file = _role_to_file.get("top18")

            with st.spinner("Loading and pre-processing data…"):
                try:
                    cfg      = st.session_state.get("cfg", _DEFAULT_CFG)
                    ns_bytes = ns_file.read()
                    jp_bytes = jp_file.read()
                    bu_bytes = bu_file.read()

                    # ── columns.json validation ──────────────────────────────
                    # Catches the silent-failure case where a wrong column letter
                    # (e.g. "BU": "Z" on a 15-column sheet) would have produced
                    # None values throughout the loaded DataFrame.
                    # Deposits bytes are passed when available (optional file).
                    _dep_file_for_val = _role_to_file.get("deposits")
                    _dep_bytes_for_val = None
                    if _dep_file_for_val is not None:
                        _dep_bytes_for_val = _dep_file_for_val.read()
                        _dep_file_for_val.seek(0)  # rewind for later use

                    cfg_errors = validate_columns_config(
                        cfg, ns_bytes, jp_bytes, bu_bytes,
                        dep_bytes=_dep_bytes_for_val,
                    )
                    if cfg_errors:
                        st.error(
                            "columns.json validation failed — fix these and try again:\n\n"
                            + "\n".join(f"• {e}" for e in cfg_errors)
                        )
                        st.stop()

                    # ── Load all three sources ───────────────────────────────
                    bu_map_df, bu_conflicts          = load_bu_mapping(bu_bytes, cfg)
                    ns_df_clean, ns_dropped_df       = load_netsuite(ns_bytes, cfg)
                    (jp_df_clean, jp_unmapped,
                     jp_dropped_basic_df,
                     jp_dropped_zero_df,
                     jp_dropped_noise_df) = load_jpmc(jp_bytes, bu_map_df, cfg)

                    st.session_state["cfg"]          = cfg
                    st.session_state["bu_map_df"]    = bu_map_df
                    st.session_state["ns_df_clean"]  = ns_df_clean
                    st.session_state["jp_df_clean"]  = jp_df_clean
                    st.session_state["jp_unmapped"]  = jp_unmapped

                    # Fix04 — track diagnostic CSVs so the ZIP export can include
                    # the same audit files that preprocessing writes to disk.
                    diagnostic_exports: list[dict] = []

                    # ── FEAT-01: optional Top18_mapping.json ─────────────────
                    if top18_file is not None:
                        try:
                            top18_map = load_top18_mapping(top18_file)
                            st.session_state["top18_map"] = top18_map
                        except Top18MappingError as e:
                            st.error(f"Top18_mapping.json validation failed: {e}")
                            st.stop()
                    else:
                        st.session_state.pop("top18_map", None)

                    # ── Optional: Deposits table ─────────────────────────────
                    dep_file = _role_to_file.get("deposits")
                    dep_lines = []  # built here, displayed after JPMC bar
                    dep_dropped_count = 0
                    dep_no_origco_count = 0
                    dep_skipped_count = 0
                    if dep_file is not None:
                        try:
                            dep_bytes = dep_file.read()
                            (dep_df_clean,
                             dep_dropped_df,
                             dep_dropped_no_origco_df) = load_deposits(dep_bytes, cfg, filename=dep_file.name)

                            st.session_state["dep_df_clean"] = dep_df_clean
                            dep_dropped_count = len(dep_dropped_df)
                            dep_no_origco_count = len(dep_dropped_no_origco_df)
                            dep_skipped_count = dep_dropped_count + dep_no_origco_count

                            # Diagnostic exports
                            dep_drop_file    = export_diagnostic(dep_dropped_df,           dep_file.name, "dropped_rows")
                            dep_origco_file  = export_diagnostic(dep_dropped_no_origco_df, dep_file.name, "dropped_no_origco")
                            _remember_diagnostic_export(diagnostic_exports, "Deposits", "dropped_rows", dep_drop_file, len(dep_dropped_df))
                            _remember_diagnostic_export(diagnostic_exports, "Deposits", "dropped_no_origco", dep_origco_file, len(dep_dropped_no_origco_df))

                            dep_msg = f"Deposits: **{len(dep_df_clean):,} rows** loaded for 3-way reconciliation."
                            if len(dep_dropped_df):
                                line = f"• {len(dep_dropped_df):,} rows dropped — missing BU or unparseable date"
                                if dep_drop_file:
                                    line += f"  →  `{dep_drop_file}`"
                                dep_lines.append(line)
                            if len(dep_dropped_no_origco_df):
                                line = f"• {len(dep_dropped_no_origco_df):,} rows filtered — no ORIG CO NAME token"
                                if dep_origco_file:
                                    line += f"  →  `{dep_origco_file}`"
                                dep_lines.append(line)
                            if dep_lines:
                                dep_msg += "\n\n" + "\n".join(dep_lines)
                            # Store for display after JPMC bar
                            st.session_state["_dep_info_msg"] = dep_msg

                        except Exception as e:
                            st.warning(f"Deposits file could not be loaded ({e}). Continuing with 2-way reconciliation.")
                            st.session_state.pop("dep_df_clean", None)
                            st.session_state.pop("_dep_info_msg", None)
                    else:
                        st.session_state.pop("dep_df_clean", None)
                        st.session_state.pop("_dep_info_msg", None)

                    # ── Diagnostic exports + UI feedback ──────────────────────
                    # Order: NS (yellow) → JPMC (blue) → Deposits (blue) → Success (green)
                    ns_drop_file       = export_diagnostic(ns_dropped_df,       ns_file.name, "dropped_rows")
                    jp_basic_file      = export_diagnostic(jp_dropped_basic_df, jp_file.name, "dropped_basic")
                    jp_zero_file       = export_diagnostic(jp_dropped_zero_df,  jp_file.name, "dropped_zero_credit")
                    jp_noise_file      = export_diagnostic(jp_dropped_noise_df, jp_file.name, "dropped_noise")
                    jp_unmapped_file   = export_diagnostic(jp_unmapped,         jp_file.name, "unmapped")
                    _remember_diagnostic_export(diagnostic_exports, "NetSuite", "dropped_rows", ns_drop_file, len(ns_dropped_df))
                    _remember_diagnostic_export(diagnostic_exports, "JPMC", "dropped_basic", jp_basic_file, len(jp_dropped_basic_df))
                    _remember_diagnostic_export(diagnostic_exports, "JPMC", "dropped_zero_credit", jp_zero_file, len(jp_dropped_zero_df))
                    _remember_diagnostic_export(diagnostic_exports, "JPMC", "dropped_noise", jp_noise_file, len(jp_dropped_noise_df))
                    _remember_diagnostic_export(diagnostic_exports, "JPMC", "unmapped", jp_unmapped_file, len(jp_unmapped))

                    # ── NetSuite (yellow) ────────────────────────────────────
                    ns_dropped_count = len(ns_dropped_df)
                    if ns_dropped_count:
                        msg = (
                            f"NetSuite: dropped {ns_dropped_count:,} rows with missing BU "
                            f"or unparseable date."
                        )
                        if ns_drop_file:
                            msg += f" Details will be included in the diagnostics ZIP folder."
                        st.warning(msg)

                    # ── JPMC (single blue bar consolidating every observation)
                    jp_zero_count    = len(jp_dropped_zero_df)
                    jp_noise_count   = len(jp_dropped_noise_df)
                    jp_basic_count   = len(jp_dropped_basic_df)
                    jp_unmapped_count = len(jp_unmapped)
                    jp_total          = len(jp_df_clean) + jp_unmapped_count
                    jp_coverage       = (len(jp_df_clean) / jp_total * 100) if jp_total else 0

                    jp_lines = []
                    if jp_basic_count:
                        line = f"• {jp_basic_count:,} rows dropped — missing BU_Full or unparseable date"
                        if jp_basic_file:
                            line += f"  →  `{jp_basic_file}`"
                        jp_lines.append(line)
                    if jp_zero_count:
                        line = f"• {jp_zero_count:,} rows filtered out — $0.00 credit"
                        if jp_zero_file:
                            line += f"  →  `{jp_zero_file}`"
                        jp_lines.append(line)
                    if jp_noise_count:
                        line = f"• {jp_noise_count:,} rows filtered out — noise tokens (e.g. CASH CONCENTRATION)"
                        if jp_noise_file:
                            line += f"  →  `{jp_noise_file}`"
                        jp_lines.append(line)

                    cov_line = (
                        f"• BU mapping: {len(jp_df_clean):,} of {jp_total:,} rows mapped "
                        f"({jp_coverage:.1f}% coverage)"
                    )
                    if jp_unmapped_count:
                        cov_line += f" — {jp_unmapped_count:,} unmapped"
                        if jp_unmapped_file:
                            cov_line += f"  →  `{jp_unmapped_file}`"
                    else:
                        cov_line += " — all rows mapped"
                    jp_lines.append(cov_line)

                    if jp_lines:
                        intro = "**JPMC observations**"
                        if any([jp_basic_file, jp_zero_file, jp_noise_file, jp_unmapped_file]):
                            intro += " (details included in diagnostics ZIP folder)"
                        st.info(f"{intro}:\n\n" + "\n".join(jp_lines))

                    # ── Deposits (blue, after JPMC) ──────────────────────────
                    _dep_info = st.session_state.get("_dep_info_msg")
                    if _dep_info:
                        st.info(_dep_info)


                    # ─────────────────────────────────────────────────────────
                    # Fix07 — Pre-processing diagnostics dashboard
                    # ─────────────────────────────────────────────────────────
                    # ─────────────────────────────────────────────────────────
                    # Fix07 — Pre-processing diagnostics dashboard
                    # Force visible KPI dashboard after preprocessing.
                    # ─────────────────────────────────────────────────────────
                    st.divider()
                    st.subheader("📊 Pre-processing health summary")

                    dep_rows = len(st.session_state.get("dep_df_clean", pd.DataFrame()))

                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        st.metric(
                            "NetSuite usable",
                            f"{len(ns_df_clean):,}",
                            delta=f"-{ns_dropped_count:,} dropped"
                        )

                    with col_b:
                        st.metric(
                            "JPMC usable",
                            f"{len(jp_df_clean):,}",
                            delta=f"{jp_coverage:.1f}% mapped"
                        )

                    with col_c:
                        st.metric(
                            "Deposits usable",
                            f"{dep_rows:,}"
                        )

                    st.info(
                        f"Noise rows: {jp_noise_count:,} | "
                        f"Unmapped rows: {jp_unmapped_count:,}"
                    )

                    dep_rows = len(st.session_state.get("dep_df_clean", pd.DataFrame()))

                    d1, d2, d3 = st.columns(3)

                    with d1:
                        st.metric(
                            "NetSuite usable rows",
                            f"{len(ns_df_clean):,}",
                            delta=f"-{ns_dropped_count:,} dropped"
                        )

                    with d2:
                        st.metric(
                            "JPMC usable rows",
                            f"{len(jp_df_clean):,}",
                            delta=f"{jp_coverage:.1f}% mapped"
                        )

                    with d3:
                        st.metric(
                            "Deposits usable rows",
                            f"{dep_rows:,}"
                        )

                    st.success(
                        f"Pre-processing complete. "
                        f"NetSuite: {len(ns_df_clean):,} rows | "
                        f"JPMC: {len(jp_df_clean):,} rows | "
                        f"BU mapping: {len(bu_map_df):,} entries."
                    )

                    # ─────────────────────────────────────────────────────────
                    # Fix07 — Persist preprocessing diagnostics
                    # Streamlit reruns immediately after preprocessing, so any
                    # dashboard rendered only inside this button-click branch
                    # disappears. We store the metrics in session_state here,
                    # then render them later in the persistent page flow.
                    # ─────────────────────────────────────────────────────────
                    st.session_state["diagnostic_exports"] = diagnostic_exports

                    _dep_rows = len(st.session_state.get("dep_df_clean", pd.DataFrame()))
                    _jp_skipped = jp_basic_count + jp_zero_count + jp_noise_count + jp_unmapped_count
                    st.session_state["preprocess_metrics"] = {
                        "ns_found": len(ns_df_clean) + ns_dropped_count,
                        "ns_ingested": len(ns_df_clean),
                        "ns_skipped": ns_dropped_count,
                        "jp_found": len(jp_df_clean) + _jp_skipped,
                        "jp_ingested": len(jp_df_clean),
                        "jp_skipped": _jp_skipped,
                        "dep_found": _dep_rows + dep_skipped_count,
                        "dep_ingested": _dep_rows,
                        "dep_skipped": dep_skipped_count,
                        "has_deposits": "dep_df_clean" in st.session_state,
                    }

                    if len(bu_conflicts):
                        with st.expander(
                            f"⚠️ {len(bu_conflicts)} mapping conflicts (same BU name → different short codes)",
                            expanded=True
                        ):
                            st.caption("Resolve these in your BU Mapping file before running reconciliation.")
                            st.dataframe(
                                bu_conflicts[["BU", "BU_Full"]].sort_values("BU_Full"),
                                width="stretch",
                                hide_index=True,
                            )

                    # Trigger a rerun so other sections see the new session_state.
                    # @st.fragment isolates reruns by default — without this, the
                    # downstream sections continue showing stale state.
                    st.rerun()

                except Exception as e:
                    st.error(f"Pre-processing failed: {e}")



section_uploads()


# ─────────────────────────────────────────
# Fix07 — Persistent Pre-processing Health Summary
# ─────────────────────────────────────────
# This diagnostics panel is rendered OUTSIDE the Pre-process button branch.
# Pre-processing triggers st.rerun(), so anything rendered only inside the
# button-click branch flashes briefly and disappears. These metrics are read
# from session_state and remain visible while the user moves to Step 2.
#
# UX update:
# - Collapsible/expandable panel to avoid cluttering the main screen.
# - Three balanced source cards: NetSuite, JPMC, Deposits.
# - JPMC retains detailed operational diagnostics.
# - NetSuite/Deposits get improved visibility instead of only one metric.
if "preprocess_metrics" in st.session_state:
    ppm = st.session_state["preprocess_metrics"]

    with st.expander("📊 Pre-processing Health Summary", expanded=False):
        card_ns, card_jp, card_dep = st.columns(3)

        def _preprocess_card(title: str, found: int, ingested: int, skipped: int):
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.write(f"**Records found:** {int(found or 0):,}")
                st.markdown(
                    f"**Records ingested:** <span style='color:#22c55e;font-weight:700'>{int(ingested or 0):,}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Records skipped:** <span style='color:#ef4444;font-weight:700'>{int(skipped or 0):,}</span>",
                    unsafe_allow_html=True,
                )

        with card_ns:
            _preprocess_card(
                "🧾 NetSuite",
                ppm.get("ns_found", 0),
                ppm.get("ns_ingested", ppm.get("ns_rows", 0)),
                ppm.get("ns_skipped", ppm.get("ns_dropped", 0)),
            )

        with card_jp:
            _preprocess_card(
                "🏦 JPMC",
                ppm.get("jp_found", 0),
                ppm.get("jp_ingested", ppm.get("jp_rows", 0)),
                ppm.get("jp_skipped", 0),
            )

        with card_dep:
            if ppm.get("has_deposits"):
                _preprocess_card(
                    "💰 Deposits",
                    ppm.get("dep_found", 0),
                    ppm.get("dep_ingested", ppm.get("dep_rows", 0)),
                    ppm.get("dep_skipped", 0),
                )
            else:
                _preprocess_card("💰 Deposits", 0, 0, 0)

        st.caption(
            "Skipped record details are available in the diagnostics logs included in the ZIP export."
        )


# ─────────────────────────────────────────
@st.fragment
def section_filters():
    st.subheader("2. Filters and reconciliation")

    if all(k in st.session_state for k in ["ns_df_clean", "jp_df_clean"]):
        ns_df_clean      = st.session_state["ns_df_clean"]
        jp_df_clean      = st.session_state["jp_df_clean"]
        entities_in_data = sorted(ns_df_clean["Entity"].dropna().unique().tolist())
        top18_map        = st.session_state.get("top18_map")  # None if not uploaded

        # ── Top carrier groups selector (FEAT-01) ────────────────
        # Driven entirely by the uploaded Top18_mapping.json. The panel
        # is disabled when no JSON has been uploaded — single-Entity
        # dropdown below still works in that case.
        matched_entities: list[str] = []   # entities chosen via the panel
        unmatched_summary: list[str] = []  # per-group warnings (partial / no matches)

        if top18_map is None:
            with st.expander("🏆 Top carrier groups", expanded=False):
                st.info(
                    "Upload **Top18_mapping.json** in Section 1 to enable "
                    "carrier-group selection. The single-Entity dropdown "
                    "below still works without it."
                )
        else:
            # Pre-build a normalized lookup of NS entities so each click is O(1)
            # Key: normalized entity (CAPS, special chars stripped)
            # Val: original entity ID as it appears in NS data
            ns_norm_lookup: dict[str, str] = {
                normalize_for_match(e): e for e in entities_in_data
            }

            # Carrier-group keys, sorted alphabetically for the panel
            cg_names_sorted = sorted(top18_map.keys(), key=lambda s: s.lower())

            with st.expander(
                f"🏆 Top carrier groups ({len(cg_names_sorted)} available)",
                expanded=False,
            ):
                # ── Select-all propagation (FEAT-01 follow-up fix) ──
                # Streamlit's `value=` parameter on a checkbox is only honored
                # the first time that widget renders; on subsequent reruns the
                # session_state value wins. So toggling a master "Select all"
                # checkbox does NOT flow into per-item checkboxes once they've
                # been rendered once.
                #
                # The fix: detect the moment the master toggles, and on that
                # rerun, programmatically write the new value to every per-item
                # session_state key. After the propagation rerun, individual
                # checkboxes work independently as expected.
                select_all = st.checkbox(
                    f"Select all {len(cg_names_sorted)}", key="cg_all"
                )

                prev = st.session_state.get("_cg_all_prev", None)
                if prev is not None and prev != select_all:
                    # Master just toggled — propagate to every per-item key
                    for i in range(len(cg_names_sorted)):
                        st.session_state[f"cg_{i}"] = select_all
                st.session_state["_cg_all_prev"] = select_all

                cols_cb = st.columns(3)
                cg_selected: list[str] = []
                for i, cg_name in enumerate(cg_names_sorted):
                    # value=select_all only matters on first render. Once each
                    # cg_{i} key exists in session_state, Streamlit reads from
                    # there — which is exactly what we want, since the master
                    # propagation above has already updated those keys.
                    if cols_cb[i % 3].checkbox(cg_name, value=select_all, key=f"cg_{i}"):
                        cg_selected.append(cg_name)

                # For each selected carrier group, look up its mapped entities
                # in the JSON and check which actually exist in the loaded NS data.
                if cg_selected:
                    # Per-group status messages (built before flat list so order
                    # of warnings is meaningful for the user)
                    for cg_name in cg_selected:
                        json_entities = top18_map[cg_name]
                        found, missing = [], []
                        for je in json_entities:
                            je_norm = normalize_for_match(je)
                            if je_norm in ns_norm_lookup:
                                found.append(ns_norm_lookup[je_norm])
                            else:
                                missing.append(je)

                        matched_entities.extend(found)

                        if found and not missing:
                            # All entities matched — quiet success
                            pass
                        elif found and missing:
                            unmatched_summary.append(
                                f"**{cg_name}**: {len(found)} of {len(json_entities)} "
                                f"mapped entities found in NetSuite "
                                f"(found: {', '.join(found)} · missing: {', '.join(missing)})"
                            )
                        else:
                            unmatched_summary.append(
                                f"**{cg_name}**: none of the {len(json_entities)} "
                                f"mapped entities found in NetSuite "
                                f"(missing: {', '.join(missing)})"
                            )

                    # Deduplicate while preserving order — same NS entity could
                    # be referenced by multiple carrier groups (rare but possible)
                    matched_entities = list(dict.fromkeys(matched_entities))

                    if matched_entities:
                        st.success(
                            f"✅ {len(matched_entities)} NetSuite entit(ies) selected: "
                            f"{', '.join(matched_entities)}"
                        )
                    if unmatched_summary:
                        st.warning(
                            "⚠️ Mapping issues — review your Top18_mapping.json "
                            "or NetSuite data:\n\n" + "\n\n".join(
                                f"• {line}" for line in unmatched_summary
                            )
                        )

        # ── Standard filters ─────────────────────────────────────
        f1, f2, f3 = st.columns(3)
        with f1:
            selected_month = st.selectbox("Month", MONTHS, key="sel_month")
        with f2:
            selected_year  = st.selectbox("Year",  YEARS,  key="sel_year")
        with f3:
            if not matched_entities:
                selected_entity = st.selectbox("Entity Line ID", entities_in_data, key="sel_entity")
                entities_to_run = [selected_entity]
            else:
                st.selectbox(
                    "Entity Line ID",
                    ["— overridden by carrier-group selection —"],
                    disabled=True, key="sel_entity",
                )
                entities_to_run = matched_entities

        if st.button("START RECONCILIATION", type="primary"):
            t0 = datetime.now()
            dep_df_clean = st.session_state.get("dep_df_clean")  # None if not uploaded
            three_way    = dep_df_clean is not None

            with st.spinner(f"Running {'3-way' if three_way else '2-way'} reconciliation for {len(entities_to_run)} entit(ies)…"):
                try:
                    frames        = []
                    empty_entities = []

                    for entity in entities_to_run:
                        try:
                            frames.append(
                                reconcile_three_way(
                                    ns_df_clean, jp_df_clean, entity,
                                    selected_year, selected_month,
                                    dep_df=dep_df_clean,
                                )
                            )
                        except ReconciliationEmpty as e:
                            empty_entities.append((entity, str(e)))

                    # Schema depends on whether deposits are present
                    if three_way:
                        _empty_summary_cols = [
                            "Entity", "Month", "Year",
                            "BU", "CG",
                            "NetSuite_Total", "Chase_Total", "Deposits_Total", "Result",
                        ]
                    else:
                        _empty_summary_cols = [
                            "Entity", "Month", "Year",
                            "BU", "CG",
                            "NetSuite_Total", "Chase_Total", "Variance",
                        ]

                    if frames:
                        summary_df = pd.concat(frames, ignore_index=True)
                    else:
                        summary_df = pd.DataFrame(columns=_empty_summary_cols)

                    elapsed = datetime.now() - t0

                    st.session_state["summary_df"]    = summary_df
                    st.session_state["recon_time"]    = elapsed
                    st.session_state["three_way"]     = three_way
                    lbl = (", ".join(entities_to_run) if len(entities_to_run) <= 3
                           else f"{len(entities_to_run)} entities")
                    st.session_state["recon_label"] = f"{lbl} · {selected_month} {selected_year}"

                    # ── Surface empty-result entities clearly ────────────
                    if empty_entities:
                        with st.expander(
                            f"ℹ️ {len(empty_entities)} entit(ies) had no rows in scope — skipped",
                            expanded=True,
                        ):
                            for ent, msg in empty_entities:
                                st.write(f"**{ent}** — {msg}")

                    # Rerun so section_results picks up summary_df
                    st.rerun()
                except Exception as e:
                    st.error(f"Reconciliation failed: {e}")
    else:
        st.info("Please pre-process files first.")



section_filters()
st.markdown('---')

# ─────────────────────────────────────────
@st.fragment
def section_results():
    st.subheader("3. Results")

    if "summary_df" in st.session_state:
        summary_df = st.session_state["summary_df"]
        elapsed    = st.session_state.get("recon_time")
        label      = st.session_state.get("recon_label", "")
        three_way  = st.session_state.get("three_way", False)

        # ── Summary table ─────────────────────────────────────────
        hdr_l, hdr_r = st.columns([3, 1])
        with hdr_l:
            mode_badge = "3-way ✦ Deposits included" if three_way else "2-way"
            st.markdown(f"### Reconciliation summary — {label}  <span style='font-size:0.75em;color:#888'>({mode_badge})</span>", unsafe_allow_html=True)
        with hdr_r:
            if three_way:
                view_filter = st.radio(
                    "Show", ["All rows", "Match", "Mismatch"],
                    index=0, horizontal=True, key="view_filter",
                )
            else:
                view_filter = st.radio(
                    "Show", ["All rows", "Variances only"],
                    index=0, horizontal=True, key="view_filter",
                )

        total_rows = len(summary_df)
        if three_way:
            if view_filter == "Match":
                display_df   = summary_df[summary_df["Result"] == "Match"].copy()
                _row_caption = f"Showing <b>{len(display_df):,}</b> of {total_rows:,} rows (Match only)"
            elif view_filter == "Mismatch":
                display_df   = summary_df[summary_df["Result"] == "Mismatch"].copy()
                _row_caption = f"Showing <b>{len(display_df):,}</b> of {total_rows:,} rows (Mismatch only)"
            else:
                display_df   = summary_df
                _row_caption = f"Showing <b>{total_rows:,}</b> rows"
        else:
            if view_filter == "Variances only":
                display_df   = summary_df[summary_df["Variance"] != 0].copy()
                _row_caption = f"Showing <b>{len(display_df):,}</b> of {total_rows:,} rows (variances only)"
            else:
                display_df   = summary_df
                _row_caption = f"Showing <b>{total_rows:,}</b> rows"

        # Right-aligned row-count caption
        with hdr_r:
            st.markdown(
                f"<div style='text-align:right; color:#888; font-size:0.85em; margin-top:-0.5em;'>"
                f"{_row_caption}</div>",
                unsafe_allow_html=True,
            )

        def _color_variance(val):
            return "color: #2ecc71" if round(val, 2) == 0 else "color: #e74c3c"

        def _color_result(val):
            return "color: #2ecc71" if val == "Match" else "color: #e74c3c"

        DISPLAY_RENAMES = {
            "Entity":     "Entity Line ID",
            "CG":         "Remarks",
        }

        # Fix Arrow serialization — outer merge can leave float NaN in str cols
        for _c in ["Entity", "Month", "BU", "CG"]:
            if _c in display_df.columns:
                display_df[_c] = display_df[_c].fillna("").astype(str)

        display_df_renamed = display_df.rename(columns=DISPLAY_RENAMES)

        if len(display_df_renamed) == 0:
            st.info(
                "No reconciliation rows to display. "
                "All selected entities returned empty results — they have no "
                "`ORIG CO NAME` activity for the chosen Month/Year. "
                "Try a different period, a different entity, or check the "
                "expander above for which entities were skipped."
            )
            st.dataframe(with_serial_index(display_df_renamed), width="stretch", hide_index=True)
        else:
            if three_way:
                fmt = {
                    "NetSuite_Total":  "${:,.2f}",
                    "Chase_Total":     "${:,.2f}",
                    "Deposits_Total":  "${:,.2f}",
                }
                st.dataframe(
                    with_serial_index(display_df_renamed).style
                    .format(fmt)
                    .map(_color_result, subset=["Result"]),
                    width="stretch",
                    hide_index=True,
                )
            else:
                fmt = {
                    "NetSuite_Total": "${:,.2f}",
                    "Chase_Total":    "${:,.2f}",
                    "Variance":       "${:,.2f}",
                }
                st.dataframe(
                    with_serial_index(display_df_renamed).style
                    .format(fmt)
                    .map(_color_variance, subset=["Variance"]),
                    width="stretch",
                    hide_index=True,
                )

        if elapsed:
            mm = int(elapsed.total_seconds()) // 60
            ss = int(elapsed.total_seconds()) % 60
            st.markdown(f"**Completion time:** {mm:02d}:{ss:02d}")

        # ── Totals metrics ────────────────────────────────────────
        total_ns  = summary_df["NetSuite_Total"].sum()
        total_jp  = summary_df["Chase_Total"].sum() if three_way else summary_df.get("Chase_Total", summary_df.get("JPMC_Total", pd.Series([0]))).sum()

        if three_way:
            total_dep = summary_df["Deposits_Total"].sum()
            amount_coverage_pct = (total_dep / total_jp * 100) if total_jp else 0.0

            # Patch03 follow-up: keep the visual bar count aligned with the
            # exact Result values shown in the reconciliation table/filter.
            # The earlier helper used an eligibility mask, which could differ
            # by one row from the visible table count.
            result_series = summary_df.get("Result", pd.Series(dtype=str)).astype(str).str.strip()
            matches = int(result_series.eq("Match").sum())
            mismatches = int(result_series.eq("Mismatch").sum())
            visible_result_total = matches + mismatches
            visual_match_pct = (matches / visible_result_total * 100) if visible_result_total else 0.0

            # ─────────────────────────────────────────────────────────
            # Fix01 revised — separate financial coverage from operational
            # visual relief. Amount Coverage % is the explicit KPI:
            # Deposits Total ÷ JPMC/Chase Total. The match bar is kept only
            # as a compact visual indicator and does not expose a competing
            # percentage label.
            # ─────────────────────────────────────────────────────────
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("NetSuite Total", f"${total_ns:,.2f}")
            m2.metric("JPMC Total", f"${total_jp:,.2f}")
            m3.metric("Deposits Total", f"${total_dep:,.2f}")
            m4.metric(
                "Amount Coverage %",
                f"{amount_coverage_pct:.1f}%",
                help="Deposits Total ÷ JPMC Total. This is the primary financial coverage KPI.",
            )

            with m5:
                st.markdown("**Visual Match Bar**")
                st.progress(max(0.0, min(float(visual_match_pct) / 100, 1.0)))
                st.caption(f"✅ {matches:,} matched | ❌ {mismatches:,} unmatched")

        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total NetSuite", f"${total_ns:,.2f}")
            m2.metric("Total Chase",    f"${total_jp:,.2f}")

            total_var = (summary_df["NetSuite_Total"] - total_jp).sum() if "Variance" not in summary_df.columns else summary_df["Variance"].sum()
            var_pct   = (total_var / total_ns * 100) if total_ns else 0.0

            m3.metric(
                "Total Variance",
                f"${total_var:,.2f}",
                delta_color="inverse" if total_var < 0 else "normal"
            )

            m4.metric(
                "Variance %",
                f"{var_pct:.4f}%",
                help="Total Variance ÷ Total NetSuite × 100"
            )

        # Test06: per-table download button removed — bundle in Section 6

    else:
        st.info("Run a reconciliation to see results.")



section_results()
st.markdown('---')

# ─────────────────────────────────────────
@st.fragment
def section_trend():
    st.subheader("4. Month-over-month BU trend analysis (NetSuite only)")
    st.caption(
        "Analyzes credit totals per BU across all 12 months of the latest "
        "calendar year present in the NetSuite file. The latest month with "
        "data is always the in-progress (partial) month — its values appear "
        "in the table but are excluded from trend classification and Change "
        "calculations. At least 3 complete months are required."
    )

    if "ns_df_clean" not in st.session_state:
        st.info("Pre-process the NetSuite file first (Section 1) to enable this analysis.")
    else:
        ns_df_clean      = st.session_state["ns_df_clean"]
        entities_in_data = sorted(ns_df_clean["Entity"].dropna().unique().tolist())
        bus_in_data      = sorted(ns_df_clean["BU"].dropna().unique().tolist())

        # Optional filters use "(All)" as the first option
        ALL = "(All)"

        t1, t2, t3 = st.columns(3)
        with t1:
            trend_entity_choice = st.selectbox(
                "Entity (optional)", [ALL] + entities_in_data, index=0, key="trend_entity",
                help="Single entity to filter by, or (All) for every entity."
            )
        with t2:
            trend_bu_choice = st.selectbox(
                "BU (optional)", [ALL] + bus_in_data, index=0, key="trend_bu",
                help="Single BU to filter by, or (All) for every BU."
            )
        with t3:
            trend_top_n = st.number_input(
                "Max rows to show", min_value=1, max_value=50, value=10, step=1,
                key="trend_top_n",
                help=(
                    "Maximum number of rows to display in each trend results table. "
                    "The actual number shown may be less if fewer eligible BUs meet "
                    "the selected trend criteria after Entity/BU filters and partial-month exclusions."
                )
            )

        if st.button("▶ Run Trend Analysis", type="primary", key="run_trend"):
            ent_arg = None if trend_entity_choice == ALL else trend_entity_choice
            bu_arg  = None if trend_bu_choice     == ALL else trend_bu_choice

            scope_lbl_parts = []
            if ent_arg: scope_lbl_parts.append(ent_arg)
            if bu_arg:  scope_lbl_parts.append(f"BU {bu_arg}")
            scope_lbl = " · ".join(scope_lbl_parts) if scope_lbl_parts else "All entities · All BUs"

            with st.spinner(f"Analyzing month-over-month trends · {scope_lbl}…"):
                try:
                    dec_df, inc_df, window_meta = analyze_mom_trend(
                        ns_df_clean,
                        selected_entity=ent_arg,
                        selected_bu=bu_arg,
                        top_n=int(trend_top_n),
                    )
                    st.session_state["trend_dec"]    = dec_df
                    st.session_state["trend_inc"]    = inc_df
                    st.session_state["trend_label"]  = scope_lbl
                    st.session_state["trend_window"] = window_meta
                    # Fix04.2: force a full app rerun so Section 7 rebuilds
                    # the ZIP payload from the newly populated session data.
                    st.rerun()
                except TrendInsufficientData as e:
                    st.error(f"Trend analysis cannot run: {e}")
                    # Clear any prior results so the UI doesn't show stale data
                    for k in ("trend_dec", "trend_inc", "trend_label", "trend_window"):
                        st.session_state.pop(k, None)

        # ── Results ───────────────────────────────────────────────
        if "trend_dec" in st.session_state:
            dec_df      = st.session_state["trend_dec"]
            inc_df      = st.session_state["trend_inc"]
            lbl         = st.session_state.get("trend_label", "")
            window_meta = st.session_state.get("trend_window", {})

            # Window caption — Test07 wording
            target_year   = window_meta.get("year")
            partial_month = window_meta.get("partial_month")
            if target_year:
                window_line = f"Showing all 12 months of **{target_year}**."
                if partial_month:
                    window_line += (
                        f"  **{partial_month}** is the current in-progress month "
                        f"and is excluded from trend analysis."
                    )
                st.markdown(window_line)

            tab_dec, tab_inc = st.tabs([
                f"📉 Decreasing ({len(dec_df)})",
                f"📈 Increasing ({len(inc_df)})",
            ])

            def _color_change(val):
                """Red for negative change, green for positive."""
                try:
                    return "color: #e74c3c" if float(val) < 0 else "color: #2ecc71"
                except Exception:
                    return ""

            # Currency format applies to all 12 month columns + Change_$
            month_labels = window_meta.get("month_labels", [])
            currency_fmt = {col: "${:,.2f}" for col in month_labels}
            currency_fmt["Change_$"] = "${:,.2f}"
            currency_fmt["Change_%"] = "{:.1f}%"

            with tab_dec:
                if dec_df.empty:
                    st.success(f"No BUs with strictly decreasing credits found for {lbl}.")
                else:
                    st.markdown(
                        f"**Top {len(dec_df)} with declining credits — {lbl}**  \n"
                        f"Ranked by largest absolute dollar decline (first complete month "
                        f"vs last complete month, partial month excluded)."
                    )
                    st.dataframe(
                        with_serial_index(dec_df).style
                        .format(currency_fmt, na_rep="—")
                        .map(_color_change, subset=["Change_$", "Change_%"]),
                        width="stretch",
                        hide_index=True,
                    )
                    # Test06: per-table download button removed — bundle in Section 6

            with tab_inc:
                if inc_df.empty:
                    st.info(f"No BUs with strictly increasing credits found for {lbl}.")
                else:
                    st.markdown(
                        f"**Top {len(inc_df)} with growing credits — {lbl}**  \n"
                        f"Ranked by largest absolute dollar growth (first complete month "
                        f"vs last complete month, partial month excluded)."
                    )
                    st.dataframe(
                        with_serial_index(inc_df).style
                        .format(currency_fmt, na_rep="—")
                        .map(_color_change, subset=["Change_$", "Change_%"]),
                        width="stretch",
                        hide_index=True,
                    )
                    # Test06: per-table download button removed — bundle in Section 6



section_trend()
st.markdown('---')

# ─────────────────────────────────────────
@st.fragment
def section_round():
    st.subheader("5. Round number detection (NetSuite only)")
    st.caption(
        "Flags individual NetSuite transactions with suspiciously round credit amounts "
        "for a selected period. "
        "Round figures (e.g. 5,000 · 10,000 · 12,000) are often bonuses, marketing "
        "allowances, or reimbursements — not commissions — and may require proof of invoice."
    )

    if "ns_df_clean" not in st.session_state:
        st.info("Pre-process the NetSuite file first (Section 1) to enable this analysis.")
    else:
        ns_df_clean = st.session_state["ns_df_clean"]

        r1, r2, r3, r4 = st.columns(4)
        with r1:
            round_month = st.selectbox("Month", MONTHS, key="round_month")
        with r2:
            round_year = st.selectbox("Year", YEARS, key="round_year")
        with r3:
            round_divisor = st.selectbox(
                "Round if divisible by",
                options=[100, 250, 500, 1000, 2500, 5000],
                index=2,
                key="round_divisor",
                help=(
                    "$500 = catches $500, $1,000, $1,500, $2,000 …\n"
                    "$1,000 = only $1,000, $2,000, $5,000 …\n"
                    "$100 = broader net, more noise"
                ),
            )
        with r4:
            round_min = st.number_input(
                "Minimum amount ($)",
                min_value=0,
                value=500,
                step=100,
                key="round_min",
                help="Ignore round amounts below this threshold to reduce noise.",
            )

        if st.button("▶ Find Round Amounts", type="primary", key="run_round"):
            with st.spinner(f"Scanning all entities · {round_month} {round_year}…"):
                round_df = find_round_amounts(
                    ns_df_clean,
                    selected_year=round_year,
                    selected_month=round_month,
                    round_divisor=float(round_divisor),
                    min_amount=float(round_min),
                )
            st.session_state["round_df"]    = round_df
            st.session_state["round_label"] = f"All entities · {round_month} {round_year}"
            # Fix04.2: rebuild Section 7 download bundle after fragment-local update.
            st.rerun()

        if "round_df" in st.session_state:
            round_df    = st.session_state["round_df"]
            round_label = st.session_state.get("round_label", "")

            if round_df.empty:
                st.success(
                    f"No round-number transactions found for {round_label} "
                    f"(divisible by {round_divisor:,} · minimum {round_min:,})."
                )
            else:
                # Build the warning string without bold around dollar amounts —
                # markdown was eating the `*` characters in some renderers.
                st.warning(
                    f"⚠️  {len(round_df):,} round-number transaction(s) found — "
                    f"{round_label}  ·  divisible by {round_divisor:,}  ·  "
                    f"minimum {round_min:,}"
                )

                st.markdown("**All flagged transactions:**")

                # Format Date as date-only (drop the 00:00:00 time component).
                # Done on a display copy — session_state DataFrame is untouched.
                display_round = round_df.copy()
                if "Date" in display_round.columns:
                    display_round["Date"] = pd.to_datetime(
                        display_round["Date"], errors="coerce"
                    ).dt.strftime("%Y-%m-%d")

                st.dataframe(
                    with_serial_index(display_round).style
                    .format({"Credit": "${:,.2f}"}),
                    width="stretch",
                    hide_index=True,
                )

                # Test06: per-table download button removed — bundle in Section 6

                st.caption(
                    "💡 Suggested action: share this list with the relevant BU representatives "
                    "and request proof of invoice for each flagged amount before the audit cycle."
                )



section_round()
st.markdown('---')

# ─────────────────────────────────────────
@st.fragment
def section_materiality():
    st.subheader("6. BU materiality analysis (NetSuite only)")
    st.caption(
        "For each BU, shows every Entity ID's credit as a percentage of that BU's "
        "total credit for the selected period. Use the Materiality % to decide "
        "whether a BU + Entity combination belongs to the 90-category (high "
        "contributor) or 10-category (low contributor)."
    )

    if "ns_df_clean" not in st.session_state:
        st.info("Pre-process the NetSuite file first (Section 1) to enable this analysis.")
    else:
        _ns_mat = st.session_state["ns_df_clean"]


# ─────────────────────────────────────────────────────────
        # ─────────────────────────────────────────────────────────
        # Fix03 — BU filter for materiality analysis
        # ─────────────────────────────────────────────────────────
        m1, m2, m3 = st.columns(3)

        with m1:
            mat_month = st.selectbox("Month", MONTHS, key="mat_month")

        with m2:
            mat_year = st.selectbox("Year", YEARS, key="mat_year")

        with m3:
            available_bus = sorted(_ns_mat["BU"].dropna().unique().tolist())
            mat_bu = st.selectbox(
                "BU Filter",
                ["(All)"] + available_bus,
                key="mat_bu"
            )

        if st.button("▶ Run Materiality Analysis", type="primary", key="run_mat"):
            with st.spinner(f"Computing materiality — {mat_month} {mat_year}…"):
                mat_df = analyze_bu_materiality(
                    _ns_mat,
                    selected_year=mat_year,
                    selected_month=mat_month,
                )

            st.session_state["mat_df"] = mat_df
            st.session_state["mat_label"] = f"{mat_month} {mat_year}"
            # Fix04.2: rebuild Section 7 download bundle after fragment-local update.
            st.rerun()

        if "mat_df" in st.session_state:

            mat_df    = st.session_state["mat_df"]
            mat_label = st.session_state.get("mat_label", "")

            # Fix03 — Apply BU filter dynamically
            if mat_bu != "(All)":
                mat_df = mat_df[mat_df["BU"] == mat_bu].copy()

            if mat_df.empty:
                st.warning(f"No NetSuite data found for {mat_label}.")
            else:
                unique_bus = mat_df["BU"].nunique()
                st.success(
                    f"**{len(mat_df):,} BU + Entity combinations** across "
                    f"**{unique_bus} BUs** — {mat_label}"
                )

                def _color_materiality(val):
                    """Highlight high vs low contributors."""
                    try:
                        v = float(val)
                        if v >= 50:
                            return "color: #2ecc71; font-weight:bold"   # green — dominant
                        elif v >= 10:
                            return "color: #f39c12"                      # amber — notable
                        else:
                            return "color: #e74c3c"                      # red — low
                    except Exception:
                        return ""

                st.dataframe(
                    with_serial_index(mat_df).style
                    .format({
                        "Entity_Total":    "${:,.2f}",
                        "BU_Grand_Total":  "${:,.2f}",
                        "Materiality_Pct": "{:.2f}%",
                    })
                    .map(_color_materiality, subset=["Materiality_Pct"]),
                    width="stretch",
                )

                st.caption(
                    "🟢 ≥ 50% — dominant contributor  "
                    "🟡 10–49% — notable contributor  "
                    "🔴 < 10% — low contributor (candidate for 10-category)"
                )



section_materiality()
st.markdown('---')

# ─────────────────────────────────────────
@st.fragment
def section_download():
    st.subheader("7. Download everything")

    # Fix04.2: export bundle includes populated CORE CSVs and available
    # Diagnostics CSVs only. Intentionally excludes manifest/metadata files
    # and avoids header-only core extracts.
    _RECON_EXPORT_RENAMES = {
        "Entity": "Entity Line ID",
        "CG":     "Remarks",
    }

    _three_way = st.session_state.get("three_way", False)
    _empty_recon_cols = (
        ["Entity Line ID", "Month", "Year", "BU", "Remarks",
         "NetSuite_Total", "Chase_Total", "Deposits_Total", "Result"]
        if _three_way else
        ["Entity Line ID", "Month", "Year", "BU", "Remarks",
         "NetSuite_Total", "Chase_Total", "Variance"]
    )
    _empty_round_cols = ["BU", "Date", "Entity", "Remarks", "Credit"]
    _trend_year = (st.session_state.get("trend_window") or {}).get("year")
    _empty_trend_cols = trend_empty_schema(_trend_year)
    _empty_mat_cols = ["BU", "Entity_ID", "Entity_Total", "BU_Grand_Total", "Materiality_Pct"]

    def _frame_or_empty(key: str, default_cols: list[str]) -> pd.DataFrame:
        df = st.session_state.get(key)
        if df is None or len(df) == 0:
            return pd.DataFrame(columns=default_cols)
        return df

    def _csv_bytes(df: pd.DataFrame) -> str:
        return df.to_csv(index=False)

    _recon_df_raw = _frame_or_empty("summary_df", _empty_recon_cols)
    if not _recon_df_raw.empty and "Entity" in _recon_df_raw.columns:
        _recon_df_for_export = _recon_df_raw.rename(columns=_RECON_EXPORT_RENAMES)
    else:
        _recon_df_for_export = _recon_df_raw

    _core_targets = [
        ("core/recon_summary.csv",     _recon_df_for_export),
        ("core/trend_decreasing.csv",  _frame_or_empty("trend_dec",  _empty_trend_cols)),
        ("core/trend_increasing.csv",  _frame_or_empty("trend_inc",  _empty_trend_cols)),
        ("core/round_amounts.csv",     _frame_or_empty("round_df",   _empty_round_cols)),
        ("core/bu_materiality.csv",    _frame_or_empty("mat_df",     _empty_mat_cols)),
    ]

    # Do not write header-only core files. If a section was not generated
    # in the current Streamlit session, omit that CSV from the ZIP instead
    # of creating an empty extract that looks broken to the user.
    _core_targets = [(_path, _df) for _path, _df in _core_targets if _df is not None and len(_df) > 0]

    _diagnostic_exports = st.session_state.get("diagnostic_exports", []) or []
    _diagnostic_targets = []
    for _item in _diagnostic_exports:
        _fname = _item.get("filename")
        if not _fname:
            continue
        _zip_path = f"diagnostics/{_safe_zip_name(_fname)}"
        if os.path.exists(_fname):
            _diagnostic_targets.append((_zip_path, _fname))

    _generated_at = datetime.now()
    _total_files = len(_core_targets) + len(_diagnostic_targets)
    st.caption(
        f"Bundle includes {len(_core_targets)} populated core CSV(s) "
        f"and {len(_diagnostic_targets)} diagnostic CSV(s)."
    )

    _buf = io.BytesIO()
    with zipfile.ZipFile(_buf, "w", zipfile.ZIP_DEFLATED) as _zf:
        for _path, _df in _core_targets:
            _zf.writestr(_path, _csv_bytes(_df))
        for _zip_path, _disk_path in _diagnostic_targets:
            with open(_disk_path, "rb") as _fh:
                _zf.writestr(_zip_path, _fh.read())
    _buf.seek(0)

    st.download_button(
        label=f"⬇️ Download all outputs (zip · {_total_files} files)",
        data=_buf.getvalue(),
        file_name=f"bu_cg_outputs_v{APP_VERSION.replace('.', '_')}_{_generated_at:%Y%m%d_%H%M%S}.zip",
        mime="application/zip",
        key="dl_bundle",
    )


section_download()
st.markdown('---')


# Footer removed (Test04). APP_VERSION remains imported from config for
# internal/diagnostic use but is not displayed in the UI.