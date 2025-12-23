import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import hashlib

# --- CONFIGURATION ---
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡")

# Remove top bars
hide_bar = """<style>header {visibility: hidden;} footer {visibility: hidden;} #MainMenu {visibility: hidden;}</style>"""
st.markdown(hide_bar, unsafe_allow_html=True)

# --- 1. AUTHENTICATION & DATABASE FUNCTIONS ---
@st.cache_resource
def connect_db():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Secrets missing.")
        st.stop()
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # Auto-Discover File
    files = client.list_spreadsheet_files()
    if not files:
        st.error("❌ No Sheet found.")
        st.stop()
    
    sh = client.open_by_key(files[0]['id'])
    return sh

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_auth_system(sh):
    # Check if 'Users' tab exists, if not create it
    try:
        ws = sh.worksheet("Users")
    except:
        ws = sh.add_worksheet(title="Users", rows=100, cols=5)
        # Add Header and Default Admin
        ws.append_row(["Username", "Password", "Role", "Name"])
        ws.append_row(["admin", hash_pass("admin123"), "Manager", "System Admin"])
    return ws

def check_credentials(username, password, users_df):
    hashed = hash_pass(password)
    user_row = users_df[users_df['Username'] == username]
    if not user_row.empty:
        stored_pass = user_row.iloc[0]['Password']
        if stored_pass == hashed:
            return user_row.iloc[0]
    return None

# --- 2. INITIALIZATION ---
try:
    sh = connect_db()
    
    # 1. Setup/Get Users Tab
    users_sheet = init_auth_system(sh)
    users_data = users_sheet.get_all_records()
    users_df = pd.DataFrame(users_data)
    
    # 2. Setup/Get Leads Tab
    found_sheet = None
    for ws in sh.worksheets():
        if "lead" in ws.title.lower(): found_sheet = ws; break
    leads_sheet = found_sheet if found_sheet else sh.get_worksheet(0)
    
except Exception as e:
    st.error(f"Connection Error: {e}")
    st.stop()

# --- 3. LOGIN LOGIC ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 TerraTip Login")
        with st.form("login_form"):
            user_input = st.text_input("Username")
            pass_input = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                user_info = check_credentials(user_input, pass_input, users_df)
                if user_info is not None:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user_info['Username']
                    st.session_state['role'] = user_info['Role']
                    st.session_state['name'] = user_info['Name']
                    st.rerun()
                else:
                    st.error("Invalid Username or Password")
    st.stop() # Stop here if not logged in

# --- 4. APP DASHBOARD (Only visible after login) ---

# Sidebar Info
st.sidebar.title("TerraTip CRM 🏡")
st.sidebar.write(f"👤 **{st.session_state['name']}**")
st.sidebar.write(f"🛡️ {st.session_state['role']}")

if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.rerun()

st.sidebar.divider()

# --- ADMIN PANEL (Only for Manager) ---
if st.session_state['role'] == "Manager":
    with st.sidebar.expander("⚙️ Manage Users (Admin)"):
        with st.form("new_user"):
            new_u = st.text_input("New Username")
            new_p = st.text_input("New Password", type="password")
            new_n = st.text_input("Full Name")
            new_r = st.selectbox("Role", ["Telecaller", "Sales Specialist", "Manager"])
            if st.form_submit_button("Create User"):
                if new_u and new_p:
                    # Check duplicate
                    if new_u in users_df['Username'].values:
                        st.error("Username exists!")
                    else:
                        users_sheet.append_row([new_u, hash_pass(new_p), new_r, new_n])
                        st.success(f"Created {new_u}!")
                        st.rerun() # Refresh to update list

# --- MAIN CRM LOGIC ---

# 1. Load Leads
leads_data = leads_sheet.get_all_records()
leads_df = pd.DataFrame(leads_data)

# 2. Filter Logic (Based on Role)
if st.session_state['role'] == "Telecaller":
    # Filter for their name or ID
    # We match "Name" from login to "Assigned" column in Leads
    col_match = [c for c in leads_df.columns if "Assigned" in c]
    if col_match:
        # We assume the 'Assigned' column in Excel uses the Telecaller's Name or Username
        # Let's try matching both
        leads_df = leads_df[
            (leads_df[col_match[0]] == st.session_state['username']) | 
            (leads_df[col_match[0]] == st.session_state['name']) |
            (leads_df[col_match[0]] == "TC1") # Fallback for old data
        ]

# 3. Add Lead Form
with st.expander("➕ Add New Lead", expanded=False):
    with st.form("add_lead"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Client Name")
        phone = c2.text_input("Phone")
        source = st.selectbox("Source", ["Meta Ads", "Referral", "Cold Call"])
        if st.form_submit_button("Save"):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            # Modify this row to match your Excel structure exactly!
            # Example: [ID, Time, Name, Phone, Source, Agent, Assigned, Status...]
            new_row = ["L-New", ts, name, phone, source, st.session_state['name'], st.session_state['username'], "Naya"]
            leads_sheet.append_row(new_row)
            st.success("Saved!")
            st.rerun()

# 4. Display Leads
st.divider()

# Ghost Row Cleaner
if not leads_df.empty and 'Client Name' in leads_df.columns:
    leads_df = leads_df[leads_df['Client Name'] != ""]

if leads_df.empty:
    st.info("No leads assigned to you.")

for i, row in leads_df.iterrows():
    name = row.get('Client Name', 'Unknown')
    status = row.get('Status', 'Naya')
    phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
    
    icon = "⚪"
    if status == "Sold": icon = "🟢"
    if status == "Lost": icon = "🔴"
    if status == "Site Visit Scheduled": icon = "🚕"
    
    with st.expander(f"{icon} {name} | {status}"):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.write(f"📞 **{phone}**")
            st.write(f"📌 {row.get('Source', '-')}")
        with c2:
            st.link_button("WhatsApp", f"https://wa.me/91{phone}?text=Namaste {name}")
        
        with st.form(f"u_{i}"):
            ns = st.selectbox("Status", ["Naya", "Call Done", "Site Visit Scheduled", "Lost", "Sold"], key=f"s_{i}")
            note = st.text_input("Note", key=f"n_{i}")
            if st.form_submit_button("Update"):
                try:
                    head = leads_sheet.row_values(1)
                    s_idx = head.index("Status") + 1
                    try: n_idx = head.index("Notes") + 1
                    except: n_idx = 12
                    
                    real_row = i + 2
                    leads_sheet.update_cell(real_row, s_idx, ns)
                    if note: leads_sheet.update_cell(real_row, n_idx, note)
                    st.success("Updated!")
                    st.rerun()
                except:
                    st.error("Error finding columns.")
