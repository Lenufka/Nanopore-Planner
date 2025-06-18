import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.title("Nanopore Planner")

# Připojení ke Google Sheet
@st.cache_resource
def connect_to_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gspread_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1DSG-Ae8UZjtcETsl7GrvXsNbPy--bGpR57rm3YowblQ").sheet1
    return sheet

sheet = connect_to_gsheet()
data = sheet.get_all_records()

st.subheader("Seznam vzorků")
st.dataframe(data)

st.markdown("---")

# Spočítej vzorky
num_samples = len(data)
st.write(f"Celkový počet vzorků: **{num_samples}**")

# Odhad flowcell (např. 24 vzorků/run)
samples_per_flowcell = 24
needed_flowcells = (num_samples + samples_per_flowcell - 1) // samples_per_flowcell
st.write(f"Odhadovaný počet flowcells: **{needed_flowcells}**")
