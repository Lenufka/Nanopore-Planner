import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import io

st.set_page_config(page_title="Nanopore Planner", layout="wide")
st.title("Nanopore Run Planner")

@st.cache_resource
def connect_to_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gspread_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open("Nanopore Planner")
    ws_samples = sheet.worksheet("NEW_single_barcode_sample_count")
    ws_planned = sheet.worksheet("PLANNED_RUNS")
    ws_in_run = sheet.worksheet("SAMPLES_IN_RUN")
    ws_flowcells = sheet.worksheet("FLOWCELL_CALC")
    return sheet, ws_samples, ws_planned, ws_in_run, ws_flowcells

def safe_get_records(worksheet):
    try:
        data = worksheet.get_all_records(empty2zero=False, head=1)
        return pd.DataFrame(data)
    except Exception as e:
        st.warning(f"Could not load worksheet: {worksheet.title} – {e}")
        return pd.DataFrame()

sheet, ws_samples, ws_planned, ws_in_run, ws_flowcells = connect_to_gsheet()

df_samples = safe_get_records(ws_samples)
df_planned = safe_get_records(ws_planned)
df_in_run = safe_get_records(ws_in_run)
df_flowcells = safe_get_records(ws_flowcells)

st.header("Sample Overview")
projects = df_samples["Name/Project"].dropna().unique().tolist() if not df_samples.empty and "Name/Project" in df_samples.columns else []
selected_project = st.selectbox("Filter by project", ["All"] + projects)
if selected_project != "All" and not df_samples.empty and "Name/Project" in df_samples.columns:
    df_samples = df_samples[df_samples["Name/Project"] == selected_project]

# Interactive filtering for df_samples
if not df_samples.empty:
    with st.expander("🔍 Advanced Filter Options"):
        cols_to_filter = st.multiselect("Select columns to filter", df_samples.columns.tolist())
        for col in cols_to_filter:
            options = df_samples[col].dropna().unique().tolist()
            selected_values = st.multiselect(f"Filter by {col}", options, default=options)
            df_samples = df_samples[df_samples[col].isin(selected_values)]

st.dataframe(df_samples, use_container_width=True)

# Convert numeric columns
numeric_cols = [
    "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)", "TOTAL_len_bp", "N50",
    "AVEG.LEN", "MAX LEN (bp)", "Q20%", "Q30%"]
for col in numeric_cols:
    if col in df_samples.columns:
        df_samples[col] = pd.to_numeric(df_samples[col], errors="coerce")

st.markdown("---")
st.header("Project Statistics")
if not df_samples.empty and "Name/Project" in df_samples.columns:
    summary = df_samples.groupby("Name/Project").agg({
        "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)": "sum",
        "TOTAL_len_bp": "sum",
        "N50": "mean",
        "AVEG.LEN": "mean",
        "Q20%": "mean",
        "Q30%": "mean",
        "ID": "count" if "ID" in df_samples.columns else 'size'
    }).rename(columns={
        "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)": "Total Reads",
        "TOTAL_len_bp": "Total Length (bp)",
        "N50": "Average N50",
        "AVEG.LEN": "Average Length",
        "Q20%": "Average Q20%",
        "Q30%": "Average Q30%",
        "ID": "Sample Count"
    }).reset_index()
    st.dataframe(summary, use_container_width=True)

    if "Date" in df_samples.columns:
        df_samples["Date"] = pd.to_datetime(df_samples["Date"], errors="coerce")
        df_samples = df_samples.dropna(subset=["Date"])
        yearly_stats = df_samples.groupby(df_samples["Date"].dt.to_period("M")).agg({
            "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)": "sum"
        }).rename(columns={"NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)": "Monthly Reads"}).reset_index()
        yearly_stats["Date"] = yearly_stats["Date"].astype(str)

        fig = px.line(yearly_stats, x="Date", y="Monthly Reads", title="Reads per Month")
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.header("Plan a New Run")
max_samples = 24
if not df_in_run.empty and "ID" in df_in_run.columns:
    available_ids = df_in_run["ID"].dropna().astype(str).tolist()
    selected_samples = st.multiselect("Select up to 24 samples", available_ids)
    if len(selected_samples) > max_samples:
        st.warning(f"Too many samples selected! Max is {max_samples}.")
        selected_samples = selected_samples[:max_samples]
    if selected_samples:
        run_df = df_in_run[df_in_run["ID"].astype(str).isin(selected_samples)].copy()
        next_run_num = 50 + len(df_planned["RUN"].dropna().unique()) if "RUN" in df_planned.columns else 50
        run_name = f"RUN{next_run_num:03d}"
        run_df.insert(0, "RUN", run_name)
        st.dataframe(run_df, use_container_width=True)
        if st.button("Confirm and Save Run"):
            try:
                ws_planned.append_rows(run_df.fillna("NA").values.tolist(), value_input_option="USER_ENTERED")
                st.success(f"Run {run_name} successfully saved.")
            except Exception as e:
                st.error(f"Error saving run: {e}")
    else:
        st.info("Please select samples to plan a run.")

st.markdown("---")
st.header("Planned Runs Overview")
if not df_planned.empty:
    st.dataframe(df_planned.fillna("NA"), use_container_width=True)
else:
    st.info("No planned run data available.")

st.markdown("---")
st.header("Export Data")
if not df_planned.empty:
    try:
        buffer_xlsx = io.BytesIO()
        with pd.ExcelWriter(buffer_xlsx, engine='openpyxl') as writer:
            df_planned.to_excel(writer, index=False)
        buffer_xlsx.seek(0)
        st.download_button(
            label="Download Planned Runs (.xlsx)",
            data=buffer_xlsx,
            file_name="planned_runs.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"Error generating Excel file: {e}")
else:
    st.info("No planned run data available to export.")

st.download_button(
    label="Download Samples in Run (.csv)",
    data=df_in_run.to_csv(index=False).encode("utf-8"),
    file_name="samples_in_run.csv",
    mime="text/csv"
)

if not df_flowcells.empty:
    st.markdown("---")
    st.header("Flowcell Calculation Overview")
    st.dataframe(df_flowcells.fillna("NA"), use_container_width=True)
