import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- PAGE CONFIG ---
st.set_page_config(page_title="TerraTip CRM", page_icon="🏡", layout="wide")

# --- ROBUST CONNECTION FUNCTION ---
@st.cache_resource
def connect_to_google_sheets():
    # Define the "Scopes" (Permissions we need)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # DEBUG STEP 1: Check if Secrets exist
    if "gcp_service_account" not in st.secrets:
        st.error("❌ CRITICAL ERROR: Secrets not found!")
        st.info("Did you paste the TOML code into the 'Secrets' tab on Streamlit Cloud?")
        st.stop()
    
    try:
        # Load credentials from Streamlit Secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # DEBUG STEP 2: Verify Key Type (without revealing the key)
        if "private_key" in creds_dict:
            # Fix common copy-paste error where \n is treated as text instead of new line
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        # Authenticate using modern google-auth library
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
        
    except Exception as e:
        st.error(f"❌ Authentication Failed: {e}")
        st.stop()

# --- MAIN APP LOGIC ---
try:
    client = connect_to_google_sheets()
    
    # DEBUG STEP 3: Try to open the specific sheet
    sheet_name = "TerraTip_AppSheet_Backend"
    try:
        sheet = client.open(sheet_name).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ Spreadsheet Not Found: '{sheet_name}'")
        st.info("Please make sure you created the Google Sheet and SHARED it with the 'client_email' from your JSON key.")
        st.info(f"The bot email is: {st.secrets['gcp_service_account']['client_email']}")
        st.stop()

except Exception as e:
    st.error(f"❌ Unknown Error: {e}")
    st.stop()

# --- SIDEBAR & LOGIN ---
st.sidebar.title("TerraTip Login")
st.sidebar.success("✅ Connected to Database") # Visual confirmation
user_user = st.sidebar.selectbox("Select User", ["Manager", "Amit (TC1)", "Rahul (TC2)", "Sales Specialist"])

# --- FILTERING LOGIC ---
if user_user == "Manager":
    filtered_df = df
elif "TC" in user_user:
    tc_code = "TC1" if "Amit" in user_user else "TC2"
    
    # Check if column exists
    if 'Assigned TC Email' in df.columns:
         filtered_df = df[df['Assigned TC Email'] == tc_code]
    elif 'Assigned TC' in df.columns:
         filtered_df = df[df['Assigned TC'] == tc_code]
    else:
         st.warning("⚠️ Column 'Assigned TC' not found. Showing all data.")
         filtered_df = df
elif user_user == "Sales Specialist":
    filtered_df = df[df['Status'] == "Site Visit Scheduled"]

# --- UI DISPLAY ---
st.title(f"🏡 Welcome, {user_user}")

if filtered_df.empty:
    st.info("No leads found for this view.")

for index, row in filtered_df.iterrows():
    with st.expander(f"{row['Client Name']} ({row['Status']})"):
        st.write(f"**Phone:** {row['Phone']}")
        st.write(f"**Source:** {row.get('Source', 'N/A')}")
        
        # WhatsApp Link
        wa_link = f"https://wa.me/91{row['Phone']}?text=Namaste {row['Client Name']}, TerraTip se baat kar raha hoon."
        st.link_button("💬 Chat on WhatsApp", wa_link)
        
        # Update Form
        with st.form(key=f"form_{index}"):
            new_status = st.selectbox(
                "Update Status", 
                ["Naya", "Call Done", "Site Visit Scheduled", "No Show", "Lost", "Sold"],
                key=f"status_{index}"
            )
            
            submit = st.form_submit_button("💾 Save Update")
            
            if submit:
                # Find real row (Index + 2 for header/0-index)
                real_row = index + 2
                
                try:
                    # Update Column 8 (Status) - Change '8' if your status column is different
                    sheet.update_cell(real_row, 8, new_status)
                    st.success(f"Updated {row['Client Name']}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to write to Google Sheet: {e}")
