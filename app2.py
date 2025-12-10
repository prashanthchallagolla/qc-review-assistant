import streamlit as st
import pandas as pd

st.set_page_config(page_title="AI QC Review Assistant", layout="wide")

st.title("AI-Powered QC Review Assistant")
st.caption("Upload QC file → Filter by auditor → Review DP / RE / Geofence buckets in one place")

# ======================================================
# 1. COLUMN NAME CONFIG  (EDIT THESE IF NEEDED)
# ======================================================

# Identification
AUDITOR_COL             = "auditor"
ADDRESS_ID_COL          = "addressid"
WEEK_COL                = "week"
PROGRAM_COL             = "program"
TRACKING_ID_COL         = "trackingid"

# DP / PRE buckets
PDP_PRE_DP_COL          = "pdp_pre_dp_geocodes"      # where geocodes were present before auditing (DP)
PRE_RE_GEOCODES_COL     = "pre_re_geocodes"         # same as PDP but for RE

AUDITOR_GRAN_DP_COL     = "auditor_granularity_dp"  # auditor DP granularity
AUDITOR_GRAN_RE_COL     = "auditor_granularity_re"  # auditor RE granularity

DP_GEOCODES_COL         = "dp_geocodes"             # final DP geocodes marked by auditor
RE_GEOCODES_COL         = "re_geocodes"             # final RE geocodes marked by auditor

ACTION_TAKEN_COL        = "action_taken"            # NFR / Fixed / NEI

AUDITOR_PRE_TOL_COL     = "auditor_pre_tolerance"   # geofence before audit
AUDITOR_POST_TOL_COL    = "post_tolerance"          # geofence after audit

# Disagreements raised by QC
DP_DISAGREE_COL         = "dp_disagreement"         # DP incorrect
RE_DISAGREE_COL         = "re_disagreement"         # RE incorrect
GF_DISAGREE_COL         = "geofence_disagreement"   # geofence issue

# QC buckets (similar structure to auditor buckets)
QC_DP_GRAN_COL          = "qc_dp_granularity"
QC_RE_GRAN_COL          = "qc_re_granularity"
QC2_DP_COL              = "qc2_dp"
QC2_RE_COL              = "qc2_re"
QC2_TOL_COL             = "qc2_tolerance"

# Comments / reasons
AUDITOR_COMMENT_COL     = "auditor_comment"         # why auditor mapped as they did
QC2_COMMENT_COL         = "qc2_comment"             # QC comment explaining auditor mistake
QC2_SOURCE_COL          = "qc2_source"              # source used by QC (Bing, etc.)
QC2_GAM_ISSUE_COL       = "qc2_gam_issue"

REASON_DP_COL           = "reason_dp_issue"         # why DP incorrect
REASON_RE_COL           = "reason_re_issue"         # why RE incorrect
REASON_GF_COL           = "reason_geofence_issue"   # why geofence incorrect

# Internal status column (we create / maintain this)
STATUS_COL              = "review_status"           # Pending / Completed


# Small helper to safely read a value from a row
def get_val(row, col_name, default="N/A"):
    if col_name in row.index and pd.notna(row[col_name]):
        return row[col_name]
    return default


# ======================================================
# 2. SIDEBAR – UPLOAD + FILTERS
# ======================================================

with st.sidebar:
    st.header("Controls")

    uploaded_file = st.file_uploader(
        "Upload QC file",
        type=["xlsx", "xls", "csv"]
    )

    auditor_name = None
    status_filter = None

    if uploaded_file is not None:
        # Decide reader based on extension
        filename = uploaded_file.name.lower()
        if filename.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        # Show columns so you can confirm mapping
        with st.expander("Show detected columns"):
            st.write(list(df.columns))

        # Validate essential columns
        needed = [AUDITOR_COL, ADDRESS_ID_COL]
        missing = [c for c in needed if c not in df.columns]
        if missing:
            st.error(f"These essential columns are missing in the file: {missing}")
        else:
            # Create status column if not present
            if STATUS_COL not in df.columns:
                df[STATUS_COL] = "Pending"

            auditors = sorted(df[AUDITOR_COL].dropna().astype(str).unique())
            auditor_name = st.selectbox("Select auditor", auditors)

            status_options = ["All", "Pending", "Completed"]
            status_filter = st.selectbox("Review status", status_options, index=0)
    else:
        df = None


# ======================================================
# 3. MAIN CONTENT
# ======================================================

if df is None:
    st.info("👈 Upload a QC Excel/CSV file in the sidebar to get started.")
else:
    # Filter for auditor + status
    filtered_df = df[df[AUDITOR_COL] == auditor_name].copy()

    if status_filter and status_filter != "All":
        filtered_df = filtered_df[filtered_df[STATUS_COL] == status_filter]

    if filtered_df.empty:
        st.warning("No cases found for this auditor / filter.")
        st.stop()

    # Summary numbers
    total_cases = len(filtered_df)
    pending_cases = (filtered_df[STATUS_COL] == "Pending").sum()
    completed_cases = (filtered_df[STATUS_COL] == "Completed").sum()

    tab_summary, tab_cases, tab_detail = st.tabs(["Summary", "Cases table", "Case detail"])

    # ---------------------------
    # TAB 1: SUMMARY
    # ---------------------------
    with tab_summary:
        st.subheader(f"Summary for auditor: {auditor_name}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total cases", total_cases)
        c2.metric("Pending", pending_cases)
        c3.metric("Completed", completed_cases)

        st.markdown("---")
        st.write("Preview of data:")
        st.dataframe(filtered_df.head(), use_container_width=True)

    # ---------------------------
    # TAB 2: CASES TABLE
    # ---------------------------
    with tab_cases:
        st.subheader("Cases list")

        show_cols = []
        for col in [
            ADDRESS_ID_COL,
            WEEK_COL,
            PROGRAM_COL,
            TRACKING_ID_COL,
            STATUS_COL,
            QC2_RE_COL,
            DP_DISAGREE_COL,
            RE_DISAGREE_COL,
            GF_DISAGREE_COL,
        ]:
            if col in filtered_df.columns:
                show_cols.append(col)

        if not show_cols:
            show_cols = filtered_df.columns.tolist()

        st.dataframe(filtered_df[show_cols], use_container_width=True)

    # ---------------------------
    # TAB 3: CASE DETAIL
    # ---------------------------
    with tab_detail:
        st.subheader("Case detail – DP / RE / Geofence breakdown")

        case_ids = filtered_df[ADDRESS_ID_COL].astype(str).tolist()
        selected_case_id = st.selectbox("Select case (addressid)", case_ids)

        case_row = filtered_df[filtered_df[ADDRESS_ID_COL].astype(str) == selected_case_id].iloc[0]

        # ----- BASIC INFO -----
        st.markdown("### Basic information")
        i1, i2, i3 = st.columns(3)
        i1.write(f"**addressid:** {get_val(case_row, ADDRESS_ID_COL)}")
        i1.write(f"**auditor:** {get_val(case_row, AUDITOR_COL)}")
        i2.write(f"**week:** {get_val(case_row, WEEK_COL)}")
        i2.write(f"**program:** {get_val(case_row, PROGRAM_COL)}")
        i3.write(f"**trackingid:** {get_val(case_row, TRACKING_ID_COL)}")
        i3.write(f"**status:** {get_val(case_row, STATUS_COL, 'Pending')}")

        st.markdown("---")

        # ======================================================
        # 3A. DELIVERY POINT (DP)
        # ======================================================
        with st.expander("🟦 Delivery Point (DP)", expanded=True):
            c1, c2 = st.columns(2)
            c1.write("**PDP / Pre-DP geocodes (before auditing):**")
            c1.code(str(get_val(case_row, PDP_PRE_DP_COL)))
            c1.write("**DP geocodes (after auditing):**")
            c1.code(str(get_val(case_row, DP_GEOCODES_COL)))

            c2.write("**Auditor DP granularity:**")
            c2.write(str(get_val(case_row, AUDITOR_GRAN_DP_COL)))
            c2.write("**QC DP granularity:**")
            c2.write(str(get_val(case_row, QC_DP_GRAN_COL)))
            c2.write("**QC2 DP bucket (qc2_dp):**")
            c2.write(str(get_val(case_row, QC2_DP_COL)))

            st.markdown("---")
            c3, c4 = st.columns(2)
            c3.write("**DP disagreement flag:**")
            c3.write(str(get_val(case_row, DP_DISAGREE_COL)))
            c3.write("**Reason DP issue:**")
            c3.write(str(get_val(case_row, REASON_DP_COL)))
            c4.write("**Action taken:**")
            c4.write(str(get_val(case_row, ACTION_TAKEN_COL)))

        # ======================================================
        # 3B. ROAD ENTRY (RE)
        # ======================================================
        with st.expander("🟩 Road Entry (RE)", expanded=True):
            c1, c2 = st.columns(2)
            c1.write("**PRE (RE) geocodes (before auditing):**")
            c1.code(str(get_val(case_row, PRE_RE_GEOCODES_COL)))
            c1.write("**RE geocodes (after auditing):**")
            c1.code(str(get_val(case_row, RE_GEOCODES_COL)))

            c2.write("**Auditor RE granularity:**")
            c2.write(str(get_val(case_row, AUDITOR_GRAN_RE_COL)))
            c2.write("**QC RE granularity:**")
            c2.write(str(get_val(case_row, QC_RE_GRAN_COL)))
            c2.write("**QC2 RE bucket (qc2_re):**")
            c2.write(str(get_val(case_row, QC2_RE_COL)))

            st.markdown("---")
            c3, c4 = st.columns(2)
            c3.write("**RE disagreement flag:**")
            c3.write(str(get_val(case_row, RE_DISAGREE_COL)))
            c3.write("**Reason RE issue:**")
            c3.write(str(get_val(case_row, REASON_RE_COL)))
            c4.write("**Action taken:**")
            c4.write(str(get_val(case_row, ACTION_TAKEN_COL)))

        # ======================================================
        # 3C. GEOFENCE
        # ======================================================
        with st.expander("🟨 Geofence", expanded=True):
            c1, c2 = st.columns(2)
            c1.write("**Auditor pre-tolerance (before auditing):**")
            c1.write(str(get_val(case_row, AUDITOR_PRE_TOL_COL)))
            c1.write("**Auditor post-tolerance (after auditing):**")
            c1.write(str(get_val(case_row, AUDITOR_POST_TOL_COL)))

            c2.write("**QC2 tolerance (qc2_tolerance):**")
            c2.write(str(get_val(case_row, QC2_TOL_COL)))
            c2.write("**Geofence disagreement flag:**")
            c2.write(str(get_val(case_row, GF_DISAGREE_COL)))
            c2.write("**Reason geofence issue:**")
            c2.write(str(get_val(case_row, REASON_GF_COL)))

        # ======================================================
        # 3D. OVERALL / COMMENTS
        # ======================================================
        with st.expander("🟥 Overall comments & QC notes", expanded=True):
            st.write("**Auditor comment:**")
            st.write(str(get_val(case_row, AUDITOR_COMMENT_COL)))

            st.write("**QC2 comment (why auditor is incorrect):**")
            st.write(str(get_val(case_row, QC2_COMMENT_COL)))

            c1, c2 = st.columns(2)
            c1.write("**QC2 source:**")
            c1.write(str(get_val(case_row, QC2_SOURCE_COL)))
            c2.write("**QC2 GAM issue:**")
            c2.write(str(get_val(case_row, QC2_GAM_ISSUE_COL)))

        st.markdown("---")

        # ======================================================
        # 3E. AUDITOR DECISION (placeholder – GenAI will plug here)
        # ======================================================
        st.markdown("### Auditor review & decision")

        decision = st.radio(
            "Choose action for this case:",
            ["Agree with QC", "Appeal"],
            horizontal=True
        )

        notes = st.text_area(
            "Your notes / appeal text (for now entered manually; later we will auto-generate with GenAI)",
            height=150
        )

        if st.button("Save decision for this case"):
            # In a real system, you’d update df and write back to DB/Excel.
            st.success(f"Decision for case {selected_case_id}: {decision}")
            if decision == "Appeal":
                st.info("Saved appeal text:")
                st.write(notes)
