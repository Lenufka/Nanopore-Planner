import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
from oauth2client.service_account import ServiceAccountCredentials

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
    return worksheet

worksheet = connect_to_gsheet()
data = worksheet.get_all_records()
df = pd.DataFrame(data)

st.subheader("Seznam vzorků")

# Filtrování podle projektu
projekty = df["Project"].unique().tolist()
vybrany_projekt = st.selectbox("Vyber projekt", ["Vše"] + projekty)

if vybrany_projekt != "Vše":
    df = df[df["Project"] == vybrany_projekt]

st.dataframe(df, use_container_width=True)

# Statistika vzorků
st.markdown("---")
st.subheader("Statistiky")
st.write(f"Celkový počet vzorků: **{len(df)}**")

samples_per_flowcell = 24
needed_flowcells = (len(df) + samples_per_flowcell - 1) // samples_per_flowcell
st.write(f"Odhadovaný počet flowcells: **{needed_flowcells}**")

# Graf: počet vzorků podle projektu
if "Project" in df.columns:
    fig = px.histogram(df, x="Project", title="Počet vzorků podle projektu")
    st.plotly_chart(fig, use_container_width=True)

# Graf: počet vzorků podle typu
if "Sample type" in df.columns:
    fig2 = px.histogram(df, x="Sample type", title="Počet vzorků podle typu vzorku")
    st.plotly_chart(fig2, use_container_width=True)

# Místo pro plánování nového runu
st.markdown("---")
st.subheader("Plánování nových runů")

st.markdown("Zde bude možnost vybírat vzorky a sestavit run podle zvolených kritérií.")