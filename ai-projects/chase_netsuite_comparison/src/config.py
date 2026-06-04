# ============================================================
#  config.py
#  BU–CG Reconciliation Engine — Version 3.9.8
#
#  Central constants file. Change values here only.
#
#  AI layer has been removed from this version.
#  See HANDOVER.md for options to re-enable AI in future.
# ============================================================

# ── App settings ─────────────────────────────────────────────
APP_VERSION        = "3.9.9.2"
ROUNDING_TOLERANCE = 0.01

# ── ACH originator token ─────────────────────────────────────
# The string used to identify ACH originator rows in the Remarks
# field of both NetSuite and JPMC. This is the common key between
# the two systems — both sides are filtered to rows containing
# this token before any grouping or matching.
#
# Centralised here so a typo in one place can't silently break
# reconciliation. NEVER hardcode "ORIG CO NAME" anywhere else.
ORIG_CO_TOKEN = "ORIG CO NAME"

# ── JPMC noise tokens ────────────────────────────────────────
# Substrings (case-insensitive) used to drop noise rows from the
# JPMC source during normalization. Cash concentration entries
# are internal sweeps between accounts — they don't represent
# customer deposits and would inflate the JPMC totals.
JPMC_NOISE_TOKENS = [
    "CASH CONCENTRATION",
]

# ── Carrier groups (FEAT-01) ─────────────────────────────────
# The list of carrier groups (formerly "Top 18") is now driven by
# the user-uploaded Top18_mapping.json file. The single source of
# truth for which carrier groups exist and which NetSuite Entity
# Line IDs belong to each is the JSON. config.py no longer maintains
# a parallel hardcoded list.
#
# See Top18_mapping.example.json for the expected file format.

# ── Default column configuration ─────────────────────────────
# Mirrors the original columns.json. Used as the pre-fill values
# for the sidebar column editor in app.py (_DEFAULT_CFG).
# When Snowflake mode is active, these hold column names instead
# of Excel letters — same structure, different values.
DEFAULT_COLUMN_CFG = {
    "netsuite": {
        "BU":      "B",
        "DATE":    "E",
        "ENTITY":  "J",
        "REMARKS": "M",
        "CREDIT":  "O",
    },
    "jpmc": {
        "BU_FULL": "F",
        "DATE":    "H",
        "CREDIT":  "N",
        "REMARKS": "L",
    },
    "bu_mapping": {
        "BU":      "A",
        "BU_FULL": "B",
    },
    "deposits": {
        "BU":      "D",   # COMPANY_BUSINESS_UNIT_CODE
        "DATE":    "F",   # DEPOSIT_DATE
        "AMOUNT":  "I",   # DEPOSIT_AMOUNT
        "REMARKS": "K",   # NOTES (contains ORIG CO NAME)
    },
}


# ── Calendar ─────────────────────────────────────────────────
# Month and year lists used by multiple Streamlit sections.
# Lifted to module scope to avoid duplicate definitions in app.py.
from datetime import datetime as _dt

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

# Years from current year back to 2018 (inclusive). Used by the
# Year selectors in Sections 2 and 5.
YEARS = list(range(_dt.now().year, 2017, -1))
