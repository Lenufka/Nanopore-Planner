import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="Nanopore Run Planner", layout="wide")
st.title("Nanopore Run Planner")

@st.cache_resource
def connect_to_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gspread_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open("Nanopore Planner")
    ws_main = sheet.worksheet("NEW_single_barcode_sample_count")
    ws_planned = sheet.worksheet("PLANNED_RUNS")
    ws_samples = sheet.worksheet("SAMPLES_IN_RUN")
    return ws_main, ws_planned, ws_samples

ws_main, ws_planned, ws_samples = connect_to_gsheet()

df_main = pd.DataFrame(ws_main.get_all_records())
df_planned = pd.DataFrame(ws_planned.get_all_records())
df_samples = pd.DataFrame(ws_samples.get_all_records())

st.subheader("Sample Overview")
projects = df_main["NAME/PROJECT"].dropna().unique().tolist()
selected_project = st.selectbox("Filter by project", ["All"] + projects)
if selected_project != "All":
    df_main = df_main[df_main["NAME/PROJECT"] == selected_project]

st.dataframe(df_main, use_container_width=True)

# Convert numeric columns
numeric_cols = [
    "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)", "TOTAL_len_bp", "N50",
    "AVEG.LEN", "MAX LEN (bp)", "Q20%", "Q30%"
]
for col in numeric_cols:
    if col in df_main.columns:
        df_main[col] = pd.to_numeric(df_main[col], errors="coerce")

st.markdown("---")
st.subheader("Project Statistics")
summary = df_main.groupby("NAME/PROJECT").agg({
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

st.markdown("---")
st.subheader("Plan New Run")

max_samples = 24
selected_samples = st.multiselect("Select up to 24 samples to include in new run", df_main["ID"].dropna().tolist())

if len(selected_samples) > max_samples:
    st.warning(f"Too many samples selected! Max is {max_samples}.")
    selected_samples = selected_samples[:max_samples]

if selected_samples:
    run_df = df_main[df_main["ID"].isin(selected_samples)][[
        "ID", "BARCODE", "TYPE", "NAME/PROJECT",
        "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)", "TOTAL_len_bp", "N50",
        "AVEG.LEN", "MAX LEN (bp)", "Q20%", "Q30%", "BASECALL", "MODEL"
    ]]
    run_name = f"RUN{50 + len(df_planned):03d}"
    run_df.insert(0, "RUN", run_name)

    st.dataframe(run_df, use_container_width=True)

    if st.button("Confirm and Save Planned Run"):
        try:
            ws_planned.append_rows(run_df.values.tolist(), value_input_option="USER_ENTERED")
            st.success(f"Run {run_name} successfully saved.")
        except Exception as e:
            st.error(f"Error saving run: {e}")
else:
    st.info("Please select samples to create a planned run.")

st.markdown("---")
st.subheader("Export Data")

csv_export = st.radio("Choose format to download planned runs:", ["CSV", "Excel"])
if csv_export == "CSV":
    st.download_button(
        label="Download CSV",
        data=df_planned.to_csv(index=False).encode("utf-8"),
        file_name="planned_runs.csv",
        mime="text/csv"
    )
else:
    st.download_button(
        label="Download Excel",
        data=df_planned.to_excel(index=False, engine='openpyxl'),
        file_name="planned_runs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.markdown("---")
st.subheader("Assigned Samples in Runs")
st.dataframe(df_samples, use_container_width=True)
