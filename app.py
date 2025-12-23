import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="TerraTip CRM", page_icon="🏡", layout="wide")

# --- CONNECTION ---
@st.cache_resource
def connect_to_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Critical: Secrets not found.")
        st.stop()
    
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client, creds_dict.get("client_email")
    except Exception as e:
        st.error(f"❌ Auth Failed: {e}")
        st.stop()

# --- MAIN LOGIC ---
try:
    client, bot_email = connect_to_google_sheets()
    
    # --- DIAGNOSTIC: TEST DRIVE API ---
    with st.expander("🕵️‍♂️ Connection Diagnostics (Check here first!)", expanded=True):
        st.write(f"**🤖 Bot Email:** `{bot_email}`")
        try:
            # Try to list files. If this fails, Drive API is OFF.
            files = client.list_spreadsheet_files()
            if not files:
                st.warning("⚠️ The Bot sees 0 files. Google Drive API might be OFF or sync is delayed.")
            else:
                st.success(f"✅ The Bot can see {len(files)} files. Connection is GOOD.")
                for f in files:
                    st.text(f"Found: {f['name']} (ID: {f['id']})")
        except Exception as e:
            st.error("❌ CRITICAL: Google Drive API is DISABLED.")
            st.info("👉 Go to Cloud Console > APIs > Enable 'Google Drive API'.")
            st.stop()

    # --- OPEN SHEET ---
    # We use the ID from your screenshot
    sheet_id = "1glNrjdnr9sg7nkKh0jcazwZ5_92Rv4ZBeBYFaDZ_khU"
    
    sheet = client.open_by_key(sheet_id).sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

except Exception as e:
    st.error(f"❌ Error Opening Sheet: {e}")
    st.stop()

# --- APP INTERFACE ---
st.sidebar.title("TerraTip CRM")
user_user = st.sidebar.selectbox("User", ["Manager", "Amit (TC1)", "Rahul (TC2)"])

# Filter Data
if "TC" in user_user:
    tc_code = "TC1" if "Amit" in user_user else "TC2"
    if 'Assigned' in df.columns:
         df = df[df['Assigned'] == tc_code]

st.title(f"Welcome, {user_user}")

for index, row in df.iterrows():
    c_name = row.get('Client Name', 'Unknown')
    c_status = row.get('Status', 'Naya')
    c_phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
    
    with st.expander(f"{c_name} ({c_status})"):
        st.write(f"📞 {c_phone}")
        
        wa_link = f"https://wa.me/91{c_phone}?text=Namaste {c_name}"
        st.link_button("Chat on WhatsApp", wa_link)
        
        with st.form(key=f"f_{index}"):
            new_stat = st.selectbox("Status", ["Naya", "Call Done", "Lost", "Sold"], key=f"s_{index}")
            if st.form_submit_button("Update"):
                sheet.update_cell(index + 2, 8, new_stat) # Col 8 = Status
                st.success("Updated!")
                st.rerun()
