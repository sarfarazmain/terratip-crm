import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- PAGE CONFIG ---
st.set_page_config(page_title="TerraTip CRM", page_icon="🏡", layout="mobile")

# --- CONNECT TO GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # This checks if we are running on Streamlit Cloud (Secrets) or Locally
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Fallback for local testing if you have the file
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
    client = gspread.authorize(creds)
    return client

try:
    client = get_google_sheet_client()
    # MAKE SURE YOUR GOOGLE SHEET IS NAMED EXACTLY THIS:
    sheet = client.open("TerraTip_AppSheet_Backend").sheet1 
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
except Exception as e:
    st.error("🚨 Connection Error. Please check your Secrets setup.")
    st.stop()

# --- SIDEBAR LOGIN ---
st.sidebar.title("TerraTip Login")
user_user = st.sidebar.selectbox("Select User", ["Manager", "Amit (TC1)", "Rahul (TC2)", "Sales Specialist"])

# --- PRIVACY LOGIC ---
if user_user == "Manager":
    filtered_df = df
elif "TC" in user_user:
    tc_code = "TC1" if "Amit" in user_user else "TC2"
    # Ensure your Google Sheet has a column named "Assigned TC Email" or similar
    # For this code, we map TC1/TC2 to that column. Adjust column name if needed.
    if 'Assigned TC Email' in df.columns:
         filtered_df = df[df['Assigned TC Email'] == tc_code]
    else:
         st.warning("Column 'Assigned TC Email' not found in sheet.")
         filtered_df = df
elif user_user == "Sales Specialist":
    filtered_df = df[df['Status'] == "Site Visit Scheduled"]

# --- APP INTERFACE ---
st.title(f"🏡 Welcome, {user_user}")

for index, row in filtered_df.iterrows():
    with st.expander(f"{row['Client Name']} ({row['Status']})"):
        st.write(f"**Phone:** {row['Phone']}")
        
        # WhatsApp Button
        wa_link = f"https://wa.me/91{row['Phone']}?text=Namaste {row['Client Name']}"
        st.link_button("💬 WhatsApp", wa_link)
        
        # Status Update
        with st.form(key=f"form_{index}"):
            new_status = st.selectbox("Update Status", 
                ["Naya", "Call Done", "Site Visit Scheduled", "No Show", "Lost", "Sold"],
                key=f"status_{index}"
            )
            submit = st.form_submit_button("Save")
            
            if submit:
                # Find real row number (Index + 2 for header and 0-index)
                real_row = index + 2
                # Update Status Column (Assuming Column H / Index 8)
                sheet.update_cell(real_row, 8, new_status)
                st.success("Updated!")
                st.rerun()
