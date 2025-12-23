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
            submit = st.form_submit_button("Login Karein")
            
            if submit:
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
                    st.error("❌ Galat Username ya Password.")
    st.stop()

# --- 4. APP LAYOUT ---

st.sidebar.title("TerraTip CRM 🏡")
st.sidebar.write(f"👤 **{st.session_state['name']}**")
st.sidebar.caption(f"Role: {st.session_state['role']}")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.rerun()

# --- FUNCTIONS FOR MAIN VIEWS ---

def show_crm_dashboard(users_df):
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

    # 3. ADD NEW LEAD
    with st.expander("➕ Naya Lead Jodein", expanded=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Customer Ka Naam")
        phone = c2.text_input("Phone Number (10 Digits)")
        
        c3, c4 = st.columns(2)
        source = c3.selectbox("Kahan se aaya? (Source)", ["Meta Ads", "Canopy", "Agent", "Others"])
        
        agent_name = ""
        if source == "Agent":
            agent_name = c4.text_input("Agent Ka Naam Likhein")
        
        assigned_to = st.session_state['username'] 
        if st.session_state['role'] == "Manager":
            all_users = users_df['Username'].tolist()
            assigned_to = st.selectbox("Kisko Dena Hai? (Assign To)", all_users, index=all_users.index(st.session_state['username']) if st.session_state['username'] in all_users else 0)
        
        if st.button("💾 Lead Save Karein", type="primary"):
            if not name:
                st.error("⚠️ Customer ka naam likhna zaroori hai.")
            elif not phone.isdigit() or len(phone) != 10:
                st.error("⚠️ Galat Phone Number.")
            elif source == "Agent" and not agent_name:
                st.error("⚠️ Agent ka naam likhna zaroori hai.")
            else:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                # Default status is 'Naya Lead'
                new_row = ["L-New", ts, name, phone, source, agent_name, assigned_to, "Naya Lead"]
                leads_sheet.append_row(new_row)
                st.success(f"✅ Lead Save Ho Gaya! (Assigned to {assigned_to})")
                st.rerun()

    # 4. Display Leads
    st.divider()
    if not leads_df.empty and 'Client Name' in leads_df.columns:
        leads_df = leads_df[leads_df['Client Name'] != ""]

    if leads_df.empty:
        st.info("📭 Abhi koi leads nahi hain.")

    # --- NEW PIPELINE LOGIC ---
    def get_instruction(status):
        if status == "Naya Lead": 
            return "⚡ ACTION: Abhi call karein aur project samjhayein."
        if status == "Call Uthaya Nahi / Busy": 
            return "⏰ ACTION: 4 ghante baad phir try karein. WhatsApp par 'Hello' bhejein."
        if status == "Baat Hui - Interested": 
            return "💬 ACTION: WhatsApp par Brochure bhejein aur Site Visit ke liye manayein."
        if status == "Site Visit Scheduled": 
            return "📍 ACTION: Visit se 2 ghante pehle confirm karein."
        if status == "Visit Done - Soch Raha Hai": 
            return "🤝 ACTION: Booking amount ke liye baat karein. Deal close karein!"
        if status == "Faltu / Agent / Spam": 
            return "🗑️ ACTION: Isko ignore karein. Dobara call na karein."
        if status == "Not Interested (Mehenga Hai)": 
            return "❌ ACTION: Call na karein. Future project ke liye rakhein."
        if status == "Sold (Plot Bik Gaya)": 
            return "🎉 ACTION: Mithai khilayein!"
        return "❓ ACTION: Status update karein."

    # Status Options List
    status_options = [
        "Naya Lead",
        "Call Uthaya Nahi / Busy",
        "Baat Hui - Interested",
        "Site Visit Scheduled",
        "Visit Done - Soch Raha Hai",
        "Faltu / Agent / Spam",
        "Not Interested (Mehenga Hai)",
        "Sold (Plot Bik Gaya)"
    ]

    for i, row in leads_df.iterrows():
        name = row.get('Client Name', 'Unknown')
        status = row.get('Status', 'Naya Lead')
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        
        # Color coding icons
        icon = "⚪"
        if "Sold" in status: icon = "🟢"
        if "Faltu" in status or "Not Interested" in status: icon = "🔴"
        if "Visit" in status: icon = "🚕"
        if "Naya" in status: icon = "⚡"
        if "Interested" in status: icon = "🔹"
        
        with st.expander(f"{icon} {name} | {status}"):
            # ACTION BOX
            instruction = get_instruction(status)
            if "ACTION" in instruction:
                if "🗑️" in instruction or "❌" in instruction:
                    st.error(instruction)
                elif "🎉" in instruction:
                    st.success(instruction)
                else:
                    st.info(instruction)
            
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(f"📞 **{phone}**")
                st.write(f"📌 Source: {row.get('Source', '-')}")
                if row.get('Agent Name'): st.write(f"👤 Agent: {row.get('Agent Name')}")
                st.caption(f"Assigned: {row.get('Assigned', '-')}")
                
            with c2:
                st.link_button("💬 WhatsApp", f"https://wa.me/91{phone}?text=Namaste {name}, TerraTip se baat kar raha hoon.")
            
            with st.form(f"u_{i}"):
                # Use the new status list here
                ns = st.selectbox("Status Badlein (Result Kya Hua?)", status_options, key=f"s_{i}")
                note = st.text_input("Koi Note Likhein (Optional)", key=f"n_{i}")
                
                if st.form_submit_button("💾 Update Result"):
                    try:
                        headers = leads_sheet.row_values(1)
                        try: s_idx = headers.index("Status") + 1
                        except: s_idx = 8 
                        try: n_idx = headers.index("Notes") + 1
                        except: n_idx = 12
                        
                        real_row = i + 2
                        leads_sheet.update_cell(real_row, s_idx, ns)
                        if note: leads_sheet.update_cell(real_row, n_idx, note)
                        st.success("✅ Update Ho Gaya!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

def show_admin_panel(users_df, users_sheet):
    st.header("⚙️ Admin Panel")
    if 'admin_msg' in st.session_state and st.session_state['admin_msg']:
        st.success(st.session_state['admin_msg'])
        st.session_state['admin_msg'] = None

    ac1, ac2 = st.columns([1, 2])
    with ac1:
        st.subheader("Naya Banda Jodein")
        with st.form("new_user", clear_on_submit=True):
            new_u = st.text_input("Username")
            new_p = st.text_input("Password", type="password")
            new_n = st.text_input("Poora Naam")
            new_r = st.selectbox("Role", ["Telecaller", "Sales Specialist", "Manager"])
            if st.form_submit_button("Create User"):
                if new_u and new_p:
                    if new_u in users_df['Username'].values:
                        st.error("⚠️ Username exists!")
                    else:
                        users_sheet.append_row([new_u, hash_pass(new_p), new_r, new_n])
                        st.session_state['admin_msg'] = f"✅ User '{new_u}' ban gaya!"
                        st.rerun()
    with ac2:
        st.subheader("Team List")
        st.dataframe(users_df[['Name', 'Username', 'Role']], use_container_width=True, hide_index=True)
        st.divider()
        
        st.subheader("Delete User")
        options = [u for u in users_df['Username'].unique() if u != st.session_state['username']]
        if options:
            c_del_1, c_del_2 = st.columns([3,1])
            with c_del_1:
                del_target = st.selectbox("User Select Karein", options, label_visibility="collapsed")
            with c_del_2:
                if st.button("❌ DELETE", type="primary"):
                    cell = users_sheet.find(del_target)
                    users_sheet.delete_rows(cell.row)
                    st.session_state['admin_msg'] = f"🗑️ {del_target} ko delete kar diya."
                    st.rerun()

# --- 5. MAIN PAGE LOGIC ---
if st.session_state['role'] == "Manager":
    tab1, tab2 = st.tabs(["🏠 Leads Dashboard", "⚙️ Admin Panel"])
    with tab1: show_crm_dashboard(users_df)
    with tab2: show_admin_panel(users_df, users_sheet)
else:
    show_crm_dashboard(users_df)
