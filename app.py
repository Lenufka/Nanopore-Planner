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
    worksheet_planned = sheet.worksheet("PLANNED_RUNS")
    return sheet, worksheet_main, worksheet_planned

sheet, worksheet_main, worksheet_planned = connect_to_gsheet()
data = worksheet_main.get_all_records()
df = pd.DataFrame(data)

planned_data = worksheet_planned.get_all_records()
df_planned = pd.DataFrame(planned_data)

st.subheader("Seznam vzorků")

# Filtrování podle projektu
projekty = df["NAME/PROJECT"].unique().tolist()
vybrany_projekt = st.selectbox("Vyber projekt", ["Vše"] + projekty)

if vybrany_projekt != "Vše":
    df = df[df["NAME/PROJECT"] == vybrany_projekt]

st.dataframe(df, use_container_width=True)

# Statistika vzorků
st.markdown("---")
st.subheader("Statistiky dle projektu")

# Převod sloupců na číselné hodnoty
numeric_cols = ["(MIN 10Q, 1000bp)", "TOTAL_len_bp", "AVEG.LEN", "Q20%", "Q30%", "N50"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Souhrnná tabulka podle projektu
project_summary = df.groupby("NAME/PROJECT").agg({
    "(MIN 10Q, 1000bp)": "sum",
    "TOTAL_len_bp": "sum",
    "AVEG.LEN": "mean",
    "N50": "mean",
    "Q20%": "mean",
    "Q30%": "mean",
    "ID": "count"
}).rename(columns={
    "(MIN 10Q, 1000bp)": "Reads",
    "TOTAL_len_bp": "Total length (bp)",
    "AVEG.LEN": "Average length",
    "N50": "Mean N50",
    "Q20%": "Mean Q20%",
    "Q30%": "Mean Q30%",
    "ID": "Sample count"
}).reset_index()

st.write("### Souhrnné statistiky podle projektu")
st.dataframe(project_summary, use_container_width=True)

# Místo pro plánování nového runu
st.markdown("---")
st.subheader("Plánování nových runů")

max_samples = 24
selected_samples = st.multiselect("Vyber vzorky pro nový run (max 24)", df["ID"].tolist())

if len(selected_samples) > max_samples:
    st.warning(f"Vybráno příliš mnoho vzorků! Maximum je {max_samples}.")
    selected_samples = selected_samples[:max_samples]

if selected_samples:
    run_df = df[df["ID"].isin(selected_samples)][df.columns.tolist()]
    st.write("### Náhled vybraných vzorků pro nový run")
    st.dataframe(run_df, use_container_width=True)

    if st.button("Potvrdit a uložit run"):
        try:
            existing_data = worksheet_planned.get_all_records()
            run_number = 50 + len(existing_data) // max_samples
            run_name = f"RUN{run_number:03d}"

            new_data = run_df.copy()
            new_data.insert(0, "Run Name", run_name)

            worksheet_planned.append_rows(new_data.values.tolist(), value_input_option="USER_ENTERED")
            st.success(f"Run {run_name} byl úspěšně uložen.")
        except Exception as e:
            st.error(f"Chyba při ukládání: {e}")
else:
    st.info("Vyber vzorky pro nový run.")

# Zobrazení naplánovaných runů
st.markdown("---")
st.subheader("📅 Naplánované runy")

if not df_planned.empty:
    runy = df_planned["Run Name"].unique().tolist()
    vybrany_run = st.selectbox("Vyber run", ["Vše"] + runy)

    filtered_df = df_planned.copy()
    if vybrany_run != "Vše":
        filtered_df = df_planned[df_planned["Run Name"] == vybrany_run]

    st.dataframe(filtered_df, use_container_width=True)

    # Stahování jako CSV
    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Stáhnout jako CSV",
        data=csv,
        file_name="planned_runs.csv",
        mime="text/csv"
    )

    # Stahování jako XLSX
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        filtered_df.to_excel(writer, index=False, sheet_name='Planned Runs')
        writer.save()
    st.download_button(
        label="📥 Stáhnout jako Excel",
        data=output.getvalue(),
        file_name="planned_runs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Zatím nejsou uloženy žádné naplánované runy.")
