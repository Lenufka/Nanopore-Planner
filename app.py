import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="Nanopore Planner", layout="wide")
st.title("Nanopore Run Planner")

@st.cache_resource
def connect_to_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gspread_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open("Nanopore Planner")
    try:
        worksheet_planned = sheet.worksheet("PLANNED_RUNS")
    except:
        worksheet_planned = sheet.add_worksheet(title="PLANNED_RUNS", rows="1000", cols="20")
    worksheet_main = sheet.worksheet("NEW_single_barcode_sample_count")
    return sheet, worksheet_main, worksheet_planned

sheet, worksheet_main, worksheet_planned = connect_to_gsheet()
data = worksheet_main.get_all_records()
df = pd.DataFrame(data)

st.subheader("📋 Seznam vzorků")

# Filtrování podle projektu
projekty = df["NAME/PROJECT"].unique().tolist()
vybrany_projekt = st.selectbox("Vyber projekt", ["Vše"] + projekty)

if vybrany_projekt != "Vše":
    df = df[df["NAME/PROJECT"] == vybrany_projekt]

st.dataframe(df, use_container_width=True)

# Statistika vzorků
st.markdown("---")
st.subheader("📊 Statistiky dle projektu")

numeric_cols = [
    "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)",
    "TOTAL_len_bp", "N50", "AVEG.LEN", "Q20%", "Q30%"
]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

project_summary = df.groupby("NAME/PROJECT").agg({
    "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)": "sum",
    "TOTAL_len_bp": "sum",
    "N50": "mean",
    "AVEG.LEN": "mean",
    "Q20%": "mean",
    "Q30%": "mean",
    "ID": "count"
}).rename(columns={
    "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)": "Reads",
    "TOTAL_len_bp": "Total length (bp)",
    "N50": "Mean N50",
    "AVEG.LEN": "Average length",
    "Q20%": "Mean Q20%",
    "Q30%": "Mean Q30%",
    "ID": "Sample count"
}).reset_index()

st.dataframe(project_summary, use_container_width=True)

# Export možnosti
st.markdown("---")
st.subheader("📤 Export dat")

csv = df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Stáhnout aktuální tabulku (CSV)",
    data=csv,
    file_name='nanopore_data.csv',
    mime='text/csv'
)

# Plánování runů
st.markdown("---")
st.subheader("🧪 Plánování nových runů")

max_samples = 24
selected_samples = st.multiselect("Vyber vzorky pro nový run (max 24)", df["ID"].tolist())

if len(selected_samples) > max_samples:
    st.warning(f"Vybráno příliš mnoho vzorků! Maximum je {max_samples}.")
    selected_samples = selected_samples[:max_samples]

if selected_samples:
    run_df = df[df["ID"].isin(selected_samples)][[
        "ID", "BARCODE", "TYPE", "NAME/PROJECT",
        "NREAD-QCHECK(MIN 10Q, 1000bp, NO LAMBDA)",
        "TOTAL_len_bp", "N50", "AVEG.LEN", "MAX LEN (bp)", "Q20%", "Q30%", "BASECALL", "MODEL"
    ]]
    st.dataframe(run_df, use_container_width=True)

    if st.button("✅ Potvrdit a uložit run"):
        try:
            existing_data = worksheet_planned.get_all_records()
            run_number = 50 + len(existing_data) // max_samples
            run_name = f"RUN{run_number:03d}"

            run_df.insert(0, "RUN", run_name)
            worksheet_planned.append_rows(run_df.values.tolist(), value_input_option="USER_ENTERED")

            st.success(f"Run {run_name} byl úspěšně uložen do PLANNED_RUNS.")
        except Exception as e:
            st.error(f"Chyba při ukládání: {e}")
else:
    st.info("Vyber vzorky pro nový run a potvrď.")
