import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- PAGE CONFIG (FIXED) ---
# Changed layout="mobile" to layout="wide" to fix the error
st.set_page_config(page_title="TerraTip CRM", page_icon="🏡", layout="wide")

# --- CONNECT TO GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Check if running on Streamlit Cloud (uses Secrets) or Locally (uses file)
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Fallback for local testing
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        except:
            st.error("⚠️ Credentials not found. If on Cloud, check Secrets. If local, check JSON file.")
            st.stop()
        
    client = gspread.authorize(creds)
    return client

try:
    client = get_google_sheet_client()
    # Opens the sheet named "TerraTip_AppSheet_Backend" (Sheet1)
    sheet = client.open("TerraTip_AppSheet_Backend").sheet1 
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"🚨 Connection Error: {e}")
    st.stop()

# --- SIDEBAR LOGIN ---
st.sidebar.title("TerraTip Login")
user_user = st.sidebar.selectbox("Select User", ["Manager", "Amit (TC1)", "Rahul (TC2)", "Sales Specialist"])

# --- PRIVACY LOGIC (Who sees what?) ---
if user_user == "Manager":
    filtered_df = df
elif "TC" in user_user:
    # Logic: Maps "Amit" to "TC1" and "Rahul" to "TC2"
    tc_code = "TC1" if "Amit" in user_user else "TC2"
    
    # Check if column exists to prevent crash
    if 'Assigned TC Email' in df.columns:
         filtered_df = df[df['Assigned TC Email'] == tc_code]
    elif 'Assigned TC' in df.columns:
         filtered_df = df[df['Assigned TC'] == tc_code]
    else:
         st.warning("⚠️ Column 'Assigned TC Email' not found in Excel. Showing all leads.")
         filtered_df = df
elif user_user == "Sales Specialist":
    filtered_df = df[df['Status'] == "Site Visit Scheduled"]

# --- MAIN APP INTERFACE ---
st.title(f"🏡 Welcome, {user_user}")

if filtered_df.empty:
    st.info("No leads found for this user.")

# LOOP THROUGH LEADS AND DISPLAY CARDS
for index, row in filtered_df.iterrows():
    # Create an expandable card for each lead
    with st.expander(f"{row['Client Name']} ({row['Status']})"):
        st.write(f"**Phone:** {row['Phone']}")
        st.write(f"**Source:** {row.get('Source', 'N/A')}")
        
        # 1. WHATSAPP BUTTON
        # It creates a clickable link that opens WhatsApp app
        wa_link = f"https://wa.me/91{row['Phone']}?text=Namaste {row['Client Name']}, TerraTip se baat kar raha hoon."
        st.link_button("💬 Chat on WhatsApp", wa_link)
        
        # 2. STATUS UPDATE FORM
        # We use a unique key for every form based on the index
        with st.form(key=f"form_{index}"):
            new_status = st.selectbox(
                "Update Status", 
                ["Naya", "Call Done", "Site Visit Scheduled", "No Show", "Lost", "Sold"],
                key=f"status_{index}"
            )
            
            submit = st.form_submit_button("💾 Save Update")
            
            if submit:
                # Calculate the real row number in Google Sheets
                # (Index + 2 because Sheets are 1-indexed and have a Header row)
                real_row = index + 2
                
                # Update the Status Column (Assuming it is Column H, which is index 8)
                # If your columns are different, change the '8' below.
                try:
                    sheet.update_cell(real_row, 8, new_status)
                    st.success(f"Updated {row['Client Name']} to {new_status}!")
                    st.rerun() # Refresh the page to show new data
                except Exception as e:
                    st.error(f"Error updating sheet: {e}")
