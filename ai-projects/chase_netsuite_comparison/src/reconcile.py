# ============================================================
#  reconcile.py
#  BU–CG Reconciliation Engine — Version 3.8.0
#
#  Three pure data functions:
#    reconcile()         — variance summary for one entity + period
#    analyze_mom_trend() — month-over-month BU trend classification
#    find_round_amounts()— suspicious round-dollar transaction finder
#
#  Helper:
#    trend_empty_schema() — column schema for empty trend exports
#
#  No file I/O. No Streamlit. No AI. Pure data logic.
#  Easily unit-testable in isolation.
#
#  v3.5.0 changes (Test07):
#    - analyze_mom_trend rewritten for fixed 12-month layout:
#        * Uses the MAXIMUM year present in the data (other years dropped)
#        * Always returns 12 month columns (Jan–Dec of that year)
#        * Latest month's data is shown but EXCLUDED from trend
#          classification and Change_$ / Change_% calculations
#        * No more min_months parameter (hardcoded floor of 3 inside)
#        * No more last_three_labels — replaced by always-12 month_labels
#        * Window meta now reports {year, partial_month, complete_months}
#        * BUs with <3 complete months show Trend='N/A' (still rendered)
#    - New trend_empty_schema() helper for empty-CSV exports
#
#  v3.4.0 changes (Test02 + Test03):
#    - find_round_amounts now sorts by BU ascending (was Credit desc)
#    - analyze_mom_trend rewritten:
#        * Always drops the latest month present in the data (it's
#          partial — NetSuite is extracted mid-cycle)
#        * Requires ≥ 3 complete months (raises TrendInsufficientData)
#        * Entity and BU filters both optional and single-select
#        * Returns last 3 complete months as separate columns
#        * Returns a window_meta dict for the UI caption
#    - New TrendInsufficientData exception
#
#  v3.3.0 changes:
#    - reconcile() raises ReconciliationEmpty if NS post-filter is empty
#    - "ORIG CO NAME" replaced with ORIG_CO_TOKEN constant from config
#    - analyze_mom_trend distinguishes FLAT (all deltas == 0) from
#      DECREASING (was previously misclassified as decreasing)
#    - find_round_amounts uses integer-cents arithmetic to avoid
#      floating-point edge cases on amounts like $499.99999...
# ============================================================

import pandas as pd

from config import ORIG_CO_TOKEN


# Patch03 — hardcoded Deposits BU normalization to NetSuite BU codes
DEPOSITS_BU_TO_NETSUITE_BU = {
    "PRE": "PSM",
    "APL": "PIP",
    "NEV": "IMG",
    "GCR": "GCU",
    "SMS": "MMG",
    "SBS": "MMG",
    "CMG": "MMG",
    "NHIM": "NHI",
    "NHMA": "NHI",
    "NHSA": "NHI",
    "NHSB": "NHI",
}


def normalize_deposits_bu(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with Deposits-side BU values normalized to NetSuite BU codes."""
    if df is None or df.empty or "BU" not in df.columns:
        return df.copy() if isinstance(df, pd.DataFrame) else df
    out = df.copy()
    bu = out["BU"].fillna("").astype(str).str.strip().str.upper()
    out["BU"] = bu.replace(DEPOSITS_BU_TO_NETSUITE_BU)
    return out


# ─────────────────────────────────────────
# Custom exception for empty reconciliation
# ─────────────────────────────────────────

class ReconciliationEmpty(Exception):
    """
    Raised when the NetSuite filter for a given Entity + Year + Month +
    ORIG CO NAME yields zero rows. Caller (app.py) catches this and shows
    a user-facing message rather than silently returning an empty frame.
    """
    pass


class TrendInsufficientData(Exception):
    """
    Raised by analyze_mom_trend when, after dropping the latest (incomplete)
    month from the data, fewer than 3 complete months remain. Trend analysis
    requires at least 3 complete months — anything less is just a delta or
    a single point, not a trend. Caller (app.py) catches this and shows a
    clear user-facing message.
    """
    pass


# ============================================================
#  Reconciliation
# ============================================================

def reconcile(
    ns_df: pd.DataFrame,
    jp_df: pd.DataFrame,
    selected_entity: str,
    selected_year: int,
    selected_month: str,
) -> pd.DataFrame:
    """
    Reconcile NetSuite credits vs JPMC deposits for a given entity + period.

    Both input dataframes must already be:
      - Loaded and normalized (via loaders.py)
      - Containing columns: BU, Date, Remarks, Credit, Year, MonthName
      - JPMC must additionally have BU column (mapped via BU mapping)

    Steps:
      1. Filter NS to selected Entity + Month + Year + ORIG CO NAME rows only
      2. Guard: raise ReconciliationEmpty if NS filter is empty
      3. Filter JPMC to Month + Year + BU codes present in NS + ORIG CO NAME rows
      4. Group each side by BU + Remarks, sum Credit
      5. Outer join on BU + Remarks — rows missing from either side appear with $0
      6. Compute Variance = NetSuite_Total − JPMC_Total, rounded to 2dp
         (round(2) prevents floating point $-0.00 display artifacts)
      7. Add metadata columns, sort by BU alphabetically

    Raises:
        ReconciliationEmpty — when no NS rows match the entity + period
                              + ORIG CO NAME filter. Caller should show
                              a clear message and skip this entity.

    Returns:
        DataFrame with columns:
            Entity, Month, Year, BU, CG, NetSuite_Total, JPMC_Total, Variance
    """

    # ── STEP 1 — Filter NetSuite ──────────────────────────────────────────
    # Scope to the selected entity, period, and ORIG CO NAME remarks only.
    # ORIG CO NAME is the ACH originator name — the common key between systems.
    ns_f = ns_df[
        (ns_df["Entity"]    == selected_entity.upper()) &
        (ns_df["Year"]      == selected_year) &
        (ns_df["MonthName"] == selected_month) &
        (ns_df["Remarks"].str.contains(ORIG_CO_TOKEN, na=False))
    ].copy()

    # ── STEP 2 — Empty-result guard ──────────────────────────────────────
    # Without this, the function would silently return an empty DataFrame
    # and the user would see a blank summary table with no explanation.
    if ns_f.empty:
        raise ReconciliationEmpty(
            f"No NetSuite rows found for Entity '{selected_entity}' · "
            f"{selected_month} {selected_year} with '{ORIG_CO_TOKEN}' in Remarks. "
            f"Check the Entity name, period, or that the source file contains "
            f"ACH originator rows for this scope."
        )

    # ── STEP 3 — Filter JPMC ─────────────────────────────────────────────
    # Scope to same period. Use BU codes AND Remarks found in NS (not the
    # entire JPMC file for that month) for entity isolation — this prevents
    # rows from other entities bleeding into the join.
    #
    # v3.8.0 fix: the Sonnet v3.7.1 code lost this scoping and filtered
    # only by Year + Month + ORIG_CO_TOKEN. That caused the full outer
    # merge to pull in every BU across all entities — inflating Chase
    # totals and producing thousands of spurious rows (the 8237-row bug).
    valid_bus     = ns_f["BU"].unique().tolist()
    valid_remarks = ns_f["Remarks"].unique().tolist()

    jp_f = jp_df[
        (jp_df["Year"]      == selected_year) &
        (jp_df["MonthName"] == selected_month) &
        (jp_df["BU"].isin(valid_bus)) &
        (jp_df["Remarks"].isin(valid_remarks)) &
        (jp_df["Remarks"].str.contains(ORIG_CO_TOKEN, na=False))
    ].copy()

    # ── STEP 4 — Group by BU + Remarks ───────────────────────────────────
    # Both sides grouped by same key: BU short code + ORIG CO NAME value.
    # NS BU comes from col B. JPMC BU comes from BU mapping (col F → short code).
    # These must match for the join to work — if column letters are correct
    # and BU mapping is complete, they will.
    ns_grouped = (
        ns_f
        .groupby(["BU", "Remarks"], as_index=False)["Credit"]
        .sum()
        .rename(columns={"Credit": "NetSuite_Total"})
    )
    jp_grouped = (
        jp_f
        .groupby(["BU", "Remarks"], as_index=False)["Credit"]
        .sum()
        .rename(columns={"Credit": "JPMC_Total"})
    )

    # ── STEP 5 — Outer merge on BU + Remarks ─────────────────────────────
    # Rows present on only one side appear with $0 on the other.
    summary = ns_grouped.merge(
        jp_grouped, on=["BU", "Remarks"], how="outer"
    ).fillna(0.0)

    # ── STEP 6 — Variance + rounding ─────────────────────────────────────
    summary["NetSuite_Total"] = summary["NetSuite_Total"].round(2)
    summary["JPMC_Total"]     = summary["JPMC_Total"].round(2)
    summary["Variance"]       = (summary["NetSuite_Total"] - summary["JPMC_Total"]).round(2)

    # ── STEP 7 — Metadata + column order ─────────────────────────────────
    summary["Entity"] = selected_entity
    summary["Year"]   = selected_year
    summary["Month"]  = selected_month
    summary["CG"]     = summary["Remarks"]

    # Ensure no NaN strings after outer merge
    for col in ["BU", "CG", "Entity", "Month"]:
        summary[col] = summary[col].fillna("").astype(str)

    summary = summary[[
        "Entity", "Month", "Year",
        "BU", "CG",
        "NetSuite_Total", "JPMC_Total", "Variance",
    ]]

    return summary.sort_values("BU").reset_index(drop=True)


# ============================================================
#  Month-over-month BU trend analysis (NetSuite only)
# ============================================================

# Calendar month ordering — needed to sort months correctly
# regardless of which year they appear in
MONTH_ORDER = {
    "January":1,"February":2,"March":3,"April":4,
    "May":5,"June":6,"July":7,"August":8,
    "September":9,"October":10,"November":11,"December":12
}


def analyze_mom_trend(
    ns_df: pd.DataFrame,
    selected_entity: str | None = None,
    selected_bu: str | None = None,
    top_n: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Analyze month-over-month credit trends per BU within a single calendar
    year of NetSuite data. Uses NetSuite data only — JPMC not involved.

    YEAR SELECTION (Test07):
      The function uses the MAXIMUM year value present in ns_df.
      Any rows from earlier years are silently ignored. The output table
      always shows all 12 months (January–December) of the chosen year as
      fixed columns. Months with no data render as NaN (UI shows '—').

    PARTIAL-MONTH RULE (Test07):
      The latest month present in the chosen year's data is the in-progress
      month (NetSuite is extracted mid-cycle and grows day by day until
      December 31). Its values ARE shown in the table — users want to see
      what's been reported so far — but it is EXCLUDED from:
        • Trend classification (DECREASING/INCREASING/FLAT/MIXED)
        • Change_$ and Change_% calculations

    MINIMUM DATA REQUIREMENT:
      ≥ 3 complete months (i.e. months other than the partial latest)
      must exist for ANY classification to be meaningful. If fewer,
      TrendInsufficientData is raised. Floor is hardcoded — there is no
      knob for this in the UI.

    OPTIONAL FILTERS:
      Both Entity and BU are optional and single-select. None means "all".
        Entity=None, BU=None → all entities, all BUs
        Entity=X,    BU=None → all BUs under entity X
        Entity=None, BU=Y    → BU Y across all entities
        Entity=X,    BU=Y    → single combination

    A BU is classified as:
      DECREASING — at least one delta is negative AND no delta is positive
      INCREASING — at least one delta is positive AND no delta is negative
      FLAT       — every delta is exactly zero  (excluded from top-N lists)
      MIXED      — some up, some down

    Parameters:
        ns_df            — full normalized NetSuite dataframe
        selected_entity  — entity ID to analyze, or None for all
        selected_bu      — BU short code to analyze, or None for all
        top_n            — how many BUs to return in each direction (default 10)

    Raises:
        TrendInsufficientData — when fewer than 3 complete (non-partial)
                                months exist in the chosen year.

    Returns:
        (decreasing_df, increasing_df, window_meta)

        Each result DataFrame has columns:
            Entity, BU, Trend,
            January <YEAR>, February <YEAR>, …, December <YEAR>,    ← 12 fixed
            Change_$, Change_%
        Months without data render as NaN. The partial month appears with
        its actual value but does NOT contribute to Trend / Change_$ / Change_%.

        window_meta carries caption info:
            {
              "year":             2026,
              "month_labels":     ["January 2026", …, "December 2026"],   # always 12
              "partial_month":    "April 2026",   # the in-progress month, or None
              "complete_months":  ["January 2026", "February 2026", "March 2026"],
              "num_complete":     3,
            }
    """

    MIN_COMPLETE = 3   # hardcoded — see docstring

    # Always 12 columns. Month numbers 1-12 in chronological order.
    num_to_name = {v: k for k, v in MONTH_ORDER.items()}

    empty_meta = {
        "year": None, "month_labels": [], "partial_month": None,
        "complete_months": [], "num_complete": 0,
    }

    # ── Step 1: Find the MAX year and filter to that year only ────────────
    if ns_df.empty:
        return pd.DataFrame(), pd.DataFrame(), empty_meta

    years_in_data = ns_df["Year"].dropna()
    if years_in_data.empty:
        return pd.DataFrame(), pd.DataFrame(), empty_meta

    target_year = int(years_in_data.max())
    df_year = ns_df[ns_df["Year"] == target_year].copy()

    # Always 12 fixed month-column labels for this year, in chronological order
    month_labels = [f"{num_to_name[m]} {target_year}" for m in range(1, 13)]

    # ── Step 2: Identify the partial (latest) month present in the year ───
    df_year["MonthNum"] = df_year["MonthName"].map(MONTH_ORDER)
    months_with_data    = sorted(df_year["MonthNum"].dropna().unique().astype(int).tolist())

    if not months_with_data:
        return pd.DataFrame(), pd.DataFrame(), {**empty_meta, "year": target_year, "month_labels": month_labels}

    partial_month_num = months_with_data[-1]
    partial_label     = f"{num_to_name[partial_month_num]} {target_year}"
    complete_month_nums = months_with_data[:-1]
    complete_labels     = [f"{num_to_name[m]} {target_year}" for m in complete_month_nums]
    num_complete        = len(complete_month_nums)

    # ── Step 3: Apply optional Entity / BU filters ────────────────────────
    if selected_entity:
        df_year = df_year[df_year["Entity"] == selected_entity.upper()]
    if selected_bu:
        df_year = df_year[df_year["BU"] == selected_bu.upper()]

    base_meta = {
        "year":            target_year,
        "month_labels":    month_labels,
        "partial_month":   partial_label,
        "complete_months": complete_labels,
        "num_complete":    num_complete,
    }

    if df_year.empty:
        return pd.DataFrame(), pd.DataFrame(), base_meta

    # ── Step 4: Validate ≥ MIN_COMPLETE complete months exist ─────────────
    # Check is on the YEAR-level data (not the filtered slice) so the user
    # gets a clear "not enough data globally" message rather than per-filter.
    if num_complete < MIN_COMPLETE:
        scope_parts = []
        if selected_entity: scope_parts.append(f"Entity '{selected_entity}'")
        if selected_bu:     scope_parts.append(f"BU '{selected_bu}'")
        scope_str = " · ".join(scope_parts) if scope_parts else "the selected scope"
        raise TrendInsufficientData(
            f"Trend analysis requires at least {MIN_COMPLETE} complete months. "
            f"In {target_year}, only {num_complete} complete month(s) exist "
            f"(latest month '{partial_label}' is in-progress and excluded). "
            f"Scope: {scope_str}. Wait for more historical data and try again."
        )

    # ── Step 5: Group by Entity + BU + MonthNum, sum credits ──────────────
    grouped = (
        df_year.groupby(["Entity", "BU", "MonthNum"], as_index=False)["Credit"]
        .sum()
        .sort_values(["Entity", "BU", "MonthNum"])
    )

    # ── Step 6: Per (Entity, BU) — build row, classify on COMPLETE months ─
    # Trend classification and Change calculations use ONLY the complete
    # months — partial month is shown but does not influence the verdict.
    results = []

    for (entity, bu), grp in grouped.groupby(["Entity", "BU"]):
        grp = grp.sort_values("MonthNum").reset_index(drop=True)
        month_to_credit = dict(zip(grp["MonthNum"].astype(int), grp["Credit"]))

        # Build all 12 month columns — NaN where this BU has no data
        month_cols = {
            f"{num_to_name[m]} {target_year}":
                round(month_to_credit[m], 2) if m in month_to_credit else float("nan")
            for m in range(1, 13)
        }

        # Classification series: only complete months that this BU actually has
        bu_complete_credits = [
            month_to_credit[m] for m in complete_month_nums if m in month_to_credit
        ]

        if len(bu_complete_credits) < MIN_COMPLETE:
            # This BU doesn't have enough complete-month data of its own.
            # Mark as N/A — still display the row (user wants to see all BUs)
            # but exclude from top-N decreasing/increasing lists.
            row = {
                "Entity":   entity,
                "BU":       bu,
                "Trend":    "N/A",
                **month_cols,
                "Change_$": float("nan"),
                "Change_%": float("nan"),
            }
            results.append(row)
            continue

        first_total = bu_complete_credits[0]
        last_total  = bu_complete_credits[-1]

        deltas = [
            round(bu_complete_credits[i] - bu_complete_credits[i-1], 2)
            for i in range(1, len(bu_complete_credits))
        ]
        has_neg = any(d < 0 for d in deltas)
        has_pos = any(d > 0 for d in deltas)

        if not has_neg and not has_pos:
            trend = "FLAT"
        elif has_neg and not has_pos:
            trend = "DECREASING"
        elif has_pos and not has_neg:
            trend = "INCREASING"
        else:
            trend = "MIXED"

        change_dollar = round(last_total - first_total, 2)
        change_pct    = round(((last_total - first_total) / first_total * 100), 1) if first_total else 0.0

        row = {
            "Entity":   entity,
            "BU":       bu,
            "Trend":    trend,
            **month_cols,
            "Change_$": change_dollar,
            "Change_%": change_pct,
        }
        results.append(row)

    if not results:
        return pd.DataFrame(), pd.DataFrame(), base_meta

    all_df = pd.DataFrame(results)

    # Column order: Entity, BU, Trend, <12 months Jan–Dec>, Change_$, Change_%
    col_order = ["Entity", "BU", "Trend"] + month_labels + ["Change_$", "Change_%"]
    all_df = all_df[col_order]

    # ── Step 7: Split and rank ────────────────────────────────────────────
    dec_df = (
        all_df[all_df["Trend"] == "DECREASING"]
        .sort_values("Change_$", ascending=True)    # most negative first
        .head(top_n)
        .reset_index(drop=True)
    )
    inc_df = (
        all_df[all_df["Trend"] == "INCREASING"]
        .sort_values("Change_$", ascending=False)   # most positive first
        .head(top_n)
        .reset_index(drop=True)
    )

    return dec_df, inc_df, base_meta


def trend_empty_schema(year: int | None = None) -> list[str]:
    """
    Return the exact column schema for an empty trend DataFrame, for use in
    Test06's Section 6 bundle when no analysis has been run yet (or no
    decreasing/increasing BUs were found). Year defaults to the current
    year-of-the-data convention (caller can pass year=None for a generic
    placeholder).

    Used by app.py when generating empty CSVs — guarantees a recipient of
    the zip always sees the same column structure.
    """
    num_to_name = {v: k for k, v in MONTH_ORDER.items()}
    if year is None:
        # Generic placeholders; real runs will overwrite with the data's max year
        month_labels = [num_to_name[m] for m in range(1, 13)]
    else:
        month_labels = [f"{num_to_name[m]} {year}" for m in range(1, 13)]
    return ["Entity", "BU", "Trend"] + month_labels + ["Change_$", "Change_%"]


# ============================================================
#  Round number detection (NetSuite only)
# ============================================================

def find_round_amounts(
    ns_df: pd.DataFrame,
    selected_year: int,
    selected_month: str,
    round_divisor: float = 500.0,
    min_amount: float = 500.0,
) -> pd.DataFrame:
    """
    Find individual NetSuite transactions with suspiciously round credit amounts
    for a given period across ALL entities. Returns raw transaction rows.

    A transaction is flagged when:
      1. Credit amount >= min_amount
      2. Credit amount is exactly divisible by round_divisor (no cents remainder)

    v3.3.0 fix: divisibility check now uses integer-cents arithmetic
    (round(x*100)) instead of float modulo. This avoids edge cases where
    a value like 499.9999999998 would slip through `% 500.0 == 0` due to
    float representation, or where 500.00 would fail `% 500.0 == 0` for
    the same reason.

    Parameters:
        ns_df          — full normalized NetSuite dataframe
        selected_year  — year filter
        selected_month — month name filter
        round_divisor  — divisibility threshold (default $500)
        min_amount     — minimum credit to consider (default $500)

    Returns:
        DataFrame with columns: BU, Date, Entity, Remarks, Credit
        Sorted by BU ascending (alphabetical) for predictable scanning.
    """

    cols_out = ["BU", "Date", "Entity", "Remarks", "Credit"]

    # ── Filter to period only — all entities ──────────────────────────────
    df = ns_df[
        (ns_df["Year"]      == selected_year) &
        (ns_df["MonthName"] == selected_month)
    ].copy()

    if df.empty:
        return pd.DataFrame(columns=cols_out)

    # Patch01 — known operational false-positive; exclude from rounding review.
    # Rule: BU=NAA, Entity=HEALTH ALLIANCE, Remarks=ORIG CO NAME=INTEGRATED TRUST.
    _bu = df["BU"].fillna("").astype(str).str.strip().str.upper() if "BU" in df.columns else ""
    _entity = df["Entity"].fillna("").astype(str).str.strip().str.upper() if "Entity" in df.columns else ""
    _remarks = df["Remarks"].fillna("").astype(str).str.strip().str.upper() if "Remarks" in df.columns else ""
    _skip_mask = (
        (_bu == "NAA") &
        (_entity == "HEALTH ALLIANCE") &
        (_remarks == "ORIG CO NAME=INTEGRATED TRUST")
    )
    df = df[~_skip_mask].copy()

    if df.empty:
        return pd.DataFrame(columns=cols_out)

    # ── Apply round number filter using integer-cents arithmetic ──────────
    # Convert dollars → cents as ints to dodge float modulo edge cases.
    credit_cents  = (df["Credit"].round(2) * 100).round().astype("int64")
    divisor_cents = int(round(round_divisor * 100))
    min_cents     = int(round(min_amount    * 100))

    if divisor_cents <= 0:
        # Defensive: a divisor of 0 would raise ZeroDivisionError on modulo
        return pd.DataFrame(columns=cols_out)

    flagged = df[
        (credit_cents >= min_cents) &
        (credit_cents % divisor_cents == 0)
    ].copy()

    if flagged.empty:
        return pd.DataFrame(columns=cols_out)

    return (
        flagged[cols_out]
        .sort_values("BU", ascending=True)
        .reset_index(drop=True)
    )


# ============================================================
#  Three-way reconciliation — NS + Chase + Deposits (optional)
# ============================================================

def reconcile_three_way(
    ns_df: pd.DataFrame,
    jp_df: pd.DataFrame,
    selected_entity: str,
    selected_year: int,
    selected_month: str,
    dep_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Extends reconcile() to include Deposits as a third source.

    Fix A: Deposits scoped by valid_bus + valid_remarks from NS result
           so cross-carrier orphan rows are excluded.
    Fix B: Orphan deposit rows get Entity/Month filled with selected
           scope values instead of float 0.0.
    """
    two_way = reconcile(ns_df, jp_df, selected_entity, selected_year, selected_month)

    if dep_df is None:
        return two_way.rename(columns={"JPMC_Total": "Chase_Total"})

    # Patch03: normalize Deposits-side BU values to NetSuite BU codes before
    # reconciliation scoping/grouping. UI/export intentionally show normalized BU only.
    dep_df = normalize_deposits_bu(dep_df)

    # Fix A: scope Deposits by BU + Remarks from NS result
    valid_bus     = set(two_way["BU"].dropna().unique())
    valid_remarks = set(two_way["CG"].dropna().unique())

    dep_f = dep_df[
        (dep_df["Year"]      == selected_year) &
        (dep_df["MonthName"] == selected_month) &
        (dep_df["BU"].isin(valid_bus)) &
        (dep_df["Remarks"].isin(valid_remarks))
    ].copy()

    dep_grouped = (
        dep_f
        .groupby(["BU", "Remarks"], as_index=False)["Amount"]
        .sum()
        .rename(columns={"Amount": "Deposits_Total"})
    )
    dep_grouped["Deposits_Total"] = dep_grouped["Deposits_Total"].round(2)

    three_way = two_way.merge(
        dep_grouped.rename(columns={"Remarks": "CG"}),
        on=["BU", "CG"],
        how="outer",
    ).fillna(0.0)

    three_way["NetSuite_Total"] = three_way["NetSuite_Total"].round(2)
    three_way["JPMC_Total"]     = three_way["JPMC_Total"].round(2)
    three_way["Deposits_Total"] = three_way["Deposits_Total"].round(2)

    # Fix B: fill orphan metadata — replace float 0.0 with correct scope values
    def _fix_str(v, fallback):
        if not isinstance(v, str) or v in ("", "0.0", "0"):
            return fallback
        return v

    three_way["Entity"] = three_way["Entity"].apply(lambda v: _fix_str(v, selected_entity))
    three_way["Month"]  = three_way["Month"].apply(lambda v: _fix_str(v, selected_month))
    three_way["Year"]   = three_way["Year"].apply(
        lambda v: selected_year if (isinstance(v, float) and v == 0.0) or v == 0 else v
    )

    three_way["Result"] = three_way.apply(
        lambda r: "Match"
        if r["NetSuite_Total"] == r["JPMC_Total"] == r["Deposits_Total"]
        else "Mismatch",
        axis=1,
    )

    three_way = three_way[[
        "Entity", "Month", "Year",
        "BU", "CG",
        "NetSuite_Total", "JPMC_Total", "Deposits_Total", "Result",
    ]].rename(columns={"JPMC_Total": "Chase_Total"})

    return three_way.sort_values("BU").reset_index(drop=True)


def analyze_bu_materiality(
    ns_df: pd.DataFrame,
    selected_year: int,
    selected_month: str,
) -> pd.DataFrame:
    """
    For each BU in the selected month + year, compute each Entity ID's
    share of that BU's total credit — the materiality % — which the
    team uses to classify BU+Entity combinations as 90-category
    (high contributor) or 10-category (low contributor).

    Logic:
        Grand Total (BU) = SUM(Credit) for ALL Entity IDs under that BU
        Entity Total     = SUM(Credit) for ONE Entity ID under that BU
        Materiality %    = Entity Total / Grand Total (BU) × 100

    Filtered to ORIG CO NAME rows only — same scope as the reconciliation
    table, so materiality percentages are comparable with recon totals.

    Parameters:
        ns_df          — full normalized NetSuite dataframe (all periods)
        selected_year  — year to analyze
        selected_month — month name to analyze (e.g. "March")

    Returns:
        DataFrame with columns:
            BU, Entity_ID, Entity_Total, BU_Grand_Total, Materiality_Pct
        Sorted by BU ascending, then Materiality_Pct descending within BU.
        Empty DataFrame with same schema if no data found for the period.
    """
    COLS_OUT = ["BU", "Entity_ID", "Entity_Total", "BU_Grand_Total", "Materiality_Pct"]

    df = ns_df[
        (ns_df["Year"]      == selected_year) &
        (ns_df["MonthName"] == selected_month) &
        (ns_df["Remarks"].str.contains(ORIG_CO_TOKEN, na=False))
    ].copy()

    if df.empty:
        return pd.DataFrame(columns=COLS_OUT)

    entity_totals = (
        df.groupby(["BU", "Entity"], as_index=False)["Credit"]
        .sum()
        .rename(columns={"Credit": "Entity_Total", "Entity": "Entity_ID"})
    )
    entity_totals["Entity_Total"] = entity_totals["Entity_Total"].round(2)

    bu_totals = (
        entity_totals.groupby("BU", as_index=False)["Entity_Total"]
        .sum()
        .rename(columns={"Entity_Total": "BU_Grand_Total"})
    )

    result = entity_totals.merge(bu_totals, on="BU", how="left")
    result["Materiality_Pct"] = (
        result["Entity_Total"] / result["BU_Grand_Total"] * 100
    ).round(2)

    return (
        result[COLS_OUT]
        .sort_values(["BU", "Materiality_Pct"], ascending=[True, False])
        .reset_index(drop=True)
    )