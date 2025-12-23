import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- PAGE CONFIG ---
st.set_page_config(page_title="TerraTip CRM", page_icon="🏡", layout="wide")

# --- CONNECTION FUNCTION ---
@st.cache_resource
def connect_to_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Critical Error: Secrets not found.")
        st.stop()
    
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
        
    except Exception as e:
        st.error(f"❌ Authentication Failed: {e}")
        st.stop()

# --- MAIN LOGIC ---
try:
    client = connect_to_google_sheets()
    
    # URL from your screenshot
    sheet_url = "https://docs.google.com/spreadsheets/d/1glNrjdnr9sg7nkKh0jcazwZ5_92Rv4ZBeBYFaDZ_khU/edit"
    
    try:
        sheet = client.open_by_url(sheet_url).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
    except Exception as e:
        st.error(f"❌ Spreadsheet Error: {e}")
        st.stop()

except Exception as e:
    st.error(f"❌ System Error: {e}")
    st.stop()

# --- SIDEBAR ---
st.sidebar.title("TerraTip Login")
st.sidebar.success("✅ Database Connected") 
user_user = st.sidebar.selectbox("Select User", ["Manager", "Amit (TC1)", "Rahul (TC2)", "Sales Specialist"])

# --- FILTERING LOGIC (Updated for your Column Names) ---
if user_user == "Manager":
    filtered_df = df
elif "TC" in user_user:
    tc_code = "TC1" if "Amit" in user_user else "TC2"
    
    # Your screenshot shows the column is named "Assigned"
    if 'Assigned' in df.columns:
         filtered_df = df[df['Assigned'] == tc_code]
    elif 'Assigned TC' in df.columns:
         filtered_df = df[df['Assigned TC'] == tc_code]
    else:
         st.warning("⚠️ Column 'Assigned' not found. Showing all data.")
         filtered_df = df
elif user_user == "Sales Specialist":
    if 'Status' in df.columns:
        filtered_df = df[df['Status'] == "Site Visit Scheduled"]
    else:
        filtered_df = df

# --- UI DISPLAY ---
st.title(f"🏡 Welcome, {user_user}")

if filtered_df.empty:
    st.info("No leads found for this view.")

for index, row in filtered_df.iterrows():
    # Safe Get to avoid errors
    c_name = row.get('Client Name', 'Unknown')
    c_status = row.get('Status', 'Naya')
    # Convert phone to string to prevent comma issues (e.g. 9,999...)
    c_phone = str(row.get('Phone', '')).replace(',', '')
    
    with st.expander(f"{c_name} ({c_status})"):
        st.write(f"**Phone:** {c_phone}")
        st.write(f"**Source:** {row.get('Source', 'N/A')}")
        
        # WhatsApp Link
        wa_link = f"https://wa.me/91{c_phone}?text=Namaste {c_name}, TerraTip se baat kar raha hoon."
        st.link_button("💬 Chat on WhatsApp", wa_link)
        
        # Update Form (Fixed Syntax Error here)
        form_key_name = f"form_{index}"
        selectbox_key_name = f"status_{index}"
        
        with st.form(key=form_key_name):
            new_status = st.selectbox(
                "Update Status", 
                ["Naya", "Call Done", "Site Visit Scheduled", "No Show", "Lost", "Sold"],
                key=selectbox_key_name
            )
            
            submit = st.form_submit_button("💾 Save Update")
            
            if submit:
                # Index + 2 is the standard calculation for GSpread (Header + 1-based index)
                real_row = index + 2
                try:
                    # Updating Column 8 (Status) based on your screenshot
                    sheet.update_cell(real_row, 8, new_status)
                    st.success(f"Updated {c_name}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to write: {e}")
