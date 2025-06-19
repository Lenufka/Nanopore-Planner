import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import io
from io import BytesIO

st.set_page_config(page_title="Nanopore Run Planner", layout="wide")
st.title("🧬 Nanopore Run Planner")

# Connect to Google Sheets
@st.cache_resource

def connect_to_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gspread_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open("Nanopore Planner")
    ws_samples = sheet.worksheet("NEW_single_barcode_sample_count")
    ws_planned = sheet.worksheet("PLANNED_RUNS")
    ws_in_run = sheet.worksheet("SAMPLES_IN_RUN")
    ws_flowcells = sheet.worksheet("FLOWCELL_CALC")
    return ws_samples, ws_planned, ws_in_run, ws_flowcells

try:
    ws_samples, ws_planned, ws_in_run, ws_flowcells = connect_to_gsheet()
    df_samples = pd.DataFrame(ws_samples.get_all_records())
    df_planned = pd.DataFrame(ws_planned.get_all_records())
    df_in_run = pd.DataFrame(ws_in_run.get_all_records())
    df_flowcells = pd.DataFrame(ws_flowcells.get_all_records())
except Exception as e:
    st.error(f"Error loading Google Sheets: {e}")
    st.stop()

st.header("📋 Sample Overview")
if "NAME/PROJECT" in df_samples.columns:
    projects = df_samples["NAME/PROJECT"].dropna().unique().tolist()
    selected_project = st.selectbox("Filter by project", ["All"] + projects)
    if selected_project != "All":
        df_samples = df_samples[df_samples["NAME/PROJECT"] == selected_project]
    st.dataframe(df_samples, use_container_width=True)
else:
    st.warning("Missing 'NAME/PROJECT' column in sample data.")

st.markdown("---")

st.header("📈 Project Statistics")
numeric_cols = [
    "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)", "TOTAL_len_bp", "N50",
    "AVEG.LEN", "MAX LEN (bp)", "Q20%", "Q30%"]
for col in numeric_cols:
    if col in df_samples.columns:
        df_samples[col] = pd.to_numeric(df_samples[col], errors="coerce")

if "NAME/PROJECT" in df_samples.columns:
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
else:
    st.warning("Project statistics cannot be calculated due to missing column.")

st.markdown("---")

st.header("🧪 Plan a New Run")
max_samples = 24
if "ID" in df_samples.columns:
    selected_samples = st.multiselect("Select up to 24 samples", df_samples["ID"].dropna().tolist())
    if len(selected_samples) > max_samples:
        st.warning(f"Too many samples selected! Max is {max_samples}.")
        selected_samples = selected_samples[:max_samples]

    if selected_samples:
        run_df = df_samples[df_samples["ID"].isin(selected_samples)][[
            "ID", "BARCODE", "TYPE", "NAME/PROJECT",
            "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)", "TOTAL_len_bp", "N50",
            "AVEG.LEN", "MAX LEN (bp)", "Q20%", "Q30%", "BASECALL", "MODEL"]]
        next_run_num = 50 + len(df_planned["RUN"].unique()) if "RUN" in df_planned.columns else 50
        run_name = f"RUN{next_run_num:03d}"
        run_df.insert(0, "RUN", run_name)
        st.dataframe(run_df, use_container_width=True)
        if st.button("Confirm and Save Run"):
            try:
                ws_planned.append_rows(run_df.values.tolist(), value_input_option="USER_ENTERED")
                st.success(f"Run {run_name} successfully saved.")
            except Exception as e:
                st.error(f"Error saving run: {e}")
    else:
        st.info("Please select samples to plan a run.")
else:
    st.warning("No column 'ID' found in samples.")

st.markdown("---")

st.header("📥 Export Data")

def to_excel_download(df, filename):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    st.download_button(
        label=f"Download {filename}",
        data=output.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if not df_planned.empty:
    to_excel_download(df_planned, "planned_runs.xlsx")
if not df_in_run.empty:
    st.download_button(
        label="Download Samples in Run (.csv)",
        data=df_in_run.to_csv(index=False).encode("utf-8"),
        file_name="samples_in_run.csv",
        mime="text/csv"
    )

st.markdown("---")

st.header("📦 Flowcell Calculation")
if df_flowcells.empty:
    st.info("Flowcell calculation table is currently empty.")
else:
    st.dataframe(df_flowcells, use_container_width=True)
