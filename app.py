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
    
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Secrets not found!")
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

# --- MAIN APP LOGIC ---
try:
    client = connect_to_google_sheets()
    
    # ---------------------------------------------------------
    # 👇 THE FIX: WE USE THE URL DIRECTLY (Taken from your screenshot)
    # ---------------------------------------------------------
    sheet_url = "https://docs.google.com/spreadsheets/d/1glNrjdnr9sg7nkKh0jcazwZ5_92Rv4ZBeBYFaDZ_khU/edit"
    
    try:
        # Open by URL is much safer than Open by Name
        sheet = client.open_by_url(sheet_url).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
    except gspread.exceptions.APIError as e:
         st.error(f"❌ Permission Error: The bot cannot open the sheet.")
         st.info("Please verify you clicked 'Share' -> pasted the bot email -> Set as Editor.")
         st.stop()
    except Exception as e:
         st.error(f"❌ Connection Error: {e}")
         st.stop()

except Exception as e:
    st.error(f"❌ Critical Error: {e}")
    st.stop()

# --- SIDEBAR & LOGIN ---
st.sidebar.title("TerraTip Login")
st.sidebar.success("✅ Connected to Database") 
user_user = st.sidebar.selectbox("Select User", ["Manager", "Amit (TC1)", "Rahul (TC2)", "Sales Specialist"])

# --- FILTERING LOGIC ---
if user_user == "Manager":
    filtered_df = df
elif "TC" in user_user:
    tc_code = "TC1" if "Amit" in user_user else "TC2"
    
    # Check if column exists
    if 'Assigned TC Email' in df.columns:
         filtered_df = df[df['Assigned TC Email'] == tc_code]
    elif 'Assigned' in df.columns: # Handling partial match from your screenshot
         filtered_df = df[df['Assigned'] == tc_code]
    elif 'Assigned TC' in df.columns:
         filtered_df = df[df['Assigned TC'] == tc_code]
    else:
         st.warning("⚠️ Column 'Assigned TC' not found. Showing all data.")
         filtered_df = df
elif user_user == "Sales Specialist":
    # Safe check for Status column
    if 'Status' in df.columns:
        filtered_df = df[df['Status'] == "Site Visit Scheduled"]
    else:
        filtered_df = df

# --- UI DISPLAY ---
st.title(f"🏡 Welcome, {user_user}")

if filtered_df.empty:
    st.info("No leads found for this view.")

for index, row in filtered_df.iterrows():
    # Use .get() to avoid errors if column names change
    client_name = row.get('Client Name', 'Unknown Client')
    status = row.get('Status', 'Naya')
    phone = row.get('Phone', '')
    
    with st.expander(f"{client_name} ({status})"):
        st.write(f"**Phone:** {phone}")
        st.write(f"**Source:** {row.get('Source', 'N/A')}")
        
        # WhatsApp Link
        wa_link = f"https://wa.me/91{phone}?text=Namaste {client_name}, TerraTip se baat kar raha hoon."
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
                    # Update Column 8 (Status) - Ensure this matches your Sheet
                    # Based on your screenshot, Status looks like Column H (8th)
                    sheet.update_cell(real_row, 8, new_status)
                    st.success(f"Updated {client_name}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to write to Google Sheet: {e}")
