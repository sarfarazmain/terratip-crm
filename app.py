import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import hashlib
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡")
hide_bar = """<style>header {visibility: hidden;} footer {visibility: hidden;} #MainMenu {visibility: hidden;}</style>"""
st.markdown(hide_bar, unsafe_allow_html=True)

# --- GLOBAL MESSAGE RELAY SYSTEM ---
def set_feedback(message, type="success"):
    st.session_state['feedback_msg'] = message
    st.session_state['feedback_type'] = type

def show_feedback():
    if 'feedback_msg' in st.session_state and st.session_state['feedback_msg']:
        msg = st.session_state['feedback_msg']
        typ = st.session_state.get('feedback_type', 'success')
        if typ == "success": st.success(msg)
        elif typ == "error": st.error(msg)
        elif typ == "warning": st.warning(msg)
        st.session_state['feedback_msg'] = None

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

# --- ROBUST UPDATE FUNCTION (THE FIX) ---
def robust_update(sheet, phone_number, col_index, value):
    """Finds the row by Phone Number before updating. Prevents row mismatch errors."""
    try:
        # Find cell with the specific phone number
        # We assume Phone is in the first 5 columns to speed up search, or search whole sheet
        cell = sheet.find(phone_number)
        if cell:
            sheet.update_cell(cell.row, col_index, value)
            return True, "Updated"
        else:
            return False, "Lead not found (Deleted?)"
    except gspread.exceptions.APIError:
        time.sleep(1) # Wait and retry once if API is busy
        try:
            cell = sheet.find(phone_number)
            if cell:
                sheet.update_cell(cell.row, col_index, value)
                return True, "Updated"
        except:
            return False, "API Error (Try again)"
    except Exception as e:
        return False, str(e)

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

def phone_call_btn(phone_number):
    return f"""<a href="tel:{phone_number}" style="display:inline-block;background-color:#28a745;color:white;padding:5px 12px;border-radius:4px;text-decoration:none;">📞 Call</a>"""

# --- VIEW 1: LEADS DASHBOARD ---
def show_crm_dashboard(users_df):
    show_feedback()
    
    # Refresh data
    leads_data = leads_sheet.get_all_records()
    leads_df = pd.DataFrame(leads_data)

    # Filter Logic
    if st.session_state['role'] == "Telecaller":
        col_match = [c for c in leads_df.columns if "Assigned" in c]
        if col_match:
            leads_df = leads_df[
                (leads_df[col_match[0]] == st.session_state['username']) | 
                (leads_df[col_match[0]] == st.session_state['name']) |
                (leads_df[col_match[0]] == "TC1")
            ]

    # ADD LEAD
    with st.expander("➕ Naya Lead Jodein", expanded=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Customer Ka Naam")
        phone = c2.text_input("Phone Number (10 Digits)")
        c3, c4 = st.columns(2)
        source = c3.selectbox("Source", ["Meta Ads", "Canopy", "Agent", "Others"])
        agent_name = ""
        if source == "Agent": agent_name = c4.text_input("Agent Ka Naam")
        
        assigned_to = st.session_state['username'] 
        if st.session_state['role'] == "Manager":
            all_users = users_df['Username'].tolist()
            assigned_to = st.selectbox("Assign To", all_users, index=all_users.index(st.session_state['username']) if st.session_state['username'] in all_users else 0)
        
        if st.button("💾 Save Lead", type="primary"):
            if not name: st.error("⚠️ Naam zaroori hai.")
            elif not phone.isdigit() or len(phone) != 10: st.error("⚠️ Phone number galat hai.")
            else:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                new_row = ["L-New", ts, name, phone, source, agent_name, assigned_to, "Naya Lead"]
                leads_sheet.append_row(new_row)
                set_feedback(f"✅ Lead '{name}' Saved!")
                st.rerun()

    st.divider()
    if not leads_df.empty and 'Client Name' in leads_df.columns:
        leads_df = leads_df[leads_df['Client Name'] != ""]

    if leads_df.empty: st.info("📭 Koi leads nahi hain.")

    status_options = [
        "Naya Lead", "Call Uthaya Nahi / Busy", "Baat Hui - Interested",
        "Site Visit Scheduled", "Visit Done - Soch Raha Hai",
        "Faltu / Agent / Spam", "Not Interested (Mehenga Hai)", "Sold (Plot Bik Gaya)"
    ]

    for i, row in leads_df.iterrows():
        name = row.get('Client Name', 'Unknown')
        status = row.get('Status', 'Naya Lead')
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        
        icon = "⚪"
        if "Sold" in status: icon = "🟢"
        if "Faltu" in status or "Not Interested" in status: icon = "🔴"
        if "Visit" in status: icon = "🚕"
        if "Naya" in status: icon = "⚡"
        if "Interested" in status: icon = "🔹"
        
        with st.expander(f"{icon} {name} | {status}"):
            instr = "❓ Update Status"
            if "Naya" in status: instr = "⚡ ACTION: Abhi call karein."
            elif "Busy" in status: instr = "⏰ ACTION: 4 ghante baad try karein."
            elif "Interested" in status: instr = "💬 ACTION: WhatsApp par brochure bhejein."
            elif "Visit Scheduled" in status: instr = "📍 ACTION: Visit confirm karein."
            elif "Visit Done" in status: instr = "🤝 ACTION: Closing ke liye push karein."
            elif "Faltu" in status: instr = "🗑️ ACTION: Ignore karein."
            elif "Sold" in status: instr = "🎉 ACTION: Party!"
            
            if "🗑️" in instr or "❌" in instr: st.error(instr)
            elif "🎉" in instr: st.success(instr)
            else: st.info(instr)
            
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.write(f"📞 **{phone}**")
                st.write(f"📌 {row.get('Source', '-')}")
                if row.get('Agent Name'): st.write(f"👤 {row.get('Agent Name')}")
                st.caption(f"Assigned: {row.get('Assigned', '-')}")
            with c2:
                st.markdown(phone_call_btn(phone), unsafe_allow_html=True)
            with c3:
                st.link_button("💬 WhatsApp", f"https://wa.me/91{phone}?text=Namaste {name}")
            
            with st.form(f"u_{i}"):
                ns = st.selectbox("Status Badlein", status_options, key=f"s_{i}")
                note = st.text_input("Note", key=f"n_{i}")
                
                if st.form_submit_button("💾 Update"):
                    # --- NEW ROBUST UPDATE LOGIC ---
                    try:
                        headers = leads_sheet.row_values(1)
                        try: s_idx = headers.index("Status") + 1; n_idx = headers.index("Notes") + 1
                        except: s_idx=8; n_idx=12
                        
                        # Use Phone Number to find exact row (Prevention of Race Condition)
                        success, msg = robust_update(leads_sheet, phone, s_idx, ns)
                        
                        if success:
                            if note: robust_update(leads_sheet, phone, n_idx, note)
                            set_feedback(f"✅ {name} updated!")
                            st.rerun()
                        else:
                            st.error(f"❌ Error: {msg}")
                    except Exception as e:
                        st.error(f"System Error: {e}")

# --- VIEW 2: ANALYTICS ---
def show_analytics_dashboard():
    st.header("📊 Business Insights")
    leads_data = leads_sheet.get_all_records()
    df = pd.DataFrame(leads_data)
    
    if df.empty:
        st.info("No data yet.")
        return

    total = len(df)
    sold = len(df[df['Status'].str.contains("Sold", na=False)])
    junk = len(df[df['Status'].str.contains("Faltu|Spam|Not Interested", na=False)])
    interested = len(df[df['Status'].str.contains("Interested|Visit", na=False)])
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Leads", total)
    m2.metric("🎉 Sold", sold)
    m3.metric("🔥 Interested", interested)
    m4.metric("🗑️ Junk", junk)
    
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📢 Source Analysis")
        if 'Source' in df.columns: st.bar_chart(df['Source'].value_counts())
    with c2:
        st.subheader("🕵️ Quality Check")
        junk_rate = round((junk / total) * 100) if total > 0 else 0
        st.write(f"**Bad Lead %:** {junk_rate}%")
        st.progress(junk_rate / 100)
        if junk_rate > 40: st.error("⚠️ Ads check karein. Junk leads zyada hain.")
        else: st.success("✅ Quality control acha hai.")

# --- VIEW 3: ADMIN ---
def show_admin_panel(users_df, users_sheet):
    st.header("⚙️ Admin Panel")
    show_feedback()

    ac1, ac2 = st.columns([1, 2])
    with ac1:
        st.subheader("Create User")
        with st.form("new_user", clear_on_submit=True):
            new_u = st.text_input("Username")
            new_p = st.text_input("Password", type="password")
            new_n = st.text_input("Name")
            new_r = st.selectbox("Role", ["Telecaller", "Sales Specialist", "Manager"])
            if st.form_submit_button("Create"):
                if new_u in users_df['Username'].values: st.error("Exists!")
                else:
                    users_sheet.append_row([new_u, hash_pass(new_p), new_r, new_n])
                    set_feedback(f"✅ User {new_u} created")
                    st.rerun()
    with ac2:
        st.subheader("Team List")
        st.dataframe(users_df[['Name', 'Username', 'Role']], use_container_width=True, hide_index=True)
        options = [u for u in users_df['Username'].unique() if u != st.session_state['username']]
        if options:
            del_target = st.selectbox("Delete User", options)
            if st.button("❌ Delete"):
                cell = users_sheet.find(del_target)
                users_sheet.delete_rows(cell.row)
                set_feedback(f"🗑️ Deleted {del_target}")
                st.rerun()

# --- MAIN ---
if st.session_state['role'] == "Manager":
    tab1, tab2, tab3 = st.tabs(["🏠 Dashboard", "📊 Insights", "⚙️ Admin"])
    with tab1: show_crm_dashboard(users_df)
    with tab2: show_analytics_dashboard()
    with tab3: show_admin_panel(users_df, users_sheet)
else:
    show_crm_dashboard(users_df)
