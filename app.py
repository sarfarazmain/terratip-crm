import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import hashlib
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="TerraTip CRM", layout="wide", page_icon="🏡")

# --- HIDE STREAMLIT BRANDING ---
hide_bar = """
    <style>
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppDeployButton {display: none;}
        [data-testid="stElementToolbar"] {display: none;}
        [data-testid="stDecoration"] {display: none;}
    </style>
"""
st.markdown(hide_bar, unsafe_allow_html=True)

# --- GLOBAL MESSAGE RELAY ---
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

# --- 1. DATABASE CONNECTION ---
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
    return client.open_by_key(files[0]['id'])

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_auth_system(sh):
    try: ws = sh.worksheet("Users")
    except:
        ws = sh.add_worksheet(title="Users", rows=100, cols=5)
        ws.append_row(["Username", "Password", "Role", "Name"])
        ws.append_row(["admin", hash_pass("admin123"), "Manager", "System Admin"])
    return ws

def check_credentials(username, password, users_df):
    hashed = hash_pass(password)
    user_row = users_df[users_df['Username'] == username]
    if not user_row.empty:
        if user_row.iloc[0]['Password'] == hashed: return user_row.iloc[0]
    return None

def robust_update(sheet, phone_number, col_index, value):
    try:
        cell = sheet.find(phone_number)
        if cell:
            sheet.update_cell(cell.row, col_index, value)
            return True, "Updated"
        return False, "Lead not found"
    except gspread.exceptions.APIError:
        time.sleep(1)
        try:
            cell = sheet.find(phone_number)
            if cell:
                sheet.update_cell(cell.row, col_index, value)
                return True, "Updated"
        except: return False, "API Error"
    except Exception as e: return False, str(e)

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

# --- 3. SESSION & LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# Auto-Login via URL
if not st.session_state['logged_in']:
    qp = st.query_params
    if "u" in qp and "k" in qp:
        u_row = users_df[users_df['Username'] == qp["u"]]
        if not u_row.empty and u_row.iloc[0]['Password'] == qp["k"]:
            st.session_state.update({'logged_in':True, 'username':u_row.iloc[0]['Username'], 
                                     'role':u_row.iloc[0]['Role'], 'name':u_row.iloc[0]['Name']})
            st.rerun()

if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 TerraTip Login")
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login Karein"):
                # Reload users to check fresh data
                users_df = pd.DataFrame(users_sheet.get_all_records())
                info = check_credentials(u, p, users_df)
                if info is not None:
                    st.session_state.update({'logged_in':True, 'username':info['Username'], 
                                             'role':info['Role'], 'name':info['Name']})
                    st.query_params["u"] = info['Username']; st.query_params["k"] = info['Password']
                    st.rerun()
                else: st.error("❌ Galat login")
    st.stop()

# --- 4. DASHBOARD LOGIC ---
st.sidebar.title("TerraTip CRM 🏡")
st.sidebar.write(f"👤 **{st.session_state['name']}**")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.query_params.clear()
    st.rerun()

def phone_btn(num): return f"""<a href="tel:{num}" style="display:inline-block;background-color:#28a745;color:white;padding:5px 12px;border-radius:4px;text-decoration:none;">📞 Call</a>"""

# --- LIVE FEED FRAGMENT (AUTO REFRESH) ---
# This part refreshes every 10 seconds automatically!
@st.fragment(run_every=10)
def show_live_leads_list():
    # Fetch Fresh Data
    try:
        data = leads_sheet.get_all_records()
        df = pd.DataFrame(data)
    except: return # Fail silently on network blip
    
    # Filter
    if st.session_state['role'] == "Telecaller":
        c_match = [c for c in df.columns if "Assigned" in c]
        if c_match:
            df = df[(df[c_match[0]] == st.session_state['username']) | 
                    (df[c_match[0]] == st.session_state['name']) |
                    (df[c_match[0]] == "TC1")]

    if not df.empty and 'Client Name' in df.columns:
        df = df[df['Client Name'] != ""]

    if df.empty:
        st.info("📭 Abhi koi leads nahi hain.")
        return

    st.caption(f"⚡ Live Updates On (Auto-refresh every 10s)")
    
    status_opts = ["Naya Lead", "Call Uthaya Nahi / Busy", "Baat Hui - Interested", "Site Visit Scheduled", "Visit Done - Soch Raha Hai", "Faltu / Agent / Spam", "Not Interested (Mehenga Hai)", "Sold (Plot Bik Gaya)"]

    for i, row in df.iterrows():
        name = row.get('Client Name', 'Unknown')
        status = row.get('Status', 'Naya Lead')
        phone = str(row.get('Phone', '')).replace(',', '').replace('.', '')
        
        icon = "⚪"
        if "Sold" in status: icon = "🟢"
        elif "Faltu" in status or "Not" in status: icon = "🔴"
        elif "Visit" in status: icon = "🚕"
        elif "Naya" in status: icon = "⚡"
        elif "Interested" in status: icon = "🔹"
        
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
            with c2: st.markdown(phone_btn(phone), unsafe_allow_html=True)
            with c3: st.link_button("💬 WhatsApp", f"https://wa.me/91{phone}")
            
            # Form inside fragment
            with st.form(f"u_{i}"):
                ns = st.selectbox("Status", status_opts, key=f"s_{i}")
                note = st.text_input("Note", key=f"n_{i}")
                if st.form_submit_button("💾 Update"):
                    try:
                        h = leads_sheet.row_values(1)
                        s_idx = h.index("Status") + 1 if "Status" in h else 8
                        n_idx = h.index("Notes") + 1 if "Notes" in h else 12
                        
                        succ, msg = robust_update(leads_sheet, phone, s_idx, ns)
                        if succ:
                            if note: robust_update(leads_sheet, phone, n_idx, note)
                            set_feedback(f"✅ {name} updated!")
                            st.rerun()
                        else: st.error(msg)
                    except Exception as e: st.error(f"Err: {e}")

# --- STATIC ADD FORM (NO REFRESH WHILE TYPING) ---
def show_add_lead_form(users_df):
    with st.expander("➕ Naya Lead Jodein", expanded=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Customer Ka Naam")
        phone = c2.text_input("Phone Number")
        c3, c4 = st.columns(2)
        src = c3.selectbox("Source", ["Meta Ads", "Canopy", "Agent", "Others"])
        ag = c4.text_input("Agent Name") if src == "Agent" else ""
        
        assign = st.session_state['username']
        if st.session_state['role'] == "Manager":
            all_u = users_df['Username'].tolist()
            assign = st.selectbox("Assign To", all_u, index=all_u.index(assign) if assign in all_u else 0)
        
        if st.button("💾 Save Lead"):
            if not name or not phone: st.error("⚠️ Name/Phone zaroori hai")
            else:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                leads_sheet.append_row(["L-New", ts, name, phone, src, ag, assign, "Naya Lead"])
                set_feedback(f"✅ Lead '{name}' Saved!")
                st.rerun()

# --- MAIN PAGE ---
def show_dashboard(users_df):
    show_feedback()
    show_add_lead_form(users_df) # Static Part
    st.divider()
    show_live_leads_list() # Live Part (Auto Refresh)

def show_analytics():
    st.header("📊 Insights")
    df = pd.DataFrame(leads_sheet.get_all_records())
    if df.empty: return
    
    tot = len(df); sold = len(df[df['Status'].str.contains("Sold", na=False)])
    junk = len(df[df['Status'].str.contains("Faltu|Not", na=False)])
    m1, m2, m3 = st.columns(3)
    m1.metric("Total", tot); m2.metric("Sold", sold); m3.metric("Junk", junk)
    
    st.divider()
    c1, c2 = st.columns(2)
    with c1: 
        if 'Source' in df.columns: st.bar_chart(df['Source'].value_counts())
    with c2:
        jr = round((junk/tot)*100) if tot>0 else 0
        st.write(f"**Junk %:** {jr}%"); st.progress(jr/100)

def show_admin(users_df):
    st.header("⚙️ Admin")
    show_feedback()
    c1, c2 = st.columns([1,2])
    with c1:
        with st.form("nu", clear_on_submit=True):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            n = st.text_input("Name"); r = st.selectbox("Role", ["Telecaller", "Sales Specialist", "Manager"])
            if st.form_submit_button("Create"):
                if u in users_df['Username'].values: st.error("Exists")
                else: 
                    users_sheet.append_row([u, hash_pass(p), r, n])
                    set_feedback(f"✅ Created {u}"); st.rerun()
    with c2:
        st.dataframe(users_df[['Name','Username','Role']], hide_index=True)
        opts = [x for x in users_df['Username'].unique() if x != st.session_state['username']]
        if opts:
            dt = st.selectbox("Delete", opts)
            if st.button("❌ Delete"):
                users_sheet.delete_rows(users_sheet.find(dt).row)
                set_feedback(f"Deleted {dt}"); st.rerun()

if st.session_state['role'] == "Manager":
    t1, t2, t3 = st.tabs(["🏠 CRM", "📊 Insights", "⚙️ Admin"])
    with t1: show_dashboard(users_df)
    with t2: show_analytics()
    with t3: show_admin(users_df)
else:
    show_dashboard(users_df)
