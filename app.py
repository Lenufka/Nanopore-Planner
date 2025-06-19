import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Nanopore Planner", layout="wide")
st.title("Nanopore Run Planner")

@st.cache_resource
def connect_to_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gspread_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open("Nanopore Planner")
    worksheet_main = sheet.worksheet("NEW_single_barcode_sample_count")
    try:
        worksheet_planned = sheet.worksheet("PLANNED_RUNS")
    except:
        worksheet_planned = sheet.add_worksheet(title="PLANNED_RUNS", rows="1000", cols="15")
    return sheet, worksheet_main, worksheet_planned

sheet, worksheet_main, worksheet_planned = connect_to_gsheet()
data = worksheet_main.get_all_records()
df = pd.DataFrame(data)

st.subheader("Sample List")

projects = df["NAME/PROJECT"].dropna().unique().tolist()
selected_project = st.selectbox("Filter by project", ["All"] + projects)

if selected_project != "All":
    df = df[df["NAME/PROJECT"] == selected_project]

st.dataframe(df, use_container_width=True)

numeric_cols = [
    "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)", "TOTAL_len_bp", "N50",
    "AVEG.LEN", "MAX LEN (bp)", "Q20%", "Q30%"
]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

st.markdown("---")
st.subheader("Project Statistics")

summary = df.groupby("NAME/PROJECT").agg({
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
st.subheader("Plan a New Run")

max_samples = 24
selected_samples = st.multiselect("Select up to 24 samples to plan a new run", df["ID"].dropna().tolist())

if len(selected_samples) > max_samples:
    st.warning(f"Too many samples selected! Max is {max_samples}.")
    selected_samples = selected_samples[:max_samples]

if selected_samples:
    run_df = df[df["ID"].isin(selected_samples)][[
        "ID", "BARCODE", "TYPE", "NAME/PROJECT",
        "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)", "TOTAL_len_bp", "N50",
        "AVEG.LEN", "MAX LEN (bp)", "Q20%", "Q30%", "BASECALL", "MODEL"
    ]]
    run_name = f"RUN{50 + worksheet_planned.row_count // max_samples:03d}"
    run_df.insert(0, "RUN", run_name)

    st.dataframe(run_df, use_container_width=True)

    if st.button("Confirm and Save Run"):
        try:
            worksheet_planned.append_rows(run_df.values.tolist(), value_input_option="USER_ENTERED")
            st.success(f"Run {run_name} successfully saved.")
        except Exception as e:
            st.error(f"Error saving run: {e}")
else:
    st.info("Please select samples to plan a run.")

st.markdown("---")
st.subheader("Export Planned Runs")

planned_data = worksheet_planned.get_all_records()
df_planned = pd.DataFrame(planned_data)

csv_data = df_planned.to_csv(index=False).encode("utf-8")
excel_buffer = BytesIO()
df_planned.to_excel(excel_buffer, index=False, engine='openpyxl')
excel_buffer.seek(0)

st.download_button(
    label="Download as CSV",
    data=csv_data,
    file_name="planned_runs.csv",
    mime="text/csv"
)

st.download_button(
    label="Download as Excel",
    data=excel_buffer,
    file_name="planned_runs.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.markdown("---")
st.subheader("Modify or Delete Runs")

if not df_planned.empty:
    selected_run = st.selectbox("Select run to modify or delete", df_planned["RUN"].unique().tolist())
    editable_df = df_planned[df_planned["RUN"] == selected_run].copy()
    edited_df = st.data_editor(editable_df, use_container_width=True, num_rows="dynamic")

    if st.button("Update Selected Run"):
        try:
            all_data = worksheet_planned.get_all_values()
            headers = all_data[0]
            body = all_data[1:]
            body_df = pd.DataFrame(body, columns=headers)
            body_df = body_df[~(body_df["RUN"] == selected_run)]
            worksheet_planned.clear()
            worksheet_planned.append_row(headers)
            worksheet_planned.append_rows(body_df.values.tolist() + edited_df.values.tolist())
            st.success("Run successfully updated.")
        except Exception as e:
            st.error(f"Error updating run: {e}")

    if st.button("Delete Selected Run"):
        try:
            all_data = worksheet_planned.get_all_values()
            headers = all_data[0]
            body = all_data[1:]
            body_df = pd.DataFrame(body, columns=headers)
            body_df = body_df[~(body_df["RUN"] == selected_run)]
            worksheet_planned.clear()
            worksheet_planned.append_row(headers)
            worksheet_planned.append_rows(body_df.values.tolist())
            st.success("Run successfully deleted.")
        except Exception as e:
            st.error(f"Error deleting run: {e}")

st.info("ℹ️ Any changes made in the Google Sheet directly will appear here after refreshing the app.")
