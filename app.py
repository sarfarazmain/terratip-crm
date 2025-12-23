import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- PAGE CONFIG ---
st.set_page_config(page_title="TerraTip CRM", page_icon="🏡", layout="wide")

# --- ROBUST CONNECTION FUNCTION ---
@st.cache_resource
def connect_to_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. CHECK SECRETS EXIST
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Critical Error: Secrets not found in Streamlit settings.")
        st.stop()
    
    try:
        # 2. LOAD CREDENTIALS
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Fix the "New Line" bug if present
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client, creds_dict.get("client_email")
        
    except Exception as e:
        st.error(f"❌ Authentication Failed: {e}")
        st.stop()

# --- MAIN APP LOGIC ---
try:
    client, bot_email = connect_to_google_sheets()
    
    # ======================================================
    # 🕵️‍♂️ DIAGNOSTIC MODE (This runs before loading data)
    # ======================================================
    with st.expander("🕵️‍♂️ Click here if you see Connection Errors", expanded=True):
        st.write(f"**🤖 Bot Email:** `{bot_email}`")
        st.info("👉 Please ensure your Google Sheet is SHARED with this email as 'Editor'.")
        
        st.write("**📂 Files currently visible to this Bot:**")
        try:
            # List all sheets the bot can access
            files = client.list_spreadsheet_files()
            if not files:
                st.error("❌ The bot sees 0 files. You have NOT shared the sheet correctly yet.")
            else:
                for f in files:
                    st.success(f"✅ Found Sheet: '{f['name']}' (ID: {f['id']})")
        except Exception as e:
            st.warning(f"Could not list files (Drive API might be off): {e}")

    # ======================================================
    # 📝 LOAD DATA
    # ======================================================
    
    # 1. ATTEMPT TO OPEN BY URL (Replace this if Diagnostic Mode gives you a better ID)
    # Based on your previous screenshot, this is the URL
    target_url = "https://docs.google.com/spreadsheets/d/1glNrjdnr9sg7nkKh0jcazwZ5_92Rv4ZBeBYFaDZ_khU/edit"
    
    try:
        sheet = client.open_by_url(target_url).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("❌ ERROR 404: Sheet Not Found.")
        st.stop()
    except gspread.exceptions.APIError as e:
        st.error(f"❌ Google API Error: {e}")
        st.stop()

except Exception as e:
    st.error(f"❌ System Error: {e}")
    st.stop()

# --- SIDEBAR & LOGIN ---
st.sidebar.title("TerraTip Login")
user_user = st.sidebar.selectbox("Select User", ["Manager", "Amit (TC1)", "Rahul (TC2)", "Sales Specialist"])

# --- FILTERING LOGIC ---
if user_user == "Manager":
    filtered_df = df
elif "TC" in user_user:
    tc_code = "TC1" if "Amit" in user_user else "TC2"
    
    # Flexible Column Checking
    if 'Assigned TC Email' in df.columns:
         filtered_df = df[df['Assigned TC Email'] == tc_code]
    elif 'Assigned' in df.columns:
         filtered_df = df[df['Assigned'] == tc_code]
    elif 'Assigned TC' in df.columns:
         filtered_df = df[df['Assigned TC'] == tc_code]
    else:
         st.warning("⚠️ Column 'Assigned TC' not found. Showing all data.")
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
    # Safe Get (.get avoids crashes if column is missing)
    c_name = row.get('Client Name', 'Unknown')
    c_status = row.get('Status', 'Naya')
    c_phone = row.get('Phone', '')
    
    with st.expander(f"{c_name} ({c_status})"):
        st.write(f"**Phone:** {c_phone}")
        st.write(f"**Source:** {row.get('Source', 'N/A')}")
        
        # WhatsApp Link
        wa_link = f"https://wa.me/91{c_phone}?text=Namaste {c_name}, TerraTip se baat kar raha hoon."
        st.link_button("💬 Chat on WhatsApp", wa_link)
        
        # Update Form
        with st.form(key=f"form_{index}"):
            new_status = st.selectbox(
                "Update Status", 
                ["Naya", "Call Done", "Site Visit Scheduled", "No Show", "Lost", "Sold"],
                key=f"
