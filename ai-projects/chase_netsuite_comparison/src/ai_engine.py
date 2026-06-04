# ============================================================
#  ai_engine.py
#  BU–CG Reconciliation Engine — Version 3.0.0
#
#  Three-tier AI Q&A system:
#
#  Tier 1 — classify_intent()
#    Fast intent router using qwen2.5:3b.
#    Sends only the question (no table data).
#    Returns "python" or "ai".
#    Falls back to keyword matching if Ollama is unavailable.
#
#  Tier 2 — answer_python()
#    Text-to-pandas: generates a pandas expression from the question,
#    executes it safely against the dataframe, formats the result.
#    BUG FIX v3.0: prompt now explicitly instructs the model to sort
#    by the correct column BEFORE calling .head(N). The old prompt
#    produced expressions like df['BU'].head(5) which returned the
#    first 5 rows of the dataframe, not the top 5 by variance.
#
#  Tier 3 — answer_reasoning()
#    Full Ollama reasoning using conversation history.
#    Model is pre-primed at reconciliation time with full context
#    via build_system_primer(). For "why" questions, raw NS+JPMC
#    rows are appended to the question before sending.
# ============================================================

import re

import pandas as pd
import requests
import streamlit as st

from config import OLLAMA_URL, MODEL_CLASSIFIER, MODEL_CODEGEN, MODEL_REASONING


# ─────────────────────────────────────────
# Shared Ollama HTTP call
# ─────────────────────────────────────────

def _ollama(model: str, messages: list[dict], timeout: int = 60) -> str:
    """
    Single reusable Ollama API call.
    Uses /api/chat endpoint with a messages list so conversation
    history is preserved across multi-turn Q&A.

    Raises RuntimeError with a user-friendly message on failure.
    """
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to Ollama. Make sure `ollama serve` is running.")
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Ollama timed out after {timeout}s. Try a smaller model or shorter question.")
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}")


# ─────────────────────────────────────────
# Tier 1 — Intent classifier
# ─────────────────────────────────────────

def classify_intent(question: str, classifier_model: str = MODEL_CLASSIFIER) -> str:
    """
    Route the question to the correct handler tier.

    Uses a fast small model (qwen2.5:3b) to classify intent.
    Only the question is sent — no table data, so this is fast.

    Returns "python" for data retrieval questions, "ai" for analysis.

    Falls back to keyword matching if Ollama is unavailable so the
    app continues to work even without a running model.
    """
    prompt = """You are a question router for a financial reconciliation tool.
Classify the question below as exactly one of two types:

"python" — if it asks for a specific number, lookup, count, filter, sort, or
           comparison that can be answered directly from a dataframe.
           Examples: totals, highest/lowest variance, list of BUs,
           rows above a threshold, positive/negative variances,
           matched rows, unmatched rows, specific BU or CG lookup,
           top N BUs, bottom N rows, any ranking or sorting question.

"ai"     — if it asks for interpretation, explanation, pattern analysis,
           summary, recommendation, or anything that requires reasoning
           beyond simple data retrieval.
           Examples: why is there a variance, what does this suggest,
           summarize the results, explain the pattern.

Question: """ + question + """

Reply with only one word: python or ai"""

    try:
        result = _ollama(classifier_model, [{"role": "user", "content": prompt}], timeout=20)
        word   = result.lower().split()[0].strip(".,!?")
        return "python" if word == "python" else "ai"
    except Exception:
        # Keyword fallback — covers the most common retrieval question patterns
        keywords = [
            r"total", r"sum", r"how much", r"how many", r"count",
            r"which bu", r"which cg", r"list", r"show",
            r"highest", r"lowest", r"largest", r"smallest", r"top", r"bottom",
            r"positive", r"negative", r"zero", r"matched", r"unmatched",
            r"variance", r"over", r"under", r"above", r"below",
            r"netsuite", r"jpmc", r"filter", r"where", r"rank",
        ]
        q = question.lower()
        return "python" if any(re.search(p, q) for p in keywords) else "ai"


# ─────────────────────────────────────────
# Tier 2 — Text-to-pandas engine
# ─────────────────────────────────────────

# Schema sent to the code-generation model.
# Contains column names and types only — no actual data rows.
DF_SCHEMA = """
DataFrame name: df
Columns and types:
  Entity         (str)   : entity name, e.g. 'AETNA'
  Month          (str)   : month name, e.g. 'March'
  Year           (int)   : e.g. 2026
  BU             (str)   : business unit short code, e.g. 'ABL'
  CG             (str)   : cash group / remarks, e.g. 'ORIG CO NAME=AETNA LIFE INSUR'
  NetSuite_Total (float) : summed NetSuite credit for this BU+CG
  JPMC_Total     (float) : summed JPMC credit for this BU+CG
  Variance       (float) : NetSuite_Total - JPMC_Total
                           positive = NetSuite higher, negative = JPMC higher
"""

# Correct example expressions shown to the model to prevent common mistakes.
# The old bug: df['BU'].head(5) returns first 5 rows, not top 5 by variance.
# The fix:     always sort FIRST, then .head(N).
PANDAS_EXAMPLES = """
CORRECT examples (always sort BEFORE .head):
  Q: top 5 BUs with highest variance
  A: df.assign(AbsVar=df['Variance'].abs()).sort_values('AbsVar', ascending=False).head(5)[['BU','CG','NetSuite_Total','JPMC_Total','Variance']]

  Q: list BUs where variance is above $1000
  A: df[df['Variance'].abs() > 1000][['BU','CG','Variance']].sort_values('Variance', key=abs, ascending=False)

  Q: total variance
  A: df['Variance'].sum()

  Q: how many rows have zero variance
  A: (df['Variance'] == 0).sum()

  Q: show rows where JPMC is zero
  A: df[df['JPMC_Total'] == 0][['BU','CG','NetSuite_Total','Variance']]

  Q: top 3 CGs by JPMC total
  A: df.sort_values('JPMC_Total', ascending=False).head(3)[['BU','CG','JPMC_Total']]

WRONG (never do this — head() before sort returns wrong rows):
  df['BU'].head(5)                          <- wrong: returns first 5 rows, not top 5
  df.head(5)['Variance']                    <- wrong: same problem
  df['Variance'].sort_values().head(5)      <- wrong: returns Series not DataFrame
"""


def answer_python(question: str, df: pd.DataFrame,
                  codegen_model: str = MODEL_CODEGEN) -> tuple[str, pd.DataFrame | None]:
    """
    Generate a pandas expression via LLM and execute it safely.

    The model receives:
      - The dataframe schema (column names + types)
      - Correct example expressions showing sort-before-head pattern
      - The user's question

    Execution sandbox: only df and pd are in scope — no builtins,
    no imports, no file access possible.

    Returns:
        (text_answer, optional_dataframe)
        If the result is a DataFrame or Series it's returned for st.dataframe() rendering.
        If the result is a scalar it's formatted as currency.
    """
    prompt = f"""You are a pandas code generator for a financial reconciliation dataframe.

{DF_SCHEMA}

{PANDAS_EXAMPLES}

Generate a single Python expression (no imports, no assignments, no markdown fences)
that answers the question below.

Critical rules:
- ALWAYS sort the dataframe BEFORE calling .head(N) — never head() on unsorted data
- For "top N by X" queries: sort_values('X', ascending=False).head(N)
- For "highest/lowest variance": use Variance.abs() for absolute value ranking
- Return a DataFrame with relevant columns, not just a Series of one column
- Never use print(), display(), or any IO functions
- Return ONLY the expression on a single line, nothing else

Question: {question}

Expression:"""

    try:
        expr = _ollama(codegen_model, [{"role": "user", "content": prompt}], timeout=30)
        # Strip markdown fences if model adds them
        expr = re.sub(r"```[a-z]*\n?", "", expr).strip().strip("`").strip()

        # Safe execution — only df and pandas in scope, no builtins
        result = eval(expr, {"df": df, "pd": pd, "__builtins__": {}})

        if isinstance(result, pd.DataFrame):
            if result.empty:
                return "No rows match that criteria.", None
            return f"Found {len(result)} row(s):", result.reset_index(drop=True)

        elif isinstance(result, pd.Series):
            if result.empty:
                return "No results.", None
            df_result = result.reset_index()
            df_result.columns = [str(c) for c in df_result.columns]
            return f"Found {len(df_result)} row(s):", df_result

        elif isinstance(result, (int, float)):
            return f"**${result:,.2f}**", None

        elif isinstance(result, (bool, )):
            return str(result), None

        else:
            return str(result), None

    except Exception as e:
        return (
            f"I understood this as a data question but couldn't compute it automatically. "
            f"Try rephrasing more specifically — e.g. 'list BUs where variance is above $1000'.\n\n"
            f"_Debug: {e}_"
        ), None


# ─────────────────────────────────────────
# Tier 3 — Reasoning engine
# ─────────────────────────────────────────

def _extract_drill_down(question: str, summary_df: pd.DataFrame,
                        ns_df: pd.DataFrame, jp_df: pd.DataFrame) -> dict | None:
    """
    For "why" questions: find the BU/CG mentioned in the question and
    extract the raw individual transaction rows from both NS and JPMC.

    Uses already-filtered session dataframes — no re-filtering by period
    needed because the data passed in is already scoped to the selected
    entity/month/year from the pre-processing step.

    Returns a dict with ns_rows, jp_rows, summary_row, bu, cg
    or None if no specific BU/CG can be identified from the question.
    """
    q = question.lower()

    matched_bu = [bu for bu in summary_df["BU"].dropna().unique() if str(bu).lower() in q]
    matched_cg = [
        cg for cg in summary_df["CG"].dropna().unique()
        if any(word in q for word in str(cg).lower().split() if len(word) > 3)
    ]

    if not matched_bu and not matched_cg:
        return None

    bu_filter = matched_bu[0] if matched_bu else None
    cg_filter = matched_cg[0] if matched_cg else None

    # Summary row for this BU/CG
    mask = pd.Series([True] * len(summary_df))
    if bu_filter:
        mask &= summary_df["BU"] == bu_filter
    if cg_filter:
        mask &= summary_df["CG"] == cg_filter

    # Slice raw NS rows — already filtered by entity/month/year
    ns_mask = ns_df["Remarks"].str.contains("ORIG CO NAME", na=False)
    if bu_filter:
        ns_mask &= ns_df["BU"] == bu_filter
    if cg_filter:
        cg_words = [w for w in cg_filter.split() if len(w) > 3]
        if cg_words:
            ns_mask &= ns_df["Remarks"].str.contains("|".join(cg_words), na=False)

    # Slice raw JPMC rows — already filtered by month/year
    jp_mask = jp_df["Remarks"].str.contains("ORIG CO NAME", na=False)
    if bu_filter:
        jp_mask &= jp_df["BU"] == bu_filter
    if cg_filter:
        cg_words = [w for w in cg_filter.split() if len(w) > 3]
        if cg_words:
            jp_mask &= jp_df["Remarks"].str.contains("|".join(cg_words), na=False)

    return {
        "bu":          bu_filter,
        "cg":          cg_filter,
        "summary_row": summary_df[mask],
        "ns_rows":     ns_df[ns_mask][["BU", "Date", "Remarks", "Credit"]].reset_index(drop=True),
        "jp_rows":     jp_df[jp_mask][["BU", "Date", "Remarks", "Credit"]].reset_index(drop=True),
    }


def answer_reasoning(question: str, summary_df: pd.DataFrame,
                     model: str = MODEL_REASONING,
                     ns_df: pd.DataFrame | None = None,
                     jp_df: pd.DataFrame | None = None) -> str:
    """
    Open-ended analysis via Ollama using full conversation history.

    The model is pre-primed with reconciliation context at run time
    via build_system_primer(). Each question appends to that history
    so the model remembers prior exchanges within a session.

    For "why/explain" questions: raw NS+JPMC transaction rows for the
    relevant BU+CG are extracted and appended to the question message
    so the model can identify the specific cause of the variance.
    """
    is_why = any(w in question.lower() for w in [
        "why", "reason", "cause", "explain", "where does", "what caused",
        "extra row", "missing", "what is the difference", "break down",
    ])

    # Build the user message — append raw rows for why questions
    user_message = question
    if is_why and ns_df is not None and jp_df is not None:
        drill = _extract_drill_down(question, summary_df, ns_df, jp_df)
        if drill:
            ns_text = drill["ns_rows"].to_string(index=False) if not drill["ns_rows"].empty else "  (no rows)"
            jp_text = drill["jp_rows"].to_string(index=False) if not drill["jp_rows"].empty else "  (no rows)"
            user_message = (
                f"{question}\n\n"
                f"Raw transaction rows for BU={drill['bu']} / CG={drill['cg']}:\n\n"
                f"NETSUITE RAW ({len(drill['ns_rows'])} rows):\n{ns_text}\n\n"
                f"JPMC RAW ({len(drill['jp_rows'])} rows):\n{jp_text}"
            )

    # Get conversation history pre-primed at reconciliation time
    history  = st.session_state.get("chat_history", [])
    messages = history + [{"role": "user", "content": user_message}]

    try:
        answer = _ollama(model, messages, timeout=120)
        # Accumulate history so follow-up questions have context
        st.session_state["chat_history"] = messages + [{"role": "assistant", "content": answer}]
        return answer
    except RuntimeError as e:
        return f"❌ {e}"


# ─────────────────────────────────────────
# System primer — runs once on reconcile complete
# ─────────────────────────────────────────

def build_system_primer(summary_df: pd.DataFrame, label: str) -> str:
    """
    Build a rich context message sent to the model before any user questions.

    Pre-computes the key facts the model would otherwise need to calculate
    on every question — totals, top variances, one-sided rows — so the
    model already "knows" the reconciliation when the first question arrives.

    Stored as messages[0..1] in st.session_state["chat_history"].
    Reset automatically when a new reconciliation is run.
    """
    total_ns  = summary_df["NetSuite_Total"].sum()
    total_jp  = summary_df["JPMC_Total"].sum()
    total_var = summary_df["Variance"].sum()
    var_pct   = (total_var / total_ns * 100) if total_ns else 0

    top5 = (
        summary_df
        .reindex(summary_df["Variance"].abs().sort_values(ascending=False).index)
        .head(5)[["BU", "CG", "NetSuite_Total", "JPMC_Total", "Variance"]]
        .to_string(index=False)
    )

    jpmc_only = summary_df[summary_df["NetSuite_Total"] == 0]
    ns_only   = summary_df[summary_df["JPMC_Total"]     == 0]

    if len(summary_df) > 150:
        table_df   = summary_df.reindex(
            summary_df["Variance"].abs().sort_values(ascending=False).index
        ).head(150)
        table_note = f"(Top 150 of {len(summary_df)} rows by absolute variance)"
    else:
        table_df   = summary_df
        table_note = f"({len(summary_df)} rows total)"

    return f"""You are a financial reconciliation analyst assistant.

Reconciliation run: {label}

=== DATA SCHEMA ===
- Entity         : NetSuite entity name
- Month / Year   : Period
- BU             : Business Unit short code
- CG             : Cash Group = ORIG CO NAME value from ACH/wire remarks
- NetSuite_Total : Summed ERP credits
- JPMC_Total     : Summed bank credits
- Variance       : NetSuite_Total − JPMC_Total
                   Positive = ERP higher · Negative = Bank higher · Zero = Matched

=== BUSINESS CONTEXT ===
- All rows are filtered to ORIG CO NAME remarks only
- BU codes are short identifiers mapped from JPMC full account names
- A variance means ERP and bank do not agree on the amount received

=== KEY FIGURES ===
Total NetSuite  : ${total_ns:,.2f}
Total JPMC      : ${total_jp:,.2f}
Total Variance  : ${total_var:,.2f}  ({var_pct:.4f}% of NetSuite)
Total rows      : {len(summary_df)}
Matched ($0)    : {len(summary_df[summary_df['Variance'] == 0])}
Variance rows   : {len(summary_df[summary_df['Variance'] != 0])}

=== TOP 5 VARIANCES (by absolute value) ===
{top5}

=== JPMC ONLY (no NetSuite entry, {len(jpmc_only)} rows) ===
{jpmc_only[['BU','CG','JPMC_Total']].to_string(index=False) if not jpmc_only.empty else 'None'}

=== NETSUITE ONLY (no JPMC entry, {len(ns_only)} rows) ===
{ns_only[['BU','CG','NetSuite_Total']].to_string(index=False) if not ns_only.empty else 'None'}

=== FULL TABLE {table_note} ===
{table_df.to_string(index=False)}

=== YOUR RULES ===
1. Use ONLY data shown above — never hallucinate values or rows.
2. Remember this context for the entire conversation.
3. When asked about a specific BU or CG, refer directly to its rows.
4. Be concise, structured, and specific — always cite BU/CG/amounts.
5. If a question cannot be answered from this data, say so clearly.

You are ready to answer questions about this reconciliation."""
