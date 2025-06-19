import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import io

st.set_page_config(page_title="Nanopore Planner", layout="wide")
st.title("🧬 Nanopore Run Planner")

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

sheet, ws_samples, ws_planned, ws_in_run, ws_flowcells = connect_to_gsheet()

# Load data from Google Sheets
df_samples = pd.DataFrame(ws_samples.get_all_records())
df_planned = pd.DataFrame(ws_planned.get_all_records())
df_in_run = pd.DataFrame(ws_in_run.get_all_records())
df_flowcells = pd.DataFrame(ws_flowcells.get_all_records())

# Sample Overview
st.header("📋 Sample Overview")
projects = df_samples["NAME/PROJECT"].dropna().unique().tolist()
selected_project = st.selectbox("Filter by Project", ["All"] + projects)
if selected_project != "All":
    df_samples = df_samples[df_samples["NAME/PROJECT"] == selected_project]
st.dataframe(df_samples, use_container_width=True)

# Convert columns to numeric for statistics
numeric_cols = [
    "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)", "TOTAL_len_bp", "N50",
    "AVEG.LEN", "MAX LEN (bp)", "Q20%", "Q30%"]
for col in numeric_cols:
    if col in df_samples.columns:
        df_samples[col] = pd.to_numeric(df_samples[col], errors="coerce")

# Project Statistics
st.markdown("---")
st.header("📊 Project Statistics")
summary = df_samples.groupby("NAME/PROJECT").agg({
    "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)": "sum",
    "TOTAL_len_bp": "sum",
    "N50": "mean",
    "AVEG.LEN": "mean",
    "Q20%": "mean",
    "Q30%": "mean",
    "ID": "count"
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

# Plan a New Run
st.markdown("---")
st.header("🧪 Plan a New Run")
max_samples = 24
selected_samples = st.multiselect("Select up to 24 samples", df_samples["ID"].dropna().tolist())
if len(selected_samples) > max_samples:
    st.warning(f"Too many samples selected! Maximum is {max_samples}.")
    selected_samples = selected_samples[:max_samples]
if selected_samples:
    run_df = df_samples[df_samples["ID"].isin(selected_samples)][[
        "ID", "BARCODE", "TYPE", "NAME/PROJECT",
        "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)", "TOTAL_len_bp", "N50",
        "AVEG.LEN", "MAX LEN (bp)", "Q20%", "Q30%", "BASECALL", "MODEL"]]
    next_run_num = 50 + len(df_planned["RUN"].unique())
    run_name = f"RUN{next_run_num:03d}"
    run_df.insert(0, "RUN", run_name)
    st.dataframe(run_df, use_container_width=True)
    if st.button("✅ Confirm and Save Run"):
        try:
            ws_planned.append_rows(run_df.values.tolist(), value_input_option="USER_ENTERED")
            st.success(f"Run {run_name} successfully saved.")
        except Exception as e:
            st.error(f"Error saving run: {e}")
else:
    st.info("Please select samples to plan a run.")

# Export Data
st.markdown("---")
st.header("⬇️ Export Data")

# Export planned runs to .xlsx
buffer_xlsx = io.BytesIO()
with pd.ExcelWriter(buffer_xlsx, engine='openpyxl') as writer:
    df_planned.to_excel(writer, index=False, sheet_name="Planned Runs")
buffer_xlsx.seek(0)

st.download_button(
    label="Download Planned Runs (.xlsx)",
    data=buffer_xlsx,
    file_name="planned_runs.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Export samples in run
st.download_button(
    label="Download Samples in Run (.csv)",
    data=df_in_run.to_csv(index=False).encode("utf-8"),
    file_name="samples_in_run.csv",
    mime="text/csv"
)

# Flowcell Calculation
st.markdown("---")
st.header("📦 Flowcell Calculation")
if df_flowcells.empty:
    st.info("Flowcell calculation table is currently empty.")
else:
    st.dataframe(df_flowcells, use_container_width=True)
