import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="TerraTip CRM", layout="wide")

# --- STEP 1: CONNECT ---
@st.cache_resource
def connect():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

try:
    client = connect()
    st.success("✅ Step 1: Bot Logged In")
    
    # --- STEP 2: OPEN WORKBOOK ---
    # ID from your screenshot: 1glNrjdnr9sg7nkKh0jcazwZ5_92Rv4ZBeBYFaDZ_khU
    sheet_id = "1glNrjdnr9sg7nkKh0jcazwZ5_92Rv4ZBeBYFaDZ_khU"
    
    try:
        sh = client.open_by_key(sheet_id)
        st.success(f"✅ Step 2: Found File '{sh.title}'")
    except Exception as e:
        st.error(f"❌ Failed to open file: {e}")
        st.stop()

    # --- STEP 3: LIST TABS (The Diagnosis) ---
    st.info("👇 The Bot sees these Tabs inside your file:")
    
    worksheet_list = sh.worksheets()
    found_leads = False
    
    for ws in worksheet_list:
        # We print the EXACT name (with quotes) to see hidden spaces
        st.write(f"📄 Found Tab: `'{ws.title}'`")
        if "lead" in ws.title.lower():
            sheet = ws
            found_leads = True
    
    if not found_leads:
        st.warning("⚠️ logic: Could not find a tab named 'Leads'. Defaulting to first tab.")
        sheet = sh.get_worksheet(0)
    else:
        st.success(f"✅ Selected Tab: '{sheet.title}'")

    # --- STEP 4: LOAD DATA ---
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    st.write("---")

except Exception as e:
    st.error(f"❌ CRASH REPORT: {e}")
    st.stop()

# --- APP INTERFACE ---
st.title("TerraTip CRM")
user = st.sidebar.selectbox("User", ["Manager", "Amit (TC1)", "Rahul (TC2)"])

if "TC" in user:
    code = "TC1" if "Amit" in user else "TC2"
    # Flexible filter
    if 'Assigned' in df.columns: df = df[df['Assigned'] == code]
    elif 'Assigned TC' in df.columns: df = df[df['Assigned TC'] == code]

for i, row in df.iterrows():
    name = row.get('Client Name', 'Unknown')
    phone = str(row.get('Phone', '')).replace(',', '')
    status = row.get('Status', 'Naya')
    
    with st.expander(f"{name} ({status})"):
        st.write(f"📞 {phone}")
        st.link_button("Chat", f"https://wa.me/91{phone}")
        
        with st.form(f"f_{i}"):
            new_s = st.selectbox("Status", ["Naya", "Call Done", "Sold"], key=f"s_{i}")
            if st.form_submit_button("Update"):
                # Use the 'sheet' variable we found in Step 3
                sheet.update_cell(i + 2, 8, new_s)
                st.success("Updated!")
                st.rerun()
