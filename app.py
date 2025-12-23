import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡")

# --- 1. REMOVE TOP BAR & FOOTER (CSS HACK) ---
hide_decoration_bar_style = '''
    <style>
        header {visibility: hidden;}
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}
    </style>
'''
st.markdown(hide_decoration_bar_style, unsafe_allow_html=True)

# --- 2. CONNECT TO DATABASE ---
@st.cache_resource
def connect():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Secrets missing.")
        st.stop()
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

try:
    client = connect()
    
    # Auto-Discovery of Sheet
    files = client.list_spreadsheet_files()
    if not files:
        st.error("❌ No files found. Share your sheet with the bot email!")
        st.stop()
    
    # Open First File Found
    sh = client.open_by_key(files[0]['id'])
    
    # Find 'Leads' tab or default to first
    found_sheet = None
    for ws in sh.worksheets():
        if "lead" in ws.title.lower():
            found_sheet = ws
            break
    sheet = found_sheet if found_sheet else sh.get_worksheet(0)

    data = sheet.get_all_records()
    df = pd.DataFrame(data)

except Exception as e:
    st.error(f"❌ Connection Error: {e}")
    st.stop()

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.header("TerraTip CRM 🏡")
user = st.sidebar.selectbox("Login As:", ["Manager", "Amit (TC1)", "Rahul (TC2)"])

# --- 4. ADD NEW LEAD FORM ---
with st.expander("➕ Add New Lead", expanded=False):
    with st.form("add_lead_form"):
        c1, c2 = st.columns(2)
        new_name = c1.text_input("Client Name")
        new_phone = c2.text_input("Phone Number")
        new_source = st.selectbox("Source", ["Meta Ads", "Referral", "Walk-in", "Cold Call"])
        
        if st.form_submit_button("Save Lead"):
            if new_name and new_phone:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                # Structure: [ID, Time, Name, Phone, Source, Agent, Assigned, Status...]
                new_row = ["L-New", timestamp, new_name, new_phone, new_source, user, "TC1", "Naya"]
                sheet.append_row(new_row)
                st.success(f"Saved {new_name}!")
                st.rerun()
            else:
                st.warning("Name and Phone are required.")

# --- 5. MAIN LEAD LIST ---
st.divider()

# Filter for Telecallers
if "TC" in user:
    code = "TC1" if "Amit" in user else "TC2"
    col_match = [c for c in df.columns if "Assigned" in c]
    if col_match:
        df = df[df[col_match[0]] == code]

# Hide Ghost Rows (Empty Names)
if not df.empty and 'Client Name' in df.columns:
    df = df[df['Client Name'] != ""]

if df.empty:
    st.info("No active leads found.")

for i, row in df.iterrows():
    name = row.get('Client Name', 'Unknown')
    status = row.get('Status', 'Naya')
    phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
    
    # Icons for visual status
    status_icon = "⚪"
    if status == "Sold": status_icon = "🟢"
    if status == "Lost": status_icon = "🔴"
    if status == "Site Visit Scheduled": status_icon = "🚕"
    
    with st.expander(f"{status_icon} {name}  |  {status}"):
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.write(f"📞 **{phone}**")
            st.write(f"📌 Source: {row.get('Source', '-')}")
            
        with c2:
            st.link_button("💬 WhatsApp", f"https://wa.me/91{phone}?text=Namaste {name}")
        
        with st.form(f"update_{i}"):
            new_stat = st.selectbox("Change Status", 
                ["Naya", "Call Done", "Site Visit Scheduled", "Lost", "Sold"], 
                key=f"s_{i}")
            
            note = st.text_input("Add Note", key=f"n_{i}")
            
            if st.form_submit_button("Update"):
                try:
                    headers = sheet.row_values(1)
                    # Dynamic Column Finding
                    stat_idx = headers.index("Status") + 1
                    # Try to find Notes, otherwise ignore
                    try: note_idx = headers.index("Notes") + 1
                    except: note_idx = 12 
                    
                    real_row = i + 2
                    sheet.update_cell(real_row, stat_idx, new_stat)
                    if note:
                        sheet.update_cell(real_row, note_idx, note)
                        
                    st.success("Updated!")
                    st.rerun()
                except:
                    st.error("Could not find 'Status' column.")
