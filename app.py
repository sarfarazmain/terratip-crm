import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="TerraTip CRM", layout="wide")

# --- STEP 1: CONNECT TO BOT ---
@st.cache_resource
def connect():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Critical: Secrets missing.")
        st.stop()
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

try:
    client = connect()
    st.success("✅ Bot Logged In")

    # --- STEP 2: AUTO-DISCOVER FILE (No ID needed) ---
    # We ask the bot to list all files it can see
    files = client.list_spreadsheet_files()
    
    if not files:
        st.error("❌ The Bot sees 0 files.")
        st.warning("👉 You MUST click 'Share' on your Google Sheet and add this email as Editor:")
        st.code(st.secrets["gcp_service_account"]["client_email"])
        st.stop()
    
    # We automatically pick the first file found
    target_file = files[0]
    sheet_id = target_file['id']
    sheet_name = target_file['name']
    
    st.success(f"✅ Auto-Connected to: '{sheet_name}'")
    
    # Open that file
    sh = client.open_by_key(sheet_id)

    # --- STEP 3: FIND THE RIGHT TAB ---
    # We look for a tab with "lead" in the name, otherwise take the first one
    found_sheet = None
    for ws in sh.worksheets():
        if "lead" in ws.title.lower():
            found_sheet = ws
            break
    
    if found_sheet:
        sheet = found_sheet
        st.info(f"📂 Using Tab: '{sheet.title}'")
    else:
        sheet = sh.get_worksheet(0)
        st.info(f"📂 Using First Tab: '{sheet.title}'")

    # --- STEP 4: LOAD DATA ---
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

except Exception as e:
    st.error(f"❌ Error: {e}")
    st.stop()

# --- APP INTERFACE ---
st.title("TerraTip CRM")
user = st.sidebar.selectbox("User", ["Manager", "Amit (TC1)", "Rahul (TC2)"])

if "TC" in user:
    code = "TC1" if "Amit" in user else "TC2"
    # Filter using whatever column name exists
    col_match = [c for c in df.columns if "Assigned" in c]
    if col_match:
        df = df[df[col_match[0]] == code]

if df.empty:
    st.warning("No leads found in this sheet.")

for i, row in df.iterrows():
    # Flexible Column Names
    name = row.get('Client Name', row.get('Name', 'Unknown'))
    status = row.get('Status', 'Naya')
    phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')

    with st.expander(f"{name} ({status})"):
        st.write(f"📞 {phone}")
        st.link_button("Chat", f"https://wa.me/91{phone}")
        
        with st.form(f"f_{i}"):
            new_s = st.selectbox("Status", ["Naya", "Call Done", "Sold"], key=f"s_{i}")
            if st.form_submit_button("Update"):
                # Find Status Column Index automatically
                status_col_index = 8 # Default
                try:
                    # Try to find "Status" column number dynamically
                    headers = sheet.row_values(1)
                    status_col_index = headers.index("Status") + 1
                except:
                    pass
                
                sheet.update_cell(i + 2, status_col_index, new_s)
                st.success("Updated!")
                st.rerun()
