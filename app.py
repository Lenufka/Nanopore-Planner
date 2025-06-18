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
    worksheet = sheet.worksheet("NEW_single_barcode_sample_count")
    return sheet, worksheet

sheet, worksheet = connect_to_gsheet()
data = worksheet.get_all_records()
df = pd.DataFrame(data)

st.subheader("Seznam vzorků")

# Filtrování podle projektu
projekty = df["NAME/PROJECT"].unique().tolist()
vybrany_projekt = st.selectbox("Vyber projekt", ["Vše"] + projekty)

if vybrany_projekt != "Vše":
    df = df[df["NAME/PROJECT"] == vybrany_projekt]

st.dataframe(df, use_container_width=True)

# Statistika vzorků
st.markdown("---")
st.subheader("Statistiky")
st.write(f"Celkový počet vzorků: **{len(df)}**")

samples_per_flowcell = 24
needed_flowcells = (len(df) + samples_per_flowcell - 1) // samples_per_flowcell
st.write(f"Odhadovaný počet flowcells: **{needed_flowcells}**")

# Graf: počet vzorků podle projektu
if "NAME/PROJECT" in df.columns:
    fig = px.histogram(df, x="NAME/PROJECT", title="Počet vzorků podle projektu")
    st.plotly_chart(fig, use_container_width=True)

# Graf: počet vzorků podle typu
if "TYPE" in df.columns:
    fig2 = px.histogram(df, x="TYPE", title="Počet vzorků podle typu vzorku")
    st.plotly_chart(fig2, use_container_width=True)

# Místo pro plánování nového runu
st.markdown("---")
st.subheader("Plánování nových runů")

max_samples = 24
selected_samples = st.multiselect("Vyber vzorky pro nový run (max 24)", df["ID"].tolist())

if len(selected_samples) > max_samples:
    st.warning(f"Vybráno příliš mnoho vzorků! Maximum je {max_samples}.")
    selected_samples = selected_samples[:max_samples]

if selected_samples:
    run_df = df[df["ID"].isin(selected_samples)][["ID", "NAME/PROJECT"]]
    run_df = run_df.rename(columns={"NAME/PROJECT": "Responsible/Project"})
    st.write("### Vybrané vzorky:")
    st.dataframe(run_df, use_container_width=True)

    if st.button("Potvrdit a uložit run"):
        try:
            try:
                planned_ws = sheet.worksheet("PLANNED_RUNS")
            except:
                planned_ws = sheet.add_worksheet(title="PLANNED_RUNS", rows="1000", cols="10")

            existing_data = planned_ws.get_all_records()
            run_number = 50 + len(existing_data) // max_samples
            run_name = f"RUN{run_number:03d}"

            new_data = run_df.copy()
            new_data.insert(0, "Run Name", run_name)

            planned_ws.append_rows(new_data.values.tolist(), value_input_option="USER_ENTERED")
            st.success(f"Run {run_name} byl úspěšně uložen.")
        except Exception as e:
            st.error(f"Chyba při ukládání: {e}")
else:
    st.info("Vyber vzorky pro nový run.")
