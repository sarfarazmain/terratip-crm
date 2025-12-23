import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import hashlib

# --- CONFIGURATION ---
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡")
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
    
    files = client.list_spreadsheet_files()
    if not files:
        st.error("❌ No Sheet found.")
        st.stop()
    
    sh = client.open_by_key(files[0]['id'])
    return sh

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_auth_system(sh):
    try:
        ws = sh.worksheet("Users")
    except:
        ws = sh.add_worksheet(title="Users", rows=100, cols=5)
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
    users_sheet = init_auth_system(sh)
    users_data = users_sheet.get_all_records()
    users_df = pd.DataFrame(users_data)
    
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
                # Refresh user data
                users_data = users_sheet.get_all_records()
                users_df = pd.DataFrame(users_data)
                
                user_info = check_credentials(user_input, pass_input, users_df)
                if user_info is not None:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user_info['Username']
                    st.session_state['role'] = user_info['Role']
                    st.session_state['name'] = user_info['Name']
                    st.rerun()
                else:
                    st.error("Invalid Username or Password")
    st.stop()

# --- 4. APP LAYOUT ---

# SIDEBAR (Simple Profile Info Only)
st.sidebar.title("TerraTip CRM 🏡")
st.sidebar.write(f"👤 **{st.session_state['name']}**")
st.sidebar.caption(f"Role: {st.session_state['role']}")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.rerun()

# --- FUNCTIONS FOR MAIN VIEWS ---

def show_crm_dashboard():
    # 1. Load Leads
    leads_data = leads_sheet.get_all_records()
    leads_df = pd.DataFrame(leads_data)

    # 2. Filter Logic
    if st.session_state['role'] == "Telecaller":
        col_match = [c for c in leads_df.columns if "Assigned" in c]
        if col_match:
            leads_df = leads_df[
                (leads_df[col_match[0]] == st.session_state['username']) | 
                (leads_df[col_match[0]] == st.session_state['name']) |
                (leads_df[col_match[0]] == "TC1")
            ]

    # 3. Add Lead Form
    with st.expander("➕ Add New Lead", expanded=False):
        with st.form("add_lead", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Client Name")
            phone = c2.text_input("Phone")
            source = st.selectbox("Source", ["Meta Ads", "Referral", "Cold Call"])
            if st.form_submit_button("Save"):
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                new_row = ["L-New", ts, name, phone, source, st.session_state['name'], st.session_state['username'], "Naya"]
                leads_sheet.append_row(new_row)
                st.success("Lead Saved Successfully!")
                st.rerun()

    # 4. Display Leads
    st.divider()
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

def show_admin_panel():
    st.header("⚙️ Admin Panel")
    
    # Message Relay
    if 'admin_msg' in st.session_state and st.session_state['admin_msg']:
        st.success(st.session_state['admin_msg'])
        st.session_state['admin_msg'] = None

    # Two Columns: Create vs View/Delete
    ac1, ac2 = st.columns([1, 2])
    
    with ac1:
        st.subheader("Create User")
        with st.form("new_user", clear_on_submit=True):
            new_u = st.text_input("Username")
            new_p = st.text_input("Password", type="password")
            new_n = st.text_input("Full Name")
            new_r = st.selectbox("Role", ["Telecaller", "Sales Specialist", "Manager"])
            
            if st.form_submit_button("Create User"):
                if new_u and new_p:
                    if new_u in users_df['Username'].values:
                        st.error(f"User '{new_u}' already exists!")
                    else:
                        users_sheet.append_row([new_u, hash_pass(new_p), new_r, new_n])
                        st.session_state['admin_msg'] = f"✅ Created user: {new_u}"
                        st.rerun()
    
    with ac2:
        st.subheader("Existing Users")
        display_df = users_df[['Name', 'Username', 'Role']]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("Delete User")
        
        options = [u for u in users_df['Username'].unique() if u != st.session_state['username']]
        if options:
            c_del_1, c_del_2 = st.columns([3,1])
            with c_del_1:
                delete_target = st.selectbox("Select User to Remove", options, label_visibility="collapsed")
            with c_del_2:
                if st.button("❌ DELETE", type="primary"):
                    try:
                        cell = users_sheet.find(delete_target)
                        users_sheet.delete_rows(cell.row)
                        st.session_state['admin_msg'] = f"🗑️ Deleted user: {delete_target}"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            st.info("No users to delete.")

# --- 5. MAIN PAGE LOGIC ---

if st.session_state['role'] == "Manager":
    # Manager sees Tabs
    tab1, tab2 = st.tabs(["🏡 CRM Dashboard", "⚙️ Admin Panel"])
    
    with tab1:
        show_crm_dashboard()
        
    with tab2:
        show_admin_panel()

else:
    # Telecaller sees ONLY Dashboard (No Tabs)
    show_crm_dashboard()
